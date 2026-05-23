# Phase 2 v0 — Trading bot brain (backtest harness)

## Scope of this commit

This commit drops the GUI-agent loop as the *brain* (the agent and sims
stay around for the screen-control demo) and pivots to a serious
intraday trading pipeline. v0 is the foundation: **backtesting**.

No ML model yet. Three baseline strategies (buy-and-hold, momentum
crossover, RSI mean-reversion) so we have something to beat, and a
backtester strict enough to catch the usual lookahead and free-trade
fictions.

## Layout

```
python/trading/
  data/          Alpaca historical loader + parquet cache (~/.cache/trading)
  features/      Indicators (RSI, MACD, Bollinger, ATR, time-of-day) +
                 a builder that composes the feature matrix
  strategies/    Strategy ABC + buy_hold / momentum_xover / rsi_mr baselines
  backtest/      Cost model, event-driven engine, performance metrics
python/scripts/
  backtest.py    Run one strategy on one symbol
  compare.py     Run all baselines side by side
```

## What the backtester actually does

The single most common trading-bot self-deception is using `close[t]`
both to compute the signal *and* to fill the trade. Our engine:

1. Strategies emit a target position from features at bar `t`.
2. We shift the target by one bar — fills happen at bar `t+1`.
3. Per-bar return is the *close-to-close* return at the position you
   actually held that bar (mathematically equivalent to fills at the
   open of the next bar, under mark-to-market).
4. Every change in position pays cost = `|ΔP| × one_way_bps`.
   Defaults: 0 bp commission + 2 bp spread (1 bp half-spread per leg)
   + 1 bp slippage = 2 bp one-way, 4 bp round-trip.

If your strategy looks great with these costs disabled and bad with
them on, it doesn't have an edge — it has friction debt.

## Setup

```bash
cd python
.\.venv\Scripts\activate
pip install -e .[trading]

# Alpaca API key (free, paper account)
$env:ALPACA_KEY_ID = "YOUR_KEY"
$env:ALPACA_SECRET_KEY = "YOUR_SECRET"
```

Sign up at https://alpaca.markets/ (paper account is free, doesn't
require funded money). The same key works for both historical data and
live paper trading.

## Run

```bash
# One strategy
python -m scripts.backtest --symbol SPY --timeframe 5Min \
    --strategy momentum --start 2024-01-01 --end 2024-06-30

# All baselines side by side
python -m scripts.compare --symbol SPY --timeframe 5Min \
    --start 2024-01-01 --end 2024-06-30
```

## What to expect

Honest expectations from intraday baselines on US equities:

- **Buy-and-hold** on an index like SPY usually wins on raw return
  during bull markets.
- **Momentum crossover** outperforms in trending markets, loses to
  whipsaws in chop.
- **RSI mean-reversion** can be flat-to-positive but turnover is high,
  so costs eat a lot.

If any of these have a Sharpe > 1.5 in a 6-month backtest, suspect a
bug before celebrating. Real intraday Sharpe > 1 is rare; > 2 is
publishable.

## What's next

- **Phase 2 v1**: XGBoost classifier on the existing feature panel.
  Walk-forward CV. Output: a strategy that wraps the trained model.
- **Phase 2 v2**: Live paper-trading runner. Streams Alpaca bars in,
  applies the same feature pipeline, sends orders.
- **Phase 2 v3** (gated on v1+v2 working): controlled go-live with
  small capital. Only after weeks of paper trading look credible.
