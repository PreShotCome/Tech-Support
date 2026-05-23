"""Conversation transcript logger.

Every agent session writes a markdown file to
    ~/.techsupport_agent/transcripts/YYYY-MM-DD-HHMMSS.md

Each turn (user input, assistant reply, tool calls + results) is
appended as soon as it happens, so even a crashed session leaves a
record. The agent calls TranscriptLogger.event() at the right points;
this module owns the file format and path.

Why this exists: the IDENTITY.md growth mechanism requires the human
to read the record. The record can't be read if it isn't written down.
Chat is otherwise ephemeral.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


def default_dir() -> Path:
    return Path.home() / ".techsupport_agent" / "transcripts"


class TranscriptLogger:
    def __init__(self, directory: Optional[Path] = None) -> None:
        self.directory = directory or default_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        self.path = self.directory / f"{ts}.md"
        self._write_header()

    # ------------------------------------------------------------------ write

    def event(self, kind: str, content: str, name: str | None = None) -> None:
        """kind in {'user', 'assistant', 'tool_call', 'tool_result',
        'note'}; `name` is the tool name when relevant."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if kind == "user":
            self._append(f"## you · {now}\n\n{content.rstrip()}\n\n")
        elif kind == "assistant":
            self._append(f"## agent · {now}\n\n{content.rstrip()}\n\n")
        elif kind == "tool_call":
            self._append(
                f"### tool_call · {name or '?'} · {now}\n\n"
                f"```\n{content.rstrip()}\n```\n\n"
            )
        elif kind == "tool_result":
            preview = content
            if len(preview) > 4000:
                preview = preview[:4000] + f"\n... [truncated; total {len(content)} chars]"
            self._append(
                f"### tool_result · {name or '?'} · {now}\n\n"
                f"```\n{preview.rstrip()}\n```\n\n"
            )
        elif kind == "note":
            self._append(f"> _{content.strip()}_\n\n")

    # ------------------------------------------------------------------ read

    @classmethod
    def list_transcripts(cls, directory: Optional[Path] = None) -> list[Path]:
        d = directory or default_dir()
        if not d.exists():
            return []
        return sorted(d.glob("*.md"))

    @classmethod
    def search(
        cls,
        query: str,
        directory: Optional[Path] = None,
        context_lines: int = 2,
        max_hits: int = 50,
    ) -> list[dict]:
        """Substring search across all transcripts. Returns a list of
        hit dicts: {file, line_number, line, context}."""
        d = directory or default_dir()
        if not d.exists() or not query:
            return []
        q = query.lower()
        hits: list[dict] = []
        for path in cls.list_transcripts(d):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines):
                if q in line.lower():
                    lo = max(0, i - context_lines)
                    hi = min(len(lines), i + context_lines + 1)
                    hits.append({
                        "file": path.name,
                        "line": i + 1,
                        "match": line,
                        "context": "\n".join(lines[lo:hi]),
                    })
                    if len(hits) >= max_hits:
                        return hits
        return hits

    # ------------------------------------------------------------------ internals

    def _write_header(self) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        header = (
            f"# Transcript · {now}\n\n"
            f"_Session started by `agent.cli`. Read by the human and used "
            f"to revise IDENTITY.md / the playbook / the skills, per the "
            f"explicit growth mechanism._\n\n"
        )
        self._append(header)

    def _append(self, text: str) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            # The transcript is best-effort; failing to write must not
            # crash the agent loop.
            pass
