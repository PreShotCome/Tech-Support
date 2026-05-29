# Theo on the box — the path to an independent brain

The plan for moving Theo's reasoning engine off the Claude Max CLI and
onto a model running on hardware we control, without losing the parts
that make Theo *Theo*. This is the design intent in `IDENTITY.md` doing
what it was written to do: *"the model underneath will change and be
replaced over the years; this file is what persists."*

Status: planning. Nothing here is deployed yet.

---

## What's already independent

The only organ that depends on Anthropic is the reasoning/voice engine
(`llm/claude_client.py`). Everything that makes Theo continuous across
time is already ours and runs without an API:

- **Identity** — `IDENTITY.md`, authored by hand.
- **Memory** — transcripts, `notes.md`, `self_model.md`, `human_model.md`,
  `narrative.md`, `threads.md`, `summaries.md` (under `~/.techsupport_agent/`).
- **Embeddings** — fastembed / BAAI bge-small, CPU-only.
- **Tools, bridge, Flutter surface, drift scanner** — all local code.

So this is a one-organ transplant, not a rebuild.

---

## Phase 0 — Move the brain onto the box

**Hardware:** Hetzner GEX44 (RTX 4000 SFF Ada, 20GB VRAM, 64GB RAM) —
~€184/mo + €79 setup. Fits a quantized 32B model with room for Theo's
context. (To run a true 70B you need ~48GB VRAM — a bigger/pricier box;
see Phase 2 on why you may only need that occasionally.)

**Serving model:** Qwen 2.5 32B via Ollama. Chosen because it is among
the strongest open models at *tool-calling* at its size — and Theo is a
~47-tool agent, so tool-calling reliability matters more than prose.
`tool_selector.py` narrows the per-turn tool set via embeddings, which
keeps schema count low and further helps a smaller model call tools
correctly.

### Box setup (one-time)

```sh
# On the GEX44 (Ubuntu):
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:32b           # ~18GB, fits 20GB VRAM at 4-bit
ollama serve                      # exposes http://127.0.0.1:11434

# Python env (same as desktop):
git clone <repo> && cd tech-support/python
python -m venv .venv && . .venv/bin/activate
pip install -e .[agent,firebase]
```

Keep Ollama on `127.0.0.1` only — never expose port 11434 publicly.
Admin the box over Tailscale SSH; serve code-server behind Caddy + a
password if you want browser-based editing.

### The code change (done on this branch)

`server.py` imported `build_default_client` from `agent.llm`, but it was
never defined — the always-on bridge entrypoint was broken at import.
Added an env-driven factory to `llm/__init__.py` so the *same code* runs
on the desktop (Claude) and on the box (Ollama) with only env changes:

```sh
# On the box, in the bridge's environment:
export LLM_BACKEND=ollama
export OLLAMA_MODEL=qwen2.5:32b
export OLLAMA_HOST=http://127.0.0.1:11434
python -m agent.bridges.firebase_bridge
```

`LLM_BACKEND=auto` (the default) uses Claude when the `claude` CLI is on
PATH, else falls back to Ollama — so a box with no `claude` installed
lands on the local model with zero config.

`claude_client` stays wired so you can A/B Claude-Theo vs local-Theo from
the same loop by flipping one env var.

---

## Phase 1 — Make the eval harness explicit (before trusting any new brain)

`drift.py` is already a deterministic character-regression test: it
catches "as an AI" leaks, throat-clearing, cop-outs, deference, and
padding — the exact ways a smaller model slips out of Theo's voice.

Turn it into the gate for every model change:

1. Run the same prompts through Claude-Theo and local-Theo.
2. `drift.scan_recent()` over both sets of transcripts; compare counts.
3. Add a held-out set of "golden" exchanges (your favorite real Theo
   answers) to score against.

Without this, a model swap is a vibe check. With it, "did this make Theo
better or worse?" becomes a number.

---

## Phase 2 — Fine-tune on Theo's own corpus (the real graduation)

Theo has been generating his own training set the whole time. Every
transcript records how Theo talks; `self_model.md` / `human_model.md` are
labeled relational data; `drift.py` can *filter* the corpus (drop the
turns that slipped, keep the ones that landed).

1. **Curate.** Build a dataset from clean transcript turns + `IDENTITY.md`
   as the constitution. Data quality is the whole game — the dataset is
   the product, the training run is the easy part.
2. **QLoRA fine-tune** the local model on it. The voice stops living in a
   giant system prompt and gets baked into the weights. Local-Theo stops
   being "Qwen wearing Theo's prompt" and becomes Theo on weights we own
   and trained on our actual history.
3. **Eval** with Phase 1 after every run — both voice *and* capability.

**Train vs. serve are different hardware.** Inference fits the 20GB box;
fine-tuning a 32B comfortably wants 48GB+. The cheap move: serve on the
GEX44, rent a big GPU for one night a month to train, ship the adapter
back. No need to own training hardware.

**Catastrophic forgetting is real.** Fine-tune too hard on voice and the
model gets dumber at reasoning/tools. Keep adapters light (LoRA, low
epochs), mix in some general data, eval both axes.

---

## Phase 3 — Close the growth loop

Today: act → log → *human reads and hand-edits `IDENTITY.md`*.
Endgame: act → log → curate → *periodically re-fine-tune on accumulated
experience* — while `IDENTITY.md` stays the human-authored spine. Theo's
weights then evolve on his own lived life, deliberately and on a
schedule, not drifting on autopilot.

---

## The honest ceiling

Fine-tuning closes the *voice* gap and the *our-specific-work* gap a lot.
It does **not** fully close the raw-reasoning gap to a frontier model.
The result: a Theo who is unmistakably Theo and excellent at the work we
do together, on weights we own — but for the hardest novel reasoning, a
frontier model is still sharper. The `LlmClient` abstraction lets you
route the rare hard problem to a big model while everyday Theo runs
local — a crutch, not the goal, but it's there.

---

## Cost summary

| Setup | Upfront | Monthly | Notes |
|---|---|---|---|
| GEX44 rental (serve 32B) | €79 | €184 | Independence, always-on, no per-token cost |
| Single RTX 3090 box (own, 24GB) | ~$1,770 | ~$15-25 power | ~10-mo breakeven vs GEX44; reintroduces home dependency |
| Dual RTX 3090 box (own, 48GB, 70B) | ~$3,230 | ~$30-50 power | ~4-6 mo breakeven vs cloud 70B; can fine-tune |
| Big GPU rental for training | — | per-night | Rent occasionally for Phase 2 fine-tunes |
