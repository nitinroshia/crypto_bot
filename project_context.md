# Project Context: ETH/USDT & BTC/USDT Research (ETH/FDUSD retained as history)

## Current pairs (work order 1.4, 2026-09-23 -- owner-approved, not a proposal)

**ETH/USDT and BTC/USDT are the project's two live pairs, for both research and execution.**
ETH/FDUSD is retired as an execution-pair candidate: its liquidity (2.0-4.5% of ETH/USDT's daily
trade count in every fully-covered 2026 month) makes realized slippage on it too uncertain to plan
around, regardless of any research finding. ETH/FDUSD's existing results below (the fingerprint,
the dead lead-lag result, the Task 2 baseline) stay as historical reference; no further formula
work targets it. Every "S1", "S2", "Task 3" mention below that predates this work order refers to
ETH/FDUSD/BTC/USDT-replication-only history -- from work order 1.4 on, S1/S2/Task 3/Task 4 each run
as two fully independent families, `<task>-ETHUSDT` and `<task>-BTCUSDT`, each with its own Holm
adjustment, registry entry, freeze and forward test. See `docs/work-orders/1.4.md` for the full
decision and `context/STATUS.md` for current status.

## What this document is for

This project has a working, tested data pipeline and a first statistical
fingerprint of real ETH/FDUSD market data. The infrastructure phase is done.
This document exists so a fresh conversation — an AI or a human, doing
either the math or the coding side of this project (see below) — can start
directly on the mathematics without re-deriving any of the plumbing, and
without silently repeating mistakes that were already found and fixed once.

**Ground rule carried from the start of this project and still in force:**
no threshold, parameter, or rule gets adopted because it "looks right" on a
chart. Everything is derived from what the data actually shows, tested for
statistical significance, and validated out-of-sample before being trusted.

## Why this project is structured the way it is

The deliverable of this project is extensive, statistically validated
backtesting — that's the actual goal of the math phase, not a formality
before building a strategy someone already believed in. A rule earns its
way into the strategy by surviving the process below; it doesn't start
there and get confirmed.

Math and code are deliberately done by different people/AI, in isolation
from each other. Whoever designs a formula — a research-focused AI, a
different AI than whoever writes code, or a human — does not need to be
whoever implements it in `research_cli.py`, and shouldn't need to be. That
separation is the entire reason the "Formula contract" section below exists
as its own explicit thing, written in plain language as well as in Python:
it's the interface between those two roles.

Two things follow from that, and both are worth holding to on either side
of the handoff:
- A formula proposal should be written so someone who has never seen this
  codebase's Python can still hand it to a coding AI or dev and get a
  correct implementation back — precise about what the predictor is, what
  the target is, and what range of lags to test, without needing to
  reference any function or file name.
- Whoever implements a formula should be able to do so correctly without
  needing to know WHY it might work economically — only what it computes
  and what shape it must return. If implementing a proposal requires
  guessing at the proposer's intent, the proposal wasn't specific enough
  yet, and the fix is to sharpen the natural-language description, not to
  have the coder guess.

## The trading strategy this eventually feeds

A freqtrade bot (`MomentumTrailing`) trading on Binance spot. Research
pair: ETH/USDT. Execution pair: to be confirmed by the owner (default
ETH/USDT); the placeholder strategy has so far been run on ETH/FDUSD.
Current (placeholder) rule: enter on a single-candle % rise, exit via a
trailing stop. This rule is intentionally naive — the whole point of the
math phase is to replace "1% because it seemed reasonable" with parameters
that are justified by the statistical structure of the actual data. Every
value that placeholder rule needs (timeframe, entry threshold, stoploss,
trailing-stop numbers) now lives in `user_data/test_params.json`, not in
the strategy file — see the strategy layer's own README for that.

## Data available

*(Updated 2026-09-20, after work order 1.2. Every number below was measured on the real files by `task0_report.py`.)*

- Pair: ETH/FDUSD, Binance spot. Comparison pairs for cross-pair work:
  ETH/USDT and FDUSD/USDT.
- **Research pair (work order 1.2): ETH/USDT.** Discovery and walk-forward
  use data up to and including **2025-08-31**, enforced by an `--end-date`
  guard still to be built; everything after that date is a **locked holdout**
  read only by the forward-test command, once per candidate. The ETH/USDT
  5m history back to 2017-08-17, BTC/USDT 1h/1d (replication asset) and
  perpetual funding-rate history are part of a pending data batch and are not
  yet on disk (the raw store currently holds ETH/USDT 5m from 2023-08-04).
