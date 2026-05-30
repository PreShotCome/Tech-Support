"""Stage 2: QLoRA fine-tune a local base model on Theo's transcript dataset.

Pipeline so far:
    1. dataset.py   transcripts -> clean chat-format JSONL   (GPU-free)
    2. preflight.py probe the GPU, recommend a model size     (GPU-free)
    3. train.py     4-bit QLoRA SFT on that JSONL              (needs GPU)  <- you are here

The sizing logic is a pure function of VRAM (`plan_training`), mirroring
preflight's tiers, so the plan is inspectable and testable without a GPU:

    python -m agent.finetune.train --dry-run            # print the resolved plan, no torch
    python -m agent.finetune.train --selftest           # GPU-free tests of the sizing + loader

The actual run (needs a working torch+CUDA + bitsandbytes install):

    python -m agent.finetune.dataset --out theo_sft.jsonl
    python -m agent.finetune.train --data theo_sft.jsonl --out runs/theo-qlora

It auto-sizes to the detected GPU; override the base model with --base.
The heavy stack (torch / transformers / peft / trl / bitsandbytes) is
imported lazily inside train() so this module — and its self-test — load
on any machine, GPU or not. Install that stack with:

    pip install -e .[finetune]

NOTE on this desktop: the QLoRA stack needs Python 3.11/3.12 (torch CUDA,
bitsandbytes, and trl have no 3.14 wheels yet) and a torch built with CUDA.
Make a 3.12 venv for training; the dataset/preflight stages run anywhere.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TrainPlan:
    vram_gb: float
    base_model: str
    max_seq_len: int
    lora_r: int
    lora_alpha: int
    micro_batch: int
    grad_accum: int
    fits: bool = True
    note: str = ""

    @property
    def effective_batch(self) -> int:
        return self.micro_batch * self.grad_accum

    def to_dict(self) -> dict:
        d = {
            "vram_gb": self.vram_gb,
            "base_model": self.base_model,
            "max_seq_len": self.max_seq_len,
            "lora_r": self.lora_r,
            "lora_alpha": self.lora_alpha,
            "micro_batch": self.micro_batch,
            "grad_accum": self.grad_accum,
            "effective_batch": self.effective_batch,
            "fits": self.fits,
        }
        if self.note:
            d["note"] = self.note
        return d


# VRAM (GB) -> QLoRA training plan. Floors match preflight._TIERS so the two
# stages agree on what fits; the extra columns are conservative single-GPU
# 4-bit QLoRA hyperparameters (micro_batch 1 + grad accumulation, gradient
# checkpointing assumed). Shorter seq len at the low tiers because that's
# where VRAM bites — Theo's transcripts are short, so 1024 is plenty at 12GB.
#        floor  base_model                         seq   r   alpha micro accum
_TIERS = [
    (48.0, "Qwen/Qwen2.5-72B-Instruct",            2048, 16, 32,   1,    16),
    (24.0, "Qwen/Qwen2.5-32B-Instruct",            2048, 16, 32,   1,    16),
    (16.0, "Qwen/Qwen2.5-14B-Instruct",            2048, 16, 32,   1,    16),
    (12.0, "Qwen/Qwen2.5-7B-Instruct",             1024, 16, 32,   1,    16),
    (8.0,  "Qwen/Qwen2.5-3B-Instruct",              512, 16, 32,   1,     8),
]


def plan_training(vram_gb: float, base_model: Optional[str] = None) -> TrainPlan:
    """Pick a conservative QLoRA plan for the given VRAM. Pure function."""
    for floor, base, seq, r, alpha, micro, accum in _TIERS:
        if vram_gb >= floor:
            return TrainPlan(
                vram_gb=vram_gb,
                base_model=base_model or base,
                max_seq_len=seq,
                lora_r=r,
                lora_alpha=alpha,
                micro_batch=micro,
                grad_accum=accum,
            )
    return TrainPlan(
        vram_gb=vram_gb,
        base_model=base_model or "(none — too small)",
        max_seq_len=0, lora_r=0, lora_alpha=0, micro_batch=0, grad_accum=0,
        fits=False,
        note=("Under ~8GB VRAM is too small for a useful QLoRA — rent a GPU "
              "for the run, or train a tiny model just to learn the pipeline."),
    )


def load_chat_jsonl(path: Path) -> list[dict]:
    """Read the dataset.py output: one {"messages": [...]} object per line.
    Pure (stdlib only) so it's testable without `datasets` installed."""
    path = Path(path)
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "messages" not in obj or not isinstance(obj["messages"], list):
                raise ValueError(f"{path}:{ln}: row missing a 'messages' list")
            rows.append(obj)
    return rows


def _no_cuda_message() -> str:
    return (
        "torch+CUDA is not usable here, so there's nothing to train on.\n"
        "Fix the environment first (run `python -m agent.finetune.preflight`\n"
        "to confirm), then re-run. On this desktop that means a Python 3.11/\n"
        "3.12 venv with a CUDA build of torch and bitsandbytes — the 3.14\n"
        "venv has no wheels for the QLoRA stack."
    )


