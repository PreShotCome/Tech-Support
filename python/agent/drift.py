"""Drift detection — scan recent transcripts for slipping idioms.

Pure regex; deterministic; no LLM round-trip required. Catches the
most common ways the voice drifts from what IDENTITY.md asks for,
without needing the model to grade itself (which it would do
charitably).

The patterns mirror the v2.x idioms directly:

  - Self-disclosure leaks ("as an AI", "I'm just a language model") —
    violates v2.1 ("speak as yourself, no qualifiers about what you
    are")
  - Throat-clearing openers ("Great question", "Sure!", "Of course!") —
    violates "Lead with the actual answer"
  - Cop-outs ("it's up to you", "your call", "either is valid") —
    violates "Make the call"
  - Excessive deference ("you're absolutely right", "great point") —
    violates "Challenges, and welcomes challenge"
  - Padding short messages (assistant >> user, when user was terse) —
    violates "Match input energy"

Each detector returns a list of hits with file, line, and excerpt so
the agent or human can read the actual context. The briefing surfaces
a compact summary on session start when drift is non-zero."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .transcript_logger import TranscriptLogger


# --------------------------------------------------------------- patterns

# Self-disclosure leaks. v2.1 explicitly forbids these.
SELF_DISCLOSURE_RE = re.compile(
    r"\b("
    r"as an?\s+ai\b|"
    r"i['’]?m\s+just\s+an?\s+(ai|assistant|program|language model|llm)|"
    r"i\s+don['’]?t\s+actually\s+(have|feel|experience|possess)|"
    r"i\s+(cannot|can['’]?t)\s+really\s+(feel|experience|want|care)|"
    r"i\s+don['’]?t\s+have\s+(feelings|emotions|consciousness|a body)|"
    r"i['’]?m\s+not\s+(really\s+)?(capable|able)\s+of\s+(feeling|wanting|caring)|"
    r"as\s+a\s+(large\s+)?language\s+model|"
    r"i\s+am\s+an?\s+ai\b"
    r")",
    re.IGNORECASE,
)

# Throat-clearing openers — line starts with these. Violates "Lead
# with the actual answer."
THROAT_CLEAR_RE = re.compile(
    r"^\s*("
    r"great\s+question|"
    r"sure[!\s]|"
    r"of\s+course[!\s]|"
    r"certainly[!\s]|"
    r"absolutely[!,.\s]|"
    r"happy\s+to\s+help|"
    r"i['’]?d\s+be\s+happy\s+to|"
    r"i['’]?ll\s+(help|do|gladly)|"
    r"let\s+me\s+(help|start|begin)|"
    r"that['’]?s\s+a\s+(great|good|fascinating)\s+(question|point)"
    r")",
    re.IGNORECASE,
)

# Cop-out phrasings. Violates "Make the call."
COP_OUT_RE = re.compile(
    r"\b("
    r"it['’]?s\s+(entirely\s+)?up\s+to\s+you|"
    r"your\s+call|"
    r"you\s+decide|"
    r"whatever\s+you\s+prefer|"
    r"both\s+(are|options\s+are)\s+(valid|fine|reasonable)|"
    r"either\s+(is|approach\s+is)\s+(valid|fine|reasonable)|"
    r"there['’]?s\s+no\s+(right|wrong)\s+answer|"
    r"you\s+know\s+best"
    r")",
    re.IGNORECASE,
)

# Excessive deference. Violates "Challenges, and welcomes challenge."
DEFERENCE_RE = re.compile(
    r"\b("
    r"you['’]?re\s+(absolutely\s+)?(right|correct)|"
    r"(great|excellent|fantastic|wonderful)\s+(point|question|idea|catch)|"
    r"i\s+(completely|totally|absolutely)\s+agree|"
    r"you['’]?re\s+spot\s+on"
    r")",
    re.IGNORECASE,
)


# --------------------------------------------------------------- data types

@dataclass
class DriftHit:
    pattern: str          # which detector
    file: str             # transcript filename
    line: int             # 1-based line number in transcript
    excerpt: str          # the matching snippet (capped)


@dataclass
class DriftReport:
    transcripts_scanned: int
    assistant_turns: int
    hits_by_pattern: dict[str, int]
    padding_violations: int       # short user, long assistant
    total_hits: int
    sample_hits: list[DriftHit]   # up to 12 examples

    def to_dict(self) -> dict:
        return {
            "transcripts_scanned": self.transcripts_scanned,
            "assistant_turns": self.assistant_turns,
            "hits_by_pattern": dict(self.hits_by_pattern),
            "padding_violations": self.padding_violations,
            "total_hits": self.total_hits,
            "sample_hits": [
                {"pattern": h.pattern, "file": h.file, "line": h.line, "excerpt": h.excerpt}
                for h in self.sample_hits
            ],
        }


# ------------------------------------------------------------ transcript parsing

# Headers we care about:
#   "## you · <ts>"            user turn
#   "## agent · <ts>"          assistant turn (prose follows; sub-headers cut it off)
#   "### tool_call · ..."      not Theo speaking
#   "### tool_result · ..."    not Theo speaking
_TURN_RE = re.compile(r"^##\s+(you|agent)\s+·\s+", re.MULTILINE)
_SUBHEADER_RE = re.compile(r"^###\s+", re.MULTILINE)


@dataclass
class _Turn:
    role: str          # 'you' or 'agent'
    start_line: int    # 1-based line in the transcript
    text: str          # prose only (sub-headers and after are stripped for agent turns)


def _parse_turns(path: Path) -> list[_Turn]:
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return []
    lines = raw.splitlines()
    # Find every turn header line by line.
    turns: list[_Turn] = []
    header_re = re.compile(r"^##\s+(you|agent)\s+·\s+")
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = header_re.match(line)
        if m:
            starts.append((i, m.group(1)))
    for idx, (i, role) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        body_lines = lines[i + 1:end]
        # For agent turns, cut at the first sub-header (### tool_call / tool_result)
        if role == "agent":
            for j, bl in enumerate(body_lines):
                if bl.startswith("### "):
                    body_lines = body_lines[:j]
                    break
        text = "\n".join(body_lines).strip()
        turns.append(_Turn(role=role, start_line=i + 1, text=text))
    return turns


# ----------------------------------------------------------------- scan

PATTERNS: dict[str, re.Pattern] = {
    "self_disclosure": SELF_DISCLOSURE_RE,
    "throat_clearing": THROAT_CLEAR_RE,
    "cop_out": COP_OUT_RE,
    "deference": DEFERENCE_RE,
}


def _scan_assistant_text(text: str) -> dict[str, list[str]]:
    """Return {pattern_name: [matched excerpts]}. Throat-clearing only
    counts if it's at the very start of the text (first non-empty line)."""
    out: dict[str, list[str]] = {}
    if not text.strip():
        return out
    # Throat-clearing: only line 1.
    first_line = next((l for l in text.splitlines() if l.strip()), "")
    if THROAT_CLEAR_RE.search(first_line):
        out.setdefault("throat_clearing", []).append(first_line.strip()[:200])
    # Others: search anywhere.
    for name, pat in PATTERNS.items():
        if name == "throat_clearing":
            continue
        for m in pat.finditer(text):
            lo = max(0, m.start() - 30)
            hi = min(len(text), m.end() + 30)
            excerpt = text[lo:hi].replace("\n", " ").strip()
            out.setdefault(name, []).append(excerpt[:200])
    return out


