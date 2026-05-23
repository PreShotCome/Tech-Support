"""Semantic search over past transcripts using local embeddings.

Backed by `fastembed` (BAAI/bge-small-en-v1.5 by default — small ONNX
model, runs on CPU, no PyTorch dependency, ~100MB).

Index is a single JSON file mapping chunk_id -> {source, text, vector}.
Build it lazily: first query triggers indexing of anything new since
the last index update. After that, queries are O(N) cosine similarity
over the cached vectors (still fast for tens of thousands of chunks).

Install: `pip install -e .[agent]`"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .transcript_logger import TranscriptLogger


INDEX_PATH = Path.home() / ".techsupport_agent" / "embeddings_index.json"
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


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
                # Hard split on overlong paragraph
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


@dataclass
class EmbeddedChunk:
    chunk_id: str
    source: str            # transcript filename
    text: str
    vector: list[float]


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
            )
            self._indexed_sources.add(payload["source"])

    def _save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model_name,
            "chunks": {
                cid: {"source": c.source, "text": c.text, "vector": c.vector}
                for cid, c in self._cache.items()
            },
        }
        # Write atomically: tmp file then replace
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
        """Index any transcripts not yet indexed (or all if force=True)."""
        paths = TranscriptLogger.list_transcripts(transcripts_dir)
        new_sources = [p for p in paths if force or p.name not in self._indexed_sources]
        if force:
            self._cache.clear()
            self._indexed_sources.clear()

        added = 0
        for p in new_sources:
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue
            chunks = _chunk_text(text)
            if not chunks:
                continue
            vectors = self._embed(chunks)
            for i, (chunk_text, vec) in enumerate(zip(chunks, vectors)):
                cid = _chunk_id(p.name, i, chunk_text)
                self._cache[cid] = EmbeddedChunk(
                    chunk_id=cid, source=p.name, text=chunk_text, vector=vec,
                )
                added += 1
            self._indexed_sources.add(p.name)

        if added > 0:
            self._save()
        return {
            "indexed_sources": len(self._indexed_sources),
            "total_chunks": len(self._cache),
            "added_this_run": added,
        }

    # ------------------------------------------------------------------ query

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not query.strip():
            return []
        # Make sure new transcripts are reflected
        self.reindex()
        if not self._cache:
            return []
        qvec = self._embed([query])[0]
        scored = [
            (self._cosine(qvec, c.vector), c)
            for c in self._cache.values()
        ]
        scored.sort(key=lambda t: t[0], reverse=True)
        results = []
        for score, c in scored[:top_k]:
            results.append({
                "score": float(score),
                "source": c.source,
                "chunk_id": c.chunk_id,
                "text": c.text,
            })
        return results

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
