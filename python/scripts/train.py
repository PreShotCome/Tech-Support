"""Train an XGBoost direction classifier and backtest it out-of-sample.

Data split (strictly chronological — no shuffling):
    [start ........ train_frac ...... val_frac ...... 1.0 = end]
    | training              | validation       | test (OOS)  |

Default is train 70% / val 15% / test 15%. Val is used for early
stopping and metric reporting; test is the honest OOS evaluation.

Usage:
    set ALPACA_KEY_ID=...
    set ALPACA_SECRET_KEY=...
    python -m scripts.train --symbol SPY --timeframe 5Min \
        --start 2023-01-01 --end 2024-06-30 --horizon 12
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from trading.backtest import BacktestConfig, run_backtest, summarize
from trading.backtest.costs import CostModel
from trading.data import AlpacaLoader, BarSpec
from trading.data.alpaca_loader import utc
from trading.features import build_features
from trading.labels import forward_direction
from trading.models import XgbDirectionModel
from trading.models.xgb import XgbConfig
from trading.strategies import BuyAndHold, MlSignal
from scripts.compare import BARS_PER_YEAR


def chrono_split(df: pd.DataFrame, train_frac: float, val_frac: float):
    n = len(df)
    a = int(n * train_frac)
    b = int(n * (train_frac + val_frac))
    return df.iloc[:a], df.iloc[a:b], df.iloc[b:]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", default="5Min", choices=list(BARS_PER_YEAR.keys()))
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--horizon", type=int, default=12,
                   help="Bars ahead to predict (default 12 = 1 hour for 5Min bars)")
    p.add_argument("--train-frac", type=float, default=0.70)
    p.add_argument("--val-frac", type=float, default=0.15)
    p.add_argument("--threshold", type=float, default=0.55,
                   help="P(up) threshold to go long. 0.5 = aggressive, 0.6 = picky.")
    p.add_argument("--scale", action="store_true",
                   help="Scale position by confidence rather than 0/1 gating.")
    p.add_argument("--cash", type=float, default=100_000.0)
    p.add_argument("--save", type=Path, default=Path("models/xgb_latest"),
                   help="Path stem to save model.")
    args = p.parse_args()

    loader = AlpacaLoader()
    spec = BarSpec(args.symbol, args.timeframe, utc(args.start), utc(args.end))
    print(f"Loading {spec.symbol} {spec.timeframe} {args.start}..{args.end}")
    ohlcv = loader.load(spec)
    if ohlcv.empty:
        print("No data. Check credentials / date range.")
        return
    print(f"  {len(ohlcv):,} bars")

    feats = build_features(ohlcv)
    y = forward_direction(ohlcv["close"], args.horizon, threshold=0.0)

    # Align features and labels, drop rows where either is NaN
    df = feats.join(y, how="inner").dropna()
    X = df[feats.columns]
    y = df[y.name]

    train, val, test = chrono_split(df, args.train_frac, args.val_frac)
    X_tr, y_tr = train[feats.columns], train[y.name]
    X_va, y_va = val[feats.columns], val[y.name]
    X_te, y_te = test[feats.columns], test[y.name]

    print(f"  train {len(X_tr):,} rows   val {len(X_va):,}   test {len(X_te):,}")
    print(f"  class balance train: {y_tr.mean():.3f}   val: {y_va.mean():.3f}   test: {y_te.mean():.3f}")
    print(f"  horizon: {args.horizon} bars   threshold: {args.threshold}   scaled: {args.scale}")

    model = XgbDirectionModel(horizon=args.horizon, config=XgbConfig())
    report = model.fit(X_tr, y_tr, X_va, y_va)
    print(f"  fit: {report}")

    # Save
    args.save.parent.mkdir(parents=True, exist_ok=True)
    model.save(args.save)
    print(f"  model saved -> {args.save.with_suffix('.xgb.json')} + .meta.json")

    # ---------- OOS backtest on the test slice ----------
    test_index = test.index
    test_ohlcv = ohlcv.loc[test_index[0]:test_index[-1]]
    test_feats = feats.loc[test_index[0]:test_index[-1]]

    cfg = BacktestConfig(starting_cash=args.cash, cost=CostModel())
    bars_per_year = BARS_PER_YEAR[args.timeframe]

    print()
    print(f"=== OOS backtest on test slice ({test_index[0].date()} .. {test_index[-1].date()}) ===")
    rows = []
    for strat in [
        BuyAndHold(),
        MlSignal(model=model, long_threshold=args.threshold, scale=args.scale,
                 name=f"ml_xgb_t{int(args.threshold * 100)}"),
    ]:
        sig = strat.signal(test_feats)
        res = run_backtest(test_ohlcv, sig, cfg=cfg, strategy_name=strat.name, symbol=args.symbol)
        s = summarize(res, bars_per_year=bars_per_year)
        rows.append(s.as_row())

    cols = ["strategy", "total_return", "annual_return", "sharpe",
            "max_dd", "calmar", "hit_rate", "cost_drag"]
    widths = {c: max(len(c), 14) for c in cols}
    print(" | ".join(c.ljust(widths[c]) for c in cols))
    print("-" * (sum(widths.values()) + 3 * (len(cols) - 1)))
    for row in rows:
        parts = []
        for c in cols:
            v = row[c]
            if c == "strategy":
                parts.append(str(v).ljust(widths[c]))
            elif c in ("total_return", "annual_return", "max_dd", "hit_rate", "cost_drag"):
                parts.append(f"{v * 100:>+11.2f}%".ljust(widths[c]))
            else:
                parts.append(f"{v:>+11.2f}".ljust(widths[c]))
        print(" | ".join(parts))


if __name__ == "__main__":
    main()
