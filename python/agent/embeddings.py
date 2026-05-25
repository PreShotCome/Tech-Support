"""Semantic search over Theo's memory, backed by LanceDB.

This is the upgraded backend — was a single JSON file + linear cosine
over a dict-cached in memory, now a persistent Lance columnar table
with proper vector search. Same public API:

    idx = TranscriptIndex()
    idx.reindex()
    idx.search(query, top_k=5)
    idx.set_importance(query, importance=1.0)
    idx.status()

What changed:
  - Storage is `~/.techsupport_agent/embeddings.lance/` (a directory)
    instead of a single JSON file.
  - Search runs over LanceDB's vector index (brute-force at our size,
    auto-ANN once chunks > ~100K).
  - Auto-migration: on first run after the swap, if the legacy
    embeddings_index.json exists and the LanceDB table is empty, the
    old chunks are imported once and forgotten. Old JSON is left in
    place as a backup.

Weighted ranking (importance + consolidation, no time decay) is still
the same logic — applied post-search on top-K candidates.

Install: `pip install -e .[agent]` (now also pulls lancedb + pyarrow).
Reference: docs/research/_REPOS.md cross-references the source library."""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .transcript_logger import TranscriptLogger


STATE_DIR = Path.home() / ".techsupport_agent"
LANCE_PATH = STATE_DIR / "embeddings.lance"
LEGACY_JSON_PATH = STATE_DIR / "embeddings_index.json"

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384   # bge-small-en-v1.5

RECALL_BOOST_PER_HIT = 0.06
MAX_RECALL_BOOST = 0.60

# Reciprocal Rank Fusion constant. Higher = flatter weight distribution
# across ranks; 60 is the value the RRF paper uses and most libraries
# default to. Lower would amplify top-ranked items more aggressively.
RRF_K = 60

KNOWLEDGE_DIRS = ("docs/research", "docs/skills")


# ----------------------------------------------------------- chunking helpers

def _chunk_text(text: str, max_chars: int = 800, overlap: int = 100) -> list[str]:
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
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "IDENTITY.md").exists() and (parent / "python").exists():
            return parent
    return here.parent.parent.parent


def _knowledge_files() -> list[Path]:
    root = _repo_root()
    out: list[Path] = []
    for rel in KNOWLEDGE_DIRS:
        d = root / rel
        if d.exists():
            out.extend(sorted(d.rglob("*.md")))
    return out


@dataclass
class EmbeddedChunk:
    """Dataclass used at the API boundary; the storage is LanceDB."""
    chunk_id: str
    source: str
    text: str
    vector: list[float]
    importance: float = 0.0
    recall_count: int = 0
    created_at: float = 0.0
    last_recalled_at: float = 0.0


# ---------------------------------------------------------------- TranscriptIndex

