"""Web access tools.

The `claude -p` CLI mode the agent uses doesn't expose Claude Code's
own WebSearch / WebFetch tools, so the agent has no live internet by
default. These two tools fill that gap:

  - web_search(query):    DuckDuckGo HTML results (no API key needed)
  - web_fetch(url):       grab a URL, return readable text + title

Both are best-effort. They are not a substitute for proper web research
in a browser — they exist so the agent can quickly check current facts
mid-conversation without the human having to leave and come back.
"""
from __future__ import annotations

import re
from typing import Any

from .base import Tool


def _web_search(query: str, max_results: int = 8) -> dict[str, Any]:
    """Search the web via DuckDuckGo. No API key required."""
    if not query.strip():
        return {"error": "empty query"}
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return {
            "error": "duckduckgo-search not installed. Install with: pip install -e .[agent]",
        }
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=int(max_results)))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    cleaned = []
    for r in results:
        cleaned.append({
            "title": r.get("title", ""),
            "url": r.get("href") or r.get("url", ""),
            "snippet": r.get("body", ""),
        })
    return {
        "query": query,
        "n_results": len(cleaned),
        "results": cleaned,
    }


def _web_fetch(url: str, max_chars: int = 8000) -> dict[str, Any]:
    """Fetch a URL and return readable text content. Strips scripts,
    styles, nav, footer. Truncates at max_chars."""
    if not url.strip():
        return {"error": "empty url"}
    if not (url.startswith("http://") or url.startswith("https://")):
        return {"error": "url must start with http:// or https://"}

    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return {
            "error": "requests / beautifulsoup4 not installed. Install with: pip install -e .[agent]",
        }

    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 TechSupport/1.0"
                ),
            },
            allow_redirects=True,
        )
    except requests.RequestException as e:
        return {"error": f"fetch failed: {type(e).__name__}: {e}"}

    if resp.status_code >= 400:
        return {
            "url": url,
            "status_code": resp.status_code,
            "error": f"HTTP {resp.status_code}",
        }

    ctype = resp.headers.get("Content-Type", "")
    if "html" not in ctype.lower() and "xml" not in ctype.lower():
        # Plain text / json / etc — return raw, truncated.
        text = resp.text
        return {
            "url": resp.url,
            "status_code": resp.status_code,
            "content_type": ctype,
            "title": None,
            "text": text[:max_chars],
            "truncated": len(text) > max_chars,
        }

    soup = BeautifulSoup(resp.text, "lxml")
    # Strip non-content tags
    for tag in soup(["script", "style", "noscript", "iframe", "header", "footer", "nav", "aside", "form"]):
        tag.decompose()

    title = (soup.title.string.strip() if soup.title and soup.title.string else None)
    # Prefer <main> or <article> if present
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n", strip=True) if main else ""
    # Collapse runs of blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]

    return {
        "url": resp.url,
        "status_code": resp.status_code,
        "title": title,
        "text": text,
        "truncated": truncated,
        "length": len(text),
    }


WEB_SEARCH_TOOL = Tool(
    name="web_search",
    description=(
        "Search the live web via DuckDuckGo. Returns titles, URLs, and "
        "snippets. Use when the answer depends on current information "
        "the agent doesn't already have (news, current prices outside "
        "the trading tools, recent events, documentation). Follow up "
        "with web_fetch on a promising URL when a snippet isn't enough."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural-language search query."},
            "max_results": {"type": "integer", "description": "Default 8. Max 20."},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    handler=_web_search,
)


WEB_FETCH_TOOL = Tool(
    name="web_fetch",
    description=(
        "Fetch a specific URL and return its readable text content. "
        "Strips scripts, styles, navigation, and footer; returns the "
        "main content plus the page title. Truncates at 8000 chars by "
        "default. Use after web_search when a result looks promising."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Absolute http(s) URL."},
            "max_chars": {"type": "integer", "description": "Truncation cap. Default 8000."},
        },
        "required": ["url"],
        "additionalProperties": False,
    },
    handler=_web_fetch,
)


def register(registry) -> None:
    for t in (WEB_SEARCH_TOOL, WEB_FETCH_TOOL):
        registry.register(t)
