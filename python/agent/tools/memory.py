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


def _search_transcripts(query: str, max_hits: int = 20) -> dict:
    """Substring search across past chat transcripts."""
    from ..transcript_logger import TranscriptLogger
    hits = TranscriptLogger.search(query, max_hits=max_hits)
    return {
        "query": query,
        "n_hits": len(hits),
        "hits": hits,
    }


def _list_transcripts(limit: int = 20) -> dict:
    from ..transcript_logger import TranscriptLogger
    paths = TranscriptLogger.list_transcripts()
    paths = paths[-limit:]
    return {
        "n_transcripts": len(paths),
        "files": [{"name": p.name, "bytes": p.stat().st_size} for p in paths],
    }


SEARCH_TRANSCRIPTS_TOOL = Tool(
    name="search_transcripts",
    description=(
        "Search across all past chat transcripts for a substring. Use this "
        "to recall what was discussed in previous sessions, even if the "
        "user did not explicitly take a note."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Substring to search for."},
            "max_hits": {"type": "integer", "description": "Default 20."},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    handler=_search_transcripts,
)

LIST_TRANSCRIPTS_TOOL = Tool(
    name="list_transcripts",
    description="List the most recent chat transcript files on disk.",
    parameters_schema={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Default 20."},
        },
        "additionalProperties": False,
    },
    handler=_list_transcripts,
)


def _semantic_recall(query: str, top_k: int = 5) -> dict:
    """Semantic search across past transcripts using local embeddings.
    Lazy: builds the index on first call, then incrementally on demand.
    Returns the most relevant chunks ranked by similarity."""
    try:
        from ..embeddings import TranscriptIndex
    except ImportError as e:
        return {
            "error": f"semantic recall unavailable ({e}). Install with: pip install -e .[agent]",
            "fallback": "use search_transcripts for substring search",
        }
    try:
        idx = TranscriptIndex()
        results = idx.search(query, top_k=top_k)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return {
        "query": query,
        "n_results": len(results),
        "results": results,
    }


SEMANTIC_RECALL_TOOL = Tool(
    name="semantic_recall",
    description=(
        "Semantically search past transcripts for relevant context. Unlike "
        "search_transcripts (substring match), this finds passages that "
        "are related in meaning even when phrased differently. Use this "
        "for 'what did we discuss about X' questions where you don't know "
        "the exact words that were used."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural-language description of what to find."},
            "top_k": {"type": "integer", "description": "Number of results. Default 5."},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    handler=_semantic_recall,
)


def register(registry) -> None:
    for t in (NOTE_TOOL, RECALL_TOOL, SEARCH_TRANSCRIPTS_TOOL,
              LIST_TRANSCRIPTS_TOOL, SEMANTIC_RECALL_TOOL):
        registry.register(t)
