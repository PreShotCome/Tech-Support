# Phase 1 — RL environment scaffold

## What changed

The Tech-Support codebase pivoted from a tech-support remote-access tool
to a **GUI agent research environment**. The Windows agent stays — its
DXGI capture and `SendInput` injection are exactly what an RL policy
needs to operate a desktop — and we add:

- **`src/ComputeDashSim/`** — system-monitor sim. WPF window with
  hashrate gauge, fan slider, algorithm dropdown, temp/alert state.
  Writes live JSON state to `%LOCALAPPDATA%\RLEnv\compute_state.json`
  so the RL env has a clean reward channel.
- **`src/PaperTradingDesk/`** — Alpaca paper-trading sandbox. WPF
  window with watchlist, buy/sell, positions table, equity readout.
  Uses real Alpaca paper-trading when API keys are present, falls back
  to a local random-walk price simulator when not. State JSON at
  `%LOCALAPPDATA%\RLEnv\trading_state.json`.
- **`src/TechSupport.Agent/Net/HttpControlServer.cs`** — adds an HTTP
  control surface on `127.0.0.1:7023` so Python can grab frames and
  inject input without speaking the binary TCP protocol:
  - `GET /info` — display dims + format
  - `GET /frame` — raw BGRA bytes for the current frame
  - `POST /mouse/move?x=&y=`
  - `POST /mouse/button?x=&y=&button=&pressed=`
  - `POST /mouse/wheel?x=&y=&dx=&dy=`
  - `POST /key?vk=&sc=&pressed=&extended=`
- **`python/`** — Gymnasium env, reward sources, random baseline.
  See `python/README.md`.

## Wire diagram

```
+-------------------------------+         +-------------------------+
|  Windows desktop              |         |  Python (any host)      |
|                               |         |                         |
|  ComputeDashSim ───────┐      |         |  agent_env (Gymnasium)  |
|                        ↓      |         |       │                 |
|                  state JSONs ─┼────────►│  reward source          |
|  PaperTradingDesk ─────┘      |         |       │                 |
|                               |         |  policy (PPO etc)       |
|  TechSupport.Agent ◄──────────┼─ HTTP ──┤       │                 |
|   - DXGI capture ──── /frame  |         |       ▼                 |
|   - SendInject ◄─── /mouse,*  |         |   action                |
+-------------------------------+         +-------------------------+
```

The agent + sims run on Windows. The RL trainer can run anywhere with
network access to `127.0.0.1:7023` (in practice, the same Windows box
or a Linux box with port forwarding for headless training).

## Run order

1. **Start the agent.** It opens both 7022 (binary TCP, technician
   console) and 7023 (HTTP, RL env).
   ```powershell
   dotnet run --project src\TechSupport.Agent -c Debug
   ```
2. **Start one or both sims.** They take focus, are visible to the
   agent's capture, and start writing state JSON.
   ```powershell
   dotnet run --project src\ComputeDashSim -c Debug
   dotnet run --project src\PaperTradingDesk -c Debug
   ```
   For real prices, edit `src\PaperTradingDesk\appsettings.json` with
   your Alpaca paper-trading keys before running.
3. **Run the random baseline** (proves the loop):
   ```bash
   cd python
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e .
   python -m scripts.random_baseline --task trading --steps 200
   ```

## What's *not* in Phase 1

- PPO / actual learning. Goes in Phase 2 once we know the env loop is
  solid. Tooling: Stable-Baselines3 + a CNN encoder.
- Scripted baseline. Optional — the random one is enough to prove the
  pipeline.
- A second-monitor capture mode. Currently primary display only.

## Known issues

- Alpaca's free paper-trading data feed has limits. Heavy training runs
  should replay cached prices rather than hammer the live feed.
- The action space (32×32 click grid, 6 action types) is intentionally
  coarse. Bigger grids work but PPO will need more samples to converge.
- The HTTP control endpoint has no auth. Loopback-only by default. Do
  not expose 7023 to anything but localhost.
