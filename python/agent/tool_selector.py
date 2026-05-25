"""Tool selection by intent.

Theo currently has ~47 tools across 12 categories. Stuffing every
schema into the prompt costs ~5-10KB per turn — fine now, painful
at 100+ tools. This module narrows the set per turn by classifying
the user's query against per-category description embeddings.

Architecture:
  - CORE_TOOLS are always loaded (identity, basic memory, web, intro-
    spection). These are cheap, broadly useful, and Theo reaches for
    them constantly.
  - OPTIONAL_CATEGORIES are loaded only when the query's cosine
    similarity to a category description crosses a threshold.

Selection uses fastembed (the same model the memory index uses) — no
extra LLM round trip per turn. The category embeddings are computed
once on first call and cached.

If the embedder isn't available (e.g. fastembed not installed), we
fall back to loading every tool — the system still works, just
without the narrowing benefit."""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Iterable


# ----------------------------------------------------------- categories

# Always-loaded tools. Identity, durable notes, transcripts, semantic
# memory ops, web, and all the introspection tools (self-model, narrative,
# threads, summaries, drift). These are the spine of every conversation.
CORE_TOOLS: set[str] = {
    # system
    "now", "system_info",
    # identity
    "set_name", "get_name",
    # memory (always — Theo searches memory on most turns)
    "note", "recall", "search_transcripts", "list_transcripts",
    "semantic_recall", "pin_memory", "forget_memory", "memory_status",
    # web (broad utility)
    "web_search", "web_fetch",
    # introspection — the personality matrix surfaces
    "note_about_self", "read_self_model",
    "note_about_human", "read_human_model",
    "add_chapter", "read_narrative",
    "open_thread", "close_thread", "list_threads",
    "summarize_session", "read_summaries",
    "check_drift",
    # skills registry — discovering and loading SKILL.md instructions
    "list_skills", "read_skill",
}


# Optional categories: tools loaded only when relevant.
# Each entry: (set of tool names, natural-language description used
# for similarity matching against the user's query).
OPTIONAL_CATEGORIES: dict[str, tuple[set[str], str]] = {
    "trading": (
        {"portfolio", "orders", "market_clock", "rebalance_plan", "shadow_report"},
        "stock trading, portfolio positions, equity orders, Alpaca paper "
        "account, market hours, rebalance, basket, shares, buy sell",
    ),
    "trading_safety": (
        {"session_preflight", "validate_trade", "reconcile_positions",
         "track_order", "log_decision"},
        "trade validation, pre-trade checks, reconcile broker positions, "
        "order lifecycle, decision logging for trading audit trail",
    ),
    "osint": (
        {"osint_query"},
        "open source intelligence, real-time global events, earthquakes, "
        "active fires, flights in the air, news streams, conflict zones, "
        "frontlines, satellites, ports, ships, weather alerts, cyber "
        "threats CVEs, country risk",
    ),
    "finance": (
        {"openbb_query"},
        "financial data, stock quotes, OpenBB, historical OHLCV prices, "
        "company fundamentals, equities, crypto market data, ticker "
        "symbols, share price lookup",
    ),
    "server_metrics": (
        {"server_metrics"},
        "Netdata, server monitoring, CPU usage, RAM, memory, disk space, "
        "disk I/O, network traffic, processes, system load, machine health, "
        "is anything running hot, system alarms",
    ),
    "security_scan": (
        {"trivy_scan", "crowdsec_check"},
        "vulnerability scan, Trivy, CVE, container image security, file "
        "system audit, CrowdSec IP reputation, threat intelligence, is "
        "this IP malicious, known bad IP, security assessment",
    ),
    "browser_drive": (
        {"browser_task"},
        "browse a website, scrape a page, fill out a form, navigate a "
        "JavaScript-heavy site, click links, drive a real browser via "
        "browser-use, automated web flow",
    ),
    "diagrams": (
        {"render_diagram"},
        "render an architecture diagram, sketch system relationships, "
        "draw a flow chart, visualize data flow, generate a picture "
        "from text via d2 diagram language",
    ),
    "file_sync": (
        {"rclone_op"},
        "back up files to cloud storage, sync directories to S3, "
        "Dropbox, OneDrive, Google Drive, B2, list cloud bucket "
        "contents, mirror folders between machines via rclone",
    ),
    "chess": (
        {"chess_analyze"},
        "chess position analysis, best move, evaluate this FEN, "
        "Stockfish engine, principal variation, mate in N, who is "
        "winning, opening preparation, endgame study",
    ),
    "file_transfer": (
        {"croc_send"},
        "send a file to someone, peer-to-peer file transfer, share "
        "this file with another machine, croc transfer code, move "
        "data between computers without uploading to cloud first",
    ),
}


# Tunable thresholds. Top-K means "include up to this many highest-
# scoring categories"; min_sim means "but only if their similarity
# passes this floor." Tuned on the bge-small-en-v1.5 embedder; the
# right category lands every time at these settings, and most noise
# from unrelated categories gets dropped. When the embedder is
# upgraded to bge-large (#5), thresholds may want to be re-tuned —
# similarity distributions shift.
TOP_K_CATEGORIES = 2
MIN_SIMILARITY = 0.55


