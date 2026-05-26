# TechSupport Agent — your local Jarvis

A small, local agent that lets you talk to your trading system (and
anything else you give it tools for) in natural language. The brain is
Claude Opus 4.7 by default, routed through the `claude` CLI so it uses
your Max subscription instead of metered API tokens.

Architecture:

```
              ┌──────────────────────────────┐
              │       agent.cli REPL          │
              └─────────────┬─────────────────┘
                            │
              ┌─────────────▼─────────────────┐
              │     agent.Agent (loop)         │
              └─────┬──────────────────┬──────┘
                    │                  │
       ┌────────────▼───┐  ┌───────────▼─────────┐
       │  LlmClient     │  │   ToolRegistry      │
       │  • ClaudeCli   │  │   • trading.*       │
       │  • Ollama      │  │   • memory.*        │
       │                │  │   • system.*        │
       └────────────────┘  └─────────────────────┘
```

The agent loop:
1. Send the conversation + tool schemas to the LLM.
2. If the LLM responds with a tool call (a fenced JSON block), execute
   the tool and feed the result back in.
3. If the LLM responds with text, that's the final answer.

## Setup

```powershell
# Claude Code must already be installed and logged in
claude /status

# In your venv:
cd C:\src\Tech-Support\python
.\.venv\Scripts\activate
pip install -e .

# Sanity check the CLI is on PATH:
where.exe claude

# Run it:
python -m agent.cli
```

## What you can ask it

```
you> What's my paper account doing?
agent> [calls portfolio tool]
agent> Equity $100,245.12, 31 positions. Up 0.25% since deposit. ...

you> Plan a rebalance, show me only trades bigger than $200
agent> [calls rebalance_plan with min_trade_dollars=200]
agent> 4 trades would happen: ...

you> How's the shadow ML model doing vs the live basket?
agent> [calls shadow_report]
agent> 3 snapshots logged so far; cumulative alpha −0.4%. Too early to call.

you> Note that I prefer monthly rebalances over weekly.
agent> [calls note]
agent> noted.

you> What do I prefer?
agent> [calls recall]
agent> You prefer monthly rebalances over weekly.
```

## Backends

By default `--backend auto` picks `claude` if installed, else Ollama.

| Backend | Model defaults | Cost | Use when |
|---|---|---|---|
| `claude` | `claude-opus-4-7` | Max subscription | You have Claude Code installed. Best reasoning. |
| `claude` | `claude-sonnet-4-6` | Max subscription | Faster, lighter. |
| `ollama` | `llama3.1:8b` | Free (local) | No Claude install. Limited reasoning. |

Switch models any time:
```
python -m agent.cli --model claude-sonnet-4-6
python -m agent.cli --backend ollama --model qwen2.5:7b
```

## Adding your own tool

Tools are Python functions plus a JSON-Schema description. Drop a new
file in `python/agent/tools/`:

```python
# python/agent/tools/calendar.py
from .base import Tool

def _add_event(title: str, when: str) -> str:
    # ... your code ...
    return f"added {title!r} at {when}"

ADD_EVENT = Tool(
    name="add_event",
    description="Add an event to my calendar.",
    parameters_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "when":  {"type": "string", "description": "ISO 8601 datetime."},
        },
        "required": ["title", "when"],
    },
    handler=_add_event,
)

def register(registry):
    registry.register(ADD_EVENT)
```

Then add `from .tools import calendar as calendar_tools` to `cli.py`
and call `calendar_tools.register(registry)`. Tool ships with the
agent on the next CLI start.

## What this is NOT

- Not a chatbot wrapper around the Anthropic API. The Claude backend
  uses your existing CLI auth (Max subscription) and incurs no
  per-token charges.
- Not a replacement for Claude Code itself. Claude Code is the
  developer-facing tool; Theo is a domain-specific agent with Proteus
  (the trading bot) wired in.
- Not autonomous. The agent never does anything on its own — it only
  responds to your turns. To run things on a schedule, use Task
  Scheduler against `paper_runner` / `paper_shadow` as before.
