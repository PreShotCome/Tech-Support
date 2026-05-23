"""Durable agent memory — append-only notes file.

The brain itself is stateless across runs (a fresh chat each time).
This tool gives it a notebook it can scribble in: 'user prefers X',
'last trading conversation we covered Y', etc."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .base import Tool


def _default_path() -> Path:
    return Path.home() / ".techsupport_agent" / "notes.md"


def _note(text: str, path: str | None = None) -> str:
    p = Path(path) if path else _default_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n## {ts}\n\n{text.strip()}\n")
    return f"noted ({p})"


def _recall(query: str | None = None, last_n: int = 20, path: str | None = None) -> str:
    p = Path(path) if path else _default_path()
    if not p.exists():
        return "(no notes yet)"
    text = p.read_text(encoding="utf-8")
    if query:
        # Coarse substring filter; keep paragraphs matching the query.
        blocks = text.split("\n## ")
        hits = [b for b in blocks if query.lower() in b.lower()]
        if not hits:
            return f"(no notes matching '{query}')"
        return "\n## ".join(hits[-last_n:])
    blocks = text.split("\n## ")
    return "\n## ".join(blocks[-last_n:])


NOTE_TOOL = Tool(
    name="note",
    description="Append a note to the agent's durable memory. Use this for "
                "things the user says to remember or facts that should "
                "persist across sessions.",
    parameters_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Note text to append."},
        },
        "required": ["text"],
        "additionalProperties": False,
    },
    handler=_note,
)

RECALL_TOOL = Tool(
    name="recall",
    description="Read recent notes from durable memory. Optional query "
                "filters to notes containing that substring.",
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Optional substring filter."},
            "last_n": {"type": "integer", "description": "Number of recent notes to return. Default 20."},
        },
        "additionalProperties": False,
    },
    handler=_recall,
)


def register(registry) -> None:
    for t in (NOTE_TOOL, RECALL_TOOL):
        registry.register(t)
