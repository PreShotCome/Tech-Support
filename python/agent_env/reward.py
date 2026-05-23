"""Reward sources read app-side state files written by the sims."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _default_state_dir() -> Path:
    appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(appdata) / "RLEnv"


class RewardSource:
    """Returns a scalar reward for the current step."""

    def reset(self) -> None: ...
    def reward(self) -> float: return 0.0
    def info(self) -> dict: return {}


class NullReward(RewardSource):
    pass


@dataclass
class TradingReward(RewardSource):
    """Reward = change in equity since last call. State file written by PaperTradingDesk."""
    state_path: Path = field(default_factory=lambda: _default_state_dir() / "trading_state.json")
    _last_equity: Optional[float] = None
    _last_state: dict = field(default_factory=dict)

    def reset(self) -> None:
        self._last_equity = None
        self._last_state = {}

    def _read(self) -> dict:
        try:
            with self.state_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def reward(self) -> float:
        st = self._read()
        self._last_state = st
        equity = float(st.get("equity", 0.0))
        if self._last_equity is None:
            self._last_equity = equity
            return 0.0
        delta = equity - self._last_equity
        self._last_equity = equity
        return delta

    def info(self) -> dict:
        return {
            "equity": self._last_state.get("equity"),
            "cash": self._last_state.get("cash"),
            "pnl": self._last_state.get("pnl"),
        }


@dataclass
class ComputeReward(RewardSource):
    """Reward = hashrate when running and not alerting, otherwise 0 (or negative on alert)."""
    state_path: Path = field(default_factory=lambda: _default_state_dir() / "compute_state.json")
    alert_penalty: float = 10.0
    _last_state: dict = field(default_factory=dict)

    def reset(self) -> None:
        self._last_state = {}

    def _read(self) -> dict:
        try:
            with self.state_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def reward(self) -> float:
        st = self._read()
        self._last_state = st
        if not st.get("running", False):
            return 0.0
        hashrate = float(st.get("hashRateMhs", 0.0))
        if st.get("hasAlert", False):
            return -self.alert_penalty
        return hashrate * 0.01

    def info(self) -> dict:
        return {
            "running": self._last_state.get("running"),
            "hashrate": self._last_state.get("hashRateMhs"),
            "temperature": self._last_state.get("temperatureC"),
            "hasAlert": self._last_state.get("hasAlert"),
        }
