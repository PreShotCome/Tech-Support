"""Proteus crypto signals — scan a watchlist, score by RSI + drop from
7-day high, return ranked candidates.

Uses robin_stocks for crypto price history. Symbols come from the
`CRYPTO_WATCHLIST` env var (comma-separated). Default watchlist is
BTC, ETH, SOL, DOGE.

Score = (100 - RSI) + drop_pct. Higher = more oversold and farther
from recent high. RSI uses the classic 14-period Wilder's smoothing.
"""
from __future__ import annotations

import os
from typing import Any

from .base import Tool


DEFAULT_WATCHLIST = ("BTC", "ETH", "SOL", "DOGE")


def _watchlist() -> list[str]:
    raw = os.environ.get("CRYPTO_WATCHLIST", "")
    if not raw.strip():
        return list(DEFAULT_WATCHLIST)
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def _rsi(closes: list[float], period: int = 14) -> float | None:
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
        g = max(d, 0.0)
        l = max(-d, 0.0)
        avg_g = (avg_g * (period - 1) + g) / period
        avg_l = (avg_l * (period - 1) + l) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - (100.0 / (1.0 + rs))


def _history(symbol: str) -> list[float]:
    try:
        import robin_stocks.robinhood as rh
    except ImportError as e:
        raise RuntimeError(
            "robin_stocks not installed. Install with: pip install robin_stocks"
        ) from e

    # Ensure login for crypto endpoints (some require auth).
    try:
        from . import proteus_robinhood
        proteus_robinhood._rh()
    except Exception:
        # Some crypto endpoints don't strictly require login; press on.
        pass

    try:
        data = rh.crypto.get_crypto_historicals(
            symbol, interval="day", span="month", bounds="24_7",
        ) or []
    except Exception:
        data = []
    closes = []
    for row in data:
        try:
            closes.append(float(row.get("close_price", 0)))
        except (TypeError, ValueError):
            continue
    return closes


def _crypto_signals(limit: int = 10) -> dict[str, Any]:
    symbols = _watchlist()
    rows = []
    for sym in symbols:
        closes = _history(sym)
        if len(closes) < 16:
            rows.append({"symbol": sym, "error": "insufficient history"})
            continue
        rsi = _rsi(closes, period=14)
        if rsi is None:
            rows.append({"symbol": sym, "error": "rsi unavailable"})
            continue
        current = closes[-1]
        # 7-day high (last 7 entries)
        window = closes[-7:] if len(closes) >= 7 else closes
        high = max(window)
        drop_pct = (high - current) / high * 100.0 if high > 0 else 0.0
        score = (100.0 - rsi) + drop_pct
        rows.append({
            "symbol": sym,
            "score": round(score, 2),
            "rsi": round(rsi, 2),
            "drop_pct": round(drop_pct, 2),
            "current_price": round(current, 6),
        })

    # sort the rows that have a score; errors fall to the bottom
    scored = [r for r in rows if "score" in r]
    errors = [r for r in rows if "score" not in r]
    scored.sort(key=lambda r: r["score"], reverse=True)
    out = scored[: int(limit)] + errors
    return {
        "watchlist": symbols,
        "n_scored": len(scored),
        "signals": out,
    }


CRYPTO_SIGNALS = Tool(
    name="crypto_signals",
    description=(
        "Scan the crypto watchlist (env CRYPTO_WATCHLIST or default "
        "BTC,ETH,SOL,DOGE) and rank by oversold-and-discounted score: "
        "(100 - RSI14) + percent_drop_from_7d_high. Higher = more "
        "attractive buy candidate by this heuristic."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max results. Default 10."},
        },
        "additionalProperties": False,
    },
    handler=_crypto_signals,
)


def register(registry) -> None:
    registry.register(CRYPTO_SIGNALS)
