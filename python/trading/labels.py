"""Target labels for supervised learning.

Convention: a label is produced at bar t to be predicted *from* features
known at bar t. Labels look into the future — they MUST be dropped or
masked at inference time. The backtester separately enforces signal-at-t
/ fill-at-t+1 lag.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def forward_log_return(close: pd.Series, horizon: int) -> pd.Series:
    """Log return from bar t to bar t+horizon. NaN for the last `horizon` rows."""
    return (np.log(close.shift(-horizon)) - np.log(close)).rename(f"fret_{horizon}")


def forward_direction(close: pd.Series, horizon: int, threshold: float = 0.0) -> pd.Series:
    """Binary label: 1 if forward log return >= threshold, else 0. NaN for the last
    `horizon` rows."""
    fr = forward_log_return(close, horizon)
    return (fr > threshold).astype(float).where(~fr.isna()).rename(f"fdir_{horizon}")
