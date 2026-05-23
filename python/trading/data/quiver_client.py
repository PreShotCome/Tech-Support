"""Quiver Quantitative API client for Congressional trading data.

Quiver aggregates STOCK Act disclosures (Periodic Transaction Reports)
into a structured feed. Their /historical/congresstrading/{ticker}
endpoint returns a list of trades with: ReportDate, TransactionDate,
Ticker, Representative, Transaction (Purchase/Sale), Range, House.

We use the trade-disclosure stream as alternative-data features. The
hypothesis is that Congressional members concentrated in committees
overseeing a given sector may have information advantages, and their
aggregated buying / selling pressure can signal forward returns.

Subscribe at https://api.quiverquant.com to get a key, then set:
    $env:QUIVER_API_KEY = "..."
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests


class QuiverClient:
    BASE_URL = "https://api.quiverquant.com/beta"

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        cache_max_age_hours: float = 24.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("QUIVER_API_KEY", "")
        self.cache_dir = cache_dir or Path.home() / ".cache" / "trading" / "quiver"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_max_age_hours = cache_max_age_hours
        self._session = requests.Session()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def congressional_trades(self, ticker: str) -> pd.DataFrame:
        """Per-ticker disclosed Congressional trades.

        Returns DataFrame with columns:
            transaction_date, report_date, representative, party,
            chamber (House/Senate), transaction (Purchase/Sale),
            range_low, range_high
        Empty DataFrame if Quiver is disabled or no trades reported.
        """
        if not self.enabled:
            return _empty()

        cached = self._read_cache(f"congress_{ticker}")
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/historical/congresstrading/{ticker}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        try:
            r = self._session.get(url, headers=headers, timeout=15)
        except requests.RequestException as e:
            print(f"  quiver: {ticker} fetch error: {e}")
            return _empty()
        if r.status_code != 200:
            # 404 = no data for ticker; just return empty
            if r.status_code in (404, 204):
                self._write_cache(f"congress_{ticker}", _empty())
                return _empty()
            print(f"  quiver: {ticker} HTTP {r.status_code}: {r.text[:200]}")
            return _empty()

        data = r.json()
        df = _normalize(data)
        self._write_cache(f"congress_{ticker}", df)
        return df

    # ------------------------------------------------------------------ cache

    def _cache_path(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() else "_" for c in key)
        return self.cache_dir / f"{safe}.parquet"

    def _read_cache(self, key: str) -> Optional[pd.DataFrame]:
        p = self._cache_path(key)
        if not p.exists():
            return None
        age_hours = (time.time() - p.stat().st_mtime) / 3600.0
        if age_hours > self.cache_max_age_hours:
            return None
        try:
            return pd.read_parquet(p)
        except Exception:
            return None

    def _write_cache(self, key: str, df: pd.DataFrame) -> None:
        try:
            df.to_parquet(self._cache_path(key), compression="zstd")
        except Exception:
            pass


def _normalize(records: list[dict]) -> pd.DataFrame:
    if not records:
        return _empty()
    df = pd.DataFrame(records)

    def col(*candidates: str) -> Optional[str]:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    out = pd.DataFrame()
    out["transaction_date"] = pd.to_datetime(
        df[col("TransactionDate", "transactionDate", "transaction_date")], utc=True, errors="coerce"
    )
    out["report_date"] = pd.to_datetime(
        df[col("ReportDate", "reportDate", "report_date")], utc=True, errors="coerce"
    )
    out["representative"] = df[col("Representative", "representative", "Member") or "representative"]
    out["chamber"] = df[col("House", "chamber", "Chamber")] if col("House", "chamber", "Chamber") else None
    out["party"] = df[col("Party", "party")] if col("Party", "party") else None
    tx_col = col("Transaction", "transaction")
    out["transaction"] = df[tx_col] if tx_col else None
    if "Range" in df.columns or "range" in df.columns:
        out["range"] = df[col("Range", "range")]
        out["range_low"], out["range_high"] = zip(*out["range"].map(_parse_range))
    else:
        out["range_low"] = pd.NA
        out["range_high"] = pd.NA
    return out.dropna(subset=["transaction_date"]).sort_values("transaction_date").reset_index(drop=True)


def _parse_range(s: object) -> tuple[float, float]:
    """Disclosure ranges look like '$1,001 - $15,000' or '$50,001 -'."""
    if not isinstance(s, str):
        return (float("nan"), float("nan"))
    cleaned = s.replace("$", "").replace(",", "").replace(" ", "")
    if "-" not in cleaned:
        try:
            v = float(cleaned)
            return (v, v)
        except ValueError:
            return (float("nan"), float("nan"))
    lo, _, hi = cleaned.partition("-")
    try:
        lo_v = float(lo) if lo else float("nan")
    except ValueError:
        lo_v = float("nan")
    try:
        hi_v = float(hi) if hi else lo_v
    except ValueError:
        hi_v = float("nan")
    return (lo_v, hi_v)


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "transaction_date", "report_date", "representative", "chamber",
        "party", "transaction", "range_low", "range_high",
    ])
