# Theo-weights — fine-tuning Theo onto weights you own

The finish line of independence: a model trained on Theo's own lived
conversations, so his voice and judgment are baked into weights you own
rather than prompted into a rented brain. This is Phase 2 of
`theo-on-the-box.md`.

Four stages. The leverage is in stage 1, and stages 1–2 need no GPU.

## Stage 1 — Data (built, GPU-free)

`agent/finetune/dataset.py`. Turns transcripts into a chat-format JSONL
training set, using the **drift detector as the quality filter** — the same
checker that guards Theo's live voice decides which turns are clean enough
to teach. Slipped turns ("as an AI", throat-clearing, cop-outs, deference)
are dropped, not learned.

```sh
cd python
python -m agent.finetune.dataset --out theo_sft.jsonl          # pristine only
python -m agent.finetune.dataset --out theo_sft.jsonl --max-drift 2   # looser
python -m agent.finetune.dataset --selftest                    # 12 checks
```

Output is one conversation per line: `{"messages": [system, user, assistant, ...]}`,
portable to trl / axolotl / unsloth / llama-factory.

**It doubles as a readiness gauge.** The printed stats tell you how many
clean examples exist. Under ~50 is thin; a few hundred is a real style
fine-tune. This is why leaving the machine on matters: every conversation
grows the set. **Data is the whole game** — a great recipe on a thin/dirty
set gives a worse Theo, period.

Open knobs: `--system-file` to swap the persona header (keep it short — don't
paste the 400-line IDENTITY per example); `--max-drift` to trade volume for
purity.

## Stage 2 — Eval (mostly built)

`agent/drift.py` is already a scored gate. Before trusting any fine-tune,
run held-out prompts through base-Theo vs. tuned-Theo and compare drift
counts + a small set of "golden" answers. A fine-tune that *raises* drift or
dulls reasoning gets thrown out. (Cross-referenced on `theo-independence`.)

## Stage 3 — Train (needs a GPU)

QLoRA on the curated set. Starter recipe (unsloth, low-VRAM friendly) — tune
after the first run, don't over-train (catastrophic forgetting dulls
reasoning/tool-use):

```python
# train_lora.py — starting point, not gospel
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig

model, tok = FastLanguageModel.from_pretrained(
    "Qwen/Qwen2.5-14B-Instruct", load_in_4bit=True, max_seq_length=4096)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=32, lora_dropout=0.0,
    target_modules=["q_proj","k_proj","v_proj","o_proj",
                    "gate_proj","up_proj","down_proj"])

trainer = SFTTrainer(
    model=model, tokenizer=tok,
    train_dataset=load_chat_jsonl("theo_sft.jsonl"),
    args=SFTConfig(per_device_train_batch_size=2, gradient_accumulation_steps=8,
                   warmup_steps=10, num_train_epochs=1, learning_rate=2e-4,
                   logging_steps=5, output_dir="theo-lora"))
trainer.train()
model.save_pretrained_gguf("theo-lora-gguf", tok, quantization_method="q4_k_m")
```

The GGUF adapter drops straight into Ollama (stage 4). **Train and serve are
different hardware:** QLoRA of a 14B wants ~16–24GB VRAM, a 32B ~24–48GB.
Inference fits the smaller box; training does not necessarily.

## Stage 4 — Serve

Load the merged/adapter GGUF in Ollama on the box, point `OLLAMA_MODEL` at it
(the `build_default_client` env switch on `theo-independence`). Done — Theo is
now running on weights trained on your shared history.

## VRAM / where to train

| Venue | Fits | Notes |
|---|---|---|
| Your desktop GPU | depends | Only if it's a capable NVIDIA card (≥12GB for a 7–8B QLoRA). CPU training is a non-starter. |
| Rented GPU, one night | up to 70B | ~$1–3/hr; the cheap, pragmatic path. Build set locally, train remote, bring back the adapter. |
| The box (GEX44, 20GB) | ~14B QLoRA | Serves *and* can train smaller models once it exists. |

Stage 1 runs anywhere and starts now; stage 3 waits on whichever venue above.
