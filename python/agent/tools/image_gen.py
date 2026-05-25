"""Image generation via Pollinations.ai — free, no API key.

Pollinations.ai (https://pollinations.ai) hosts a free public image
generation endpoint that accepts a prompt in the URL path and returns
a PNG. Multiple models available (FLUX is the default; SDXL, Turbo,
others as alternatives). No key, no rate-limit signup required.

The tool returns a public URL. To put the image in the chat, Theo
embeds it in his reply using markdown image syntax:

    Here's the diagram you asked for:

    ![the thing](https://image.pollinations.ai/prompt/...)

The Flutter chat bubble parses `![alt](url)` patterns and renders
each one as an inline Image.network widget below or alongside the
text. Multiple images per message are fine.

Note: Pollinations URLs are deterministic for the same (prompt,
model, seed, dimensions) tuple. Same prompt + seed = same image
forever. For a fresh result, change the seed."""
from __future__ import annotations

import random
import urllib.parse
from typing import Any

from .base import Tool


POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
SUPPORTED_MODELS = {
    "flux":    "FLUX — best general-purpose model, balanced quality.",
    "turbo":   "Turbo — faster, lower quality. Good for iteration.",
    "flux-realism":   "FLUX-realism — photo-realistic style.",
    "flux-cablyai":   "FLUX-cablyai — stylized artistic.",
    "flux-anime":     "FLUX-anime — anime / illustration style.",
    "flux-3d":        "FLUX-3d — 3D-render style.",
    "any-dark":       "Any-dark — darker color palette.",
}


def _generate_image(prompt: str,
                     model: str = "flux",
                     width: int = 1024,
                     height: int = 1024,
                     seed: int | None = None,
                     enhance: bool = True) -> dict[str, Any]:
    """Build a Pollinations URL for the given prompt. The URL itself
    IS the image — fetching it returns PNG bytes. Theo embeds it as
    markdown image syntax in his reply for inline rendering."""
    if not prompt.strip():
        return {"error": "empty prompt"}
    if model not in SUPPORTED_MODELS:
        return {
            "error": f"unknown model {model!r}",
            "supported": sorted(SUPPORTED_MODELS.keys()),
        }
    if width < 64 or height < 64 or width > 2048 or height > 2048:
        return {"error": "width and height must be in [64, 2048]"}

    if seed is None:
        seed = random.randint(1, 999_999)

    encoded = urllib.parse.quote(prompt.strip(), safe="")
    params = urllib.parse.urlencode({
        "model":   model,
        "width":   int(width),
        "height":  int(height),
        "seed":    int(seed),
        "nologo":  "true",
        "enhance": "true" if enhance else "false",
    })
    url = f"{POLLINATIONS_BASE}/{encoded}?{params}"

    # Markdown snippet ready to drop into the reply
    md = f"![{prompt.strip()[:120]}]({url})"

    return {
        "prompt":   prompt.strip(),
        "model":    model,
        "width":    int(width),
        "height":   int(height),
        "seed":     int(seed),
        "url":      url,
        "markdown": md,
        "hint": (
            "To show the image in chat, include the `markdown` string "
            "above somewhere in your reply text. The Flutter chat will "
            "render it inline."
        ),
    }


GENERATE_IMAGE_TOOL = Tool(
    name="generate_image",
    description=(
        "Generate an image from a text prompt via Pollinations.ai "
        "(free, no API key). Returns a public image URL plus a "
        "markdown image snippet `![alt](url)` ready to embed in your "
        "chat reply — the Flutter chat parses markdown image syntax "
        "and renders inline. Models: flux (default, best general), "
        "turbo (fast), flux-realism (photo), flux-anime, flux-3d, "
        "any-dark. Same prompt+seed = same image; change seed for "
        "fresh results. Use when the human asks for a picture, "
        "diagram-as-illustration, mood image, sketch, concept art, "
        "etc."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Describe what to generate. Be specific about style, subject, lighting, composition.",
            },
            "model": {
                "type": "string",
                "description": "Model id: flux / turbo / flux-realism / flux-anime / flux-3d / flux-cablyai / any-dark. Default flux.",
            },
            "width": {"type": "integer", "description": "Image width in px. Default 1024. Max 2048."},
            "height": {"type": "integer", "description": "Image height in px. Default 1024. Max 2048."},
            "seed": {"type": "integer", "description": "Random seed. Omit for a fresh random one."},
            "enhance": {"type": "boolean", "description": "Let the service enhance the prompt with extra detail. Default true."},
        },
        "required": ["prompt"],
        "additionalProperties": False,
    },
    handler=_generate_image,
)


def register(registry) -> None:
    registry.register(GENERATE_IMAGE_TOOL)
