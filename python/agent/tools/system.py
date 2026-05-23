"""Generic system / time tools — small, always-useful."""
from __future__ import annotations

import platform
from datetime import datetime, timezone

from .base import Tool


def _now(timezone_name: str = "UTC") -> str:
    if timezone_name.upper() == "UTC":
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    return datetime.now().isoformat(timespec="seconds")


def _system_info() -> dict:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "hostname": platform.node(),
    }


NOW_TOOL = Tool(
    name="now",
    description="Return the current date and time. Defaults to UTC.",
    parameters_schema={
        "type": "object",
        "properties": {
            "timezone_name": {"type": "string", "description": "'UTC' or 'local'."},
        },
        "additionalProperties": False,
    },
    handler=_now,
)

SYSTEM_INFO_TOOL = Tool(
    name="system_info",
    description="Return information about the host machine (OS, Python version, hostname).",
    parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_system_info,
)


def register(registry) -> None:
    for t in (NOW_TOOL, SYSTEM_INFO_TOOL):
        registry.register(t)
