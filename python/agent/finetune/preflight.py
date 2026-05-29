"""Preflight: can this desktop train, and how big?

You picked "train on my desktop GPU." I can't see your hardware from the
repo, so run this on the machine that will train:

    cd python && python -m agent.finetune.preflight

It reports CUDA availability, the GPU, and total VRAM, then recommends the
largest model a single-GPU QLoRA run can fit. Paste the output back and I'll
size the training script to it.

GPU-free to test (the VRAM->model logic is a pure function):

    python -m agent.finetune.preflight --selftest
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


@dataclass
class GpuInfo:
    available: bool
    name: str = ""
    vram_gb: float = 0.0
    source: str = ""          # "torch" | "nvidia-smi" | "none"
    detail: str = ""


def gpu_info() -> GpuInfo:
    """Best-effort GPU probe: prefer torch (what training will use), fall
    back to nvidia-smi, else report nothing usable."""
    # 1) torch — the source of truth for whether training will see the GPU.
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            i = torch.cuda.current_device()
            props = torch.cuda.get_device_properties(i)
            return GpuInfo(
                available=True,
                name=props.name,
                vram_gb=round(props.total_memory / (1024 ** 3), 1),
                source="torch",
            )
        else:
            torch_note = "torch present but torch.cuda.is_available() is False"
    except Exception as e:  # torch not installed, or import/driver error
        torch_note = f"torch unavailable ({e.__class__.__name__})"

    # 2) nvidia-smi — there's a card even if torch can't use it yet.
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            first = out.stdout.strip().splitlines()[0]
            name, mem = [s.strip() for s in first.split(",")[:2]]
            return GpuInfo(
                available=False,  # card seen, but torch/CUDA not confirmed
                name=name,
                vram_gb=round(float(mem) / 1024, 1),
                source="nvidia-smi",
                detail=(f"{torch_note}; nvidia-smi sees the card but training "
                        "needs a working torch+CUDA install (pip install torch "
                        "with CUDA, then re-run)."),
            )
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return GpuInfo(available=False, source="none",
                   detail=f"{torch_note}; no nvidia-smi found. No usable NVIDIA "
                          "GPU detected — CPU training isn't viable; rent a GPU "
                          "for the run instead.")


# VRAM (GB) -> largest model a single-GPU 4-bit QLoRA run can train at ~4k seq.
# Conservative; bump seq length down or model up at your own risk.
_TIERS = [
    (48.0, "70B", "Qwen2.5-72B / Llama-3.3-70B (4-bit QLoRA, tight; 2x24GB also works)"),
    (24.0, "32B", "Qwen2.5-32B-Instruct (4-bit QLoRA)"),
    (16.0, "14B", "Qwen2.5-14B-Instruct (4-bit QLoRA)"),
    (12.0, "8B",  "Llama-3.1-8B / Qwen2.5-7B-Instruct (4-bit QLoRA)"),
    (8.0,  "3-4B", "Qwen2.5-3B / Llama-3.2-3B (tight; short seq len)"),
]


def recommend_model(vram_gb: float) -> dict:
    for floor, size, suggestion in _TIERS:
        if vram_gb >= floor:
            return {"max_size": size, "suggested": suggestion, "fits": True}
    return {
        "max_size": "none",
        "suggested": "Under ~8GB VRAM is too small for a useful QLoRA — "
                     "rent a GPU for the run, or train a tiny model just to learn the pipeline.",
        "fits": False,
    }


def report() -> str:
    g = gpu_info()
    lines = ["=== Theo-weights desktop preflight ==="]
    lines.append(f"CUDA usable by torch: {g.available}")
    if g.name:
        lines.append(f"GPU: {g.name}")
        lines.append(f"VRAM: {g.vram_gb} GB  (via {g.source})")
    else:
        lines.append("GPU: (none detected)")
    if g.detail:
        lines.append(f"Note: {g.detail}")
    if g.vram_gb:
        rec = recommend_model(g.vram_gb)
        lines.append("")
        lines.append(f"Largest QLoRA-trainable model: {rec['max_size']}")
        lines.append(f"Suggested base: {rec['suggested']}")
        if g.vram_gb and not g.available:
            lines.append("(But fix torch+CUDA first — see Note above — or this VRAM can't be used.)")
    lines.append("")
    lines.append("Paste this back and I'll size the training script to it.")
    return "\n".join(lines)


def _selftest() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"[{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    check("80GB -> 70B", recommend_model(80)["max_size"] == "70B")
    check("48GB -> 70B", recommend_model(48)["max_size"] == "70B")
    check("24GB -> 32B", recommend_model(24)["max_size"] == "32B")
    check("16GB -> 14B", recommend_model(16)["max_size"] == "14B")
    check("12GB -> 8B", recommend_model(12)["max_size"] == "8B")
    check("10GB -> 3-4B", recommend_model(10)["max_size"] == "3-4B")
    check("6GB -> none (too small)", recommend_model(6)["fits"] is False)
    check("boundary 23.9 -> 14B not 32B", recommend_model(23.9)["max_size"] == "14B")
    # gpu_info must never raise, even with no GPU / no torch / no nvidia-smi.
    try:
        g = gpu_info()
        check("gpu_info returns without raising", isinstance(g, GpuInfo))
    except Exception:
        check("gpu_info returns without raising", False)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("All preflight self-tests passed.")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return _selftest()
    print(report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
