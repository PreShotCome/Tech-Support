"""HTTP client for the TechSupport.Agent control endpoints."""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

import numpy as np
import requests


@dataclass(frozen=True)
class DisplayInfo:
    width: int
    height: int
    display_index: int
    stride: int
    format: str


class AgentClient:
    """Thin wrapper over the agent's HTTP control surface (port 7023 by default)."""

    def __init__(self, base_url: str = "http://127.0.0.1:7023", timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._info: Optional[DisplayInfo] = None

    @property
    def info(self) -> DisplayInfo:
        if self._info is None:
            r = self._session.get(f"{self.base_url}/info", timeout=self.timeout)
            r.raise_for_status()
            j = r.json()
            self._info = DisplayInfo(
                width=int(j["width"]),
                height=int(j["height"]),
                display_index=int(j["displayIndex"]),
                stride=int(j["stride"]),
                format=j["format"],
            )
        return self._info

    def grab_frame(self) -> np.ndarray:
        """Return the most recent desktop frame as an HxWx4 uint8 BGRA array."""
        r = self._session.get(f"{self.base_url}/frame", timeout=self.timeout)
        r.raise_for_status()
        info = self.info
        buf = np.frombuffer(r.content, dtype=np.uint8)
        # The agent may return stride > width*4 for some captures
        stride = int(r.headers.get("X-Stride", info.stride))
        height = int(r.headers.get("X-Height", info.height))
        width = int(r.headers.get("X-Width", info.width))
        frame = buf.reshape(height, stride // 4, 4)[:, :width, :]
        return frame

    def mouse_move(self, x: int, y: int) -> None:
        self._post("/mouse/move", {"x": x, "y": y})

    def mouse_button(self, x: int, y: int, button: int, pressed: bool) -> None:
        self._post("/mouse/button", {
            "x": x, "y": y, "button": button, "pressed": 1 if pressed else 0
        })

    def click(self, x: int, y: int, button: int = 0) -> None:
        self.mouse_button(x, y, button, pressed=True)
        self.mouse_button(x, y, button, pressed=False)

    def mouse_wheel(self, x: int, y: int, dx: int, dy: int) -> None:
        self._post("/mouse/wheel", {"x": x, "y": y, "dx": dx, "dy": dy})

    def key(self, vk: int, pressed: bool, scan: int = 0, extended: bool = False) -> None:
        self._post("/key", {
            "vk": vk, "sc": scan,
            "pressed": 1 if pressed else 0,
            "extended": 1 if extended else 0,
        })

    def _post(self, path: str, params: dict) -> None:
        r = self._session.post(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"{path} -> {r.status_code} {r.text}")