class TranscriptIndex:
    """LanceDB-backed semantic memory."""

    TABLE_NAME = "chunks"

    def __init__(self, index_path: Path = LANCE_PATH, model: str = DEFAULT_MODEL):
        self.index_path = Path(index_path)
        self.model_name = model
        self._embedder = None
        self._db = None
        self._table = None
        self._open_or_create()
        self._maybe_migrate_from_json()

    # ------------------------------------------------------------- LanceDB I/O

    def _open_or_create(self) -> None:
        import lancedb
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self.index_path))
        if self.TABLE_NAME in self._db.table_names():
            self._table = self._db.open_table(self.TABLE_NAME)
        else:
            self._table = self._db.create_table(
                self.TABLE_NAME,
                schema=self._schema(),
                mode="create",
            )

    @staticmethod
    def _schema():
        import pyarrow as pa
        return pa.schema([
            pa.field("chunk_id",         pa.string()),
            pa.field("source",           pa.string()),
            pa.field("text",             pa.string()),
            pa.field("vector",           pa.list_(pa.float32(), EMBEDDING_DIM)),
            pa.field("importance",       pa.float32()),
            pa.field("recall_count",     pa.int64()),
            pa.field("created_at",       pa.float64()),
            pa.field("last_recalled_at", pa.float64()),
        ])

    def _indexed_sources(self) -> set[str]:
        try:
            rows = (self._table
                    .search()
                    .select(["source"])
                    .limit(10_000_000)
                    .to_list())
        except Exception:
            return set()
        return {r["source"] for r in rows}

    def _chunk_id_exists(self, chunk_id: str) -> bool:
        cnt = self._table.count_rows(f"chunk_id = '{chunk_id}'")
        return cnt > 0

    # ----------------------------------------------------------- FTS index

    _fts_ready: bool = False

    def _ensure_fts_index(self) -> bool:
        """Create the full-text index on `text` if missing. Idempotent.
        Returns True if FTS is usable, False if the table is empty or
        the create failed."""
        if self._fts_ready:
            return True
        if self._table.count_rows() == 0:
            return False
        try:
            # create_fts_index is safe to call repeatedly; replace=True
            # in case the schema's drifted under us.
            self._table.create_fts_index("text", replace=False)
            self._fts_ready = True
            return True
        except Exception:
            # Some lancedb versions raise if the index already exists;
            # treat that as success.
            try:
                # Probe with a tiny query — if it works, the index is fine
                self._table.search("test", query_type="fts").limit(1).to_list()
                self._fts_ready = True
                return True
            except Exception:
                return False

    # ----------------------------------------------------------- migration

    def _maybe_migrate_from_json(self) -> None:
        """If LanceDB is empty and the legacy JSON exists, import the old
        chunks once. Idempotent — checks both file presence and row count."""
        if self._table.count_rows() > 0:
            return
        if not LEGACY_JSON_PATH.exists():
            return
        try:
            data = json.loads(LEGACY_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        chunks = data.get("chunks", {})
        if not chunks:
            return
        rows = []
        for chunk_id, payload in chunks.items():
            vec = payload.get("vector") or []
            if len(vec) != EMBEDDING_DIM:
                continue
            rows.append({
                "chunk_id":         chunk_id,
                "source":           payload.get("source", ""),
                "text":             payload.get("text", ""),
                "vector":           [float(x) for x in vec],
                "importance":       float(payload.get("importance", 0.0)),
                "recall_count":     int(payload.get("recall_count", 0)),
                "created_at":       float(payload.get("created_at", 0.0)),
                "last_recalled_at": float(payload.get("last_recalled_at", 0.0)),
            })
        if rows:
            self._table.add(rows)

    # --------------------------------------------------------- embedder lazy

    def _ensure_embedder(self):
        if self._embedder is None:
            from fastembed import TextEmbedding
            self._embedder = TextEmbedding(model_name=self.model_name)
        return self._embedder

    def _embed(self, texts: list[str]) -> list[list[float]]:
        emb = self._ensure_embedder()
        return [list(v) for v in emb.embed(texts)]

    # --------------------------------------------------------------- reindex

    def reindex(self, transcripts_dir: Optional[Path] = None, force: bool = False) -> dict:
        if force:
            # Drop and recreate the table; FTS index is gone too
            self._db.drop_table(self.TABLE_NAME)
            self._open_or_create()
            self._fts_ready = False

        already = self._indexed_sources()

        candidates: list[tuple[Path, str]] = []
        for p in TranscriptLogger.list_transcripts(transcripts_dir):
            candidates.append((p, p.name))
        for p in _knowledge_files():
            try:
                rel = p.relative_to(_repo_root()).as_posix()
            except ValueError:
                rel = p.name
            candidates.append((p, f"knowledge/{rel}"))

        new = [(p, s) for p, s in candidates if s not in already]
        added = 0
        now = time.time()

        # Process in batches so embed + insert isn't one huge call
        BATCH = 32
        batch_rows: list[dict] = []

        for path, source_key in new:
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
                batch_rows.append({
                    "chunk_id":         cid,
                    "source":           source_key,
                    "text":             chunk_text,
                    "vector":           [float(x) for x in vec],
                    "importance":       0.0,
                    "recall_count":     0,
                    "created_at":       now,
                    "last_recalled_at": 0.0,
                })
                added += 1
                if len(batch_rows) >= BATCH:
                    self._table.add(batch_rows)
                    batch_rows = []

        if batch_rows:
            self._table.add(batch_rows)

        return {
            "indexed_sources": len(self._indexed_sources()),
            "total_chunks":    self._table.count_rows(),
            "added_this_run":  added,
        }

    # ----------------------------------------------------------- search

    @staticmethod
    def _importance_mult(importance: float) -> float:
        imp = max(-1.0, min(1.0, float(importance)))
        return 1.0 + (imp * 0.5)

    @staticmethod
    def _consolidation_mult(recall_count: int) -> float:
        if recall_count <= 0:
            return 1.0
        return 1.0 + min(MAX_RECALL_BOOST, recall_count * RECALL_BOOST_PER_HIT)

    def search(self, query: str, top_k: int = 5, *,
               update_recall: bool = True, hybrid: bool = True) -> list[dict]:
        """Search the index. Hybrid by default — combines cosine
        vector search with BM25 full-text search via Reciprocal Rank
        Fusion. Set hybrid=False for pure vector (skipping FTS)."""
        if not query.strip():
            return []
        # Lazy reindex on every search so new files become searchable
        self.reindex()

        if self._table.count_rows() == 0:
            return []

        candidate_k = max(top_k * 4, 12)

        # --- vector arm: cosine over embeddings ---
        qvec = self._embed([query])[0]
        try:
            vec_results = (
                self._table
                .search([float(x) for x in qvec])
                .metric("cosine")
                .limit(candidate_k)
                .to_list()
            )
        except Exception:
            vec_results = []

        # --- fts arm: BM25 over the text field ---
        fts_results: list[dict] = []
        if hybrid and self._ensure_fts_index():
            try:
                fts_results = (
                    self._table
                    .search(query, query_type="fts")
                    .limit(candidate_k)
                    .to_list()
                )
            except Exception:
                fts_results = []  # FTS query parse error etc

        # --- combine via Reciprocal Rank Fusion ---
        # RRF score per doc = sum over rankings of 1 / (RRF_K + rank).
        # Then we keep raw cosine similarity for inspection and apply
        # importance + consolidation multipliers on top.
        merged: dict[str, dict] = {}
        for rank, r in enumerate(vec_results, start=1):
            cid = r["chunk_id"]
            entry = merged.setdefault(cid, {"row": r, "rrf": 0.0,
                                            "sim": 1.0 - float(r.get("_distance", 1.0)),
                                            "in_vec": False, "in_fts": False})
            entry["rrf"] += 1.0 / (RRF_K + rank)
            entry["in_vec"] = True

        for rank, r in enumerate(fts_results, start=1):
            cid = r["chunk_id"]
            entry = merged.setdefault(cid, {"row": r, "rrf": 0.0,
                                            "sim": 0.0,
                                            "in_vec": False, "in_fts": False})
            entry["rrf"] += 1.0 / (RRF_K + rank)
            entry["in_fts"] = True

        if not merged:
            return []

        # Final score = rrf * importance_mult * consolidation_mult.
        # Importance/consolidation are tiny multipliers (0.5..1.5x and
        # up to 1.6x); they nudge ranking among similarly-scored chunks
        # without overwhelming RRF's signal.
        scored: list[tuple[float, dict]] = []
        for cid, entry in merged.items():
            r = entry["row"]
            imp_mult = self._importance_mult(r.get("importance", 0.0))
            cons_mult = self._consolidation_mult(int(r.get("recall_count", 0)))
            score = entry["rrf"] * imp_mult * cons_mult
            entry["final"] = score
            scored.append((score, entry))

        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:top_k]

        if update_recall and top:
            now = time.time()
            for _score, entry in top:
                r = entry["row"]
                cid = r["chunk_id"].replace("'", "''")
                try:
                    self._table.update(
                        where=f"chunk_id = '{cid}'",
                        values={
                            "recall_count": int(r.get("recall_count", 0)) + 1,
                            "last_recalled_at": now,
                        },
                    )
                except Exception:
                    pass

        out = []
        for score, entry in top:
            r = entry["row"]
            out.append({
                "score":         float(score),
                "similarity":    float(entry["sim"]),  # raw cosine, for auto-recall gating
                "rrf_score":     float(entry["rrf"]),
                "matched_via":   ("vec+fts" if (entry["in_vec"] and entry["in_fts"])
                                  else ("vec" if entry["in_vec"] else "fts")),
                "importance":    float(r.get("importance", 0.0)),
                "recall_count":  int(r.get("recall_count", 0)),
                "source":        r["source"],
                "chunk_id":      r["chunk_id"],
                "text":          r["text"],
            })
        return out

    # ------------------------------------------------------- pin / forget

    def set_importance(self, query: str, importance: float, top_k: int = 3) -> list[dict]:
        hits = self.search(query, top_k=top_k, update_recall=False)
        if not hits:
            return []
        imp = max(-1.0, min(1.0, float(importance)))
        modified = []
        for h in hits:
            cid = h["chunk_id"].replace("'", "''")
            try:
                self._table.update(
                    where=f"chunk_id = '{cid}'",
                    values={"importance": imp},
                )
            except Exception:
                continue
            modified.append({
                "source": h["source"],
                "chunk_id": h["chunk_id"],
                "text": (h["text"][:200] + ("..." if len(h["text"]) > 200 else "")),
                "importance": imp,
            })
        return modified

    # ---------------------------------------------------------- status

    def status(self) -> dict:
        total = self._table.count_rows()
        pinned = self._table.count_rows("importance > 0")
        forgotten = self._table.count_rows("importance < 0")
        try:
            top_rows = (self._table
                        .search()
                        .where("recall_count > 0")
                        .limit(50)
                        .to_list())
            top_rows.sort(key=lambda r: r.get("recall_count", 0), reverse=True)
            top_rows = top_rows[:5]
        except Exception:
            top_rows = []

        return {
            "total_chunks": int(total),
            "indexed_sources": len(self._indexed_sources()),
            "pinned_count": int(pinned),
            "soft_forgotten_count": int(forgotten),
            "top_recalled": [
                {
                    "source": r["source"],
                    "recall_count": int(r.get("recall_count", 0)),
                    "importance": float(r.get("importance", 0.0)),
                    "preview": r["text"][:120] + ("..." if len(r["text"]) > 120 else ""),
                }
                for r in top_rows
            ],
        }