- **ETH/FDUSD is reference only.** Its sample is post-break: 2026-01-29 (the
  day taker fees returned for everyone) is treated as a structural break, the
  break day is excluded, and the ETH/FDUSD sample starts 2026-01-30 00:00 UTC.
  Full-history ETH/FDUSD runs are skipped: they add looks and mix regimes.
- **freqtrade files:** `user_data/data/binance/ETH_FDUSD-{1m,5m,15m,30m,1h,1d,1w}.feather`
  (columns: date, open, high, low, close, volume).
  - **1m runs 2026-01-30 to 2026-09-19: 335,520 bars, 233 days, no missing
    minutes.** It is entirely post-break.
  - **5m and coarser reach back to 2023-08-04**, so about 80% of their rows
    predate the break. Any post-break result must trim them
    (`run_fingerprint.py --start-date 2026-01-30`, or slice in the formula).
    Post-break bar counts: 5m 67,104; 15m 22,368; 30m 11,184; 1h 5,592;
    1d 233; 1w 32.
- **Raw-kline store:** `user_data/data/binance_raw/{PAIR}-{tf}.feather`,
  with the extra columns `quote_volume`, `n_trades`, `taker_buy_base`,
  `taker_buy_quote`: ETH_FDUSD 1m, ETH_USDT 1m / 5m / 1h / 1d (1h and 1d back
  to 2017-08-17), FDUSD_USDT 1m, plus `symbol_filters.json`. It is kept apart
  from freqtrade's data dir on purpose: freqtrade assigns its six standard
  column names when it reads a feather file, so a file with extra columns
  would break it. The ETH_FDUSD raw 1m file is bar-for-bar identical to
  freqtrade's (335,520 common rows, 0 differences). `ETH_USDT-1h` has 128
  missing hours over its history (not yet located; matters only for later
  work).
- **"Flat" means "zero trades".** Binance emits a flat placeholder bar
  (O=H=L=C=previous close, volume 0) for a minute with no trades. The
  project's flat definition (O=H=L=C and volume 0) and `n_trades == 0` are the
  same set (checked on real ETH/FDUSD and FDUSD/USDT data).
- **Exchange facts** (from Binance `exchangeInfo`, never assumed): ETHFDUSD
  tick 0.01, step 0.0001, min notional 5, `LIMIT_MAKER` supported (also for
  ETHUSDT and FDUSDUSDT; FDUSDUSDT tick 0.0001).
- **Costs: planning fee 0.10% for makers and takers.** The account's current
  maker fee of 0% is a promotion and is ignored; promotions are never
  modeled. The two cost cases (base and stress) are in `costs.py`; see
  "Costs" below.
- **Extending or refreshing 1m data.** freqtrade's `download-data` does not
  backfill earlier history into an existing file, and the shipped
  `scripts/download_data.sh` asks for 1,825 days on every timeframe. Use
  `fetch_klines.py --start YYYY-MM-DD --export-freqtrade` instead: it
  re-downloads from Binance, merges, backs up the old freqtrade file, and
  refuses to write anything if any existing bar is missing or differs. The
  first extension (2026-03-19 back to 2026-01-30) was verified: seam
  consecutive on all four 1m series, and the new file reproduces the
  original file exactly (0 rows lost, 69,120 rows added before it).

## The toolkit (`user_data/analysis/`)

Each file below is self-tested (`python3 <file>.py`, or `--self-test` where a
file has its own CLI) against synthetic data with known ground truth before
being trusted against real data. `bash selftest_all.sh` runs all of them (14
scripts; passes on pandas 3.0 and, apart from a statsmodels-version issue in
`stats_fingerprint.py`, on pandas 2.2). Treat these as the vocabulary for
describing new ideas — "run it through `stats_fingerprint.py`'s ACF" is a
precise instruction, "add some math" is not.

- **`resample.py`** — Aggregates 1-minute candles up to any target
  timeframe, left-labeled. **Default rule is "traded" (since work order
  1.1):** open = first *traded* minute's open, high/low = extremes of traded
  minutes, close = last traded minute's close, volume = sum, and a bin with
  no traded minute carries the previous close. This reproduces Binance's
  native bars exactly (zero mismatches on 5m, 15m, 30m, 1h, 1d and 1w on the
  real data). The old rule ("filled": every 1m row counts, including flat
  placeholders) is kept as `rule="filled"` for comparison only; it
  mismatched native `open` on 7.6% of 5m bins and `high`/`low` on about 2%,
  because a flat placeholder can become a coarse bar's open, high or low.
  Also cross-checks a resampled timeframe against the native file.
  `resample_rule_test.py` is the real-data test that made this the default.

