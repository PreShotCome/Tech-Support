---
name: pre-trade-validation
description: Run a hard mechanical check against framework limits before submitting any order. Use this on every order, immediately after trade-justification and immediately before order submission. Any failed check blocks the order.
---

# Pre-Trade Validation

A deterministic gate between a justified trade and a submitted order. No judgment, no interpretation — each check is a boolean. Any `false` blocks the order. This skill assumes the risk framework (caps, stop rules, kill-switch thresholds) is already defined; it enforces, it does not decide.

## When this runs

Immediately before every order submission, after `trade-justification` has produced a record. The justification record supplies most inputs to these checks.

## The checklist

Run all checks. Do not short-circuit on the first failure — evaluate every check so the log shows the full picture.

```
validation:
  1. account_status_ok          account is active, not restricted, not in
                                liquidation-only; paper account responding
  2. market_open_for_symbol     symbol is tradable now; not halted; session
                                type (regular/extended) matches strategy rules
  3. buying_power_sufficient    available buying power >= order notional
  4. size_within_cap            position size % <= framework per-position cap
  5. exposure_within_cap        total deployed % after fill <= framework cap
  6. position_count_within_cap  open position count after fill <= framework cap
  7. stop_defined               an exit/stop price exists for this position
  8. stop_distance_sane         stop is on the correct side of entry and
                                non-zero distance; stop loss % <= framework
                                per-trade loss cap
  9. no_duplicate_order         no existing open order for same symbol+side
                                that this would unintentionally stack
  10. kill_switch_clear         daily and total drawdown are both inside
                                framework kill-switch thresholds
  11. symbol_not_blocklisted    symbol is not on any exclusion list the
                                framework defines
  12. order_params_valid        order type, time-in-force, qty, and limit
                                price (if any) are well-formed and non-null
```

## Outputs

```
validation_result:
  timestamp:        ISO-8601, UTC
  symbol:           ticker
  checks:           map of check_name -> true | false
  passed:           true only if ALL checks are true
  failed_checks:    list of names that returned false
  decision:         submit | block
```

## Rules

1. **All-true or block.** `decision` is `submit` only if every check is `true`. One `false` anywhere → `block`.

2. **No overrides.** There is no flag, confidence level, or signal strength that bypasses a failed check. If the strategy "really wants" a trade that fails check 5, the answer is still block. The framework is the confine; this skill is how the confine is enforced.

3. **Compute after-fill state, not current state.** Checks 5 and 6 evaluate exposure and position count *as they would be once this order fills*, not as they are now. A trade that is fine today and over-cap once filled must block.

4. **Kill-switch is checked here too.** Even though `session-state-review` checks it at session start, conditions change intra-session. Check 10 re-evaluates drawdown live. If the kill-switch threshold is crossed mid-session, every subsequent order blocks until the bot is reviewed.

5. **A block is data.** Write every `block` to the decision log with `failed_checks`. Recurring blocks on the same check during the paper phase tell you whether the strategy is systematically trying to exceed a limit — that is a finding, not noise.

6. **Validation failure ≠ silent skip.** A blocked order must be logged and, if it was an *exit* the strategy wanted, escalated (see below).

## Special case: blocked exits

If the blocked order was an **exit** (closing or reducing a position) and it failed a check, that is more serious than a blocked entry — the bot wanted out and couldn't form a valid order. Log it as `block` with `severity: high`, and surface it for review immediately rather than at end-of-session. A bot that can't exit cleanly is the failure mode that matters most to catch in paper.

## What this skill is for

This is the seatbelt. It does not make the bot conservative — it makes the framework's existing limits actually binding instead of advisory. Inside the limits, the strategy does whatever it does.
