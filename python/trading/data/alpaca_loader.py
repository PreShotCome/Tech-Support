"""Alpaca historical-bar loader.

Free Alpaca paper key is enough to pull historical data — no funded
account required. Set ALPACA_KEY_ID and ALPACA_SECRET_KEY in the env or
pass them directly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from .cache import ParquetCache


@dataclass(frozen=True)
class BarSpec:
    symbol: str
    timeframe: str            # "1Min", "5Min", "15Min", "1Hour", "1Day"
    start: datetime           # inclusive, UTC-aware
    end: datetime             # exclusive, UTC-aware
    feed: str = "iex"         # "iex" (free) or "sip" (paid)
    adjustment: str = "raw"   # "raw", "split", "dividend", "all"

    def cache_key(self) -> str:
        return (f"alpaca_{self.symbol}_{self.timeframe}_{self.feed}_{self.adjustment}"
                f"_{self.start.isoformat()}_{self.end.isoformat()}")


class AlpacaLoader:
    """Wraps alpaca-py's StockHistoricalDataClient with a parquet cache."""

    def __init__(
        self,
        key_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        cache: Optional[ParquetCache] = None,
    ) -> None:
        self.key_id = key_id or os.environ.get("ALPACA_KEY_ID", "")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY", "")
        self.cache = cache or ParquetCache()
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not self.key_id or not self.secret_key:
            raise RuntimeError(
                "Alpaca API keys not set. Export ALPACA_KEY_ID and ALPACA_SECRET_KEY "
                "or pass them to AlpacaLoader().")
        # Lazy import so the trading package can be imported without alpaca-py.
        from alpaca.data.historical import StockHistoricalDataClient
        self._client = StockHistoricalDataClient(self.key_id, self.secret_key)
        return self._client

    def load(self, spec: BarSpec, use_cache: bool = True) -> pd.DataFrame:
        """Return a DataFrame indexed by UTC timestamp with columns
        open/high/low/close/volume/trade_count/vwap."""
        if use_cache:
            cached = self.cache.get(spec.cache_key())
            if cached is not None:
                return cached

        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        amount, unit = _parse_timeframe(spec.timeframe)
        client = self._ensure_client()
        req = StockBarsRequest(
            symbol_or_symbols=spec.symbol,
            timeframe=TimeFrame(amount, unit),
            start=spec.start,
            end=spec.end,
            feed=spec.feed,
            adjustment=spec.adjustment,
        )
        bars = client.get_stock_bars(req).df
        if bars is None or bars.empty:
            df = pd.DataFrame(columns=[
                "open", "high", "low", "close", "volume", "trade_count", "vwap"
            ])
            df.index = pd.DatetimeIndex([], tz="UTC", name="timestamp")
            return df

        # alpaca-py returns a multi-index (symbol, timestamp); drop the symbol level
        if isinstance(bars.index, pd.MultiIndex):
            bars = bars.droplevel(0)
        bars.index = bars.index.tz_convert("UTC")
        bars.index.name = "timestamp"
        bars = bars[["open", "high", "low", "close", "volume", "trade_count", "vwap"]]
        bars = bars.sort_index()

        if use_cache:
            self.cache.put(spec.cache_key(), bars)
        return bars


def _parse_timeframe(tf: str):
    from alpaca.data.timeframe import TimeFrameUnit
    tf = tf.strip()
    # Accept "1Min", "5Min", "15Min", "1Hour", "1Day"
    for suffix, unit in (
        ("Min", TimeFrameUnit.Minute),
        ("Hour", TimeFrameUnit.Hour),
        ("Day", TimeFrameUnit.Day),
        ("Week", TimeFrameUnit.Week),
        ("Month", TimeFrameUnit.Month),
    ):
        if tf.endswith(suffix):
            num = int(tf[:-len(suffix)])
            return num, unit
    raise ValueError(f"Unrecognized timeframe {tf!r}")


def utc(dt: datetime | str) -> datetime:
    """Convenience: ensure a datetime (or ISO string) is timezone-aware UTC."""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
