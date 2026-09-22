**Developer orientation reply, round 1 (nothing built)**

### 1. Goal and role

The project tests whether ETH/USDT has a statistically defensible, cost-surviving predictive signal, using pre-registered candidates (S2 `funding_extreme`, S1 `trend_slope`, then Task 3 `shock_response`) at 5m and above on data through 2025-08-31. Each candidate must pass Holm within its family, walk-forward stability, by-year and leave-one-year-out checks, an economic gate at the 0.30% stress round trip (slope cells), and a locked holdout consumed once, and only a survivor becomes a freqtrade strategy. My role is developer: I build and test the code, state every interpretation in the docstring and report, run both readings and label them wherever a spec allows two (never assuming anything that touches the financial model), test on synthetic data with known ground truth, and send research-design questions to you rather than the owner. The owner runs every command on their Mac and pastes back the output, so I give exact copy-pasteable commands, and this round I build nothing.

### 2. First three builds, in order (your queue 1–3, §7.4)

1. **Selection-rule change.** Lag chosen by smallest p (largest |HAC t|), with no "significant" pre-filter. I will regress against the previous outputs and add a synthetic test where smallest-p and largest-|beta| pick different lags.
2. **Pass-rule machinery.**
   - The `--end-date` guard and holdout lock, with the §7.9 origin purge at every discovery and walk-forward boundary.
   - The by-year table and leave-one-year-out, with the 120-day rule from §7.10.
   - The registry, empty for ETH/USDT, with the ETH/FDUSD runs imported as `history` / `void_pre_fix` (§7.12).
   - The freeze manifest and a one-shot forward-test command that enforces the §7.6 minimum sample and the §7.7 net-positive check.
   - Tests: the guard must refuse to read past the cutoff, and a candidate cannot be forward-tested twice.
3. **Data batch tools, then one owner run.**
   - A funding-rate fetcher: REST first, `data.binance.vision` monthly fallback, reporting the source, the first settlement date and any interval change.
   - ETH/USDT 5m and BTC/USDT 1h/1d back to 2017-08-17.
   - A gap locator for the 128 missing ETH/USDT hours, with a 5m cross-check; gaps are masked, never dropped.
   - The monthly liquidity table, ETH/FDUSD vs ETH/USDT, 2026, from the raw 1m store.

After these come S2, S1, Task 3 (queue 4). The rule evaluator and Task 4 wait for a candidate. The ETH/USDT freqtrade files wait for a candidate that has passed discovery and stability (1.4 items 1 and 3).

### 3. Ambiguities and contradictions

**Need your answer.** Each touches a gate or a rule. Until answered I run both readings and label them.

- **A1. S2 rank convention.**
  - §7.5: "rank = its percentile within the previous 270 settlements (current excluded)". The convention is undefined: share strictly below, share at-or-below, or mid-rank.
  - I expect many ties, since funding often sits at the 0.01% baseline; I will count them on real data.
  - The S2 rule ("latest rank <= 0.5", §7.7) and the tails (≤ 0.10, ≥ 0.90) flip with the convention.
  - Working: report strict-below and at-or-below.
- **A2. Economic-gate windows.**
  - §7.7: "net return >= 0 in at least 70% of the 90-day validate windows". The S1 and S2 rules fit nothing, so which windows?
  - (a) The walk-forward validate windows, which exclude the first 365 days.
  - (b) Non-overlapping 90-day windows tiling the whole discovery sample.
  - Is "pooled" over the same span?
  - Working: run both, labeled.
- **A3. Funding interval change.**
  - §7.3 item 2: "normalize to 8h and report where". §7.8: "report the dates and set HAC lags to ceil(H / shortest interval)".
  - Do I scale the rate by 8h/interval and keep every native settlement as an observation, or keep only 8h-aligned settlements?
  - This is live only if the data shows a change. I will report what it shows first; a pre-answer saves a round trip.
- **A4. Holdout integrity.**
  - (a) §7.2 locks data after 2025-08-31, but the ETH/USDT raw store already runs to 2026-09-19 (about 384 days past the cutoff). 1.4 item 1 will later put ETH/USDT into freqtrade format, so the lock is software-only (`--end-date`, `TIMERANGE`). I propose truncating the freqtrade export at the cutoff, with the forward-test command reading the raw store only. Agreed?
  - (b) §5's ETH/FDUSD analyses (fingerprint, lead-lag, Task 2) use 2026-01-30 to 2026-09-19, inside the ETH/USDT holdout window, and the two pairs trade at nearly the same price. §7.12 keeps them out of Holm, but do you still treat the holdout as unseen?
  - (c) Does the forward test read up to the latest data at test time (currently 2026-09-19)?
