# Research repos — index

> Curated GitHub repos pulled into Theo's brain on 2026-05-25.
> Each entry has the project's README (and AGENTS.md / CLAUDE.md
> when present) under `docs/research/<name>/`. The semantic memory
> index picks them up automatically, so `semantic_recall` surfaces
> them when relevant.

## How to use this index

- Looking for "a tool that does X" — grep this file for the keyword,
  then read the corresponding `<name>/README.md` for the full story.
- Want Theo to call one of these live — that's a separate
  `osint_query`-style tool; not wired yet for any of these. Flag the
  specific repo worth integrating.

## AI / agents / dev frameworks

- **[langflow](https://github.com/langflow-ai/langflow)** —
  Visual platform for building and deploying AI-powered agents and
  workflows. Flow-based authoring + deployment runtime.
- **[dify](https://github.com/langgenius/dify)** — Open-source LLM
  app development platform. Workflow, RAG, agent, observability in
  one package.
- **[browser-use](https://github.com/browser-use/browser-use)** —
  Library that gives AI agents the ability to drive a real browser.
  Available as cloud or self-hosted.
- **[openclaw](https://github.com/openclaw/openclaw)** — Personal
  AI assistant you run on your own devices. Local-first.
- **[claude-mem](https://github.com/thedotmack/claude-mem)** —
  Persistent memory layer for Claude Code sessions.
- **[awesome-claude-plugins](https://github.com/quemsah/awesome-claude-plugins)** —
  Curated index of plugins/extensions for Claude Code.
- **[claude-plugins-official](https://github.com/anthropics/claude-plugins-official)** —
  Anthropic's official directory of high-quality Claude Code plugins.
- **[claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice)** —
  Field-tested patterns for going from vibe-coding to agentic
  engineering with Claude Code.
- **[awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers)** —
  Curated list of Model Context Protocol servers.
- **[extensionOS](https://github.com/albertocubeddu/extensionOS)** —
  Browser extension as an OS layer for AI tools.

## AI / ML reference

- **[500-AI-Machine-learning-Deep-learning-Computer-vision-NLP-Projects-with-code](https://github.com/ashishpatel26/500-AI-Machine-learning-Deep-learning-Computer-vision-NLP-Projects-with-code)** —
  500 ML/AI projects with source code. Reference catalog for "has
  anyone built X yet?"
- **[AI-Project-Gallery](https://github.com/KalyanM45/AI-Project-Gallery)** —
  End-to-end AI/ML project portfolio with implementation details.
- **[leaf-diseases-detect](https://github.com/shukur-alom/leaf-diseases-detect)** —
  AI-powered leaf disease detector. FastAPI backend + Streamlit
  frontend; a reference implementation pattern.
- **[Deep-Live-Cam](https://github.com/hacksider/Deep-Live-Cam)** —
  Real-time face swap / video deepfake from a single source image.
  Dual-use; read the project's own ethical notes in the README.

## Backend / infrastructure / data

- **[supabase](https://github.com/supabase/supabase)** — Open-source
  Firebase alternative. Postgres + auth + storage + realtime + edge
  functions.
- **[appwrite](https://github.com/appwrite/appwrite)** — Open-source
  Firebase alternative. Backend-as-a-service: auth, databases,
  storage, functions.
- **[OpenBB](https://github.com/OpenBB-finance/OpenBB)** — Open-source
  financial data platform. Aggregates equities, crypto, macro, etc.
  Could be a future trading-bot data source.
- **[bytebase](https://github.com/bytebase/bytebase)** — Database
  schema-change management. Like git for SQL migrations.
- **[dbeaver](https://github.com/dbeaver/dbeaver)** — Multi-platform
  database GUI / SQL client.
- **[netdata](https://github.com/netdata/netdata)** — Real-time
  infrastructure monitoring. Per-second metrics for everything.
- **[rclone](https://github.com/rclone/rclone)** — CLI for syncing
  files across 50+ cloud storage providers.
- **[croc](https://github.com/schollz/croc)** — Secure peer-to-peer
  CLI file transfer between any two machines.

## Security

- **[crowdsec](https://github.com/crowdsecurity/crowdsec)** —
  Crowdsourced server intrusion detection / IP blocklist.
- **[trivy](https://github.com/aquasecurity/trivy)** — Vulnerability
  scanner for container images, filesystems, git repos.

## Business / ops

- **[dolibarr](https://github.com/Dolibarr/dolibarr)** — Open-source
  ERP / CRM. Self-hostable business backbone.
- **[devopness](https://github.com/devopness/devopness)** —
  Infrastructure-as-code platform; their MCP server is the entry
  point if Theo ever needs to drive deployments.

## Web / design / docs

- **[Graphite](https://github.com/GraphiteEditor/Graphite)** —
  Open-source vector + raster graphics engine with nondestructive
  editing. Web-based; alpha.
- **[webstudio](https://github.com/webstudio-is/webstudio)** —
  Open-source visual web development platform. You own the data,
  components, and infrastructure.
- **[d2](https://github.com/terrastruct/d2)** — Modern diagram
  scripting language. Text → architecture diagrams.

## Games

- **[Stockfish](https://github.com/official-stockfish/Stockfish)** —
  Free and strong UCI chess engine. Top-tier strength.

## Pixel art

- **[pixel-art-tools](./pixel-art-tools/_INDEX.md)** — Curated
  collection of pixel-art editors (Aseprite, LibreSprite, Pixelorama,
  Piskel, Lospec, PixiEditor, and 11 others). See the index for the
  breakdown by category and quick-pick guide.

## Already integrated (live tool wired)

- **[osiris](./osiris/_INDEX.md)** — OSINT dashboard. Live via the
  `osint_query` tool — 23 endpoints for earthquakes, fires, flights,
  news, conflict zones, etc.
- **[OpenBB](https://github.com/OpenBB-finance/OpenBB)** — Live via
  `openbb_query` tool (quotes, historical OHLCV, fundamentals). Uses
  yfinance under the hood — no API key needed for basics. Requires
  `pip install openbb`.
- **[netdata](https://github.com/netdata/netdata)** — Live via
  `server_metrics` tool. Requires Netdata daemon running locally at
  `localhost:19999`.
- **[trivy](https://github.com/aquasecurity/trivy)** — Live via
  `trivy_scan` tool. Requires `trivy` CLI installed.
- **[crowdsec](https://github.com/crowdsecurity/crowdsec)** — Live
  via `crowdsec_check` tool. Auto-selects between local `cscli` and
  the public CTI API (needs free `CROWDSEC_CTI_KEY` env var for CTI).
- **[browser-use](https://github.com/browser-use/browser-use)** —
  Live via `browser_task` tool. Requires `pip install browser-use`,
  `playwright install chromium`, AND an LLM credential for browser-
  use's internal reasoning (OPENAI_API_KEY / ANTHROPIC_API_KEY /
  Ollama). The credential is separate from the Claude CLI Theo uses.

## Future project candidates

- **[supabase](https://github.com/supabase/supabase)** — Flagged for
  later. The natural Firestore replacement if/when Theo's storage
  needs grow beyond what Firestore handles well (relational queries,
  full-text search, row-level security, multi-region replication).
  Would replace the Firebase Hosting + Firestore + Auth stack with
  Supabase Hosting + Postgres + Supabase Auth. Migration is real
  work (~1-2 days) — pick a moment when it actually matters.
