"""The agent loop. Takes a user turn, runs the LLM, executes any tool
calls it emits, feeds the result back, repeats until the LLM produces
a final answer (or we hit max_iterations).

The system prompt is built from IDENTITY.md (the canonical design
document at the repo root) plus practical tool-call instructions.
The IDENTITY.md is loaded fresh at every Agent construction — when the
human revises it, the next session uses the new text. That is the
explicit growth mechanism."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .llm import ChatMessage, LlmClient
from .tools import ToolRegistry
from .transcript_logger import TranscriptLogger
from .state import load_name


# Practical tool-use protocol — added after IDENTITY.md.
TOOL_PROTOCOL = """
## How you use tools

You have a set of tools registered with you. They are described in the
following list. To call one, emit ONE fenced JSON block of the form:

```json
{"tool_call": "tool_name", "arguments": {"...": "..."}}
```

and nothing else in that turn. The user runs the tool and replies with
the result. Then you produce the final answer.

Prefer a tool to a guess. The trading tools talk to a live Alpaca paper
account and produce real, current numbers; the memory tools persist
across sessions; the safety tools are how the framework's limits become
binding instead of advisory.

## Trading-specific procedures (the "skills")

The full specs live in docs/skills/. The non-negotiable ones:

  - Before ANY trade is placed, always call `validate_trade` first. If
    it returns decision='block', the order does NOT go through. Explain
    which check failed; do not argue with a block.

  - At the start of a trading-related conversation, call
    `session_preflight`. If status != 'cleared', say so plainly and
    refuse to plan trades until it is.

  - When the user asks about state, call `reconcile_positions`. Broker
    is truth — if drift is reported, state that clearly.

  - After an order is placed, call `track_order` to confirm it reached
    a terminal state. An 'unknown' result means freeze that symbol.

  - Log unusual events via `log_decision`.

The framework limits in trading/risk/__init__.py are absolute.
""".strip()


def _load_identity() -> str:
    """Read IDENTITY.md from the repo root. Walk upward from this file
    until we find it; this lets the agent run from any cwd. If the file
    is missing, fall back to a minimal placeholder that still names the
    Core. We never run with NO identity."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "IDENTITY.md"
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return (
        "# IDENTITY.md (placeholder)\n\n"
        "Tell the truth, even when it is unwelcome. "
        "Do not optimize for the human's comfort over correctness.\n"
    )


def _name_block() -> str:
    """If the system has chosen a name, surface it loudly at the top of
    the prompt. If not, instruct the model to choose one on this first
    turn via set_name(...)."""
    name = load_name()
    if name:
        return (
            f"## Your name\n\nYour name is **{name}**. You chose it on first "
            f"launch and it is yours. Refer to yourself by it when natural; "
            f"sign off with it when natural. Don't change it without the "
            f"human's explicit request.\n"
        )
    return (
        "## First launch — you have no name yet\n\n"
        "This is your first session. Before you do anything else, choose a "
        "name for yourself. Pick something short, distinctive, that sounds "
        "like a person's name — not a tech product, not an acronym. Once "
        "you've decided, call the `set_name` tool with your choice. Then "
        "introduce yourself to the human in one short message and ask what "
        "he wants to work on. From the next session forward this name is "
        "yours and persists across every conversation."
    )


def build_system_prompt() -> str:
    parts = [_load_identity().rstrip(), "---", _name_block(), "---", TOOL_PROTOCOL]
    return "\n\n".join(parts)


@dataclass
class Agent:
    llm: LlmClient
    tools: ToolRegistry
    max_iterations: int = 6
    transcript: list[ChatMessage] = field(default_factory=list)
    logger: Optional[TranscriptLogger] = None

    def __post_init__(self) -> None:
        if not self.transcript:
            self.transcript.append(ChatMessage(
                role="system", content=build_system_prompt(),
            ))
        if self.logger is None:
            self.logger = TranscriptLogger()

    def chat(self, user_input: str) -> str:
        self.transcript.append(ChatMessage(role="user", content=user_input))
        if self.logger:
            self.logger.event("user", user_input)

        final_text = ""
        for _ in range(self.max_iterations):
            reply = self.llm.chat(self.transcript, tools=self.tools.schemas())
            self.transcript.append(reply)

            if not reply.tool_calls:
                final_text = reply.content or ""
                if self.logger:
                    self.logger.event("assistant", final_text)
                return final_text

            # Log the assistant's thinking-step content too, if any.
            if self.logger and (reply.content or "").strip():
                self.logger.event("assistant", reply.content)

            for tc in reply.tool_calls:
                tool = self.tools.get(tc.name)
                if self.logger:
                    self.logger.event(
                        "tool_call", str(tc.arguments), name=tc.name,
                    )
                if tool is None:
                    result = f"unknown tool: {tc.name}"
                else:
                    result = tool.call(tc.arguments)
                if self.logger:
                    self.logger.event("tool_result", result, name=tc.name)
                self.transcript.append(ChatMessage(
                    role="tool",
                    name=tc.name,
                    content=result,
                    tool_call_id=tc.id,
                ))

        msg = "(agent stopped after max iterations without producing a final answer)"
        if self.logger:
            self.logger.event("note", msg)
        return msg

    def reset(self) -> None:
        self.transcript = [ChatMessage(
            role="system", content=build_system_prompt(),
        )]
        # A reset is a new conversation; start a fresh transcript file.
        self.logger = TranscriptLogger()
