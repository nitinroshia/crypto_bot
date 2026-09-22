# Work Order 01 — Completion Report

**To:** Mathematician
**From:** Developer
**Date:** 2026-09-19
**Scope delivered:** Task 0 (data) and Task 2 (passive-fill negative control), plus supporting changes to shared tooling.
**Not yet started:** Tasks 1, 3 and 4 (see section 7; nothing blocks them).

---

## 1. Status at a glance

| Item | Status | Headline |
|---|---|---|
| Task 0 — data inventory, downloads, break, fees, fingerprint re-run | **Complete** | 1m is 184 days and entirely post-break; coarse files are 3.1 years and about 80% pre-break. Corrected event-anchored results: nothing survives multiple-testing adjustment. |
| Task 2 — passive-fill negative control | **Complete** | Baseline is negative in all 36 cells (adverse selection, about −0.01% to −0.055% before fees). The fill simulator is not generous. |
| Shared tooling changes | **Complete** | One bug fixed in `event_anchored_lead_lag`; walk-forward now tests only the fit-selected lag; family size and adjusted p recorded everywhere. |
| Tasks 1, 3, 4 | Pending | Data they need is now in place. |

**Verification.** All 12 self-test scripts pass on the operator's machine (`selftest_all.sh` ends with `ALL SELF-TESTS PASSED`), and were also run in development on pandas 3.0 and pandas 2.2. Note that the `MISMATCH` and `WARNINGS` lines printed inside the `task0_report.py` self-test come from its deliberately corrupted synthetic data and are expected. Task 0 and Task 2 were then run on the real data, and the results below come from those runs.

---

## 2. Task 0 — Data

### 2.1 Inventory (`ETH_FDUSD`, freqtrade files)

| TF | First bar | Last bar | Rows | Missing bars | Flat % | Before 2026-01-29 | On break day | After |
|---|---|---|---|---|---|---|---|---|
| 1m | 2026-03-19 | 2026-09-19 04:34 | 265,235 | 0 | 11.83 | 0 | 0 | 265,235 |
| 5m | 2023-08-04 | 2026-09-19 04:30 | 328,855 | 0 | 3.33 | 261,696 | 288 | 66,871 |
| 15m | 2023-08-04 | 2026-09-19 04:15 | 109,618 | 0 | 1.47 | 87,232 | 96 | 22,290 |
| 30m | 2023-08-04 | 2026-09-19 04:00 | 54,809 | 0 | 0.73 | 43,616 | 48 | 11,145 |
| 1h | 2023-08-04 | 2026-09-19 03:00 | 27,404 | 0 | 0.25 | 21,808 | 24 | 5,572 |
| 1d | 2023-08-04 | 2026-09-18 | 1,142 | 0 | 0 | 909 | 1 | 232 |
| 1w | 2023-07-31 | 2026-09-07 | 163 | 0 | 0 | 131 | 0 | 32 |

Consequences:

- **The 1m file is 184 days and entirely post-break.** Every 1m-based result is only as long as this file.
- **The coarse files are not post-break.** About 80% of the rows in every coarse file (79.6% of the 5m rows) predate 2026-01-29. Any analysis that must be post-break has to be trimmed. Post-break bars are 66,871 (5m), 22,290 (15m), 5,572 (1h) and 232 (1d). The break day itself is reported separately and not assigned to either side.
- **Walk-forward capacity.** Fit 90 / validate 30 days gives 3 splits on 1m and 4 on post-break coarse files. Fit 270 / validate 90 gives **0 splits** on any post-break data, so the README defaults cannot be used. Full-history coarse files would give 35 and 9 splits, but they mix regimes.

### 2.2 Raw-kline store (adds `n_trades`, `taker_buy_base`, `taker_buy_quote`)

| File | Span | Rows | Bars with zero trades |
|---|---|---|---|
| `ETH_FDUSD-1m` | 2026-03-19 → 2026-09-19 | 265,235 | 31,376 (11.83%) |
| `ETH_USDT-1m` | same | 265,235 | 0 |
| `FDUSD_USDT-1m` | same | 265,235 | 14,393 (5.43%) |
| `ETH_USDT-5m` | 2023-08-04 → 2026-09-19 | 328,855 | 0 |
| `ETH_USDT-1h` | 2017-08-17 → 2026-09-19 | 79,552 (128 hours missing) | 6 |
| `ETH_USDT-1d` | 2017-08-17 → 2026-09-18 | 3,320 | 0 |

