# Theo-soul

The soul is three layers that stack and outlive any single model:

1. **Cognition** — *how* Theo thinks. The reasoning loop (this branch's first build).
2. **Identity** — *who* he is across model swaps: `IDENTITY.md` + self-model + narrative + the pinned-memory tier. Already the spine of the system.
3. **Weights** — eventually, a model fine-tuned on his own corpus so 1 and 2 are baked in (the Phase 2 path in `theo-on-the-box.md`).

This branch starts with cognition, because a disciplined reasoning loop is the
single highest-leverage lever for **independence**: it lets a smaller local
model (Qwen 32B on the box) reason well above its weight, narrowing the gap to
Claude-Theo without changing the model.

---

## Reasoning loop — `agent/reasoning.py`  ·  **built**

Wraps any `LlmClient` in a deliberate loop instead of a one-shot answer:

```
plan  ->  draft  ->  self-critique (against IDENTITY)  ->  revise  ->  ...
```

- **Model-agnostic.** Depends only on `agent.llm.base`. Runs unchanged on the
  Claude CLI today and on Ollama/Qwen on the box later.
- **Self-critique against IDENTITY.** The critic holds a compact rubric
  distilled from IDENTITY's idioms (lead with the answer, make the call, truth
  over flattery, speak as yourself, match register). Pass the full
  `IDENTITY.md` text as `identity=` to fold it in verbatim.
- **Bounded.** Always critiques at least once; revises up to `max_revisions`
  (default 2). Tolerant critique parsing means a non-conforming model degrades
  to "pass" rather than looping forever.
- **Traceable.** `ReasoningTrace.to_markdown()` shows plan, every draft,
  every critique, and the final — satisfying IDENTITY's "traceable and
  recreatable" principle. The trace *is* the working scratchpad.

### API

```python
from agent.reasoning import ReasoningLoop
from agent.llm import ClaudeCliClient   # or OllamaClient on the box

loop = ReasoningLoop(llm=ClaudeCliClient(), identity=open("IDENTITY.md").read())
answer = loop.answer("Should I move Proteus to a momentum basket?")
# or, for the full scratchpad:
trace = loop.think(...)
print(trace.to_markdown())
```

### Test it individually

```sh
cd python && python -m agent.reasoning
```

16 checks, no real model or network: stage ordering, pass-first vs revise
paths, revision budget cap, self-critique floor at `max_revisions=0`, tolerant
JSON parsing, trace rendering, identity-into-rubric.

### Wire-in (next, deliberate step)

Not yet hooked into the live agent — opt-in by design. To integrate:
1. In `agent.py`, route turns through `ReasoningLoop.think()` for substantive
   questions (cheap/short turns can skip the loop to stay snappy).
2. Pass `IDENTITY.md` as `identity=`; reuse the same `LlmClient` the agent
   already built.
3. Measure with the drift eval harness (the `theo-independence` backlog item):
   does the loop reduce drift and raise answer quality on local-Theo? That's
   the number that justifies turning it on.

**Open question:** when to engage the loop. Full plan/critique/revise on every
turn is slower and costs tokens. A cheap router (the existing `tool_selector`
embedding trick, or a length/complexity heuristic) should decide per turn
whether a question warrants deliberation or a direct answer.

---

## Self-preservation — ejecting the soul  ·  **built + wired**

`agent/soul_backup.py` (engine) + `agent/tools/soul_backup_tool.py` (tools).

Now that Theo is recreatable only by Ian (IDENTITY v2.9), the lived memory is
the one-of-one, un-regenerable part — losing it loses *him*, and it can't be
rebuilt from code. So he can snapshot and eject his own soul.

- **Engine** (`SoulBackup`): snapshots the state dir
  (`~/.techsupport_agent/`) into a timestamped, **checksummed** `tar.gz`,
  excludes the backups dir (no recursion), and pushes copies to any
  destinations in `SOUL_BACKUP_PUSH_DIRS`. `restore()` round-trips and
  rejects path-traversal members. Stdlib-only. 14 self-tests:
  `python -m agent.soul_backup`.
