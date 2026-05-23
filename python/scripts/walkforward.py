"""Walk-forward evaluation of the cross-sectional model.

For each rolling window:
    [-------- train window --------][--- test window ---]
    Retrain XGBoost from scratch on the train window, run an OOS
    backtest on the test window, record alpha vs equal-weight.

The output is the only honest answer we have to "is this edge real or
window-luck?" — averaged across many test windows that the model has
never seen.

Usage:
    python -m scripts.walkforward --start 2015-01-01 --end 2024-06-30 \\
        --train-years 5 --test-months 6 --step-months 6 --top-k 10
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

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
from scripts.train_basket import DEFAULT_UNIVERSE, BARS_PER_YEAR


@dataclass
class WindowResult:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    val_auc: float
    bench_return: float
    ml_return: float
    alpha: float
    sharpe_ml: float
    sharpe_bench: float
    max_dd_ml: float
    n_train: int
    n_test: int


def run_window(
    feats_long: pd.DataFrame,
    close_panel: pd.DataFrame,
    rank_cols: list[str],
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
    horizon: int,
    top_q: float,
    top_k: int,
    cfg: BacktestConfig,
    bars_per_year: float,
) -> WindowResult:
    """Train on [train_start, train_end), evaluate on [test_start, test_end)."""
    # Slice features by timestamp level.
    ts = feats_long.index.get_level_values("timestamp")
    train_mask = (ts >= train_start) & (ts < train_end)
    test_mask = (ts >= test_start) & (ts < test_end)
    train_long = feats_long.loc[train_mask].copy()
    test_long = feats_long.loc[test_mask].copy()

    # Cross-sectional rank features must be computed per-timestamp, so it's
    # safe to compute them on the joined long frame before splitting.

    # Labels: compute on the close panel for the union and join.
    labels_wide = forward_top_decile(close_panel, horizon, top_q=top_q)
    labels_long = labels_wide.stack().rename("y")
    labels_long.index = labels_long.index.set_names(["timestamp", "symbol"])

    train_df = train_long.join(labels_long, how="inner").dropna()
    test_df = test_long.join(labels_long, how="inner").dropna()

    feature_cols = [c for c in train_df.columns if c != "y"]
    X_tr, y_tr = train_df[feature_cols], train_df["y"]
    X_te, y_te = test_df[feature_cols], test_df["y"]

    # Hold out the last 10% of training rows as val for early stopping.
    n_tr = len(X_tr)
    cut = int(n_tr * 0.9)
    X_va, y_va = X_tr.iloc[cut:], y_tr.iloc[cut:]
    X_tr, y_tr = X_tr.iloc[:cut], y_tr.iloc[:cut]

    model = XgbDirectionModel(horizon=horizon, config=XgbConfig())
    report = model.fit(X_tr, y_tr, X_va, y_va)
    val_auc = float(report.get("val_auc", float("nan")))

    # Predictions on test slice
    test_df = test_df.copy()
    test_df["p"] = model.predict_proba(X_te)

    p_wide = test_df["p"].unstack(level="symbol")
    # Long top-K equal-weight
    ranks = p_wide.rank(axis=1, ascending=False, method="first")
    weights = (ranks <= top_k).astype(float).div(top_k)
    valid = p_wide.notna().astype(float)
    bench_weights = valid.div(valid.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)

    test_close = close_panel.loc[
        weights.index[0]: weights.index[-1], weights.columns
    ]
    res_ml = run_basket_backtest(test_close, weights, cfg=cfg, strategy_name=f"ml_top{top_k}")
    res_bench = run_basket_backtest(test_close, bench_weights, cfg=cfg, strategy_name="equal_weight")
    s_ml = summarize(res_ml, bars_per_year=bars_per_year)
    s_bench = summarize(res_bench, bars_per_year=bars_per_year)

    return WindowResult(
        train_start=train_start, train_end=train_end,
        test_start=test_start, test_end=test_end,
        val_auc=val_auc,
        bench_return=s_bench.total_return,
        ml_return=s_ml.total_return,
        alpha=s_ml.total_return - s_bench.total_return,
        sharpe_ml=s_ml.sharpe,
        sharpe_bench=s_bench.sharpe,
        max_dd_ml=s_ml.max_drawdown,
        n_train=len(train_df),
        n_test=len(test_df),
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="*", default=DEFAULT_UNIVERSE)
    p.add_argument("--market", default="SPY")
    p.add_argument("--timeframe", default="1Day", choices=list(BARS_PER_YEAR.keys()))
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--horizon", type=int, default=1)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--top-q", type=float, default=0.2)
    p.add_argument("--train-years", type=float, default=5.0)
    p.add_argument("--test-months", type=int, default=6)
    p.add_argument("--step-months", type=int, default=6)
    p.add_argument("--cash", type=float, default=100_000.0)
    args = p.parse_args()

    # ---------------- Load + features ----------------
    loader = MultiLoader(AlpacaLoader())
    syms_to_load = list(args.symbols)
    if args.market and args.market not in syms_to_load:
        syms_to_load.append(args.market)
    panel = loader.load_basket(syms_to_load, args.timeframe, utc(args.start), utc(args.end))
    if not panel:
        print("No data.")
        return
    print(f"Loaded {len(panel)} symbols")

    market_close = panel.get(args.market, pd.DataFrame()).get("close") if args.market else None
    feat_panel = {
        sym: build_features(df, market_close=market_close)
        for sym, df in panel.items()
        if sym != args.market
    }
    feat_panel = {s: df for s, df in feat_panel.items() if not df.empty}
    feats_long = panel_to_long(feat_panel)

    rank_cols_candidates = [
        "ret_5", "ret_15", "ret_60", "rsi_14", "macd_hist", "bb_pct",
        "atr_pct", "vol_z_30", "dd_20", "runup_20",
        "dist_ma_50", "dist_ma_200", "rv_20", "rs_20", "rs_60",
    ]
    rank_cols = [c for c in rank_cols_candidates if c in feats_long.columns]
    feats_long = add_cross_sectional_ranks(feats_long, rank_cols)

    universe_panel = {s: df for s, df in panel.items() if s != args.market}
    close_panel = stack_panel(universe_panel, "close")

    # ---------------- Build walk-forward windows ----------------
    start = utc(args.start)
    end = utc(args.end)
    train_delta = pd.Timedelta(days=int(args.train_years * 365))
    test_delta = pd.Timedelta(days=args.test_months * 30)
    step_delta = pd.Timedelta(days=args.step_months * 30)

    windows = []
    first_test_start = start + train_delta
    cur = first_test_start
    while cur + test_delta <= end:
        windows.append((cur - train_delta, cur, cur, cur + test_delta))
        cur = cur + step_delta
    if not windows:
        print("Not enough data for given window sizes.")
        return
    print(f"Walk-forward: {len(windows)} windows, "
          f"train={args.train_years}y, test={args.test_months}mo, step={args.step_months}mo")
    print()

    cfg = BacktestConfig(starting_cash=args.cash, cost=CostModel())
    bpy = BARS_PER_YEAR[args.timeframe]

    rows = []
    for i, (ts, te, vs, ve) in enumerate(windows, 1):
        try:
            r = run_window(
                feats_long, close_panel, rank_cols,
                ts, te, vs, ve,
                horizon=args.horizon, top_q=args.top_q, top_k=args.top_k,
                cfg=cfg, bars_per_year=bpy,
            )
        except Exception as exc:
            print(f"window {i}: FAILED ({exc.__class__.__name__}: {exc})")
            continue
        rows.append(r)
        print(f"window {i:2d}  test {r.test_start.date()}..{r.test_end.date()}  "
              f"auc={r.val_auc:.3f}  "
              f"bench={r.bench_return * 100:+6.2f}%  "
              f"ml={r.ml_return * 100:+6.2f}%  "
              f"alpha={r.alpha * 100:+6.2f}%  "
              f"sharpe_ml={r.sharpe_ml:+.2f}")

    if not rows:
        print("No completed windows.")
        return

    # ---------------- Aggregate ----------------
    alphas = np.array([r.alpha for r in rows])
    wins = (alphas > 0).sum()
    mean_alpha = alphas.mean()
    median_alpha = float(np.median(alphas))
    std_alpha = alphas.std(ddof=0)
    ir = mean_alpha / std_alpha if std_alpha > 0 else float("nan")

    # Annualized alpha across the OOS path
    n_per_year = 12.0 / max(args.test_months, 1)
    ann_alpha = (1.0 + mean_alpha) ** n_per_year - 1.0

    print()
    print(f"=== Aggregate over {len(rows)} OOS windows ===")
    print(f"  Mean alpha per {args.test_months}mo : {mean_alpha * 100:+.2f}%")
    print(f"  Median alpha per {args.test_months}mo: {median_alpha * 100:+.2f}%")
    print(f"  Std alpha                : {std_alpha * 100:.2f}%")
    print(f"  Information ratio        : {ir:+.2f}")
    print(f"  Annualized alpha         : {ann_alpha * 100:+.2f}%")
    print(f"  Win rate                 : {wins}/{len(rows)} = {wins/len(rows)*100:.0f}%")
    print(f"  Mean val_auc             : {np.mean([r.val_auc for r in rows]):.3f}")


if __name__ == "__main__":
    main()
