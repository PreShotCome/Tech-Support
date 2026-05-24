"""Semantic search over past transcripts using local embeddings.

Backed by `fastembed` (BAAI/bge-small-en-v1.5 by default — small ONNX
model, runs on CPU, no PyTorch dependency, ~100MB).

Index is a single JSON file mapping chunk_id -> {source, text, vector,
importance, recall_count, created_at, last_recalled_at}. Build it
lazily: first query triggers indexing of anything new since the last
index update.

## Ranking

Default ranking is cosine similarity, multiplied by two weights:

  - **Importance** (-1..+1, default 0.0 = neutral). A pin/forget
    signal. Mapped to a 0.5..1.5 multiplier so unmarked chunks rank
    normally (1.0x), pinned chunks (+1.0) get +50%, and soft-forgotten
    chunks (-1.0) drop to 0.5x. Soft-forgotten chunks are still in the
    index — they're demoted, not deleted.
  - **Consolidation** (recall_count). Each time a chunk is returned in
    a search hit, recall_count increments. The multiplier is
    1 + min(0.6, recall_count * 0.06), so a chunk recalled 10+ times
    floats to the top of similar-similarity competitors. Cap is +60%.

There is **no time-based decay**. A conversation from a year ago and
one from this morning are weighted identically by default. Nothing
fades. The whole point of this system is perfect recollection — the
weights only let you say "this one matters more" or "this one keeps
coming up," not "this one is old, forget it."

Install: `pip install -e .[agent]`"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .transcript_logger import TranscriptLogger


INDEX_PATH = Path.home() / ".techsupport_agent" / "embeddings_index.json"
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

RECALL_BOOST_PER_HIT = 0.06
MAX_RECALL_BOOST = 0.60

# Knowledge directories indexed alongside transcripts. Path is resolved
# relative to the Tech-Support repo root (the parent of `python/`).
# Each .md file in these dirs becomes searchable via semantic_recall.
KNOWLEDGE_DIRS = ("docs/research", "docs/skills")


def _chunk_text(text: str, max_chars: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks at paragraph boundaries.
    Embeddings work best on coherent chunks; overlap reduces the chance
    of cutting a thought in half."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paras:
        if len(current) + len(p) + 2 <= max_chars:
            current = (current + "\n\n" + p).strip()
        else:
            if current:
                chunks.append(current)
            if len(p) > max_chars:
                for i in range(0, len(p), max_chars - overlap):
                    chunks.append(p[i: i + max_chars])
                current = ""
            else:
                current = p
    if current:
        chunks.append(current)
    return chunks


def _chunk_id(source: str, index: int, text: str) -> str:
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{source}::{index}::{h}"


def _repo_root() -> Path:
    """Tech-Support repo root, walking up from this module."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "IDENTITY.md").exists() and (parent / "python").exists():
            return parent
    # Fallback: assume two levels up (python/agent/embeddings.py -> repo)
    return here.parent.parent.parent


def _knowledge_files() -> list[Path]:
    """All .md files under KNOWLEDGE_DIRS, sorted for stable ordering."""
    root = _repo_root()
    out: list[Path] = []
    for rel in KNOWLEDGE_DIRS:
        d = root / rel
        if d.exists():
            out.extend(sorted(d.rglob("*.md")))
    return out


@dataclass
class EmbeddedChunk:
    chunk_id: str
    source: str            # transcript filename
    text: str
    vector: list[float]
    # Weighting fields. All default to neutral so existing chunks loaded
    # from a pre-weighting index behave like raw cosine ranking.
    importance: float = 0.0           # -1..+1, pin/forget signal; 0 = neutral
    recall_count: int = 0             # consolidation counter
    created_at: float = 0.0           # unix ts; 0 means "unknown / pre-weighting"
    last_recalled_at: float = 0.0     # unix ts; 0 means "never"


