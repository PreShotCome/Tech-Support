"""Proteus Robinhood tools — broker-switched naming (suffix _rh) so they
coexist with the Alpaca tools in trading.py.

Login is lazy: we wait until the first tool call to authenticate, so
importing this module doesn't hit Robinhood. Credentials come from env:
  RH_USERNAME, RH_PASSWORD, RH_MFA_TOTP (the seed, not a code)

robin_stocks is an optional dep — install with `pip install robin_stocks`.
"""
from __future__ import annotations

import os
from typing import Any

from .base import Tool


_LOGGED_IN = False


def _rh():
    """Return the robin_stocks module after ensuring login."""
    global _LOGGED_IN
    try:
        import robin_stocks.robinhood as rh
    except ImportError as e:
        raise RuntimeError(
            "robin_stocks not installed. Install with: pip install robin_stocks"
        ) from e

    if _LOGGED_IN:
        return rh

    user = os.environ.get("RH_USERNAME", "")
    pw = os.environ.get("RH_PASSWORD", "")
    if not user or not pw:
        raise RuntimeError(
            "RH_USERNAME / RH_PASSWORD not set in environment."
        )

    totp_seed = os.environ.get("RH_MFA_TOTP", "").strip()
    mfa_code = None
    if totp_seed:
        try:
            import pyotp
            mfa_code = pyotp.TOTP(totp_seed).now()
        except ImportError:
            # Try to login without — robin_stocks may prompt or fail.
            pass

    try:
        if mfa_code:
            rh.login(user, pw, mfa_code=mfa_code)
        else:
            rh.login(user, pw)
    except Exception as e:
        raise RuntimeError(f"Robinhood login failed: {e}") from e

    _LOGGED_IN = True
    return rh


def _portfolio_rh() -> dict[str, Any]:
    rh = _rh()
    profile = rh.profiles.load_account_profile() or {}
    portfolio = rh.profiles.load_portfolio_profile() or {}
    positions_raw = rh.account.get_open_stock_positions() or []

    positions = []
    for p in positions_raw:
        qty = float(p.get("quantity", 0) or 0)
        if qty <= 0:
            continue
        instrument_url = p.get("instrument", "")
        symbol = ""
        try:
            # robin_stocks helper to resolve instrument -> symbol
            symbol = rh.stocks.get_symbol_by_url(instrument_url) or ""
        except Exception:
            pass
        avg_buy = float(p.get("average_buy_price", 0) or 0)
        positions.append({
            "symbol": symbol,
            "qty": qty,
            "avg_buy_price": avg_buy,
            "market_value": qty * avg_buy,
        })

    return {
        "cash": float(profile.get("cash", 0) or 0),
        "buying_power": float(profile.get("buying_power", 0) or 0),
        "equity": float(portfolio.get("equity", 0) or 0),
        "market_value": float(portfolio.get("market_value", 0) or 0),
        "n_positions": len(positions),
        "positions": positions,
    }


def _buy_rh(symbol: str, dollar_amount: float | None = None,
            quantity: float | None = None) -> dict[str, Any]:
    rh = _rh()
    if dollar_amount is None and quantity is None:
        raise ValueError("Provide either dollar_amount or quantity.")
    symbol = symbol.upper().strip()
    if dollar_amount is not None:
        order = rh.orders.order_buy_fractional_by_price(symbol, float(dollar_amount))
    else:
        order = rh.orders.order_buy_market(symbol, float(quantity))
    return {"symbol": symbol, "side": "buy", "order": order}


def _sell_rh(symbol: str, dollar_amount: float | None = None,
             quantity: float | None = None) -> dict[str, Any]:
    rh = _rh()
    if dollar_amount is None and quantity is None:
        raise ValueError("Provide either dollar_amount or quantity.")
    symbol = symbol.upper().strip()
    if dollar_amount is not None:
        order = rh.orders.order_sell_fractional_by_price(symbol, float(dollar_amount))
    else:
        order = rh.orders.order_sell_market(symbol, float(quantity))
    return {"symbol": symbol, "side": "sell", "order": order}


PORTFOLIO_RH = Tool(
    name="portfolio_rh",
    description=(
        "Get current Robinhood positions, cash, buying power, and "
        "equity. Live brokerage account — these are real numbers."
    ),
    parameters_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    handler=_portfolio_rh,
)

BUY_RH = Tool(
    name="buy_rh",
    description=(
        "Place a market buy on Robinhood. Pass either dollar_amount "
        "(fractional) or quantity (whole shares). Live brokerage — "
        "this executes immediately."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol."},
            "dollar_amount": {"type": "number", "description": "Fractional dollar order size."},
            "quantity": {"type": "number", "description": "Whole-share quantity."},
        },
        "required": ["symbol"],
        "additionalProperties": False,
    },
    handler=_buy_rh,
)

SELL_RH = Tool(
    name="sell_rh",
    description=(
        "Place a market sell on Robinhood. Pass either dollar_amount "
        "(fractional) or quantity (whole shares). Live brokerage."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol."},
            "dollar_amount": {"type": "number", "description": "Fractional dollar order size."},
            "quantity": {"type": "number", "description": "Whole-share quantity."},
        },
        "required": ["symbol"],
        "additionalProperties": False,
    },
    handler=_sell_rh,
)


def register(registry) -> None:
    for t in (PORTFOLIO_RH, BUY_RH, SELL_RH):
        registry.register(t)
