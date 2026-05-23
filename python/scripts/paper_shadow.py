"""Shadow-mode learning loop.

Each run:
  1. Retrains the cross-sectional XGBoost model on the trailing 5 years.
  2. Computes the model's target weights for *today*.
  3. Reads current basket prices and the live Alpaca account equity.
  4. Appends a snapshot to shadow_log.jsonl.
  5. If a previous snapshot exists, computes realized P&L between then
     and now for both the shadow model and the equal-weight benchmark,
     and prints a track-record table.

After enough runs (4-12 weeks), the track record tells us whether the
model adds value vs the live equal-weight strategy. Until then it's
just collecting evidence — it never touches the real paper account.

Schedule weekly (e.g., Mondays 30 minutes after market open) with the
same Task Scheduler approach used for paper_runner.

Usage:
    python -m scripts.paper_shadow              # log + report
    python -m scripts.paper_shadow --report     # report only, no new snapshot
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

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
from scripts.train_basket import DEFAULT_UNIVERSE


LOG_PATH = Path("shadow_log.jsonl")
TOP_K = 10
TRAIN_YEARS = 5
HORIZON = 1
TOP_Q = 0.2
RANK_COL_CANDIDATES = [
    "ret_5", "ret_15", "ret_60", "rsi_14", "macd_hist", "bb_pct",
    "atr_pct", "vol_z_30", "dd_20", "runup_20",
    "dist_ma_50", "dist_ma_200", "rv_20", "rs_20", "rs_60",
]


@dataclass
class Snapshot:
    ts: str
    alpaca_equity: float | None
    prices: dict[str, float]
    shadow_weights: dict[str, float]
    bench_weights: dict[str, float]
    val_auc: float | None


def append_snapshot(path: Path, snap: Snapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap.__dict__) + "\n")


def read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def alpaca_equity() -> float | None:
    try:
        from alpaca.trading.client import TradingClient
        key = os.environ.get("ALPACA_KEY_ID", "")
        secret = os.environ.get("ALPACA_SECRET_KEY", "")
        if not key or not secret:
            return None
        c = TradingClient(key, secret, paper=True)
        return float(c.get_account().equity)
    except Exception as e:
        print(f"  (could not read alpaca equity: {e})")
        return None


def train_today_model(symbols: list[str], market: str = "SPY") -> tuple[XgbDirectionModel, dict, dict, float]:
    """Returns (model, today_prices, target_weights, val_auc)."""
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - pd.Timedelta(days=int(TRAIN_YEARS * 365 + 90))

    loader = MultiLoader(AlpacaLoader())
    syms_to_load = list(symbols)
    if market not in syms_to_load:
        syms_to_load.append(market)
    panel = loader.load_basket(syms_to_load, "1Day", start, end)
    if market not in panel:
        raise RuntimeError(f"market symbol {market} unavailable")

    spy_close = panel[market].get("close")
    feat_panel = {
        sym: build_features(df, market_close=spy_close)
        for sym, df in panel.items()
        if sym != market
    }
    feat_panel = {s: df for s, df in feat_panel.items() if not df.empty}

    # If Quiver is available, augment per-symbol features with
    # smart-money-filtered Congressional aggregates. This is the
    # "historical memory" hook — see docs/bot-playbook.md.
    try:
        from trading.data.quiver_client import QuiverClient
        from trading.features.congressional import build_congressional_features
        client = QuiverClient()
        if client.enabled:
            print("  (quiver: adding smart-money Congressional features)")
            union_idx = pd.DatetimeIndex(
                sorted({ts for df in feat_panel.values() for ts in df.index})
            )
            cong = build_congressional_features(
                list(feat_panel.keys()), union_idx,
                client=client, members_of_interest=True,
            )
            for sym in list(feat_panel.keys()):
                if sym in cong:
                    feat_panel[sym] = feat_panel[sym].join(cong[sym], how="left").fillna(0.0)
    except Exception as e:
        print(f"  (quiver augmentation skipped: {e})")

    feats_long = panel_to_long(feat_panel)
    rank_cols_full = RANK_COL_CANDIDATES + [
        "cong_net_30", "cong_net_90", "cong_dollars_30",
        "cong_dem_net_30", "cong_rep_net_30",
    ]
    rank_cols = [c for c in rank_cols_full if c in feats_long.columns]
    feats_long = add_cross_sectional_ranks(feats_long, rank_cols)

    universe_panel = {s: df for s, df in panel.items() if s != market}
    close_panel = stack_panel(universe_panel, "close")

    labels_wide = forward_top_decile(close_panel, HORIZON, top_q=TOP_Q)
    labels_long = labels_wide.stack().rename("y")
    labels_long.index = labels_long.index.set_names(["timestamp", "symbol"])

    df = feats_long.join(labels_long, how="inner").dropna()

    # Training cut: leave a small forward buffer so today's row is purely OOS.
    latest_ts = feats_long.index.get_level_values("timestamp").max()
    train_cutoff = latest_ts - pd.Timedelta(days=7)
    train_df = df.loc[df.index.get_level_values("timestamp") < train_cutoff]
    feature_cols = [c for c in train_df.columns if c != "y"]
    X_tr, y_tr = train_df[feature_cols], train_df["y"]

    cut = int(len(X_tr) * 0.9)
    X_va, y_va = X_tr.iloc[cut:], y_tr.iloc[cut:]
    X_tr, y_tr = X_tr.iloc[:cut], y_tr.iloc[:cut]
    if y_va.nunique() < 2:
        X_va, y_va = None, None

    model = XgbDirectionModel(horizon=HORIZON, config=XgbConfig())
    report = model.fit(X_tr, y_tr, X_va, y_va)
    val_auc = float(report.get("val_auc", float("nan")))

    # Predict on the most recent row per symbol
    latest_rows = feats_long.loc[feats_long.index.get_level_values("timestamp") == latest_ts]
    if latest_rows.empty:
        raise RuntimeError("no feature row available for today")
    latest_X = latest_rows[feature_cols]
    p = model.predict_proba(latest_X)
    p_series = pd.Series(p, index=latest_rows.index.get_level_values("symbol"))

    ranks = p_series.rank(ascending=False, method="first")
    top = (ranks <= TOP_K).astype(float)
    shadow_weights = (top / top.sum()).to_dict()

    bench_weights = {s: 1.0 / len(p_series) for s in p_series.index}

    today_prices = {
        sym: float(panel[sym]["close"].iloc[-1])
        for sym in shadow_weights
        if sym in panel
    }
    return model, today_prices, shadow_weights, val_auc, bench_weights


def compute_return(weights: dict[str, float], prev_prices: dict[str, float], curr_prices: dict[str, float]) -> float:
    """Portfolio return between two price snapshots given fixed weights."""
    ret = 0.0
    for sym, w in weights.items():
        p0 = prev_prices.get(sym)
        p1 = curr_prices.get(sym)
        if p0 is None or p1 is None or p0 <= 0:
            continue
        ret += w * (p1 / p0 - 1.0)
    return ret


def print_report(rows: list[dict]) -> None:
    if len(rows) < 2:
        print(f"\n{len(rows)} snapshot(s) logged so far — need at least 2 for a comparison.")
        return

    shadow_cum = 1.0
    bench_cum = 1.0
    print()
    print(f"{'ts':<23}  {'shadow %':>10}  {'bench %':>10}  {'alpha %':>10}  "
          f"{'shadow_cum':>12}  {'bench_cum':>12}")
    print("-" * 90)
    for i in range(1, len(rows)):
        prev, curr = rows[i - 1], rows[i]
        sret = compute_return(prev["shadow_weights"], prev["prices"], curr["prices"])
        bret = compute_return(prev["bench_weights"], prev["prices"], curr["prices"])
        shadow_cum *= 1.0 + sret
        bench_cum *= 1.0 + bret
        print(f"{curr['ts']:<23}  {sret * 100:>+9.2f}%  {bret * 100:>+9.2f}%  "
              f"{(sret - bret) * 100:>+9.2f}%  {shadow_cum:>12.4f}  {bench_cum:>12.4f}")

    total_alpha = shadow_cum - bench_cum
    n = len(rows) - 1
    print()
    print(f"Total return  shadow: {(shadow_cum - 1) * 100:+.2f}%   bench: {(bench_cum - 1) * 100:+.2f}%")
    print(f"Total alpha (shadow - bench, cumulative): {total_alpha * 100:+.2f}%")
    print(f"Snapshots compared: {n}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", action="store_true",
                   help="Print the track record only; don't append a new snapshot.")
    p.add_argument("--log", type=Path, default=LOG_PATH,
                   help="Path to shadow log JSONL.")
    args = p.parse_args()

    rows = read_log(args.log)

    if args.report:
        print(f"Log: {args.log}  ({len(rows)} snapshots)")
        print_report(rows)
        return

    print("Retraining shadow XGBoost on trailing data...")
    try:
        _, prices, shadow_w, val_auc, bench_w = train_today_model(DEFAULT_UNIVERSE)
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)

    eq = alpaca_equity()
    snap = Snapshot(
        ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        alpaca_equity=eq,
        prices=prices,
        shadow_weights=shadow_w,
        bench_weights=bench_w,
        val_auc=val_auc,
    )
    append_snapshot(args.log, snap)

    print(f"\nSnapshot {snap.ts}")
    print(f"  val_auc: {val_auc:.3f}")
    print(f"  alpaca equity: ${eq:,.2f}" if eq is not None else "  alpaca equity: (not available)")
    top_picks = sorted(shadow_w.items(), key=lambda kv: -kv[1])[:TOP_K]
    print(f"  shadow top-{TOP_K} picks: {[s for s, _ in top_picks]}")

    # Print rolling track record
    rows = read_log(args.log)
    print_report(rows)


if __name__ == "__main__":
    main()
