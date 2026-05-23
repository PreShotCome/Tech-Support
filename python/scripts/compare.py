"""Compare all baseline strategies on the same symbol/timeframe.

Usage:
    python -m scripts.compare --symbol SPY --timeframe 5Min \
        --start 2024-01-01 --end 2024-06-30
"""
from __future__ import annotations

import argparse

from trading.backtest import BacktestConfig, run_backtest, summarize
from trading.backtest.costs import CostModel
from trading.data import AlpacaLoader, BarSpec
from trading.data.alpaca_loader import utc
from trading.features import build_features
from trading.strategies import BuyAndHold, MomentumCrossover, RsiMeanReversion


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
    p.add_argument("--timeframe", default="5Min", choices=list(BARS_PER_YEAR.keys()))
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--cash", type=float, default=100_000.0)
    args = p.parse_args()

    loader = AlpacaLoader()
    spec = BarSpec(args.symbol, args.timeframe, utc(args.start), utc(args.end))
    ohlcv = loader.load(spec)
    if ohlcv.empty:
        print("No data.")
        return
    feats = build_features(ohlcv)
    ohlcv = ohlcv.loc[feats.index[0]:]

    cfg = BacktestConfig(starting_cash=args.cash, cost=CostModel())
    strategies = [BuyAndHold(), MomentumCrossover(), RsiMeanReversion()]

    rows = []
    for strat in strategies:
        sig = strat.signal(feats)
        res = run_backtest(ohlcv, sig, cfg=cfg, strategy_name=strat.name, symbol=args.symbol)
        rows.append(summarize(res, bars_per_year=BARS_PER_YEAR[args.timeframe]).as_row())

    # Print a tidy comparison table.
    cols = ["strategy", "total_return", "annual_return", "sharpe", "max_dd",
            "calmar", "hit_rate", "cost_drag"]
    widths = {c: max(len(c), 10) for c in cols}
    print(" | ".join(c.ljust(widths[c]) for c in cols))
    print("-" * (sum(widths.values()) + 3 * (len(cols) - 1)))
    for row in rows:
        def fmt(c):
            v = row[c]
            if c == "strategy":
                return str(v).ljust(widths[c])
            return f"{v * 100:>+9.2f}%".ljust(widths[c]) if c in (
                "total_return", "annual_return", "max_dd", "hit_rate", "cost_drag"
            ) else f"{v:>+9.2f}".ljust(widths[c])
        print(" | ".join(fmt(c) for c in cols))


if __name__ == "__main__":
    main()
