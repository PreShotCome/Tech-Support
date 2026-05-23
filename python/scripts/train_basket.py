"""Cross-sectional training: train one model on a stacked panel of
many symbols, predict which symbols will outperform the basket the
next bar(s), backtest long-top-K vs equal-weight basket.

Universe defaults to large-cap megas; pass --symbols to override.

Usage:
    python -m scripts.train_basket --timeframe 1Day --horizon 1 \
        --start 2015-01-01 --end 2024-06-30 --top-k 5
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from trading.backtest import BacktestConfig, run_basket_backtest, summarize
from trading.backtest.costs import CostModel
from trading.data import AlpacaLoader, MultiLoader, stack_panel
from trading.data.alpaca_loader import utc
from trading.features import build_features
from trading.features.cross_sectional import (
    add_cross_sectional_ranks,
    forward_top_decile,
    panel_to_long,
)
from trading.models import XgbDirectionModel
from trading.models.xgb import XgbConfig


DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO",
    "BRK.B", "JPM", "JNJ", "V", "PG", "MA", "HD", "CVX", "ABBV",
    "MRK", "PEP", "KO", "COST", "WMT", "DIS", "BAC", "ADBE",
    "NFLX", "CRM", "AMD", "INTC", "QCOM",
]

BARS_PER_YEAR = {
    "1Min": 252 * 390,
    "5Min": 252 * 78,
    "15Min": 252 * 26,
    "1Hour": 252 * 6.5,
    "1Day": 252,
}


def chrono_split(idx: pd.Index, train_frac: float, val_frac: float):
    """Split a unique-sorted index of timestamps into train/val/test by
    chronological fraction."""
    uniq = idx.get_level_values("timestamp").unique().sort_values()
    n = len(uniq)
    a = int(n * train_frac)
    b = int(n * (train_frac + val_frac))
    return uniq[:a], uniq[a:b], uniq[b:]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="*", default=DEFAULT_UNIVERSE)
    p.add_argument("--timeframe", default="1Day", choices=list(BARS_PER_YEAR.keys()))
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--horizon", type=int, default=1)
    p.add_argument("--top-k", type=int, default=5,
                   help="Number of stocks to go long each rebalance.")
    p.add_argument("--bottom-k", type=int, default=None,
                   help="Stocks to short in longshort mode (defaults to --top-k).")
    p.add_argument("--mode", choices=["topk", "topk_weighted", "longshort", "ranked"],
                   default="topk",
                   help="Portfolio construction: "
                        "topk=long equal-weight top K; "
                        "topk_weighted=long top K weighted by P; "
                        "longshort=long top K + short bottom K (market-neutral); "
                        "ranked=tilt all symbols by their rank vs basket median.")
    p.add_argument("--top-q", type=float, default=0.2,
                   help="Top quantile of forward returns labelled as +1.")
    p.add_argument("--train-frac", type=float, default=0.70)
    p.add_argument("--val-frac", type=float, default=0.15)
    p.add_argument("--cash", type=float, default=100_000.0)
    p.add_argument("--save", type=Path, default=Path("models/xgb_basket"),
                   help="Path stem to save model.")
    args = p.parse_args()

    print(f"Universe: {len(args.symbols)} symbols")
    print(f"Period: {args.start} .. {args.end}  timeframe: {args.timeframe}  horizon: {args.horizon}")

    # --------------------------------------------------------------- load
    loader = MultiLoader(AlpacaLoader())
    panel = loader.load_basket(args.symbols, args.timeframe, utc(args.start), utc(args.end))
    if not panel:
        print("No data for any symbol.")
        return
    print(f"Loaded {len(panel)}/{len(args.symbols)} symbols")

    # --------------------------------------------------------------- features
    feat_panel = {sym: build_features(df) for sym, df in panel.items()}
    feat_panel = {sym: df for sym, df in feat_panel.items() if not df.empty}
    long_feats = panel_to_long(feat_panel)
    if long_feats.empty:
        print("No features available after warm-up.")
        return

    # cross-sectional ranks for a few signal columns
    rank_cols = ["ret_5", "ret_15", "ret_60", "rsi_14", "macd_hist", "bb_pct", "atr_pct", "vol_z_30"]
    long_feats = add_cross_sectional_ranks(long_feats, rank_cols)

    # --------------------------------------------------------------- labels
    close_panel = stack_panel(panel, "close")
    labels_wide = forward_top_decile(close_panel, args.horizon, top_q=args.top_q)
    labels_long = labels_wide.stack().rename("y")
    labels_long.index = labels_long.index.set_names(["timestamp", "symbol"])

    df = long_feats.join(labels_long, how="inner").dropna()
    feature_cols = [c for c in df.columns if c not in ("symbol", "y")]
    print(f"Stacked dataset: {len(df):,} rows, {len(feature_cols)} features, "
          f"positive rate {df['y'].mean():.3f}")

    # --------------------------------------------------------------- split
    train_idx, val_idx, test_idx = chrono_split(df.index, args.train_frac, args.val_frac)
    is_train = df.index.get_level_values("timestamp").isin(train_idx)
    is_val = df.index.get_level_values("timestamp").isin(val_idx)
    is_test = df.index.get_level_values("timestamp").isin(test_idx)

    X_tr, y_tr = df.loc[is_train, feature_cols], df.loc[is_train, "y"]
    X_va, y_va = df.loc[is_val, feature_cols], df.loc[is_val, "y"]
    X_te, y_te = df.loc[is_test, feature_cols], df.loc[is_test, "y"]
    print(f"train {len(X_tr):,}   val {len(X_va):,}   test {len(X_te):,}")

    # --------------------------------------------------------------- train
    model = XgbDirectionModel(horizon=args.horizon, config=XgbConfig())
    report = model.fit(X_tr, y_tr, X_va, y_va)
    print(f"fit: {report}")

    args.save.parent.mkdir(parents=True, exist_ok=True)
    model.save(args.save)
    print(f"saved -> {args.save.with_suffix('.xgb.json')}")

    # --------------------------------------------------------------- backtest
    # Predict for ALL test rows, pivot to wide (timestamp × symbol) of P(top).
    df_te = df.loc[is_test].copy()
    df_te["p"] = model.predict_proba(X_te)

    p_wide = df_te["p"].unstack(level="symbol")

    # Each rebalance: rank symbols, build portfolio weights per --mode.
    K = args.top_k
    bK = args.bottom_k or K
    ranks = p_wide.rank(axis=1, ascending=False, method="first")
    asc_ranks = p_wide.rank(axis=1, ascending=True, method="first")
    n_per_row = p_wide.notna().sum(axis=1)

    if args.mode == "topk":
        weights = (ranks <= K).astype(float).div(K)
        strat_name = f"ml_top{K}"
    elif args.mode == "topk_weighted":
        is_top = (ranks <= K).astype(float)
        p_in_top = (p_wide * is_top).fillna(0.0)
        # Normalize each row so weights sum to 1
        row_sum = p_in_top.sum(axis=1).replace(0, np.nan)
        weights = p_in_top.div(row_sum, axis=0).fillna(0.0)
        strat_name = f"ml_top{K}_pweighted"
    elif args.mode == "longshort":
        long_w = (ranks <= K).astype(float).div(K)
        short_w = (asc_ranks <= bK).astype(float).div(bK)
        weights = long_w - short_w   # gross exposure = 2.0, net = 0
        strat_name = f"ml_L{K}S{bK}"
    elif args.mode == "ranked":
        # Tilt weight by signed rank-distance from median; normalize so
        # the long side sums to 1 (matches buy-hold notional exposure).
        median_rank = (n_per_row + 1) / 2.0
        tilt = (median_rank.values[:, None] - ranks.values)  # > 0 means above-median
        tilt = pd.DataFrame(tilt, index=p_wide.index, columns=p_wide.columns)
        long_side = tilt.clip(lower=0.0)
        weights = long_side.div(long_side.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
        strat_name = f"ml_ranked"
    else:
        raise ValueError(f"unknown mode {args.mode}")

    # Equal-weight benchmark across the same universe each day.
    valid = p_wide.notna().astype(float)
    bench_weights = valid.div(valid.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)

    test_close = close_panel.loc[weights.index[0]: weights.index[-1], weights.columns]

    cfg = BacktestConfig(starting_cash=args.cash, cost=CostModel())
    res_model = run_basket_backtest(test_close, weights, cfg=cfg,
                                    strategy_name=strat_name)
    res_bench = run_basket_backtest(test_close, bench_weights, cfg=cfg,
                                    strategy_name="equal_weight")

    bpy = BARS_PER_YEAR[args.timeframe]
    rows = [summarize(res, bars_per_year=bpy).as_row() for res in (res_bench, res_model)]

    print()
    print(f"=== OOS basket backtest ({weights.index[0].date()} .. {weights.index[-1].date()}) ===")
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
