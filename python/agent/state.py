"""Durable agent state (small, slow-changing things that aren't logs).

Currently just the system's chosen name — selected by the system itself
on first launch when the matrix is fully loaded for the first time. This
is the first creative act, and it persists across all future sessions
unless explicitly revised."""
from __future__ import annotations

from pathlib import Path


def _state_dir() -> Path:
    return Path.home() / ".techsupport_agent"


def name_path() -> Path:
    return _state_dir() / "name.txt"


def load_name() -> str | None:
    p = name_path()
    if not p.exists():
        return None
    try:
        name = p.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return name or None


def save_name(name: str) -> Path:
    p = name_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(name.strip() + "\n", encoding="utf-8")
    return p
