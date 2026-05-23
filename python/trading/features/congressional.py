"""Features built from Congressional trade disclosures.

For each (timestamp, symbol), compute trailing-window aggregates of
Congressional buying / selling pressure. These get joined onto the
per-symbol feature DataFrame so the cross-sectional model can use them
just like any other ranked feature.

All trades are observed from `report_date` (when disclosure happened),
not `transaction_date` — using transaction_date would leak future info
because disclosures lag the actual trade by up to 45 days.
"""
from __future__ import annotations

import pandas as pd

from ..data.quiver_client import QuiverClient


def build_congressional_features(
    symbols: list[str],
    target_index: pd.DatetimeIndex,
    client: QuiverClient | None = None,
    windows: tuple[int, ...] = (30, 90),
) -> dict[str, pd.DataFrame]:
    """Return {symbol: DataFrame} where each DataFrame is indexed by
    target_index and contains rolling-window congressional features.

    Cols per window N:
        cong_n_buys_<N>     count of Purchase disclosures in last N days
        cong_n_sells_<N>    count of Sale disclosures
        cong_net_<N>        buys - sells
        cong_dollars_<N>    net signed dollar magnitude (midpoint of range)
        cong_dem_net_<N>    democrat buys - democrat sells
        cong_rep_net_<N>    republican buys - republican sells

    When QUIVER_API_KEY is not set, returns a dict of empty DataFrames
    (still keyed by symbol). The training pipeline can then merge with
    `how="left"` and zero-fill, so the feature columns exist but carry
    no information until you set up the key.
    """
    client = client or QuiverClient()
    target_index = pd.DatetimeIndex(target_index).tz_convert("UTC") \
        if target_index.tz is not None else pd.DatetimeIndex(target_index).tz_localize("UTC")
    feat_cols = []
    for w in windows:
        feat_cols += [f"cong_n_buys_{w}", f"cong_n_sells_{w}", f"cong_net_{w}",
                      f"cong_dollars_{w}", f"cong_dem_net_{w}", f"cong_rep_net_{w}"]

    out: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        trades = client.congressional_trades(sym) if client.enabled else None
        if trades is None or trades.empty:
            out[sym] = pd.DataFrame(0.0, index=target_index, columns=feat_cols)
            continue

        df = trades.copy()
        # Use report_date as the "available" timestamp.
        df = df.dropna(subset=["report_date"])
        df["report_date"] = pd.to_datetime(df["report_date"], utc=True)
        df["is_buy"] = (df["transaction"].astype(str).str.lower().str.startswith("purchase")).astype(float)
        df["is_sell"] = (df["transaction"].astype(str).str.lower().str.startswith("sale")).astype(float)
        df["mid_dollars"] = (df["range_low"].astype(float).fillna(0) + df["range_high"].astype(float).fillna(0)) / 2.0
        df["signed_dollars"] = df["mid_dollars"] * (df["is_buy"] - df["is_sell"])
        party = df["party"].astype(str).str.lower().fillna("")
        df["dem_net"] = (df["is_buy"] - df["is_sell"]) * party.str.startswith("d").astype(float)
        df["rep_net"] = (df["is_buy"] - df["is_sell"]) * party.str.startswith("r").astype(float)

        df = df.set_index("report_date").sort_index()
        keep = ["is_buy", "is_sell", "signed_dollars", "dem_net", "rep_net"]
        df = df[keep]

        # Resample to daily counts so we can rolling-sum over calendar days.
        daily = df.resample("1D").sum()

        feats = pd.DataFrame(index=daily.index)
        for w in windows:
            feats[f"cong_n_buys_{w}"] = daily["is_buy"].rolling(w, min_periods=1).sum()
            feats[f"cong_n_sells_{w}"] = daily["is_sell"].rolling(w, min_periods=1).sum()
            feats[f"cong_net_{w}"] = feats[f"cong_n_buys_{w}"] - feats[f"cong_n_sells_{w}"]
            feats[f"cong_dollars_{w}"] = daily["signed_dollars"].rolling(w, min_periods=1).sum()
            feats[f"cong_dem_net_{w}"] = daily["dem_net"].rolling(w, min_periods=1).sum()
            feats[f"cong_rep_net_{w}"] = daily["rep_net"].rolling(w, min_periods=1).sum()

        # Reindex to target_index using as-of join (forward fill); a feature
        # at time t reflects disclosures available *as of* t.
        feats = feats.reindex(feats.index.union(target_index)).sort_index().ffill().fillna(0.0)
        feats = feats.loc[target_index]
        out[sym] = feats

    return out
