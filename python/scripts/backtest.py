"""Backtest a single strategy on one symbol.

Usage:
    set ALPACA_KEY_ID=...
    set ALPACA_SECRET_KEY=...
    python -m scripts.backtest --symbol SPY --timeframe 5Min --strategy momentum \
        --start 2024-01-01 --end 2024-06-30
"""
from __future__ import annotations

import argparse
from datetime import datetime

from trading.backtest import BacktestConfig, run_backtest, summarize
from trading.backtest.costs import CostModel
from trading.data import AlpacaLoader, BarSpec
from trading.data.alpaca_loader import utc
from trading.features import build_features
from trading.strategies import BuyAndHold, MomentumCrossover, RsiMeanReversion


STRATEGIES = {
    "buy_hold": lambda: BuyAndHold(),
    "momentum": lambda: MomentumCrossover(),
    "mean_reversion": lambda: RsiMeanReversion(),
}

BARS_PER_YEAR = {
    "1Min": 252 * 390,
    "5Min": 252 * 78,
    "15Min": 252 * 26,
    "1Hour": 252 * 6.5,
    "1Day": 252,
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", default="5Min",
                   choices=list(BARS_PER_YEAR.keys()))
    p.add_argument("--strategy", required=True, choices=list(STRATEGIES.keys()))
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--cash", type=float, default=100_000.0)
    p.add_argument("--spread-bps", type=float, default=2.0)
    p.add_argument("--slippage-bps", type=float, default=1.0)
    args = p.parse_args()

    loader = AlpacaLoader()
    spec = BarSpec(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=utc(args.start),
        end=utc(args.end),
    )
    print(f"Loading {spec.symbol} {spec.timeframe} {args.start}..{args.end} ...")
    ohlcv = loader.load(spec)
    print(f"  got {len(ohlcv):,} bars")
    if ohlcv.empty:
        print("No data. Check symbol, dates, or your Alpaca credentials.")
        return

    feats = build_features(ohlcv)
    # Trim ohlcv to feature-available range (after warm-up)
    ohlcv = ohlcv.loc[feats.index[0]:]
    print(f"  features ready: {len(feats):,} bars after warm-up, {feats.shape[1]} features")

    strat = STRATEGIES[args.strategy]()
    sig = strat.signal(feats)

    cfg = BacktestConfig(
        starting_cash=args.cash,
        cost=CostModel(spread_bps=args.spread_bps, slippage_bps=args.slippage_bps),
    )
    res = run_backtest(ohlcv, sig, cfg=cfg, strategy_name=strat.name, symbol=args.symbol)
    s = summarize(res, bars_per_year=BARS_PER_YEAR[args.timeframe])

    print()
    print(f"=== {s.strategy} on {s.symbol} ({args.timeframe}) ===")
    print(f"bars              : {s.bars:,}")
    print(f"total return      : {s.total_return * 100:+.2f}%")
    print(f"annualized return : {s.annualized_return * 100:+.2f}%")
    print(f"annualized vol    : {s.annualized_vol * 100:.2f}%")
    print(f"Sharpe            : {s.sharpe:.2f}")
    print(f"Sortino           : {s.sortino:.2f}")
    print(f"max drawdown      : {s.max_drawdown * 100:.2f}%")
    print(f"Calmar            : {s.calmar:.2f}")
    print(f"avg turnover/bar  : {s.avg_turnover:.4f}")
    print(f"total cost drag   : {s.cost_drag_total * 100:.2f}%")
    print(f"hit rate          : {s.hit_rate * 100:.1f}%")
    print(f"final equity      : ${res.equity.iloc[-1]:,.2f}")


if __name__ == "__main__":
    main()
