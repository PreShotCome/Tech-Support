"""theo_net — small MLP that maps a 6-feature vector to a probability
that the symbol beats SPY over the next 5 trading days.

Architecture: [6 -> 32 -> 16 -> 1] with ReLU between hidden layers and
sigmoid at the output. Tiny on purpose — we want something that trains
on a few hundred bars in seconds, not a deep model that overfits the
thin universe Theo actually uses.

Features (see features.py):
  0: returns_1d              — 1-day total return
  1: returns_5d              — 5-day total return
  2: returns_20d             — 20-day total return
  3: rsi_14                  — Wilder RSI(14), 0..100
  4: volume_ratio            — today's volume / 20d avg volume
  5: congress_signal_strength — placeholder 0..1 score from congress
                                trades for this ticker (defaults to 0
                                when offline)
"""
from __future__ import annotations

import torch
from torch import nn


FEATURE_NAMES = (
    "returns_1d",
    "returns_5d",
    "returns_20d",
    "rsi_14",
    "volume_ratio",
    "congress_signal_strength",
)
INPUT_DIM = len(FEATURE_NAMES)


class TheoNet(nn.Module):
    def __init__(self, input_dim: int = INPUT_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)
