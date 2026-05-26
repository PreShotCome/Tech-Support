"""Trading tools — the agent talks to the existing paper-trading
infrastructure through these. Wraps the same Alpaca client paper_runner
uses, so the brain and the rebalancer agree on account state.

Tools registered here:
  - portfolio:        current Alpaca paper positions and equity
  - rebalance_plan:   dry-run rebalance, show what would be traded
  - shadow_report:    last N shadow snapshots and cumulative track record
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .base import Tool


def _trading_client():
    from alpaca.trading.client import TradingClient
    key = os.environ.get("ALPACA_KEY_ID", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not key or not secret:
        raise RuntimeError("ALPACA_KEY_ID / ALPACA_SECRET_KEY not set.")
    return TradingClient(key, secret, paper=True)


def _portfolio() -> dict[str, Any]:
    c = _trading_client()
    acct = c.get_account()
    positions = c.get_all_positions()
    return {
        "equity": float(acct.equity),
        "cash": float(acct.cash),
        "buying_power": float(acct.buying_power),
        "last_equity": float(acct.last_equity),
        "n_positions": len(positions),
        "positions": [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "avg_entry_price": float(p.avg_entry_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }
            for p in positions
        ],
    }


def _rebalance_plan(min_trade_dollars: float = 50.0,
                    min_drift_pct: float = 0.0) -> dict[str, Any]:
    # Lazy-import the existing planner so we don't duplicate logic.
    from scripts.paper_runner import _client, build_plan, _safety_check
    from trading.universes import DEFAULT_UNIVERSE
    client = _client()
    _safety_check(client)
    plan, drift_table = build_plan(
        client, DEFAULT_UNIVERSE,
        min_trade_dollars=min_trade_dollars,
        min_drift_pct=min_drift_pct,
    )
    return {
        "min_trade_dollars": min_trade_dollars,
        "min_drift_pct":     min_drift_pct,
        "n_trades_planned":  len(plan),
        "n_in_band":         sum(1 for r in drift_table if r["in_band"]),
        "trades": [
            {
                "symbol": p.symbol,
                "last": p.last_price,
                "current_value": p.current_value,
                "target_value": p.target_value,
                "delta_value": p.delta_value,
                "delta_qty": p.delta_qty,
                "side": "BUY" if p.delta_value > 0 else "SELL",
            }
            for p in plan
        ],
        # Per-symbol drift snapshot for every symbol, not just the ones
        # we're trading. This is what the human reads to confirm the
        # rebalancer is doing the right thing on quiet days.
        "drift_table": drift_table,
    }


def _shadow_report(last_n: int = 12, log_path: str = "shadow_log.jsonl") -> dict[str, Any]:
    p = Path(log_path)
    if not p.exists():
        return {"snapshots": 0, "note": f"no shadow log at {p}"}
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        return {"snapshots": 0}

    # Compute cumulative shadow vs bench using the same logic as paper_shadow.
    def ret(weights, prev_p, curr_p):
        r = 0.0
        for sym, w in weights.items():
            p0, p1 = prev_p.get(sym), curr_p.get(sym)
            if p0 is None or p1 is None or p0 <= 0:
                continue
            r += w * (p1 / p0 - 1.0)
        return r

    shadow_cum, bench_cum = 1.0, 1.0
    weekly = []
    for i in range(1, len(rows)):
        prev, curr = rows[i - 1], rows[i]
        sret = ret(prev["shadow_weights"], prev["prices"], curr["prices"])
        bret = ret(prev["bench_weights"], prev["prices"], curr["prices"])
        shadow_cum *= 1.0 + sret
        bench_cum *= 1.0 + bret
        weekly.append({
            "ts": curr["ts"], "shadow_pct": sret * 100, "bench_pct": bret * 100,
            "alpha_pct": (sret - bret) * 100,
        })

    return {
        "snapshots": len(rows),
        "comparisons": len(weekly),
        "shadow_total_return_pct": (shadow_cum - 1) * 100,
        "bench_total_return_pct": (bench_cum - 1) * 100,
        "cumulative_alpha_pct": (shadow_cum - bench_cum) * 100,
        "weekly_tail": weekly[-min(last_n, len(weekly)):],
    }


PORTFOLIO_TOOL = Tool(
    name="portfolio",
    description=("Get the current paper-trading account: equity, cash, "
                 "buying power, and all open positions with P&L."),
    parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_portfolio,
)

REBALANCE_PLAN_TOOL = Tool(
    name="rebalance_plan",
    description=("Dry-run the equal-weight rebalance — return the trades "
                 "that would be placed (no actual orders), plus the "
                 "per-symbol drift_table for every symbol whether or not "
                 "it's being traded. A symbol is only skipped when BOTH "
                 "thresholds say skip: |delta_value| < min_trade_dollars "
                 "AND |drift_pct| < min_drift_pct. Pass min_drift_pct=0 "
                 "(default) for legacy absolute-dollar-only behavior; "
                 "pass e.g. 3 to add a 3% relative band that scales with "
                 "account equity."),
    parameters_schema={
        "type": "object",
        "properties": {
            "min_trade_dollars": {
                "type": "number",
                "description": "Absolute dollar floor. Skip trades smaller than this. Default 50.",
            },
            "min_drift_pct": {
                "type": "number",
                "description": (
                    "Relative drift band (percent of target). Skip "
                    "symbols whose drift is within this band AND below "
                    "the dollar floor. Default 0 (band disabled)."
                ),
            },
        },
        "additionalProperties": False,
    },
    handler=_rebalance_plan,
)

SHADOW_REPORT_TOOL = Tool(
    name="shadow_report",
    description=("Read the shadow-mode learning log and return the "
                 "track record: shadow vs equal-weight cumulative return, "
                 "alpha, and the most recent weekly comparisons."),
    parameters_schema={
        "type": "object",
        "properties": {
            "last_n": {"type": "integer", "description": "Number of recent weeks to include. Default 12."},
            "log_path": {"type": "string", "description": "Path to shadow_log.jsonl. Default 'shadow_log.jsonl'."},
        },
        "additionalProperties": False,
    },
    handler=_shadow_report,
)


def _orders(status: str = "open", limit: int = 50) -> dict[str, Any]:
    """Pull orders from Alpaca paper. status='open' shows pending/accepted
    only; status='closed' shows filled/cancelled/expired; status='all'
    shows everything."""
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    c = _trading_client()
    status_map = {
        "open": QueryOrderStatus.OPEN,
        "closed": QueryOrderStatus.CLOSED,
        "all": QueryOrderStatus.ALL,
    }
    qs = status_map.get(status.lower(), QueryOrderStatus.OPEN)
    req = GetOrdersRequest(status=qs, limit=int(limit))
    orders = c.get_orders(req)

    rows = []
    by_status: dict[str, int] = {}
    for o in orders:
        s = getattr(o, "status", "")
        s_str = s.value if hasattr(s, "value") else str(s)
        by_status[s_str] = by_status.get(s_str, 0) + 1
        rows.append({
            "symbol": o.symbol,
            "side": (o.side.value if hasattr(o.side, "value") else str(o.side)),
            "qty": float(o.qty) if o.qty else None,
            "notional": float(o.notional) if o.notional else None,
            "filled_qty": float(o.filled_qty) if o.filled_qty else 0.0,
            "filled_avg_price": (float(o.filled_avg_price)
                                 if o.filled_avg_price else None),
            "status": s_str,
            "submitted_at": str(o.submitted_at) if o.submitted_at else None,
            "filled_at": str(o.filled_at) if o.filled_at else None,
        })

    return {
        "status_filter": status,
        "n_orders": len(rows),
        "by_status": by_status,
        "orders": rows,
    }


ORDERS_TOOL = Tool(
    name="orders",
    description=("List Alpaca paper orders. Use status='open' (default) "
                 "to see pending/accepted orders, 'closed' to see "
                 "filled/cancelled/expired, or 'all' for everything."),
    parameters_schema={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "open | closed | all. Default 'open'.",
            },
            "limit": {
                "type": "integer",
                "description": "Max number of orders to return. Default 50.",
            },
        },
        "additionalProperties": False,
    },
    handler=_orders,
)


def _market_clock() -> dict[str, Any]:
    """Is the US equity market open right now? Returns next open / next close."""
    c = _trading_client()
    clock = c.get_clock()
    return {
        "is_open": bool(clock.is_open),
        "timestamp": str(clock.timestamp),
        "next_open": str(clock.next_open),
        "next_close": str(clock.next_close),
    }


MARKET_CLOCK_TOOL = Tool(
    name="market_clock",
    description=("Check whether the US equity market is open right now, "
                 "and when it next opens/closes."),
    parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_market_clock,
)


def register(registry) -> None:
    for t in (PORTFOLIO_TOOL, REBALANCE_PLAN_TOOL, SHADOW_REPORT_TOOL,
              ORDERS_TOOL, MARKET_CLOCK_TOOL):
        registry.register(t)
