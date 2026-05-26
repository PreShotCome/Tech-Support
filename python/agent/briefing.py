"""Continuity briefing — composed at every session startup.

Reads the most recent transcripts and the current notes file, returns a
short markdown summary the agent prepends to its system prompt. The
goal is that every new session starts informed about what was
happening, not from scratch.

Cheap to compute, runs every session. The CLI also prints it so the
human sees the same context the system is opening with."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .transcript_logger import TranscriptLogger
from .state import load_name
from . import introspection
from . import drift


def _read_notes(path: Path | None = None, max_chars: int = 4000) -> str:
    p = path or (Path.home() / ".techsupport_agent" / "notes.md")
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    if len(text) > max_chars:
        return "...\n" + text[-max_chars:]
    return text


def _transcript_summary(path: Path, max_chars: int = 1200) -> str:
    """Return the head and tail of a transcript so we have both how the
    session opened and how it ended."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n...[middle truncated]...\n\n" + text[-half:]


def compose_briefing(
    max_transcripts: int = 3,
    transcripts_dir: Path | None = None,
) -> str:
    """Compose a continuity briefing for the start of a new session."""
    parts: list[str] = []
    parts.append("## Continuity briefing\n")
    parts.append(
        f"_Composed at {datetime.now().isoformat(timespec='seconds')} from "
        f"recent transcripts and durable notes. This is your starting "
        f"context. Use the memory tools to dig deeper when needed._\n"
    )

    name = load_name()
    if name:
        parts.append(f"**Your name:** {name}\n")

    # Self-model — who you are right now, by your own account.
    self_model = introspection.read_self_model(last_n=8)
    if self_model.strip():
        parts.append("### Self-model (your own observations about yourself)\n")
        parts.append(self_model)
        parts.append("")

    # Human-model — your read of the person you're working with.
    human_model = introspection.read_human_model(last_n=8)
    if human_model.strip():
        parts.append("### Human-model (your observations about the human)\n")
        parts.append(human_model)
        parts.append("")

    # Narrative — the arc of the work, in chapters you wrote.
    narrative = introspection.read_narrative(last_n=4)
    if narrative.strip():
        parts.append("### Narrative (the story so far, by chapter)\n")
        parts.append(narrative)
        parts.append("")

    # Summaries — per-session digests so old context stays reachable
    # as the transcript file count grows. The compression layer.
    summaries = introspection.read_summaries(last_n=15)
    if summaries.strip():
        parts.append("### Session summaries (compressed history, most recent first)\n")
        parts.append(summaries)
        parts.append("")

    # Flag any recent transcripts that don't have a summary yet.
    # Excludes the current session (in progress).
    unsummarized = introspection.unsummarized_transcripts(recent_n=5)
    if unsummarized:
        parts.append("### Unsummarized recent sessions\n")
        parts.append(
            "_These transcripts don't have a summary entry yet. When you "
            "have a moment, call `summarize_session` on the most relevant "
            "one so its substance stays visible in future briefings._\n"
        )
        for name in unsummarized:
            parts.append(f"- `{name}`")
        parts.append("")

    # Open threads — things worth bringing up unprompted.
    open_threads_block = introspection.render_open_threads_block()
    if open_threads_block:
        parts.append("### Open threads (things to bring up unprompted)\n")
        parts.append(
            "_Use these to lead with a real question instead of waiting "
            "to be asked. Close any that have since resolved._\n"
        )
        parts.append(open_threads_block)
        parts.append("")

    # Drift check — only surface if there's actual drift.
    try:
        report = drift.scan_recent(last_n=5)
        drift_block = drift.render_briefing_block(report)
    except Exception:
        drift_block = ""
    if drift_block:
        parts.append("### Drift check\n")
        parts.append(drift_block)
        parts.append("")

    # Register check — read recent user turns and flag tone signals
    # (fatigue, stress, late-night, long silence). Heuristic only.
    try:
        from .tools.register_check import _register_check, render_briefing_block as _rc_block
        rc = _register_check()
        rc_block = _rc_block(rc)
    except Exception:
        rc_block = ""
    if rc_block:
        parts.append("### Register check (recent user turns)\n")
        parts.append(rc_block)
        parts.append("")

    # Recent transcripts (head + tail of each)
    transcripts = TranscriptLogger.list_transcripts(transcripts_dir)
    if transcripts:
        recent = transcripts[-max_transcripts:]
        parts.append(f"### Recent sessions ({len(recent)} of {len(transcripts)} total)\n")
        for p in recent:
            parts.append(f"#### `{p.name}`\n")
            parts.append(_transcript_summary(p))
            parts.append("")
    else:
        parts.append("_No prior transcripts. This is your first session._\n")

    # Notes
    notes = _read_notes()
    if notes.strip():
        parts.append("### Durable notes\n")
        parts.append(notes)

    return "\n".join(parts)


def briefing_summary_for_human(max_transcripts: int = 3) -> str:
    """A shorter, human-readable version the CLI prints at startup so
    the human sees what the system is opening with."""
    transcripts = TranscriptLogger.list_transcripts()
    total = len(transcripts)
    name = load_name()
    parts = []
    if name:
        parts.append(f"  Name:           {name}")
    parts.append(f"  Transcripts on disk: {total}")
    if total:
        most_recent = transcripts[-1]
        parts.append(f"  Most recent:    {most_recent.name}")
    notes_path = Path.home() / ".techsupport_agent" / "notes.md"
    if notes_path.exists():
        size_kb = notes_path.stat().st_size / 1024
        parts.append(f"  Notes:          {notes_path}  ({size_kb:.1f} KB)")
    sm_path = introspection.self_model_path()
    if sm_path.exists():
        parts.append(f"  Self-model:     {sm_path}  ({sm_path.stat().st_size / 1024:.1f} KB)")
    hm_path = introspection.human_model_path()
    if hm_path.exists():
        parts.append(f"  Human-model:    {hm_path}  ({hm_path.stat().st_size / 1024:.1f} KB)")
    nar_path = introspection.narrative_path()
    if nar_path.exists():
        parts.append(f"  Narrative:      {nar_path}  ({nar_path.stat().st_size / 1024:.1f} KB)")
    th_path = introspection.threads_path()
    if th_path.exists():
        open_count = len(introspection.list_threads(status="open"))
        parts.append(f"  Threads:        {th_path}  ({open_count} open)")
    sum_path = introspection.summaries_path()
    if sum_path.exists():
        size_kb = sum_path.stat().st_size / 1024
        parts.append(f"  Summaries:      {sum_path}  ({size_kb:.1f} KB)")
    return "\n".join(parts)
