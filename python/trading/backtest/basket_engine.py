"""Multi-asset backtest. Takes a weights DataFrame (timestamps × symbols),
applies the standard signal-at-t / fill-at-t+1 lag, computes per-bar
net return after costs.

Weights at bar t are the *target* portfolio weights to achieve at the
open of bar t+1. Rows should sum to <= 1.0 in absolute terms; any
remainder is implicit cash. Negative weights are shorts."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .costs import CostModel
from .engine import BacktestResult, BacktestConfig


def run_basket_backtest(
    close_panel: pd.DataFrame,         # wide: index=timestamp, cols=symbols
    target_weights: pd.DataFrame,      # same shape, values in [-1, 1]
    cfg: BacktestConfig | None = None,
    strategy_name: str = "strategy",
) -> BacktestResult:
    if cfg is None:
        cfg = BacktestConfig()

    # Align and ffill weights to the price panel, then lag one bar.
    weights = target_weights.reindex_like(close_panel).ffill().fillna(0.0)
    weights = weights.shift(1).fillna(0.0)

    # Per-bar return = sum over symbols of weight * pct_change.
    bar_returns = close_panel.pct_change().fillna(0.0)
    gross = (weights * bar_returns).sum(axis=1)

    # Turnover: sum |Δweight| across symbols per bar.
    dweights = weights.diff().fillna(weights.iloc[0])
    turnover = dweights.abs().sum(axis=1)
    cost_drag = turnover * cfg.cost.one_way_bps / 10_000.0

    net = gross - cost_drag
    equity = cfg.starting_cash * (1.0 + net).cumprod()
    equity.name = "equity"

    # For BacktestResult.position we store gross exposure (sum |w|)
    gross_exposure = weights.abs().sum(axis=1)

    return BacktestResult(
        equity=equity,
        position=gross_exposure,
        returns=net,
        gross_returns=gross,
        cost_drag=cost_drag,
        turnover=turnover,
        cfg=cfg,
        strategy_name=strategy_name,
        symbol="(basket)",
    )
