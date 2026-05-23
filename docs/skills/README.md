# Trading Bot Skills — Paper Phase

Six skills for a Claude-powered trading bot running on Alpaca paper trading. They assume a risk framework (position caps, exposure cap, position-count cap, per-trade loss cap, kill-switch thresholds) is already defined and loaded. The skills **enforce and observe** that framework — they do not define strategy or set limits.

## The six skills

| # | Skill | Role |
|---|---|---|
| 1 | `trade-justification` | Structured, falsifiable rationale before every order. Unjustifiable → blocked. |
| 2 | `pre-trade-validation` | Hard mechanical gate against framework limits. Any failed check → blocked. |
| 3 | `order-lifecycle` | Tracks orders to a confirmed terminal state; handles partials, rejections, unknowns. |
| 4 | `position-reconciliation` | Keeps the internal model equal to broker truth; drift halts trading. |
| 5 | `backtest-live-drift` | Compares live vs. backtest; the viability verdict for the paper phase. |
| 6 | `session-state-review` | Preflight check; no trading until session state is verified. |

## Execution order

**Session start:** `session-state-review` (6) → which invokes `position-reconciliation` (4) and `order-lifecycle` (3) to resolve anything in flight.

**Per trade:** `trade-justification` (1) → `pre-trade-validation` (2) → submit → `order-lifecycle` (3) → on fill, `position-reconciliation` (4).

**Periodic during session:** `position-reconciliation` (4) on a timer; `pre-trade-validation` (2) re-checks the kill-switch live.

**Session end / rolling:** `backtest-live-drift` (5).

## How they interlock

- 1 and 2 are the gate on *entering* a trade. 1 is reasoning, 2 is mechanics.
- 3 and 4 are correctness — they keep the position model true so 2's checks mean something.
- 6 makes sure 4 and the framework are sound before any of it runs.
- 5 stands apart: it judges whether the strategy the other five faithfully execute actually works.

## Design notes

- These are written as procedures, not advice. "Be careful" appears nowhere; specific blocking conditions appear everywhere. The framework is the confine — the skills make it binding.
- The failure-handling content in skills 3 and 4 (partial fills, rejections, the unknown-execution state, state drift) is correctness, not conservatism. A bot that mishandles those reports positions it doesn't have, which makes every framework check downstream meaningless.
- Every skill writes a structured log record. In the paper phase those logs *are* the research output — blocked-trade counts, justification quality, reconciliation drift, and backtest divergence are how you learn whether the bot is viable.

## Paper → live

When considering a move to real money: skill 5 (`backtest-live-drift`) becomes more important, not less — real fills add slippage and liquidity effects paper does not model. Treat the first real-money window as another validation period. Whether the strategy clears that bar is a decision for you, ideally with a professional; these skills supply evidence, not an investment recommendation.

## Updating

Each skill is a standalone file — update one without touching the others. If you change a framework value, the skills don't change (they read the framework); if you change *how* a check works, edit only that skill's file.
