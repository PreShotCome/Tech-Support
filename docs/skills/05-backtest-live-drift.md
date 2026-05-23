---
name: backtest-live-drift
description: Compare live paper-trading behavior and performance against the strategy's backtest expectations to detect overfitting, data bugs, and execution-modeling errors. Use this at session end and on a rolling basis to answer whether the strategy is actually viable.
---

# Backtest vs. Live Drift

A backtest is a hypothesis: "this strategy behaves like X." Live paper trading is the test of that hypothesis. When live behavior diverges from the backtest, the divergence has a cause, and the cause is almost always something you need to know: overfitting, a data bug, or an unrealistic execution assumption. This skill measures the divergence and names the likely cause. It is the core "is this viable?" instrument of the paper phase.

## When this runs

- At session end, comparing the session against the backtest's per-period expectations.
- On a rolling basis (e.g. weekly), comparing cumulative live results against cumulative backtest expectations over the same window.

## Prerequisites

This skill needs the backtest to have produced, for the relevant period, comparable expectations:

```
backtest_expectations:
  period:                the window being compared
  trade_count:           expected number of trades
  win_rate:              expected fraction of winning trades
  avg_win / avg_loss:    expected average P&L per winning / losing trade
  avg_holding_period:    expected time in trade
  signal_frequency:      how often each signal rule was expected to fire
  return:                expected return for the period
  max_drawdown:          expected worst drawdown for the period
```

If the backtest cannot produce these, that is the first finding — a strategy with no measurable expectations cannot be validated.

## The comparison procedure

1. **Assemble live actuals** for the same period from the decision log and order lifecycle records: realized trade count, win rate, avg win/loss, holding periods, per-signal fire counts, return, drawdown.

2. **Compute the divergence** on each metric — both absolute and as a ratio to the backtest expectation.

3. **Classify each metric:**
   - `in_line` — live within a tolerance band of backtest (tolerance is yours to set per metric).
   - `minor_drift` — outside tolerance but plausibly explained by sample size or normal variance.
   - `material_drift` — outside tolerance and not explained by variance.

4. **For every `material_drift`, attribute a likely cause** (see below).

5. **Write the drift report.** Do not "smooth over" divergence — the divergence is the product of this skill.

## Common causes and what they look like

| Symptom | Likely cause |
|---|---|
| Live win rate well below backtest; entries look right | Backtest used optimistic fills (no slippage, mid-price). Live fills are worse. |
| Live trade count far below backtest signal frequency | Signals firing in backtest but blocked live by validation, or a data-feed difference (different bars, timing). |
| Live trade count far above backtest | A signal rule behaving differently on live data; possible look-ahead bias removed in live that was present in backtest. |
| Avg win/loss skewed vs. backtest | Execution timing — live enters/exits later than the backtest assumed. |
| Live results dramatically worse across all metrics | Overfitting — the backtest was tuned to historical noise that does not recur. |
| Live drawdown exceeds backtest max drawdown | The backtest's worst case was not the real worst case; risk assumptions need revisiting. |
| Holding periods differ systematically | Exit logic interacting with live market hours / session rules differently than modeled. |

## Outputs

```
drift_report:
  period:           the compared window
  metrics:          map of metric -> {backtest, live, abs_diff, ratio, class}
  material_drifts:  list of {metric, likely_cause, evidence}
  overall:          tracking | drifting | diverged
  viability_note:   plain-language read on whether the strategy still
                    looks viable given this period's evidence
```

`overall` is `tracking` only if no metric is `material_drift`. One material drift → `drifting`. Multiple, or any drift in return/drawdown → `diverged`.

## Rules

1. **Slippage is the usual suspect.** Paper fills on Alpaca are optimistic relative to a live market with real liquidity. If live underperforms backtest and the entries are correct, suspect execution modeling before suspecting the signal.

2. **Small samples lie.** A handful of trades cannot confirm or refute a backtest. Mark `minor_drift` rather than `material_drift` until the live sample is large enough to be meaningful, and say so in `viability_note`.

3. **Diverged ≠ broken automatically, but it ≠ ignore.** A `diverged` report is the signal to investigate the strategy itself, not to keep collecting more divergent data and hoping.

4. **This report is the viability verdict.** The whole reason for the paper phase is to answer "is this worth running with real money." That answer lives in this report's `viability_note`, accumulated over enough periods.

## The paper-to-live transition

When you eventually consider moving from paper to real money: this skill does not retire — it becomes more important. Real-money fills introduce slippage and liquidity effects that paper does not. Expect a *further* drift step down from paper to live. Re-run this comparison continuously after any real-money cutover and treat the first weeks of real trading as another validation window, not a settled outcome. Whether the strategy clears that bar is a decision for you — this skill only supplies the evidence.

## What this skill is for

This is the instrument that tells you the truth about the strategy. Justification, validation, and reconciliation keep the bot honest and correct; this skill tells you whether the thing the bot is correctly and honestly doing actually works.
