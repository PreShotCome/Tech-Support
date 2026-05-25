"""Generic system / time tools — small, always-useful."""
from __future__ import annotations

import platform
from datetime import datetime, timezone

from .base import Tool, ToolRegistry


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


def _build_full_registry() -> ToolRegistry:
    """Single source of truth lives in tools/_all.py — see that file
    for the canonical module list. Keeping a thin wrapper here so
    tool_info / list_tools have nothing to forget to update when a
    new tool module lands."""
    from ._all import build_full_registry as _bfr
    return _bfr()


def _tool_info(name: str) -> dict:
    """Return the full schema for a tool by name.

    Useful when the per-turn loadout doesn't include a tool you want
    details on, or when the prompt-embedded tool list shows a
    description but you need to verify exact parameter names."""
    reg = _build_full_registry()
    tool = reg.get(name)
    if tool is None:
        names = reg.names()
        # Try case-insensitive / substring fallback
        lower = name.lower()
        for n in names:
            if n.lower() == lower or lower in n.lower():
                tool = reg.get(n)
                break
    if tool is None:
        return {
            "error": f"no tool named {name!r}",
            "available_count": len(reg.names()),
            "hint": "Call list_tools to see all registered tools.",
        }
    return {
        "name":        tool.name,
        "description": tool.description,
        "parameters":  tool.parameters_schema,
    }


def _list_tools(category_filter: str | None = None) -> dict:
    """List every registered tool. Optional substring filter on the name."""
    reg = _build_full_registry()
    names = reg.names()
    if category_filter:
        f = category_filter.lower()
        names = [n for n in names if f in n.lower()]
    return {"count": len(names), "tools": names}


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

TOOL_INFO_TOOL = Tool(
    name="tool_info",
    description=(
        "Look up the full JSON schema (description + parameters) for "
        "any registered tool by name. Use this when you want to call "
        "a tool but aren't sure of its exact parameter names — the "
        "prompt-embedded tool list shows descriptions but the schema "
        "is the source of truth. Case-insensitive substring matching "
        "falls back if no exact name hit."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Tool name (e.g. 'osint_query')."},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
    handler=_tool_info,
)

LIST_TOOLS_TOOL = Tool(
    name="list_tools",
    description=(
        "List the names of every tool registered in the system "
        "(not just the ones loaded for this turn). Optional "
        "substring filter on names. Pair with tool_info to drill "
        "into any one's schema."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "category_filter": {
                "type": "string",
                "description": "Substring filter on tool name (e.g. 'memory').",
            },
        },
        "additionalProperties": False,
    },
    handler=_list_tools,
)


def register(registry) -> None:
    for t in (NOW_TOOL, SYSTEM_INFO_TOOL, TOOL_INFO_TOOL, LIST_TOOLS_TOOL):
        registry.register(t)
