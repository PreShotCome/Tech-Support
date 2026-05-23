"""Firebase / Firestore bridge.

This is the missing half of the Flutter chat app. The Flutter UI writes
user messages to Firestore; this script listens for them in real time,
runs each through the local Agent, and writes the response back to the
same collection so the UI shows it.

Architecture:

    Flutter UI ── writes user msg ──► Firestore
                                       │
                              this script subscribes
                                       │
                                  Agent.chat()
                                       │
                                writes response ──► Firestore
                                                      │
                                       Flutter UI sees it via stream

Firestore document layout:

    conversations/{userId}/messages/{messageId} = {
        role:        "user" | "assistant",
        content:     string,
        created_at:  server timestamp,
        processed:   bool,    # bridge marks true once a user msg has been answered
    }

The bridge keeps ONE Agent instance per userId, so each user has their
own continuous conversation. Memory tools (notes, transcripts) are
shared globally on the host machine — single-user installs.

Setup: see flutter_app/README.md. You need:
  - A Firebase project with Firestore enabled
  - A service-account JSON for server access
  - GOOGLE_APPLICATION_CREDENTIALS pointing at it

Run:
    python -m agent.bridges.firebase_bridge
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
from typing import Optional

from ..agent import Agent
from ..cli import build_agent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["auto", "claude", "ollama"], default="auto")
    p.add_argument("--model", default=None)
    p.add_argument("--project-id", default=os.environ.get("FIREBASE_PROJECT_ID"),
                   help="Firebase project ID. Default: $FIREBASE_PROJECT_ID")
    args = p.parse_args()

    if not args.project_id:
        print("ERROR: --project-id or FIREBASE_PROJECT_ID env var required.", file=sys.stderr)
        sys.exit(2)
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS env var must point at "
              "your Firebase service-account JSON file.", file=sys.stderr)
        sys.exit(2)

    try:
        from google.cloud import firestore
    except ImportError:
        print("ERROR: google-cloud-firestore not installed.", file=sys.stderr)
        print("Install: pip install google-cloud-firestore", file=sys.stderr)
        sys.exit(2)

    db = firestore.Client(project=args.project_id)
    print(f"Connected to Firebase project {args.project_id!r}.")

    # One Agent per user_id (path: conversations/{user_id}/messages)
    agents: dict[str, Agent] = {}
    lock = threading.Lock()

    def agent_for(user_id: str) -> Agent:
        with lock:
            if user_id not in agents:
                print(f"Spawning Agent for user {user_id}")
                agents[user_id] = build_agent(args.backend, args.model)
            return agents[user_id]

    def handle_message(user_id: str, doc_ref, data: dict) -> None:
        content = (data.get("content") or "").strip()
        if not content:
            doc_ref.update({"processed": True, "skipped_reason": "empty"})
            return
        try:
            reply = agent_for(user_id).chat(content)
        except Exception as e:
            print(f"  agent error for user {user_id}: {e}")
            reply = f"(internal error: {type(e).__name__}: {e})"
        msgs = db.collection("conversations").document(user_id).collection("messages")
        msgs.add({
            "role": "assistant",
            "content": reply,
            "created_at": firestore.SERVER_TIMESTAMP,
            "processed": True,
        })
        doc_ref.update({"processed": True})
        print(f"  responded to {user_id}: {reply[:80]!r}")

    # Watch every user's messages collection via collection_group
    # filtered to role=user, processed=false.
    def on_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name != "ADDED":
                continue
            doc = change.document
            data = doc.to_dict() or {}
            if data.get("role") != "user" or data.get("processed"):
                continue
            # Path is conversations/{user_id}/messages/{msg_id}
            user_id = doc.reference.parent.parent.id
            print(f"New message from {user_id}: {data.get('content', '')[:60]!r}")
            handle_message(user_id, doc.reference, data)

    query = db.collection_group("messages")
    # Snapshot listener; runs in a background thread.
    listener = query.on_snapshot(on_snapshot)
    print("Listening for new messages. Ctrl+C to stop.")

    stop = threading.Event()
    def shutdown(signum, frame):
        print("\nShutting down...")
        stop.set()
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        while not stop.is_set():
            time.sleep(1.0)
    finally:
        listener.unsubscribe()
        print("Listener stopped.")


if __name__ == "__main__":
    main()
