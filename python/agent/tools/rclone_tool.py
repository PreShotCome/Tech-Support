"""rclone tool — sync files to/from 50+ cloud providers.

rclone (https://rclone.org) is the gold-standard CLI for moving data
between local disk and cloud storage (S3, GCS, Dropbox, OneDrive,
Google Drive, B2, SFTP, FTP, WebDAV, and dozens more). One config
file, one binary, every backend.

Setup:
  - Install: `winget install Rclone.Rclone` (Windows),
    `brew install rclone` (macOS), `apt install rclone` (Linux).
  - Configure remotes once with `rclone config`. Each named remote
    becomes addressable as `name:path`.

High-value uses for Theo:
  - Back up ~/.techsupport_agent/ (transcripts, notes, models)
    nightly to a cloud bucket. Cheap insurance.
  - Sync transcripts between PCs if Ian works from multiple machines.
  - Pull docs/data from cloud into the local workspace.

Safety: `sync` is destructive (mirrors source to dest, DELETING files
in dest that aren't in source). The tool requires `confirm=True` for
sync; copy is the default safe op.

Reference docs: docs/research/rclone/"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from .base import Tool


def _check_rclone() -> dict[str, Any] | None:
    if not shutil.which("rclone"):
        return {
            "error": "rclone not installed",
            "install": (
                "Windows: winget install Rclone.Rclone | "
                "macOS: brew install rclone | "
                "Linux: apt install rclone | "
                "Configure remotes once with: rclone config"
            ),
        }
    return None


def _rclone_op(operation: str,
               source: str | None = None,
               dest: str | None = None,
               path: str | None = None,
               remote: str | None = None,
               dry_run: bool = False,
               confirm_sync: bool = False) -> dict[str, Any]:
    """Run an rclone operation. Operations:
      - listremotes: list configured remotes
      - ls:          list contents of a remote path (uses lsjson)
      - copy:        copy source -> dest (non-destructive)
      - sync:        sync source -> dest (DESTRUCTIVE, requires confirm_sync=True)
      - size:        size of a remote path
      - about:       quota info for a remote
    """
    err = _check_rclone()
    if err:
        return err

    op = operation.strip().lower()
    base = ["rclone"]
    if dry_run:
        base.append("--dry-run")

    if op == "listremotes":
        cmd = base + ["listremotes"]
    elif op == "ls":
        if not path:
            return {"error": "ls requires `path` (e.g. 'mydrive:backups')"}
        cmd = base + ["lsjson", path]
    elif op == "copy":
        if not source or not dest:
            return {"error": "copy requires `source` and `dest`"}
        cmd = base + ["copy", source, dest, "--progress=false"]
    elif op == "sync":
        if not source or not dest:
            return {"error": "sync requires `source` and `dest`"}
        if not confirm_sync and not dry_run:
            return {
                "error": "sync is destructive (deletes files in dest not in source)",
                "fix": "Re-run with confirm_sync=True, OR with dry_run=True first to preview.",
            }
        cmd = base + ["sync", source, dest, "--progress=false"]
    elif op == "size":
        if not path:
            return {"error": "size requires `path`"}
        cmd = base + ["size", path, "--json"]
    elif op == "about":
        if not remote:
            return {"error": "about requires `remote` (e.g. 'mydrive:')"}
        cmd = base + ["about", remote, "--json"]
    else:
        return {
            "error": f"unknown operation {operation!r}",
            "supported": ["listremotes", "ls", "copy", "sync", "size", "about"],
        }

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"error": "rclone timed out after 5min"}

    if proc.returncode != 0:
        return {
            "error": f"rclone exit {proc.returncode}",
            "stderr": proc.stderr[:500] if proc.stderr else "",
            "cmd": " ".join(cmd),
        }

    # Try JSON-parse where appropriate; fall back to raw text
    out = proc.stdout or ""
    parsed: Any = None
    if op in {"ls", "size", "about"}:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = out.strip()
    elif op == "listremotes":
        parsed = [line.strip() for line in out.splitlines() if line.strip()]
    else:
        parsed = out.strip()[:2000] or "ok"

    return {
        "operation": op,
        "dry_run":   dry_run,
        "result":    parsed,
    }


RCLONE_OP_TOOL = Tool(
    name="rclone_op",
    description=(
        "File sync operations via rclone — moves data between local "
        "disk and 50+ cloud providers (S3, Dropbox, OneDrive, Google "
        "Drive, B2, SFTP, etc.). Use this when Ian asks to back up, "
        "sync, list, or check the size of files across cloud storage.\n"
        "Operations:\n"
        "  - listremotes: enumerate configured remotes (no args)\n"
        "  - ls:          list a path (set `path`, e.g. 'mydrive:backups')\n"
        "  - copy:        copy source->dest (set `source`, `dest`; non-destructive)\n"
        "  - sync:        mirror source->dest (DESTRUCTIVE — requires confirm_sync=True)\n"
        "  - size:        size of a path (set `path`)\n"
        "  - about:       quota info (set `remote`, e.g. 'mydrive:')\n"
        "Use `dry_run=true` to preview without executing. Requires "
        "rclone installed and remotes configured via `rclone config`."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "operation": {"type": "string", "description": "One of: listremotes / ls / copy / sync / size / about."},
            "source": {"type": "string", "description": "Source path (for copy / sync)."},
            "dest":   {"type": "string", "description": "Dest path (for copy / sync)."},
            "path":   {"type": "string", "description": "Target path (for ls / size)."},
            "remote": {"type": "string", "description": "Remote name with trailing colon (for about)."},
            "dry_run": {"type": "boolean", "description": "Preview without executing. Default false."},
            "confirm_sync": {"type": "boolean", "description": "Required true for destructive sync. Default false."},
        },
        "required": ["operation"],
        "additionalProperties": False,
    },
    handler=_rclone_op,
)


def register(registry) -> None:
    registry.register(RCLONE_OP_TOOL)
