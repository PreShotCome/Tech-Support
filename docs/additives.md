# Theo additives

A catalog of feature ideas, each built and tested **individually** before
being wired into the live agent. The pattern: a self-contained module under
`python/agent/additives/` with its own runnable self-test, proven in
isolation, *then* a deliberate wire-in step. A half-finished idea here can
never destabilize Theo's live memory or voice.

Run any additive's self-test directly:

```sh
cd python && python -m agent.additives.<name>
```

## Status legend

- **idea** — described, not built
- **built** — module + self-test exist and pass, not yet wired into the agent
- **wired** — integrated into the live loop/briefing
- **live** — running on the deployed Theo

---

## #1 — Hot-memory (frequency promotion)  ·  **built**

`agent/additives/hot_memory.py`

Ian's idea (2026-05-29): the briefing surfaces memory by recency + semantic
relevance, but never by *how often* a thing gets pulled back. Track
retrieval frequency so topics he keeps circling back to stay warm in the
briefing automatically, while untouched ones decay and "collect dust."

- **Algorithm:** exponentially time-decayed access frequency. Each recall
  decays the prior score by elapsed half-lives, then adds the access
  weight. Decay *is* the dust — no separate eviction sweep, no single
  ancient spike dominating forever. Half-life default: 1 week (tunable).
- **API:** `HotMemoryTracker.record(key)`, `.warmth(key)`, `.hot(n)`,
  `.render_briefing_block()`, `.save()`. Stdlib-only, clock injectable for
  deterministic tests.
- **Self-test:** 10 checks (seeding, frequency ordering, half-life decay,
  recency-beats-dormant, persistence round-trip, briefing rendering). All
  passing.

**Wire-in (next, deliberate step):**
1. Call `tracker.record(key)` inside the recall tools — `semantic_recall`,
   `recall`, `search_transcripts` (see `tools/memory.py` /
   `tools/typed_memory.py`) — keyed by the recalled note id / topic /
   transcript name.
2. Add `tracker.render_briefing_block()` output to `briefing.py`'s
   `compose_briefing`, beside the existing recent-transcript section.
3. Persist to `~/.techsupport_agent/hot_memory.json` (matches the
   `state.py` convention).

Open question for wire-in: what's the right *key* granularity — note id,
semantic topic, or transcript? Start with note id + transcript name (cheap,
already unique); revisit topic-level keys once it's earning its place.

---

## Backlog — ideas, not yet built

- **Pinned tier / eviction guard.** A frequency cache will eventually want
  to drop cold items, but some cold items are load-bearing (a one-time
  hard constraint). Needs an explicit "pinned, never ages out" set above
  the frequency tier. `IDENTITY.md` + `notes.md` are the implicit pinned
  tier today; make it explicit before any eviction lands.
- **Arc paging (zip/unzip raw arcs).** Beat lossy compaction by storing
  raw conversation arcs externally with a short tagged stub + pointer in
  context, and paging the raw arc back on demand. Separate the *index*
  (in context) from the *store* (on disk) so recall is reversible, not
  just compression. (MemGPT/Letta-style tiered memory.)
- **Drift eval harness.** Turn `drift.py` into a scored gate for model
  swaps/fine-tunes — compare local-Theo vs Claude-Theo on a fixed prompt
  set + a held-out "golden answers" set. (Tracked on
  `claude/theo-independence`; cross-referenced here.)
