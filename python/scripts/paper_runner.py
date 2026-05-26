"""Live paper-trading runner for the equal-weight megacap basket.

What this does:
  1. Connects to Alpaca paper trading.
  2. Reads current account equity + positions.
  3. Computes target dollar value per symbol = equity / N (equal weight).
  4. For each symbol: if the difference between current and target is
     bigger than --min-trade-dollars, submits a market order to close
     the gap.
  5. Logs every decision.

What this does NOT do:
  - Use any ML model. Walk-forward proved the models we tested lose to
    this benchmark. The strategy IS the basket.
  - Trade options, futures, or anything other than the listed symbols.
  - Run continuously. Schedule it with Windows Task Scheduler at the
    cadence you want (weekly is sensible).

Safety:
  - Refuses to run against a non-paper Alpaca endpoint.
  - Dry-run is the default. Pass --execute to actually place orders.

Usage:
    python -m scripts.paper_runner --dry-run         # see what it would do
    python -m scripts.paper_runner --execute         # actually trade
    python -m scripts.paper_runner --cancel-open     # cancel open orders first
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scripts.train_basket import DEFAULT_UNIVERSE


PAPER_ENDPOINT_HOST = "paper-api.alpaca.markets"
DECISION_LOG = Path("decisions.jsonl")


def _log_decision(record: dict, path: Path = DECISION_LOG) -> None:
    """Append a structured decision record to decisions.jsonl. Local
    helper so we don't reach across to agent/tools/safety.py from the
    runner — both writers agree on the file format (JSON-per-line)."""
    record = {"logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              **record}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception as e:
        # Never let a logging failure break a trade
        print(f"  (decision log write failed: {e})", file=sys.stderr)


def _client():
    from alpaca.trading.client import TradingClient
    key = os.environ.get("ALPACA_KEY_ID", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not key or not secret:
        print("ALPACA_KEY_ID / ALPACA_SECRET_KEY not set in env.", file=sys.stderr)
        sys.exit(2)
    c = TradingClient(key, secret, paper=True)
    return c


def _data_client():
    from alpaca.data.historical import StockHistoricalDataClient
    key = os.environ.get("ALPACA_KEY_ID", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    return StockHistoricalDataClient(key, secret)


def _safety_check(client) -> None:
    """Refuse to run if we are pointed at the live trading endpoint."""
    host = getattr(client, "_base_url", "")
    if PAPER_ENDPOINT_HOST not in str(host) and "paper" not in str(host).lower():
        print(f"REFUSING TO RUN: client base url is {host!r}, not paper.")
        sys.exit(2)


@dataclass
class Plan:
    symbol: str
    last_price: float
    current_value: float
    target_value: float
    delta_value: float
    delta_qty: float


def latest_prices(symbols: list[str]) -> dict[str, float]:
    from alpaca.data.requests import StockLatestTradeRequest
    dc = _data_client()
    req = StockLatestTradeRequest(symbol_or_symbols=symbols)
    trades = dc.get_stock_latest_trade(req)
    return {sym: float(t.price) for sym, t in trades.items()}


def build_plan(client, symbols: list[str],
               min_trade_dollars: float,
               min_drift_pct: float = 0.0,
               ) -> tuple[list[Plan], list[dict]]:
    """Build the rebalance plan. Returns (trades, drift_table).

    A symbol is skipped only when BOTH thresholds say skip:
      - |delta_value| < min_trade_dollars  (absolute floor)
      - |drift_pct|   < min_drift_pct      (relative band)
    Pass min_drift_pct=0 to disable the band (legacy behavior).

    drift_table is the per-symbol drift snapshot for EVERY universe
    symbol plus orphans, even ones that didn't make the trades list.
    That's the table a human actually wants to read on a quiet
    rebalance day.

    TODO: account for pending transfers / contributions / withdrawals
    before computing target_per. Currently `equity` is settled cash +
    market value; an in-flight deposit would make target_per stale.
    Low-priority on paper; revisit at live.
    """
    account = client.get_account()
    equity = float(account.equity)
    print(f"Account equity: ${equity:,.2f}")
    print(f"Buying power:   ${float(account.buying_power):,.2f}")

    positions = {p.symbol: p for p in client.get_all_positions()}
    prices = latest_prices(symbols)
    n = len(symbols)
    target_per = equity / n

    plan: list[Plan] = []
    drift_table: list[dict] = []

    for sym in symbols:
        price = prices.get(sym)
        if price is None:
            print(f"  {sym}: no price, skipping")
            continue
        cur_val = float(positions[sym].market_value) if sym in positions else 0.0
        delta_val = target_per - cur_val
        drift_pct = (delta_val / target_per * 100.0) if target_per > 0 else 0.0

        skip_by_dollars = abs(delta_val) < min_trade_dollars
        skip_by_pct     = abs(drift_pct)  < min_drift_pct
        skipped = skip_by_dollars and skip_by_pct

        drift_table.append({
            "symbol":        sym,
            "current_value": cur_val,
            "target_value":  target_per,
            "delta_value":   delta_val,
            "drift_pct":     drift_pct,
            "in_band":       skipped,
            "reason":        "in_band" if skipped else "would_trade",
        })

        if skipped:
            continue

        delta_qty = delta_val / price
        plan.append(Plan(
            symbol=sym, last_price=price,
            current_value=cur_val, target_value=target_per,
            delta_value=delta_val, delta_qty=delta_qty,
        ))

    # Also produce a row for any held symbol that's NOT in the target
    # universe (sell-to-zero so we don't carry orphan positions).
    orphans = [p for sym, p in positions.items() if sym not in symbols]
    for p in orphans:
        cur_val = float(p.market_value)
        drift_table.append({
            "symbol":        p.symbol,
            "current_value": cur_val,
            "target_value":  0.0,
            "delta_value":   -cur_val,
            "drift_pct":     None,            # not in target universe
            "in_band":       abs(cur_val) < min_trade_dollars,
            "reason":        "orphan_in_band" if abs(cur_val) < min_trade_dollars else "orphan_close",
        })
        if abs(cur_val) < min_trade_dollars:
            continue
        price = float(p.current_price) if p.current_price else 0.0
        if price <= 0:
            continue
        plan.append(Plan(
            symbol=p.symbol, last_price=price,
            current_value=cur_val, target_value=0.0,
            delta_value=-cur_val, delta_qty=-cur_val / price,
        ))

    # Log the in-band no-op explicitly so the audit trail records
    # "decided not to trade" as a real decision, not silent absence.
    if not plan:
        _log_decision({
            "event":            "skip_rebalance",
            "reason":           "in_band",
            "min_trade_dollars": min_trade_dollars,
            "min_drift_pct":     min_drift_pct,
            "equity":            equity,
            "target_per_symbol": target_per,
            "universe_size":     n,
            "drift_table":       drift_table,
        })

    return plan, drift_table


def submit_orders(client, plan: list[Plan], execute: bool) -> None:
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    if not plan:
        print("\nNothing to rebalance — already within tolerance.")
        return

    print(f"\n{'symbol':<7}  {'last':>10}  {'cur $':>12}  {'tgt $':>12}  {'Δ $':>12}  {'Δ qty':>10}  action")
    print("-" * 90)
    for p in plan:
        side = "BUY " if p.delta_value > 0 else "SELL"
        print(f"{p.symbol:<7}  {p.last_price:>10.2f}  {p.current_value:>12,.2f}  "
              f"{p.target_value:>12,.2f}  {p.delta_value:>+12,.2f}  {p.delta_qty:>+10.4f}  {side}")

    if not execute:
        print("\nDry-run. No orders submitted. Re-run with --execute to trade.")
        return

    print("\nSubmitting orders...")
    for p in plan:
        side = OrderSide.BUY if p.delta_qty > 0 else OrderSide.SELL
        qty = abs(round(p.delta_qty, 4))   # Alpaca fractional shares: 4 decimals
        if qty <= 0:
            continue
        req = MarketOrderRequest(
            symbol=p.symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        try:
            order = client.submit_order(req)
            print(f"  {p.symbol:<7} {side.value:<4} {qty:>10.4f}  order_id={order.id}")
            _log_decision({
                "event":         "order_submitted",
                "reason":        "equal_weight_rebalance",
                "symbol":        p.symbol,
                "side":          side.value,
                "qty":           qty,
                "last_price":    p.last_price,
                "current_value": p.current_value,
                "target_value":  p.target_value,
                "delta_value":   p.delta_value,
                "order_id":      str(getattr(order, "id", "")),
            })
        except Exception as e:
            print(f"  {p.symbol:<7} {side.value:<4} FAILED: {e}")
            _log_decision({
                "event":  "order_failed",
                "reason": "equal_weight_rebalance",
                "symbol": p.symbol,
                "side":   side.value,
                "qty":    qty,
                "error":  str(e),
            })


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="*", default=DEFAULT_UNIVERSE,
                   help="Equal-weight basket. Defaults to 30 megacaps.")
    p.add_argument("--min-trade-dollars", type=float, default=50.0,
                   help="Skip trades smaller than this dollar amount.")
    p.add_argument("--min-drift-pct", type=float, default=0.0,
                   help="Skip trades where |drift| < this %% of target. "
                        "Combines with --min-trade-dollars: both must be "
                        "below threshold for a symbol to be skipped. "
                        "Default 0 (band disabled, legacy behavior).")
    p.add_argument("--execute", action="store_true",
                   help="Actually place orders. Default is dry-run.")
    p.add_argument("--cancel-open", action="store_true",
                   help="Cancel all open orders before rebalancing.")
    args = p.parse_args()

    client = _client()
    _safety_check(client)

    if args.cancel_open:
        print("Cancelling all open orders...")
        try:
            client.cancel_orders()
        except Exception as e:
            print(f"  warning: {e}")

    print(f"Universe: {len(args.symbols)} symbols")
    plan, drift_table = build_plan(
        client, args.symbols,
        min_trade_dollars=args.min_trade_dollars,
        min_drift_pct=args.min_drift_pct,
    )

    # Always show the drift table — it's what the human reads on a
    # quiet rebalance day to confirm the bot is watching.
    print(f"\nDrift table ({len(drift_table)} symbols):")
    print(f"  {'symbol':<7}  {'cur $':>12}  {'tgt $':>12}  {'Δ $':>12}  {'drift %':>8}  reason")
    print("  " + "-" * 72)
    for row in drift_table:
        drift_str = f"{row['drift_pct']:>+7.2f}%" if row['drift_pct'] is not None else "    n/a"
        print(f"  {row['symbol']:<7}  {row['current_value']:>12,.2f}  "
              f"{row['target_value']:>12,.2f}  {row['delta_value']:>+12,.2f}  "
              f"{drift_str}  {row['reason']}")

    submit_orders(client, plan, execute=args.execute)


if __name__ == "__main__":
    main()
