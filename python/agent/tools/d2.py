"""d2 diagram rendering — text-to-SVG/PNG architecture diagrams.

d2 (https://d2lang.com) is a modern text-based diagram language by
Terrastruct. Theo can sketch architecture / flow / system diagrams
when explaining how things fit together — much clearer than ASCII art.

Requires the d2 CLI installed:
    winget install terrastruct.d2          # Windows
    brew install d2                        # macOS
    curl -fsSL https://d2lang.com/install.sh | sh -s --   # Linux

Reference docs: docs/research/d2/

Example d2 source:
    bridge -> Theo: incoming msg
    Theo -> claude-cli: prompt
    claude-cli -> Theo: reply
    Theo -> bridge: response

The tool writes the diagram to a temp file (default SVG) and returns
the path. The Flutter chat app doesn't render images yet, so for now
this is a "Theo can produce a diagram file on disk Ian can open"
capability rather than inline rendering."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import Tool


def _render_diagram(d2_source: str, output_format: str = "svg",
                    theme: int = 0) -> dict[str, Any]:
    """Render a d2 source string to SVG or PNG. Returns a dict with
    the output file path or an error."""
    if not d2_source.strip():
        return {"error": "empty d2 source"}
    if not shutil.which("d2"):
        return {
            "error": "d2 CLI not installed",
            "install": (
                "Windows: winget install terrastruct.d2 | "
                "macOS: brew install d2 | "
                "Linux: curl -fsSL https://d2lang.com/install.sh | sh -s --"
            ),
        }
    if output_format not in {"svg", "png", "pdf"}:
        return {"error": f"format must be svg/png/pdf, got {output_format!r}"}

    # Write source to a temp file
    src_fd, src_path = tempfile.mkstemp(suffix=".d2", prefix="theo_d2_")
    out_fd, out_path = tempfile.mkstemp(
        suffix=f".{output_format}", prefix="theo_d2_",
    )
    import os
    os.close(src_fd)
    os.close(out_fd)
    Path(src_path).write_text(d2_source, encoding="utf-8")

    cmd = ["d2", "--theme", str(int(theme)), src_path, out_path]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"error": "d2 render timed out after 30s"}
    finally:
        try:
            Path(src_path).unlink()
        except Exception:
            pass

    if proc.returncode != 0:
        return {
            "error": f"d2 exit {proc.returncode}",
            "stderr": (proc.stderr or "")[:500],
        }

    size = Path(out_path).stat().st_size if Path(out_path).exists() else 0
    return {
        "output_path": out_path,
        "format": output_format,
        "size_bytes": size,
        "note": "Diagram written to disk. Open the path to view.",
    }


RENDER_DIAGRAM_TOOL = Tool(
    name="render_diagram",
    description=(
        "Render a d2-language source string into an SVG, PNG, or PDF "
        "diagram on disk. d2 (https://d2lang.com) is a clean text-based "
        "diagram language. Use this when explaining architecture, data "
        "flow, system relationships — anything where a picture beats "
        "prose. Returns the output file path the human can open. "
        "Requires the d2 CLI on PATH; falls back to a clear install "
        "hint when missing."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "d2_source": {
                "type": "string",
                "description": (
                    "d2 source code. Example: 'bridge -> Theo: incoming msg\\n"
                    "Theo -> claude-cli: prompt'"
                ),
            },
            "output_format": {
                "type": "string",
                "description": "svg (default), png, or pdf.",
            },
            "theme": {
                "type": "integer",
                "description": (
                    "d2 theme ID. 0 default (neutral), 200 dark mode, "
                    "300 origami, 8 mint. See d2 themes docs."
                ),
            },
        },
        "required": ["d2_source"],
        "additionalProperties": False,
    },
    handler=_render_diagram,
)


def register(registry) -> None:
    registry.register(RENDER_DIAGRAM_TOOL)
