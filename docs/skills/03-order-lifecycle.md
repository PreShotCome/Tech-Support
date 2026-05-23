---
name: order-lifecycle
description: Track every submitted order from submission to terminal state, and handle partial fills, rejections, timeouts, and the unknown-execution state correctly. Use this immediately after any order is submitted and until that order reaches a confirmed terminal state.
---

# Order Lifecycle

An order is not "done" when it is submitted. It is done when it reaches a confirmed terminal state. This skill governs the gap in between. The single most dangerous state in automated trading is *not knowing whether your order executed* — most of this skill exists to handle that state correctly.

## When this runs

From the moment an order is submitted until it reaches a confirmed terminal state for every order, no exceptions.

## Order states

```
submitted     -> sent to broker, no acknowledgement yet
accepted      -> broker acknowledged, working
partially_filled -> some quantity filled, remainder still working
filled        -> TERMINAL: full quantity filled
canceled      -> TERMINAL: order canceled before full fill
rejected      -> TERMINAL: broker refused the order
expired       -> TERMINAL: time-in-force elapsed
unknown       -> NON-TERMINAL: bot cannot confirm true state — see below
```

The bot's internal model of every order must be in exactly one of these states at all times. An order with no state is a bug.

## The lifecycle procedure

1. **On submission**, record the order with state `submitted`, a client-side `order_id`, submission timestamp, and the full order params. Start a timeout clock.

2. **Poll or consume order updates** from the Alpaca order stream / API. Update state on every event. Do not assume — read the broker's reported state.

3. **On a fill or partial fill**, record filled quantity, average fill price, and remaining quantity. Update the position model only from *confirmed* fill events, never from the assumption that a submitted order filled.

4. **On a terminal state** (`filled`, `canceled`, `rejected`, `expired`), close the lifecycle: stop polling, write the final record, release the order from the open-orders set.

5. **If the timeout clock elapses** before a terminal state is confirmed, the order enters `unknown`. Go to the unknown-state procedure.

## Partial fills

A partial fill is not an exit and not a failure — it is a position smaller than intended.

- Update the position model to the *actually filled* quantity.
- The remainder is still a working order: keep tracking it.
- Re-check framework exposure against the *actual* filled size — a position that partially filled may now leave room, or a follow-on order may now fit differently. Do not act on the *intended* size.
- If the remainder is still working and the strategy's reason for the trade has since invalidated, cancel the remainder rather than letting it fill into a stale thesis.

## Rejections

A rejected order did not execute. Record `rejected` with the broker's reason code verbatim.

- Do **not** auto-resubmit. A rejection means something about the order or account state was wrong; resubmitting blindly repeats the error.
- Route the rejection reason back through `pre-trade-validation` logic: did a check that passed at submission now fail? If so, the rejection is consistent with the framework — log and move on.
- If the rejection reason is *not* explained by any validation check (e.g. an unexpected broker-side reason), flag it for review. Unexplained rejections are findings.

## The unknown state — most important section

The bot reaches `unknown` when it submitted an order but cannot confirm the true outcome: API timeout, connection drop, ambiguous or missing response, or a restart with orders in flight.

**In the `unknown` state, the bot does not guess and does not place new orders for that symbol.**

Procedure:

1. **Freeze trading on the affected symbol.** No new entries, exits, or adjustments on that symbol until the order's true state is resolved.

2. **Reconcile against the broker as source of truth.** Query Alpaca directly for: the order's current status by `order_id`, and the current position in that symbol. The broker's record — not the bot's assumption — is authoritative.

3. **Resolve the state:**
   - If the broker shows the order in a terminal state → adopt it, update the position model from the broker's reported fills, close the lifecycle.
   - If the broker shows the order still working → resume normal tracking.
   - If the broker shows no record of the order at all → treat as not executed, but verify the position is consistent with that before resuming.

4. **If the true state still cannot be determined** after querying the broker, halt all trading on that symbol and escalate to the human. Do not trade a symbol whose position the bot cannot confirm. An uncertain position size makes every downstream framework check meaningless.

5. **Never** "assume it filled" or "assume it didn't" to keep the loop moving. Both assumptions can be wrong, and a wrong position model corrupts every subsequent decision.

## Outputs

Every order produces a lifecycle record:

```
order_lifecycle:
  order_id:          client-side id
  symbol:            ticker
  state_history:     ordered list of (state, timestamp) transitions
  final_state:       terminal state, or unknown if escalated
  intended_qty:      quantity at submission
  filled_qty:        confirmed filled quantity
  avg_fill_price:    confirmed average price
  reject_reason:     verbatim broker reason, if rejected
  unknown_resolution: how an unknown state was resolved, if applicable
  escalated:         true | false
```

## What this skill is for

This is correctness, not caution. A bot that mishandles partial fills or unknown states will report a position it does not have, and every framework limit computed against that phantom position is wrong. Building and hardening this in the paper phase is the entire point of paper trading — find the order-handling bugs here, where they cost nothing.