- **`diagnose_gaps.py`** — Investigates *why* a resample-vs-native mismatch
  happens: finds literal missing-minute gaps and flat/zero-volume
  placeholder candles in the 1m data, and checks whether they explain
  specific mismatched bins.

- **`stats_fingerprint.py`** — The core statistical battery, run per
  timeframe and per lookback (1, 3, 5 candles), always on **non-overlapping**
  return windows: `stationarity_test` (ADF), `distribution_stats`
  (mean/std/skew/kurtosis + Jarque-Bera), `autocorrelation_analysis` (ACF +
  Ljung-Box), `volume_participation` (Mann-Whitney: do big moves carry more
  volume), `flat_candle_fraction` (% of zero-volume placeholder candles).
  Has a `--fast` / `adf_maxlag` mode: **never trust a `--fast` result — only
  use it to confirm code runs.** Needs statsmodels >= 0.15.

- **`leadlag.py`** — Tests whether one timeframe's return series leads
  another's. `nonoverlapping_lagged_correlation` and `hac_lagged_regression`
  are the original row-sliding pair (see "Mistakes already made" #1-5) —
  kept for comparison and for same-timeframe questions only, NOT reliable for
  cross-timeframe pairs. **`event_anchored_lead_lag` is the one to trust for
  cross-timeframe results.** It anchors once per closed coarse bar and only
  reads fine-grid returns at or after that bar's close. Since work order 1.1
  it also uses **strict time alignment**: a (coarse bar, lag) pair is used
  only if the fine row sits exactly at `close + (j-1) x fine step`;
  anything else is dropped, not shifted (mistake #6). `grid_returns` builds
  returns that never span a missing row. Its table has `lag_bars` (the j-th
  fine bar after the close), `lag_minutes` (= bars x fine bar length, the END
  of that bar's window: on a 5m fine series, bar 25 is minute 125), and
  `correlation` next to `beta`. `legacy_alignment=True` reproduces the old
  behaviour for comparison only.

- **`config_schema.py`** — On/off + lookback-window scaffolding per
  timeframe (JSON round-trippable). Not yet wired into any strategy logic.

- **`walkforward.py`** — Rolling fit/validate date-range splitter. Wired to
  formulas via `research_cli.py`'s `--walkforward` mode. On the 233-day
  sample, fit 90 / validate 30 gives **4 splits**; the earlier default of
  270/90 gives none.

- **`run_fingerprint.py`** — Orchestrates the fixed, full battery: loads
  native data (always preferred over resampled), runs the fingerprint per
  timeframe and lead-lag across the three standard pairs, writes everything
  to `user_data/analysis/results/`. `--start-date 2026-01-30` restricts every
  timeframe to post-break bars and writes to `results/from_2026-01-30/`
  (full-history results are never overwritten). It also writes
  `data_ranges.json` and, for each event-anchored pair, the family size and
  adjusted p (per pair, and pooled across all pairs: 15 + 15 + 36 = 66).

- **`research_cli.py`** — Entry point for testing a NEW mathematical idea: a
  formula registry (`--list-formulas`), flags (`--formula X --param key=value`)
  or guided prompts, a manifest per run in `analysis/results/runs/`, and
  walk-forward validation (`--walkforward`). `data` keys are now
  `PAIR:timeframe` (a bare `"5m"` still means the default pair;
  `"ETH_FDUSD:1m:raw"` reads the raw-kline store). Every run records its
  family size and Bonferroni and Holm adjusted p. In walk-forward, validate
  tests only the fit-selected lag, and windows are half-open (see mistake #8).

- **`databundle.py`, `multitest.py`, `costs.py`** — PAIR:timeframe data
  loading and half-open slicing; Bonferroni/Holm adjustment (family = the
  tests actually run); the two-case taker cost model (base and stress,
  execution at the next bar's open). The earlier Scenario A/B cost model is
  archived in `retired/costs_scenarios_AB.py`.

- **`fetch_klines.py`** — Raw Binance klines (all 12 fields) via the public
  REST API, resumable, plus exchange filters (`symbol_filters.json`);
  `--start` and `--export-freqtrade` as described under "Data available".

- **`task0_report.py`** — Read-only data inventory: history, gaps, flat
  share (overall and by month), break split, 1d-vs-1m check, raw-vs-freqtrade
  check, seam check, walk-forward capacity. `--previous-1m` proves an
  extended file reproduces the previous one.

- **`passive_fill_baseline.py`** — **History.** Signal-free resting-order
  negative control (work order 1.0 Task 2); every timing convention is in its
  docstring. Its follow-ups and the whole maker-fill line of work were
  retired in work order 1.2; the file stays as delivered history and no
  longer imports `costs.py`.

- **`retired/`** — Archive of retired work (work order 1.2): the Scenario A/B
  cost model, with a one-page README saying what was retired and why. Nothing
  in it is imported by live code.

## Costs

*(Work order 1.2 replaced the earlier Scenario A/B model; work order 1.3
tied the backtest script to it.)* Two cases (`costs.py`), both **taker
execution at the next bar's open**: **base** — fee 0.10% plus slippage 0.02%
per side (0.0012 per side, 0.24% round trip); **stress** — fee 0.12% plus
slippage 0.03% per side (0.0015 per side, 0.30% round trip). The planning fee
is 0.10% for makers and takers; the account's current maker 0% is a promotion
and is ignored; promotions are never modeled. `python3 costs.py --per-side
{base,stress}` prints the per-side number. `scripts/backtest.sh` takes its
`--fee` from it (`COST_CASE=base` by default, or `stress`): freqtrade has no
slippage setting, so the per-side fee plus slippage is passed as the fee,
which agrees with `costs.py net_return` within 1e-8 (checked in the
self-test). The script's `TIMERANGE` ends 20250831; the holdout lock covers
strategy backtests too.

## Formula contract — how a new equation becomes testable

This is the spec for turning a mathematical idea into something
`research_cli.py` can run, phrased so it's usable whether you're proposing
a formula in plain language/notation or writing the Python for it — see
"Why this project is structured the way it is" above for why this
separation matters enough to spell out explicitly.

**What's available to draw from:** every downloaded timeframe's OHLCV data
(open, high, low, close, volume, at 1m/5m/15m/30m/1h/1d/1w), the same for
ETH/USDT and FDUSD/USDT where downloaded, the raw-kline fields (`n_trades`,
`taker_buy_base`, `taker_buy_quote`) from the raw store, and anything you
derive from them (returns, rolling stats, volume ratios, whatever). A formula
can use one series or several — nothing requires comparing exactly two.

**What a formula fundamentally is:** a PREDICTOR (something computable from
data available up to a point in time) tested against a TARGET (a later
return or move-size, on whatever timeframe you care about) across a range
of LAGS. That's a deliberately wide net — "does a 15m bar's return predict
the 5m return 4 minutes after it closes" (already built,
`event_anchored_lead_lag`) and "does elevated volume on a bar predict a
bigger move some number of bars later" (also already built,
`volume_leads_volatility`, as a worked example of a formula that only
needs one timeframe) are both instances of this same shape. So would a
composite score (e.g. a weighted blend of 1m and 5m momentum) — the
predictor is just computed from more inputs.

**What a formula must produce**, regardless of what it computes internally:
a table with one row per lag tested, containing at minimum: the lag, the
sample size, an effect-size number (a correlation or a regression beta),
and whether that lag was statistically significant (p < 0.05). This shared
shape is what lets `research_cli.py` summarize, manifest, and
walk-forward-validate any formula the same way, without knowing what's
inside it.

**The one mandatory gut-check, on every new formula, no exceptions:** does
this comparison let the same price data appear on both sides — is the
target, or any piece of it, arithmetically part of how the predictor was
computed (or vice versa)? That question, and the mistake history of
getting it wrong in progressively subtler ways, is the entire "Mistakes
already made" section below. Read it before designing anything that
compares data across two different time resolutions.

**In Python**, this is a function `def formula(*, data, max_lag, **params)`
registered in `research_cli.py` with `@register("name", "description")`;
`data` is a dict of DataFrames keyed by `PAIR:timeframe` (a bare timeframe
string means the same timeframe on the default pair), `params` is
whatever your formula needs beyond `max_lag` (a timeframe pair, a lookback
window) supplied via `--param key=value` on the command line. See
`research_cli.py`'s own module docstring for the exact contract, and its
existing four formulas for two different concrete shapes to copy from.

## What counts as a finding worth promoting

*(Revised 2026-09-20 for work order 1.2. It supersedes the promotion text of
work order 1.1; the pipeline machinery below is the next developer's build
queue, not yet implemented. If this text and the mathematician's current
instructions disagree, the mathematician's instructions win, and this file
should be corrected.)*

Testing a formula produces a number. This is the bar that number has to
clear before it stops being "an interesting result." None of these is
optional, and none substitutes for another.

**Sample design.** ETH/USDT is the research pair. Discovery and walk-forward
use data up to and including 2025-08-31 (an `--end-date` guard enforces it).
Data after that date is a locked holdout, readable only by the forward-test
command, once per candidate; Holm is applied across the candidates that reach
it, via the registry. Walk-forward on ETH/USDT: fit 365 / validate 90 days
(ETH/FDUSD keeps its post-break 90/30 rules, for reference only). Every result
reports a by-year table and a leave-one-year-out check: if dropping any single
year cuts the estimate by more than half or flips its sign, the candidate does
not advance without the mathematician's review.

**The pipeline, in order.**
1. **Discovery:** the result must clear Holm-adjusted p < 0.05 within its own
   pre-registered family (Bonferroni is reported for reference). Every cell is
   tagged `pre-registered` or `exploratory` in its manifest, and the cumulative
   count of tests run is reported alongside every result.
2. **Walk-forward** as a **stability check, not independent evidence**. In each
   fit window select the lag with the **smallest p (largest |HAC t|)** — no
   "significant" pre-filter, and not the largest |beta| or |correlation|. Then,
   in the validate windows at the fit-selected lag: (a) same sign in every
   window; (b) a one-sided Stouffer combination of the validate z-scores
   (z = orientation sign x HAC t, equal weights) with p < 0.05, Holm-adjusted
   across candidates carried forward; (c) no split significantly opposite
   (two-sided p < 0.05 with the opposite sign). Report the selected lag per
   split — lags that jump around are a warning even when the combined statistic
   passes. Orientation sign: the pre-registered direction for pre-registered
   cells (they select no lag); each split's fit-window sign for two-sided cells
   and lag scans.
3. **Freeze:** a timestamp in the manifest fixing the exact cell, direction,
   discovery estimate and dispersion, and code commit.
4. **One forward test** on the locked holdout, then the test is consumed.
   Success: one-sided p < 0.05 and an estimate at least half the discovery
   estimate, and also at least M for event cells. Failure means the candidate
   is dead — no retuning.

**Forward-test conditions and clarifications (work order 1.3).**
- **Minimum sample.** The holdout test runs only when, at test time, the
  holdout has at least 45 days and at least 100 events or observations for the
  primary cell, and the standard error is no larger than half the claimed
  effect (from the discovery dispersion, scaled to holdout size). Otherwise
  wait; if it would need more than 120 further days, ask the mathematician.
- **Slope cells (S1, S2): economic gate.** M applies to event cells only. For
  slope cells, between stability and freeze, run the frozen rule in the rule
  evaluator at stress cost over the discovery sample: pooled net return must be
  above 0, and net return at least 0 in at least 70% of the 90-day validate
  windows (a window fully in cash counts as 0). At the holdout the frozen rule
  must also be net-positive at stress cost, in addition to the slope cell's
  forward success. Pre-registered rules: S1 — long from the next open if
  x (L = 40) > 0 at the day's close, otherwise cash; S2 — long from the open of
  the 1h bar at s+1h while the latest rank is at most 0.5, otherwise cash,
  re-evaluated at each settlement.
- **S2 endpoints.** Entry = open of the 1h bar labeled s+1h; exit = open of the
  1h bar labeled s+1h+H, H = 24h and 72h in clock time. The rank window is the
  previous 90 days of settlements (270 at 8h). If any interval other than 8h
  appears, report the dates and set the HAC lags to ceil(H / shortest
  interval).
- **Cutoff mechanics.** The cutoff is 2025-08-31 23:59:59 UTC inclusive. Last
  usable bars: 1d labeled 2025-08-31; 1h labeled 23:00; 15m labeled 23:45; 5m
  labeled 23:55; funding settlements up to 16:00. Discovery keeps an origin
  only if its entry is at or after the sample start and its whole target
  window ends at or before the cutoff; otherwise drop it, no truncation.
  Holdout origins have entry time at or after 2025-09-01 00:00 UTC, and their
  predictors may look back into discovery data. Straddling origins belong to
  neither. The same purge applies at every walk-forward fit/validate boundary.
- **Partial years.** Every calendar year is a row with n and days covered.
  Years with fewer than 120 days are shown but not judged: they stay in the
  pooled estimate and are excluded from leave-one-year-out and year-by-year
  sign statements.
- **Task 4.** ETH/USDT, same cutoff and holdout, walk-forward fit 365 /
  validate 90, realized variance from 5m returns; primary = volume coefficient
  positive. The deliverable is the forecast series and calibration table. It
  runs only after a candidate passes discovery.

**Materiality.** For event-type primary cells (Task 3), **M = 0.35% gross per
round trip, measured as the excess over the unconditional mean forward return
at the same horizon**, so drift alone cannot pass. **Pass** = one-sided
p < 0.05 and excess at least M. **Dead** = one-sided 95% upper bound below M.
Otherwise **inconclusive**. Report the minimum detectable effect from the
standard error.

**Effect size sanity.** Judge a new beta/correlation against this project's own
scale: same-asset autocorrelation on ETH/FDUSD post-break is on the order of
0.001 to 0.01; the fabricated mistake-#5 artifacts were 0.6-0.9. An effect of
roughly 0.01-0.05 is worth taking seriously; anything approaching 0.5 is far
more likely to be a construction artifact — re-run the mandatory gut-check.
Correlation is reported beside beta.

**Multiple testing.** Holm within each task's pre-registered family; state the
family size and cumulative count next to every hit. One hit among 66 tests at
p < 0.05 is a candidate for further testing, not a finding.

**Costs.** Nothing tradable is reported without the base and stress cost cases
(0.24% and 0.30% round trip, taker at the next bar's open).

Only a result that clears all of this gets a line in `test_params.json` or a
new entry/exit condition in the strategy — and it is the researcher's job to
state the result clearly enough (predictor, target, lag, the numbers above)
that implementing it does not require the coder to re-judge whether it is real.

## What the real data has already shown (history: ETH/FDUSD post-break, 2026-01-30 to 2026-09-19)

*(Updated 2026-09-20. All timeframes on equal spans. Figures quoted in
earlier versions of this file came from different spans — 1m 184 days,
coarser timeframes full history — which is why they differ.)*

- **Flat (zero-trade) minutes are concentrated at high frequency, and their
  share is not stable over time.** Overall 1m flat share is 9.6% (32,170 of
  335,520), 0.39% at 5m and 0% from 15m up. **By month, ETH/FDUSD 1m:** Jan
  0.0%, Feb 0.4%, Mar 3.0%, Apr 8.1%, May 13.9%, Jun 6.6%, Jul 14.1%, Aug
  21.3%, Sep (19 days) 8.4%. **FDUSD/USDT 1m:** 0.1%, 0.5%, 3.0%, 5.1%, 4.3%,
  3.7%, 7.1%, 6.9%, 5.3%. ETH/USDT has essentially none. So any result that
  depends on the flat/traded split, or on `n_trades`, rests on a state whose
  frequency moved from about 0% to about 21% inside the sample. It is a real
  liquidity characteristic, not a data bug — and a naive 1m momentum
  calculation is partly measuring silence. **Decided (work order 1.3): signal
  work uses 5m and above; 1m is not used in the new phase.**

- **Returns are stationary at every timeframe** (ADF, p about 0 everywhere
  it can be computed).

- **Fat tails shrink as timeframe grows** (excess kurtosis: 80.6 at 1m,
  31.7 at 5m, 21.9 at 15m, 20.4 at 30m, 11.3 at 1h, 5.7 at 1d, 5.0 at 1w with
  only 31 observations). Textbook aggregational Gaussianity, not a red flag.

- **Autocorrelation is real but tiny** (lag-1: -0.011 at 1m, -0.0013 at 5m,
  -0.0002 at 15m, +0.0076 at 30m; Ljung-Box significant from 1m to 30m, not at
  1h, 1d or 1w). With hundreds of thousands of observations, negligible
  autocorrelation clears p < 0.05. Statistically significant is not
  economically usable.

- **Volume participation** holds at every timeframe except 1w (too few
  observations): big moves carry more volume than small ones. Still only a
  same-bar association; the forward-looking test (`volume_leads_volatility`)
  is not yet run on real data.

- **Cross-timeframe lead-lag, re-run with the corrected tool
  (`event_anchored_lead_lag`, strict alignment): nothing survives multiple
  testing.** Lags are in fine-bar units; family = 15 + 15 + 36 = 66 tests.

  | Pair | Best lag | n | beta | corr | raw p | Holm (own family) | Holm (all 66) |
  |---|---|---|---|---|---|---|---|
  | 1m:5m | 6 bars (6 min) | 67,101 | -0.0088 | -0.018 | 0.0203 | 0.305 | 1.00 |
  | 5m:15m | 5 bars (25 min) | 22,365 | -0.0151 | -0.025 | 0.0253 | 0.379 | 1.00 |
  | 5m:1h | 25 bars (125 min) | 5,588 | -0.0212 | -0.067 | 0.0019 | 0.068 | 0.124 |

  The 1m:5m best lag moved from +10 minutes (beta +0.0130) on a 184-day
  sample to 6 minutes (beta -0.0088) on 233 days: a sign flip. Treat
  `nonoverlapping_best` / `hac_best` in `leadlag_summary.json` (betas around
  0.6-0.75, p of 1e-113 to 1e-256) as the known-contaminated old results.
  These "best lag" rows were computed under the old selection rule (largest
  |beta| among significant lags), stored before the rule changed, and were
  never recomputed. The rule itself is now smallest p, no pre-filter
  (`leadlag.summarize_best_lag`, default since work order 1.2); the old rule
  survives only as `select="legacy_max_abs_effect_among_significant"`, so a
  frozen result like this one can still be reproduced exactly if needed.

- **Passive-fill negative control (`passive_fill_baseline.py`, 233 days,
  about 5,590 hourly origins per cell). History: this line of work was
  retired in work order 1.2.** A signal-free resting order, filled only when
  price trades at least one tick through the limit, earned a mean forward
  return **below zero in all 36 cells** (adverse selection): about -0.003% to
  -0.034% before fees, with fill rates of about 72%, 57% and 33% at d = 0.05%,
  0.10% and 0.20%. 16 of the 36 cells (two window variants x 18) were
  individually significantly negative after Holm adjustment; none was
  positive. The simulator was not generous. The 14-bar and 15-bar order
  windows differed negligibly.

- **Data quality:** 1d built from 1m now matches native 1d on all 233 days
  under the traded-minutes rule (5 days had mismatched `open` under the old
  rule, each with a flat first or last minute), and every timeframe matches
  its native file exactly.

## Mistakes already made and fixed (read this before designing anything similar)

These are documented so the same category of error doesn't get rebuilt
under a different name:

1. **Pandas' default weekly resample rule anchors to Sunday; Binance anchors
   weekly candles to Monday.** A silent one-day label offset caused zero
   overlap between resampled and native 1-week data. Fixed by using the
   `W-MON` rule explicitly.

2. **Joining two series at different native frequencies collapses to the
   coarser frequency's spacing.** A "lag" of 4 between 1m and 5m data
   actually meant 4 *five-minute* steps (20 minutes), not 4 minutes.
   Fixed with `align_to_common_grid`, which explicitly reindexes onto the
   finer series' grid first.

3. **Comparing a fine-grid return to the coarse return of the window it's
   mechanically part of produces near-1.0 correlation that looks like a
   finding but isn't** — it's the same price move measured twice. Fixed by
   shifting the coarse series forward by one full window
   (`shift_periods=1`) before alignment, so comparisons are always against
   an already-closed prior window, never the one in progress.

4. **Even after that fix, shifting the fine series by exactly one full
   coarse-window-width re-enters the same window the coarse value came
   from** — the same tautology reappearing at `lag = upsample_factor`
   instead of `lag = 0`. Fixed by capping the tested lag range strictly
   below the coarse-to-fine ratio.

5. **The cap in #4 turned out to be incomplete — RESOLVED.** A re-run after
   that fix still showed the strongest result landing right at the edge of
   the allowed range for two of three timeframe pairs (`1m:5m` at lag 4 of
   a 0-4 range, `5m:15m` at lag 2 of a 0-2 range) — the same "suspiciously
   at the boundary" signature as before, just smaller. Confirmed root
   cause: `nonoverlapping_lagged_correlation` / `hac_lagged_regression`
   test each lag by shifting the RAW fine series a few rows at a time and
   comparing it against the coarse return broadcast across the whole next
   window. For any lag strictly between 0 and upsample_factor, a growing
   *fraction* of rows in that comparison land back inside the very coarse
   window the target return is made of — 100% of rows do at
   lag=upsample_factor (what the cap blocks), but the contamination is
   already present, just diluted, at every lag below that. Reproduced this
   on pure i.i.d. noise with zero injected relationship (no real data
   needed): `hac_lagged_regression` still reports a "significant" best lag
   at the clipped boundary with beta approaching 0.8 and t-stats over 100,
   from construction alone.
   Fixed by adding `event_anchored_lead_lag` (in `leadlag.py`): instead of
   sliding a lag across individual fine-grid rows, anchor once per CLOSED
   coarse bar and only ever compare against fine-grid returns AT OR AFTER
   that bar's close. A closed coarse bar's return is built from fine-grid
   returns strictly BEFORE its own close, so predictor and target can never
   share a raw observation at any lag — no upsample_factor ceiling needed,
   and lags well past it are safe (and useful: they show whether an effect
   decays or was only ever the artifact above). Verified against both a
   negative control (pure noise -> 0/12 lags flagged, vs. the old method's
   fabricated boundary result on the same data) and a positive control (a
   real, modest, injected effect at a known number of minutes after the
   close, recovered cleanly with no false positives elsewhere).
   **Status: `event_anchored_lead_lag` is the one to trust; the two
   row-sliding functions are kept for comparison/history and for
   same-timeframe questions (upsample_factor=1) only. The real ETH/FDUSD
   data has since been re-run through it (post-break, 66 tests): no lag
   survives multiple-testing adjustment — see "What the real data has
   already shown".**

6. **Pairing a coarse and a fine series by row position when their date
   ranges differ.** Match by timestamp, and drop anything that is not exactly
   on time. `event_anchored_lead_lag` located "the fine row j-1 steps after the
   close" by position. On the real data the 5m file reaches back to 2023 while
   the 1m file began much later, so every coarse bar that closed before the 1m
   data began was `searchsorted` to row 0 and paired with the first few fine
   returns of the file (about 84% of the 5m bars against the original 184-day
   1m file). On synthetic data this made n about 3x too large and an injected
   beta of 0.05 come out as 0.017. Missing rows had a similar effect, shifting
   later positions so a lag was no longer its labeled number of minutes. Fixed
   with strict time alignment and gap-aware returns (`grid_returns`); on
   gap-free, same-span data the results are unchanged. **Any event-anchored
   result computed before this fix is invalid.**

7. **Resampling coarse bars from flat placeholder minutes.** A minute with no
   trades is emitted as a flat bar priced at the previous close. Treating it as
   a real price let a placeholder become a coarse bar's open (previous close
   instead of the first real trade) and sometimes its high or low: 7.6% of 5m
   opens mismatched the native file. Fixed by building coarse bars from traded
   minutes only (`resample_ohlcv` rule "traded", now the default); verified to
   match native bars exactly on every timeframe.

8. **Walk-forward leaks.** (a) Validate re-ran the whole lag scan and compared
   "best lag within 1 step", so validate could pick its own winner among many
   lags; validate must test only the lag chosen in the fit window. (b) Fit and
   validate windows were sliced with an inclusive `.loc[start:end]`, so the
   boundary bar sat in both; windows are now half-open. (c) The event-anchored
   column named `lag_minutes_after_close` actually counted fine bars (5 minutes
   each on a 5m series); it is now `lag_bars`, with an explicit `lag_minutes`.

9. **Taking the walk-forward reference sign from the full sample.** If the
   direction used to orient the validate z-scores comes from the full-sample
   estimate, that estimate already contains the validate windows, so the sign
   check is partly circular. The reference sign is the pre-registered direction
   (pre-registered cells) or the fit window's own sign (two-sided cells and lag
   scans) — never the full sample. Caught in design review before it was built.

10. **Judging raw forward returns in a drifting market.** A rule can clear a
    return threshold on drift alone (ETH rose over most of the sample). For
    event cells, measure the excess over the unconditional mean forward return
    at the same horizon, and compare that excess with the threshold M.

**The pattern across all of these**: overlapping time windows (#1-5), misaligned
observations (#6), placeholder data treated as real prices (#7), a
validation step that gets to choose (#8) or that borrows its answer from the
data it validates (#9), and drift mistaken for signal (#10) each manufacture or flatter a finding
in a way that is not obvious on first pass. Any new equation that compares data
across two different time resolutions should be checked against this list before
being trusted — "does this comparison secretly let the same price data appear on
both sides?" is the first question to ask, and "could the validation step have
chosen its own answer?" is the second.

## Where this leaves the math phase

*(Updated 2026-09-20, after work order 1.2.)* The infrastructure can now: load
correct, seam-verified data, compute per-timeframe fingerprints on equal spans,
test cross-timeframe lead-lag with strict alignment and a family-aware
adjusted p, and run walk-forward validation that tests only the fit-selected
lag. What has been established on ETH/FDUSD (history): no cross-timeframe
lead-lag survives adjustment; a signal-free resting order carries a consistent
adverse-selection drag; the flat-minute share is non-stationary (0% to 21% by
month); and coarse bars must be built from traded minutes. Work order 1.2
retired the maker/resting-order line (Task 1, Task 5, the re-costing tool and
related items), simplified costs to taker execution at the next bar's open, and
moved the research to ETH/USDT with a locked holdout.

What it does NOT yet have — the next developer's queue, in the mathematician's
order (the full text is section 7 of `HANDOFF_developer.md`): the smallest-p
selection-rule change; the pass-rule machinery, registry, freeze and
forward-test command, `--end-date` guard and holdout lock; the data batch
(ETH/USDT 5m to 2017, BTC/USDT 1h/1d, perpetual funding-rate history, the 128
missing ETH/USDT hours located and masked, and a liquidity comparison table);
the S2 `funding_extreme`, S1 `trend_slope` and Task 3 `shock_response`
studies; and, only if a candidate passes discovery, the rule evaluator and
Task 4.

This is the actual starting point for the mathematics: given OHLCV, volume and
funding-rate data as inputs and the statistical structure already observed,
what equation would you want to define and test next?