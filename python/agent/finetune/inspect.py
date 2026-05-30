"""Diagnose why transcripts get dropped from the dataset build.

Prints how many transcripts have actual agent prose, and for those that don't,
distinguishes "transcript has no `## agent` header at all" from "agent header
exists but it stripped to empty (tool calls only)". That tells you whether the
gap is the transcript-logger missing agent headers (a bug to fix), Theo
genuinely never writing prose in those sessions (just more conversations
needed), or something else.

Run from python/:

    python -m agent.finetune.inspect
"""
from __future__ import annotations

import os
from pathlib import Path

from .dataset import _iter_turns, _drift_hits, _default_transcripts_dir


def main() -> int:
    td = Path(os.environ.get("THEO_TRANSCRIPTS_DIR", str(_default_transcripts_dir())))
    if not td.exists():
        print(f"No transcripts dir at {td}")
        return 1

    eligible: list[tuple[str, int, int]] = []         # has both user + agent prose
    drifty: list[tuple[str, int]] = []                # eligible but too many drift hits
    no_agent_header: list[str] = []                   # no `## agent` line at all
    agent_header_no_prose: list[tuple[str, int]] = [] # `## agent` exists but stripped empty
    no_user_prose: list[str] = []                     # rare; user wrote nothing

    for p in sorted(td.glob("*.md")):
        raw = p.read_text(encoding="utf-8", errors="replace")
        # Count raw `## agent` headers (with the middle-dot separator). Use a
        # tolerant match in case the formatter ever drifts.
        agent_header_count = sum(
            1 for line in raw.splitlines()
            if line.startswith("## agent ")
        )
        turns = list(_iter_turns(p))
        you_text = [t for r, t, _ in turns if r == "you" and t.strip()]
        agent_text = [t for r, t, _ in turns if r == "agent" and t.strip()]
        drift_hits = sum(_drift_hits(t) for t in agent_text)

        if you_text and agent_text:
            if drift_hits > 5:
                drifty.append((p.name, drift_hits))
            else:
                eligible.append((p.name, len(you_text), len(agent_text)))
        elif not you_text:
            no_user_prose.append(p.name)
        elif agent_header_count == 0:
            no_agent_header.append(p.name)
        else:
            agent_header_no_prose.append((p.name, agent_header_count))

    total = (len(eligible) + len(drifty) + len(no_agent_header)
             + len(agent_header_no_prose) + len(no_user_prose))
    print(f"Transcripts scanned: {total}\n")
    print(f"  eligible (would train on these):       {len(eligible)}")
    print(f"  too drifty (kept-then-cut):            {len(drifty)}")
    print(f"  NO `## agent` header at all:           {len(no_agent_header)}")
    print(f"  has `## agent` but stripped to empty:  {len(agent_header_no_prose)}")
    print(f"  no user prose (weird):                 {len(no_user_prose)}")
    print()

    def sample(label: str, items: list, n: int = 5) -> None:
        if not items:
            return
        print(f"Sample {label} (first {min(n, len(items))}):")
        for it in items[:n]:
            print(f"  {it}")
        print()

    sample("NO `## agent` header", no_agent_header)
    sample("`## agent` exists but stripped to empty", agent_header_no_prose)
    sample("no user prose", no_user_prose)
    sample("eligible", eligible, n=3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
