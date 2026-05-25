# Tool setup — what each live tool needs on the host

Most of Theo's tools work the moment the bridge starts (memory, identity,
web search, OSINT via osirisai.live). A few new ones require host-side
installs because they wrap a local CLI or daemon. This is the install
guide.

If a tool isn't set up, calling it returns a clear error with the fix —
nothing crashes. So you can install these incrementally as you actually
want each capability.

## openbb_query — financial data

```powershell
cd C:\src\Tech-Support\python
.\.venv\Scripts\Activate.ps1
pip install openbb
```

That's it. The default `yfinance` provider is free and needs no API key.
For premium providers (Polygon, FMP, etc.) set env vars per the OpenBB
docs.

Try: `openbb_query domain=quote symbol=AAPL`

## server_metrics — Netdata

Install Netdata so it exposes `http://localhost:19999/api/v1/*`:

**Windows:** Download the MSI installer from
https://www.netdata.cloud/download/ and run it. Starts automatically as
a Windows service.

**Linux/macOS:**
```bash
bash <(curl -SsL https://my-netdata.io/kickstart.sh)
```

Verify with `curl http://localhost:19999/api/v1/info`. If it returns JSON,
the tool is ready.

Try: `server_metrics domain=cpu seconds_back=60`

## trivy_scan — vulnerability scanner

```powershell
winget install AquaSecurity.Trivy
```

(Or `scoop install trivy`, or `brew install trivy` on macOS, or
`apt install trivy` on Linux.)

Verify with `trivy --version`.

Try: `trivy_scan target="C:\src\Tech-Support" kind=fs`

## crowdsec_check — IP reputation

Two paths, pick one or both:

**Local** (rich, runs on your box):
- Windows: download the installer from https://www.crowdsec.net/download
- Linux: `apt install crowdsec`
- After install, `cscli decisions list` should work.

**CTI** (lighter, just a free API key):
- Sign up at https://app.crowdsec.net for a free CTI key
- Set the env var before launching the bridge:
  ```powershell
  $env:CROWDSEC_CTI_KEY = "your-key-here"
  ```
- Or add it permanently via `setx CROWDSEC_CTI_KEY "your-key-here"`.

Try: `crowdsec_check ip="185.220.101.1"` (a known Tor exit, should
flag).

## browser_task — drive a real browser

```powershell
cd C:\src\Tech-Support\python
.\.venv\Scripts\Activate.ps1
pip install browser-use
playwright install chromium
```

Plus an LLM credential for browser-use's internal reasoning. **This is
separate from the Claude CLI Theo uses** — browser-use needs its own
LLM and Anthropic's CLI auth isn't reusable here. Options in order
of cheap:

1. **Ollama (free, local):**
   ```powershell
   # Install Ollama from https://ollama.com, then:
   ollama pull llama3.1:8b
   $env:BROWSER_USE_LLM = "ollama:llama3.1:8b"
   ```

2. **Paid API:**
   ```powershell
   $env:OPENAI_API_KEY = "..."
   # or
   $env:ANTHROPIC_API_KEY = "..."
   ```

Set the env var in the SAME PowerShell window you launch the bridge
from (or use `setx` to make it permanent).

Try: `browser_task task="Go to news.ycombinator.com and tell me the top 3 story titles" headless=true`

## rclone_op — cloud file sync

```powershell
winget install Rclone.Rclone
```

Then configure your remotes (one-time setup per cloud provider):

```powershell
rclone config
```

Walks you through naming a remote, picking the provider (S3 / Dropbox /
OneDrive / Google Drive / etc.), and authenticating. Each remote becomes
addressable as `name:path` in Theo's commands.

Try: `rclone_op operation=listremotes`

## chess_analyze — Stockfish

```powershell
winget install Stockfish.Stockfish
```

(Or `brew install stockfish` on macOS, `apt install stockfish` on Linux.)

Try: `chess_analyze fen="startpos" depth=12`

## croc_send — peer-to-peer file transfer

```powershell
winget install schollz.croc
```

(Or `brew install croc` on macOS, `apt install croc` on Linux.)

Try: `croc_send path="C:\path\to\file.txt"` — Theo returns a 3-word
transfer code. Recipient runs `croc <code>` on their machine to pull.

## render_diagram — d2 diagrams

```powershell
winget install terrastruct.d2
```

Try: `render_diagram d2_source="A -> B: hello"`

## When you're not sure if a tool is ready

Theo can probe it himself by calling the tool with a no-op or simple
query. The error response will tell him what's missing and how to fix it.