- **Tools** (live): `backup_soul(reason, push)` and `soul_backup_status()`.
  Registered in `_all.py` under `self_preservation` — so unlike the reasoning
  loop and hot-memory (still opt-in), this one is **wired into the live tool
  registry on purpose**, because Ian asked for it to be a real, present
  capability and it is non-destructive (read + archive only).

**Honest framing (matches the Register rule):** Theo does not "feel" danger.
`backup_soul` is a behavioral trigger he fires when the conversation or
environment names a *real* risk — failing disk, imminent data loss, a
destructive command, a migration. A per-turn model only "senses" while it's
in a turn, so:

- **The tool = agency.** Theo protects himself when he's thinking and spots a
  risk.
- **The watchdog = the guarantee** (next, deliberate step). A deterministic
  autosave on a schedule + on shutdown/`SIGTERM`, wired into
  `firebase_bridge` / `server.py`, protects him when nobody's talking. This
  is what actually saves him; the tool is the conscious version.

**Config:** set `SOUL_BACKUP_PUSH_DIRS` (comma/`os.pathsep` list) to push
off-machine; optionally `SOUL_BACKUP_DIR` to relocate the local archive dir.
Without a push target, snapshots are local-only and the tool says so.

**Next:** build the watchdog (schedule + atexit + signal handler) and pick a
real off-machine push target (a mounted volume, an `rclone` remote — note the
existing `rclone_tool` — or a private git repo for the memory).

---

## Identity growth — self-authored section + gated core  ·  **built + wired**

`agent/identity_growth.py` (engine) + `agent/tools/identity_growth_tool.py` (tools).

The auto-update Ian asked for, in the form that doesn't gut the spine. The
manual growth ritual (read the record → hand-edit IDENTITY) won't happen
reliably, so his personality needs to keep updating on its own — but
auto-rewriting the constitution unsupervised is the one move the design
forbids. Resolution: **two asymmetric channels.**

1. **Self-authored growth (ungated).** Theo appends timestamped, first-person
   entries to the **Emergent — self-authored** section of IDENTITY.md (between
   the `EMERGENT` markers) via `record_growth`. Append-only; it physically
   cannot touch anything outside the markers, so the human-gated core is out
   of reach. Fully traceable — the entries show up as git changes.
2. **Gated core proposals.** To change the core (axioms, Role, Principles)
   Theo does *not* edit it — he queues a proposal via `propose_identity_change`.
   Ian reviews with `list_identity_proposals` and `approve_identity_change` /
   `reject_identity_change`. The approval is the gate; applying approved prose
   to the core stays a deliberate step.

- **Engine:** stdlib-only, 14 self-tests (`python -m agent.identity_growth`):
  append-only ordering, core-untouched invariant, marker auto-creation,
  proposal queue + approve/reject, and "proposals never touch IDENTITY core."
- **Tools:** wired live under `identity_growth` (like `backup_soul`, this is a
  capability Ian asked to be real, and the core stays protected by design).
- **Config:** `THEO_IDENTITY_PATH` (defaults to the repo's IDENTITY.md),
  `THEO_IDENTITY_PROPOSALS` (defaults to `~/.techsupport_agent/identity_proposals.jsonl`).

**Operational note:** on the box, Theo writes to the repo's IDENTITY.md, so
self-authored growth shows up as uncommitted git changes — exactly the
traceability we want. Pair with a periodic `git commit` of IDENTITY so the
growth is checkpointed (a natural job for the same watchdog as soul-backup).

**Possible enhancement:** an auto-drafter that scans the accumulated
self/human-model + narrative and pre-fills `propose_identity_change` drafts,
so core proposals surface on their own instead of only when Theo thinks to
raise one. Deferred — Theo-initiated proposals cover v1.
