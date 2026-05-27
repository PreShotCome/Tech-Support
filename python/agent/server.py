"""FastAPI HTTP bridge around the Agent — exposes chat() over HTTP so
other processes (Flutter app, scripts, CLIs in other languages) can
talk to the same in-process Agent without re-implementing the loop.

Sessions are kept in an in-memory dict keyed by session_id. That means
they live only as long as this process — restart drops them. Persistent
memory still works because the Agent's tools (notes, embeddings,
typed memory) write to ~/.techsupport_agent/. The session dict is just
for transcript continuity within a process lifetime.

Run:
    python -m agent.server
    THEO_PORT=9000 python -m agent.server

Requires the `agent` extra (fastapi + uvicorn[standard]).
"""
from __future__ import annotations

import os
from typing import Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agent import Agent
from .llm import build_default_client
from .tools._all import build_full_registry


app = FastAPI(title="Theo HTTP bridge")

# session_id -> Agent. In-memory only; restart drops these. Each Agent
# carries its own transcript + logger; durable memory (notes,
# embeddings, typed memory) lives in ~/.techsupport_agent/ and is
# shared across sessions.
_AGENTS: Dict[str, Agent] = {}


def _get_or_create(session_id: str) -> Agent:
    a = _AGENTS.get(session_id)
    if a is None:
        a = Agent(llm=build_default_client(), tools=build_full_registry())
        _AGENTS[session_id] = a
    return a


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatReply(BaseModel):
    reply: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "active_sessions": len(_AGENTS)}


@app.post("/chat", response_model=ChatReply)
def chat(req: ChatRequest) -> ChatReply:
    if not req.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id required")
    agent = _get_or_create(req.session_id)
    try:
        reply = agent.chat(req.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    return ChatReply(reply=reply)


def main() -> None:
    import uvicorn
    port = int(os.environ.get("THEO_PORT", "8765"))
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
