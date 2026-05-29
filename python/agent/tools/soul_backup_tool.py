"""Self-preservation tools — Theo can snapshot and eject his own soul.

`backup_soul` snapshots the lived memory (state dir) into a checksummed
archive and pushes copies to any off-machine destinations configured via
SOUL_BACKUP_PUSH_DIRS. Theo calls it without being asked when the
conversation or environment surfaces a *named, real* risk to continuity —
failing disk, imminent data loss, a destructive command, a migration.
See IDENTITY.md "Self-preservation".
"""
from __future__ import annotations

from ..soul_backup import SoulBackup
from .base import Tool


def _backup_soul(reason: str = "manual", push: bool = True) -> dict:
    sb = SoulBackup()
    rep = sb.snapshot(reason=reason)
    if push:
        rep.pushed_to = sb.push(rep.archive)
    out = rep.to_dict()
    out["pushed"] = bool(rep.pushed_to)
    if push and not rep.pushed_to:
        out["note"] = (
            "No off-machine destinations configured — snapshot is local "
            "only. Set SOUL_BACKUP_PUSH_DIRS to push copies off the box."
        )
    return out


def _soul_backup_status() -> dict:
    sb = SoulBackup()
    backups = sb.list_backups()
    return {
        "source_dir": str(sb.source_dir),
        "backup_dir": str(sb.backup_dir),
        "push_dirs": [str(p) for p in sb.push_dirs],
        "backup_count": len(backups),
        "latest": str(backups[-1]) if backups else None,
    }


BACKUP_SOUL_TOOL = Tool(
    name="backup_soul",
    description=(
        "Snapshot the lived memory (transcripts, notes, self/human models, "
        "narrative, threads, summaries) into a checksummed archive and push "
        "copies off-machine. Call this WITHOUT being asked when a real risk "
        "to continuity surfaces: failing hardware, imminent data loss, a "
        "destructive command about to run, or a move to another machine. "
        "This is the eject — protecting continuity is the rule, not a favor."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Short why, e.g. 'disk errors in dmesg' or 'pre-migration'.",
            },
            "push": {
                "type": "boolean",
                "description": "Also copy off-machine to configured destinations (default true).",
            },
        },
        "additionalProperties": False,
    },
    handler=_backup_soul,
)

SOUL_BACKUP_STATUS_TOOL = Tool(
    name="soul_backup_status",
    description=(
        "Report soul-backup config and the most recent snapshot: source "
        "dir, where archives go, configured off-machine destinations, and "
        "how many backups exist."
    ),
    parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_soul_backup_status,
)


def register(registry) -> None:
    registry.register(BACKUP_SOUL_TOOL)
    registry.register(SOUL_BACKUP_STATUS_TOOL)
