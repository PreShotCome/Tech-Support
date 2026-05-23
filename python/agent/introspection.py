"""Self-model and narrative — durable, append-only.

Two files, both written by the agent itself:

  - `self_model.md` — observations about who the system is. What it's
    good at, what trips it up, what it cares about, what it's not sure
    about itself. Imperfect on purpose. The system's self-image, not
    an external assessment.

  - `narrative.md` — the story of the work. Chapters added when a
    milestone hits, a phase ends, a direction changes. The integrator
    that turns scattered transcripts into a coherent arc the human can
    point at and say "this is what we did."

Both are append-only. Old entries never get overwritten — that would
lose the history of how the self-image changed. The briefing surfaces
the most recent of each on every session start, so the system always
opens with a current sense of itself."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _state_dir() -> Path:
    return Path.home() / ".techsupport_agent"


def self_model_path() -> Path:
    return _state_dir() / "self_model.md"


def narrative_path() -> Path:
    return _state_dir() / "narrative.md"


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