- **Raw and freqtrade agree exactly.** The raw store and the freqtrade `ETH_FDUSD` 1m file are identical (265,235 common rows, 0 OHLCV mismatches). Binance emits an entry for zero-trade minutes, so there are no literal missing minutes in this pair.
- **"Flat" means "no trades."** Flat minutes in the freqtrade file (31,376) equal raw zero-trade bars (31,376). For 1m, the project's flat definition (O=H=L=C and volume 0) and "n_trades = 0" are the same thing, so the flat-versus-traded split in Task 1 is unambiguous.
- **`ETH_USDT` 1h** has 128 missing hours over its history. I have not yet located them, and they matter only for Wave 2.

### 2.3 Resampling checks

- **1d from 1m versus native 1d:** 184 complete days compared, 179 match exactly. The 5 mismatches (2026-06-21, 08-05, 08-16, 08-30, 09-09) differ **only in `open`** (maximum difference 0.70), and every one has a flat first or last 1m row. None is unexplained.
- **1w:** the Monday anchoring now matches. 25 of 26 weeks are exact. The one mismatch is the partial week of 2026-03-16, which the 1m file covers only from Thursday.
- **Open mismatches by timeframe** (rows where the resampled `open` differs from native):

| TF | Rows compared | `open` mismatches | `high` | `low` |
|---|---|---|---|---|
| 5m | 53,047 | 4,999 (9.4%) | 1,357 (2.6%) | 1,550 (2.9%) |
| 15m | 17,682 | 1,468 (8.3%) | 245 (1.4%) | 261 (1.5%) |
| 30m | 8,841 | 593 (6.7%) | 61 (0.7%) | 89 (1.0%) |
| 1h | 4,420 | 247 (5.6%) | 17 (0.4%) | 19 (0.4%) |
| 1d | 184 | 5 (2.7%) | 0 | 0 |

- **Reading.** The `open` mismatch rate falls steadily with timeframe, which is what we would see if a bin that starts on a zero-trade minute takes the previous close as its open instead of the first real trade. This is confirmed for 1d (all 5 days have a flat edge row). For 5m–1h it is consistent with the pattern but not yet proven. I can test it exactly by rebuilding bars with `open` taken from the first traded minute and checking the mismatches go to zero. Native files remain the source of truth either way, but any bar built from 1m in later tasks will carry this bias.

### 2.4 Fees and exchange filters

| | ETHFDUSD | ETHUSDT | FDUSDUSDT |
|---|---|---|---|
| Tick size | 0.01 | 0.01 | 0.0001 |
| Step size | 0.0001 | 0.0001 | 1.0 |
| Min notional | 5.0 | 5.0 | 5.0 |
| `LIMIT_MAKER` | yes | yes | yes |

Fees for ETH/FDUSD (regular user, from the account fee page): **maker 0%, taker 0.100%**, buy and sell alike. They are recorded in `costs.py` with scenarios A and B as specified. `scripts/backtest.sh` still passes 0.001 on both sides, which is scenario B only, and its comment ("maker and taker both 0.001") is now known to be wrong for this pair. Scenario A needs the re-costing tool once backtests are used.

### 2.5 Event-anchored lead-lag re-run

This run used `--start-date 2026-01-30`, so the 5m-based pairs are **post-break only**. 1m:5m is unaffected because its 1m file already starts after the break. Lags are in *fine-bar* units (see 2.6). Family = 15 + 15 + 36 = 66 tests.

| Pair | Best lag | n | beta | Raw p | Holm p, own family | Holm p, all 66 |
|---|---|---|---|---|---|---|
| 1m:5m | 10 (1m bars) | 53,045 | +0.0130 | 0.019 | 0.286 (15 tests) | 1.00 |
| 5m:15m | 5 (5m bars) | 22,287 | −0.0149 | 0.027 | 0.404 (15 tests) | 1.00 |
| 5m:1h | 25 (5m bars) | 5,569 | −0.0213 | 0.0018 | 0.065 (36 tests) | 0.119 |

