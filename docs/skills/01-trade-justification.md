---
name: trade-justification
description: Produce a structured, auditable rationale for every trade decision before an order is placed. Use this on every entry, exit, scale-in, and scale-out. If a justification cannot be completed, the trade is not taken.
---

# Trade Justification

Every order is preceded by a justification record. The bot does not place an order it cannot justify against its own framework. This is not a review step — it is a gate. An unjustifiable trade is a blocked trade.

## When this runs

Before EVERY order of any kind: entry, exit, scale-in, scale-out, stop adjustment, hedge. No exceptions, including trades the bot considers "obvious."

## The justification record

Produce this as a structured object and write it to the decision log BEFORE the order is submitted. Every field is required. A field that cannot be filled is a hard stop — see "Incomplete justification" below.

```
trade_justification:
  timestamp:            ISO-8601, UTC
  symbol:               ticker
  action:               buy | sell | sell_short | buy_to_cover
  intent:               new_entry | exit | scale_in | scale_out | stop_move
  signal_source:        which strategy rule/indicator/model fired
  signal_detail:        the concrete values that triggered it
                        (e.g. "20EMA crossed 50EMA at 09:41; RSI 58")
  thesis:               one sentence — what the bot expects to happen and why
  framework_checks:
    position_size_pct:  computed size as % of account equity
    size_within_cap:    true | false  (cap value from framework)
    total_exposure_pct: deployed % across all positions AFTER this trade
    exposure_within_cap: true | false
    concurrent_positions: count AFTER this trade
    positions_within_cap: true | false
    stop_defined:       true | false  — exit price for this position
    stop_price:         the actual price
    stop_loss_pct:      loss at stop as % of account equity
  expected_outcome:     target/expectation in concrete terms
  invalidation:         what observation would prove this thesis wrong
  confidence:           the signal's own score, if the strategy produces one
```

## Rules

1. **Signal traceability.** `signal_source` and `signal_detail` must trace to a specific, named strategy rule. "Looked good" is not a signal. "Momentum" is not a signal. The exact rule and the exact values that triggered it are the signal.

2. **The thesis must be falsifiable.** `invalidation` must name an observable event. If there is no observation that would prove the trade wrong, the thesis is not a thesis and the trade is blocked.

3. **One trade, one record.** Do not batch. Each order gets its own record even if three orders fire on the same signal in the same second.

4. **The record is written before the order, not after.** Post-hoc justification is the failure mode this skill exists to prevent. If the order has already been submitted, the record is a log entry, not a justification — flag it as `post_hoc: true` so the audit catches it.

## Incomplete justification

If any field cannot be filled, OR any `*_within_cap` / `*_defined` field is `false`:

- Do not submit the order.
- Write the record anyway with status `blocked` and `blocked_reason` naming the failing field(s).
- A blocked trade is a logged event. The point of the paper phase is to count these.

## What this skill is for

In the paper phase the justification log is the primary research artifact. At session review, read it and ask: did the stated theses actually predict outcomes? Are signals being described precisely or vaguely? Are blocked trades clustering around one rule? The bot reasoning is only as good as this log is honest.
