"""Wrap a trained probability model as a Strategy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .base import Strategy
from ..models import XgbDirectionModel


@dataclass
class MlSignal(Strategy):
    """Long when the model's P(up) exceeds `long_threshold`. Flat otherwise.

    If `scale=True`, the position is interpolated between flat and full
    as the probability moves from `long_threshold` to 1.0 — gives smaller
    sizing for low-confidence calls.
    """
    model: XgbDirectionModel = None
    long_threshold: float = 0.55
    scale: bool = False
    name: str = "ml_xgb"

    def signal(self, features: pd.DataFrame) -> pd.Series:
        if self.model is None:
            raise RuntimeError("MlSignal needs a trained model")
        X = features[self.model.feature_names]
        p = self.model.predict_proba(X)
        if self.scale:
            # Linear ramp from 0 at long_threshold to 1 at 1.0.
            denom = max(1.0 - self.long_threshold, 1e-6)
            pos = np.clip((p - self.long_threshold) / denom, 0.0, 1.0)
        else:
            pos = np.where(p >= self.long_threshold, 1.0, 0.0)
        return pd.Series(pos, index=features.index, name=self.name)
