"""The bot's risk framework — the *confines* that the operational
skills (pre-trade-validation, session-state-review, etc.) enforce.

These are deliberate limits the bot must operate inside. They are NOT
strategy — strategy decides what to do inside the limits.

Edit values here; nothing else changes. The skills read this module
and don't redefine any of the values.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskFramework:
    # Per-position notional cap, as a fraction of account equity.
    position_cap: float = 0.05        # 5% per name

    # Total gross-exposure cap (sum of |weights|).
    exposure_cap: float = 1.00        # 100% invested (no leverage)

    # Maximum number of concurrent positions.
    position_count_cap: int = 40

    # Per-trade loss cap — distance to stop, as fraction of equity.
    # For the equal-weight basket we don't run stops, so this is the
    # *effective* notional risk per name == position_cap.
    per_trade_loss_cap: float = 0.05

    # Kill-switch: cumulative drawdown thresholds at which the bot stops
    # opening new positions. Daily = since session start; total = since
    # the high-water mark.
    daily_drawdown_kill: float = 0.05     # 5% intraday drawdown
    total_drawdown_kill: float = 0.20     # 20% from high-water mark

    # Symbols the bot will not trade even if asked.
    blocklist: tuple[str, ...] = ()

    # Tolerance for account-state reconciliation (broker vs internal).
    cash_tolerance_dollars: float = 1.00
    equity_tolerance_dollars: float = 5.00

    # How fresh price/account data must be before a decision.
    max_data_age_seconds: float = 300.0


# Singleton. Treat as immutable at runtime; edit the dataclass defaults
# rather than mutating the instance.
DEFAULT = RiskFramework()
