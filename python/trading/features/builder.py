"""Compose an indicator panel from raw OHLCV. Output is what every
strategy sees. Optionally accepts a market reference series (e.g. SPY
close) to add market-relative features."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .indicators import (
    atr,
    bollinger,
    distance_from_ma,
    drawdown_from_high,
    intraday_range_pct,
    log_returns,
    macd,
    position_in_range,
    realized_vol,
    relative_strength,
    rolling_beta,
    rolling_kurtosis,
    rolling_skew,
    rolling_z,
    rsi,
    runup_from_low,
)


def build_features(
    ohlcv: pd.DataFrame,
    market_close: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """Build the feature matrix.

    If `market_close` is provided (e.g. SPY close series), market-relative
    features (beta, relative-strength, alpha proxies) are added on top of
    the single-asset features.
    """
    close = ohlcv["close"]
    high = ohlcv["high"]
    low = ohlcv["low"]

    feats = pd.DataFrame(index=ohlcv.index)

    # Returns at multiple horizons
    ret_1 = log_returns(close, 1)
    feats["ret_1"] = ret_1
    feats["ret_5"] = log_returns(close, 5)
    feats["ret_15"] = log_returns(close, 15)
    feats["ret_60"] = log_returns(close, 60)

    # Momentum / oscillator
    feats["rsi_14"] = rsi(close, 14)
    macd_df = macd(close, 12, 26, 9)
    feats["macd"] = macd_df["macd"]
    feats["macd_signal"] = macd_df["macd_signal"]
    feats["macd_hist"] = macd_df["macd_hist"]

    # Bands
    bb = bollinger(close, 20, 2.0)
    feats["bb_pct"] = bb["bb_pct"]
    feats["bb_width"] = (bb["bb_upper"] - bb["bb_lower"]) / bb["bb_mid"]

    # Range / volatility
    feats["atr_14"] = atr(high, low, close, 14)
    feats["atr_pct"] = feats["atr_14"] / close
    feats["intraday_range"] = intraday_range_pct(high, low, close)
    feats["pos_in_range"] = position_in_range(high, low, close)

    # Realized volatility at multiple horizons (the regime input)
    feats["rv_5"] = realized_vol(ret_1, 5)
    feats["rv_20"] = realized_vol(ret_1, 20)
    feats["rv_60"] = realized_vol(ret_1, 60)

    # Path features
    feats["dd_20"] = drawdown_from_high(close, 20)
    feats["dd_60"] = drawdown_from_high(close, 60)
    feats["runup_20"] = runup_from_low(close, 20)
    feats["dist_ma_20"] = distance_from_ma(close, 20)
    feats["dist_ma_50"] = distance_from_ma(close, 50)
    feats["dist_ma_200"] = distance_from_ma(close, 200)

    # Distribution shape of recent returns
    feats["skew_20"] = rolling_skew(ret_1, 20)
    feats["kurt_20"] = rolling_kurtosis(ret_1, 20)

    # Volume regime
    feats["vol_z_30"] = rolling_z(ohlcv["volume"], 30)

    # Time-of-day cyclic encoding
    hour = ohlcv.index.hour + ohlcv.index.minute / 60.0
    feats["tod_sin"] = np.sin(2 * np.pi * hour / 24.0)
    feats["tod_cos"] = np.cos(2 * np.pi * hour / 24.0)
    feats["dow_sin"] = np.sin(2 * np.pi * ohlcv.index.dayofweek / 7.0)
    feats["dow_cos"] = np.cos(2 * np.pi * ohlcv.index.dayofweek / 7.0)

    # Market-relative features
    if market_close is not None and not market_close.empty:
        mkt_ret = np.log(market_close).diff()
        feats["beta_60"] = rolling_beta(ret_1, mkt_ret, 60)
        feats["rs_5"] = relative_strength(ret_1, mkt_ret, 5)
        feats["rs_20"] = relative_strength(ret_1, mkt_ret, 20)
        feats["rs_60"] = relative_strength(ret_1, mkt_ret, 60)

    return feats.dropna()
