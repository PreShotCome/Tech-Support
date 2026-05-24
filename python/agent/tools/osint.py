"""OSINT tools — live intel via the Osiris API.

Osiris (https://github.com/simplifaisoul/osiris) is a public OSINT
dashboard hosted at https://www.osirisai.live. Its /api/* endpoints
return JSON aggregated from public sources: USGS earthquakes, NASA
FIRMS fires, OpenSky flights, GDELT events, NOAA weather, etc.

This tool lets Theo hit those endpoints when the human asks about
real-world intel without having to leave the chat to go look it up.

Reference docs live in `docs/research/osiris/` and are indexed into
the semantic memory, so `semantic_recall` can also surface them.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from .base import Tool


OSIRIS_BASE = "https://www.osirisai.live"

# Curated map of domain -> endpoint path. Add more here as needed;
# the Osiris repo exposes more than this but these are the high-value
# ones for a chat agent to pull on demand.
OSIRIS_DOMAINS: dict[str, str] = {
    "earthquakes":   "/api/earthquakes",
    "fires":         "/api/fires",
    "flights":       "/api/flights",
    "maritime":      "/api/maritime",
    "news":          "/api/news",
    "live_news":     "/api/live-news",
    "gdelt":         "/api/gdelt",
    "weather":       "/api/weather",
    "air_quality":   "/api/air-quality",
    "satellites":    "/api/satellites",
    "space_weather": "/api/space-weather",
    "cctv":          "/api/cctv",
    "frontlines":    "/api/frontlines",
    "country_risk":  "/api/country-risk",
    "infrastructure":"/api/infrastructure",
    "cyber_threats": "/api/cyber-threats",
    "markets":       "/api/markets",
    "region_dossier":"/api/region-dossier",
    "scanner":       "/api/scanner",         # port scan; needs params
    "osint_ip":      "/api/osint/ip",        # IP lookup; needs params
    "osint_sweep":   "/api/osint/sweep",     # DNS/WHOIS/SSL sweep; needs params
    "sentinel":      "/api/sentinel",
    "health":        "/api/health",
}


def _osint_query(domain: str, params: dict[str, Any] | None = None,
                 max_chars: int = 6000) -> dict[str, Any]:
    """Hit an Osiris API endpoint and return parsed JSON (or text)."""
    try:
        import requests
    except ImportError:
        return {"error": "requests not installed (install with [agent] extra)"}

    if domain not in OSIRIS_DOMAINS:
        return {
            "error": f"unknown domain {domain!r}",
            "available": sorted(OSIRIS_DOMAINS.keys()),
        }

    url = OSIRIS_BASE + OSIRIS_DOMAINS[domain]
    if params:
        url = f"{url}?{urlencode(params)}"

    try:
        resp = requests.get(
            url, timeout=20,
            headers={"User-Agent": "TechSupport/Theo (Osiris client)"},
        )
    except requests.RequestException as e:
        return {"error": f"fetch failed: {type(e).__name__}: {e}", "url": url}

    if resp.status_code >= 400:
        body = resp.text[:500]
        return {
            "error": f"HTTP {resp.status_code}",
            "url": url,
            "body_preview": body,
        }

    # Try JSON first; fall back to text.
    try:
        data = resp.json()
        # Large payloads (e.g. /fires can be 250KB) — truncate after
        # serializing back for a stable preview the model can scan.
        payload = json.dumps(data, ensure_ascii=False)
        truncated = len(payload) > max_chars
        if truncated:
            payload = payload[:max_chars]
        return {
            "domain": domain,
            "url": url,
            "status_code": resp.status_code,
            "truncated": truncated,
            "total_chars": len(json.dumps(data, ensure_ascii=False)),
            "data": json.loads(payload) if not truncated else payload,
        }
    except ValueError:
        text = resp.text
        truncated = len(text) > max_chars
        return {
            "domain": domain,
            "url": url,
            "status_code": resp.status_code,
            "truncated": truncated,
            "text": text[:max_chars],
        }


OSINT_QUERY_TOOL = Tool(
    name="osint_query",
    description=(
        "Pull live open-source intelligence from the Osiris API "
        "(https://www.osirisai.live). Use this for real-world intel "
        "the human asks about — recent earthquakes, active fires, "
        "flights in the air, news streams, conflict frontlines, cyber "
        "CVEs, etc. Pick a `domain` from the supported list. Some "
        "domains (scanner, osint_ip, osint_sweep) accept `params` for "
        "the target (e.g. {'host': '8.8.8.8'}). Background docs live "
        "in `docs/research/osiris/` and are searchable via "
        "`semantic_recall`."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": (
                    "Which Osiris endpoint to hit. One of: "
                    + ", ".join(sorted(OSIRIS_DOMAINS.keys()))
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Optional query-string params for endpoints that "
                    "need a target (scanner / osint_ip / osint_sweep)."
                ),
                "additionalProperties": True,
            },
            "max_chars": {
                "type": "integer",
                "description": "Response truncation cap. Default 6000.",
            },
        },
        "required": ["domain"],
        "additionalProperties": False,
    },
    handler=_osint_query,
)


def register(registry) -> None:
    registry.register(OSINT_QUERY_TOOL)
