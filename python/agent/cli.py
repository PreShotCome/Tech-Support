"""Interactive CLI for the TechSupport agent.

Defaults to Claude (Opus 4.7) via your Max subscription / Claude Code
auth — no Anthropic API key, no per-token charges. Falls back to Ollama
if `claude` isn't on PATH.

Usage:
    python -m agent.cli                       # interactive REPL
    python -m agent.cli --model claude-sonnet-4-6   # lighter/faster
    python -m agent.cli --backend ollama --model llama3.1:8b   # local LLM

In the REPL:
    /tools     list registered tools
    /reset     clear conversation transcript
    /quit      exit
"""
from __future__ import annotations

import argparse
import sys

from .agent import Agent
from .llm import ClaudeCliClient, OllamaClient
from .llm.claude_client import _claude_available
from .tools import ToolRegistry
from .tools import trading as trading_tools
from .tools import memory as memory_tools
from .tools import system as system_tools


def build_agent(backend: str, model: str | None) -> Agent:
    if backend == "claude":
        llm = ClaudeCliClient(model=model or "claude-opus-4-7")
    elif backend == "ollama":
        llm = OllamaClient(model=model or "llama3.1:8b")
    elif backend == "auto":
        if _claude_available():
            llm = ClaudeCliClient(model=model or "claude-opus-4-7")
        else:
            print("(claude CLI not found; falling back to Ollama)")
            llm = OllamaClient(model=model or "llama3.1:8b")
    else:
        raise ValueError(f"unknown backend {backend!r}")

    registry = ToolRegistry()
    trading_tools.register(registry)
    memory_tools.register(registry)
    system_tools.register(registry)

    return Agent(llm=llm, tools=registry)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["auto", "claude", "ollama"], default="auto",
                   help="Which LLM to use. 'auto' uses claude if installed, else ollama.")
    p.add_argument("--model", default=None,
                   help="Model name. Defaults: 'claude-opus-4-7' for claude, "
                        "'llama3.1:8b' for ollama.")
    args = p.parse_args()

    agent = build_agent(args.backend, args.model)

    backend_name = agent.llm.__class__.__name__
    model_name = getattr(agent.llm, "model", "?") or "(default)"
    print(f"TechSupport agent ready  ·  {backend_name} / {model_name}")
    print(f"Tools: {', '.join(agent.tools.names())}")
    print("Type /quit to exit, /tools to list tools, /reset to clear transcript.\n")

    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in ("/quit", "/exit"):
            break
        if user == "/tools":
            print(f"  {', '.join(agent.tools.names())}")
            continue
        if user == "/reset":
            agent.reset()
            print("  (transcript cleared)")
            continue

        try:
            reply = agent.chat(user)
        except Exception as e:
            print(f"  error: {e.__class__.__name__}: {e}", file=sys.stderr)
            continue
        print(f"agent> {reply}\n")


if __name__ == "__main__":
    main()
