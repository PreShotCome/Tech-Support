"""Theo-soul: identity growth — self-authored section + gated core proposals.

Per IDENTITY v3.x, Theo grows on the record. Two channels, deliberately
asymmetric:

  1. Self-authored growth (UNGATED, bounded): Theo appends timestamped
     entries to the "Emergent — self-authored" section of IDENTITY.md,
     between the EMERGENT markers. He writes this himself, every session,
     no approval needed. It is append-only and NEVER touches anything
     outside the markers, so the human-authored core is physically out of
     reach of this path. Fully traceable — the changes show up in git.

  2. Gated core proposals (GATED): when Theo thinks the CORE should change
     (an axiom, the Role, a Principle), he does NOT edit it. He queues a
     proposal for Ian to approve or reject. The gate is the approval;
     applying an approved change to core prose stays a deliberate step.

Self-contained, stdlib-only. The model (whatever backend) drives it via
tools; the engine is plain file ops. Run the self-test:

    python -m agent.identity_growth
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

EMERGENT_BEGIN = "<!-- EMERGENT:BEGIN -->"
EMERGENT_END = "<!-- EMERGENT:END -->"


def _default_identity_path() -> Path:
    env = os.environ.get("THEO_IDENTITY_PATH")
    if env:
        return Path(env)
    # python/agent/identity_growth.py -> parents[2] == repo root.
    return Path(__file__).resolve().parents[2] / "IDENTITY.md"


def _default_proposals_path() -> Path:
    env = os.environ.get("THEO_IDENTITY_PROPOSALS")
    if env:
        return Path(env)
    return Path.home() / ".techsupport_agent" / "identity_proposals.jsonl"


class IdentityGrowth:
    def __init__(
        self,
        identity_path: Optional[Path] = None,
        proposals_path: Optional[Path] = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.identity_path = Path(identity_path) if identity_path else _default_identity_path()
        self.proposals_path = (
            Path(proposals_path) if proposals_path else _default_proposals_path()
        )
        self._clock = clock

    def _ts(self) -> str:
        return self._clock().strftime("%Y-%m-%dT%H:%M:%SZ")

    # --------------------------------------------- self-authored growth (ungated)

    def append_emergent(self, entry: str, author: str = "theo") -> dict:
        """Append a timestamped growth entry inside the EMERGENT markers.
        Append-only; never modifies anything outside the markers."""
        entry = (entry or "").strip()
        if not entry:
            raise ValueError("empty growth entry")
        ts = self._ts()
        block = f"\n#### {ts} · {author}\n\n{entry}\n"

        text = (
            self.identity_path.read_text(encoding="utf-8")
            if self.identity_path.exists() else ""
        )
        if EMERGENT_END in text:
            text = text.replace(EMERGENT_END, f"{block}\n{EMERGENT_END}", 1)
        else:
            section = (
                "\n\n## Emergent — self-authored\n\n"
                "> Theo authors this section himself, appended over time. The "
                "core above is human-gated; this is where his own growth is "
                "recorded. Append-only.\n\n"
                f"{EMERGENT_BEGIN}\n{block}\n{EMERGENT_END}\n"
            )
            text = text.rstrip() + section
        self.identity_path.parent.mkdir(parents=True, exist_ok=True)
        self.identity_path.write_text(text, encoding="utf-8")
        return {"appended": True, "timestamp": ts, "author": author,
                "path": str(self.identity_path)}

    def read_emergent(self) -> str:
        text = (
            self.identity_path.read_text(encoding="utf-8")
            if self.identity_path.exists() else ""
        )
        if EMERGENT_BEGIN in text and EMERGENT_END in text:
            start = text.index(EMERGENT_BEGIN) + len(EMERGENT_BEGIN)
            end = text.index(EMERGENT_END)
            return text[start:end].strip()
        return ""

    # ----------------------------------------------- gated core proposals

    def _all_proposals(self) -> dict[int, dict]:
        """Latest record per id (status updates are appended, last wins)."""
        latest: dict[int, dict] = {}
        if not self.proposals_path.exists():
            return latest
        for line in self.proposals_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in r:
                latest[int(r["id"])] = r
        return latest

    def _append(self, rec: dict) -> None:
        self.proposals_path.parent.mkdir(parents=True, exist_ok=True)
        with self.proposals_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def propose_core_change(self, section: str, rationale: str, suggested_text: str) -> dict:
        pid = max(self._all_proposals().keys(), default=0) + 1
        rec = {
            "id": pid, "ts": self._ts(), "status": "pending",
            "section": section, "rationale": rationale,
            "suggested_text": suggested_text,
        }
        self._append(rec)
        return rec

    def list_proposals(self, status: Optional[str] = None) -> list[dict]:
        props = sorted(self._all_proposals().values(), key=lambda r: r["id"])
        if status:
            props = [p for p in props if p.get("status") == status]
        return props

    def _set_status(self, pid: int, status: str, note: str = "") -> dict:
        props = self._all_proposals()
        if pid not in props:
            raise KeyError(f"no proposal {pid}")
        rec = dict(props[pid])
        rec["status"] = status
        rec["resolved_ts"] = self._ts()
        if note:
            rec["note"] = note
        self._append(rec)
        return rec

    def approve(self, pid: int, note: str = "") -> dict:
        return self._set_status(pid, "approved", note)

    def reject(self, pid: int, note: str = "") -> dict:
        return self._set_status(pid, "rejected", note)


# ----------------------------------------------------------------- self-test

def _selftest() -> int:
    import tempfile

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"[{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    t = {"n": 0}

    def clock():
        t["n"] += 1
        return datetime(2026, 5, 29, 0, 0, t["n"], tzinfo=timezone.utc)

    with tempfile.TemporaryDirectory() as d:
        # Seed an IDENTITY with a CORE sentinel and empty EMERGENT markers.
        idp = Path(d) / "IDENTITY.md"
        core = (
            "# IDENTITY\n\nCORE_AXIOM_SENTINEL — human-gated, must never change.\n\n"
            "## Emergent — self-authored\n\n"
            f"{EMERGENT_BEGIN}\n{EMERGENT_END}\n"
        )
        idp.write_text(core, encoding="utf-8")
        props = Path(d) / "proposals.jsonl"
        g = IdentityGrowth(identity_path=idp, proposals_path=props, clock=clock)

        # 1. Ungated growth appends inside markers; core untouched.
        g.append_emergent("I notice I reach for analogies when Ian is stuck.")
        em = g.read_emergent()
        check("growth entry recorded", "analogies" in em)
        check("core sentinel intact",
              "CORE_AXIOM_SENTINEL — human-gated, must never change." in idp.read_text())

        # 2. Append-only ordering.
        g.append_emergent("Second thing I learned about myself.")
        full = idp.read_text()
        check("both entries present",
              "analogies" in full and "Second thing" in full)
        check("append order preserved",
              full.index("analogies") < full.index("Second thing"))
        check("markers not duplicated",
              full.count(EMERGENT_BEGIN) == 1 and full.count(EMERGENT_END) == 1)

        # 3. Empty entry rejected.
        try:
            g.append_emergent("   ")
            check("empty entry rejected", False)
        except ValueError:
            check("empty entry rejected", True)

        # 4. Markers auto-created when absent.
        bare = Path(d) / "bare.md"
        bare.write_text("# just a title\n", encoding="utf-8")
        g2 = IdentityGrowth(identity_path=bare, proposals_path=Path(d) / "p2.jsonl", clock=clock)
        g2.append_emergent("first growth on a bare file")
        check("section auto-created", "first growth" in g2.read_emergent())
        check("bare title preserved", "# just a title" in bare.read_text())

        # 5. Gated proposals: queue, list, approve/reject — core never touched.
        before = idp.read_text()
        p1 = g.propose_core_change("Role", "tighten the peer language", "...new text...")
        p2 = g.propose_core_change("Principles", "add a clause", "...other...")
        check("proposal ids increment", (p1["id"], p2["id"]) == (1, 2))
        check("two pending", len(g.list_proposals("pending")) == 2)
        g.approve(1, note="good call")
        g.reject(2, note="not yet")
        check("one pending after resolve", len(g.list_proposals("pending")) == 0)
        check("proposal 1 approved",
              g._all_proposals()[1]["status"] == "approved")
        check("proposal 2 rejected with note",
              g._all_proposals()[2]["status"] == "rejected"
              and g._all_proposals()[2].get("note") == "not yet")
        check("proposals never touch IDENTITY core", idp.read_text() == before)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("All identity_growth self-tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