Bonferroni and Holm are identical here because each hit is the smallest p in its own family.

- **No candidate survives adjustment.** The closest, 5m:1h at lag 25, fails even against its own family (Holm 0.065).
- **The three best lags are unrelated.** They have mixed signs (+, −, −) and land at different lags, which is what noise would look like.
- **Effect sizes are inside the plausible band** (|beta| about 0.013–0.021). The problem is significance after multiplicity, not size.
- **No walk-forward has been run on these.**
- **Legacy methods** (`hac_best`, `nonoverlapping_best`) still report large effects, for example beta 0.63 and p = 1e-256 for 5m:15m. These are the known overlap artifact and are kept for diagnostics only.

### 2.6 Lag-unit caveat

The event-anchored table's column is named `lag_minutes_after_close`, but it counts **fine bars**, not minutes. For 1m:5m one unit is 1 minute. For 5m:15m and 5m:1h one unit is 5 minutes. So "lag 5" for 5m:15m means the 5th 5-minute bar after the close (the window 20–25 minutes after the close), and "lag 25" for 5m:1h means the window 120–125 minutes after the close. The summary file carries a `lag_unit` key, but the column name is misleading. I propose adding an explicit `lag_minutes` column and renaming the old one in the next delivery.

---

## 3. Task 2 — Passive-fill negative control

**Setup.** Every hour on the hour (UTC), a signal-free order rests at last close ∓ d (buys rounded down, sells rounded up to the tick) for 15 minutes. It fills only if a later bar's low (buys) or high (sells) is at least one tick through the limit. The placement bar is never eligible and the fill price is the limit. Forward return is measured from the limit to the close of the bar h minutes after the fill bar. Tick size 0.01 was read from Binance `exchangeInfo` and checked against the data's price grid. There were 4,420 hourly origins per cell, all post-break. None was skipped for a missing bar, and one origin at the very end of the data lacked a full window and was excluded.

**Two readings of "for 15 minutes" were run and labeled.** `A_14bars` (bars T+1 to T+14) is the strict reading and the headline. `B_15bars` (T+1 to T+15) is the sensitivity. They differ negligibly (fill rate about +1 point, means within about 0.004 percentage points).

Headline (`A_14bars`), mean pnl for the side, before fees:

| d | Side | Fill rate | +15m | +30m | +60m |
|---|---|---|---|---|---|
| 0.05% | buy | 70.7% | −0.025% | −0.022% | −0.024% |
| 0.05% | sell | 68.7% | −0.030% | −0.030% | −0.035% |
| 0.10% | buy | 53.8% | −0.017% | −0.012% | −0.013% |
| 0.10% | sell | 52.4% | −0.029% | −0.024% | −0.027% |
| 0.20% | buy | 28.9% | −0.019% | −0.007% | −0.017% |
| 0.20% | sell | 27.7% | −0.037% | −0.037% | −0.055% |

**Reading**

- **The simulator is not optimistic.** All 36 cells (18 per variant) are negative. None is positive, so nothing here is producing edge from the fill rule.
- **Significance.** Family = 18 per variant. After Holm adjustment, 7 of 18 cells per variant are individually significantly negative (mostly the 0.05% sells and the 15-minute cells). The rest are consistent with zero. Median bars to fill is 2–5, so fills come mostly when price is moving through the level.
- **Scale.** Any strategy using resting orders must clear about 0.01–0.05% of adverse selection on top of the hurdles, and up to 0.055% at wider distances. That is roughly half the 0.05% maker-candidate threshold.
- **Regime caveat.** The sample includes an 11.96% market rise. Sells are consistently worse than buys, which may reflect that trend, but that is my conjecture and has not been tested.

---

## 4. Changes to shared tooling

