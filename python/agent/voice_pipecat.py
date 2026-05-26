"""Pipecat-driven voice REPL — real conversational voice with Theo.

Stack (all local, all free):
  - LocalAudioTransport — mic in / speaker out, no WebRTC needed
  - Silero VAD — voice activity detection, ends turns on silence
  - Whisper STT — speech to text (local, faster-whisper backend)
  - TheoAgentService — wraps Theo's existing Agent.chat() so voice
    and CLI share the same brain, memory, identity, transcripts
  - Piper TTS — natural-sounding text-to-speech (local, free)

Why this over the simpler agent.voice_cli:
  - No press-Enter dance. Silero VAD detects when you've finished
    speaking and triggers transcription automatically.
  - Piper sounds way better than pyttsx3's SAPI default.
  - Streaming pipeline — reply starts speaking as soon as Theo
    finishes thinking, not after pyttsx3 blocks.

Usage:
    python -m agent.voice_pipecat
    python -m agent.voice_pipecat --whisper-model base.en
    python -m agent.voice_pipecat --voice en_US-ryan-high

Setup (one-time):
    pip install "pipecat-ai[silero,whisper,piper]"
    pip install piper-tts
    python -m piper.download_voices en_US-ryan-high

Theo and his bridge can run side-by-side; this script just spawns
its own Agent instance pointing at the shared ~/.techsupport_agent/
state. The bridge stays online for the phone PWA."""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

# Pipecat 1.2.1 imports. If any of these paths shift in a later
# pipecat release the error will be clear enough to fix here without
# rewriting the architecture.
try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.transports.local.audio import (
        LocalAudioTransport,
        LocalAudioTransportParams,
    )
    from pipecat.services.whisper.stt import WhisperSTTService
    from pipecat.services.piper.tts import PiperTTSService
    from pipecat.processors.frame_processor import (
        FrameProcessor, FrameDirection,
    )
    from pipecat.frames.frames import (
        Frame, TextFrame, TranscriptionFrame, EndFrame,
    )
    from pipecat.audio.vad.silero import SileroVADAnalyzer
except ImportError as e:
    print(
        f"pipecat-ai not installed or version-shifted ({e}).\n"
        f"  Setup: pip install 'pipecat-ai[silero,whisper,piper]'",
        file=sys.stderr,
    )
    sys.exit(1)


class TheoAgentService(FrameProcessor):
    """Plug Theo's existing Agent into the pipecat pipeline.

    Receives TranscriptionFrames from the STT stage, runs Theo's
    Agent.chat() on the transcribed text (in a worker thread so it
    doesn't block the pipeline's event loop), and emits the reply
    as a TextFrame that the downstream TTS consumes.

    Theo's chat() can take 10-60s per turn — claude CLI start-up plus
    tool calls plus generation. The event loop stays responsive
    because asyncio.to_thread offloads the blocking call."""

    def __init__(self, agent):
        super().__init__()
        self._agent = agent

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if not text:
                return
            print(f"\nyou (heard): {text}")
            try:
                reply = await asyncio.to_thread(self._agent.chat, text)
            except Exception as e:
                reply = f"(internal error: {type(e).__name__}: {e})"
            if reply:
                print(f"theo (speaks): {reply}\n")
                await self.push_frame(TextFrame(reply))
        else:
            # Everything else passes through unchanged
            await self.push_frame(frame, direction)


def _build_agent(backend: str, model: str | None):
    """Reuse cli.build_agent so voice and CLI share identical wiring."""
    from .cli import build_agent
    return build_agent(backend, model)


async def _run(args):
    agent = _build_agent(args.backend, args.model)
    print(f"Theo voice REPL  ·  Pipecat / Whisper / Piper")
    print(f"  STT:   faster-whisper / {args.whisper_model}")
    print(f"  TTS:   piper / {args.voice}")
    print(f"  Brain: {agent.llm.__class__.__name__} / "
          f"{getattr(agent.llm, 'model', '?')}")
    print(f"  Tools: {len(agent.tools.names())} registered")
    print()
    print("Start talking. Silero VAD detects when you stop and triggers")
    print("transcription. Ctrl+C to quit.\n")

    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        )
    )

    stt = WhisperSTTService(
        model=args.whisper_model,
        device="cpu",
        no_speech_prob=0.4,
    )

    tts = PiperTTSService(
        voice=args.voice,
    )

    theo = TheoAgentService(agent)

    pipeline = Pipeline([
        transport.input(),
        stt,
        theo,
        tts,
        transport.output(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=False,
        ),
    )

    runner = PipelineRunner()
    try:
        await runner.run(task)
    except KeyboardInterrupt:
        await task.queue_frame(EndFrame())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["auto", "claude", "ollama"], default="auto")
    p.add_argument("--model", default=None,
                   help="Brain model. Defaults: claude-opus-4-7 / llama3.1:8b.")
    p.add_argument("--whisper-model", default="base.en",
                   help="faster-whisper model. tiny.en / base.en / small.en / medium.en. Default base.en.")
    p.add_argument("--voice", default="en_US-ryan-high",
                   help="Piper voice id. Run `python -m piper.download_voices --help` to discover more.")
    args = p.parse_args()

    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\n(stopped)")


if __name__ == "__main__":
    main()
