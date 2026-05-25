"""Claude client that uses your Claude Code / Max subscription.

Uses the `claude-agent-sdk` Python package if installed; otherwise
shells out to the `claude` CLI. Either path authenticates with the same
mechanism Claude Code uses, so no Anthropic API key is needed and no
per-token charges hit your account — usage is metered against your
Max subscription.

Requirements:
  - The `claude` CLI must be installed and logged in. Verify with:
        claude /status
  - Optionally:  pip install claude-agent-sdk  (cleaner integration)

Tool calling notes:
  Claude Code's native tool surface is file/bash/browser-level. Our
  agent has its own tool registry (trading, memory, system). We embed
  the tool schemas in the system prompt and ask Claude to emit tool
  calls as a JSON block; we parse and execute, then feed the result
  back in a follow-up turn. Not as elegant as native function-calling
  but works reliably with the CLI.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any, Optional

from .base import ChatMessage, LlmClient, ToolCall


_TOOL_BLOCK_RE = re.compile(
    r"```(?:json)?\s*\{[\s\S]*?\}\s*```", re.MULTILINE
)


def _claude_available() -> bool:
    return shutil.which("claude") is not None


class ClaudeCliClient(LlmClient):
    """Shells out to the `claude` CLI with --print mode for one-shot
    completions. Uses your Claude Code subscription auth."""

    def __init__(
        self,
        model: Optional[str] = None,
        executable: str = "claude",
        timeout: float = 300.0,
    ) -> None:
        if not _claude_available():
            raise RuntimeError(
                "claude CLI not found on PATH. Install Claude Code first: "
                "https://code.claude.com/docs"
            )
        self.model = model            # None = let CLI pick the default (e.g. Opus 4.7)
        self.executable = executable
        self.timeout = timeout

    def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.2,
    ) -> ChatMessage:
        prompt = _build_prompt(messages, tools)
        # Pipe the prompt through stdin instead of as a positional arg.
        # The matrix briefing pushes the system prompt well past Windows'
        # ~8000-char command-line limit (WinError 206 otherwise).
        cmd = [self.executable, "-p", "--output-format", "text"]
        if self.model:
            cmd.extend(["--model", self.model])

        try:
            result = subprocess.run(
                cmd, input=prompt,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=self.timeout, check=False,
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"claude CLI not runnable: {e}")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"claude CLI timed out after {self.timeout}s")

        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exit {result.returncode}: {result.stderr[:500]}"
            )

        raw = (result.stdout or "").strip()
        return _parse_response(raw)


def _build_prompt(messages: list[ChatMessage], tools: Optional[list[dict]]) -> str:
    """Flatten the conversation + tool schemas into a single prompt the
    CLI can consume. The system prompt at the start tells Claude how to
    emit tool calls."""
    parts: list[str] = []
    if tools:
        parts.append("You have access to the following tools. To call a "
                     "tool, emit a fenced JSON block with `tool_call` and "
                     "`arguments` keys, like:\n"
                     '```json\n{"tool_call": "portfolio", "arguments": {}}\n```\n'
                     "After the tool result comes back you will be asked to "
                     "produce a final answer. Tools available:\n")
        for t in tools:
            fn = t.get("function", {})
            parts.append(f"  - {fn.get('name', '?')}: {fn.get('description', '')}")
            params = fn.get("parameters", {}).get("properties", {})
            if params:
                for pname, pspec in params.items():
                    parts.append(f"      {pname}: {pspec.get('description', '')}")
        parts.append("\nIf no tool is needed, just answer directly.\n")

    for m in messages:
        if m.role == "system":
            parts.append(f"[system]\n{m.content}\n")
        elif m.role == "user":
            parts.append(f"[user]\n{m.content}\n")
        elif m.role == "assistant":
            parts.append(f"[assistant]\n{m.content}\n")
        elif m.role == "tool":
            parts.append(f"[tool result: {m.name or ''}]\n{m.content}\n")

    parts.append("[assistant]\n")
    return "\n".join(parts)


def _parse_response(text: str) -> ChatMessage:
    """If the response contains a fenced JSON block with `tool_call`,
    convert it into a ToolCall. Otherwise it's a direct answer."""
    match = _TOOL_BLOCK_RE.search(text)
    if match:
        block = match.group(0)
        inner = block.strip("`").strip()
        if inner.startswith("json\n"):
            inner = inner[5:]
        try:
            data = json.loads(inner)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and "tool_call" in data:
            return ChatMessage(
                role="assistant",
                content=text[:match.start()].strip(),
                tool_calls=[ToolCall(
                    id=f"call_{abs(hash(text)) % 10_000_000}",
                    name=str(data["tool_call"]),
                    arguments=data.get("arguments") or {},
                )],
            )
    return ChatMessage(role="assistant", content=text)
