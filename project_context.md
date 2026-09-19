# Project Context: ETH/FDUSD Multi-Timeframe Momentum Math

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

A freqtrade bot (`MomentumTrailing`) trading ETH/FDUSD on Binance spot.
Current (placeholder) rule: enter on a single-candle % rise, exit via a
trailing stop. This rule is intentionally naive — the whole point of the
math phase is to replace "1% because it seemed reasonable" with parameters
that are justified by the statistical structure of the actual data. Every
value that placeholder rule needs (timeframe, entry threshold, stoploss,
trailing-stop numbers) now lives in `user_data/test_params.json`, not in
the strategy file — see the strategy layer's own README for that.

## Data available

- Pair: ETH/FDUSD, Binance spot.
- Timeframes downloaded: 1m, 5m, 15m, 30m, 1h, 1w (10m skipped — not a
  native Binance interval).
- Stored as feather files: `user_data/data/binance/ETH_FDUSD-{timeframe}.feather`.
- Columns: date, open, high, low, close, volume.

## The toolkit (`user_data/analysis/`)

Each file below is self-tested (`python3 <file>.py` runs its own checks
against synthetic data with known ground truth) before being trusted
against real data. Treat these as the vocabulary for describing new ideas —
"run it through `stats_fingerprint.py`'s ACF" is a precise instruction, "add
some math" is not.

- **`resample.py`** — Aggregates 1-minute candles up to any target
  timeframe (open=first, high=max, low=min, close=last, volume=sum,
  left-labeled). Also cross-checks a resampled timeframe against the
  natively-downloaded file for the same timeframe.

- **`diagnose_gaps.py`** — Investigates *why* a resample-vs-native mismatch
  happens: finds literal missing-minute gaps and flat/zero-volume
  placeholder candles in the 1m data, and checks whether they explain
  specific mismatched bins.

- **`stats_fingerprint.py`** — The core statistical battery, run per
  timeframe and per lookback (1, 3, 5 candles), always on **non-overlapping**
  return windows:
  - `stationarity_test` — Augmented Dickey-Fuller (unit root test).
  - `distribution_stats` — mean/std/skew/kurtosis + Jarque-Bera normality.
  - `autocorrelation_analysis` — ACF + Ljung-Box (is any autocorrelation
    statistically distinguishable from noise).
  - `volume_participation` — Mann-Whitney test of whether big moves carry
    more volume than small ones.
  - `flat_candle_fraction` — % of candles that are zero-volume placeholders
    (a liquidity characteristic, not noise — see findings below).
  - Has a `--fast` / `adf_maxlag` mode that skips the (expensive) ADF lag
    search for quick iteration. **Never trust a `--fast` result — only use
    it to confirm code runs, then re-run in full before reading numbers.**

