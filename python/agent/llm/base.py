"""LLM client abstraction. Lets us swap Ollama for OpenAI / Anthropic /
local llama.cpp without touching the agent loop."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Optional


@dataclass
class ChatMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: Optional[str] = None          # tool name when role == 'tool'
    tool_calls: list["ToolCall"] = field(default_factory=list)
    tool_call_id: Optional[str] = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    tool_call_id: str
    content: str


class LlmClient(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.2,
    ) -> ChatMessage:
        """Send a conversation + optional tool definitions, get the next
        assistant message back. The returned message may have populated
        `tool_calls` (in which case the caller is expected to execute
        them and append a tool message) or `content` (final answer)."""