# ----------------------------------------------------------- embedding

_category_vectors: dict[str, list[float]] | None = None


def _get_embedder():
    """Lazy import — fastembed may not be installed if [agent] extra
    wasn't picked up. Returns None on failure; caller falls back to
    "load everything"."""
    try:
        from .embeddings import DEFAULT_MODEL
        from fastembed import TextEmbedding
        return TextEmbedding(model_name=DEFAULT_MODEL)
    except Exception:
        return None


def _ensure_category_vectors(embedder) -> dict[str, list[float]]:
    global _category_vectors
    if _category_vectors is not None:
        return _category_vectors
    out: dict[str, list[float]] = {}
    descs = [d for _, (_, d) in OPTIONAL_CATEGORIES.items()]
    names = list(OPTIONAL_CATEGORIES.keys())
    vecs = list(embedder.embed(descs))
    for name, vec in zip(names, vecs):
        out[name] = list(vec)
    _category_vectors = out
    return out


# ------------------------------------------------ explicit-name shortcuts
#
# When the query literally names a tool or a known brand from a category,
# force-include that category regardless of cosine similarity. The
# embedding selector is best-effort; explicit naming is the strongest
# signal possible. Theo flagged a bug where a query like "use openbb_query"
# wasn't loading the openbb category because the cosine wasn't high enough.

_BRAND_KEYWORDS: dict[str, set[str]] = {
    "trading":         {"alpaca", "portfolio", "rebalance"},
    "osint":           {"osint", "osiris", "earthquake", "wildfire", "flight tracker"},
    "finance":         {"openbb", "yfinance", "stock quote", "ticker", "ohlcv"},
    "server_metrics":  {"netdata", "server metric"},
    "security_scan":   {"trivy", "crowdsec", "cve scan", "vulnerability scan"},
    "browser_drive":   {"browser-use", "browser_task"},
    "diagrams":        {"d2", "render_diagram", "render a diagram"},
    "file_sync":       {"rclone"},
    "chess":           {"stockfish", "chess", "fen", "uci"},
    "file_transfer":   {"croc"},
}


def _all_tool_names() -> dict[str, str]:
    """Map every known tool name to its category id."""
    out: dict[str, str] = {}
    for cat, (tools, _) in OPTIONAL_CATEGORIES.items():
        for t in tools:
            out[t] = cat
    return out


def _explicit_matches(query: str) -> set[str]:
    """Categories the query explicitly invokes by tool name or brand."""
    q = query.lower()
    cats: set[str] = set()
    # 1. Direct tool-name mentions: 'openbb_query', 'osint_query', 'chess_analyze'
    for tname, cat in _all_tool_names().items():
        if tname.lower() in q:
            cats.add(cat)
    # 2. Brand / domain keywords
    for cat, kws in _BRAND_KEYWORDS.items():
        for kw in kws:
            if kw in q:
                cats.add(cat)
                break
    return cats


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ----------------------------------------------------------- selection

def select_tool_names(query: str,
                       top_k: int = TOP_K_CATEGORIES,
                       min_sim: float = MIN_SIMILARITY) -> set[str]:
    """Return the set of tool names to expose for this query.

    Always includes CORE_TOOLS. Force-includes any optional category
    the query names explicitly (by tool name or brand keyword). Then
    adds the top-K categories whose embedding similarity to the query
    crosses min_sim."""
    selected = set(CORE_TOOLS)
    q = (query or "").strip()
    if not q:
        return selected

    # Explicit naming wins over semantic similarity — if Theo or Ian
    # writes "use openbb_query" we MUST load openbb, regardless of how
    # the rest of the message scores.
    for cat in _explicit_matches(q):
        tools, _ = OPTIONAL_CATEGORIES[cat]
        selected.update(tools)

    embedder = _get_embedder()
    if embedder is None:
        # No embedder available — load all tools so we don't gate
        # capabilities the system would need.
        for tools, _ in OPTIONAL_CATEGORIES.values():
            selected.update(tools)
        return selected

    try:
        cat_vecs = _ensure_category_vectors(embedder)
        qvec = list(next(iter(embedder.embed([q]))))
    except Exception:
        # Any embedding failure: fail open (load everything).
        for tools, _ in OPTIONAL_CATEGORIES.values():
            selected.update(tools)
        return selected

    scored = [(cat, _cosine(qvec, vec)) for cat, vec in cat_vecs.items()]
    scored.sort(key=lambda t: t[1], reverse=True)
    for cat, sim in scored[:top_k]:
        if sim >= min_sim:
            tools, _ = OPTIONAL_CATEGORIES[cat]
            selected.update(tools)

    return selected


def filter_schemas(schemas: list[dict], names: set[str]) -> list[dict]:
    """Filter a list of OpenAI-format tool schemas down to `names`."""
    out = []
    for s in schemas:
        n = s.get("function", {}).get("name")
        if n in names:
            out.append(s)
    return out


def select_schemas(query: str, all_schemas: list[dict]) -> tuple[list[dict], set[str]]:
    """Convenience: pick names for query, then filter schemas to match.
    Returns (filtered_schemas, selected_names)."""
    names = select_tool_names(query)
    return filter_schemas(all_schemas, names), names