class TranscriptIndex:
    def __init__(self, index_path: Path = INDEX_PATH, model: str = DEFAULT_MODEL):
        self.index_path = index_path
        self.model_name = model
        self._embedder = None
        self._cache: dict[str, EmbeddedChunk] = {}
        self._indexed_sources: set[str] = set()
        self._load()

    # ------------------------------------------------------------------ persist

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return
        for chunk_id, payload in data.get("chunks", {}).items():
            self._cache[chunk_id] = EmbeddedChunk(
                chunk_id=chunk_id,
                source=payload["source"],
                text=payload["text"],
                vector=payload["vector"],
                importance=float(payload.get("importance", 0.0)),
                recall_count=int(payload.get("recall_count", 0)),
                created_at=float(payload.get("created_at", 0.0)),
                last_recalled_at=float(payload.get("last_recalled_at", 0.0)),
            )
            self._indexed_sources.add(payload["source"])

    def _save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model_name,
            "chunks": {
                cid: {
                    "source": c.source,
                    "text": c.text,
                    "vector": c.vector,
                    "importance": c.importance,
                    "recall_count": c.recall_count,
                    "created_at": c.created_at,
                    "last_recalled_at": c.last_recalled_at,
                }
                for cid, c in self._cache.items()
            },
        }
        tmp = self.index_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self.index_path)

    # ------------------------------------------------------------------ embed

    def _ensure_embedder(self):
        if self._embedder is None:
            from fastembed import TextEmbedding
            self._embedder = TextEmbedding(model_name=self.model_name)
        return self._embedder

    def _embed(self, texts: list[str]) -> list[list[float]]:
        emb = self._ensure_embedder()
        return [list(v) for v in emb.embed(texts)]

    # ------------------------------------------------------------------ build

    def reindex(self, transcripts_dir: Optional[Path] = None, force: bool = False) -> dict:
        """Index any transcripts not yet indexed (or all if force=True).
        Also indexes .md files under KNOWLEDGE_DIRS so curated docs
        (skills, research notes) live in the same semantic index as
        chat transcripts."""
        if force:
            self._cache.clear()
            self._indexed_sources.clear()

        # Build the unified list of source files to consider.
        candidates: list[tuple[Path, str]] = []  # (path, source_key)
        for p in TranscriptLogger.list_transcripts(transcripts_dir):
            candidates.append((p, p.name))
        for p in _knowledge_files():
            # Source key includes the relative path so files in different
            # subdirs (osiris/README.md vs trading/README.md) don't collide.
            try:
                rel = p.relative_to(_repo_root()).as_posix()
            except ValueError:
                rel = p.name
            candidates.append((p, f"knowledge/{rel}"))

        added = 0
        now = time.time()
        for path, source_key in candidates:
            if not force and source_key in self._indexed_sources:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            chunks = _chunk_text(text)
            if not chunks:
                continue
            vectors = self._embed(chunks)
            for i, (chunk_text, vec) in enumerate(zip(chunks, vectors)):
                cid = _chunk_id(source_key, i, chunk_text)
                self._cache[cid] = EmbeddedChunk(
                    chunk_id=cid,
                    source=source_key,
                    text=chunk_text,
                    vector=vec,
                    created_at=now,
                )
                added += 1
            self._indexed_sources.add(source_key)

        if added > 0:
            self._save()
        return {
            "indexed_sources": len(self._indexed_sources),
            "total_chunks": len(self._cache),
            "added_this_run": added,
        }

    # ------------------------------------------------------------------ query

    @staticmethod
    def _importance_mult(importance: float) -> float:
        imp = max(-1.0, min(1.0, importance))
        return 1.0 + (imp * 0.5)

    @staticmethod
    def _consolidation_mult(recall_count: int) -> float:
        if recall_count <= 0:
            return 1.0
        return 1.0 + min(MAX_RECALL_BOOST, recall_count * RECALL_BOOST_PER_HIT)

    def search(self, query: str, top_k: int = 5, *, update_recall: bool = True) -> list[dict]:
        if not query.strip():
            return []
        self.reindex()
        if not self._cache:
            return []
        qvec = self._embed([query])[0]

        scored: list[tuple[float, float, EmbeddedChunk]] = []
        for c in self._cache.values():
            sim = self._cosine(qvec, c.vector)
            if sim <= 0:
                continue
            imp_mult = self._importance_mult(c.importance)
            cons_mult = self._consolidation_mult(c.recall_count)
            eff = sim * imp_mult * cons_mult
            scored.append((eff, sim, c))

        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:top_k]

        if update_recall and top:
            now = time.time()
            for _eff, _sim, c in top:
                c.recall_count += 1
                c.last_recalled_at = now
            self._save()

        results = []
        for eff, sim, c in top:
            results.append({
                "score": float(eff),
                "similarity": float(sim),
                "importance": c.importance,
                "recall_count": c.recall_count,
                "source": c.source,
                "chunk_id": c.chunk_id,
                "text": c.text,
            })
        return results

    # ------------------------------------------------------------------ pin/forget

    def set_importance(self, query: str, importance: float, top_k: int = 3) -> list[dict]:
        """Find chunks matching `query` and set their importance.
        Returns the list of chunks that were modified.

        importance > 0  → pin (boost). +1.0 is the max boost (+50%).
        importance < 0  → soft-forget. -1.0 demotes by 50% (0.5x).
        importance = 0  → neutral.
        """
        hits = self.search(query, top_k=top_k, update_recall=False)
        if not hits:
            return []
        modified = []
        imp = max(-1.0, min(1.0, float(importance)))
        for h in hits:
            chunk = self._cache.get(h["chunk_id"])
            if chunk is None:
                continue
            chunk.importance = imp
            modified.append({
                "source": chunk.source,
                "chunk_id": chunk.chunk_id,
                "text": chunk.text[:200] + ("..." if len(chunk.text) > 200 else ""),
                "importance": chunk.importance,
            })
        if modified:
            self._save()
        return modified

    def status(self) -> dict:
        """Summary of the index: counts, pinned, most-recalled."""
        chunks = list(self._cache.values())
        pinned = [c for c in chunks if c.importance > 0]
        forgotten = [c for c in chunks if c.importance < 0]
        most_recalled = sorted(chunks, key=lambda c: c.recall_count, reverse=True)[:5]
        return {
            "total_chunks": len(chunks),
            "indexed_sources": len(self._indexed_sources),
            "pinned_count": len(pinned),
            "soft_forgotten_count": len(forgotten),
            "top_recalled": [
                {
                    "source": c.source,
                    "recall_count": c.recall_count,
                    "importance": c.importance,
                    "preview": c.text[:120] + ("..." if len(c.text) > 120 else ""),
                }
                for c in most_recalled if c.recall_count > 0
            ],
        }

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        import math
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
