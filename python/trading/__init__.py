"""Proteus — the trading bot. Backtest harness, baselines, ML model.

The package separates three concerns deliberately:

  data/         price ingestion + cache (Alpaca historical bars)
  features/     deterministic feature engineering on OHLCV
  strategies/   anything that maps features -> signal (-1 / 0 / +1)
  backtest/     event-driven simulator that turns signals into a P&L curve
                with realistic costs (commission + slippage)
  portfolio/    position + cash tracking

The brain (strategy) only ever sees features. The backtester is the only
thing that knows about prices, costs, and fills. This is the boring but
critical separation that prevents lookahead bias from creeping in.

Theo invokes Proteus through the registered trading tools (portfolio,
orders, market_clock, rebalance_plan, etc.) plus the safety surface
(validate_trade, reconcile_positions, session_preflight, etc.).
"""

__version__ = "0.1.0"
