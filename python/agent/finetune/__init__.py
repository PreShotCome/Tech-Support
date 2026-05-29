"""Fine-tuning support — turning Theo's lived conversations into weights.

The weights work has four stages; this package owns the GPU-free ones:

  1. DATA   — `dataset.py`: transcripts -> clean training set. (here)
  2. EVAL   — reuse `agent/drift.py` as the scored gate. (mostly built)
  3. TRAIN  — QLoRA on a GPU. (config in docs/theo-weights.md; needs hardware)
  4. SERVE  — the adapter via Ollama on the box.

Stage 1 is where the leverage is ("data is the whole game") and it runs
with no GPU, so it can start now and improve as Theo talks more.
"""
