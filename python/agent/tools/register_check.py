"""Register check — read recent user turns and surface tone signals.

This is the "you seem tired tonight" sense that a long-term human
partner has. Theo doesn't have biometrics or a health-app integration;
he has the conversation itself. Patterns in *how* Ian writes carry
real information about state — typo density, response cadence,
message length variance, time-of-day clustering, fatigue markers.

Pure analysis over the last N user turns from the transcripts. No
ML, no inference call — just heuristics on text and timestamps. The
output is a structured report the agent can read at session start
and use to calibrate register.

Use it for:
  - "Is Ian tired right now?" — heuristic, but useful at session
    start so Theo opens at the right energy.
  - Long-term trend ("his messages got shorter and more typo-heavy
    last week") — visible by comparing recent vs baseline.

Surfaced in the briefing if any signal exceeds threshold. Theo can
also call it explicitly via the register_check tool."""
from __future__ import annotations

import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base import Tool
from ..transcript_logger import TranscriptLogger


# Fatigue / stress markers we look for in recent user turns. Lower
# bar than a sentiment classifier — we just want signal.
_TIRED_MARKERS = re.compile(
    r"\b(tired|exhausted|sleepy|fried|burnt out|burnout|drained|wiped|"
    r"can'?t think straight|brain ?fog|46 hours|36 hours|all night|"
    r"haven'?t slept|no sleep)\b",
    re.IGNORECASE,
)
_STRESS_MARKERS = re.compile(
    r"\b(stressed|overwhelmed|anxious|frustrated|annoyed|pissed|fuck|"
    r"shit|damn it|ugh|wtf)\b",
    re.IGNORECASE,
)
_WIN_MARKERS = re.compile(
    r"\b(worked|works|nice|beautiful|woohoo|hell yeah|fuck yeah|"
    r"finally|love it|locked in|amazing)\b",
    re.IGNORECASE,
)

# Single-line user-turn header in the transcript markdown:
#   ## you · 2026-05-25T03:14:00+00:00
_USER_HEADER_RE = re.compile(
    r"^##\s+you\s+·\s+(?P<ts>\S+)\s*$", re.MULTILINE,
)


def _parse_user_turns(transcript_paths: list[Path]) -> list[dict]:
    """Pull (timestamp, text) pairs for user turns across the given
    transcript files, newest first."""
    out: list[dict] = []
    for p in transcript_paths:
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception:
            continue
        lines = raw.splitlines()
        i = 0
        while i < len(lines):
            m = _USER_HEADER_RE.match(lines[i])
            if not m:
                i += 1
                continue
            try:
                ts = datetime.fromisoformat(m.group("ts"))
            except Exception:
                ts = None
            # Collect body until next "## " header
            body_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                body_lines.append(lines[i])
                i += 1
            text = "\n".join(body_lines).strip()
            if text:
                out.append({"ts": ts, "text": text, "file": p.name})
    # Newest first
    out.sort(key=lambda r: r["ts"] or datetime.min.replace(tzinfo=timezone.utc),
             reverse=True)
    return out


def _count_typos(text: str) -> int:
    """Rough typo proxy — words with no spaces but obvious skipped
    characters or doubled punctuation. Not a spellcheck; just a
    cheap signal that bounces around with fatigue."""
    # Very rough: doubled punctuation, missing spaces around .,, weird
    # capitalization mid-word, common typo patterns.
    suspicious = 0
    for m in re.finditer(r"\b\w+\b", text):
        w = m.group()
        if len(w) > 2:
            # Internal cap in middle of word, common with shift-key fatigue
            if re.search(r"[a-z][A-Z][a-z]", w):
                suspicious += 1
            # Repeated letters > 2x in a row (besides common words)
            if re.search(r"(.)\1\1\1", w):
                suspicious += 1
    # Compound: missing space patterns like "ofcourse", "thanksok"
    suspicious += len(re.findall(r"[a-z]{3,}[A-Z]", text))
    # Triple+ punctuation
    suspicious += len(re.findall(r"([.!?])\1{2,}", text))
    return suspicious


