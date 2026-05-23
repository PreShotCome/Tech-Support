"""Walk-forward evaluation of the *defensive overlay* strategy.

Instead of picking stocks, the model predicts the probability that the
market will be in significant drawdown in the next N bars. When that
probability exceeds a threshold, we cut basket exposure from 100% to
`risk_off_weight` (default 30%). Otherwise we hold the equal-weight
basket fully.

We're explicitly NOT trying to beat the basket on raw return in good
times — we're trying to avoid the 2022-style drawdowns the previous
walk-forward exposed.

Usage:
    python -m scripts.walkforward_overlay \\
        --start 2015-01-01 --end 2024-06-30 \\
        --train-years 5 --test-months 6 --step-months 6 \\
        --horizon 20 --drawdown-threshold 0.05
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
from trading.models import XgbDirectionModel
from trading.models.xgb import XgbConfig
from trading.regime import (
    build_breadth_features,
    build_regime_features,
    forward_drawdown_label,
)
from scripts.train_basket import DEFAULT_UNIVERSE, BARS_PER_YEAR


@dataclass
class WindowResult:
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    val_auc: float
    pct_risk_off: float
    bench_return: float
    overlay_return: float
    alpha: float
    bench_sharpe: float
    overlay_sharpe: float
    bench_dd: float
    overlay_dd: float


def run_window(
    feats: pd.DataFrame,
    labels: pd.Series,
    close_panel: pd.DataFrame,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
    horizon: int,
    risk_off_threshold: float,
    risk_off_weight: float,
    cfg: BacktestConfig,
    bars_per_year: float,
) -> WindowResult:
    # Align features + labels to one DataFrame
    df = feats.join(labels.rename("y"), how="inner").dropna()
    df = df.loc[(df.index >= train_start) & (df.index < test_end)]

    ts = df.index
    train_df = df.loc[(ts >= train_start) & (ts < train_end)]
    test_df = df.loc[(ts >= test_start) & (ts < test_end)]
    if train_df.empty or test_df.empty:
        raise ValueError("empty window")

    feature_cols = [c for c in df.columns if c != "y"]
    X_tr, y_tr = train_df[feature_cols], train_df["y"]
    X_te = test_df[feature_cols]

    cut = int(len(X_tr) * 0.9)
    X_va, y_va = X_tr.iloc[cut:], y_tr.iloc[cut:]
    X_tr, y_tr = X_tr.iloc[:cut], y_tr.iloc[:cut]
    # If the val slice has only one class, skip val (early stopping disabled);
    # the model still trains, we just don't get a val_auc this window.
    if y_va.nunique() < 2:
        X_va, y_va = None, None

    model = XgbDirectionModel(horizon=horizon, config=XgbConfig())
    try:
        report = model.fit(X_tr, y_tr, X_va, y_va)
    except ValueError as e:
        # Fall back to no-val training if sklearn complains about classes.
        report = model.fit(X_tr, y_tr, None, None)
    val_auc = float(report.get("val_auc", float("nan")))

    p = model.predict_proba(X_te)
    p_series = pd.Series(p, index=test_df.index, name="p_danger")

    # Build per-symbol weights from the basket exposure.
    universe = list(close_panel.columns)
    n = len(universe)
    test_close = close_panel.loc[test_df.index[0]: test_df.index[-1], universe]

    # Exposure: smooth (when threshold is negative sentinel) or binary.
    if risk_off_threshold < 0:
        exposure = 1.0 - p_series.values * (1.0 - risk_off_weight)
    else:
        exposure = np.where(p_series.values >= risk_off_threshold, risk_off_weight, 1.0)
    exposure = np.clip(exposure, 0.0, 1.0)
    exposure_s = pd.Series(exposure, index=p_series.index)
    weights_overlay = pd.DataFrame(
        np.tile((1.0 / n) * exposure_s.values[:, None], (1, n)),
        index=p_series.index,
        columns=universe,
    )
    weights_bench = pd.DataFrame(
        1.0 / n, index=p_series.index, columns=universe,
    )

    res_overlay = run_basket_backtest(test_close, weights_overlay, cfg=cfg, strategy_name="overlay")
    res_bench = run_basket_backtest(test_close, weights_bench, cfg=cfg, strategy_name="equal_weight")

    s_overlay = summarize(res_overlay, bars_per_year=bars_per_year)
    s_bench = summarize(res_bench, bars_per_year=bars_per_year)

    return WindowResult(
        train_end=train_end,
        test_start=test_df.index[0],
        test_end=test_df.index[-1],
        val_auc=val_auc,
        pct_risk_off=float((p_series.values >= risk_off_threshold).mean()),
        bench_return=s_bench.total_return,
        overlay_return=s_overlay.total_return,
        alpha=s_overlay.total_return - s_bench.total_return,
        bench_sharpe=s_bench.sharpe,
        overlay_sharpe=s_overlay.sharpe,
        bench_dd=s_bench.max_drawdown,
        overlay_dd=s_overlay.max_drawdown,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="*", default=DEFAULT_UNIVERSE)
    p.add_argument("--market", default="SPY")
    p.add_argument("--timeframe", default="1Day", choices=list(BARS_PER_YEAR.keys()))
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--horizon", type=int, default=20,
                   help="Bars ahead to look for drawdown (default 20 = about 1 month).")
    p.add_argument("--drawdown-threshold", type=float, default=0.05,
                   help="Drawdown magnitude that counts as risk-off (default 0.05).")
    p.add_argument("--risk-off-threshold", type=float, default=0.50,
                   help="P(drawdown) above which we cut exposure (default 0.50).")
    p.add_argument("--risk-off-weight", type=float, default=0.30,
                   help="Basket exposure when model says risk-off (default 0.30).")
    p.add_argument("--smooth", action="store_true",
                   help="Smooth-scale exposure as 1 - p*(1 - risk_off_weight) "
                        "instead of binary threshold. Avoids being stuck in "
                        "risk-off after the regime improves.")
    p.add_argument("--train-years", type=float, default=5.0)
    p.add_argument("--test-months", type=int, default=6)
    p.add_argument("--step-months", type=int, default=6)
    p.add_argument("--cash", type=float, default=100_000.0)
    args = p.parse_args()

    # ---------------- Load ----------------
    loader = MultiLoader(AlpacaLoader())
    syms_to_load = list(args.symbols)
    if args.market not in syms_to_load:
        syms_to_load.append(args.market)
    panel = loader.load_basket(syms_to_load, args.timeframe, utc(args.start), utc(args.end))
    if args.market not in panel:
        print(f"Market symbol {args.market} unavailable.")
        return
    print(f"Loaded {len(panel)} symbols")

    spy = panel[args.market]
    universe_panel = {s: df for s, df in panel.items() if s != args.market}
    close_panel = stack_panel(universe_panel, "close")

    # ---------------- Features + labels ----------------
    spy_feats = build_regime_features(spy)
    breadth = build_breadth_features(close_panel)
    feats = spy_feats.join(breadth, how="left")
    # Median-impute the breadth columns rather than drop rows. The
    # SPY-only features carry most of the signal; we'd rather train on
    # an imputed breadth value than discard the whole bar.
    breadth_cols = list(breadth.columns)
    feats[breadth_cols] = feats[breadth_cols].fillna(feats[breadth_cols].median())
    # Final dropna removes only rows missing core SPY features.
    feats = feats.dropna()
    labels = forward_drawdown_label(spy["close"], args.horizon, args.drawdown_threshold)
    print(f"Features: {feats.shape[1]} cols, {len(feats):,} rows")
    print(f"Label positive rate: {labels.mean():.3f} "
          f"(fraction of bars where next {args.horizon}d had ≥{args.drawdown_threshold * 100:.0f}% DD)")

    # ---------------- Windows ----------------
    start = utc(args.start)
    end = utc(args.end)
    train_delta = pd.Timedelta(days=int(args.train_years * 365))
    test_delta = pd.Timedelta(days=args.test_months * 30)
    step_delta = pd.Timedelta(days=args.step_months * 30)

    windows = []
    cur = start + train_delta
    while cur + test_delta <= end:
        windows.append((cur - train_delta, cur, cur, cur + test_delta))
        cur = cur + step_delta
    print(f"Walk-forward: {len(windows)} windows  train={args.train_years}y  test={args.test_months}mo")
    print(f"  risk-off when P >= {args.risk_off_threshold}; exposure cut to {args.risk_off_weight}")
    print()

    cfg = BacktestConfig(starting_cash=args.cash, cost=CostModel())
    bpy = BARS_PER_YEAR[args.timeframe]

    rows = []
    for i, (ts, te, vs, ve) in enumerate(windows, 1):
        try:
            r = run_window(
                feats, labels, close_panel,
                ts, te, vs, ve,
                horizon=args.horizon,
                # Use -1.0 sentinel to flip the engine into smooth mode.
                risk_off_threshold=(-1.0 if args.smooth else args.risk_off_threshold),
                risk_off_weight=args.risk_off_weight,
                cfg=cfg,
                bars_per_year=bpy,
            )
        except Exception as exc:
            print(f"window {i}: FAILED ({exc.__class__.__name__}: {exc})")
            continue
        rows.append(r)
        print(f"window {i:2d}  {r.test_start.date()}..{r.test_end.date()}  "
              f"auc={r.val_auc:.3f}  off={r.pct_risk_off * 100:>4.0f}%  "
              f"bench={r.bench_return * 100:+6.2f}%  ovr={r.overlay_return * 100:+6.2f}%  "
              f"alpha={r.alpha * 100:+6.2f}%  "
              f"ddB={r.bench_dd * 100:+6.2f}%  ddO={r.overlay_dd * 100:+6.2f}%")

    if not rows:
        print("No completed windows.")
        return

    alphas = np.array([r.alpha for r in rows])
    bench_dd = np.array([r.bench_dd for r in rows])
    overlay_dd = np.array([r.overlay_dd for r in rows])
    bench_sharpe = np.array([r.bench_sharpe for r in rows])
    overlay_sharpe = np.array([r.overlay_sharpe for r in rows])

    print()
    print(f"=== Aggregate over {len(rows)} OOS windows ===")
    print(f"  Mean alpha per {args.test_months}mo : {alphas.mean() * 100:+.2f}%")
    print(f"  Median alpha             : {float(np.median(alphas)) * 100:+.2f}%")
    print(f"  Std alpha                : {alphas.std(ddof=0) * 100:.2f}%")
    ir = alphas.mean() / alphas.std(ddof=0) if alphas.std(ddof=0) > 0 else float("nan")
    print(f"  Information ratio        : {ir:+.2f}")
    print(f"  Mean max drawdown        : bench={bench_dd.mean() * 100:+.2f}%  overlay={overlay_dd.mean() * 100:+.2f}%")
    print(f"  Worst max drawdown       : bench={bench_dd.min() * 100:+.2f}%  overlay={overlay_dd.min() * 100:+.2f}%")
    print(f"  Mean Sharpe              : bench={bench_sharpe.mean():+.2f}  overlay={overlay_sharpe.mean():+.2f}")


if __name__ == "__main__":
    main()
