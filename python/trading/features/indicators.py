"""Technical indicators. All vectorized over pandas Series; no loops."""
from __future__ import annotations

import numpy as np
import pandas as pd


def log_returns(close: pd.Series, periods: int = 1) -> pd.Series:
    """Log return over `periods` bars."""
    return np.log(close).diff(periods)


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Returns DataFrame with columns macd, macd_signal, macd_hist."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": hist,
    })


def bollinger(
    close: pd.Series,
    window: int = 20,
    n_std: float = 2.0,
) -> pd.DataFrame:
    """Bollinger bands. Returns columns: bb_mid, bb_upper, bb_lower, bb_pct."""
    mid = close.rolling(window, min_periods=window).mean()
    std = close.rolling(window, min_periods=window).std(ddof=0)
    upper = mid + n_std * std
    lower = mid - n_std * std
    # %B: where price sits between bands (0 = lower, 1 = upper)
    pct = (close - lower) / (upper - lower)
    return pd.DataFrame({
        "bb_mid": mid,
        "bb_upper": upper,
        "bb_lower": lower,
        "bb_pct": pct,
    })


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
) -> pd.Series:
    """Average True Range (Wilder)."""
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()


def rolling_z(s: pd.Series, window: int) -> pd.Series:
    """Rolling z-score: (x - mean) / std."""
    mu = s.rolling(window, min_periods=window).mean()
    sd = s.rolling(window, min_periods=window).std(ddof=0)
    return (s - mu) / sd.replace(0, np.nan)


def realized_vol(returns: pd.Series, window: int) -> pd.Series:
    """Rolling standard deviation of returns — realized volatility proxy."""
    return returns.rolling(window, min_periods=window).std(ddof=0)


def drawdown_from_high(close: pd.Series, window: int) -> pd.Series:
    """How far below the rolling N-bar high (always <= 0)."""
    high = close.rolling(window, min_periods=window).max()
    return (close - high) / high


def runup_from_low(close: pd.Series, window: int) -> pd.Series:
    """How far above the rolling N-bar low (always >= 0)."""
    low = close.rolling(window, min_periods=window).min()
    return (close - low) / low.replace(0, np.nan)


def position_in_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Where close sits within the bar's high-low range: 0 = at low, 1 = at high."""
    span = (high - low).replace(0, np.nan)
    return (close - low) / span


def intraday_range_pct(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Bar range as a percentage of close — intraday volatility proxy."""
    return (high - low) / close.replace(0, np.nan)


def distance_from_ma(close: pd.Series, window: int) -> pd.Series:
    """Percent distance from the rolling mean — positive when above."""
    ma = close.rolling(window, min_periods=window).mean()
    return (close - ma) / ma.replace(0, np.nan)


def rolling_skew(returns: pd.Series, window: int) -> pd.Series:
    return returns.rolling(window, min_periods=window).skew()


def rolling_kurtosis(returns: pd.Series, window: int) -> pd.Series:
    return returns.rolling(window, min_periods=window).kurt()


def rolling_beta(returns: pd.Series, market_returns: pd.Series, window: int) -> pd.Series:
    """Rolling beta of returns to market_returns over `window` bars."""
    mkt = market_returns.reindex(returns.index)
    cov = returns.rolling(window, min_periods=window).cov(mkt)
    var = mkt.rolling(window, min_periods=window).var(ddof=0)
    return cov / var.replace(0, np.nan)


def relative_strength(returns: pd.Series, market_returns: pd.Series, window: int) -> pd.Series:
    """Cumulative log-return of asset minus market over the trailing `window` bars."""
    mkt = market_returns.reindex(returns.index)
    asset_cum = returns.rolling(window, min_periods=window).sum()
    mkt_cum = mkt.rolling(window, min_periods=window).sum()
    return asset_cum - mkt_cum