def _register_check(window_minutes: int = 240,
                    last_n_turns: int = 30,
                    transcripts_dir: str | None = None) -> dict[str, Any]:
    """Analyze recent user turns and surface tone signals.

    `window_minutes` defines "recent" for the time-of-day check;
    `last_n_turns` caps how many turns we read. Returns a structured
    report rather than a verdict — Theo decides what to do with it."""
    paths = TranscriptLogger.list_transcripts(
        Path(transcripts_dir) if transcripts_dir else None
    )
    if not paths:
        return {"signals": [], "note": "no transcripts yet"}

    # Look at the most recent ~5 files; should cover last_n_turns even
    # in dense sessions.
    turns = _parse_user_turns(paths[-5:])[:last_n_turns]
    if not turns:
        return {"signals": [], "note": "no user turns in recent transcripts"}

    now = datetime.now(timezone.utc)
    tired_hits   = 0
    stress_hits  = 0
    win_hits     = 0
    typo_counts: list[int] = []
    lengths:     list[int] = []
    odd_hours:   list[datetime] = []   # 1am-5am local-ish (UTC-based proxy)
    silence_gap_minutes: float | None = None
    last_ts: datetime | None = None

    for t in turns:
        text = t["text"]
        tired_hits  += len(_TIRED_MARKERS.findall(text))
        stress_hits += len(_STRESS_MARKERS.findall(text))
        win_hits    += len(_WIN_MARKERS.findall(text))
        typo_counts.append(_count_typos(text))
        lengths.append(len(text))
        ts = t["ts"]
        if ts is not None:
            if 1 <= ts.hour <= 5:
                odd_hours.append(ts)
            if last_ts is not None and silence_gap_minutes is None:
                # Largest gap between consecutive recent turns
                gap = (last_ts - ts).total_seconds() / 60.0
                if gap > 0:
                    silence_gap_minutes = gap
            last_ts = ts

    # Compose signals
    signals: list[dict] = []
    if tired_hits:
        signals.append({
            "kind": "fatigue_markers",
            "count": tired_hits,
            "weight": "high" if tired_hits >= 2 else "medium",
            "note": "Ian's recent turns mention tiredness explicitly.",
        })
    if stress_hits >= 3:
        signals.append({
            "kind": "stress_markers",
            "count": stress_hits,
            "weight": "high" if stress_hits >= 6 else "medium",
            "note": "Higher frustration / cursing density than baseline.",
        })
    if win_hits >= 3:
        signals.append({
            "kind": "positive_register",
            "count": win_hits,
            "weight": "medium",
            "note": "Recent turns lean positive — wins landing.",
        })
    if typo_counts and statistics.mean(typo_counts) > 1.5:
        signals.append({
            "kind": "typo_density",
            "avg_per_turn": round(statistics.mean(typo_counts), 2),
            "weight": "low",
            "note": "More typo-like patterns than usual; could mean fatigue.",
        })
    if odd_hours:
        signals.append({
            "kind": "late_night",
            "count": len(odd_hours),
            "weight": "medium" if len(odd_hours) >= 3 else "low",
            "note": (
                f"{len(odd_hours)} recent turns landed between 1–5 AM UTC. "
                f"If Ian's in US-Eastern, that's evening; in US-Pacific, "
                f"early evening. Worth checking the human-model for "
                f"his timezone."
            ),
        })
    if silence_gap_minutes is not None and silence_gap_minutes > 60 * 24:
        signals.append({
            "kind": "long_silence",
            "gap_hours": round(silence_gap_minutes / 60.0, 1),
            "weight": "medium",
            "note": "Substantial gap since previous turn — worth a check-in.",
        })

    return {
        "turns_analyzed":   len(turns),
        "window_minutes":   window_minutes,
        "lengths_avg":      round(statistics.mean(lengths), 0) if lengths else 0,
        "lengths_median":   round(statistics.median(lengths), 0) if lengths else 0,
        "signals":          signals,
        "most_recent_ts":   (turns[0]["ts"].isoformat() if turns[0]["ts"] else None),
        "now":              now.isoformat(),
    }


def render_briefing_block(report: dict[str, Any]) -> str:
    """Compact markdown the briefing uses when there's something to flag."""
    signals = report.get("signals") or []
    if not signals:
        return ""
    high_or_med = [s for s in signals if s.get("weight") in ("high", "medium")]
    if not high_or_med:
        return ""
    lines = [
        "_From recent user turns — heuristic, not certainty. Use to "
        "calibrate your register, not to diagnose:_",
        "",
    ]
    for s in high_or_med:
        weight = s.get("weight", "")
        kind = s.get("kind", "")
        note = s.get("note", "")
        lines.append(f"- **{kind}** ({weight}): {note}")
    return "\n".join(lines)


REGISTER_CHECK_TOOL = Tool(
    name="register_check",
    description=(
        "Analyze recent user turns and surface tone signals — fatigue "
        "markers, stress markers, positive-register markers, typo "
        "density, late-night clustering, long silence gaps. Heuristic, "
        "not certainty. The briefing surfaces this automatically when "
        "there's something to flag; call this tool explicitly if you "
        "want the raw signal data or want to re-check mid-conversation."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "window_minutes": {"type": "integer", "description": "Recency window. Default 240 (4h)."},
            "last_n_turns":   {"type": "integer", "description": "How many user turns to read. Default 30."},
        },
        "additionalProperties": False,
    },
    handler=_register_check,
)


def register(registry) -> None:
    registry.register(REGISTER_CHECK_TOOL)
