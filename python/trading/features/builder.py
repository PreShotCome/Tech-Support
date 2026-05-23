"""Compose an indicator panel from raw OHLCV. The output of this is
what every strategy actually sees."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import atr, bollinger, log_returns, macd, rolling_z, rsi


def build_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Take an OHLCV DataFrame indexed by UTC timestamp and return a
    feature matrix. Drops the warm-up bars where indicators are NaN."""
    close = ohlcv["close"]

    feats = pd.DataFrame(index=ohlcv.index)
    feats["ret_1"] = log_returns(close, 1)
    feats["ret_5"] = log_returns(close, 5)
    feats["ret_15"] = log_returns(close, 15)
    feats["ret_60"] = log_returns(close, 60)

    feats["rsi_14"] = rsi(close, 14)

    macd_df = macd(close, 12, 26, 9)
    feats["macd"] = macd_df["macd"]
    feats["macd_signal"] = macd_df["macd_signal"]
    feats["macd_hist"] = macd_df["macd_hist"]

    bb = bollinger(close, 20, 2.0)
    feats["bb_pct"] = bb["bb_pct"]
    feats["bb_width"] = (bb["bb_upper"] - bb["bb_lower"]) / bb["bb_mid"]

    feats["atr_14"] = atr(ohlcv["high"], ohlcv["low"], close, 14)
    feats["atr_pct"] = feats["atr_14"] / close

    feats["vol_z_30"] = rolling_z(ohlcv["volume"], 30)

    # Time-of-day cyclic encoding (US equities only trade 9:30-16:00 ET, but
    # the index can be in UTC — encode UTC hour-of-day directly).
    hour = ohlcv.index.hour + ohlcv.index.minute / 60.0
    feats["tod_sin"] = np.sin(2 * np.pi * hour / 24.0)
    feats["tod_cos"] = np.cos(2 * np.pi * hour / 24.0)
    feats["dow_sin"] = np.sin(2 * np.pi * ohlcv.index.dayofweek / 7.0)
    feats["dow_cos"] = np.cos(2 * np.pi * ohlcv.index.dayofweek / 7.0)

    return feats.dropna()
