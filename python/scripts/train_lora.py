"""QLoRA fine-tune Theo on his own transcripts.

Sized for: NVIDIA RTX 3060 (12 GB VRAM), Python 3.12, torch 2.5.1+cu121.
Default base: Qwen2.5-7B-Instruct — the strongest open model at this size
for *tool-calling*, which is Theo's hottest path (~47 tools). Llama-3.1-8B
is also fine (`--base unsloth/llama-3-8b-bnb-4bit`).

Stage 3 of the weights pipeline (see docs/theo-weights.md). Run from the
`python/` directory after activating .venv-train:

    python -m scripts.train_lora --data theo_sft.jsonl

Output: a LoRA adapter at ./theo-lora/. Merge to GGUF and load in Ollama.

Tuning knobs that matter on 12 GB:
  --batch        per-device microbatch (default 2; drop to 1 if OOM)
  --grad-accum   effective batch multiplier (default 8 → effective 16)
  --epochs       3 is a sane default for thin datasets; raise as you grow
  --max-seq      2048 is the safe ceiling on a 3060; 4096 is risky here
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_BASE = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="theo_sft.jsonl",
                    help="Chat-format JSONL from agent.finetune.dataset.")
    ap.add_argument("--base", default=DEFAULT_BASE,
                    help="Base model (4-bit unsloth variant).")
    ap.add_argument("--out", default="theo-lora",
                    help="Adapter output directory.")
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--max-seq", type=int, default=2048)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERROR: dataset not found: {data_path.resolve()}\n"
              "Build it first:\n"
              "  python -m agent.finetune.dataset --transcripts-dir "
              "$env:USERPROFILE\\.techsupport_agent\\transcripts "
              "--out theo_sft.jsonl --max-drift 5", file=sys.stderr)
        return 1

    # Imports are deferred so --help and the dataset check don't pay the
    # multi-second CUDA/transformers import cost.
    from unsloth import FastLanguageModel
    from datasets import load_dataset
    from trl import SFTTrainer, SFTConfig

    print(f"Loading {args.base} (4-bit, max_seq_length={args.max_seq})...")
    model, tok = FastLanguageModel.from_pretrained(
        model_name=args.base,
        max_seq_length=args.max_seq,
        load_in_4bit=True,
        dtype=None,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.0,
        bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    print(f"Loading dataset: {data_path}")
    ds = load_dataset("json", data_files=str(data_path), split="train")
    print(f"  {len(ds)} examples")
    if len(ds) < 30:
        print("  WARNING: under 30 clean examples — fine-tune will be weak. "
              "Loosen --max-drift in the dataset builder and keep accumulating "
              "transcripts before serious training.")

    # Render each chat conversation through the model's own chat template.
    def _to_text(ex):
        return {"text": tok.apply_chat_template(ex["messages"], tokenize=False)}
    ds = ds.map(_to_text, remove_columns=ds.column_names)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tok,
        train_dataset=ds,
        dataset_text_field="text",
        max_seq_length=args.max_seq,
        args=SFTConfig(
            per_device_train_batch_size=args.batch,
            gradient_accumulation_steps=args.grad_accum,
            warmup_steps=10,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            # Ampere (3060) supports bf16. If you hit a bnb error, swap to
            # fp16=True, bf16=False.
            bf16=True,
            fp16=False,
            logging_steps=5,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="cosine",
            seed=3407,
            output_dir=args.out,
            report_to="none",
            save_strategy="epoch",
        ),
    )
    trainer.train()

    print(f"\nSaving LoRA adapter to {args.out}/ ...")
    model.save_pretrained(args.out)
    tok.save_pretrained(args.out)

    print(
        "\nDone. To export for Ollama (GGUF, 4-bit), run in a Python shell:\n"
        "    from unsloth import FastLanguageModel\n"
        f"    model, tok = FastLanguageModel.from_pretrained('{args.out}', load_in_4bit=True)\n"
        f"    model.save_pretrained_gguf('{args.out}-gguf', tok, "
        "quantization_method='q4_k_m')\n"
        "Then point Ollama at the resulting .gguf file."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
