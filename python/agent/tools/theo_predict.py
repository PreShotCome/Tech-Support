"""theo_predict tool — wraps the ml.theo_net model.

Graceful behavior when there's no checkpoint: returns an error string
pointing the human at `python -m ml.train ...`. Lazy imports torch /
yfinance so the agent boots without them.
"""
from __future__ import annotations

from typing import Any

from .base import Tool


def _theo_predict(symbol: str) -> dict[str, Any]:
    symbol = symbol.upper().strip()
    try:
        from ml.predict import predict, build_features_for_symbol
    except ImportError as e:
        return {
            "error": f"ml package unavailable ({e}).",
            "hint":  "Install with: pip install -e .[ml]",
        }
    try:
        score = predict(symbol)
        feats = build_features_for_symbol(symbol)
    except FileNotFoundError as e:
        return {
            "error": str(e),
            "hint":  "Train first: python -m ml.train --symbols AAPL,MSFT,NVDA --epochs 20",
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return {
        "symbol":   symbol,
        "score":    float(score),
        "features": feats,
    }


THEO_PREDICT_TOOL = Tool(
    name="theo_predict",
    description=(
        "Predict the probability that `symbol` outperforms SPY over "
        "the next 5 trading days using the locally-trained theo_net "
        "model. Returns a 0..1 score and the input features. If no "
        "checkpoint exists, returns an error pointing to the train "
        "command."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol."},
        },
        "required": ["symbol"],
        "additionalProperties": False,
    },
    handler=_theo_predict,
)


def register(registry) -> None:
    registry.register(THEO_PREDICT_TOOL)
