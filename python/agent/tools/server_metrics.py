"""Netdata tool — live server metrics from the local Netdata daemon.

Netdata (https://netdata.cloud) is a real-time per-second metrics
agent. When installed, it exposes a REST API at http://localhost:19999/
with thousands of pre-built dashboards covering CPU, RAM, disk, net,
processes, etc.

Requires Netdata running on the same machine as the bridge:
    # Linux/macOS
    bash <(curl -SsL https://my-netdata.io/kickstart.sh)
    # Windows
    Download from https://www.netdata.cloud/download/

Reference docs: docs/research/netdata/

This tool is useful when Ian asks about machine state — "is anything
running hot?", "what's CPU look like?", "any alarms firing?"."""
from __future__ import annotations

from typing import Any

from .base import Tool


DEFAULT_BASE = "http://localhost:19999"

# Curated common chart IDs. Netdata's `/api/v1/charts` exposes the
# full catalog (thousands). These are the high-value ones.
CHARTS = {
    "cpu":          "system.cpu",
    "ram":          "system.ram",
    "load":         "system.load",
    "swap":         "system.swap",
    "net":          "system.net",
    "disk_io":      "system.io",
    "disk_space":   "disk_space._",
    "processes":    "system.processes",
    "uptime":       "system.uptime",
    "ctx":          "system.ctxt",
}


def _server_metrics(domain: str = "cpu", seconds_back: int = 60,
                    base_url: str = DEFAULT_BASE) -> dict[str, Any]:
    """Pull a chart's recent data from the local Netdata API."""
    try:
        import requests
    except ImportError:
        return {"error": "requests not installed (in [agent] extra)"}

    if domain == "info":
        url = f"{base_url}/api/v1/info"
    elif domain == "alarms":
        url = f"{base_url}/api/v1/alarms?all=false"
    elif domain == "charts_list":
        url = f"{base_url}/api/v1/charts"
    else:
        chart = CHARTS.get(domain, domain)
        url = f"{base_url}/api/v1/data?chart={chart}&after=-{int(seconds_back)}&points=20&format=json"

    try:
        resp = requests.get(url, timeout=5)
    except requests.RequestException as e:
        return {
            "error": f"{type(e).__name__}: {e}",
            "hint": (
                "Is Netdata running on this machine? Start with "
                "`sudo systemctl start netdata` on Linux, or check "
                "Services on Windows. Default endpoint is "
                f"{base_url}."
            ),
        }
    if resp.status_code >= 400:
        return {"error": f"HTTP {resp.status_code}", "url": url, "body": resp.text[:300]}
    try:
        data = resp.json()
    except ValueError:
        return {"text": resp.text[:2000], "url": url}

    # Trim very large responses
    if domain == "charts_list" and isinstance(data, dict):
        names = sorted((data.get("charts") or {}).keys())[:80]
        return {"chart_count_total": len(data.get("charts") or {}),
                "first_80_names": names}
    return {"domain": domain, "url": url, "data": data}


SERVER_METRICS_TOOL = Tool(
    name="server_metrics",
    description=(
        "Live machine metrics via the local Netdata daemon "
        "(http://localhost:19999). `domain` shortcuts: cpu, ram, "
        "load, swap, net, disk_io, disk_space, processes, uptime, "
        "ctx — or 'info' for system overview, 'alarms' for active "
        "alerts, 'charts_list' for the full chart catalog, or pass "
        "any raw chart ID directly. `seconds_back` controls the "
        "time window (default 60s). Use this when the human asks "
        "about machine state or load. Netdata must be installed and "
        "running locally; the tool returns a clear error pointing at "
        "setup docs otherwise."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": (
                    "Shortcut (cpu/ram/load/swap/net/disk_io/disk_space/"
                    "processes/uptime/ctx/info/alarms/charts_list) or a "
                    "raw Netdata chart ID."
                ),
            },
            "seconds_back": {
                "type": "integer",
                "description": "Time window in seconds. Default 60.",
            },
            "base_url": {
                "type": "string",
                "description": "Override base URL. Default http://localhost:19999.",
            },
        },
        "additionalProperties": False,
    },
    handler=_server_metrics,
)


def register(registry) -> None:
    registry.register(SERVER_METRICS_TOOL)
