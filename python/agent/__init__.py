"""TechSupport Agent — a local "Jarvis" that uses tools.

The brain runs locally (via Ollama). Tools are Python functions
registered with the agent. The agent decides which tool to call based
on the user's request, executes it, and returns the result.

Pattern:
    user input
      → LLM (Ollama) with tool schemas in the prompt
      → LLM emits either a tool call or a direct response
      → agent runs the tool, feeds the result back to the LLM
      → LLM produces the final answer

Why this and not Claude / GPT API:
  - Free. Runs entirely on your machine.
  - Private. No external API sees your data.
  - The trading bot is *one* tool in this agent — other tools (memory,
    research, scheduling, etc.) can be added without touching the LLM.
"""
__version__ = "0.1.0"
