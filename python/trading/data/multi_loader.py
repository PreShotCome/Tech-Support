"""Parallel loader for a basket of symbols. Returns a dict mapping
symbol -> OHLCV DataFrame, all aligned to the same timeframe and window."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import pandas as pd

from .alpaca_loader import AlpacaLoader, BarSpec


@dataclass
class MultiLoader:
    loader: AlpacaLoader
    max_workers: int = 6

    def load_basket(
        self,
        symbols: Iterable[str],
        timeframe: str,
        start: datetime,
        end: datetime,
        feed: str = "iex",
        adjustment: str = "all",
        use_cache: bool = True,
    ) -> dict[str, pd.DataFrame]:
        symbols = list(symbols)
        results: dict[str, pd.DataFrame] = {}

        def _load(sym: str) -> tuple[str, pd.DataFrame]:
            spec = BarSpec(sym, timeframe, start, end, feed=feed, adjustment=adjustment)
            return sym, self.loader.load(spec, use_cache=use_cache)

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(_load, s): s for s in symbols}
            for fut in as_completed(futures):
                sym, df = fut.result()
                if not df.empty:
                    results[sym] = df

        return results


def stack_panel(panel: dict[str, pd.DataFrame], price_col: str = "close") -> pd.DataFrame:
    """Pivot the basket into a wide DataFrame: rows = timestamps, columns = symbols."""
    return pd.DataFrame({sym: df[price_col] for sym, df in panel.items()}).sort_index()
