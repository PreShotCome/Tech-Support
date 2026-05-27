"""Feature builder for theo_net.

build_features(symbol, asof_date) returns a dict with the 6 columns
documented in theo_net.FEATURE_NAMES. Lazy-imports yfinance so this
module is importable even when the [ml] extra isn't installed (the
import will fail at call time with a clear error).

Return shape is a plain dict so it's easy to log and pass through the
agent tool boundary as JSON.
"""
from __future__ import annotations

from datetime import date as _date, timedelta
from typing import Any


def _rsi(closes, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        if d >= 0:
            gains += d
        else:
            losses -= d
    avg_g = gains / period
    avg_l = losses / period
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0.0)) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - (100.0 / (1.0 + rs))


def _congress_score_for(symbol: str) -> float:
    """Best-effort: call the congress_signals tool function if it's
    available and find a matching ticker. Returns 0..1."""
    try:
        from agent.tools.proteus_congress import _congress_signals
        data = _congress_signals(limit=50)
    except Exception:
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    signals = data.get("signals") or []
    scores = [float(s.get("score", 0)) for s in signals]
    if not scores:
        return 0.0
    max_score = max(scores) or 1.0
    for s in signals:
        if str(s.get("ticker", "")).upper() == symbol.upper():
            return min(1.0, float(s.get("score", 0)) / max_score)
    return 0.0


def build_features(symbol: str, asof_date: _date | None = None) -> dict[str, Any]:
    """Compute the 6 features for `symbol` as of `asof_date` (default:
    today). Returns a dict matching theo_net.FEATURE_NAMES. Raises if
    yfinance isn't installed or the symbol has insufficient history."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError(
            "yfinance not installed. Install with: pip install -e .[ml]"
        ) from e

    if asof_date is None:
        asof_date = _date.today()
    # Need ~30 trading days of history; pad start to be safe.
    start = asof_date - timedelta(days=90)
    end = asof_date + timedelta(days=1)
    df = yf.Ticker(symbol).history(start=start.isoformat(), end=end.isoformat(),
                                   auto_adjust=True)
    if df is None or len(df) < 22:
        raise RuntimeError(f"insufficient history for {symbol}")

    closes = df["Close"].tolist()
    volumes = df["Volume"].tolist()

    last = closes[-1]
    r1 = (last / closes[-2]) - 1.0 if len(closes) >= 2 else 0.0
    r5 = (last / closes[-6]) - 1.0 if len(closes) >= 6 else 0.0
    r20 = (last / closes[-21]) - 1.0 if len(closes) >= 21 else 0.0
    rsi = _rsi(closes[-30:], period=14) or 50.0
    avg_vol_20 = sum(volumes[-20:]) / 20.0 if len(volumes) >= 20 else (sum(volumes) / max(1, len(volumes)))
    vol_ratio = (volumes[-1] / avg_vol_20) if avg_vol_20 > 0 else 1.0

    return {
        "returns_1d":               float(r1),
        "returns_5d":               float(r5),
        "returns_20d":              float(r20),
        "rsi_14":                   float(rsi),
        "volume_ratio":             float(vol_ratio),
        "congress_signal_strength": float(_congress_score_for(symbol)),
    }


def features_to_vector(feats: dict[str, Any]) -> list[float]:
    from .theo_net import FEATURE_NAMES
    return [float(feats[name]) for name in FEATURE_NAMES]
