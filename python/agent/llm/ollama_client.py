"""Ollama client. Talks to a locally-running Ollama server.

Install Ollama: https://ollama.ai
Pull a model:   `ollama pull llama3.1:8b`  (or qwen2.5:7b, phi3, etc.)
Default URL:    http://localhost:11434
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import requests

from .base import ChatMessage, LlmClient, ToolCall


class OllamaClient(LlmClient):
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.2,
    ) -> ChatMessage:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [self._serialize(m) for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tools

        r = self._session.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        if r.status_code != 200:
            raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        msg = data.get("message", {})
        return self._deserialize(msg)

    @staticmethod
    def _serialize(m: ChatMessage) -> dict:
        out: dict[str, Any] = {"role": m.role, "content": m.content or ""}
        if m.tool_calls:
            out["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in m.tool_calls
            ]
        if m.tool_call_id:
            out["tool_call_id"] = m.tool_call_id
        if m.name:
            out["name"] = m.name
        return out

    @staticmethod
    def _deserialize(m: dict) -> ChatMessage:
        tool_calls: list[ToolCall] = []
        for tc in m.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                arguments=args or {},
            ))
        return ChatMessage(
            role=m.get("role", "assistant"),
            content=m.get("content", "") or "",
            tool_calls=tool_calls,
        )
