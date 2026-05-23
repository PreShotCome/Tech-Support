# Bot Playbook — durable memory across sessions

This file is the trading bot's institutional memory. Read it before you
extend the strategy. Every "obvious" idea below has already been tested
on this codebase and the result is recorded here so we don't redo work.

Last updated: 2026-05-23.

---

## 1. What's actually running in paper

- **Universe:** `MEGACAP_30 + NANC` (31 names — see
  `python/trading/universes.py:DEFAULT_UNIVERSE`).
- **Strategy:** equal-weight rebalance via `scripts.paper_runner`.
- **Schedule:** weekly. Cost drag observed at this cadence is ~0.02%
  per rebalance.
- **Honest performance expectation:** Sharpe ~3 in backtest 2018-2024.
  Expect a 20%+ drawdown at some point in any 5-year window. The
  benchmark is itself a strong strategy — beating it has proven hard
  with the tools we have.

## 2. What we tried and what it told us

| Approach | Walk-forward result | Verdict |
|---|---|---|
| Single-symbol intraday XGBoost (SPY 5Min, h=12) | val_auc 0.508 | No signal. Coin-flip. |
| Single-symbol intraday XGBoost (NVDA 5Min, h=12) | val_auc 0.526 raw; ~0 after fixing split | Tiny edge, eaten by costs |
| Single-symbol daily SPY | 989 rows total; val_auc 0.44 | Not enough samples |
| Cross-sectional ranking on 30 megacaps (1Day, h=1) | val_auc 0.61 single split | Looked great, walk-forward killed it |
| Same, walk-forward 9 windows | Mean alpha **-1.44%** per 6mo, IR -0.30 | **Strategy has no real edge** |
| Defensive overlay (regime model, binary cut to 30%) | Cut DD -19% → -6% in bear, lost 17% in recovery | Drawdown-cut works, exit timing fails |
| Defensive overlay (smooth scaling) | Persistent risk-off post-2022, missed recoveries | Same exit-timing problem |
| Richer features (vol regime, path, market-relative) | val_auc 0.6133 → 0.6057 | No improvement |
| Long-short top-5 / bottom-5 | -12% in test window | Short signal is broken |

**Bottom line:** simple ML on free OHLCV + technicals doesn't beat
equal-weight on this universe. The benchmark is too good.

## 3. The data sources that *might* unlock real alpha

Tried partially or wired but not validated yet:

- **NANC ETF (in the live basket now)** — Subversive Capital's
  Democratic-Congressional-trade tracker. Returned +27% in 2024 vs SPY
  +25% per Unusual Whales 2024 report.
- **Quiver Quantitative API ($10-30/mo)** — structured Congressional
  trade disclosures. Wired in `trading/data/quiver_client.py` and
  `trading/features/congressional.py`. Features available once
  `QUIVER_API_KEY` is set; `paper_shadow` picks them up automatically
  with smart-money filtering.
- **`CONGRESSIONAL_PICKS` universe** — 32 tickers explicitly cited in
  `docs/research/stock-market-deep.md` as notable holdings by
  high-performing members. Available as `trading.universes.CONGRESSIONAL_PICKS`
  for shadow comparison vs MEGACAP_30.

Not tried:

- News sentiment, options flow, fundamentals, intraday microstructure,
  cross-asset (rates / commodities / FX). These are the next-real-tier
  alpha sources.

## 4. The members of interest list

Per `docs/research/stock-market-deep.md`, these are the names cited as
notable performers in 2024-2026. The shadow model filters Congressional
features to *just* these members rather than averaging across all of
Congress, which is mostly noise.

(Lives in `trading.universes.MEMBERS_OF_INTEREST`.)

- Nancy Pelosi (D-CA) — and Paul Pelosi on disclosures
- Ron Wyden (D-OR) — Senate Finance Committee Ranking Member
- Josh Gottheimer (D-NJ) — House Financial Services
- Markwayne Mullin (R-OK) — known late filer, "third-party managed"
- Marjorie Taylor Greene (R-GA) — House Oversight
- Michael McCaul (R-TX) — Foreign Affairs, Homeland Security
- Dan Crenshaw (R-TX) — Energy and Commerce (lost 2026 primary)
- Tina Smith (D-MN) — Senate Health
- Jared Moskowitz (D-FL) — Foreign Affairs
- Maria (Elvira) Salazar (R-FL) — Foreign Affairs
- Dan Newhouse (R-WA) — Appropriations / Homeland Security
- Debbie Wasserman Schultz (D-FL) — Critical Minerals / Mil-Con
- Thomas Carper (D-DE, former) — Finance / Energy

