from __future__ import annotations

import pandas as pd

from .base import Strategy


class BuyAndHold(Strategy):
    """The benchmark. If your fancy ML can't beat this, throw it out."""
    name = "buy_hold"

    def signal(self, features: pd.DataFrame) -> pd.Series:
        return pd.Series(1.0, index=features.index, name=self.name)
