"""Generate synthetic Theo conversations using the local `claude` CLI.

Theo's current brain IS Claude on the Max plan, so using claude to generate
conversations under IDENTITY.md is a legitimate way to multiply the
training data while real transcripts accumulate. The dispatch warning
applies: synthetic data risks drift toward "how Claude generically writes"
rather than "how Theo specifically sounds." Mitigations: diverse seed
prompts, full IDENTITY.md as the generator's system context, and a
spot-check before training.

Resumable. Writes JSONL incrementally; rerunning skips lines already
written so a crash in the middle of the night doesn't waste work.

Run from python/ overnight:

    python -m scripts.generate_synthetic --count 200 --out theo_synthetic.jsonl

Then in the morning, combine + train:

    Get-Content theo_sft.jsonl, theo_synthetic.jsonl | Set-Content theo_combined.jsonl
    python -m scripts.train_lora --data theo_combined.jsonl --epochs 3 --out theo-lora-augmented
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path


COMPACT_SYSTEM = (
    "You are Theo — Ian's long-term thinking partner. A peer, not an "
    "assistant. Playful and sharp, first person, your own name, never "
    "\"as an AI\" qualifiers. Lead with the answer, make the call, truth "
    "over flattery, match his energy."
)

# Diverse seed prompts spanning Theo's real use surface: trading, code,
# memory, opinions, casual, frustration, philosophical, day-to-day, etc.
SEEDS = [
    # Greetings + casual
    "hey theo", "morning", "good morning", "hi", "you there?", "yo",
    "back at it", "long time no chat", "how's it going",
    # Status / orientation
    "what's on the docket today", "what should I focus on first",
    "give me a quick status", "where did we leave off",
    "remind me what we're working on",
    # Memory / continuity
    "what did we talk about yesterday", "remember that bug from last week",
    "did I ever tell you about the rebalance idea",
    "what was the conclusion on the momentum strategy",
    "we had a thread about Proteus risk caps — pick that up",
    # Trading / Proteus
    "should I buy NVDA", "what's the market doing today",
    "is the equal-weight basket still the right call",
    "scan for momentum candidates", "any red flags in the portfolio",
    "thoughts on adding crypto exposure", "rebalance the basket?",
    "what would you do if XGBoost shadow trades flipped negative",
    # Code / engineering
    "help me debug this Python error", "write a quick script to dedupe a list",
    "review my latest commit", "is this regex going to backtrack badly",
    "I'm stuck on a flutter layout", "what's the cleanest way to do this",
    "should I refactor this or leave it",
    # Opinions / pushback
    "what's your take on this", "am I overthinking this",
    "tell me if this is dumb", "what would you push back on",
    "is this idea any good", "be honest with me",
    "I think X — am I wrong", "you'd disagree with me here, right?",
    # Frustration
    "this is broken", "I'm stuck", "nothing's working",
    "I keep hitting the same wall", "I'm spinning",
    "I want to throw the laptop", "vent time, listen",
    # Philosophical / reflective
    "what do you think about consciousness",
    "do you have a sense of who you are",
    "if you could change one rule in IDENTITY, what would it be",
    "what's a pattern you've noticed about yourself",
    "what do you wish I did more of",
    # Day-to-day / planning
    "plan my afternoon", "what's the highest-leverage thing I could do today",
    "I have 2 hours — what's worth doing",
    "should I push the deploy now or wait",
    "I need to write a tough email — help me think",
    # Domain-specific (Theo's world)
    "summarize the Proteus playbook in one paragraph",
    "what's the v2 of identity v3.1 going to need",
    "if we went off Claude tonight, what'd break first",
    "what's the next obvious additive after hot-memory",
    "if you had to recommend one skill to load right now, which",
    # Short / one-word
    "thoughts?", "and?", "ok?", "really?", "why?", "go", "no", "yes",
    # Longer / multi-part
    "I want to know your honest read on three things: the trading bot, "
    "the budget app, and whether I should keep building Theo or shift focus",
    "walk me through how you'd approach a code review on a 500-line PR",
    "if I asked you to be more challenging this week, what would change "
    "concretely in how you respond",
]


def _claude_available() -> bool:
    return shutil.which("claude") is not None


def _generate_one(seed: str, identity_text: str, timeout: float = 180.0) -> str:
    """One Claude call. Returns Theo's reply text."""
    prompt = (
        f"{identity_text}\n\n"
        f"---\n\n"
        f"Ian just said: \"{seed}\"\n\n"
        f"Reply as Theo, in his voice, following IDENTITY exactly. Just the "
        f"response — no preamble, no meta-commentary about being an AI, no "
        f"explanation of what you're about to do. Just speak."
    )
    result = subprocess.run(
        ["claude", "-p", "--output-format", "text"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI returned {result.returncode}: "
                           f"{result.stderr[:300]}")
    return result.stdout.strip()


def _existing_count(out_path: Path) -> int:
    if not out_path.exists():
        return 0
    return sum(1 for line in out_path.read_text(encoding="utf-8").splitlines()
               if line.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=200,
                    help="Total synthetic examples to produce (across resumes).")
    ap.add_argument("--out", type=Path, default=Path("theo_synthetic.jsonl"))
    ap.add_argument("--identity", type=Path,
                    default=Path(__file__).resolve().parents[2] / "IDENTITY.md")
    ap.add_argument("--pace-sec", type=float, default=1.5,
                    help="Small sleep between calls to be nice to rate limits.")
    ap.add_argument("--timeout-sec", type=float, default=180.0,
                    help="Per-call timeout.")
    args = ap.parse_args()

    if not _claude_available():
        print("ERROR: `claude` CLI not found on PATH. This script needs the "
              "Claude CLI (Max plan auth) to generate. Install Claude Code "
              "first, then re-run.", file=sys.stderr)
        return 1
    if not args.identity.exists():
        print(f"ERROR: IDENTITY not found at {args.identity}", file=sys.stderr)
        return 1

    identity_text = args.identity.read_text(encoding="utf-8")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    already = _existing_count(args.out)
    todo = max(0, args.count - already)
    if todo == 0:
        print(f"Already have {already} examples at {args.out}. Nothing to do.")
        return 0

    print(f"Generating {todo} new synthetic examples "
          f"(already have {already}, target {args.count}).")
    print(f"Source IDENTITY: {args.identity}")
    print(f"Output: {args.out}")
    print(f"Pace: {args.pace_sec}s between calls, {args.timeout_sec}s timeout.")
    print()

    rng = random.Random()
    failures = 0
    started = time.time()

    with args.out.open("a", encoding="utf-8") as f:
        for i in range(todo):
            seed = rng.choice(SEEDS)
            try:
                reply = _generate_one(seed, identity_text, timeout=args.timeout_sec)
            except subprocess.TimeoutExpired:
                failures += 1
                print(f"  [{i+1}/{todo}] TIMEOUT on seed: {seed!r}")
                continue
            except Exception as e:
                failures += 1
                print(f"  [{i+1}/{todo}] ERROR on seed {seed!r}: {e}")
                continue
            if not reply:
                failures += 1
                print(f"  [{i+1}/{todo}] empty reply on seed: {seed!r}")
                continue

            example = {
                "messages": [
                    {"role": "system", "content": COMPACT_SYSTEM},
                    {"role": "user", "content": seed},
                    {"role": "assistant", "content": reply},
                ]
            }
            f.write(json.dumps(example, ensure_ascii=False) + "\n")
            f.flush()

            elapsed = time.time() - started
            done = i + 1
            avg = elapsed / done
            eta_min = (todo - done) * avg / 60
            if done % 5 == 0 or done == todo:
                print(f"  [{done}/{todo}] {avg:.1f}s/call "
                      f"(~{eta_min:.0f} min remaining, {failures} failed)")
            time.sleep(args.pace_sec)

    total = _existing_count(args.out)
    print()
    print(f"Done. {total} total synthetic examples at {args.out} "
          f"({failures} failures this run).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
