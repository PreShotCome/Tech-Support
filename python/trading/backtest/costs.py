"""Transaction cost model.

Per round-trip cost is in basis points (1 bp = 0.01%). For US equities
on Alpaca commission is $0, but spread + slippage is very real and is
the silent killer of every "profitable" intraday backtest.

Defaults:
  commission_bps = 0.0     (Alpaca free)
  spread_bps     = 2.0     (1 bp half-spread, paid on each leg)
  slippage_bps   = 1.0     (cushion for adverse fill, paid each leg)

So a round-trip costs ~6 bps. If your strategy turns over the book
twice a day, that's 24 bps/day = ~60% / year in friction. Be honest
about this number.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    commission_bps: float = 0.0
    spread_bps: float = 2.0
    slippage_bps: float = 1.0

    @property
    def one_way_bps(self) -> float:
        return self.commission_bps + self.spread_bps / 2.0 + self.slippage_bps

    @property
    def round_trip_bps(self) -> float:
        return 2.0 * self.one_way_bps
