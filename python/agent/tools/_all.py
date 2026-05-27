"""Single source of truth for registering every tool module.

There are several places that need the full tool inventory:
  - cli.py / build_agent() — what the running agent exposes
  - scripts/dump_brain.py — what the brain visualization shows
  - tools/system.py / tool_info, list_tools — what Theo can introspect

Before this module existed, each of those built its own list of
imports. Twice in a row a new tool got added to the agent but missed
the dump_brain or introspection list, leaving the brain or tool_info
blind to it. Now everyone calls build_full_registry() and the import
list lives in exactly one place.

When adding a new tool module:
  1. Create `python/agent/tools/<name>.py` with a `register(registry)`
     function.
  2. Import it here and add to TOOL_MODULES in alphabetical order.
  3. Done. The agent, the brain, and tool_info all see it on the
     next start with zero further edits."""
from __future__ import annotations

from . import base as _base


def _import_modules():
    """Import each tool module lazily so importing this helper at
    startup doesn't trigger every tool's import side-effects."""
    from . import trading
    from . import memory
    from . import system
    from . import safety
    from . import identity_tools
    from . import web
    from . import introspection
    from . import osint
    from . import finance
    from . import server_metrics
    from . import security_tools
    from . import browser
    from . import skills
    from . import d2
    from . import rclone_tool
    from . import chess
    from . import croc_tool
    from . import image_gen
    from . import qr
    from . import ascii_art
    from . import vision
    from . import register_check as _register_check
    from . import proteus_robinhood
    from . import proteus_crypto
    from . import proteus_congress
    from . import typed_memory
    from . import theo_predict
    return [
        ("trading",         trading),
        ("memory",          memory),
        ("system",          system),
        ("safety",          safety),
        ("identity",        identity_tools),
        ("web",             web),
        ("introspection",   introspection),
        ("osint",           osint),
        ("finance",         finance),
        ("server_metrics",  server_metrics),
        ("security",        security_tools),
        ("browser",         browser),
        ("skills",          skills),
        ("diagrams",        d2),
        ("file_sync",       rclone_tool),
        ("chess",           chess),
        ("file_transfer",   croc_tool),
        ("image_gen",       image_gen),
        ("qr",              qr),
        ("ascii",           ascii_art),
        ("vision",          vision),
        ("register_check",  _register_check),
        ("proteus_rh",      proteus_robinhood),
        ("proteus_crypto",  proteus_crypto),
        ("proteus_congress", proteus_congress),
        ("typed_memory",    typed_memory),
        ("theo_predict",    theo_predict),
    ]


def build_full_registry() -> _base.ToolRegistry:
    """Return a fresh ToolRegistry with every known tool registered.
    Cheap; no shared state."""
    reg = _base.ToolRegistry()
    for _name, mod in _import_modules():
        mod.register(reg)
    return reg


def grouped_modules() -> list[tuple[str, object]]:
    """Return [(category_name, module), ...] for callers that need to
    know which group each tool came from (e.g. the brain visualization
    which colors by group)."""
    return _import_modules()