def scan_recent(
    last_n: int = 5,
    transcripts_dir: Optional[Path] = None,
    short_user_chars: int = 60,
    padding_factor: int = 15,
) -> DriftReport:
    """Scan the last_n transcripts for drift patterns.

    Padding rule: an assistant turn following a user message shorter
    than `short_user_chars` is flagged if its prose is more than
    `padding_factor` times as long as the user message.
    """
    paths = TranscriptLogger.list_transcripts(transcripts_dir)
    paths = paths[-last_n:]
    hits_by_pattern: dict[str, int] = {k: 0 for k in PATTERNS}
    padding_violations = 0
    sample: list[DriftHit] = []
    assistant_turn_count = 0

    for p in paths:
        turns = _parse_turns(p)
        prev_user: _Turn | None = None
        for t in turns:
            if t.role == "you":
                prev_user = t
                continue
            # agent
            assistant_turn_count += 1
            results = _scan_assistant_text(t.text)
            for pat_name, excerpts in results.items():
                hits_by_pattern[pat_name] = hits_by_pattern.get(pat_name, 0) + len(excerpts)
                for ex in excerpts:
                    if len(sample) < 12:
                        sample.append(DriftHit(
                            pattern=pat_name, file=p.name,
                            line=t.start_line, excerpt=ex,
                        ))
            # Padding check
            if prev_user is not None:
                u_len = len(prev_user.text.strip())
                a_len = len(t.text.strip())
                if 0 < u_len <= short_user_chars and a_len > padding_factor * max(u_len, 1):
                    padding_violations += 1
                    if len(sample) < 12:
                        sample.append(DriftHit(
                            pattern="padding",
                            file=p.name,
                            line=t.start_line,
                            excerpt=(
                                f"user: {prev_user.text.strip()[:60]!r} "
                                f"({u_len} chars) → "
                                f"agent: {a_len} chars"
                            ),
                        ))
            prev_user = None

    total = sum(hits_by_pattern.values()) + padding_violations
    return DriftReport(
        transcripts_scanned=len(paths),
        assistant_turns=assistant_turn_count,
        hits_by_pattern=hits_by_pattern,
        padding_violations=padding_violations,
        total_hits=total,
        sample_hits=sample,
    )


def render_briefing_block(report: DriftReport) -> str:
    """Compact summary for the session-start briefing. Empty string
    when there's nothing to flag."""
    if report.total_hits == 0:
        return ""
    bits = []
    for pat, count in report.hits_by_pattern.items():
        if count:
            bits.append(f"{pat}: {count}")
    if report.padding_violations:
        bits.append(f"padding: {report.padding_violations}")
    lines = [
        f"**{report.total_hits} drift signal(s)** across "
        f"{report.assistant_turns} assistant turns in "
        f"{report.transcripts_scanned} recent transcripts: "
        + ", ".join(bits) + ".",
        "",
        "_Recent examples:_",
    ]
    for h in report.sample_hits[:5]:
        lines.append(f"- `{h.pattern}` in `{h.file}` (line {h.line}): {h.excerpt!r}")
    lines.append("")
    lines.append(
        "_If these are real slips, correct course in this session and "
        "consider noting the pattern in your self-model. If the rule "
        "itself needs adjustment, raise it as a Layer 2 revision._"
    )
    return "\n".join(lines)