**Caveat the model can't see:** "high performer in 2024" is
backward-looking. Whether they continue to outperform is what the live
shadow track record will tell us.

## 5. Rules of the road — things that have burned us

- **Backtest on a single holdout is not OOS.** Always walk-forward.
- **Costs eat small edges.** A 1% per-trade edge with weekly turnover
  ≈ 50% annual cost. Don't deploy anything that needs frequent
  rebalancing on free retail spreads.
- **Long-short doesn't fix a one-sided signal.** If the model's bottom
  picks aren't actually worse than average, the short leg just bleeds
  costs and adds drawdown.
- **Defensive models are sticky on the way out.** A model that learns
  "high vol = danger" will stay defensive deep into the recovery and
  give back the recovery gains.
- **Adjustments matter.** Set `adjustment="all"` on the Alpaca loader,
  not "raw" — splits cause fake -90% crashes otherwise (we hit this
  with NVDA's 10:1 split).
- **Validation slices need both classes.** Add a `y.nunique() < 2`
  guard or sklearn raises during `auc` calculation.
- **`PipeReader.Create(NetworkStream)` over loopback stalls** on some
  Windows configurations. We bypass it with raw `Stream.ReadAsync`.

## 6. The shadow loop — how to read it

`scripts.paper_shadow` runs weekly, retrains the cross-sectional model
on the trailing 5 years, predicts target weights for today, and logs to
`shadow_log.jsonl`. From the second run forward it prints:

```
ts                       shadow %    bench %    alpha %   shadow_cum   bench_cum
2026-05-23T...           +0.92       +0.85      +0.07     1.0092       1.0085
2026-05-30T...           +1.31       +1.50      -0.19     1.0224       1.0237
...
```

**Verdict criteria after ~12 weekly snapshots:**

- If shadow `cum > bench cum` consistently → consider switching
  `paper_runner` to use shadow weights.
- If they're indistinguishable → keep paper_runner as-is.
- If shadow < bench → kill the model, save the dev time.

Don't switch live trading on fewer than 8-10 weeks of data. The
walk-forward result already warned us this would likely not work
forward; let the live data either prove or disprove it.

## 7. The next experiment worth running

Ranked by expected impact:

1. **Subscribe to Quiver Quant** and let the shadow accumulate
   smart-money Congressional features for 8+ weeks. If shadow starts
   beating bench, that's the first real signal we have.
2. **Compare shadow universes side-by-side** — run a second shadow
   pointed at `CONGRESSIONAL_PICKS` and one at `MEGACAP_30`. After 8
   weeks we know whether the curated picks list does anything live.
3. **Risk overlay using VIX** — if/when Alpaca exposes VIX or a vol
   proxy is available, train a regime model that just cuts exposure
   when vol > X. Simpler than what we tried, possibly more durable.

Don't try, in order of futility:

- Single-symbol short-horizon prediction with technicals alone (proven
  no signal).
- Long-short on the existing cross-sectional model (the short side is
  broken; richer features didn't fix it).
- Adding more technical indicators to the existing feature panel.
  Diminishing returns past ~20 features.

## 8. Operational facts

- Trading account: Alpaca **paper** only. Endpoint must contain
  `paper-api`; `scripts.paper_runner` refuses to run against any other
  endpoint.
- API keys live as user environment variables, not in the repo:
  `ALPACA_KEY_ID`, `ALPACA_SECRET_KEY`, optionally `QUIVER_API_KEY`.
- Data cache: `~/.cache/trading/` (parquet for Alpaca,
  `~/.cache/trading/quiver/` for Quiver).
- Shadow log: `shadow_log.jsonl` in repo root.
- Scheduled tasks:
  - `paper_runner --execute` weekly Monday post-open
  - `paper_shadow` weekly Monday after paper_runner

---

If a future session is debating whether to do something this document
already covers, the answer is: **don't redo it; extend the playbook.**
