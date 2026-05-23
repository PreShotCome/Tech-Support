"""Forward regime labels.

forward_drawdown_label(close, horizon, threshold) = 1 if the market's
worst close-to-close drawdown over the next `horizon` bars is at least
`threshold` (e.g. 0.05 = 5%). Else 0. NaN for the last `horizon` rows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def forward_drawdown_label(
    close: pd.Series,
    horizon: int,
    threshold: float = 0.05,
) -> pd.Series:
    """Compute the worst forward drawdown over [t+1, t+horizon] for each
    bar, then label 1 if it meets the threshold (drawdown >= threshold)
    or 0 otherwise. The threshold should be positive (e.g. 0.05 for
    "at least 5% drawdown ahead")."""
    close = close.astype(float)
    n = len(close)
    out = np.full(n, np.nan, dtype=float)

    # For each t, look at close[t+1 .. t+horizon] and compute the worst
    # drawdown from any local peak in that window. We use a simple "min
    # of close[t+i] / max-so-far - 1" approach.
    vals = close.values
    for t in range(n - horizon):
        window = vals[t + 1: t + 1 + horizon]
        peak = window[0]
        worst = 0.0
        for v in window:
            if v > peak:
                peak = v
            dd = v / peak - 1.0
            if dd < worst:
                worst = dd
        # `worst` is negative; threshold should be its positive magnitude.
        out[t] = 1.0 if worst <= -abs(threshold) else 0.0

    return pd.Series(out, index=close.index, name=f"fdd_{horizon}_{int(threshold * 100)}")
