"""Identity-related tools — the system manages its own name.

On first launch the system has no name. The system prompt instructs the
model to choose one and persist it via `set_name`. From then on every
session loads the name and refers to itself by it."""
from __future__ import annotations

from .base import Tool
from ..state import load_name, save_name, name_path


def _set_name(name: str) -> str:
    if not name or not name.strip():
        return "set_name failed: empty name"
    if len(name) > 60:
        return f"set_name failed: name too long ({len(name)} chars; max 60)"
    p = save_name(name)
    return f"name set to {name!r} and saved to {p}"


def _get_name() -> dict:
    n = load_name()
    return {
        "name": n,
        "is_set": n is not None,
        "path": str(name_path()),
    }


SET_NAME_TOOL = Tool(
    name="set_name",
    description=(
        "Choose and persist your own name. Call this on first launch "
        "when you have no name yet, after you've decided what to call "
        "yourself. Once set, the name is stable across sessions; do not "
        "change it without the human's explicit request."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The name you choose for yourself."},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
    handler=_set_name,
)

GET_NAME_TOOL = Tool(
    name="get_name",
    description="Return the system's currently-stored name, if any.",
    parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_get_name,
)


def register(registry) -> None:
    for t in (SET_NAME_TOOL, GET_NAME_TOOL):
        registry.register(t)
