"""Browser-use tool — Theo drives a real browser.

browser-use (https://github.com/browser-use/browser-use) is a Python
library that wraps Playwright + an LLM. You give it a high-level task
and it figures out the click/scroll/type sequence to accomplish it.

Setup:
    pip install browser-use
    playwright install chromium

And one of:
    - OPENAI_API_KEY=...     (uses GPT-4 by default)
    - ANTHROPIC_API_KEY=...  (or this — browser-use auto-detects)
    - For Ollama: set BROWSER_USE_LLM=ollama:llama3.1:8b (or similar)

Honest caveat: browser-use needs an LLM to *reason* about the page.
That LLM is separate from the Claude CLI Theo uses. The cleanest free
path is Ollama locally. Otherwise it's a paid API key for browser-use's
own reasoning. The tool surfaces a clear error when no provider is
configured.

Reference docs: docs/research/browser-use/

Use cases: have Theo grab a price from a site that doesn't expose a
clean API, scrape an article behind JS, fill out a form, navigate a
flow web_fetch can't handle. NOT a substitute for real research; treat
each task as a one-shot operation."""
from __future__ import annotations

import asyncio
import os
from typing import Any

from .base import Tool


def _has_llm_credential() -> str | None:
    """Return the name of the first available LLM provider, or None."""
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("BROWSER_USE_LLM"):
        return "explicit"
    return None


def _run_task(task: str, max_steps: int, headless: bool) -> dict[str, Any]:
    """Run a browser-use Agent against the task. Blocks until done."""
    try:
        from browser_use import Agent, Browser
    except ImportError:
        return {
            "error": "browser-use not installed",
            "install": (
                "pip install browser-use && playwright install chromium "
                "in the python/.venv"
            ),
        }

    provider = _has_llm_credential()
    if provider is None:
        return {
            "error": "no LLM credential for browser-use",
            "fix": (
                "browser-use needs its own LLM to reason about pages. "
                "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or BROWSER_USE_LLM "
                "in the bridge's environment. For free local: install "
                "Ollama and set BROWSER_USE_LLM=ollama:llama3.1:8b."
            ),
        }

    async def _go() -> dict[str, Any]:
        # browser-use's Agent API has shifted across versions; this is
        # a best-effort wrapper compatible with the current shape. If
        # the import works but the call fails, the error surfaces back.
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini")
        except Exception:
            try:
                from langchain_anthropic import ChatAnthropic
                llm = ChatAnthropic(model="claude-sonnet-4-6")
            except Exception as e:
                return {"error": f"could not build LLM client: {e}"}

        try:
            browser = Browser(headless=headless)
            agent = Agent(task=task, llm=llm, browser=browser, max_steps=max_steps)
            result = await agent.run()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

        # Normalize the result — browser-use returns an AgentHistoryList
        # or similar; we want a text + URL summary.
        final_url = getattr(result, "final_url", None)
        out_text = getattr(result, "final_result", None)
        if callable(out_text):
            out_text = out_text()
        return {
            "task": task,
            "final_url": final_url,
            "result": str(out_text) if out_text else None,
            "steps_used": getattr(result, "n_steps", None),
        }

    try:
        return asyncio.run(_go())
    except RuntimeError as e:
        # Already in an event loop (rare here, but be defensive)
        return {"error": f"event loop conflict: {e}"}


def _browser_task(task: str, max_steps: int = 12, headless: bool = True) -> dict[str, Any]:
    """Run a high-level browser task. Returns the result text + final URL."""
    if not task.strip():
        return {"error": "empty task"}
    return _run_task(task, max_steps=int(max_steps), headless=bool(headless))


BROWSER_TASK_TOOL = Tool(
    name="browser_task",
    description=(
        "Drive a real browser to accomplish a high-level task via "
        "browser-use. `task` is plain English ('go to news.ycombinator.com "
        "and tell me the top 3 story titles'). `max_steps` caps the "
        "action budget (default 12). `headless` runs without a visible "
        "window (default true). Slow (10s-2min per task). Use when "
        "web_search + web_fetch can't reach the answer — e.g. content "
        "behind JS, a multi-step flow, a site without a clean API. "
        "Requires browser-use installed and an LLM credential configured. "
        "See docs/research/browser-use/ for setup."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Plain-English task description."},
            "max_steps": {"type": "integer", "description": "Action budget cap. Default 12."},
            "headless": {"type": "boolean", "description": "Run without a visible window. Default true."},
        },
        "required": ["task"],
        "additionalProperties": False,
    },
    handler=_browser_task,
)


def register(registry) -> None:
    registry.register(BROWSER_TASK_TOOL)
