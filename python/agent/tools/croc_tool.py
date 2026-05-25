"""croc tool — peer-to-peer file transfer between any two machines.

croc (https://github.com/schollz/croc) is a CLI for ad-hoc secure file
transfer. The sender runs `croc send <file>` and croc prints a short
code. The receiver runs `croc <code>` on any internet-connected
machine and the file arrives, encrypted in transit.

Setup:
  - Install: `winget install schollz.croc` (Windows),
    `brew install croc` (macOS), `apt install croc` (Linux).

Theo's use: prepare a file to share, hand Ian (or anyone Ian is
talking to) a transfer code they can run on the other end.

Note: `croc send` is a long-running blocking command — it waits for
the receiver to connect. This tool starts it in the background,
captures the generated code from stdout, and returns the code
immediately. The send subprocess keeps running until either someone
picks up the file or it times out (croc's own default ~24h).

Reference docs: docs/research/croc/"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .base import Tool


_CODE_RE = re.compile(r"croc\s+(\S+(?:-\S+){2,})")


def _croc_send(path: str, code: str | None = None,
                timeout_seconds: int = 60) -> dict[str, Any]:
    """Start a croc send in the background and return the transfer code.
    The send subprocess keeps running until pickup or croc's internal
    timeout; this tool just hands you the code to share."""
    if not shutil.which("croc"):
        return {
            "error": "croc not installed",
            "install": (
                "Windows: winget install schollz.croc | "
                "macOS: brew install croc | "
                "Linux: apt install croc"
            ),
        }

    src = Path(path).expanduser()
    if not src.exists():
        return {"error": f"source not found: {src}"}

    # Build the command. If user supplied a code, use it; otherwise let
    # croc generate one.
    cmd = ["croc", "--yes"]
    if code:
        cmd.extend(["send", "--code", code, str(src)])
    else:
        cmd.extend(["send", str(src)])

    # Spawn detached. We read stdout/stderr until we see the receive
    # code, then return — but keep the subprocess running.
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1,
            # On Windows, DETACHED_PROCESS lets croc outlive our agent.
            # On *nix, start_new_session does the equivalent.
            creationflags=(0x00000008 if os.name == "nt" else 0),
            start_new_session=(os.name != "nt"),
        )
    except Exception as e:
        return {"error": f"failed to start croc: {type(e).__name__}: {e}"}

    # Read lines until we find the code or timeout.
    found_code: str | None = code
    start = time.time()
    buf: list[str] = []
    if proc.stdout is not None:
        while time.time() - start < timeout_seconds:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
                continue
            buf.append(line)
            if found_code is None:
                m = _CODE_RE.search(line)
                if m:
                    found_code = m.group(1)
                    break

    if found_code is None:
        # Couldn't extract code; kill subprocess and report what we saw
        try:
            proc.terminate()
        except Exception:
            pass
        return {
            "error": "could not extract croc transfer code",
            "stdout_preview": "".join(buf)[:500],
        }

    # Detach the reader thread — we don't need the rest of croc's
    # output. The subprocess continues to run until receiver connects
    # or croc's internal timeout fires.
    def _drain() -> None:
        try:
            if proc.stdout:
                for _ in proc.stdout:
                    pass
        except Exception:
            pass
    threading.Thread(target=_drain, daemon=True).start()

    return {
        "transfer_code": found_code,
        "instructions":  f"On the other machine, run:   croc {found_code}",
        "source_path":   str(src),
        "pid":           proc.pid,
        "note":          (
            "Subprocess is running in the background. It'll exit once "
            "the receiver connects, or after croc's internal timeout."
        ),
    }


CROC_SEND_TOOL = Tool(
    name="croc_send",
    description=(
        "Prepare a file or directory for peer-to-peer transfer via "
        "croc. Returns a short transfer code (3 words) the recipient "
        "runs on their machine as `croc <code>` to pull the file. "
        "Encrypted in transit, works across NAT/firewalls via a "
        "relay. Use this when Ian wants to share a file with someone, "
        "or move files between his own machines. `code` is optional "
        "(supply if you want a specific phrase, otherwise croc "
        "generates one). Requires the croc CLI installed."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File or directory to send."},
            "code": {"type": "string", "description": "Optional custom 3-word code (croc generates one if omitted)."},
            "timeout_seconds": {"type": "integer", "description": "How long to wait for croc to print the code. Default 60."},
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    handler=_croc_send,
)


def register(registry) -> None:
    registry.register(CROC_SEND_TOOL)
