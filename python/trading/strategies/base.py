"""Strategy interface.

A strategy takes a features DataFrame and returns a target-position
Series, one value per bar:
    +1  fully long
     0  flat
    -1  fully short
Fractions between are allowed.

The crucial rule: signal at bar t may use features from bars <= t, but
the trade fills at the *open of bar t+1*. The backtest engine enforces
this — strategies don't need to worry about lag themselves, but they
also must not peek at future bars when computing features.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    name: str = "strategy"

    @abstractmethod
    def signal(self, features: pd.DataFrame) -> pd.Series:
        """Return a series indexed by the same timestamps as `features`
        with values in [-1, 1]."""
