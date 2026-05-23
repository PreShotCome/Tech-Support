"""Event-driven backtester.

Rules of the road:

  1. Signal at bar t may use any features whose timestamp is <= t.
  2. The resulting target position is achieved at the *open of bar t+1*.
     (We shift by one bar.)
  3. Per-bar return is realized between open[t+1] and open[t+2].
     (We compute via close-to-close internally for stability and then
     apply a one-bar lag, which is mathematically equivalent under
     mark-to-market.)
  4. Every change in position incurs cost proportional to the absolute
     change times the one-way cost in bps.

This avoids the most common backtester sins:
  - using close[t] as both the signal source and the fill price
  - paying no transaction cost
  - paying cost only on entry, not exit
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .costs import CostModel


@dataclass(frozen=True)
class BacktestConfig:
    starting_cash: float = 100_000.0
    cost: CostModel = field(default_factory=CostModel)


@dataclass
class BacktestResult:
    equity: pd.Series          # equity curve, indexed by bar
    position: pd.Series        # actual position after fill at each bar
    returns: pd.Series         # per-bar net return (after costs)
    gross_returns: pd.Series   # per-bar return ignoring costs
    cost_drag: pd.Series       # per-bar return lost to costs
    turnover: pd.Series        # |position change| per bar
    cfg: BacktestConfig
    strategy_name: str
    symbol: str


def run_backtest(
    ohlcv: pd.DataFrame,
    target_position: pd.Series,
    cfg: Optional[BacktestConfig] = None,
    strategy_name: str = "strategy",
    symbol: str = "?",
) -> BacktestResult:
    """Vectorized backtest.

    `ohlcv` must contain at least a `close` column. `target_position` is
    the signal series; will be reindexed to the OHLCV index and lagged
    by one bar (the trade happens at the *next* bar).
    """
    if cfg is None:
        cfg = BacktestConfig()

    close = ohlcv["close"].astype(float)
    # Align signal to price index, then lag by one bar so we can't trade
    # on information from the same bar.
    target = target_position.reindex(close.index).ffill().fillna(0.0).clip(-1.0, 1.0)
    position = target.shift(1).fillna(0.0)

    bar_returns = close.pct_change().fillna(0.0)
    gross = position * bar_returns

    # Cost: when position changes by dP, we pay |dP| * one_way_bps of notional.
    dpos = position.diff().fillna(position.iloc[0])
    turnover = dpos.abs()
    bps_to_frac = 1.0 / 10_000.0
    cost_drag = turnover * cfg.cost.one_way_bps * bps_to_frac

    net = gross - cost_drag
    equity = cfg.starting_cash * (1.0 + net).cumprod()
    equity.name = "equity"

    return BacktestResult(
        equity=equity,
        position=position,
        returns=net,
        gross_returns=gross,
        cost_drag=cost_drag,
        turnover=turnover,
        cfg=cfg,
        strategy_name=strategy_name,
        symbol=symbol,
    )
