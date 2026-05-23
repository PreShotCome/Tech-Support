---
name: position-reconciliation
description: Continuously verify that the bot's internal model of positions, orders, and account state matches what the broker actually reports. Use this at session start, after every fill, on a periodic timer, and before any session-level decision. Drift between internal and broker state halts trading.
---

# Position Reconciliation

The bot keeps an internal model of what it owns. The broker keeps the real record. These must agree. When they do not, the broker is right and the bot is wrong — and a wrong position model silently corrupts every framework check, every justification, and every risk calculation downstream. This skill detects that drift and stops trading before it compounds.

## When this runs

- At session start (before any trade — see `session-state-review`).
- After every confirmed fill or partial fill.
- On a periodic timer during the session (e.g. every N minutes).
- Before any session-level decision (e.g. evaluating total exposure).
- Always after resolving an `unknown` order state.

## What gets reconciled

For each, compare the bot's internal model against a fresh query to the Alpaca API:

```
reconciliation_scope:
  positions:
    - symbol
    - quantity        (signed: long positive, short negative)
    - avg_entry_price
  open_orders:
    - order_id
    - symbol, side, qty, type, status
  account:
    - equity
    - cash
    - buying_power
    - account_status   (active / restricted / etc.)
```

## The reconciliation procedure

1. **Fetch broker state.** Query Alpaca for current positions, open orders, and account values. This is the source of truth.

2. **Diff against the internal model.** For each item, compare. Classify every discrepancy:

   - `missing_internal` — broker has a position/order the bot does not.
   - `missing_broker` — bot has a position/order the broker does not.
   - `qty_mismatch` — same symbol, different quantity.
   - `price_mismatch` — same symbol, materially different avg entry price.
   - `account_mismatch` — equity/cash/buying-power differ beyond a tiny rounding tolerance.

3. **Classify severity:**
   - **Clean** — no discrepancies. Continue normally. Log the clean check.
   - **Benign** — differences fully explained by in-flight orders or known timing lag (e.g. a fill confirmed by the broker but not yet folded into the model this cycle). Adopt broker state, log, continue.
   - **Drift** — any discrepancy not fully explained by timing. Go to the drift procedure.

4. **Adopt broker state as truth.** Whenever the broker and the model disagree and the difference is real, overwrite the internal model with the broker's values. The bot never "wins" a reconciliation dispute.

## The drift procedure

Drift means the bot's view of reality is wrong in a way it cannot explain. This is a halt condition.

1. **Stop opening new positions immediately.** No new entries until drift is resolved.

2. **Determine whether existing positions can still be managed safely.** If the drift is isolated to one symbol, trading on *other* symbols may continue at the human's discretion — but the drifted symbol is frozen.

3. **Investigate the cause.** Common causes: a fill that was missed by the order stream, an `unknown` order that resolved differently than assumed, a bot restart that lost in-flight state, a manual change on the account, a bug in the position-update logic. Record the most likely cause.

4. **Reconcile to broker truth**, then re-run the reconciliation. If it now comes back clean, log the resolution and the cause, and resume.

5. **If drift cannot be explained or keeps recurring**, halt all trading and escalate to the human. Recurring unexplained drift is a bug in the bot's state handling — it must be fixed, not traded through.

## Outputs

```
reconciliation_result:
  timestamp:        ISO-8601, UTC
  trigger:          session_start | post_fill | timer | pre_decision | post_unknown
  status:           clean | benign | drift
  discrepancies:    list of {type, symbol, internal_value, broker_value}
  cause:            explanation, if drift
  action_taken:     none | adopted_broker_state | halt_new | halt_all | escalated
```

## Rules

1. **Broker is truth, always.** There is no scenario where the internal model overrides the broker. If they disagree, the model is wrong.

2. **Unexplained drift halts.** Benign timing differences are fine. Anything not explained by timing stops new positions until resolved.

3. **Reconcile before you reason.** Any decision that depends on "how much do I have" or "what's my exposure" must run on freshly reconciled state, not stale model state.

4. **Log clean checks too.** A history of clean reconciliations is what lets you trust the model. Only logging failures hides the base rate.

## What this skill is for

This is the dashboard's accuracy check. The paper phase is exactly where state-handling bugs surface — a missed fill, a restart that drops in-flight orders. Catching drift here, where positions are imaginary money, is the difference between finding the bug and finding it later with real capital on the line.