- **A5. Execution pair.**
  - §11: "Only one decision remains, and it belongs to the owner: the execution pair." Clarification 1.4 item 1 assumes ETH/USDT.
  - I have asked the owner to confirm. Nothing depends on it until a candidate exists.

**Working readings.** Reply only if wrong.

- **B1. Origin sets (§7.9 with 1.4 item 4).**
  - "One common origin set" means the intersection over all cells in a family.
  - S1: the first origin is the 161st daily close, and the h=1 cells drop their last 4 origins to match h=5.
  - S2: the first origin is the 271st settlement (270 previous plus the current one, per "current excluded"), and the 24h cells drop their last 6 settlements to match 72h.
  - The rank window is stated as "previous 270 settlements" in §7.5 and "previous 90 days" in §7.8. These agree at 8h. If the interval ever differs, I use §7.8 (90 days in clock time).
  - I will report the first origin dates from the data.
- **B2. Entry time on daily bars.**
  - §7.5 S1 target is `ln(C_{t+h} / C_t)`, which enters at the close of day t. The §7.7 rule enters "from the next open". §7.9 puts holdout origins at "entry time >= 2025-09-01 00:00 UTC".
  - Working: slope cells use the bar's close time (23:59:59.999). So the 2025-08-31 origin has its entry in discovery and its window past the cutoff, and it is dropped, belonging to neither. The rule evaluator uses the next open, and the first S1 holdout origin is t = 2025-09-01.
  - If you meant the next open, the 2025-08-31 origin belongs to the holdout.
- **B3. Rule-evaluator trigger.**
  - §7.4 item 5 and §7.5 say "only if a candidate passes discovery". 1.4 item 3 says a precondition to freeze, built once a slope candidate passes discovery and stability, and "earlier allowed".
  - Working: 1.4 governs. I build it when a slope candidate passes discovery and stability, and not earlier unless you say.
- **B4. §7.6 SE scaling.** "Scaled to holdout size" has no formula. Working: SE_holdout = SE_discovery × sqrt(N_discovery / N_holdout), stated in the docstring.
- **B5. Numbers and evidence in the handoff.**
  - §4 says "1h has 128 missing hours", but 3,321 days × 24 = 79,704 hours against 79,572 rows is 132. The 4-hour difference would fit a series that starts at 04:00 on 2017-08-17 (my inference; file unseen). The gap locator will report the leading partial day separately from the interior gaps.
  - The 3,321 daily rows equal the calendar-day count from 2017-08-17 to 2026-09-19, so 1d shows no missing days on that arithmetic.
  - §3 says "Sizes in bytes", but 1.4 item 6 implies some earlier sizes may have been character counts. I have asked for `ls -l` and will report any difference.
  - §3 and §10 cite `tree-02.txt`, `terminal-05.txt` and `terminal-06.txt`, but §8 lists only `terminal-01/02/03.txt` and `tree-01.txt`. I have asked for the three missing ones.

### 4. Files read and not seen

- **Read in full:**
  - `HANDOFF_developer-1.3.md` (v2.2), header through §11, fetched from the raw URL you gave.
  - Clarifications 1.4, as pasted in your message.
- **Not seen:**
  - All source code, `README.md`, `project_context.md`, `requirements.txt` and `scripts/backtest.sh`.
  - `workorder-01`, `1.1`, `1.2`, `1.3`, `answer-01`, `answer-02`, `terminal-01` to `06`, `tree-01`, `tree-02`.
  - Everything in `dump-sept-02` (JSON and logs).
- **What follows from that:**
  - Every statement about code, sizes, self-tests and data spans above is the handoff's claim, not something I verified.
  - I computed myself only the day/hour arithmetic in B5 and the origin counts in B1.
  - The "verbatim" status of §7.1–7.5 is unchecked.
  - Task 3's full spec lives in `workorder-01.md` (§7.5: "as in workorder-01.md"), so I cannot yet check it against §7.13 (1m unused).
  - I also cannot tell whether the GitHub copy of the handoff matches the owner's local one.


