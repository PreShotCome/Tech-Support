"""Code tools — give Theo hands on Ian's filesystem and shell.

read_file, write_file, edit_file, list_dir, grep, run_command. Same shape
as Claude Code's basic tools, scoped for Theo running on Ian's machine.

Writes auto-apply (Ian asked for Theo to actually code, not propose).
Every invocation is appended to ~/.techsupport_agent/code_log.jsonl as an
audit trail. A small denylist catches obviously destructive shell
commands; the real guard is that Theo's brain is Claude, which won't
casually do harm.

If you ever want to make these tools opt-in instead of live, remove the
('code', code_tools) line from tools/_all.py.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from .base import Tool


_LOG_PATH = Path.home() / ".techsupport_agent" / "code_log.jsonl"

# Soft denylist on shell commands. Catches accidents -- a determined model
# could trivially work around it (e.g., split tokens). Audit log is the real
# accountability surface.
_DESTRUCTIVE_RE = re.compile(
    r"(rm\s+-rf?\s+[/~]|"          # rm -rf / or ~
    r"\bmkfs\b|"                    # mkfs.anything
    r"dd\s+of=/dev/|"               # dd to a device
    r">\s*/dev/sd|"                 # redirect to a disk
    r"\bshutdown\b|\breboot\b|\bhalt\b|"
    r":\(\)\s*\{|"                  # bash fork bomb
    r"del\s+/[fsq]\s+\w?:?\\|"      # Windows recursive force delete on a drive root
    r"format\s+[a-zA-Z]:)",         # Windows format
    re.IGNORECASE,
)


def _log(op: str, payload: dict) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "op": op, **payload}) + "\n")
    except Exception:
        pass  # logging must never break a tool call


# ----------------------------------------------------------------- handlers

def _read_file(path: str, max_bytes: int = 100_000, offset_bytes: int = 0) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": f"no such file: {p}"}
    if not p.is_file():
        return {"error": f"not a file: {p}"}
    size = p.stat().st_size
    with p.open("rb") as f:
        f.seek(max(0, offset_bytes))
        data = f.read(max_bytes)
    truncated = (offset_bytes + len(data)) < size
    text = data.decode("utf-8", errors="replace")
    _log("read_file", {"path": str(p), "bytes": len(data), "truncated": truncated})
    return {"path": str(p), "size": size, "read_bytes": len(data),
            "offset": offset_bytes, "truncated": truncated, "content": text}


def _write_file(path: str, content: str, create_dirs: bool = True) -> dict:
    p = Path(path).expanduser()
    if create_dirs:
        p.parent.mkdir(parents=True, exist_ok=True)
    bytes_written = p.write_text(content, encoding="utf-8")
    _log("write_file", {"path": str(p), "bytes": bytes_written})
    return {"path": str(p), "bytes_written": bytes_written}


def _edit_file(path: str, old_string: str, new_string: str, count: int = 1) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": f"no such file: {p}"}
    text = p.read_text(encoding="utf-8")
    occurrences = text.count(old_string)
    if occurrences == 0:
        return {"error": "old_string not found in file"}
    if count == -1:
        new_text = text.replace(old_string, new_string)
        replaced = occurrences
    else:
        if occurrences > count >= 0:
            return {"error": f"old_string occurs {occurrences} times but count={count}; "
                             f"pass count=-1 to replace all, or make old_string unique"}
        new_text = text.replace(old_string, new_string, count)
        replaced = min(count, occurrences)
    p.write_text(new_text, encoding="utf-8")
    _log("edit_file", {"path": str(p), "replaced": replaced})
    return {"path": str(p), "replaced": replaced}


def _list_dir(path: str = ".", pattern: str = "*", max_entries: int = 200) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": f"no such path: {p}"}
    if not p.is_dir():
        return {"error": f"not a directory: {p}"}
    entries = []
    for e in sorted(p.glob(pattern)):
        if len(entries) >= max_entries:
            break
        entries.append({
            "name": e.name,
            "type": "dir" if e.is_dir() else "file",
            "size": e.stat().st_size if e.is_file() else None,
        })
    return {"path": str(p), "count": len(entries),
            "entries": entries,
            "truncated": len(entries) == max_entries}


def _grep(pattern: str, path: str = ".", recursive: bool = True,
          max_matches: int = 100, glob: str = "*") -> dict:
    p = Path(path).expanduser()
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return {"error": f"bad regex: {e}"}
    matches = []
    files = p.rglob(glob) if recursive else p.glob(glob)
    for f in files:
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                matches.append({"file": str(f), "line": i, "text": line[:300]})
                if len(matches) >= max_matches:
                    return {"count": len(matches), "matches": matches, "truncated": True}
    return {"count": len(matches), "matches": matches, "truncated": False}


def _run_command(command: str, cwd: str = None, timeout: float = 120.0) -> dict:
    if _DESTRUCTIVE_RE.search(command):
        _log("run_command", {"command": command, "denied": True})
        return {"error": "command matches destructive denylist; refusing",
                "command": command}
    try:
        result = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        _log("run_command", {"command": command, "timeout": True})
        return {"error": f"timed out after {timeout}s", "command": command}
    stdout = (result.stdout or "")[:32_000]
    stderr = (result.stderr or "")[:8_000]
    _log("run_command", {"command": command, "rc": result.returncode,
                         "stdout_bytes": len(stdout), "stderr_bytes": len(stderr)})
    return {"command": command, "cwd": cwd, "returncode": result.returncode,
            "stdout": stdout, "stderr": stderr}


# -------------------------------------------------------------------- tools

READ_FILE_TOOL = Tool(
    name="read_file",
    description=(
        "Read a file from the filesystem. Returns content (UTF-8 decoded; "
        "binary is best-effort). Truncates at max_bytes; use offset_bytes to "
        "page through large files."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or ~-expanded path."},
            "max_bytes": {"type": "integer", "description": "Default 100000."},
            "offset_bytes": {"type": "integer", "description": "Byte offset to start at."},
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    handler=_read_file,
)

WRITE_FILE_TOOL = Tool(
    name="write_file",
    description=(
        "Create or overwrite a file with the given content (UTF-8). Creates "
        "parent directories by default. Auto-applies; use intentionally."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "create_dirs": {"type": "boolean", "description": "Default true."},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    },
    handler=_write_file,
)

EDIT_FILE_TOOL = Tool(
    name="edit_file",
    description=(
        "Find-and-replace edit a file. By default replaces the first occurrence "
        "and errors if old_string is not unique (Claude-Code style). Pass "
        "count=-1 to replace all occurrences. Auto-applies."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
            "count": {"type": "integer", "description": "Default 1; -1 for all."},
        },
        "required": ["path", "old_string", "new_string"],
        "additionalProperties": False,
    },
    handler=_edit_file,
)

LIST_DIR_TOOL = Tool(
    name="list_dir",
    description="List directory entries, optionally filtered by a glob pattern.",
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Default current dir."},
            "pattern": {"type": "string", "description": "Glob (default '*')."},
            "max_entries": {"type": "integer", "description": "Default 200."},
        },
        "additionalProperties": False,
    },
    handler=_list_dir,
)

GREP_TOOL = Tool(
    name="grep",
    description=(
        "Search files for a regex pattern. Returns matching {file, line, text}. "
        "Recursive by default; restrict with glob (e.g. '*.py')."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Python regex."},
            "path": {"type": "string", "description": "Default current dir."},
            "recursive": {"type": "boolean", "description": "Default true."},
            "max_matches": {"type": "integer", "description": "Default 100."},
            "glob": {"type": "string", "description": "File glob (default '*')."},
        },
        "required": ["pattern"],
        "additionalProperties": False,
    },
    handler=_grep,
)

RUN_COMMAND_TOOL = Tool(
    name="run_command",
    description=(
        "Execute a shell command. Returns {returncode, stdout, stderr}. Uses "
        "the OS default shell (cmd on Windows, sh on POSIX); prefix with "
        "'powershell -Command' to run PowerShell on Windows. A small denylist "
        "refuses obviously destructive patterns (rm -rf /, mkfs, format C:, "
        "shutdown). Output truncated; default 120s timeout."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string", "description": "Working directory."},
            "timeout": {"type": "number", "description": "Seconds (default 120)."},
        },
        "required": ["command"],
        "additionalProperties": False,
    },
    handler=_run_command,
)


def register(registry) -> None:
    for t in (READ_FILE_TOOL, WRITE_FILE_TOOL, EDIT_FILE_TOOL,
              LIST_DIR_TOOL, GREP_TOOL, RUN_COMMAND_TOOL):
        registry.register(t)
