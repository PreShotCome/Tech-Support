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

## Trading / finance (Proteus material)

- **[financial-services](./financial-services/)** — **Anthropic's
  own** patterns for Claude in finance. 249 markdown files including
  10 managed-agent cookbooks (model-builder, pitch-agent, market-
  researcher, valuation-reviewer, earnings-reviewer, kyc-screener,
  statement-auditor, gl-reconciler, month-end-closer, meeting-prep)
  plus partner-built plugins (LSEG, S&P Global) and the Microsoft
  365 install path. Highest-signal reference for how Theo should
  approach financial workflows.
- **[dexter](https://github.com/virattt/dexter)** — Trading-agent
  project. Similar shape to Theo's trading slice; useful for
  architectural ideas.
- **[Kronos](https://github.com/shiyu-coder/Kronos)** — Time-series
  forecasting research codebase.
- **[Finance](https://github.com/shashankvemuri/Finance)** —
  Python collection of indicators, screeners, TA snippets. Reference
  when Theo needs to recall a specific indicator formula or
  screening pattern for Proteus work.
- **[awesome-ai-in-finance](https://github.com/georgezouq/awesome-ai-in-finance)** —
  Curated list of AI/ML finance projects. Meta-reference.

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
- **[claude-plugins-official](./claude-plugins-official/)** — 28
  SKILL.md instruction docs wired through the `list_skills` and
  `read_skill` tools. Theo can browse available skills by name +
  description, then load any one's full body and follow it as
  operating instructions. Covers: code review, frontend design,
  MCP server dev, skill creation, plugin dev (commands / agents /
  hooks / settings / structure), claude-md management, session
  reporting, math olympiad, plus 6 external integrations
  (Discord / iMessage / Telegram access + configure).
- **[d2](./d2/README.md)** — Diagram language. Live via
  `render_diagram` — Theo can sketch architecture / flow / system
  diagrams as SVG/PNG/PDF. Requires the d2 CLI on PATH.
- **[rclone](./rclone/README.md)** — Cloud file sync. Live via
  `rclone_op` (listremotes / ls / copy / sync / size / about).
  Back up Theo's `~/.techsupport_agent/` to cloud, sync transcripts
  between machines, list bucket contents. Requires the rclone CLI
  plus configured remotes via `rclone config`.
- **[Stockfish](./Stockfish/README.md)** — Top open-source chess
  engine. Live via `chess_analyze` — pass a FEN, get back best move,
  evaluation, principal variation. Requires the stockfish binary
  on PATH.
- **[croc](./croc/README.md)** — Peer-to-peer file transfer. Live
  via `croc_send` — Theo prepares a file, returns a 3-word transfer
  code, recipient runs `croc <code>` on the other machine to pull.
  Requires the croc CLI on PATH.
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
