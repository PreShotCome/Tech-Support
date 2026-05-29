"""Hot-memory tracker — frequency-promotion layer (Additive #1).

Idea (Ian, 2026-05-29): the briefing surfaces memory by recency and
semantic relevance, but never by *how often* a thing gets pulled back.
Track retrieval frequency so topics he keeps circling back to stay warm
in the briefing automatically, while untouched ones decay and "collect
dust." A cache-warmth layer on top of the existing recall.

Algorithm — exponentially time-decayed access frequency:
  Each recall of a key decays its prior score by the elapsed number of
  half-lives, then adds the access weight. Frequently-hit keys stay high;
  cold keys decay toward zero on their own. The decay *is* the
  "collecting dust" — no separate eviction sweep needed, and a single
  ancient spike can't dominate forever.

This module is intentionally self-contained (stdlib only) and does not
touch embeddings, the briefing, or the recall tools yet. Wiring it in is
a separate, deliberate step (see docs/additives.md). Run the self-test:

    python -m agent.additives.hot_memory
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Optional


# One week to halve an untouched topic's warmth. Tunable.
DEFAULT_HALFLIFE_S: float = 7 * 24 * 3600


@dataclass
class HotEntry:
    key: str
    score: float        # decayed frequency ("warmth")
    hits: int           # raw lifetime access count
    last_access: float  # epoch seconds


class HotMemoryTracker:
    """Tracks decayed access frequency per memory key.

    `key` is whatever identifies a recalled item — a topic string, a note
    id, a transcript name. The tracker is agnostic to what it counts.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        halflife_s: float = DEFAULT_HALFLIFE_S,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = Path(path) if path else (
            Path.home() / ".techsupport_agent" / "hot_memory.json"
        )
        self.halflife_s = float(halflife_s)
        self._clock = clock
        self._entries: dict[str, HotEntry] = {}
        self._load()

    # ----------------------------------------------------------- decay math

    def _decay_factor(self, dt: float) -> float:
        """Multiplier applied to an old score after `dt` seconds elapsed."""
        if dt <= 0 or self.halflife_s <= 0:
            return 1.0
        return 0.5 ** (dt / self.halflife_s)

    # --------------------------------------------------------------- writes

    def record(self, key: str, weight: float = 1.0) -> HotEntry:
        """Register one access to `key`. Returns its updated entry."""
        now = self._clock()
        e = self._entries.get(key)
        if e is None:
            e = HotEntry(key=key, score=0.0, hits=0, last_access=now)
        else:
            e.score *= self._decay_factor(now - e.last_access)
        e.score += weight
        e.hits += 1
        e.last_access = now
        self._entries[key] = e
        return e

    # ---------------------------------------------------------------- reads

    def warmth(self, key: str) -> float:
        """Current decayed score for `key` as of now (0.0 if unknown)."""
        e = self._entries.get(key)
        if e is None:
            return 0.0
        return e.score * self._decay_factor(self._clock() - e.last_access)

    def hot(self, n: int = 5, min_score: float = 0.0) -> list[tuple[str, float, int]]:
        """Top-`n` keys by current warmth: (key, warmth, lifetime_hits)."""
        now = self._clock()
        scored: list[tuple[float, HotEntry]] = []
        for e in self._entries.values():
            s = e.score * self._decay_factor(now - e.last_access)
            if s > min_score:
                scored.append((s, e))
        scored.sort(key=lambda t: (t[0], t[1].last_access), reverse=True)
        return [(e.key, s, e.hits) for s, e in scored[:n]]

    def render_briefing_block(self, n: int = 5, min_score: float = 0.5) -> str:
        """Markdown for the session-start briefing. Empty when nothing's
        warm enough to surface — so it adds zero noise on a cold start."""
        rows = self.hot(n=n, min_score=min_score)
        if not rows:
            return ""
        lines = ["**Hot topics** — frequently revisited lately, kept warm:"]
        for key, score, hits in rows:
            lines.append(f"- {key}  ·  warmth {score:.1f} ({hits} hits)")
        return "\n".join(lines)

    # ----------------------------------------------------------- persistence

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "halflife_s": self.halflife_s,
            "entries": [asdict(e) for e in self._entries.values()],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return self.path

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return  # corrupt/partial file: start empty rather than crash
        for row in data.get("entries", []):
            try:
                e = HotEntry(
                    key=str(row["key"]),
                    score=float(row["score"]),
                    hits=int(row["hits"]),
                    last_access=float(row["last_access"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._entries[e.key] = e


# ----------------------------------------------------------------- self-test

def _selftest() -> int:
    """Deterministic checks using a controllable fake clock. Returns 0 on
    pass, 1 on failure. No pytest dependency — runnable as a module."""
    import tempfile

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"[{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    # Controllable clock.
    t = {"now": 1_000_000.0}
    clock = lambda: t["now"]
    day = 24 * 3600

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "hot.json"
        hm = HotMemoryTracker(path=p, halflife_s=7 * day, clock=clock)

        # 1. First access seeds hits=1, warmth≈1.
        hm.record("the box")
        check("first access -> 1 hit", hm._entries["the box"].hits == 1)
        check("first access -> warmth ~1", abs(hm.warmth("the box") - 1.0) < 1e-9)

        # 2. Repeated access raises warmth above a single-hit item.
        for _ in range(4):
            hm.record("the box")
        hm.record("chess")
        check("frequent > rare warmth", hm.warmth("the box") > hm.warmth("chess"))
        check("frequent hits counted", hm._entries["the box"].hits == 5)

        # 3. One half-life of silence halves warmth (the 'dust' rule).
        warm_before = hm.warmth("the box")
        t["now"] += 7 * day
        check("decay halves over one half-life",
              abs(hm.warmth("the box") - warm_before / 2) < 1e-6)

        # 4. A fresh single hit outranks a once-frequent but long-dormant one.
        t["now"] += 60 * day            # 'the box' goes very cold
        hm.record("plutus")             # fresh single hit
        top = hm.hot(n=1)
        check("recent fresh item is hottest", top and top[0][0] == "plutus")

        # 5. Persistence round-trips.
        hm.save()
        hm2 = HotMemoryTracker(path=p, halflife_s=7 * day, clock=clock)
        check("reloaded entry count matches", len(hm2._entries) == 3)
        check("reloaded hits preserved", hm2._entries["the box"].hits == 5)

        # 6. Briefing block: empty below threshold, populated above.
        cold = HotMemoryTracker(path=Path(d) / "c.json", clock=clock)
        check("empty briefing on cold start", cold.render_briefing_block() == "")
        block = hm2.render_briefing_block(min_score=0.0)
        check("briefing names a hot topic", "plutus" in block)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("All hot_memory self-tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
