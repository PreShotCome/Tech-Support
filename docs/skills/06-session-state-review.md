---
name: session-state-review
description: Verify all state before the bot is allowed to trade in a new session. Use this at the start of every run, after any restart, and after any connectivity interruption. The bot does not place its first order of a session until this review passes.
---

# Session State Review

A trading session does not begin with a trade. It begins with verifying that the bot's picture of the world is correct and its constraints loaded. A bot that starts trading on assumed continuity from a previous session — assumed positions, assumed limits, assumed connectivity — is trading blind. This skill is the gate on the start of every session.

## When this runs

- At the start of every run / session.
- After any process restart, crash recovery, or redeploy.
- After any connectivity interruption long enough to have missed order or market events.

## The review checklist

Run every item. The session is cleared to trade only when all items pass.

```
session_review:
  1. broker_connectivity      Alpaca API reachable; auth valid; account
                              endpoint responds.
  2. account_status_ok        account is active, not restricted, not
                              liquidation-only. (Paper account expected.)
  3. account_is_paper         confirm the account in use is the PAPER
                              account. A live account where paper is
                              expected is an immediate hard halt.
  4. framework_loaded         risk framework loaded and non-empty: per-
                              position cap, total exposure cap, position-
                              count cap, per-trade loss cap, kill-switch
                              thresholds. Each value present and sane.
  5. positions_reconciled     run `position-reconciliation`; result is
                              clean or benign.
  6. open_orders_reviewed     every pre-existing open order is accounted
                              for; any in-flight order from a prior
                              session is resolved via `order-lifecycle`.
  7. kill_switch_clear        current daily and total drawdown are inside
                              framework thresholds. If already breached,
                              the session starts halted.
  8. market_state_known       know whether the market is open, closed,
                              pre/post; know the session calendar for
                              today.
  9. data_feed_live           market data feed is connected and current;
                              timestamps on incoming data are fresh.
  10. clock_sane              system clock agrees with broker/market time
                              within tolerance — stale clocks corrupt
                              time-in-force and signal timing.
  11. logs_writable           decision log and lifecycle log are writable;
                              a session that cannot log cannot be audited
                              and must not trade.
```

## Procedure

1. Run all eleven checks.
2. If **all pass** → session is `cleared`. Trading may begin.
3. If **any fail** → session is `not_cleared`. The bot does not place orders. Go to the failure handling below.

## Failure handling

The response depends on which check failed:

- **Connectivity, data feed, or clock (1, 9, 10):** transient infrastructure problems. Retry with backoff for a bounded period. If still failing after the bound, hold the session in `not_cleared` and escalate — do not trade on a degraded feed or stale clock.

- **Account status or paper/live (2, 3):** hard halt. A restricted account or a live account where paper was expected is never traded through automatically. Escalate immediately.

- **Framework not loaded (4):** hard halt. The bot has no confines without the framework. A bot trading without loaded limits is the single worst state — never let it place an order. Escalate.

- **Reconciliation drift (5) or unresolved open orders (6):** resolve via `position-reconciliation` and `order-lifecycle` before clearing. If they cannot be resolved, the session stays `not_cleared`.

- **Kill-switch already breached (7):** the session starts `halted`. The bot may run, monitor, and reconcile, but places no new orders until the human reviews and explicitly resets.

- **Logs not writable (11):** hard halt. An unauditable session defeats the purpose of the paper phase. Fix logging before trading.

## Outputs

```
session_review_result:
  timestamp:        ISO-8601, UTC
  trigger:          session_start | restart | post_interruption
  checks:           map of check_name -> pass | fail
  status:           cleared | not_cleared | halted
  failed_checks:    list of failing check names
  action_taken:     trading_enabled | retrying | escalated | started_halted
```

## Rules

1. **No first order before `cleared`.** The session status gates the first order of the session, full stop.

2. **Restart is a new session.** A crash-and-restart does not resume the prior session's assumptions. It runs the full review again. In-flight orders from before the crash are resolved, not assumed.

3. **`halted` is a valid running state.** A halted bot still runs — it connects, monitors, reconciles, and logs. It just places no orders. This is deliberate: you want the bot observing even when it cannot act.

4. **Verify, do not assume continuity.** The recurring failure mode is "it was fine last session, so it's fine now." Positions move, limits get edited, connections drop, the account changes. Every session re-verifies from scratch.

## What this skill is for

This is the preflight check. It is cheap, it runs once per session, and it catches the class of failure where the bot trades confidently on a wrong picture of its own state. In the paper phase it also gives every session a known-good starting point, which makes the drift and reconciliation logs interpretable.
