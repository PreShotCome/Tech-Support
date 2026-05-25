"""OpenBB tool — live financial data.

OpenBB (https://openbb.co) is a free open-source financial data
platform. The Python SDK aggregates equities, crypto, fundamentals,
macro, and more from multiple providers (yfinance is the default
free path; commercial providers can be plugged in with API keys).

Requires `openbb` installed in the venv:
    pip install openbb

Reference docs: docs/research/OpenBB/

Background: the Tech-Support trading bot is an equal-weight basket
of megacaps on Alpaca paper. OpenBB is the natural data source when
Theo needs richer info than the existing market_clock / portfolio
tools provide — fundamentals, sector breakdowns, alternate prices,
macro context."""
from __future__ import annotations

from typing import Any

from .base import Tool


# Curated subset of OpenBB SDK calls. Each maps a `domain` keyword to
# a function that fetches the data. Keep this list small and high-value;
# OpenBB's full SDK has hundreds of endpoints, but most casual chat
# questions land in a few categories.
def _openbb():
    """Lazy import so missing OpenBB doesn't crash the agent on startup."""
    from openbb import obb
    return obb


def _quote(symbol: str) -> dict[str, Any]:
    obb = _openbb()
    out = obb.equity.price.quote(symbol=symbol, provider="yfinance")
    return {"symbol": symbol, "data": _to_dict(out)}


def _historical(symbol: str, period: str = "1mo") -> dict[str, Any]:
    obb = _openbb()
    out = obb.equity.price.historical(
        symbol=symbol, provider="yfinance",
        start_date=None, end_date=None,
    )
    rows = _to_dict(out)
    if isinstance(rows, list):
        # Trim to most-recent N depending on period
        cap = {"1d": 1, "5d": 5, "1mo": 22, "3mo": 66, "1y": 252}.get(period, 22)
        rows = rows[-cap:]
    return {"symbol": symbol, "period": period, "rows": rows}


def _fundamentals(symbol: str) -> dict[str, Any]:
    obb = _openbb()
    try:
        out = obb.equity.fundamental.overview(symbol=symbol, provider="yfinance")
    except Exception:
        out = obb.equity.profile(symbol=symbol, provider="yfinance")
    return {"symbol": symbol, "data": _to_dict(out)}


def _to_dict(obb_result: Any) -> Any:
    """OpenBB returns OBBject wrappers with .to_dict / .results. Flatten."""
    if hasattr(obb_result, "results"):
        results = obb_result.results
    else:
        results = obb_result
    if isinstance(results, list):
        return [getattr(r, "model_dump", lambda: r)() for r in results]
    if hasattr(results, "model_dump"):
        return results.model_dump()
    return results


DOMAINS = {
    "quote":        ("symbol",),
    "historical":   ("symbol", "period"),
    "fundamentals": ("symbol",),
}


def _openbb_query(domain: str, symbol: str | None = None,
                  period: str = "1mo") -> dict[str, Any]:
    """Live financial query via OpenBB."""
    try:
        import openbb  # noqa: F401
    except ImportError:
        return {
            "error": "openbb not installed",
            "install": "pip install openbb (in the python/.venv)",
            "available_domains": list(DOMAINS.keys()),
        }

    if domain not in DOMAINS:
        return {"error": f"unknown domain {domain!r}", "available": list(DOMAINS.keys())}
    if not symbol:
        return {"error": "symbol required for all OpenBB domains"}

    try:
        if domain == "quote":
            return _quote(symbol.upper())
        if domain == "historical":
            return _historical(symbol.upper(), period=period)
        if domain == "fundamentals":
            return _fundamentals(symbol.upper())
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "domain": domain, "symbol": symbol}


OPENBB_QUERY_TOOL = Tool(
    name="openbb_query",
    description=(
        "Live financial data via OpenBB (https://openbb.co). Pick a "
        "`domain`: 'quote' for current price/bid/ask, 'historical' "
        "for OHLCV bars (with optional `period`: 1d/5d/1mo/3mo/1y), "
        "'fundamentals' for company overview/profile. Symbol is "
        "case-insensitive. Uses yfinance under the hood — no API key "
        "needed for basic queries. Returns parsed dicts. Background "
        "docs in docs/research/OpenBB/."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "One of: quote, historical, fundamentals.",
            },
            "symbol": {"type": "string", "description": "Ticker symbol (e.g. AAPL)."},
            "period": {
                "type": "string",
                "description": "For historical only. 1d/5d/1mo/3mo/1y. Default 1mo.",
            },
        },
        "required": ["domain", "symbol"],
        "additionalProperties": False,
    },
    handler=_openbb_query,
)


def register(registry) -> None:
    registry.register(OPENBB_QUERY_TOOL)
