"""Theo — Ian's long-term thinking partner. Runs locally, uses tools.

The brain runs via the local `claude` CLI by default (Max subscription,
no API charges); Ollama is the local fallback. Tools are Python
functions registered with the agent. Theo decides which tool to call
based on the user's request, executes it, and returns the result.

Pattern:
    user input
      → LLM with tool schemas in the prompt
      → LLM emits either a tool call or a direct response
      → agent runs the tool, feeds the result back to the LLM
      → LLM produces the final answer

Why this and not a hosted Claude / GPT API:
  - Free, via the Max subscription's CLI auth.
  - Private. State (transcripts, memory, identity) lives on disk.
  - Proteus (the trading bot) is *one* capability Theo has — other
    tools (memory, research, OSINT, image gen, etc.) can be added
    without touching the LLM.
"""
__version__ = "0.1.0"
