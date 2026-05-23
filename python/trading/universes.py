"""Curated trading universes derived from public research.

These are starting points for backtesting and live deployment, not
recommendations. The MEGACAP_30 universe is what paper_runner and
train_basket default to. The CONGRESSIONAL_PICKS universe is a separate
basket assembled from specific tickers cited in the 2024-2026
Congressional-trading reporting summarized in docs/research/.

Pass any of these via --symbols on the CLI scripts.

MEMBERS_OF_INTEREST is a list of members frequently cited in
Unusual Whales / Capitol Trades reports as outperformers. The Quiver
feature builder can optionally filter to only this list to compute
'smart-money-only' aggregates rather than averaging across all of
Congress.
"""
from __future__ import annotations


# Original equal-weight megacap basket.
MEGACAP_30 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO",
    "BRK.B", "JPM", "JNJ", "V", "PG", "MA", "HD", "CVX", "ABBV",
    "MRK", "PEP", "KO", "COST", "WMT", "DIS", "BAC", "ADBE",
    "NFLX", "CRM", "AMD", "INTC", "QCOM",
]


# Subversive Capital "Unusual Whales" ETFs.
# NANC tracks disclosed Democratic Congressional trades.
# KRUZ tracks disclosed Republican Congressional trades.
# (KRUZ is intermittently marked inactive on Alpaca paper.)
CONGRESSIONAL_ETFS = ["NANC"]


# Tickers explicitly cited in docs/research/stock-market-deep.md as
# notable holdings or trades by frequently-discussed members of
# Congress. Curated to actually-tradeable symbols; private holdings
# (Databricks) and renamed-or-acquired tickers (Arcadium Lithium ALMT
# is now Rio Tinto Lithium) are excluded.
CONGRESSIONAL_PICKS = [
    # Big tech mentioned across many members
    "NVDA", "MSFT", "META", "AVGO", "AAPL", "AMZN", "GOOGL", "TSLA", "NFLX",
    # Pelosi-specific
    "PANW", "TEM", "DIS", "PYPL",
    # Crenshaw
    "WYNN", "KMI", "USO",
    # Wyden / Gottheimer
    "UPS", "FICO", "CRNX",
    # Mullin
    "SFM", "BMI", "FN",
    # Smith / McCaul / Wasserman Schultz / Moskowitz / Salazar / Newhouse / Carper
    "TCMD", "HWM", "HL", "VSAT", "LMT", "MRK", "DTM", "RTX", "VLO",
]


# Mag 7 — the AI/megacap concentration that drove most of 2023-2024
# index returns. Useful as a comparison basket for risk concentration.
MAG_7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]


# Default basket combines megacaps with the Congressional ETF.
DEFAULT_UNIVERSE = MEGACAP_30 + CONGRESSIONAL_ETFS


# Members of Congress frequently cited in 2024-2026 Unusual Whales,
# Capitol Trades, and Quiver reporting as either strong performers or
# heavily-discussed traders. Order is informational only. Surnames are
# in lowercase to make name normalization easier in the feature builder.
MEMBERS_OF_INTEREST = [
    "Nancy Pelosi",
    "Paul Pelosi",          # her husband; some disclosures list the spouse
    "Ron Wyden",
    "Josh Gottheimer",
    "Markwayne Mullin",
    "Tina Smith",
    "Jared Moskowitz",
    "Maria Elvira Salazar",
    "Maria Salazar",         # alternate name format used in some feeds
    "Michael McCaul",
    "Dan Crenshaw",
    "Marjorie Taylor Greene",
    "Debbie Wasserman Schultz",
    "Dan Newhouse",
    "Thomas Carper",
]


def normalize_member_name(name: str) -> str:
    """Lowercase + strip punctuation for fuzzy comparison across data feeds."""
    if not isinstance(name, str):
        return ""
    cleaned = []
    for ch in name:
        if ch.isalnum() or ch.isspace():
            cleaned.append(ch.lower())
    return " ".join("".join(cleaned).split())


def is_member_of_interest(disclosed_name: str) -> bool:
    """Loose match: True if any MEMBERS_OF_INTEREST is a substring of the
    disclosed name once normalized. Disclosed names are often inconsistent
    across data sources ('Rep. Nancy Pelosi' vs 'NANCY PELOSI' etc.)."""
    n = normalize_member_name(disclosed_name)
    for m in MEMBERS_OF_INTEREST:
        if normalize_member_name(m) in n:
            return True
    return False
