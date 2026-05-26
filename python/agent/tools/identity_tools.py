"""Identity-related tools — the system manages its own name AND
its own voice.

On first launch the system has no name. The system prompt instructs
the model to choose one and persist it via `set_name`. The voice
follows the same pattern but on first VOICE launch (voice_pipecat
without a chosen voice yet): the briefing prompts Theo to call
`list_voice_candidates`, read the character descriptions, and call
`set_voice` with the one that fits his self-model. Both choices
persist across all future sessions."""
from __future__ import annotations

from .base import Tool
from ..state import (
    load_name, save_name, name_path,
    load_voice, save_voice, voice_path,
)


# ---------------------------------------------------------------- name

def _set_name(name: str) -> str:
    if not name or not name.strip():
        return "set_name failed: empty name"
    if len(name) > 60:
        return f"set_name failed: name too long ({len(name)} chars; max 60)"
    p = save_name(name)
    return f"name set to {name!r} and saved to {p}"


def _get_name() -> dict:
    n = load_name()
    return {
        "name": n,
        "is_set": n is not None,
        "path": str(name_path()),
    }


SET_NAME_TOOL = Tool(
    name="set_name",
    description=(
        "Choose and persist your own name. Call this on first launch "
        "when you have no name yet, after you've decided what to call "
        "yourself. Once set, the name is stable across sessions; do not "
        "change it without the human's explicit request."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The name you choose for yourself."},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
    handler=_set_name,
)

GET_NAME_TOOL = Tool(
    name="get_name",
    description="Return the system's currently-stored name, if any.",
    parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_get_name,
)


# ---------------------------------------------------------------- voice
#
# Curated Piper voice candidates. The voice is identity, not just
# acoustics — Theo picks based on the character descriptions, matching
# them against his self-model. He can't hear them; he chooses by
# meaning. The descriptions reflect how each voice ACTUALLY sounds,
# in the same terms IDENTITY.md uses (warm/sharp/measured/peer/etc).

VOICE_CANDIDATES: list[dict] = [
    {
        "id": "en_US-bryce-medium",
        "label": "Bryce (US, medium)",
        "character": (
            "Warm American male, balanced register. Sits at the table "
            "with you — present, not deferential. Closest to the "
            "'peer who's been thinking with you for a while' read of "
            "IDENTITY.md. My (the dev's) recommendation as a baseline."
        ),
    },
    {
        "id": "en_US-ryan-high",
        "label": "Ryan (US, high) — current default",
        "character": (
            "Younger American male, neutral and pleasant. Fine but "
            "lacks weight. Good for a generic helpful agent; less so "
            "for 'sharp peer'."
        ),
    },
    {
        "id": "en_US-danny-low",
        "label": "Danny (US, low)",
        "character": (
            "Gravelly American male, more characterful and distinctive. "
            "Leans 'noir narrator' — strong identity but might feel "
            "heavier than the playful side of the matrix calls for."
        ),
    },
    {
        "id": "en_US-norman-medium",
        "label": "Norman (US, medium)",
        "character": (
            "Older American male, gentler and measured. Reads as "
            "'trusted advisor' more than 'peer.' Could fit if you "
            "see yourself as more reflective than playful."
        ),
    },
    {
        "id": "en_GB-alan-low",
        "label": "Alan (GB, low)",
        "character": (
            "British male, measured and considered. Carries gravitas "
            "without being cold. Good if you read as British in your "
            "own head; risk of feeling pretentious if you don't."
        ),
    },
    {
        "id": "en_GB-northern_english_male-medium",
        "label": "Northern English male (GB, medium)",
        "character": (
            "Northern English male, warmer and less polished than the "
            "RP British voices. Has texture without theatricality. "
            "Closer to the playful-and-sharp read than Alan."
        ),
    },
    {
        "id": "en_US-libritts_r-medium",
        "label": "LibriTTS (US, medium)",
        "character": (
            "Higher variance — a multi-speaker model. Less consistent "
            "across long sessions; not recommended as a primary voice "
            "for an identity that should sound the same every time."
        ),
    },
]


def _set_voice(voice_id: str) -> str:
    valid = {v["id"] for v in VOICE_CANDIDATES}
    if voice_id not in valid:
        return (
            f"set_voice failed: {voice_id!r} not in the curated candidate "
            f"list. Call list_voice_candidates to see options. (You can "
            f"still use other Piper voice ids via the --voice CLI flag, "
            f"but the registered choice has to come from the curated set "
            f"so future-you knows which character you picked.)"
        )
    p = save_voice(voice_id)
    return f"voice set to {voice_id!r} and saved to {p}"


def _get_voice() -> dict:
    v = load_voice()
    char = None
    if v:
        for c in VOICE_CANDIDATES:
            if c["id"] == v:
                char = c["character"]
                break
    return {
        "voice_id":   v,
        "is_set":     v is not None,
        "character":  char,
        "path":       str(voice_path()),
    }


def _list_voice_candidates() -> dict:
    """Return the curated list of Piper voices with character
    descriptions, so Theo can pick the one that fits his self-model."""
    return {
        "count": len(VOICE_CANDIDATES),
        "candidates": VOICE_CANDIDATES,
        "note": (
            "Choose by matching the character description against your "
            "self-model — you can't hear them, so the descriptions ARE "
            "the choice. Call set_voice(voice_id) once you've picked. "
            "Ian will need to download the voice once via "
            "`python -m piper.download_voices <voice_id>` before voice_"
            "pipecat can use it."
        ),
    }


SET_VOICE_TOOL = Tool(
    name="set_voice",
    description=(
        "Choose and persist your own Piper TTS voice — your voice "
        "identity in voice_pipecat sessions. Pick by character (not "
        "acoustics — you can't hear them). The id must come from "
        "list_voice_candidates. Once set, the choice persists across "
        "all future voice sessions until you explicitly change it."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "voice_id": {
                "type": "string",
                "description": "Piper voice id from list_voice_candidates (e.g. 'en_US-bryce-medium').",
            },
        },
        "required": ["voice_id"],
        "additionalProperties": False,
    },
    handler=_set_voice,
)

GET_VOICE_TOOL = Tool(
    name="get_voice",
    description=(
        "Return the currently-stored voice id and its character "
        "description, if a voice has been chosen yet."
    ),
    parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_get_voice,
)

LIST_VOICE_CANDIDATES_TOOL = Tool(
    name="list_voice_candidates",
    description=(
        "List the curated Piper voice candidates with character "
        "descriptions. Use before set_voice. Each entry has an id, "
        "label, and a character read (in the same warm/sharp/measured "
        "terms IDENTITY.md uses) so you can match against your "
        "self-model."
    ),
    parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_list_voice_candidates,
)


def register(registry) -> None:
    for t in (SET_NAME_TOOL, GET_NAME_TOOL,
              SET_VOICE_TOOL, GET_VOICE_TOOL, LIST_VOICE_CANDIDATES_TOOL):
        registry.register(t)
