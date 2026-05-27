# TechSupport

A Windows-native remote-support tool built for technicians who actually
do this work for a living. Two pieces:

- **Agent** — a Windows service that runs on the end-user's PC. Provides
  unattended access via DXGI screen capture and `SendInput` injection.
- **Console** — a WPF dashboard for the technician. Saved customers,
  quick-connect by host or pairing code, a clean Mica-themed remote view.

The point of difference is the technician workflow. Existing tools
treat every connection as a one-off "enter the 9-digit code" exchange.
This treats the customer as the first-class object: saved connections,
session history, notes, fast reconnect.

## Status

v0 — local skeleton. Works on a LAN with a direct TCP connection between
agent and console. Frames are uncompressed BGRA, fine for development;
v1 will swap in H.264 via Media Foundation. Relay / NAT traversal is
designed for but not yet implemented.

## Layout

```
src/
  TechSupport.Shared/         Wire protocol, framing, session crypto
  TechSupport.Agent/          Windows service: DXGI capture, SendInput, TCP listener
  TechSupport.Console/        WPF technician dashboard (Fluent / Mica)
  TechSupport.ConsentPrompt/  End-user consent dialog (separate exe)
scripts/
  install-agent.ps1           Installs the agent as a Windows service
docs/
  architecture.md             How the pieces fit together
  roadmap.md                  What's next: relay, H.264, MSI
```

## Build

Requires .NET 8 SDK on Windows 10 1809 or later.

```powershell
dotnet build TechSupport.sln -c Release
```

## Run (development, LAN-only)

1. On the end-user PC, run the agent in the foreground:
   ```powershell
   dotnet run --project src\TechSupport.Agent -c Release
   ```
   The agent prints its pairing code (e.g. `amber-frost-417`) and starts
   the LAN listener on port 7022.

2. On the technician PC, run the console:
   ```powershell
   dotnet run --project src\TechSupport.Console -c Release
   ```
   Enter the agent's IP in the **Quick connect** field and click
   **Connect**.

## Install agent as a service

```powershell
.\scripts\install-agent.ps1
```

Uninstall with `-Uninstall`. The script must run elevated.

## What this is not (yet)

- Not internet-routable on its own — relay is in `docs/roadmap.md`.
- Not encoded — frames are raw BGRA, so you want a fast LAN.
- Not signed — no MSI or code signature yet, so SmartScreen will warn.
- Not multi-monitor — first display only in v0.

## Theo extensions

The Python AI thinking partner (`python/agent/`) has grown a small set
of additions that other processes and the Flutter app can hook into.
Run `python -m agent.server` to start an HTTP bridge (FastAPI; defaults
to `127.0.0.1:8765`, override with `THEO_PORT`). It exposes `POST
/chat` for `{session_id, message}` -> `{reply}` and `GET /health`.
Sessions are in-memory per process, but durable memory keeps living in
`~/.techsupport_agent/`.

- **proteus_robinhood** — `portfolio_rh`, `buy_rh`, `sell_rh` against
  the Robinhood broker (env `RH_USERNAME`, `RH_PASSWORD`,
  `RH_MFA_TOTP`). Coexists with the existing Alpaca tools.
- **proteus_crypto** — `crypto_signals` ranks an env-configurable
  watchlist (`CRYPTO_WATCHLIST`, default BTC/ETH/SOL/DOGE) by RSI(14)
  plus drop-from-7d-high.
- **proteus_congress** — `congress_signals` pulls recent buys from the
  Capitol Trades public BFF and scores tickers by log-dollar-tier x
  distinct-politicians.
- **Typed memory** — `add_memory(kind, key, text, tags?)` and a
  hybrid-search `recall(query, kind?, k?)` build on the existing
  lancedb index. The append-only log lives at
  `~/.techsupport_agent/memory.jsonl`. Older `note` /
  `semantic_recall` / `recall_episodic` keep working.
- **theo_net (ml extra)** — a small PyTorch MLP that scores tickers
  on probability of beating SPY over 5 trading days. Install with
  `pip install -e .[ml]`. Train via `python -m ml.train --symbols
  AAPL,MSFT,NVDA --epochs 20`. Inference is exposed as the
  `theo_predict` tool.

## License

TBD — see LICENSE before shipping.
