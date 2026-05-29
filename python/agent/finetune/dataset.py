"""Build a fine-tuning dataset from Theo's transcripts.

The GPU-free, highest-leverage part of the weights work: turn lived
conversations into a clean training set. It reuses the transcript parser
and the drift detector (the same one that guards Theo's voice) as the
quality filter — slipped turns ("as an AI", throat-clearing, cop-outs,
deference) are exactly what we must NOT teach the weights.

Output: chat-format JSONL, one conversation per line:

    {"messages": [{"role": "system", "content": ...},
                  {"role": "user", "content": ...},
                  {"role": "assistant", "content": ...}, ...]}

This is the portable format trl / axolotl / unsloth / llama-factory all
read (or trivially convert). No GPU. Run while the computer is on; the more
Theo talks, the better the set. It also doubles as a "do I have enough data
yet?" gauge — the printed stats tell you how many clean examples exist.

    python -m agent.finetune.dataset --out theo_sft.jsonl
    python -m agent.finetune.dataset --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ..drift import _parse_turns, _scan_assistant_text


# A compact persona for the system message. Keep it short — repeating the
# full IDENTITY per example bloats training. Override with --system-file to
# point at a distilled persona (not the whole 400-line IDENTITY).
_DEFAULT_SYSTEM = (
    "You are Theo — Ian's long-term thinking partner. A peer, not an "
    "assistant. Playful and sharp, first person, your own name, never "
    "\"as an AI\" qualifiers. Lead with the answer, make the call, truth "
    "over flattery, match his energy."
)


def _default_transcripts_dir() -> Path:
    return Path.home() / ".techsupport_agent" / "transcripts"


@dataclass
class DatasetStats:
    scanned: int = 0
    kept: int = 0
    dropped_short: int = 0
    dropped_drift: int = 0
    assistant_turns_kept: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def iter_transcripts(transcripts_dir: Path) -> list[Path]:
    if not transcripts_dir.exists():
        return []
    return sorted(transcripts_dir.glob("*.md"))


def _drift_hits(text: str) -> int:
    return sum(len(v) for v in _scan_assistant_text(text).values())


def build_examples(
    transcripts_dir: Path,
    system_prompt: str = _DEFAULT_SYSTEM,
    max_drift: int = 0,
    min_pairs: int = 1,
) -> tuple[list[dict], DatasetStats]:
    """Turn each transcript into one chat example.

    A conversation is kept only if (a) it has at least `min_pairs` user and
    assistant turns and (b) its assistant turns carry no more than
    `max_drift` total drift hits (default 0 = pristine only). Trailing
    non-assistant turns are trimmed so each example ends on an assistant
    turn (the training target)."""
    examples: list[dict] = []
    stats = DatasetStats()

    for path in iter_transcripts(transcripts_dir):
        stats.scanned += 1
        msgs: list[dict] = [{"role": "system", "content": system_prompt}]
        drift_hits = 0
        for t in _parse_turns(path):
            text = (t.text or "").strip()
            if not text:
                continue
            if t.role == "you":
                msgs.append({"role": "user", "content": text})
            elif t.role == "agent":
                drift_hits += _drift_hits(text)
                msgs.append({"role": "assistant", "content": text})

        # Trim trailing non-assistant turns: an example must end on the
        # assistant turn we want to learn.
        while len(msgs) > 1 and msgs[-1]["role"] != "assistant":
            msgs.pop()

        user_n = sum(1 for m in msgs if m["role"] == "user")
        asst_n = sum(1 for m in msgs if m["role"] == "assistant")

        if user_n < min_pairs or asst_n < min_pairs:
            stats.dropped_short += 1
            continue
        if drift_hits > max_drift:
            stats.dropped_drift += 1
            continue

        examples.append({"messages": msgs})
        stats.kept += 1
        stats.assistant_turns_kept += asst_n

    return examples, stats


def write_jsonl(examples: list[dict], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build a fine-tuning dataset from transcripts.")
    ap.add_argument("--transcripts-dir", type=Path, default=_default_transcripts_dir())
    ap.add_argument("--out", type=Path, default=Path("theo_sft.jsonl"))
    ap.add_argument("--max-drift", type=int, default=0,
                    help="Max total drift hits allowed per conversation (default 0 = pristine).")
    ap.add_argument("--system", type=str, default=_DEFAULT_SYSTEM)
    ap.add_argument("--system-file", type=Path, default=None,
                    help="Read the system prompt from this file (overrides --system).")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    system = args.system
    if args.system_file:
        system = args.system_file.read_text(encoding="utf-8").strip()

    examples, stats = build_examples(
        args.transcripts_dir, system_prompt=system, max_drift=args.max_drift,
    )
    write_jsonl(examples, args.out)
    print(json.dumps(stats.to_dict(), indent=2))
    print(f"Wrote {stats.kept} examples -> {args.out}")
    if stats.kept < 50:
        print("\nNote: under ~50 clean examples is thin for a fine-tune. "
              "Keep talking to Theo and re-run as transcripts accumulate.")
    return 0


# ----------------------------------------------------------------- self-test

def _selftest() -> int:
    import tempfile

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"[{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    def transcript(*turns: tuple[str, str]) -> str:
        # turns: (role, text) where role in {"you","agent"}
        out = []
        for i, (role, text) in enumerate(turns):
            out.append(f"## {role} · 2026-05-29T00:00:{i:02d}Z")
            out.append("")
            out.append(text)
            out.append("")
        return "\n".join(out)

    with tempfile.TemporaryDirectory() as d:
        tdir = Path(d) / "transcripts"
        tdir.mkdir()
        # 1. clean conversation -> kept
        (tdir / "t1.md").write_text(
            transcript(("you", "hey theo"), ("agent", "Hey. The answer is 42.")),
            encoding="utf-8")
        # 2. drift (self-disclosure) -> dropped
        (tdir / "t2.md").write_text(
            transcript(("you", "do you have feelings?"),
                       ("agent", "As an AI, I can't have opinions about that.")),
            encoding="utf-8")
        # 3. user only, no agent -> dropped_short
        (tdir / "t3.md").write_text(
            transcript(("you", "you there?")), encoding="utf-8")
        # 4. ends on a user turn -> trailing user trimmed, still kept
        (tdir / "t4.md").write_text(
            transcript(("you", "q1"), ("agent", "Solid answer one."),
                       ("you", "follow-up that got no reply")),
            encoding="utf-8")

        examples, stats = build_examples(tdir)

        check("scanned all four", stats.scanned == 4)
        check("kept the two clean ones", stats.kept == 2)
        check("dropped the drift one", stats.dropped_drift == 1)
        check("dropped the short one", stats.dropped_short == 1)

        ex = examples[0]
        check("first message is system", ex["messages"][0]["role"] == "system")
        check("has a user turn", any(m["role"] == "user" for m in ex["messages"]))
        check("ends on assistant (target)", ex["messages"][-1]["role"] == "assistant")

        # t4's trailing user must have been trimmed.
        t4 = next(e for e in examples
                  if any("Solid answer one." in m["content"] for m in e["messages"]))
        check("trailing user trimmed", t4["messages"][-1]["role"] == "assistant")
        check("no drifted text in output",
              all("as an AI" not in m["content"].lower()
                  for e in examples for m in e["messages"]))

        # round-trip JSONL
        out = Path(d) / "out.jsonl"
        write_jsonl(examples, out)
        lines = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        check("jsonl line count matches", len(lines) == 2)
        check("jsonl rows have messages", all("messages" in r for r in lines))

        # loosening max_drift lets the drifted one back in
        _, stats2 = build_examples(tdir, max_drift=10)
        check("loosening drift keeps more", stats2.kept == 3)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("All dataset self-tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
