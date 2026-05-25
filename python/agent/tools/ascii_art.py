"""ASCII art from an image — load an image, downsample to a character
grid, map luminance to a glyph ramp, return the text.

Lightweight reimplementation of the vietnh1009/ASCII-generator approach.
No new dependencies — uses Pillow (already required at the project
level) and optionally `requests` for URL inputs (in the [agent] extra).

Use cases:
  - "ASCII-ify this Pollinations image" — chain generate_image -> the
    returned URL -> here
  - Headers / decorations for terminal output
  - Compact previews of images when an inline render isn't worth it

The output is plain text the agent embeds in a markdown code fence
so spacing renders correctly:

    ```
    @@@%%###
    %%###***
    ...
    ```"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from .base import Tool


# Glyph ramp from darkest to lightest. Standard luminance ramp used by
# most ASCII converters; tuned to roughly match what a monospace font
# renders at chat-bubble sizes.
_RAMP = "@%#*+=-:. "


def _generate_ascii(image_source: str,
                     width: int = 80,
                     invert: bool = False) -> dict[str, Any]:
    """Convert an image (URL or local path) into ASCII art.

    `width` is the output character width; height is computed to
    preserve aspect ratio with a 0.55 correction for fonts being taller
    than wide. `invert` flips the luminance ramp for dark-background
    chats where dark = empty, light = solid."""
    src = image_source.strip()
    if not src:
        return {"error": "empty image_source"}
    try:
        from PIL import Image
    except ImportError:
        return {"error": "Pillow not installed (should be in base deps)"}

    # Load: URL or local path
    try:
        if src.startswith(("http://", "https://")):
            try:
                import requests
            except ImportError:
                return {"error": "requests not installed; URL input needs [agent] extra"}
            resp = requests.get(src, timeout=20)
            if resp.status_code >= 400:
                return {"error": f"HTTP {resp.status_code} fetching image"}
            img = Image.open(BytesIO(resp.content))
        else:
            p = Path(src).expanduser()
            if not p.exists():
                return {"error": f"file not found: {p}"}
            img = Image.open(p)
    except Exception as e:
        return {"error": f"could not open image: {type(e).__name__}: {e}"}

    img = img.convert("L")  # grayscale

    width = max(20, min(200, int(width)))
    aspect = img.height / max(1, img.width)
    new_height = max(5, int(aspect * width * 0.55))
    img = img.resize((width, new_height))

    ramp = _RAMP[::-1] if invert else _RAMP
    n = len(ramp)
    pixels = list(img.getdata())
    lines: list[str] = []
    for y in range(new_height):
        row_pixels = pixels[y * width:(y + 1) * width]
        row = "".join(ramp[min(n - 1, int(p / 256 * n))] for p in row_pixels)
        lines.append(row)
    art = "\n".join(lines)

    fenced = f"```\n{art}\n```"

    return {
        "source":    src,
        "width":     width,
        "height":    new_height,
        "ascii":     art,
        "markdown":  fenced,
        "hint": (
            "Drop the `markdown` string into your reply so the chat "
            "renders it in a monospace code block — spacing matters or "
            "the picture warps."
        ),
    }


GENERATE_ASCII_TOOL = Tool(
    name="generate_ascii",
    description=(
        "Turn an image into ASCII art. `image_source` is either a URL "
        "(e.g. a Pollinations result from generate_image) or a local "
        "file path. `width` is character columns (default 80, range "
        "20-200). `invert` swaps the luminance ramp for dark-bg "
        "rendering. Returns the ASCII string plus a ready-to-embed "
        "markdown code-fenced version. Use sparingly — fun, mostly "
        "decorative; not a substitute for showing the actual image "
        "via the markdown-image syntax."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "image_source": {"type": "string", "description": "Image URL (http/https) or local path."},
            "width": {"type": "integer", "description": "Character columns. Default 80. Range 20-200."},
            "invert": {"type": "boolean", "description": "Invert luminance ramp. Default false."},
        },
        "required": ["image_source"],
        "additionalProperties": False,
    },
    handler=_generate_ascii,
)


def register(registry) -> None:
    registry.register(GENERATE_ASCII_TOOL)
