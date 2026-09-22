**Developer confirmation of Answers 1.5 (queue starting; nothing built yet)**

### 1. Accepted as ruled
A1–A5, B1–B5, the Task 3 spec, the order of work and the snapshot. My implementation readings, stated so you can catch a misreading:
- **A1:** mid-rank as specified. The tie share is computed on observations up to the cutoff. Strict-below and at-or-below appear only as labeled robustness columns.
- **A2:**
  - Each family's tiling starts at its own first origin, with the rule starting flat.
  - Cash earns 0.
  - The final partial window is out of the 70% count and in the pooled figure.
  - S1 and S2 get separate tilings.
- **A3:** native settlement times are rounded to the nearest second before assignment to (s−8h, s]. An observation whose window has a missing native settlement is masked and counted.
- **A4:**
  - The registry stores the ETH/FDUSD exposure note on every holdout test, and the manifest records the data end date.
  - Every BTC sign is computed on data up to the cutoff only, until the forward-test command.
- **B2:** the common S1 set ends 2025-08-26.

### 2. Still open from my round-1 addendum
Your 1.5 does not mention these. I proceed on the default and label it.
- **A2-extended. Stouffer windows for the S1/S2 primary cells.** Nothing is fit there. Default: the 90-day validate blocks after the first 365 days. The alternative is tiling from the first origin. I still need `walkforward.py` to see whether fit windows roll or expand. Needed before item 2.
- **C1. Guard scope.** Default:
  - Enforce `--end-date` in `databundle.load_bundle` and the `run_fingerprint` loader, plus an explicit holdout flag on the forward-test command.
  - `task0_report` (counts, spans, gaps) and `fetch_klines` (downloads) stay unguarded and are stamped "descriptive, no returns computed".
  - Post-cutoff descriptive reads (gap locator, liquidity table, funding tie share) are not "hypothesis-specific". Needed before item 2.
- **C2.** If an S2 origin's entry or exit bar falls in a missing hour, I exclude the origin and count it.
- **C3.** As far as I know, freqtrade reads an end date as 00:00 UTC of that day. So `TIMERANGE` ending `20250831` stops up to 24h before the cutoff, which is the safe side. I'll verify when a backtest is needed.

### 3. New from your answers
- **N1. Position open at the cutoff (financial model).**
  - Default: force an exit at the last discovery bar's close, which equals the next open per your B2 ruling. Charge the exit cost and label it "end-of-sample exit". This means no holdout price enters discovery.
  - Alternative: mark to market with no exit cost.
  - I run both, labeled, unless told. Needed when I build the rule evaluator.
- **N2. Task 3 direction.**
  - `answer-01` §1 makes k = 6 a fixed, pre-registered cell. `answer-02` orients Task 3 by each split's fit-window sign.
  - Your classification is one-sided with M = 0.35%.
  - Working reading: discovery and classification test positive excess after each shock type (long-only). Walk-forward orientation follows `answer-02`. Is the pre-registered direction positive for both sides?
- **N3. Dose-response.** Are the |z| ≥ 4 events (i) the subset of the kept |z| ≥ 3 events, or (ii) a fresh 13-bar de-clustering at threshold 4? I compute both, labeled. Which one governs the "discard" flag?
- **N4. Unconditional mean.** Working reading:
  - μ is the mean same-horizon return over all discovery origins of that timeframe, event bars included, treated as a constant.
  - The one-sided t-test runs on event excesses, which do not overlap by construction.
  - MDE comes from that SE.

### 4. Facts from my file checks (for your context document)
- §7.1–7.5 are identical to the new-phase block in `workorder-1.2.md` (whitespace-normalized diff, 0 differences). §7.6–7.13 match `workorder-1.3.md` section A.
- All 17 shared files match the owner's `ls -l` byte counts. The handoff figures for `costs.py` (6,710) and `backtest.sh` (1,980) are one byte high; disk has 6,709 and 1,979.
- The venv Python is 3.12.7.
- **Code shape:**
  - The selection rule lives in `leadlag.summarize_best_lag`, with 4 formula callers, 3 in `run_fingerprint` and 6 in `leadlag`'s own self-test.
  - The live walk-forward verdict is the old per-split "replicated" (same sign and validate p < 0.05), so item 2 replaces it.
  - The code slices data to a window and then computes predictors, which cannot serve S1/S2 lookbacks. For those I compute predictors once and assign origins by entry time and target end.
  - `fetch_klines` already extends backwards and maps BTCUSDT correctly. Funding needs a new client, since only spot hosts are configured, and I will test it offline.

### 5. Next
1. Read the whole snapshot before building.
2. Build the funding fetcher, gap locator and liquidity table, and hand the owner those commands.
3. Item 1, then item 2.
4. S1, then S2 after the funding data, then Task 3.

The ETH/USDT 5m and BTC/USDT 1h/1d downloads need no new code, so their commands go to the owner now.
