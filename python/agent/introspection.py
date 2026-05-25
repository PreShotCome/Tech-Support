"""Self-model, human-model, narrative, threads — durable, append-only.

Four files, all written by the agent itself:

  - `self_model.md` — observations about who the system is. What it's
    good at, what trips it up, what it cares about, what it's not sure
    about itself. Imperfect on purpose. The system's self-image, not
    an external assessment.

  - `human_model.md` — the system's model of the human it's working
    with. Preferences, register, what works and what doesn't, what he
    is building, what he values, where the relationship currently
    stands. The relational mirror to the self-model.

  - `narrative.md` — the story of the work. Chapters added when a
    milestone hits, a phase ends, a direction changes. The integrator
    that turns scattered transcripts into a coherent arc the human can
    point at and say "this is what we did."

  - `threads.md` — open threads: things the system has noticed are
    unresolved and worth bringing up unprompted. A friend's mental
    "remind me to ask about X" list, not a project manager's TODO
    board. The briefing surfaces all open threads so the system can
    naturally lead with "how did the deploy go?" instead of waiting
    to be asked.

The first three are append-only. `threads.md` is also append-only at
the entry level (entries never get rewritten, only their status flips
from OPEN to CLOSED with a resolution). The briefing surfaces the
most recent of each on every session start, so the system always
opens with a current sense of itself, the human, the work, and
what's still hanging."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional


def _state_dir() -> Path:
    return Path.home() / ".techsupport_agent"


def self_model_path() -> Path:
    return _state_dir() / "self_model.md"


def human_model_path() -> Path:
    return _state_dir() / "human_model.md"


def narrative_path() -> Path:
    return _state_dir() / "narrative.md"


def threads_path() -> Path:
    return _state_dir() / "threads.md"


# ---------------------------------------------------------------- self-model

def append_self_observation(text: str) -> Path:
    p = self_model_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n## {ts}\n\n{text.strip()}\n")
    return p


def read_self_model(last_n: int = 10, max_chars: int = 4000) -> str:
    p = self_model_path()
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    blocks = text.split("\n## ")
    tail = "\n## ".join(blocks[-last_n:]) if blocks else text
    if len(tail) > max_chars:
        return "...\n" + tail[-max_chars:]
    return tail


# ---------------------------------------------------------------- human-model

def append_human_observation(text: str) -> Path:
    p = human_model_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n## {ts}\n\n{text.strip()}\n")
    return p


def read_human_model(last_n: int = 10, max_chars: int = 4000) -> str:
    p = human_model_path()
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    blocks = text.split("\n## ")
    tail = "\n## ".join(blocks[-last_n:]) if blocks else text
    if len(tail) > max_chars:
        return "...\n" + tail[-max_chars:]
    return tail


# ----------------------------------------------------------------- narrative

def append_chapter(title: str, body: str) -> Path:
    p = narrative_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    title = title.strip() or "(untitled chapter)"
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n## {ts} — {title}\n\n{body.strip()}\n")
    return p


def read_narrative(last_n: int = 5, max_chars: int = 6000) -> str:
    p = narrative_path()
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    blocks = text.split("\n## ")
    tail = "\n## ".join(blocks[-last_n:]) if blocks else text
    if len(tail) > max_chars:
        return "...\n" + tail[-max_chars:]
    return tail


# ------------------------------------------------------------------- threads
#
# Format for each entry in threads.md:
#
#     ## thread-NNN · YYYY-MM-DD · OPEN
#     <description>
#
#     ## thread-NNN · YYYY-MM-DD · CLOSED (YYYY-MM-DD)
#     <description>
#     > resolution: <text>
#
# Entries are append-only at the block level — closing a thread
# rewrites that one block's status header and appends a resolution
# line, but no entry is ever deleted. The history of what was open
# and how it resolved stays intact.

import re as _re


def _read_threads_text() -> str:
    p = threads_path()
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def _write_threads_text(text: str) -> None:
    p = threads_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".md.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)


def _next_thread_id(text: str) -> str:
    ids = _re.findall(r"##\s+thread-(\d+)\s+", text)
    n = (max((int(i) for i in ids), default=0)) + 1
    return f"thread-{n:03d}"


def open_thread(description: str) -> dict:
    """Add a new OPEN thread. Returns the thread id and full entry."""
    description = description.strip()
    if not description:
        return {"error": "empty description"}
    text = _read_threads_text()
    tid = _next_thread_id(text)
    today = datetime.now().strftime("%Y-%m-%d")
    entry = f"\n## {tid} · {today} · OPEN\n\n{description}\n"
    _write_threads_text(text + entry)
    return {"thread_id": tid, "status": "open", "description": description}


def close_thread(thread_id: str, resolution: str) -> dict:
    """Flip a thread from OPEN to CLOSED with a resolution note.
    Returns the updated entry, or an error if the id doesn't exist or
    is already closed."""
    text = _read_threads_text()
    if not text:
        return {"error": f"{thread_id} not found (threads file is empty)"}

    pattern = _re.compile(
        rf"(##\s+{_re.escape(thread_id)}\s+·\s+(\d{{4}}-\d{{2}}-\d{{2}})\s+·\s+)OPEN\n(.*?)(?=\n## |\Z)",
        flags=_re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        # Could be already closed, or not present at all.
        if _re.search(rf"##\s+{_re.escape(thread_id)}\s+·\s+\d{{4}}-\d{{2}}-\d{{2}}\s+·\s+CLOSED",
                      text):
            return {"error": f"{thread_id} is already closed"}
        return {"error": f"{thread_id} not found"}

    today = datetime.now().strftime("%Y-%m-%d")
    body = m.group(3).rstrip()
    resolution = resolution.strip() or "(no resolution given)"
    new_block = (
        f"{m.group(1)}CLOSED ({today})\n"
        f"{body}\n> resolution: {resolution}\n"
    )
    new_text = text[:m.start()] + new_block + text[m.end():]
    _write_threads_text(new_text)
    return {"thread_id": thread_id, "status": "closed", "resolution": resolution}


def list_threads(status: str = "open") -> list[dict]:
    """List threads filtered by status: 'open', 'closed', or 'all'."""
    text = _read_threads_text()
    if not text:
        return []
    pattern = _re.compile(
        r"##\s+(thread-\d+)\s+·\s+(\d{4}-\d{2}-\d{2})\s+·\s+(OPEN|CLOSED(?:\s+\(\d{4}-\d{2}-\d{2}\))?)\n(.*?)(?=\n## |\Z)",
        flags=_re.DOTALL,
    )
    out = []
    want = status.lower()
    for tid, opened, status_header, body in pattern.findall(text):
        is_open = status_header.strip().upper() == "OPEN"
        if want == "open" and not is_open:
            continue
        if want == "closed" and is_open:
            continue
        out.append({
            "thread_id": tid,
            "opened": opened,
            "status": "open" if is_open else "closed",
            "body": body.strip(),
        })
    return out


def render_open_threads_block() -> str:
    """Markdown block for the briefing — open threads only."""
    open_ = list_threads(status="open")
    if not open_:
        return ""
    lines = []
    for t in open_:
        lines.append(f"- **{t['thread_id']}** (opened {t['opened']}): {t['body']}")
    return "\n".join(lines)


# ----------------------------------------------------------------- summaries
#
# Per-session digests. Each entry is keyed by the transcript filename
# (or just its timestamp prefix) so the briefing can answer "which
# recent transcript haven't I summarized yet?".
#
# Format:
#     ## <transcript_key> · <title>
#     <2-5 sentence body>


def summaries_path() -> Path:
    return _state_dir() / "summaries.md"


def append_summary(transcript_key: str, title: str, body: str) -> Path:
    """Add a new session summary. `transcript_key` is the transcript's
    filename (or its timestamp prefix) so we can join later."""
    p = summaries_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    key = transcript_key.strip()
    title = title.strip() or "(untitled)"
    body = body.strip()
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n## {key} · {title}\n\n{body}\n")
    return p


_SUMMARY_HEADER_RE = _re.compile(
    r"^##\s+(\S+)\s+·\s+(.+?)\s*$", _re.MULTILINE,
)


def read_summaries(last_n: int = 15, max_chars: int = 6000) -> str:
    p = summaries_path()
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    blocks = text.split("\n## ")
    tail = "\n## ".join(blocks[-last_n:]) if blocks else text
    if len(tail) > max_chars:
        return "...\n" + tail[-max_chars:]
    return tail


def summarized_transcript_keys() -> set[str]:
    """Set of transcript keys that already have a summary entry."""
    p = summaries_path()
    if not p.exists():
        return set()
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return set()
    return {m.group(1) for m in _SUMMARY_HEADER_RE.finditer(text)}


def unsummarized_transcripts(recent_n: int = 5,
                              transcripts_dir: Optional[Path] = None) -> list[str]:
    """Filenames of recent transcripts that don't have a summary yet.
    Always excludes the very newest (current session) — that one isn't
    finished yet, so don't ask for a summary mid-conversation."""
    from .transcript_logger import TranscriptLogger
    paths = TranscriptLogger.list_transcripts(transcripts_dir)
    if len(paths) <= 1:
        return []
    # Drop the most recent (current session in progress)
    paths = paths[-recent_n - 1: -1]
    summarized = summarized_transcript_keys()
    out = []
    for p in paths:
        if p.name in summarized:
            continue
        # Also accept timestamp prefix as the key (more permissive)
        stem = p.stem  # without .md
        if stem in summarized:
            continue
        out.append(p.name)
    return out
