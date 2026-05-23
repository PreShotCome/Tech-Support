"""Voice REPL — talk to the agent with your mic, hear the reply.

Usage:
    python -m agent.voice_cli                       # Enter-to-record, Enter-to-stop
    python -m agent.voice_cli --whisper base.en     # smaller/faster model
    python -m agent.voice_cli --no-speak            # transcribe-only, print reply
    python -m agent.voice_cli --list-voices         # show available TTS voices
    python -m agent.voice_cli --voice <voice_id>    # pick a specific TTS voice

In the REPL:
    Enter   start recording (then Enter again to stop)
    /text   switch to one typed line (for when you don't want to speak)
    /reset  clear conversation transcript
    /tools  list registered tools
    /quit   exit
"""
from __future__ import annotations

import argparse
import sys

from .cli import build_agent


def _print_voices() -> None:
    try:
        from .voice import list_voices
        voices = list_voices()
    except ImportError as e:
        print(
            f"voice deps not available ({e}).\n"
            f"  install: pip install -e .[voice]",
            file=sys.stderr,
        )
        sys.exit(1)
    for v in voices:
        print(f"  {v['id']}\n    name: {v['name']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["auto", "claude", "ollama"], default="auto")
    p.add_argument("--model", default=None)
    p.add_argument("--whisper", default="small.en",
                   help="Whisper model. tiny.en / base.en / small.en / medium.en. Default small.en.")
    p.add_argument("--whisper-device", default="cpu", help="cpu or cuda")
    p.add_argument("--whisper-compute", default="int8",
                   help="int8 (cpu), float16/float32 (cuda)")
    p.add_argument("--no-speak", action="store_true",
                   help="Don't speak the reply, just print it.")
    p.add_argument("--rate", type=int, default=185, help="TTS words-per-minute. Default 185.")
    p.add_argument("--voice", default=None, help="TTS voice id (see --list-voices).")
    p.add_argument("--list-voices", action="store_true",
                   help="List available TTS voices and exit.")
    args = p.parse_args()

    if args.list_voices:
        _print_voices()
        return

    # Voice imports happen lazily — fail loudly with a clear install hint
    # if the [voice] extra isn't there.
    try:
        from .voice import (
            VoiceConfig, record_until_enter, transcribe, speak,
        )
    except ImportError as e:
        print(
            f"voice deps not available ({e}).\n"
            f"  install: pip install -e .[voice]",
            file=sys.stderr,
        )
        sys.exit(1)

    cfg = VoiceConfig(
        whisper_model=args.whisper,
        whisper_device=args.whisper_device,
        whisper_compute=args.whisper_compute,
        tts_rate=args.rate,
        tts_voice_id=args.voice,
    )

    agent = build_agent(args.backend, args.model)

    from .briefing import briefing_summary_for_human
    backend_name = agent.llm.__class__.__name__
    model_name = getattr(agent.llm, "model", "?") or "(default)"
    print(f"TechSupport voice REPL  ·  {backend_name} / {model_name}")
    print(f"  STT: faster-whisper / {cfg.whisper_model} / {cfg.whisper_device}")
    print(f"  TTS: {'OFF (--no-speak)' if args.no_speak else f'pyttsx3 / rate={cfg.tts_rate}wpm'}")
    print(f"  Tools: {len(agent.tools.names())} registered")
    print()
    print("Continuity briefing:")
    print(briefing_summary_for_human())
    print()
    print("Press Enter to start speaking. Enter again to stop.")
    print("/text for typed input, /reset, /tools, /quit.\n")

    # Pre-warm whisper so the first turn isn't a 5s pause.
    print("(warming whisper model — first load takes a moment)", file=sys.stderr)
    try:
        from .voice import _get_whisper
        _get_whisper(cfg)
    except Exception as e:
        print(f"warmup failed: {e}", file=sys.stderr)
    print("(ready)\n", file=sys.stderr)

    while True:
        try:
            cue = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if cue in ("/quit", "/exit"):
            break
        if cue == "/tools":
            print(f"  {', '.join(agent.tools.names())}")
            continue
        if cue == "/reset":
            agent.reset()
            print("  (transcript cleared)")
            continue
        if cue == "/text":
            try:
                user_text = input("typed> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            if not user_text:
                continue
        elif cue == "":
            # Voice path: record, transcribe, send.
            try:
                wav = record_until_enter(cfg)
            except Exception as e:
                print(f"  mic error: {e.__class__.__name__}: {e}", file=sys.stderr)
                continue
            try:
                user_text = transcribe(wav, cfg).strip()
            except Exception as e:
                print(f"  transcribe error: {e.__class__.__name__}: {e}", file=sys.stderr)
                continue
            finally:
                try:
                    wav.unlink(missing_ok=True)
                except Exception:
                    pass
            if not user_text:
                print("  (no speech detected)")
                continue
            print(f"  you said: {user_text!r}")
        else:
            # User typed something other than an empty line — treat as text input.
            user_text = cue

        try:
            reply = agent.chat(user_text)
        except Exception as e:
            print(f"  error: {e.__class__.__name__}: {e}", file=sys.stderr)
            continue

        print(f"agent> {reply}\n")
        if not args.no_speak and reply.strip():
            try:
                speak(reply, cfg)
            except Exception as e:
                print(f"  tts error: {e.__class__.__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
