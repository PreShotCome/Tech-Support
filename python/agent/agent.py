"""The agent loop. Takes a user turn, runs the LLM, executes any tool
calls it emits, feeds the result back, repeats until the LLM produces
a final answer (or we hit max_iterations)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .llm import ChatMessage, LlmClient
from .tools import ToolRegistry


SYSTEM_PROMPT = """You are TechSupport, an in-house AI assistant for Ian.

Your superpowers come from the tools registered with you. Always prefer
a tool to a guess: the trading tools talk to a live Alpaca paper account
and produce real, current numbers. Memory tools persist across sessions.

When you call a tool, emit ONE fenced JSON block of the form:
```json
{"tool_call": "tool_name", "arguments": {"...": "..."}}
```
and nothing else in that turn. The user will run the tool and reply
with the result. Then you can use the result to answer.

If no tool is needed, answer directly in plain text. Be concise."""


@dataclass
class Agent:
    llm: LlmClient
    tools: ToolRegistry
    max_iterations: int = 6
    transcript: list[ChatMessage] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.transcript:
            self.transcript.append(ChatMessage(role="system", content=SYSTEM_PROMPT))

    def chat(self, user_input: str) -> str:
        self.transcript.append(ChatMessage(role="user", content=user_input))

        for _ in range(self.max_iterations):
            reply = self.llm.chat(self.transcript, tools=self.tools.schemas())
            self.transcript.append(reply)

            if not reply.tool_calls:
                return reply.content or ""

            for tc in reply.tool_calls:
                tool = self.tools.get(tc.name)
                if tool is None:
                    result = f"unknown tool: {tc.name}"
                else:
                    result = tool.call(tc.arguments)
                self.transcript.append(ChatMessage(
                    role="tool",
                    name=tc.name,
                    content=result,
                    tool_call_id=tc.id,
                ))

        return ("(agent stopped after max iterations without producing a "
                "final answer)")

    def reset(self) -> None:
        self.transcript = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
