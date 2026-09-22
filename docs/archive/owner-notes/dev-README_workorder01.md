# Work order #1 — developer delivery: Tasks 0 and 2

Everything below is run from the **repo root** unless stated. No new dependencies (the downloader uses only the standard library).

## 0. Install
Copy `user_data/analysis/*` from this folder over your tree.
- **3 files replaced** (diffs in `patches/`, each applies cleanly to the current live file): `leadlag.py`, `research_cli.py`, `run_fingerprint.py`
- **8 files new**: `costs.py`, `multitest.py`, `databundle.py`, `fetch_klines.py`, `task0_report.py`, `passive_fill_baseline.py`, `selftest_research_cli.py`, `selftest_all.sh`

## 1. Self-tests (offline, synthetic data with known answers)
```
cd user_data/analysis && bash selftest_all.sh
```
Expect the last line `ALL SELF-TESTS PASSED`. If not, paste the whole output back.

## 2. Task 0 — data
```
python3 user_data/analysis/fetch_klines.py --dry-run     # shows the plan + request count, downloads nothing
python3 user_data/analysis/fetch_klines.py               # downloads (resumable: re-run if interrupted)
python3 user_data/analysis/task0_report.py               # history, fees, break split, 1d-vs-1m, raw-vs-freqtrade
python3 user_data/analysis/run_fingerprint.py            # FULL run (no --fast); includes 1d and 1w
python3 user_data/analysis/run_fingerprint.py --start-date 2026-01-30   # optional: same battery, post-break bars only
```
Send back: the printed output of `fetch_klines.py` and `task0_report.py`, plus from `user_data/analysis/results/`:
`task0_report.json`, `leadlag_summary.json`, `data_ranges.json`, `resample_checks.json`, and `user_data/data/binance_raw/symbol_filters.json`.

## 3. Task 2 — passive-fill negative control
```
python3 user_data/analysis/passive_fill_baseline.py
```
(needs `symbol_filters.json` from step 2 for the tick size, or pass `--tick-size`). Send back the printed table and `results/runs/*_passive_fill_baseline.{csv,json}`.

## What changed in existing code
- **`leadlag.py` — bug fix in `event_anchored_lead_lag`.** It located "the fine row j-1 steps after the close" by *position*. Wrong whenever the coarse series is longer than the fine series (coarse bars closing before the fine data starts were all paired with the first rows of the fine file) or the fine file has missing rows. Synthetic reproduction: n 3x too large, injected beta 0.05 reported as 0.017–0.019. Now a pair is used only if the fine row sits exactly at `close + (j-1)·step`. On gap-free, same-span data results are identical (checked on all four built-in formulas). `legacy_alignment=True` reproduces the old behaviour for comparison only. Also added `grid_returns` (returns that never span a missing row).
- **`research_cli.py`**: `data` keys are now `PAIR:timeframe` (bare `"5m"` still means the default pair; `:raw` reads the raw-kline store); event-anchored inputs use `grid_returns`; every run records family size + Bonferroni and Holm adjusted p; **walk-forward now tests only the fit-selected lag in validate** (same sign and p<0.05) instead of rescanning, and windows are half-open (the boundary bar used to sit in both fit and validate).
- **`run_fingerprint.py`**: `event_anchored_best` now carries family size and adjusted p (per pair, and pooled across all pairs: 15+15+36 = 66); `--start-date`; writes `data_ranges.json`.

## Choices made and where they are visible
Nothing that moves the financial model is assumed; where the work order is open to two readings both are run and labeled.
- Adjusted p: Bonferroni **and** Holm always reported.
- Task 2 fill window: `A_14bars` (strict) and `B_15bars` both reported. All other timing rules are spelled out in the docstring of `passive_fill_baseline.py`.
- Tick size: read from Binance `exchangeInfo`, cross-checked against the price grid in the data, run aborts on mismatch.
- Fees (`costs.py`): maker 0%, taker 0.100% as reported by the project owner; scenarios A/B as in the work order.
- Post-break: `task0_report.py` reports rows before / on / after 2026-01-29 rather than choosing; Task 2 uses origins from 2026-01-30 (`--start` to change).
