"""Tool interface and registry.

A Tool is a Python callable plus a JSON-schema description the LLM uses
to decide whether and how to call it. The registry collects tools and
exposes a list of definitions in the format the LLM expects (OpenAI-
compatible, which Ollama also accepts)."""
from __future__ import annotations

import inspect
import json
import traceback
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters_schema: dict      # JSON Schema for the arguments
    handler: Callable[..., Any]

    def call(self, arguments: dict[str, Any]) -> str:
        """Run the tool. Returns a string the agent feeds back to the LLM."""
        try:
            result = self.handler(**arguments)
        except TypeError as e:
            return f"tool '{self.name}' bad arguments: {e}"
        except Exception as e:
            return (
                f"tool '{self.name}' failed: {e.__class__.__name__}: {e}\n"
                f"{traceback.format_exc(limit=3)}"
            )
        if isinstance(result, (dict, list)):
            try:
                return json.dumps(result, default=str, indent=2)
            except TypeError:
                return str(result)
        return str(result)

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return sorted(self._tools.keys())
