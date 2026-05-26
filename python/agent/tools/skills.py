"""Skills registry — discover and load Claude Code-style SKILL.md
instructions at runtime.

Anthropic's claude-plugins-official repo (pulled into docs/research/
earlier) ships 28 SKILL.md files. Each is a YAML-frontmatter +
markdown body describing a specialized workflow (code review,
frontend design, MCP server dev, skill creation, math olympiad,
session reporting, etc.). The format is exactly what an agent
loads when it wants to follow a specific procedure.

These are already searchable via semantic_recall since they live in
docs/research/. This module gives Theo a higher-affordance path:
list and read skills by name, with their frontmatter metadata exposed
so he can pick deliberately rather than relying on semantic match.

The intent is the agent reads a SKILL.md, treats its body as the
operating instructions for that turn, and follows it. No special
prompt-injection plumbing — the existing tool-call loop returns the
skill body as a tool result the agent then acts on."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .base import Tool


SKILLS_REPO_REL = "docs/research"   # scan ALL of research/, not just
                                     # claude-plugins-official — any
                                     # repo that ships SKILL.md files
                                     # under research/ gets indexed
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
_YAML_KEY_RE = re.compile(r"^(?P<key>\w+)\s*:\s*(?P<val>.+?)\s*$", re.MULTILINE)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "IDENTITY.md").exists() and (parent / "python").exists():
            return parent
    return here.parent.parent.parent.parent


def _skills_root() -> Path:
    return _repo_root() / SKILLS_REPO_REL


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter + body. Returns ({}, full text) if missing.

    Keeping the parser tiny on purpose — these files use simple
    key: value pairs, not nested structures. Avoids pulling pyyaml
    just for two fields."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for km in _YAML_KEY_RE.finditer(m.group(1)):
        fm[km.group("key").strip()] = km.group("val").strip()
    return fm, m.group(2)


@lru_cache(maxsize=1)
def _discover_skills() -> list[dict]:
    """Walk the skills repo and build a list of {skill_name, plugin,
    description, path, body} entries. Cached for the process lifetime;
    new skills require a process restart to be seen, which matches the
    "skills are reference material, edit deliberately" model."""
    root = _skills_root()
    if not root.exists():
        return []
    out: list[dict] = []
    for p in sorted(root.rglob("SKILL.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        fm, body = _parse_frontmatter(text)
        # Plugin / source naming from path:
        #   claude-plugins-official/<bucket>/<plugin>/skills/<skill>/SKILL.md
        #     -> bucket=<bucket>, plugin=<plugin>
        #   <repo>/.../skills/<skill>/SKILL.md  (e.g. dexter)
        #     -> bucket=<repo>, plugin=<repo>
        try:
            parts = p.relative_to(root).parts
            repo = parts[0] if parts else "unknown"
            if repo == "claude-plugins-official" and len(parts) >= 4:
                # Anthropic's repo: <bucket>/<plugin>/skills/<skill>/SKILL.md
                bucket = parts[1]
                plugin = parts[2]
            else:
                # Other repos: repo name becomes bucket+plugin
                bucket = repo
                plugin = repo
        except Exception:
            bucket, plugin = "", "unknown"
        out.append({
            "skill_name": fm.get("name") or p.parent.name,
            "plugin": plugin,
            "bucket": bucket,
            "description": fm.get("description", ""),
            "path": str(p.relative_to(_repo_root())).replace("\\", "/"),
            "body": body.strip(),
        })
    return out


def _by_name(name: str) -> dict | None:
    name = name.strip().lower()
    for s in _discover_skills():
        if s["skill_name"].lower() == name:
            return s
    # Fallback: substring match if no exact hit
    for s in _discover_skills():
        if name in s["skill_name"].lower():
            return s
    return None


# ----------------------------------------------------------------- tools

def _list_skills(plugin: str | None = None, bucket: str | None = None) -> dict[str, Any]:
    """Return all known skills, optionally filtered by plugin or bucket."""
    skills = _discover_skills()
    if plugin:
        skills = [s for s in skills if s["plugin"].lower() == plugin.lower()]
    if bucket:
        skills = [s for s in skills if s["bucket"].lower() == bucket.lower()]
    # Surface only metadata in the listing (body would be huge); use
    # read_skill to pull the full content of any one.
    out = [
        {
            "skill_name":  s["skill_name"],
            "plugin":      s["plugin"],
            "bucket":      s["bucket"],
            "description": s["description"][:300],
        }
        for s in skills
    ]
    return {"total": len(out), "skills": out}


def _read_skill(skill_name: str) -> dict[str, Any]:
    """Return the full body of a skill by name."""
    s = _by_name(skill_name)
    if s is None:
        return {
            "error": f"no skill matching {skill_name!r}",
            "hint": "Call list_skills to see what's available.",
        }
    return {
        "skill_name":  s["skill_name"],
        "plugin":      s["plugin"],
        "description": s["description"],
        "path":        s["path"],
        "body":        s["body"],
    }


LIST_SKILLS_TOOL = Tool(
    name="list_skills",
    description=(
        "List the SKILL.md instruction docs available from Anthropic's "
        "claude-plugins-official repo (pulled into docs/research/). "
        "Each entry has a name and one-line description so you can "
        "pick the right one. Optional filters: `plugin` (e.g. "
        "'code-review', 'frontend-design', 'mcp-server-dev', "
        "'skill-creator'), `bucket` ('plugins' or 'external_plugins'). "
        "Call this when the human asks for help with something where "
        "a structured skill might apply (code review, building an MCP "
        "server, frontend design work, creating a new skill, etc.). "
        "Then use read_skill on the most relevant one to get the full "
        "instructions, and follow them."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "plugin": {"type": "string", "description": "Filter by plugin name."},
            "bucket": {"type": "string", "description": "'plugins' or 'external_plugins'."},
        },
        "additionalProperties": False,
    },
    handler=_list_skills,
)


READ_SKILL_TOOL = Tool(
    name="read_skill",
    description=(
        "Load the full body of a SKILL.md by name and treat it as "
        "operating instructions for what comes next. The body tells "
        "you how to perform the skill — read it carefully and follow "
        "the steps. Names are case-insensitive; substring matches "
        "fall back if no exact hit. Discover available skills via "
        "list_skills first."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "Skill name from list_skills."},
        },
        "required": ["skill_name"],
        "additionalProperties": False,
    },
    handler=_read_skill,
)


def register(registry) -> None:
    registry.register(LIST_SKILLS_TOOL)
    registry.register(READ_SKILL_TOOL)
