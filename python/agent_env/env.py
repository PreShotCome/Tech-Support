"""Gymnasium environment that wraps the agent + a reward source."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .client import AgentClient
from .reward import NullReward, RewardSource


# Action layout — a single composite Discrete action selects one of these macro types,
# then a separate Box describes its parameters. We use a Dict action space so the
# agent picks both at once, and we discretize mouse XY into an NxN grid so PPO can
# learn from a finite categorical head per axis.
@dataclass
class EnvConfig:
    obs_size: tuple[int, int] = (84, 84)        # downsample for the network
    mouse_grid: int = 32                         # 32x32 click targets
    max_steps: int = 1024
    step_sleep_s: float = 0.1
    base_url: str = "http://127.0.0.1:7023"


class DesktopAgentEnv(gym.Env):
    metadata = {"render_modes": ["rgb_array"]}

    def __init__(
        self,
        config: Optional[EnvConfig] = None,
        reward: Optional[RewardSource] = None,
    ):
        super().__init__()
        self.config = config or EnvConfig()
        self.reward_source = reward or NullReward()
        self.client = AgentClient(base_url=self.config.base_url)
        self._steps = 0
        self._last_frame: Optional[np.ndarray] = None

        h, w = self.config.obs_size
        self.observation_space = spaces.Box(0, 255, shape=(h, w, 3), dtype=np.uint8)

        # action = (action_type, grid_x, grid_y)
        # action_type: 0=noop, 1=mouse_move, 2=left_click, 3=right_click, 4=wheel_up, 5=wheel_down
        self.action_space = spaces.MultiDiscrete([6, self.config.mouse_grid, self.config.mouse_grid])

    # --- gym API -------------------------------------------------------------

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self._steps = 0
        self.reward_source.reset()
        obs = self._observe()
        return obs, {}

    def step(self, action):
        action_type, gx, gy = int(action[0]), int(action[1]), int(action[2])
        info = self.client.info
        # Map grid coords back into desktop pixel coords (centered in cell)
        cell_w = info.width / self.config.mouse_grid
        cell_h = info.height / self.config.mouse_grid
        x = int((gx + 0.5) * cell_w)
        y = int((gy + 0.5) * cell_h)

        self._dispatch(action_type, x, y)
        # Brief sleep so the GUI has time to react before we read state/screenshot.
        if self.config.step_sleep_s > 0:
            import time
            time.sleep(self.config.step_sleep_s)

        obs = self._observe()
        reward = float(self.reward_source.reward())
        self._steps += 1
        terminated = False
        truncated = self._steps >= self.config.max_steps
        return obs, reward, terminated, truncated, {"reward": self.reward_source.info()}

    def render(self):
        return self._last_frame

    def close(self):
        pass

    # --- helpers -------------------------------------------------------------

    def _dispatch(self, action_type: int, x: int, y: int) -> None:
        if action_type == 0:
            return
        if action_type == 1:
            self.client.mouse_move(x, y)
        elif action_type == 2:
            self.client.click(x, y, button=0)
        elif action_type == 3:
            self.client.click(x, y, button=1)
        elif action_type == 4:
            self.client.mouse_wheel(x, y, 0, 120)
        elif action_type == 5:
            self.client.mouse_wheel(x, y, 0, -120)

    def _observe(self) -> np.ndarray:
        frame = self.client.grab_frame()  # HxWx4 BGRA
        # to RGB and downsample
        rgb = frame[..., [2, 1, 0]]
        self._last_frame = rgb
        return _resize_nn(rgb, *self.config.obs_size)


def _resize_nn(img: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Nearest-neighbour downsample, pure-numpy so we don't need cv2."""
    h, w = img.shape[:2]
    ys = (np.linspace(0, h - 1, out_h)).astype(np.int32)
    xs = (np.linspace(0, w - 1, out_w)).astype(np.int32)
    return img[ys[:, None], xs[None, :]]
