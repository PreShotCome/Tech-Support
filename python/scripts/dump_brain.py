"""Dump Theo's current brain state into a JSON the brain.html visualization reads.

Walks the repo (IDENTITY.md, docs/skills, docs/research, tools) plus
the runtime state directory (~/.techsupport_agent/) and produces a
single brain.json — categories with leaf nodes, plus headline stats —
ready for the d3 force graph in flutter_app/web/brain/.

Usage:
    python -m scripts.dump_brain                   # writes to flutter_app/web/brain.json
    python -m scripts.dump_brain --out path.json   # write elsewhere

Then deploy alongside the PWA:
    cd flutter_app && flutter build web && firebase deploy --only hosting

To swap to live-on-every-message later, the bridge can import
`dump_brain.collect()` and write the same dict to Firebase Storage."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "IDENTITY.md").exists() and (parent / "python").exists():
            return parent
    return here.parent.parent.parent


REPO = _repo_root()
STATE_DIR = Path.home() / ".techsupport_agent"


# ----------------------------------------------------------------- identity

_IDIOM_SECTION_RE = re.compile(
    r"### Idioms.*?\n\n(.+?)\n### ", re.DOTALL,
)
_IDIOM_BULLET_RE = re.compile(
    r"- \*\*(.+?)\*\*\s+(.+?)(?=\n\n- \*\*|\Z)", re.DOTALL,
)
_PRINCIPLE_BULLET_RE = re.compile(
    r"- \*\*(.+?)\*\*\s+(.+?)(?=\n\n- \*\*|\n###|\Z)", re.DOTALL,
)


def _parse_idioms(identity_text: str) -> list[dict]:
    m = _IDIOM_SECTION_RE.search(identity_text)
    if not m:
        return []
    out = []
    for bm in _IDIOM_BULLET_RE.finditer(m.group(1)):
        title = bm.group(1).strip().rstrip(".")
        body = re.sub(r"\s+", " ", bm.group(2)).strip()
        out.append({"id": f"idiom:{title[:40]}", "label": title, "body": body})
    return out


def _parse_principles(identity_text: str) -> list[dict]:
    m = re.search(r"### Principles\n\n(.+?)\n### ", identity_text, re.DOTALL)
    if not m:
        return []
    out = []
    for bm in _PRINCIPLE_BULLET_RE.finditer(m.group(1)):
        title = bm.group(1).strip().rstrip(".")
        body = re.sub(r"\s+", " ", bm.group(2)).strip()
        out.append({"id": f"principle:{title[:40]}", "label": title, "body": body})
    return out


def _parse_axioms(identity_text: str) -> list[dict]:
    """Layer 1 — Continuity and Truth."""
    out = []
    for m in re.finditer(
        r"### \d+\.\s+(.+?)\n\n(.+?)(?=\n### |\n---)", identity_text, re.DOTALL,
    ):
        title = m.group(1).strip()
        body = re.sub(r"\s+", " ", m.group(2)).strip()
        out.append({"id": f"axiom:{title[:40]}", "label": title, "body": body[:600]})
    return out[:2]


# ----------------------------------------------------------------- tools

def _collect_tools() -> list[dict]:
    """Build the same registry cli.py builds, then dump schemas."""
    import sys
    sys.path.insert(0, str(REPO / "python"))
    from agent.tools import ToolRegistry
    from agent.tools import trading as trading_tools
    from agent.tools import memory as memory_tools
    from agent.tools import system as system_tools
    from agent.tools import safety as safety_tools
    from agent.tools import identity_tools
    from agent.tools import web as web_tools
    from agent.tools import introspection as introspection_tools
    from agent.tools import osint as osint_tools
    from agent.tools import finance as finance_tools
    from agent.tools import server_metrics as server_metrics_tools
    from agent.tools import security_tools
    from agent.tools import browser as browser_tools
    from agent.tools import skills as skills_tools
    from agent.tools import d2 as d2_tools
    from agent.tools import rclone_tool as rclone_tools
    from agent.tools import chess as chess_tools
    from agent.tools import croc_tool as croc_tools
    from agent.tools import image_gen as image_gen_tools

    reg = ToolRegistry()
    groups = [
        ("trading", trading_tools),
        ("memory", memory_tools),
        ("system", system_tools),
        ("safety", safety_tools),
        ("identity", identity_tools),
        ("web", web_tools),
        ("introspection", introspection_tools),
        ("osint", osint_tools),
        ("finance", finance_tools),
        ("server_metrics", server_metrics_tools),
        ("security", security_tools),
        ("browser", browser_tools),
        ("skills", skills_tools),
        ("diagrams", d2_tools),
        ("file_sync", rclone_tools),
        ("chess", chess_tools),
        ("file_transfer", croc_tools),
        ("image_gen", image_gen_tools),
    ]
    nodes_by_group: dict[str, list[dict]] = {g: [] for g, _ in groups}
    for gname, mod in groups:
        before = set(reg.names())
        mod.register(reg)
        after = set(reg.names())
        for tname in sorted(after - before):
            tool = reg.get(tname)
            nodes_by_group[gname].append({
                "id": f"tool:{tname}",
                "label": tname,
                "body": tool.description if tool else "",
                "schema": getattr(tool, "parameters_schema", None) if tool else None,
            })
    return [
        {"id": f"toolgroup:{g}", "label": f"Tools — {g}", "nodes": ns}
        for g, ns in nodes_by_group.items() if ns
    ]


# ----------------------------------------------------------------- files

def _docs_nodes(subdir: str, label_prefix: str) -> list[dict]:
    base = REPO / "docs" / subdir
    if not base.exists():
        return []
    out = []
    for p in sorted(base.rglob("*.md")):
        rel = p.relative_to(REPO).as_posix()
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        title = _first_heading(text) or p.stem
        out.append({
            "id": f"doc:{rel}",
            "label": f"{label_prefix} · {title}",
            "body": text[:2000],
            "path": rel,
        })
    return out


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        m = re.match(r"#+\s+(.+)", line.strip())
        if m:
            return m.group(1).strip()
    return None


# ----------------------------------------------------------------- memory

def _read_state(name: str, tail: int = 4000) -> str:
    p = STATE_DIR / name
    if not p.exists():
        return ""
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return ""
    return text[-tail:] if len(text) > tail else text


def _memory_nodes() -> list[dict]:
    out = []
    for fname, label in [
        ("self_model.md", "Self-model"),
        ("human_model.md", "Human-model"),
        ("narrative.md", "Narrative"),
        ("notes.md", "Durable notes"),
    ]:
        body = _read_state(fname)
        if body.strip():
            out.append({
                "id": f"mem:{fname}",
                "label": label,
                "body": body,
            })
    return out


def _thread_nodes() -> list[dict]:
    p = STATE_DIR / "threads.md"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    out = []
    pat = re.compile(
        r"##\s+(thread-\d+)\s+·\s+(\d{4}-\d{2}-\d{2})\s+·\s+(OPEN|CLOSED(?:\s+\([^)]+\))?)\n(.+?)(?=\n## |\Z)",
        re.DOTALL,
    )
    for m in pat.finditer(text):
        tid, opened, status, body = m.groups()
        is_open = status.strip().upper() == "OPEN"
        out.append({
            "id": f"thread:{tid}",
            "label": f"{tid} · {'OPEN' if is_open else 'closed'}",
            "body": body.strip(),
            "open": is_open,
            "opened": opened,
        })
    return out


# ----------------------------------------------------------------- stats

def _stats(brain: dict) -> dict:
    transcripts_dir = STATE_DIR / "transcripts"
    n_transcripts = len(list(transcripts_dir.glob("*.md"))) if transcripts_dir.exists() else 0

    # Memory index stats — pull from LanceDB via TranscriptIndex.status().
    # Falls back to the legacy JSON file if LanceDB isn't available
    # (older venv without the new [agent] deps installed).
    chunks = pinned = recalled = 0
    try:
        import sys
        sys.path.insert(0, str(REPO / "python"))
        from agent.embeddings import TranscriptIndex
        st = TranscriptIndex().status()
        chunks = int(st.get("total_chunks", 0))
        pinned = int(st.get("pinned_count", 0))
        recalled = sum(
            1 for r in st.get("top_recalled", []) if r.get("recall_count", 0) > 0
        )
    except Exception:
        legacy = STATE_DIR / "embeddings_index.json"
        if legacy.exists():
            try:
                data = json.loads(legacy.read_text(encoding="utf-8"))
                chunks = len(data.get("chunks", {}))
                for c in data.get("chunks", {}).values():
                    if c.get("importance", 0) > 0:
                        pinned += 1
                    if c.get("recall_count", 0) > 0:
                        recalled += 1
            except Exception:
                pass

    open_threads = sum(1 for cat in brain["categories"] if cat["id"] == "threads"
                       for n in cat["nodes"] if n.get("open"))
    tool_total = sum(
        len(group["nodes"])
        for cat in brain["categories"] if cat["id"].startswith("toolgroup")
        for group in [cat]
    )
    return {
        "tools": tool_total,
        "transcripts": n_transcripts,
        "memory_chunks": chunks,
        "pinned": pinned,
        "recalled_at_least_once": recalled,
        "open_threads": open_threads,
        "idioms": sum(1 for c in brain["categories"] if c["id"] == "voice"
                      for n in c["nodes"]),
    }


# ----------------------------------------------------------------- assemble

def collect() -> dict:
    identity_text = (REPO / "IDENTITY.md").read_text(encoding="utf-8")
    version = "?"
    vm = re.search(r"\*\*Version:\*\*\s*(\S+)", identity_text)
    if vm:
        version = vm.group(1)

    categories: list[dict] = [
        {
            "id": "core",
            "label": "Core (Layer 1)",
            "nodes": _parse_axioms(identity_text),
        },
        {
            "id": "voice",
            "label": "Voice (idioms)",
            "nodes": _parse_idioms(identity_text),
        },
        {
            "id": "principles",
            "label": "Principles",
            "nodes": _parse_principles(identity_text),
        },
    ]
    categories.extend(_collect_tools())
    categories.append({
        "id": "skills",
        "label": "Skills",
        "nodes": _docs_nodes("skills", "Skill"),
    })
    categories.append({
        "id": "research",
        "label": "Research",
        "nodes": _docs_nodes("research", "Research"),
    })
    categories.append({
        "id": "memory",
        "label": "Memory",
        "nodes": _memory_nodes(),
    })
    categories.append({
        "id": "threads",
        "label": "Open threads",
        "nodes": _thread_nodes(),
    })

    # Drop empty categories so the graph doesn't render lonely hubs
    categories = [c for c in categories if c["nodes"]]

    brain = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "identity_version": version,
        "categories": categories,
    }
    brain["stats"] = _stats(brain)
    return brain


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default=str(REPO / "flutter_app" / "web" / "brain.json"),
        help="Output path. Defaults to flutter_app/web/brain.json so flutter build picks it up.",
    )
    args = ap.parse_args()

    brain = collect()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(brain, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}")
    print(f"  identity_version: {brain['identity_version']}")
    print(f"  categories:       {len(brain['categories'])}")
    print(f"  stats:            {brain['stats']}")


if __name__ == "__main__":
    main()
