# agent_env — Gymnasium env over the TechSupport agent

Wraps the Windows agent's HTTP control surface (`/info`, `/frame`,
`/mouse/*`, `/key`) in a Gymnasium environment so any RL stack can train
against the desktop.

## Install

```bash
cd python
python -m venv .venv
.venv\Scripts\activate
pip install -e .
# for training (PPO etc)
pip install -e .[train]
```

## Smoke test

Start the agent and at least one of the sim apps on Windows, then:

```bash
python -m scripts.random_baseline --task trading --steps 200
```

You should see the env reset, frames stream, and the random agent rack up
reward (negative just as often as positive — that's the point of the
baseline).

## Reward sources

- `TradingReward` — reads `%LOCALAPPDATA%\RLEnv\trading_state.json` from
  `PaperTradingDesk`. Reward = change in account equity per step.
- `ComputeReward` — reads `%LOCALAPPDATA%\RLEnv\compute_state.json` from
  `ComputeDashSim`. Reward = scaled hashrate when running, large penalty
  on thermal alert.
- `NullReward` — for protocol smoke tests.

## Action space

`MultiDiscrete([6, grid, grid])`:

- `action_type`: `0=noop`, `1=move`, `2=left click`, `3=right click`,
  `4=wheel up`, `5=wheel down`
- `grid_x, grid_y`: cell on a 32x32 grid over the desktop

Coarse on purpose. PPO will hate a continuous mouse-XY action space and
struggle with anything bigger.
