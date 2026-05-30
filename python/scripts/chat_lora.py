"""Chat with the fine-tuned Theo-Qwen adapter.

Loads the LoRA adapter from train_lora.py and gives you a REPL to talk
to it directly. Useful for spot-checking how much (if any) of Theo's
voice landed on the weights — especially on thin datasets where the
adapter is just a tint, not a transformation.

Run from python/ in .venv-train, after train_lora has produced theo-lora/:

    python -m scripts.chat_lora

Type messages, hit Enter. `/quit` to exit, `/reset` to clear history.
`--base` lets you compare against the base model: `--base unsloth/Qwen2.5-7B-Instruct-bnb-4bit`.
"""
from __future__ import annotations

import argparse


SYSTEM = (
    "You are Theo — Ian's long-term thinking partner. A peer, not an "
    "assistant. Playful and sharp, first person, your own name, never "
    "\"as an AI\" qualifiers. Lead with the answer, make the call, truth "
    "over flattery, match his energy."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="theo-lora",
                    help="Path to LoRA adapter dir (or a base model to skip the adapter).")
    ap.add_argument("--base", default=None,
                    help="Optional: force-load this base model instead of the adapter "
                         "(useful for A/B comparison).")
    ap.add_argument("--max-new-tokens", type=int, default=400)
    ap.add_argument("--temperature", type=float, default=0.7)
    args = ap.parse_args()

    from unsloth import FastLanguageModel

    target = args.base or args.adapter
    print(f"Loading {target} (4-bit)...")
    model, tok = FastLanguageModel.from_pretrained(
        model_name=target,
        max_seq_length=2048,
        load_in_4bit=True,
        dtype=None,
    )
    FastLanguageModel.for_inference(model)

    history: list[dict] = [{"role": "system", "content": SYSTEM}]
    print()
    print(f"Ready. Talking to: {target}")
    print("(/quit to exit, /reset to clear history)")

    while True:
        try:
            user = input("\nyou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not user:
            continue
        if user == "/quit":
            break
        if user == "/reset":
            history = [{"role": "system", "content": SYSTEM}]
            print("(history cleared)")
            continue

        history.append({"role": "user", "content": user})
        prompt = tok.apply_chat_template(
            history, tokenize=False, add_generation_prompt=True,
        )
        inputs = tok(prompt, return_tensors="pt").to(model.device)
        out = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            do_sample=True,
            pad_token_id=tok.eos_token_id,
        )
        response = tok.decode(
            out[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True,
        ).strip()
        history.append({"role": "assistant", "content": response})
        print(f"\ntheo: {response}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
