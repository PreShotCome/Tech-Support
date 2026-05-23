from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import Strategy


@dataclass
class RsiMeanReversion(Strategy):
    """Long when RSI is oversold (<= entry_long), exit when neutral (>= exit_long).
    No shorting by default — most retail brokers make shorting awkward."""
    entry_long: float = 30.0
    exit_long: float = 55.0
    name: str = "rsi_mr"

    def signal(self, features: pd.DataFrame) -> pd.Series:
        r = features["rsi_14"]
        state = np.zeros(len(r), dtype=float)
        pos = 0.0
        for i, v in enumerate(r.values):
            if np.isnan(v):
                state[i] = pos
                continue
            if pos == 0 and v <= self.entry_long:
                pos = 1.0
            elif pos > 0 and v >= self.exit_long:
                pos = 0.0
            state[i] = pos
        return pd.Series(state, index=features.index, name=self.name)
