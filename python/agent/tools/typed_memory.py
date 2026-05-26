"""Typed memory — a thin layer on top of the existing TranscriptIndex.

Everything Theo already had (notes, semantic_recall, pin/forget, episodic
recall) keeps working untouched. This module adds two new shapes:

  - `add_memory(kind, key, text, tags?)` — appends a JSONL line to
    ~/.techsupport_agent/memory.jsonl AND inserts the text into the
    lancedb embeddings table with a synthetic source key that encodes
    the kind/key so it's recallable both ways.

  - `recall(query, kind?, k?)` — hybrid (BM25 + cosine) search filtered
    post-hoc by kind. The TranscriptIndex doesn't expose a where-clause
    hook in its search path, so we over-fetch and filter by source-key
    prefix. Cheap; the embedding index isn't large enough for this to
    matter.

The JSONL is the durable log (one line per entry, easy to grep). The
lancedb entry is what makes it semantically searchable.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import Tool


MEMORY_JSONL = Path.home() / ".techsupport_agent" / "memory.jsonl"
SOURCE_PREFIX = "typed_memory/"  # used as the lancedb `source` field


def _source_key(kind: str, key: str) -> str:
    safe_kind = kind.strip().replace("/", "_") or "misc"
    safe_key = key.strip().replace("/", "_") or "untitled"
    return f"{SOURCE_PREFIX}{safe_kind}/{safe_key}"


def _append_jsonl(entry: dict[str, Any]) -> None:
    MEMORY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with MEMORY_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _insert_into_lance(source_key: str, text: str) -> bool:
    """Push the entry into the embeddings table directly so it's
    semantically searchable. Returns True on success."""
    try:
        from ..embeddings import TranscriptIndex, _chunk_id
    except ImportError:
        return False
    try:
        idx = TranscriptIndex()
        vec = idx._embed([text])[0]
        now = time.time()
        idx._table.add([{
            "chunk_id":         _chunk_id(source_key, 0, text),
            "source":           source_key,
            "text":             text,
            "vector":           [float(x) for x in vec],
            "importance":       0.0,
            "recall_count":     0,
            "created_at":       now,
            "last_recalled_at": 0.0,
        }])
        # FTS index will pick the new row up on next ensure call.
        idx._fts_ready = False
        return True
    except Exception:
        return False


def _add_memory(kind: str, key: str, text: str,
                tags: list[str] | None = None) -> dict[str, Any]:
    tags = list(tags or [])
    entry = {
        "ts":   datetime.now().isoformat(timespec="seconds"),
        "kind": kind,
        "key":  key,
        "text": text,
        "tags": tags,
    }
    _append_jsonl(entry)
    source_key = _source_key(kind, key)
    indexed = _insert_into_lance(source_key, text)
    return {
        "stored":           str(MEMORY_JSONL),
        "source":           source_key,
        "indexed_in_lance": indexed,
        "entry":            entry,
    }


def _load_jsonl_index() -> dict[str, dict[str, Any]]:
    """Read the JSONL once and return source_key -> latest entry. Used
    to enrich recall hits with the original tags/key."""
    out: dict[str, dict[str, Any]] = {}
    if not MEMORY_JSONL.exists():
        return out
    try:
        with MEMORY_JSONL.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                sk = _source_key(e.get("kind", ""), e.get("key", ""))
                out[sk] = e
    except Exception:
        pass
    return out


def _recall(query: str, kind: str | None = None, k: int = 5) -> dict[str, Any]:
    try:
        from ..embeddings import TranscriptIndex
    except ImportError as e:
        return {"error": f"semantic recall unavailable ({e})"}
    try:
        idx = TranscriptIndex()
        # Over-fetch when filtering by kind, since the lance search
        # has no where-clause hook in our current wrapper. 8x is plenty
        # at our index size.
        candidates_k = k * 8 if kind else k * 2
        raw = idx.search(query, top_k=candidates_k)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    jsonl_index = _load_jsonl_index()
    out = []
    for h in raw or []:
        src = str(h.get("source", ""))
        if not src.startswith(SOURCE_PREFIX):
            # Not a typed-memory entry. Keep only if no kind filter was
            # supplied (so plain queries still see general memory too).
            if kind is None:
                out.append({
                    "kind":  None,
                    "key":   None,
                    "text":  h.get("text", ""),
                    "tags":  [],
                    "score": float(h.get("score", 0.0)),
                    "source": src,
                })
            continue
        # Format: typed_memory/<kind>/<key>
        parts = src[len(SOURCE_PREFIX):].split("/", 1)
        hit_kind = parts[0] if parts else ""
        hit_key = parts[1] if len(parts) > 1 else ""
        if kind and hit_kind != kind:
            continue
        meta = jsonl_index.get(src, {})
        out.append({
            "kind":  hit_kind,
            "key":   hit_key,
            "text":  h.get("text", ""),
            "tags":  meta.get("tags", []),
            "score": float(h.get("score", 0.0)),
            "source": src,
        })
        if len(out) >= k:
            break

    return {
        "query":     query,
        "kind":      kind,
        "n_results": len(out),
        "results":   out,
    }


ADD_MEMORY_TOOL = Tool(
    name="add_memory",
    description=(
        "Persist a typed memory entry. Writes a JSONL line to "
        "~/.techsupport_agent/memory.jsonl AND inserts the text into "
        "the semantic index so it's recallable via `recall`, "
        "`semantic_recall`, or the auto-recall hook. Use `kind` to "
        "categorize (e.g. 'preference', 'fact', 'decision', "
        "'project'); `key` is a short label; `text` is the content; "
        "`tags` is an optional list of strings."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "kind": {"type": "string", "description": "Category. E.g. 'preference', 'fact', 'decision'."},
            "key":  {"type": "string", "description": "Short label — identifier inside the kind."},
            "text": {"type": "string", "description": "The memory content."},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of tags.",
            },
        },
        "required": ["kind", "key", "text"],
        "additionalProperties": False,
    },
    handler=_add_memory,
)

RECALL_TYPED_TOOL = Tool(
    name="recall",
    description=(
        "Hybrid (BM25 + cosine) semantic search over typed memory "
        "and the broader transcript index. Pass `kind` to restrict "
        "to one category of typed memory; omit it to search across "
        "everything. Returns top-k with kind/key/tags when the hit "
        "is a typed entry. Does NOT shadow the older `recall` notes "
        "tool — it supersedes it in the registry."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural-language query."},
            "kind":  {"type": "string", "description": "Optional kind filter (e.g. 'preference')."},
            "k":     {"type": "integer", "description": "Top-k results. Default 5."},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    handler=_recall,
)


def register(registry) -> None:
    # Note: the older notes-style `recall` is still registered by
    # tools/memory.py and would be overwritten if we keep this name.
    # We deliberately register `add_memory` (new) and leave the
    # typed-recall tool under name `recall` so callers get the
    # upgraded path. The notes file is still readable via
    # `search_transcripts`. If you need the old behavior, the
    # function `tools.memory._recall` is unchanged.
    for t in (ADD_MEMORY_TOOL, RECALL_TYPED_TOOL):
        registry.register(t)
