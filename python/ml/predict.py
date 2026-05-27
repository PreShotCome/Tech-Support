"""Inference for theo_net.

Loads python/ml/checkpoints/theo_net.pt and runs a single forward
pass. Raises FileNotFoundError (with a helpful message) if no
checkpoint exists.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .train import CHECKPOINT_PATH


def build_features_for_symbol(symbol: str) -> dict[str, Any]:
    from .features import build_features
    return build_features(symbol)


def predict(symbol: str) -> float:
    import torch
    from .features import features_to_vector
    from .theo_net import TheoNet

    if not Path(CHECKPOINT_PATH).exists():
        raise FileNotFoundError(
            f"no theo_net checkpoint at {CHECKPOINT_PATH}. "
            f"Train first: python -m ml.train --symbols AAPL,MSFT,NVDA --epochs 20"
        )

    state = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=False)
    model = TheoNet()
    model.load_state_dict(state["state_dict"])
    model.eval()

    feats = build_features_for_symbol(symbol)
    vec = torch.tensor([features_to_vector(feats)], dtype=torch.float32)
    with torch.no_grad():
        score = float(model(vec).item())
    return score
