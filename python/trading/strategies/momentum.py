from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import Strategy


@dataclass
class MomentumCrossover(Strategy):
    """Long when fast EMA > slow EMA, flat otherwise. Classic trend follow."""
    fast: int = 12
    slow: int = 60
    name: str = "momentum_xover"

    def signal(self, features: pd.DataFrame) -> pd.Series:
        # We reconstruct EMAs from the cumulative 1-bar log returns.
        # ret_1 in features is log return of close; cumsum -> log price (up to a constant).
        log_price = features["ret_1"].fillna(0.0).cumsum()
        ema_fast = log_price.ewm(span=self.fast, adjust=False).mean()
        ema_slow = log_price.ewm(span=self.slow, adjust=False).mean()
        sig = np.where(ema_fast > ema_slow, 1.0, 0.0)
        return pd.Series(sig, index=features.index, name=self.name)
