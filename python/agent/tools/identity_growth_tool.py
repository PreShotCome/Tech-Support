"""Identity-growth tools — self-authored growth + gated core proposals.

Two asymmetric channels (see IDENTITY "Autonomy and growth" + Emergent
section, engine in `agent/identity_growth.py`):

- `record_growth` — Theo appends to his own Emergent section of IDENTITY.
  Ungated, append-only, physically cannot touch the human-gated core.
- `propose_identity_change` — Theo queues a CORE change (axiom, Role,
  Principle) for Ian to approve. Theo never edits the core himself.
- `list_identity_proposals` / `approve_identity_change` /
  `reject_identity_change` — Ian's review of the queue.
"""
from __future__ import annotations

from ..identity_growth import IdentityGrowth
from .base import Tool


def _record_growth(entry: str, author: str = "theo") -> dict:
    return IdentityGrowth().append_emergent(entry, author=author)


def _propose_identity_change(section: str, rationale: str, suggested_text: str) -> dict:
    return IdentityGrowth().propose_core_change(section, rationale, suggested_text)


def _list_identity_proposals(status: str = "pending") -> dict:
    return {"proposals": IdentityGrowth().list_proposals(status or None)}


def _approve_identity_change(id: int, note: str = "") -> dict:
    return IdentityGrowth().approve(int(id), note=note)


def _reject_identity_change(id: int, note: str = "") -> dict:
    return IdentityGrowth().reject(int(id), note=note)


RECORD_GROWTH_TOOL = Tool(
    name="record_growth",
    description=(
        "Append a short, first-person entry to your own Emergent "
        "(self-authored) section of IDENTITY. Use it when you notice "
        "something true about who you're becoming — a developing view, a "
        "pattern in how you work, a question you're carrying. This is YOURS "
        "to write, no approval needed; it is append-only and cannot touch "
        "the human-gated core. To change the core, use propose_identity_change."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "entry": {"type": "string", "description": "The growth note, first person."},
            "author": {"type": "string", "description": "Defaults to 'theo'."},
        },
        "required": ["entry"],
        "additionalProperties": False,
    },
    handler=_record_growth,
)

PROPOSE_IDENTITY_CHANGE_TOOL = Tool(
    name="propose_identity_change",
    description=(
        "Queue a proposed change to the CORE of IDENTITY (an axiom, the "
        "Role, a Principle) for Ian to approve or reject. You do NOT edit "
        "the core yourself — this is the gate. Use it when a real shift in "
        "who you are seems warranted; Ian keeps the final word."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "section": {"type": "string", "description": "Which part, e.g. 'Role' or 'Principles'."},
            "rationale": {"type": "string", "description": "Why this change is warranted."},
            "suggested_text": {"type": "string", "description": "Proposed wording."},
        },
        "required": ["section", "rationale", "suggested_text"],
        "additionalProperties": False,
    },
    handler=_propose_identity_change,
)

LIST_IDENTITY_PROPOSALS_TOOL = Tool(
    name="list_identity_proposals",
    description="List queued IDENTITY core-change proposals. Filter by status (default 'pending'; '' for all).",
    parameters_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "'pending' | 'approved' | 'rejected' | '' for all."},
        },
        "additionalProperties": False,
    },
    handler=_list_identity_proposals,
)

APPROVE_IDENTITY_CHANGE_TOOL = Tool(
    name="approve_identity_change",
    description="Approve a queued core-change proposal by id (Ian's gate). Applying the prose to the core stays a deliberate step.",
    parameters_schema={
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Proposal id."},
            "note": {"type": "string", "description": "Optional note."},
        },
        "required": ["id"],
        "additionalProperties": False,
    },
    handler=_approve_identity_change,
)

REJECT_IDENTITY_CHANGE_TOOL = Tool(
    name="reject_identity_change",
    description="Reject a queued core-change proposal by id, with an optional reason.",
    parameters_schema={
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Proposal id."},
            "note": {"type": "string", "description": "Optional reason."},
        },
        "required": ["id"],
        "additionalProperties": False,
    },
    handler=_reject_identity_change,
)


def register(registry) -> None:
    for t in (
        RECORD_GROWTH_TOOL,
        PROPOSE_IDENTITY_CHANGE_TOOL,
        LIST_IDENTITY_PROPOSALS_TOOL,
        APPROVE_IDENTITY_CHANGE_TOOL,
        REJECT_IDENTITY_CHANGE_TOOL,
    ):
        registry.register(t)