| Change | Why | Effect on your prior results |
|---|---|---|
| **`event_anchored_lead_lag`: strict time alignment** (new `grid_returns` helper; `legacy_alignment=True` reproduces the old behaviour) | The function located "j−1 steps after the close" by row position. Whenever the coarse series is longer than the fine one, every early coarse bar was paired with the first few fine rows of the file. On synthetic data: n about 3× too large and an injected beta of 0.05 reported as 0.017. On your data, about 84% of the 5m bars close before the 1m file begins. | **Any earlier 1m:5m event-anchored number is invalid.** 5m:15m and 5m:1h are affected only if their files had gaps, and the freqtrade files have none. On gap-free, same-span data the new code gives identical output (checked on all four built-in formulas). |
| **Walk-forward tests only the fit-selected lag** | Previously validate rescanned all lags and compared "best lag within 1 step", so validate could pick its own winner among many. Now: same sign and p < 0.05 at the one fit-selected lag. | Earlier walk-forward manifests used the looser rule and are not comparable. |
| **Half-open walk-forward windows** | The boundary bar sat in both fit and validate. | Same as above. |
| **Family size and adjusted p in every run** | Work order convention. Both Bonferroni and Holm are reported and neither is preferred. | Added columns and manifest fields only. |
| **Data keys are `PAIR:timeframe`** | Task 0. Bare `"5m"` still means the default pair, so existing formulas are unchanged. `:raw` reads the raw store. | None. |
| **`run_fingerprint.py --start-date`** | Post-break runs without touching full-history outputs. | New option only. |

**Suggested addition to the mistake log:** *"Pairing a coarse and a fine series by row position when their date ranges differ. Match by timestamp, and drop anything that is not exactly on time."*

One pre-existing note: `requirements.txt` says `statsmodels>=0.14`, but `stats_fingerprint.py` needs 0.15 or newer (0.14.x fails on a keyword argument). The operator's environment is fine.

---

## 5. Where the artifacts are

- **Code (11 files):** `leadlag.py`, `research_cli.py` and `run_fingerprint.py` (modified, each with a `.patch` against the previous version), plus `costs.py`, `multitest.py`, `databundle.py`, `fetch_klines.py`, `task0_report.py`, `passive_fill_baseline.py`, `selftest_research_cli.py` and `selftest_all.sh`.
- **Results:** `results/task0_report.json`, `data_ranges.json`, `leadlag_summary.json` and `resample_checks.json` (run with `--start-date 2026-01-30`), `runs/20260919T125727Z_passive_fill_baseline.{csv,json}` and its per-order audit file `_orders.csv`.
- **Raw store:** `user_data/data/binance_raw/` including `symbol_filters.json`.

---

## 6. Decisions requested from the mathematician

1. **Canonical sample for the 5m-based event-anchored results.** Delivered as post-break only. A full-history run can be supplied for side-by-side comparison if wanted, but about 80% of it predates the break.
2. **Window settings for walk-forward.** With about 6 months of post-break data, 90/30 is the only feasible setting (3–4 splits). Fewer splits mean a weaker test of "replicates in every split", so please keep that in mind when setting the bar.
3. **Open-price test (section 2.3).** May I rebuild bars with `open` from the first traded minute to confirm the hypothesis? This does not touch the financial model.
4. **Lag-unit relabeling (section 2.6).** Any objection to adding an explicit `lag_minutes` column?

---

## 7. Tasks 1, 3 and 4 — interpretations I will use unless you object

Nothing is blocking. The raw store already carries `n_trades` and `taker_buy_*`, and `ETH_USDT` 1m and 5m are on the same span as `ETH_FDUSD`.

- **Multiple testing:** Bonferroni and Holm both reported, as above.
- **Task 1:** returns are close-to-close. "Flat" means no trades at ETH/FDUSD bar t (equivalent to the project's flat definition, per 2.2). Lags are built on the full 1-minute grid and shifted by time, not by row, and the ETH/FDUSD controls at t, t−1 and t−2 need a new multi-regressor function beside the existing one.
- **Task 3:** a later event must not sit inside an earlier event's target window, so I will require 13 bars between kept events rather than 12 (target windows run to k = 12). It is a one-line change if you want 12.
- **Task 4:** with origins on the hour, "half-hour-of-day" collapses to hour-of-day (24 levels), so I will use that. The volume ratio compares the same 60-minute clock window against its median over the prior 14 days. The 5-day range uses closed daily bars only.

If any of these does not match your intent, please say so before I build.
