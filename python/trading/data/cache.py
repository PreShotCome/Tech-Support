"""Disk cache for OHLCV dataframes. Parquet so it's fast and small."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pandas as pd


class ParquetCache:
    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            root = Path(os.environ.get("TRADING_CACHE_DIR",
                                       Path.home() / ".cache" / "trading"))
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode()).hexdigest()[:16]
        safe = "".join(c if c.isalnum() else "_" for c in key)[:60]
        return self.root / f"{safe}_{digest}.parquet"

    def get(self, key: str) -> pd.DataFrame | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return pd.read_parquet(p)
        except Exception:
            p.unlink(missing_ok=True)
            return None

    def put(self, key: str, df: pd.DataFrame) -> None:
        df.to_parquet(self._path(key), compression="zstd")

    def clear(self) -> None:
        for p in self.root.glob("*.parquet"):
            p.unlink(missing_ok=True)
