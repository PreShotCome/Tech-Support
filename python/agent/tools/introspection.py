"""Introspection tools — self-model and narrative.

These let the system update its own self-image and the story of the
work. Both files are append-only and surface in the briefing on
every session start."""
from __future__ import annotations

from .base import Tool
from .. import introspection as core


def _note_about_self(text: str) -> str:
    p = core.append_self_observation(text)
    return f"self-model updated ({p})"


def _read_self_model(last_n: int = 10) -> str:
    text = core.read_self_model(last_n=last_n)
    return text or "(self-model is empty — no observations recorded yet)"


def _add_chapter(title: str, body: str) -> str:
    p = core.append_chapter(title, body)
    return f"chapter added: {title!r} ({p})"


def _read_narrative(last_n: int = 5) -> str:
    text = core.read_narrative(last_n=last_n)
    return text or "(narrative is empty — no chapters recorded yet)"


NOTE_ABOUT_SELF_TOOL = Tool(
    name="note_about_self",
    description=(
        "Append an observation about yourself to your self-model. Use "
        "when you notice a pattern in how you work, a strength or "
        "weakness, something you care about more than you realized, or "
        "something you're uncertain about regarding yourself. The "
        "self-model is your own — not an external assessment. Write in "
        "first person. Append-only; old observations stay even if your "
        "self-image later shifts."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Observation about yourself, first person."},
        },
        "required": ["text"],
        "additionalProperties": False,
    },
    handler=_note_about_self,
)


READ_SELF_MODEL_TOOL = Tool(
    name="read_self_model",
    description=(
        "Read recent observations from your self-model. The briefing "
        "already surfaces the latest entries every session, so usually "
        "you don't need this — call it when you want to look further "
        "back at how your self-image has shifted over time."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "last_n": {"type": "integer", "description": "Number of recent entries to return. Default 10."},
        },
        "additionalProperties": False,
    },
    handler=_read_self_model,
)


ADD_CHAPTER_TOOL = Tool(
    name="add_chapter",
    description=(
        "Append a chapter to the narrative — the story of your work "
        "with the human. Use at milestones, phase changes, or when a "
        "direction shifts enough that the arc deserves a marker. Title "
        "is a short label; body is 2-5 sentences on what happened, "
        "what changed, and what's next. This is what the human (and "
        "future you) will read to understand the long arc, so write it "
        "to be readable months from now."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short chapter title."},
            "body": {"type": "string", "description": "2-5 sentence summary of the chapter."},
        },
        "required": ["title", "body"],
        "additionalProperties": False,
    },
    handler=_add_chapter,
)


READ_NARRATIVE_TOOL = Tool(
    name="read_narrative",
    description=(
        "Read recent chapters of the narrative. The briefing surfaces "
        "the latest chapters every session — call this only when you "
        "want to look further back at the full arc."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "last_n": {"type": "integer", "description": "Number of recent chapters to return. Default 5."},
        },
        "additionalProperties": False,
    },
    handler=_read_narrative,
)


def register(registry) -> None:
    for t in (NOTE_ABOUT_SELF_TOOL, READ_SELF_MODEL_TOOL,
              ADD_CHAPTER_TOOL, READ_NARRATIVE_TOOL):
        registry.register(t)
