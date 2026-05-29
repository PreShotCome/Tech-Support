import os

from .base import LlmClient, ChatMessage, ToolCall, ToolResult
from .ollama_client import OllamaClient
from .claude_client import ClaudeCliClient, _claude_available

__all__ = [
    "LlmClient", "ChatMessage", "ToolCall", "ToolResult",
    "OllamaClient", "ClaudeCliClient", "build_default_client",
]


def build_default_client(backend: str | None = None) -> LlmClient:
    """Construct the LLM client for non-interactive entrypoints (server,
    bridge) that have no argparse to drive backend selection.

    Selection mirrors cli.py's `build_agent`, but reads the environment
    so the same code runs on the desktop (Claude) and on the GPU box
    (Ollama) with only env changes:

      LLM_BACKEND   claude | ollama | auto   (default: auto)
      OLLAMA_MODEL  e.g. qwen2.5:32b         (read by OllamaClient)
      OLLAMA_HOST   e.g. http://127.0.0.1:11434

    'auto' uses Claude when the CLI is present, else falls back to
    Ollama — so a box with no `claude` on PATH lands on the local model
    automatically.
    """
    backend = (backend or os.environ.get("LLM_BACKEND", "auto")).lower()
    if backend == "claude":
        return ClaudeCliClient(model=os.environ.get("CLAUDE_MODEL") or "claude-opus-4-7")
    if backend == "ollama":
        return OllamaClient()
    if backend == "auto":
        if _claude_available():
            return ClaudeCliClient(model=os.environ.get("CLAUDE_MODEL") or "claude-opus-4-7")
        return OllamaClient()
    raise ValueError(f"unknown LLM_BACKEND {backend!r}")
