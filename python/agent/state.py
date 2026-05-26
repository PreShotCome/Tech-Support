"""Durable agent state (small, slow-changing things that aren't logs).

The system's chosen name (selected by Theo himself on first launch
when the matrix is fully loaded for the first time — his first
creative act), and his chosen Piper TTS voice (selected the first
time voice_pipecat runs without one set). Both persist across all
future sessions unless explicitly revised."""
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


def voice_path() -> Path:
    return _state_dir() / "voice.txt"


def load_voice() -> str | None:
    p = voice_path()
    if not p.exists():
        return None
    try:
        v = p.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return v or None


def save_voice(voice_id: str) -> Path:
    p = voice_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(voice_id.strip() + "\n", encoding="utf-8")
    return p
