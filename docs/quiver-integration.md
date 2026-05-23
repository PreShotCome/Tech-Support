# Quiver Quantitative integration — Congressional trade features

The basket trainer can optionally ingest Congressional trade disclosures
from Quiver Quantitative as alternative-data features. These are
disclosed under the **STOCK Act (2012)** — Periodic Transaction Reports
(PTRs) filed within 45 days of each trade. Quiver aggregates them into
a structured feed.

## Why it's interesting

Per the [Unusual Whales 2024 report](https://unusualwhales.com/congress-trading-report-2024):
- Democrat-traded portfolio avg 2024 return: **+31%**
- Republican-traded portfolio avg 2024 return: **+26%**
- SPY 2024 return: **+25%**
- ~50% of actively trading members beat the S&P 500

The signal isn't free: disclosures lag the trade by up to 45 days, and
ranges (e.g. `$1,001 - $15,000`) make exact dollar amounts unknown. Our
feature builder uses **report_date** (when disclosure became public),
not transaction_date, so we don't accidentally leak future information.

## Setup

1. Subscribe at https://api.quiverquant.com (their starter plan covers
   Congressional trading endpoints).
2. Set the API key:
   ```powershell
   $env:QUIVER_API_KEY = "..."
   # Or persist:
   [Environment]::SetEnvironmentVariable("QUIVER_API_KEY", "...", "User")
   ```
3. Run any pipeline with `--quiver` to enable:
   ```bash
   python -m scripts.train_basket --quiver --timeframe 1Day \
       --start 2018-01-01 --end 2024-06-30 --horizon 1
   ```

Disclosures are cached locally under `~/.cache/trading/quiver/` for 24h
to avoid hammering the API; subsequent runs only hit the network for
new tickers.

## What gets added

Per symbol, per timestamp, the trainer adds:

| Feature              | Meaning                                          |
|----------------------|--------------------------------------------------|
| `cong_n_buys_30`     | Disclosed purchase count in last 30 days         |
| `cong_n_sells_30`    | Disclosed sale count in last 30 days             |
| `cong_net_30`        | `buys - sells` over 30 days                       |
| `cong_dollars_30`    | Signed midpoint-of-range dollars over 30 days     |
| `cong_dem_net_30`    | Net Democratic buys-minus-sells                   |
| `cong_rep_net_30`    | Net Republican buys-minus-sells                   |
| `cong_*_90`          | Same metrics on a 90-day window                   |

The cross-sectional ranks include the net signals, so the model sees
*which symbols are accumulating Congressional buying right now* relative
to the rest of the basket.

## How to evaluate whether it helps

Compare walk-forward without and with Quiver:

```bash
# Baseline (price features only)
python -m scripts.walkforward --start 2018-01-01 --end 2024-06-30 --top-k 10

# Same harness, but with Congressional features mixed in.
# (Requires extending walkforward.py to also pass --quiver; not yet wired
# in this commit.)
```

If the with-Quiver IR meaningfully exceeds the without-Quiver IR, the
feature is contributing real signal. If not, it's noise we can drop.