def train(plan: TrainPlan, data_path: Path, out_dir: Path,
          epochs: float = 3.0, lr: float = 2e-4) -> Path:
    """Run the 4-bit QLoRA SFT. Heavy deps are imported here, not at module
    load, so the rest of this file stays GPU-free and import-light."""
    if not plan.fits:
        raise SystemExit(plan.note or "GPU too small for this run.")

    import torch  # type: ignore
    from datasets import load_dataset  # type: ignore
    from transformers import (  # type: ignore
        AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
    )
    from peft import LoraConfig, prepare_model_for_kbit_training  # type: ignore
    from trl import SFTConfig, SFTTrainer  # type: ignore

    if not torch.cuda.is_available():
        raise SystemExit(_no_cuda_message())

    rows = load_chat_jsonl(data_path)
    if not rows:
        raise SystemExit(f"No training rows in {data_path}. Run the dataset "
                         "stage first (python -m agent.finetune.dataset).")
    if len(rows) < 50:
        print(f"Note: only {len(rows)} examples — thin for a fine-tune. "
              "Expect a light persona nudge, not a deep voice change.")

    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
    )

    tok = AutoTokenizer.from_pretrained(plan.base_model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        plan.base_model,
        quantization_config=bnb,
        device_map="auto",
        torch_dtype=compute_dtype,
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    lora = LoraConfig(
        r=plan.lora_r,
        lora_alpha=plan.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules="all-linear",
    )

    ds = load_dataset("json", data_files=str(data_path), split="train")

    cfg = SFTConfig(
        output_dir=str(out_dir),
        per_device_train_batch_size=plan.micro_batch,
        gradient_accumulation_steps=plan.grad_accum,
        num_train_epochs=epochs,
        learning_rate=lr,
        bf16=(compute_dtype is torch.bfloat16),
        fp16=(compute_dtype is torch.float16),
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        max_seq_length=plan.max_seq_len,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=5,
        save_strategy="epoch",
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=cfg,
        train_dataset=ds,          # conversational ("messages") format
        peft_config=lora,
        processing_class=tok,
    )
    trainer.train()
    out_dir = Path(out_dir)
    trainer.save_model(str(out_dir))
    tok.save_pretrained(str(out_dir))
    print(f"Saved LoRA adapter -> {out_dir}")
    return out_dir


def _resolve_plan(vram_override: Optional[float], base: Optional[str]) -> TrainPlan:
    """Use the explicit --vram if given, else probe via preflight."""
    if vram_override is not None:
        return plan_training(vram_override, base_model=base)
    from .preflight import gpu_info
    g = gpu_info()
    return plan_training(g.vram_gb, base_model=base)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="QLoRA fine-tune Theo on the transcript dataset.")
    ap.add_argument("--data", type=Path, default=Path("theo_sft.jsonl"),
                    help="Chat-format JSONL from agent.finetune.dataset.")
    ap.add_argument("--out", type=Path, default=Path("runs/theo-qlora"),
                    help="Output dir for the LoRA adapter.")
    ap.add_argument("--base", type=str, default=None,
                    help="Override the auto-selected base model.")
    ap.add_argument("--vram", type=float, default=None,
                    help="Override detected VRAM (GB) for sizing — useful with --dry-run.")
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the resolved training plan and exit (no torch).")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    plan = _resolve_plan(args.vram, args.base)

    if args.dry_run:
        print("=== Theo-weights training plan ===")
        print(json.dumps(plan.to_dict(), indent=2))
        if not plan.fits:
            print(f"\n{plan.note}")
        else:
            print(f"\nWould run: python -m agent.finetune.train "
                  f"--data {args.data} --out {args.out}")
        return 0

    train(plan, args.data, args.out, epochs=args.epochs, lr=args.lr)
    return 0


# ----------------------------------------------------------------- self-test

def _selftest() -> int:
    import tempfile

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"[{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    # Sizing tiers — floors agree with preflight._TIERS.
    check("48GB -> 72B", "72B" in plan_training(48).base_model)
    check("24GB -> 32B", "32B" in plan_training(24).base_model)
    check("16GB -> 14B", "14B" in plan_training(16).base_model)
    check("12GB -> 7B", "7B" in plan_training(12).base_model)
    check("12GB seq is conservative 1024", plan_training(12).max_seq_len == 1024)
    check("10GB -> 3B", "3B" in plan_training(10).base_model)
    check("6GB does not fit", plan_training(6).fits is False)
    check("boundary 23.9 -> 14B not 32B", "14B" in plan_training(23.9).base_model)
    check("effective batch = micro*accum", plan_training(12).effective_batch == 16)
    check("base override wins", plan_training(12, base_model="meta-llama/Llama-3.1-8B").base_model
          == "meta-llama/Llama-3.1-8B")

    # Floors stay in lockstep with preflight's tiers.
    try:
        from .preflight import _TIERS as PF_TIERS
        check("tier floors match preflight",
              [t[0] for t in _TIERS] == [t[0] for t in PF_TIERS])
    except Exception:
        check("tier floors match preflight", False)

    # Loader round-trips dataset.py output and rejects malformed rows.
    with tempfile.TemporaryDirectory() as d:
        good = Path(d) / "good.jsonl"
        good.write_text(
            json.dumps({"messages": [{"role": "user", "content": "hi"},
                                     {"role": "assistant", "content": "Hey."}]}) + "\n"
            + json.dumps({"messages": [{"role": "user", "content": "yo"},
                                       {"role": "assistant", "content": "Yo."}]}) + "\n",
            encoding="utf-8")
        rows = load_chat_jsonl(good)
        check("loader reads two rows", len(rows) == 2)
        check("loader keeps messages", rows[0]["messages"][0]["content"] == "hi")

        bad = Path(d) / "bad.jsonl"
        bad.write_text(json.dumps({"oops": 1}) + "\n", encoding="utf-8")
        try:
            load_chat_jsonl(bad)
            check("loader rejects rows without 'messages'", False)
        except ValueError:
            check("loader rejects rows without 'messages'", True)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("All train self-tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
