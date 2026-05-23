"""Features for regime detection. Single time series (not per-symbol).

We derive them from SPY OHLCV and basket breadth. The output is a
DataFrame indexed by timestamp; one row per bar. Designed to feed a
binary classifier that predicts forward market drawdown.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features.indicators import (
    distance_from_ma,
    drawdown_from_high,
    log_returns,
    realized_vol,
    rolling_kurtosis,
    rolling_skew,
    rolling_z,
)


def build_regime_features(spy: pd.DataFrame) -> pd.DataFrame:
    """Features computed from the market-index OHLCV (SPY)."""
    close = spy["close"]
    high = spy["high"]
    low = spy["low"]
    volume = spy["volume"]

    ret_1 = log_returns(close, 1)

    feats = pd.DataFrame(index=spy.index)

    # Volatility regime — the single best signal of "regime change"
    feats["spy_rv_5"] = realized_vol(ret_1, 5)
    feats["spy_rv_20"] = realized_vol(ret_1, 20)
    feats["spy_rv_60"] = realized_vol(ret_1, 60)
    feats["spy_rv_5_z"] = rolling_z(feats["spy_rv_5"], 60)
    feats["spy_rv_20_z"] = rolling_z(feats["spy_rv_20"], 252)

    # Drawdown from recent highs — the market knows when it's bleeding
    feats["spy_dd_20"] = drawdown_from_high(close, 20)
    feats["spy_dd_60"] = drawdown_from_high(close, 60)
    feats["spy_dd_252"] = drawdown_from_high(close, 252)

    # Distance from MAs — trend filter
    feats["spy_dist_ma_50"] = distance_from_ma(close, 50)
    feats["spy_dist_ma_200"] = distance_from_ma(close, 200)

    # Multi-horizon returns (cum log return)
    feats["spy_ret_5"] = log_returns(close, 5)
    feats["spy_ret_20"] = log_returns(close, 20)
    feats["spy_ret_60"] = log_returns(close, 60)

    # Distribution shape — fat tails / negative skew = crash risk
    feats["spy_skew_20"] = rolling_skew(ret_1, 20)
    feats["spy_kurt_20"] = rolling_kurtosis(ret_1, 20)

    # Intraday range — wide bars often precede regime shifts
    feats["spy_range_pct"] = (high - low) / close
    feats["spy_range_avg_5"] = feats["spy_range_pct"].rolling(5).mean()

    # Volume regime
    feats["spy_vol_z_30"] = rolling_z(volume, 30)

    # 50/200 MA cross (death-cross proxy)
    feats["spy_50_200"] = (
        close.rolling(50).mean() - close.rolling(200).mean()
    ) / close.rolling(200).mean()

    return feats.dropna()


def build_breadth_features(close_panel: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional breadth: features that summarize how broadly the
    basket is participating in (or fleeing) the move.

    `close_panel` is wide: index=timestamp, columns=symbols. Tolerant of
    missing data: when a stock has no history yet it's just excluded
    from that row's average rather than nulling the whole row."""
    ret = np.log(close_panel).diff()

    ma_20 = close_panel.rolling(20, min_periods=10).mean()
    ma_50 = close_panel.rolling(50, min_periods=25).mean()
    ma_200 = close_panel.rolling(200, min_periods=100).mean()

    feats = pd.DataFrame(index=close_panel.index)

    def _pct_above(close, ma):
        valid = ma.notna() & close.notna()
        above = (close > ma) & valid
        denom = valid.sum(axis=1).replace(0, np.nan)
        return above.sum(axis=1) / denom

    feats["pct_above_ma_20"] = _pct_above(close_panel, ma_20)
    feats["pct_above_ma_50"] = _pct_above(close_panel, ma_50)
    feats["pct_above_ma_200"] = _pct_above(close_panel, ma_200)

    feats["xs_std_5"] = ret.rolling(5, min_periods=3).sum().std(axis=1)
    feats["xs_std_20"] = ret.rolling(20, min_periods=10).sum().std(axis=1)

    bvar = ret.rolling(20, min_periods=10).mean().var(axis=1)
    mvar = ret.rolling(20, min_periods=10).var().mean(axis=1).replace(0, np.nan)
    feats["avg_corr_proxy"] = 1.0 - (bvar / mvar)

    return feats
