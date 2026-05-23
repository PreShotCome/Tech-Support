"""Performance metrics. Always reported together — total return alone
hides ruin risk."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .engine import BacktestResult


@dataclass(frozen=True)
class Summary:
    strategy: str
    symbol: str
    bars: int
    total_return: float       # final equity / starting cash - 1
    annualized_return: float
    annualized_vol: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    avg_turnover: float
    cost_drag_total: float
    hit_rate: float

    def as_row(self) -> dict:
        return {
            "strategy": self.strategy,
            "symbol": self.symbol,
            "bars": self.bars,
            "total_return": self.total_return,
            "annual_return": self.annualized_return,
            "annual_vol": self.annualized_vol,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "max_dd": self.max_drawdown,
            "calmar": self.calmar,
            "avg_turnover": self.avg_turnover,
            "cost_drag": self.cost_drag_total,
            "hit_rate": self.hit_rate,
        }


def summarize(result: BacktestResult, bars_per_year: float = 252 * 390) -> Summary:
    """`bars_per_year` defaults to ~98k for 1-minute US equity bars
    (252 trading days × 390 minutes/session). Override for other timeframes:
      1-Hour bars:  252 * 6.5  ≈ 1638
      Daily bars:   252
    """
    r = result.returns.dropna()
    if r.empty or r.std() == 0:
        return _empty_summary(result)

    total_return = float(result.equity.iloc[-1] / result.cfg.starting_cash - 1.0)
    n = len(r)

    mean = r.mean()
    sd = r.std(ddof=0)
    downside = r.clip(upper=0.0).std(ddof=0)
    ann_return = (1.0 + mean) ** bars_per_year - 1.0
    ann_vol = sd * np.sqrt(bars_per_year)
    sharpe = (mean / sd) * np.sqrt(bars_per_year) if sd > 0 else 0.0
    sortino = (mean / downside) * np.sqrt(bars_per_year) if downside > 0 else 0.0

    eq = result.equity
    peak = eq.cummax()
    dd = (eq / peak - 1.0).min()
    max_dd = float(dd)
    calmar = (ann_return / abs(max_dd)) if max_dd < 0 else 0.0

    avg_turnover = float(result.turnover.mean())
    cost_drag_total = float(result.cost_drag.sum())

    nonzero = r[r != 0.0]
    hit_rate = float((nonzero > 0).mean()) if not nonzero.empty else 0.0

    return Summary(
        strategy=result.strategy_name,
        symbol=result.symbol,
        bars=n,
        total_return=total_return,
        annualized_return=float(ann_return),
        annualized_vol=float(ann_vol),
        sharpe=float(sharpe),
        sortino=float(sortino),
        max_drawdown=max_dd,
        calmar=float(calmar),
        avg_turnover=avg_turnover,
        cost_drag_total=cost_drag_total,
        hit_rate=hit_rate,
    )


def _empty_summary(result: BacktestResult) -> Summary:
    return Summary(
        strategy=result.strategy_name, symbol=result.symbol, bars=0,
        total_return=0.0, annualized_return=0.0, annualized_vol=0.0,
        sharpe=0.0, sortino=0.0, max_drawdown=0.0, calmar=0.0,
        avg_turnover=0.0, cost_drag_total=0.0, hit_rate=0.0,
    )
