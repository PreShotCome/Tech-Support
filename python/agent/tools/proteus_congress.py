"""Proteus congress signals — pull recent politician trades from the
Capitol Trades public BFF and rank by a simple notoriety x dollar-tier
score.

Endpoint: https://bff.capitoltrades.com/trades?per_page=50

Scoring (deliberately simple — refine when there's signal):
  - Only buys count (we're looking for things to buy alongside).
  - dollar_tier_score = log2 of the tier midpoint (so 1k-15k = ~12,
    50k-100k = ~16, 1m-5m = ~21).
  - per ticker: sum of dollar_tier_scores across politicians, weighted
    by number of distinct politicians (politician_count multiplier).

Lazy-imports httpx.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .base import Tool


CAPITOL_TRADES_URL = "https://bff.capitoltrades.com/trades?per_page=50"


# Capitol Trades reports trade size as buckets. Midpoints (rough):
_TIER_MIDPOINTS = {
    "1K–15K": 8_000,
    "15K–50K": 32_000,
    "50K–100K": 75_000,
    "100K–250K": 175_000,
    "250K–500K": 375_000,
    "500K–1M": 750_000,
    "1M–5M": 3_000_000,
    "5M–25M": 15_000_000,
}


def _tier_score(value: str | None) -> float:
    if not value:
        return 0.0
    midpoint = _TIER_MIDPOINTS.get(value, 5_000)
    return math.log2(max(midpoint, 1))


def _congress_signals(limit: int = 10) -> dict[str, Any]:
    try:
        import httpx
    except ImportError as e:
        raise RuntimeError(
            "httpx not installed. Install with: pip install httpx"
        ) from e

    headers = {
        "User-Agent": "Proteus/1.0 (+research)",
        "Accept": "application/json",
    }
    try:
        r = httpx.get(CAPITOL_TRADES_URL, headers=headers, timeout=15.0)
        r.raise_for_status()
    except Exception as e:
        return {"error": f"capitoltrades fetch failed: {e}"}

    payload = r.json() if r.content else {}
    data = payload.get("data") or []

    # Aggregate buys per ticker.
    per_ticker: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total_score": 0.0, "politicians": set(),
                 "latest_traded_at": "", "latest_uid": None}
    )

    for row in data:
        side = (row.get("txType") or row.get("type") or "").lower()
        if "buy" not in side and "purchase" not in side:
            continue
        asset = row.get("asset") or {}
        ticker = (asset.get("assetTicker") or asset.get("ticker") or "").upper()
        if not ticker:
            continue
        politician = row.get("politician") or {}
        pol_name = (politician.get("fullName")
                    or f"{politician.get('firstName', '')} "
                       f"{politician.get('lastName', '')}").strip()
        size_label = row.get("value")  # Capitol Trades uses 'value' for tier label
        score = _tier_score(size_label if isinstance(size_label, str) else None)

        agg = per_ticker[ticker]
        agg["total_score"] += score
        if pol_name:
            agg["politicians"].add(pol_name)
        traded_at = row.get("txDate") or row.get("tradedAt") or ""
        if traded_at > agg["latest_traded_at"]:
            agg["latest_traded_at"] = traded_at
            agg["latest_uid"] = row.get("_id") or row.get("id") or row.get("uid")

    scored = []
    for ticker, agg in per_ticker.items():
        n_pols = len(agg["politicians"])
        # Multiplier: more distinct politicians on the same ticker = stronger signal.
        final = agg["total_score"] * (1.0 + 0.25 * (n_pols - 1))
        scored.append({
            "uid": agg["latest_uid"],
            "ticker": ticker,
            "type": "buy",
            "score": round(final, 2),
            "politicians": sorted(agg["politicians"]),
            "n_politicians": n_pols,
            "traded_at": agg["latest_traded_at"],
        })

    scored.sort(key=lambda r: r["score"], reverse=True)
    return {
        "source": CAPITOL_TRADES_URL,
        "n_signals": len(scored),
        "signals": scored[: int(limit)],
    }


CONGRESS_SIGNALS = Tool(
    name="congress_signals",
    description=(
        "Fetch recent congressional trades from Capitol Trades and "
        "rank by buy-side score: sum of log-dollar-tier weights per "
        "ticker, multiplied by a distinct-politicians factor. Useful "
        "for spotting concentrated buying activity by US politicians."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max tickers to return. Default 10."},
        },
        "additionalProperties": False,
    },
    handler=_congress_signals,
)


def register(registry) -> None:
    registry.register(CONGRESS_SIGNALS)
