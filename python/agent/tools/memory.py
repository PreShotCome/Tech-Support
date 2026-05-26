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


def _recall_episodic(query: str, top_k: int = 5,
                     prefer_recent_days: float = 30.0) -> dict:
    """Episodic-biased semantic search.

    Same vector pool as semantic_recall, but with two filters that
    weight the result toward 'what happened recently' instead of
    'what's true in general':

      1. Drops knowledge/ chunks (research docs) — episodic memory is
         conversation only.
      2. Boosts chunks by recency: a chunk created within the last
         `prefer_recent_days` gets a multiplier that decays linearly
         from 1.4 (today) to 1.0 (at the cutoff). Older chunks aren't
         demoted; they just don't get the boost.

    Use this when the human asks 'when did we...' / 'what happened
    last...' / 'remember when...' — anything where temporal proximity
    matters more than semantic neighborhood."""
    try:
        from ..embeddings import TranscriptIndex
    except ImportError as e:
        return {
            "error": f"semantic recall unavailable ({e})",
            "fallback": "use search_transcripts for substring search",
        }
    try:
        idx = TranscriptIndex()
        # Pull a wider pool than we'll keep so the recency weight has
        # room to re-rank.
        raw = idx.search(query, top_k=top_k * 4, update_recall=False)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    # Filter to conversational sources only
    convo = [h for h in (raw or [])
             if not str(h.get("source", "")).startswith("knowledge/")]
    if not convo:
        return {"query": query, "n_results": 0, "results": []}

    # Recency boost: source filename like 2026-05-25-031400.md carries
    # the date. Parse it and compute a 0..1 recency factor over the
    # prefer_recent_days window.
    import re as _re
    from datetime import datetime
    today = datetime.now()

    def _recency_mult(source: str) -> float:
        m = _re.match(r"(\d{4}-\d{2}-\d{2})", source)
        if not m:
            return 1.0
        try:
            d = datetime.strptime(m.group(1), "%Y-%m-%d")
        except Exception:
            return 1.0
        age_days = max(0.0, (today - d).total_seconds() / 86400.0)
        if age_days >= prefer_recent_days:
            return 1.0
        # Linear from 1.4 (today) to 1.0 (at cutoff)
        return 1.0 + 0.4 * (1.0 - age_days / prefer_recent_days)

    scored = []
    for h in convo:
        boost = _recency_mult(h.get("source", ""))
        eff = h.get("score", 0.0) * boost
        h2 = dict(h)
        h2["episodic_score"] = eff
        h2["recency_boost"] = round(boost, 3)
        scored.append((eff, h2))

    scored.sort(key=lambda t: t[0], reverse=True)
    out = [h for _eff, h in scored[:top_k]]
    return {
        "query":      query,
        "n_results":  len(out),
        "results":    out,
        "filter":     "transcripts only (knowledge docs excluded)",
        "recency_window_days": prefer_recent_days,
    }


RECALL_EPISODIC_TOOL = Tool(
    name="recall_episodic",
    description=(
        "Episodic-biased recall — searches the same memory as "
        "semantic_recall but FILTERS to conversation transcripts only "
        "(no research docs) AND boosts recent chunks linearly over a "
        "configurable window. Use when the human asks 'what did we "
        "talk about last week,' 'when did we decide X,' 'remember "
        "when…' — anything where temporal proximity matters more than "
        "global semantic match. Returns the same shape as "
        "semantic_recall plus `episodic_score` and `recency_boost` "
        "per hit so you can see why each one surfaced."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to recall, in natural language."},
            "top_k": {"type": "integer", "description": "Results to return. Default 5."},
            "prefer_recent_days": {
                "type": "number",
                "description": (
                    "Recency window in days. Chunks newer than this get "
                    "a boost up to +40% (linear, max at today). Older "
                    "chunks aren't demoted, just don't get the boost. "
                    "Default 30."
                ),
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    handler=_recall_episodic,
)


def _pin_memory(query: str, top_k: int = 3) -> dict:
    """Pin the top-K chunks matching `query` so they rank higher in
    future searches. Importance set to +1.0 (max boost, +50%)."""
    try:
        from ..embeddings import TranscriptIndex
    except ImportError as e:
        return {"error": f"semantic memory unavailable ({e})"}
    try:
        idx = TranscriptIndex()
        modified = idx.set_importance(query, importance=1.0, top_k=top_k)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return {
        "query": query,
        "n_pinned": len(modified),
        "pinned": modified,
    }


def _forget_memory(query: str, top_k: int = 3) -> dict:
    """Soft-forget the top-K chunks matching `query`. Importance set
    to -1.0 — they stay in the index (perfect recollection is the rule)
    but are demoted to 0.5x weight, so they only surface when there's
    no better match."""
    try:
        from ..embeddings import TranscriptIndex
    except ImportError as e:
        return {"error": f"semantic memory unavailable ({e})"}
    try:
        idx = TranscriptIndex()
        modified = idx.set_importance(query, importance=-1.0, top_k=top_k)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return {
        "query": query,
        "n_demoted": len(modified),
        "demoted": modified,
    }


def _memory_status() -> dict:
    try:
        from ..embeddings import TranscriptIndex
    except ImportError as e:
        return {"error": f"semantic memory unavailable ({e})"}
    try:
        return TranscriptIndex().status()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


PIN_MEMORY_TOOL = Tool(
    name="pin_memory",
    description=(
        "Pin past transcript chunks matching `query` so they rank higher "
        "in future semantic searches (+50% weight). Use when the human "
        "says something is important to remember, or when a particular "
        "fact / preference / decision should always surface."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural-language description of what to pin."},
            "top_k": {"type": "integer", "description": "How many matching chunks to pin. Default 3."},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    handler=_pin_memory,
)

FORGET_MEMORY_TOOL = Tool(
    name="forget_memory",
    description=(
        "Soft-forget past transcript chunks matching `query` by demoting "
        "their search weight to 0.5x. The chunks stay in the index — "
        "this system never actually deletes memory — but they will only "
        "surface when nothing better matches. Use for noise, dead ends, "
        "or content the human explicitly wants to deprioritize."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to soft-forget."},
            "top_k": {"type": "integer", "description": "How many matching chunks to demote. Default 3."},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    handler=_forget_memory,
)

MEMORY_STATUS_TOOL = Tool(
    name="memory_status",
    description=(
        "Summary of the semantic memory index: total chunks, number of "
        "indexed transcripts, pinned vs soft-forgotten counts, and the "
        "top 5 most-frequently-recalled chunks (the consolidated ones)."
    ),
    parameters_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    handler=_memory_status,
)


def register(registry) -> None:
    for t in (NOTE_TOOL, RECALL_TOOL, SEARCH_TRANSCRIPTS_TOOL,
              LIST_TRANSCRIPTS_TOOL, SEMANTIC_RECALL_TOOL,
              RECALL_EPISODIC_TOOL,
              PIN_MEMORY_TOOL, FORGET_MEMORY_TOOL, MEMORY_STATUS_TOOL):
        registry.register(t)
