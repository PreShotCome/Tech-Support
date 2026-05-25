"""QR code generation — encode any text/URL as a scannable image.

Wraps python-qrcode (https://github.com/lincolnloop/python-qrcode) and
returns the result as a base64 data URL ready to embed inline in the
chat. No file storage required; the URL itself carries the image data,
and the Flutter chat's markdown-image renderer handles data: URIs the
same as http URLs.

Setup:
    pip install qrcode[pil]

Reference docs: docs/research/ (the lincolnloop/python-qrcode README,
once pulled in).

Use cases the agent should reach for this:
  - "Share this URL with my phone" -> QR code for the URL
  - "QR for the Soteria login link"
  - WiFi credentials (Theo can format the WIFI: payload)
  - vCard contact info
  - Any "scan this with your phone" moment"""
from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

from .base import Tool


def _generate_qr(text: str,
                  size: int = 10,
                  border: int = 4,
                  fill_color: str = "black",
                  back_color: str = "white") -> dict[str, Any]:
    """Generate a QR code as a base64 PNG data URL the chat can embed
    inline via the existing markdown-image renderer."""
    if not text.strip():
        return {"error": "empty text"}
    try:
        import qrcode
    except ImportError:
        return {
            "error": "qrcode library not installed",
            "install": "pip install 'qrcode[pil]' (in the python/.venv)",
        }

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=max(1, min(40, int(size))),
        border=max(0, min(16, int(border))),
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"

    short_text = text.strip()[:60] + ("..." if len(text.strip()) > 60 else "")
    md = f"![QR code: {short_text}]({data_url})"

    return {
        "text":      text,
        "size_px":   img.size[0],
        "data_url":  data_url,
        "markdown":  md,
        "hint": (
            "To show the QR in chat, include the `markdown` string above "
            "somewhere in your reply. The Flutter chat will render it inline."
        ),
    }


GENERATE_QR_TOOL = Tool(
    name="generate_qr",
    description=(
        "Generate a QR code from any text or URL and return it as a "
        "ready-to-embed markdown image (base64 data URL). The Flutter "
        "chat renders it inline. Use when the human wants to scan "
        "something with their phone: share a URL, WiFi credentials "
        "(format: 'WIFI:T:WPA;S:ssid;P:password;;'), vCard, app deep "
        "link, etc. `size` is the box size in pixels per QR module "
        "(default 10, range 1-40). `border` is the quiet-zone width "
        "in modules (default 4). Colors accept any PIL-compatible "
        "name or hex."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text or URL to encode."},
            "size": {"type": "integer", "description": "Module size px. Default 10."},
            "border": {"type": "integer", "description": "Quiet-zone width in modules. Default 4."},
            "fill_color": {"type": "string", "description": "Foreground color. Default 'black'."},
            "back_color": {"type": "string", "description": "Background color. Default 'white'."},
        },
        "required": ["text"],
        "additionalProperties": False,
    },
    handler=_generate_qr,
)


def register(registry) -> None:
    registry.register(GENERATE_QR_TOOL)