- **`leadlag.py`** — Tests whether one timeframe's return series leads
  another's. Three functions, not two: `nonoverlapping_lagged_correlation`
  and `hac_lagged_regression` are the original row-sliding pair (see
  "Mistakes already made" #1-4 for why `align_to_common_grid(coarse, fine,
  shift_periods=1)` and the `upsample_factor` cap exist) — keep these for
  comparison and for same-timeframe questions only, they are NOT reliable
  for cross-timeframe pairs (mistake #5). `event_anchored_lead_lag` is the
  one to actually trust for cross-timeframe results: it anchors once per
  closed coarse bar and only reads fine-grid returns at/after that bar's
  close, so it needs no upsample_factor ceiling and isn't subject to
  mistake #5 at all.

- **`config_schema.py`** — On/off + lookback-window scaffolding per
  timeframe (JSON round-trippable), so timeframe combinations are a config
  edit, not a code change. Not yet wired into any strategy logic.

- **`walkforward.py`** — Rolling fit/validate date-range splitter. Wired to
  actual formulas via `research_cli.py`'s `--walkforward` mode (below) —
  it no longer just generates splits, it runs a chosen formula on each one
  and reports whether the result replicates out of sample.

- **`run_fingerprint.py`** — Orchestrates the fixed, full battery: loads
  native data (always preferred over resampled, even when they mismatch —
  the mismatch is a diagnostic, not a reason to use worse data), runs the
  full fingerprint per timeframe, runs lead-lag across the three standard
  pairs, writes everything to `user_data/analysis/results/`. Use this for
  the standard battery; use `research_cli.py` (next) for anything new or
  exploratory.

- **`research_cli.py`** — The entry point for testing a NEW mathematical
  idea: a formula registry (`--list-formulas` to see what's registered),
  runnable by flags (`--formula X --param key=value`) or guided prompts
  (run with no arguments), with a manifest written per run to
  `analysis/results/runs/` and built-in walk-forward validation
  (`--walkforward`). See "Formula contract" below for exactly what a new
  formula needs to look like, and the file's own module docstring for the
  full mechanical detail.

## Formula contract — how a new equation becomes testable

This is the spec for turning a mathematical idea into something
`research_cli.py` can run, phrased so it's usable whether you're proposing
a formula in plain language/notation or writing the Python for it — see
"Why this project is structured the way it is" above for why this
separation matters enough to spell out explicitly.

**What's available to draw from:** every downloaded timeframe's OHLCV data
(open, high, low, close, volume, at 1m/5m/15m/30m/1h/1w), and anything you
derive from it (returns, rolling stats, volume ratios, whatever). A formula
can use one timeframe or several — nothing requires comparing exactly two.

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
computed (or vice versa)? That question, and the five-mistake history of
getting it wrong in progressively subtler ways, is the entire "Mistakes
already made" section below. Read it before designing anything that
compares data across two different time resolutions.

**In Python**, this is a function `def formula(*, data, max_lag, **params)`
registered in `research_cli.py` with `@register("name", "description")`;
`data` is a dict of DataFrames keyed by timeframe string, `params` is
whatever your formula needs beyond `max_lag` (a timeframe pair, a lookback
window) supplied via `--param key=value` on the command line. See
`research_cli.py`'s own module docstring for the exact contract, and its
existing four formulas for two different concrete shapes to copy from.

## What counts as a finding worth promoting

Testing a formula produces a number. This section is the bar that number
has to clear before it stops being "an interesting result" and starts
being something worth writing into the strategy layer. Meeting some but
not all of these is a reason to keep researching, not to ship early — none
of these is optional, and none substitutes for another.

1. **Walk-forward replication.** Significant (p<0.05) in every fit window
   AND its corresponding validate window, with the same sign and the best
   lag within about 1 step across splits. A result found in fit that
   doesn't show up in validate is exactly what walk-forward validation
   exists to catch — that's noise, not "needs a bigger sample."

2. **Effect size in a plausible range.** Judge a new beta/correlation
   against this project's own already-established scale, not in the
   abstract. Genuine same-asset autocorrelation here is on the order of
   0.004; the fabricated mistake-#5 artifacts were 0.6-0.9. A newly found
   effect in roughly the 0.01-0.05 range is worth taking seriously; a
   result approaching the 0.5+ range is far more likely to be a
   construction artifact resurfacing than real edge, however good the
   p-value looks — go back and re-run the mandatory gut-check above before
   trusting it.

3. **Multiple-testing awareness, stated alongside the result, not just
   computed silently.** Report how many lags/formulas/pairs were tried
   alongside any single "significant" hit. One hit among 66 tests at
   p<0.05 (roughly 3 expected by chance alone) is a candidate for further
   testing, not a finding — this was the actual position the `5m:15m`
   lead-lag result was in before it was walk-forward validated, and it's
   the default position for any first hit, on any formula, going forward.

Only a result that clears all three gets a line in `test_params.json` or a
new entry/exit condition in the strategy — and even then, per "Why this
project is structured the way it is," it's the researcher's job to state
the result clearly enough (predictor, target, lag, the numbers above) that
implementing it doesn't require the coder to independently re-judge
whether it's real.

## What the real data has already shown (from actual fingerprint runs)

- **Flat/zero-volume candles are concentrated at high frequency**: 1m
  candles are **~12% flat** (no trades at all), dropping to ~3.3% at 5m,
  ~1.5% at 15m, ~0.7% at 30m, ~0.25% at 1h, 0% at 1w. This is a real
  liquidity characteristic of this pair, not a data bug — but it means a
  naive 1m-based momentum calculation is partly measuring silence.
  Unresolved question: should 1m stay the primary timeframe with flat
  candles filtered, or should primary shift to 5m?

- **Returns are stationary at every timeframe tested** (ADF, p≈0 nearly
  everywhere) — unsurprising for financial returns, but confirms the data
  itself isn't structurally broken.

- **Fat tails shrink as timeframe grows** (kurtosis excess: ~85 at 1m → ~51
  at 5m → ~37 at 15m → ~24 at 30m → ~17 at 1h → ~2.4 at 1w). Textbook
  "aggregational Gaussianity" — expected, not a red flag.

- **Autocorrelation is statistically "real" (Ljung-Box) almost everywhere,
  but the actual ACF values are tiny** (e.g. 0.004 at 1m lag-1). With
  260,000+ observations, even negligible autocorrelation clears a p<0.05
  bar. Statistically significant ≠ economically usable — don't mistake one
  for the other when reading these tables (see "What counts as a finding
  worth promoting" above).

- **Volume participation is the cleanest finding so far**: at every single
  timeframe (1m through 1w), big moves have significantly higher median
  volume than small moves (p≈0 almost everywhere). This held up across the
  entire timeframe range, not just one — probably the most trustworthy
  building block uncovered to date. Still only shown as a same-bar
  association, though (see `volume_leads_volatility` above for the
  forward-looking version of this question — not yet run against real
  data).

- **Cross-timeframe lead-lag: the measurement tool is now fixed
  (`event_anchored_lead_lag`, mistake #5), but the real ETH/FDUSD data
  hasn't been re-run through it yet.** Every attempt before this was
  measuring some form of window overlap rather than genuine predictive
  lag. Treat `nonoverlapping_best` / `hac_best` in `leadlag_summary.json`
  as the known-contaminated old results; `event_anchored_best` (once
  re-run) is the one to actually read.

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
   feather data has not yet been re-run through the new function — that's
   the next step before treating any specific lag as a finding.**

**The pattern across all four**: overlapping time windows manufacture fake
correlation in more ways than are obvious on first pass. Any new equation
that compares data across two different time resolutions should be checked
against this list before being trusted — "does this comparison secretly let
the same price data appear on both sides?" is the first question to ask.

## Where this leaves the math phase

The infrastructure can now: load correct data, compute per-timeframe
statistical fingerprints, and test (with real safeguards) whether one
timeframe's behavior predicts another's — and any NEW such test, not just
the ones already built (see "Formula contract" above), judged against a
stated bar (see "What counts as a finding worth promoting" above). What it
does NOT yet have is:

- A validated cross-timeframe lead-lag finding (the original "5m drawdown
  precedes 1m reversal" idea is still just a hypothesis, now with a tool
  that can actually test it cleanly — `event_anchored_lead_lag` reports a
  minute-by-minute decay curve after each closed bar, which maps onto this
  idea directly. Still needs a real re-run before trusting any specific
  lag).
- A forward-looking (not just same-bar) test of the volume-participation
  finding, using `volume_leads_volatility` against real data.
- Any other composite momentum equation, volume-weighting scheme, or
  regime signal — none has been designed yet, only the toolkit (and now
  the contract, and the promotion bar) to test one once designed.
- A decision on primary timeframe, given the flat-candle finding above.
- Walk-forward validation of any SPECIFIC finding (the mechanism now
  works end-to-end; no real finding has been run through it, or judged
  against the bar above, yet).

This is the actual starting point for the mathematics: what equation, given
OHLCV + volume as inputs and the statistical structure already observed,
would you want to define and test first?