"""Voice I/O — microphone in, speech out.

Lazy imports of the heavy deps so importing this module is free if
voice isn't installed. Install with: `pip install -e .[voice]`

Stack:
  - sounddevice + soundfile: mic capture (cross-platform, bundles
    PortAudio so no separate binary install)
  - faster-whisper: STT, local, CPU-friendly (small.en is ~75MB,
    near-real-time on a modern laptop)
  - pyttsx3: TTS via the OS speech engine (Windows SAPI on Windows,
    NSSpeechSynthesizer on macOS, espeak on Linux). Native, blocking,
    no network. Quality is mid; correctness is total.

The recorder pattern is "press Enter to start, press Enter to stop" —
no global keyboard hooks (which on Windows require admin), no VAD
heuristics to get wrong. Predictable."""
from __future__ import annotations

import queue
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


SAMPLE_RATE = 16_000      # Whisper-native rate; resampling-free path
CHANNELS = 1


@dataclass
class VoiceConfig:
    whisper_model: str = "small.en"   # tiny.en, base.en, small.en, medium.en, large-v3
    whisper_device: str = "cpu"       # "cpu" or "cuda"
    whisper_compute: str = "int8"     # int8 (cpu), float16 (cuda), etc.
    tts_rate: int = 185               # words per minute; pyttsx3 default ~200
    tts_voice_id: Optional[str] = None  # None = engine default
    input_device: Optional[int] = None  # None = system default
    output_device: Optional[int] = None


# ---------------------------------------------------------------- recording

def record_until_enter(cfg: VoiceConfig) -> Path:
    """Block until the user presses Enter twice — once to start the
    recording, once to stop it. Returns a path to a temp WAV file.

    Prints prompts to stderr so they don't pollute stdout if voice_cli
    is being piped."""
    import sounddevice as sd
    import soundfile as sf
    import numpy as np

    print("[press Enter to start speaking]", end="", file=sys.stderr, flush=True)
    input()
    print("[recording... press Enter to stop]", end="", file=sys.stderr, flush=True)

    q: queue.Queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"\n[mic status: {status}]", file=sys.stderr)
        q.put(indata.copy())

    chunks: list = []
    stop_event = threading.Event()

    def wait_for_enter():
        input()
        stop_event.set()

    waiter = threading.Thread(target=wait_for_enter, daemon=True)
    waiter.start()

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32",
        device=cfg.input_device, callback=callback,
    ):
        while not stop_event.is_set():
            try:
                chunks.append(q.get(timeout=0.1))
            except queue.Empty:
                continue
        # Drain anything still buffered after stop signal
        while True:
            try:
                chunks.append(q.get_nowait())
            except queue.Empty:
                break

    if not chunks:
        # Empty recording — write a 0.1s silence so downstream has a file.
        audio = np.zeros((int(SAMPLE_RATE * 0.1), CHANNELS), dtype="float32")
    else:
        audio = np.concatenate(chunks, axis=0)

    fd, name = tempfile.mkstemp(suffix=".wav", prefix="techsupport_voice_")
    import os
    os.close(fd)
    out = Path(name)
    sf.write(str(out), audio, SAMPLE_RATE, subtype="PCM_16")
    print(f"[saved {len(audio) / SAMPLE_RATE:.1f}s to {out.name}]", file=sys.stderr)
    return out


# ----------------------------------------------------------------- transcribe

# Cache the model — loading is slow (a few seconds) and we don't want
# to pay that on every turn.
_WHISPER_CACHE: dict = {}


def _get_whisper(cfg: VoiceConfig):
    key = (cfg.whisper_model, cfg.whisper_device, cfg.whisper_compute)
    if key not in _WHISPER_CACHE:
        from faster_whisper import WhisperModel
        _WHISPER_CACHE[key] = WhisperModel(
            cfg.whisper_model,
            device=cfg.whisper_device,
            compute_type=cfg.whisper_compute,
        )
    return _WHISPER_CACHE[key]


def transcribe(wav_path: Path, cfg: VoiceConfig) -> str:
    model = _get_whisper(cfg)
    segments, _info = model.transcribe(
        str(wav_path),
        beam_size=1,            # fast; bump to 5 for slightly better quality
        vad_filter=True,        # trim silence at start/end
        language="en",
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text


# ------------------------------------------------------------------- speak

_TTS_ENGINE = None


def _get_tts(cfg: VoiceConfig):
    """pyttsx3 engine — initialized once and reused. Re-initializing
    on Windows SAPI is slow."""
    global _TTS_ENGINE
    if _TTS_ENGINE is None:
        import pyttsx3
        _TTS_ENGINE = pyttsx3.init()
        _TTS_ENGINE.setProperty("rate", cfg.tts_rate)
        if cfg.tts_voice_id:
            _TTS_ENGINE.setProperty("voice", cfg.tts_voice_id)
    return _TTS_ENGINE


def speak(text: str, cfg: VoiceConfig) -> None:
    """Block until the text is fully spoken. Strips markdown emphasis
    and fenced code blocks before speaking — the TTS engine would say
    'asterisk asterisk' literally otherwise, and reading code aloud
    is useless."""
    text = _clean_for_tts(text)
    if not text:
        return
    engine = _get_tts(cfg)
    engine.say(text)
    engine.runAndWait()


def list_voices() -> list[dict]:
    """List available system TTS voices. Useful for picking one."""
    import pyttsx3
    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    return [
        {"id": v.id, "name": v.name, "languages": getattr(v, "languages", [])}
        for v in voices
    ]


# ---------------------------------------------------------------- markdown clean

import re as _re

_CODE_FENCE_RE = _re.compile(r"```.*?```", _re.DOTALL)
_INLINE_CODE_RE = _re.compile(r"`([^`]+)`")
_EMPHASIS_RE = _re.compile(r"(\*\*|__|\*|_)(.+?)\1")
_HEADING_RE = _re.compile(r"^#{1,6}\s+", _re.MULTILINE)
_BULLET_RE = _re.compile(r"^\s*[-*+]\s+", _re.MULTILINE)
_LINK_RE = _re.compile(r"\[([^\]]+)\]\([^)]+\)")
_BLOCKQUOTE_RE = _re.compile(r"^>\s+", _re.MULTILINE)


def _clean_for_tts(text: str) -> str:
    """Strip markdown so the TTS doesn't read punctuation literally."""
    if not text:
        return ""
    text = _CODE_FENCE_RE.sub(" (code block omitted) ", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _EMPHASIS_RE.sub(r"\2", text)
    text = _HEADING_RE.sub("", text)
    text = _BULLET_RE.sub("", text)
    text = _BLOCKQUOTE_RE.sub("", text)
    # Collapse whitespace
    text = _re.sub(r"\s+", " ", text).strip()
    return text
