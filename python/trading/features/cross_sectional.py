"""Cross-sectional features and labels.

The big idea of cross-sectional models: instead of asking "will AAPL go
up?" (hard, ~50/50), ask "of these 30 stocks today, which 5 will
outperform the basket tomorrow?" Relative performance has more signal
than absolute direction.

Inputs here are dicts of per-symbol feature DataFrames already produced
by build_features(). This module adds rank-within-basket features and
relative-performance labels.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def panel_to_long(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Stack per-symbol DataFrames into a long-format DataFrame with
    columns ['symbol', ...features]. Index is (timestamp, symbol)."""
    parts = []
    for sym, df in panel.items():
        d = df.copy()
        d["symbol"] = sym
        parts.append(d)
    if not parts:
        return pd.DataFrame()
    long = pd.concat(parts).set_index("symbol", append=True)
    long.index = long.index.set_names(["timestamp", "symbol"])
    return long.sort_index()


def add_cross_sectional_ranks(
    long_df: pd.DataFrame,
    cols: list[str],
) -> pd.DataFrame:
    """For each column in `cols`, add a column `{col}_rank` that is the
    per-timestamp rank within the cross-section, normalized to [0, 1]."""
    out = long_df.copy()
    for c in cols:
        if c not in out.columns:
            continue
        ranked = out.groupby(level="timestamp")[c].rank(pct=True, method="average")
        out[f"{c}_rank"] = ranked
    return out


def forward_relative_return(
    close_panel: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    """For each (timestamp, symbol), the symbol's forward log return
    over `horizon` bars MINUS the basket-mean forward log return at the
    same timestamp.

    Positive values mean the symbol outperformed the basket. Zero on
    average across the cross-section.

    `close_panel` is wide (timestamps × symbols)."""
    log = np.log(close_panel)
    fr = log.shift(-horizon) - log
    basket_mean = fr.mean(axis=1)
    return fr.subtract(basket_mean, axis=0)


def forward_top_decile(
    close_panel: pd.DataFrame,
    horizon: int,
    top_q: float = 0.2,
) -> pd.DataFrame:
    """Binary label: 1 if the symbol's forward return will be in the
    top `top_q` quantile across the basket, else 0.

    Returns a wide DataFrame matching close_panel's shape."""
    rel = forward_relative_return(close_panel, horizon)
    # Rank within each row, normalized
    rank = rel.rank(axis=1, pct=True)
    return (rank >= 1.0 - top_q).astype(float).where(~rel.isna())
