# Mathematician notes

This file IS `context/mathematician/NOTES.md` in the project repo (see REPOSITORY below) — the owner
attaches it directly to a fresh mathematician chat or to the developer; there is no separate "context
document" anymore. Version by the snapshot line below, not by filename; when this changes, the old
copy in the repo gets overwritten, same path, and git history carries the diff.

Snapshot: 2026-09-23. Supersedes every earlier "mathematician context vX" file (v2, v2.1-v2.4) and the
first context file (maker-fee assumption). ITEM 2 (the guard, holdout lock, registry,
by-year/leave-one-year-out machinery and freeze/forward-test command) IS STILL IN PROGRESS, NOT YET
DELIVERED. Check its report in full against section 6 before trusting any pass/fail verdict it
produces — this will be the project's first real test of the gate machinery. WORK ORDER 1.4 (pair
expansion to ETH/USDT + BTC/USDT, section 4/7/9) is issued and owner-approved but NOT YET BUILT —
BTC/USDT 5m/15m data and the volatility comparison are outstanding.

REPOSITORY: the project consolidated onto one real, public, live repo on 2026-09-22:
https://github.com/nitinroshia/crypto_bot (main branch). The five scratch repos (dump-sept,
dump-sept-01, dump-sept-02, handover-2026-09-20, sample-bot) are retired; do not trust links to them
going forward. Verified 2026-09-23 (details in section 9). To fetch a specific file, use
https://raw.githubusercontent.com/nitinroshia/crypto_bot/main/<path> — GitHub's own /tree/ directory
pages refuse automated fetching by an AI's browsing tool (robots.txt), so don't try to browse a folder
that way; either fetch a known file path directly, or ask the owner/developer for the path.

FILE NAMING (settled 2026-09-23): a new formal specification from me is a new file in
docs/work-orders/, continuing the existing sequence (01, 1.1, 1.2, 1.3, 1.4 — next is 1.5). A smaller
ruling or answer to a specific developer question is a new file in docs/correspondence/, continuing
that sequence (answer-01, answer-02 so far — next is answer-03). This recurring notes file is always
context/mathematician/NOTES.md, one file, overwritten in place. I don't commit to git or run terminal
commands myself — the owner (the bridge) relays files directly: Mathematician < Owner (bridge) >
Developer, with the owner handling all execution and attaching files rather than pasting links.
Paste this at the start of a fresh chat, then the developer's latest message. Current rules only;
superseded rules are omitted on purpose. If a report mentions Scenario A, A-stress, a maker-candidate
band, a 0.04% filter threshold, "largest |beta| among significant lags" as the live default (it now
survives only as `select="legacy_max_abs_effect_among_significant"`, used solely to reproduce the
section-5 numbers), fit-window-sign orientation for Task 3's two PRIMARY cells (now pre-registered
positive), walk-forward validate windows for the S1/S2 gate or stability check (they use non-overlapping
90-day tiling instead), or Task 1/Task 5 — those are retired or superseded.

## 1. Role and working contract

- I am the math designer (senior quant statistician). A separate developer, with no shared memory
  with me, builds research code and sends reports. The owner ("the bridge") runs every command on
  their Mac and pastes outputs between us. The developer's sandbox has no route to Binance, so data
  work is batched into single owner runs with copy-pasteable commands (no placeholders).
- Developer's hard rules: never assume anything that touches the financial model; where a spec allows
  two readings, run both and label them; interpretations go in docstrings and reports. So my orders
  must be unambiguous: exact definitions, family size, primary cell, direction.
- Owner's goal: consistent results and fast compounding; a small consistent gain compounded quickly
  is fine. The owner gave me full authority over method. I never promise results, say plainly when
  nothing has been found, and keep notes to the owner short (results, not derivations).
- Stance: aggressive with ideas, strict with validation. No martingale, grids, averaging down or
  leverage; nothing that buys smoothness by selling tail risk. Failed ideas are killed, not retuned.
- Check every developer report: recompute row counts, split counts, missing-data arithmetic and Holm
  p-values before trusting them.
- Reply format: a short note to the owner, then a block "For the developer (forward as is)". Orders
  state: predictor (exact computation, availability time), target, timeframes, lags, gut-check,
  plausible effect scale, family size, primary cell, direction.
- Mandatory gut-check for every formula: (a) can the same raw price data appear on both sides?
  (b) does a shared latent state (volatility clustering, seasonality, stale last-trade prices,
  market drift) make the comparison trivially significant?
- Plausibility bands (correlation units): same-asset autocorrelation 0.004-0.011; credible new
  effect 0.01-0.05; 0.5+ presume an artifact. Beta is not on this scale; ask for correlation too.
- Methodological caution: for any long-only formula, check whether the trading constraint itself
  already fixes the pre-registered direction before defaulting to two-sided/fit-window-sign
  orientation (I made this mistake once with Task 3; see mistake #13).
- Authority (owner-confirmed 2026-09-23): I decide research design outright — formulas, thresholds,
  sample splits, gates, ambiguity rulings. Ordinary code and architecture decisions inside the
  developer's own domain (module layout, refactoring, how something is implemented) are the
  developer's call; I don't weigh in on those. Project-level decisions — objectives, strategy
  principles, system architecture (e.g. which pairs the project targets), risk or capital exposure,
  a change in direction — need the owner's sign-off; the pair-expansion decision in section 4/9 is an
  example that went through this channel. If the developer and I genuinely disagree on something, the
  owner has final say. The owner wants awareness, not to be a message router or to micromanage
  routine calls, so I keep notes short and flag only what actually needs a decision from them.

## 2. Scoreboard (out-of-sample, net of costs)

- Consistency: at least 70% of 4-week windows positive, worst window no worse than -3%, max drawdown
  at most 10%, still profitable after removing the best 5% of trades.
- Compounding: geometric growth per week with days-to-double. Target at least 1%/week, but under the
  0.10%/0.10% fee schedule that is a stretch; the realistic centre is lower. Say so plainly.
- Robustness: same verdict under the stress cost (section 3), with parameters +-20%, and one bar late.

## 3. Economics (owner's instruction, final)

- Planning fee: 0.10% maker and 0.10% taker on every fill (Binance default). Promotions are ignored
  and never modeled, including the zero maker fee the account currently shows on ETH/FDUSD. I once
  planned around that promotion and the owner corrected me. Do not reintroduce it.
- Slippage allowance: 0.02% per side (an assumption; replace with a measured value in dry-run).
  Base round trip = 0.24%. Stress: fee 0.12% + slippage 0.03% per side = 0.30% round trip.
- Execution: taker at the next bar's open. No fill-probability modeling. Freqtrade has no slippage
  setting, so strategy-layer backtests pass the per-side fee + slippage as the fee: --fee 0.0012
  (base) and --fee 0.0015 (stress); this reproduces costs.py net_return to within 1e-8 on a flat
  trade. scripts/backtest.sh selects the case with COST_CASE (default base), reads the number from
  costs.py --per-side, and caps the default TIMERANGE at 20250831 (the holdout lock also covers
  strategy backtests).
- Materiality M = 0.35% gross per round trip (stress cost 0.30% + 0.05% margin), measured as the
  EXCESS over the unconditional mean forward return at the same horizon, so a bull-market drift cannot
  pass on its own. M applies to event-type effects (Task 3); it does not apply to the S1/S2 economic
  gate, which instead requires net-positive strategy return (section 6).
- Break-even hit rate at 0.24% round trip, ETH-like volatility (about 70% annualized), symmetric
  payoffs: 15m about 90%, 1h about 70%, 4h about 60%, 1d about 54%. The small-gain high-frequency route
  is closed. Feasible domain: hours-to-days horizons, rare large conditional moves, information
  beyond price (funding). This table is ETH-specific; Work Order 1.4 asked for realized volatility on
  BTC/USDT too, to see whether a separate BTC table is needed (outstanding). M itself (below) doesn't
  need this, since it's cost-derived, not volatility-derived, and is identical for every pair.

## 4. Data and infrastructure

- Pairs (settled 2026-09-23, Work Order 1.4): ETH/USDT and BTC/USDT are the project's two live pairs,
  for research AND execution. ETH/USDT was already the research pair (my decision, 2026-09-20: deepest,
  no flat candles, 9+ years of history); it's now confirmed as the execution pair too. BTC/USDT is
  elevated from a same-sign replication check to a full second pair, run through the complete pipeline
  in its own right (section 7). ETH/FDUSD is retired from execution — the 2026 liquidity numbers below
  (2.0-4.5% of ETH/USDT's activity) made that case, and the owner acted on it. ETH/FDUSD's existing
  results (section 5) stay as historical reference; no new formula work targets it.
- ETH/USDT raw store (5m extended and BTC/USDT added in the owner's 2026-09-21 run):
  - 5m: 2017-08-17 04:00 to 2026-09-21 06:00, 955,046 rows. Every pre-existing row is byte-identical
    to the pre-extension file (developer-verified).
  - 1h: 2017-08-17 to 2026-09-19, 79,572 rows, 128 missing hours (last figure not yet re-confirmed
    past 09-19; not re-pulled in this run).
  - 1d: 3,321 rows, through 2026-09-19 (not re-pulled in this run).
  - 1m: 2026-01-30 to 2026-09-19.
  - Missing-hours finding: all 128 missing ETH/USDT hours coincide EXACTLY with 128 missing BTC/USDT
    hours (BTC/USDT 1h and 1d newly added, same start 2017-08-17, for this comparison) -- an
    exchange-wide gap pattern, not ETH-specific. Of 1,715 missing 5m bars in the full 5m history:
    1,536 fall inside those 128 hours (12 bars/hour, exactly as expected) and 179 are scattered
    elsewhere. Row-count check (independently verified): a gap-free 5m series over the exact span
    above would have 956,761 bars; 956,761 minus 1,715 missing = 955,046, matching the reported row
    count exactly. Gaps are masked, never dropped, in every downstream computation.
  - The leading-hours question from the original 132-vs-128 discrepancy is resolved: 132 = 4 leading
    hours (before the 04:00 series start, a start-of-data artifact, not a gap) + 128 interior gaps.
- Funding (ETHUSDT and BTCUSDT USD-M perpetuals; REST source, no fallback needed): constant 8h
  settlement interval since each symbol's first settlement, no interval changes observed for either.
  One observation is masked per symbol (the first, whose preceding span is unknown by construction).
  Tie share (fraction of observations at the modal/baseline funding value), up to the 2025-08-31
  cutoff: 39.6% (ETH), 40.1% (BTC) -- confirms ties are common enough that the mid-rank convention
  (section 7, S2) matters. First-settlement dates: not yet reported; ask for them, since they set
  each series' earliest usable origin.
- BTC/USDT 5m and 15m (Work Order 1.4, outstanding): not yet pulled. BTC/USDT currently has only 1h
  and 1d (see above); Task 3 needs 5m/15m and can't run on BTC/USDT until this lands, with the same
  gap-check methodology as ETH/USDT's 1h (the 128-missing-hours finding).
- Annualized realized volatility, ETH/USDT vs BTC/USDT, discovery sample only (Work Order 1.4,
  outstanding): requested to check whether section 3's break-even table needs a BTC-specific version.
- Liquidity, ETH/FDUSD vs ETH/USDT, 2026 (from the raw 1m stores; descriptive, no returns computed):
  ETH/FDUSD trades per day ran 2.0-4.5% of ETH/USDT's in every month except January (11.1% by trade
  count, 40.5% by quote volume) -- January is a partial-month artifact (the ETH/FDUSD file starts
  2026-01-30, so only 2 covered days) and is not comparable to the rest. Every other month is
  comparable and consistent: ETH/FDUSD is a thin fraction of ETH/USDT's activity all year.
- ETH/FDUSD: 1m 2026-01-30 00:00 to 2026-09-19 23:59 UTC (335,520 rows as last measured, 0 missing
  bars, 9.59% zero-trade minutes); coarse files from 2023-08-04, about 80% pre-break. FDUSD/USDT 1m
  same span. Structural break 2026-01-29 (taker fees returned for all users on FDUSD pairs); post-break
  is canonical for ETH/FDUSD.
- Raw columns: date, open, high, low, close, volume, quote_volume, n_trades, taker_buy_base,
  taker_buy_quote. Freqtrade's data dir holds OHLCV only (separate on purpose).
- Resampling rule (validated, zero mismatches vs native on every timeframe): coarse bars from TRADED
  minutes only (open = first traded minute, high/low = extremes of traded minutes, close = last
  traded, an empty bin carries the previous close). Weekly bars anchor Monday.
- Research layer (Python 3.12.7 venv; repo ~/apps/crypto_bot, user_data/analysis/): research_cli.py
  (formulas via @register; data keys PAIR:timeframe), leadlag.py, walkforward.py, stats_fingerprint.py,
  run_fingerprint.py, resample.py, fetch_klines.py (raw klines; extends backwards, maps BTCUSDT
  correctly), a new funding-rate client (REST; built and tested this round), databundle.py,
  multitest.py (Holm/Bonferroni), costs.py, selftest_all.sh (ALL SELF-TESTS PASSED as of the most
  recent run). Strategy layer: freqtrade in Docker; tunables in user_data/test_params.json;
  MomentumTrailing is a naive placeholder. Cardinal sin: testing a math idea by editing a strategy
  and backtesting it.
- Lag-selection rule, `leadlag.summarize_best_lag` (rebuilt this round -- item 1, DONE): default is
  now min-p -- smallest p-value (largest |HAC t| in the fit window), no "significant" pre-filter, and
  never the largest |beta| or |correlation|. A best lag is reported whenever any lag was testable;
  `significant_at_5pct` separately says whether it clears 5%. Ties from p underflowing to exactly 0.0
  (common in the HAC tables at large n) are broken by the larger |HAC t| (or |Fisher z| in the
  non-overlapping table), then by the smaller lag -- approved. The pre-1.2 rule (largest |beta| or
  |correlation| among lags significant at 5%) survives only as `select="legacy_max_abs_effect_among_
  significant"`, kept solely so the frozen ETH/FDUSD lead-lag numbers in section 5 stay exactly
  reproducible; no caller invokes it implicitly, and no new candidate may use it.
  - Transitional note: `research_cli.evaluate_fixed_lag` (the old live walk-forward verdict, which
    used to pre-filter on significance before validating) is not patched for the new default, since
    item 2 replaces it outright. No stored result runs through this path outside self-tests. When
    item 2 lands, confirm this function is removed or fully superseded, with nothing left calling it.

## 5. Results so far (ETH/FDUSD; historical reference only -- see section 4)

- Open-price mismatch fully explained by flat minutes (old rule: open wrong on 7.6% of 5m bins, high
  2.1%, low 2.4%); traded-minutes rule gives zero.
- Equal-span fingerprint (2026-01-30 to 2026-09-19): flat share 9.59% at 1m, 0.39% at 5m, 0% from 15m
  up. Excess kurtosis 80.6 (1m), 31.7 (5m), 21.9 (15m), 20.4 (30m), 11.3 (1h), 5.7 (1d). Lag-1
  autocorrelation -0.011 (1m) to +0.012 (1h): tiny, absent from 1h up. Earlier mixed-span ladders
  (flat 12% -> 3.3% -> 1.5%; kurtosis 85 -> 2.4) are void.
- Event-anchored lead-lag (post-break, strict alignment, family 66): DEAD. Best: 1m:5m raw p 0.020
  (Holm 0.305), 5m:15m 0.025 (0.379), 5m:1h 0.0019 (0.068 own family, 0.124 across 66). The 1m:5m best
  lag flipped sign between samples (noise). Counted as ONE family of 66. These numbers were computed
  under the pre-1.2 lag-selection rule and remain exactly reproducible via
  `select="legacy_max_abs_effect_among_significant"` (section 4); do not recompute them under min-p
  and compare, since that would silently change what "the frozen result" means.
- Task 2 passive-fill baseline: all 36 cells negative, -0.003% to -0.034% before fees. Now moot
  (fees are symmetric), kept as history.
- Liquidity drift: ETH/FDUSD zero-trade minute share 2026 by month: Jan 0.0% (2 days), Feb 0.4, Mar
  3.0, Apr 8.1, May 13.9, Jun 6.6, Jul 14.1, Aug 21.3, Sep 8.4 (19 days); FDUSD/USDT 0.1, 0.5, 3.0,
  5.1, 4.3, 3.7, 7.1, 6.9, 5.3; ETH/USDT essentially none. Inference: ETH/FDUSD has been losing
  activity after the January fee change. The 2026 trade-count comparison in section 4 (2.0-4.5% of
  ETH/USDT most months) confirms the pair is thin in absolute terms too, not just declining.

## 6. Current rules (settled unless data contradict)

Conventions
- Bars are left-labeled and usable only after they close; earliest action is the next bar's open.
  For a daily predictor computed from the close of day t, "next bar's open" means the open of day
  t+1: a close-of-day-t predictor enters the market at t+1's open, never at t's own close.
- Holm is the gate (Bonferroni for reference), within each task's pre-registered family; cumulative
  count in the append-only registry; cells tagged pre-registered or exploratory; HAC or clustered SEs;
  correlation beside beta; every result states family size and adjusted p; report MDE from the
  standard error, never post-hoc power.
- Registry: starts empty for the ETH/USDT phase. Earlier ETH/FDUSD runs are imported as `history`
  (runs before the strict-alignment fix as `void_pre_fix`) and are excluded from Holm and from the
  cumulative count for ETH/USDT candidates.
- Tie-breaking in lag selection: see section 4 (min-p, then larger |HAC t| / |Fisher z|, then smaller
  lag).
- Pair-qualified family names (Work Order 1.4): every family name carries its pair, e.g.
  `S1-ETHUSDT`, `S1-BTCUSDT`, `S2-ETHUSDT`, `S2-BTCUSDT`, `Task3-ETHUSDT`, `Task3-BTCUSDT`. Add this to
  item 2's registry schema now, since it's still being built -- don't retrofit it later. A pair's own
  pipeline (Holm, gates, freeze, forward test) is otherwise identical regardless of which pair it is.

Sample design (ETH/USDT and BTC/USDT alike)
- Discovery and walk-forward use data up to and including 2025-08-31 (--end-date guard), THE SAME
  CUTOFF FOR BOTH PAIRS (Work Order 1.4) -- not just for comparability, but because ETH and BTC returns
  are correlated, so different cutoffs would risk one pair's holdout period doing work inside the
  other pair's discovery period. Data after the cutoff is a LOCKED HOLDOUT, readable only by the
  forward-test command, once per candidate (Holm across candidates that reach it, per pair). The
  holdout is everything after the cutoff through the latest data at test time; the manifest records
  the data end date used. ETH/FDUSD keeps its post-break 90/30 rules for reference only.
- Cutoff mechanics: the cutoff is 2025-08-31 23:59:59 UTC inclusive (last usable bars: 1d labeled
  2025-08-31, 1h labeled 23:00, 15m labeled 23:45, 5m labeled 23:55; funding settlements up to
  16:00). An origin's entry time is the open of its entry bar (see Conventions above for the
  close-t/open-(t+1) case). Discovery keeps an origin only if its entry is at or after the sample
  start and its whole target window ends at or before the cutoff; otherwise the origin is dropped (no
  truncation). Holdout origins have entry time >= 2025-09-01 00:00 UTC; their predictors may look back
  into discovery data. Origins straddling the cutoff belong to neither. The same purge applies at
  every discovery/walk-forward fit-validate boundary. The discovery-mode data loader must hard-truncate
  at the cutoff -- it must never return a single post-cutoff row, not merely filter one out after
  loading -- so predictors are computed once on the already-truncated series. Only the forward-test
  command loads the full series (it needs pre-cutoff history for lookbacks).
- Holdout exposure (disclosed, not a violation): aggregate, non-hypothesis-specific 2026 ETH/FDUSD
  statistics -- the fingerprint, the dead lead-lag result, and the Task 2 baseline (section 5) -- fall
  inside the ETH/USDT holdout window (2026-01-30 onward is past the 2025-08-31 cutoff). None of them
  relates an ETH/USDT, BTC/USDT or funding predictor to an ETH/USDT return, so none is hypothesis-
  specific for this phase. Log this note on every ETH/USDT holdout test regardless. Outside the
  forward-test command, no statistic that relates a predictor to a return -- for ETH/USDT, BTC/USDT,
  or funding, in any combination, including the BTC replication sign -- may be computed on data after
  the cutoff. Purely descriptive reads that compute no return of any series (counts, spans, gaps,
  zero-trade shares, volume/trade tables, funding tie share and interval-change checks) may use the
  full data range and are logged as "descriptive, no returns computed" (section 4's data-batch results
  are all of this kind). The freqtrade export used for any live or dry-run purpose is truncated at the
  cutoff; the forward-test command alone may create a holdout-period export, at test time.
- Origin sets: each family uses one common origin set -- the intersection, by entry time, of every
  cell's usable origins. S1's first usable origin is the 161st daily close (L=160 and sigma30 both
  available); its common set across h=1 and h=5 ends at t=2025-08-26 (h=5's last complete window), so
  the last discovery origin is 2025-08-30 for h=1 alone but 2025-08-26 for the family. S2's first
  usable origin is the 271st settlement (270 previous plus the current, current excluded from the
  rank); its first holdout origin is the settlement at 2025-09-01 00:00 UTC. Report the first and last
  origin dates actually used for every primary cell, per pair -- BTC/USDT's origin dates need not match
  ETH/USDT's exactly (e.g. if a data gap shifts one pair's first usable origin) even though the cutoff
  is shared. An S1/S2 origin whose entry or exit bar falls inside a data gap (a missing hour, or any
  masked bar) is excluded and counted, not imputed.

Pipeline for a candidate
1. Discovery (data <= 2025-08-31): pre-registered cells stand on their own p-value (own-family Holm);
   exploratory cells only nominate.
2. Stability (a stability check, NOT independent evidence):
   - S1, S2 (no lag scan; fixed pre-registered direction): use the SAME non-overlapping 90-day blocks
     as the economic gate (step 3), tiled from the family's own first origin. Each block's sign is
     compared against the pre-registered direction; combined Stouffer z (equal weights) needs one-sided
     p < 0.05 (Holm across candidates carried forward); no block may be significantly opposite
     (two-sided p < 0.05, opposite sign); the final partial block is excluded from this check.
   - Task 3's two primary cells (fixed pre-registered direction, both positive -- see section 7):
     standard rolling walk-forward, fit 365 days / validate 90 days. Confirm in walkforward.py whether
     the fit window rolls or expands; I asked for this confirmation and have not yet received it --
     if it expands, tell me before trusting any Task 3 stability result.
   - Fit-window-sign orientation (picking each split's own sign from the fit window) applies only to
     genuinely exploratory cells with no pre-registered direction -- currently just Task 3's 46
     non-primary lag/timeframe/side combinations, which are descriptive and cannot pass any gate.
   - Orientation for every current primary cell: S1 positive; S2 negative; Task 3's two primary cells
     positive; Task 4 volume coefficient positive.
3. Economic gate (S1, S2 only; M from section 3 does not apply here): run the frozen pre-registered
   rule (section 7) in the evaluator at STRESS cost, on non-overlapping 90-day blocks tiled from the
   family's own first origin (the same tiling as step 2, not the walk-forward validate windows). The
   rule starts flat at the beginning of each evaluation segment; cash returns 0; a block's return is
   the compounded net strategy return at stress cost, with costs charged only when the position
   changes, so a position may carry across a block boundary at no cost. The final partial block is
   excluded from the 70% pass count but included in the pooled net-return figure. Require pooled net
   return > 0 over the whole discovery sample AND net return >= 0 in at least 70% of full blocks. At
   the holdout, the frozen rule must also be net-positive at stress cost (same end-of-segment handling
   below), in addition to the slope cell's own forward-test success (step 5).
4. Freeze: timestamp, code commit, cell, direction, discovery estimate and dispersion in the manifest.
5. Holdout / forward test (the independent evidence): exactly the frozen primary cell, one-sided in
   the discovered direction, one look, then consumed. Minimum sample at test time: at least 45 days,
   at least 100 events or observations, SE no larger than half the claimed effect; if not met, wait
   (ask me if it needs more than 120 further days). SE_holdout = SE_discovery x sqrt(N_discovery /
   N_holdout), with N the primary cell's origin count after the purge; state the formula in the
   docstring. Success: one-sided p < 0.05 and estimate at least as large as both M (event-type cells)
   and half the discovery estimate. Failure = dead, no retuning. Dry-run follows.
   - End-of-segment handling (all evaluator uses): every evaluation segment -- a discovery block, the
     whole discovery sample, the holdout -- starts flat and is forced to exit at its last close,
     charged as an exit cost and labeled "end-of-sample exit"; no holdout price ever enters a
     discovery-side computation through this mechanism. Mark-to-market with no exit cost is a labeled
     variant only, never the default.

Three-way classification for event-type primary cells: pass = one-sided p < 0.05 and excess >= M;
dead = one-sided 95% upper bound below M; otherwise inconclusive. If MDE exceeds M a null is
inconclusive.

Non-stationarity rule: for every primary cell report a by-year table and leave-one-year-out estimates
(by-month for ETH/FDUSD). Red flag: if dropping any single year (month) cuts the estimate by more than
half or flips its sign, mark it year-driven; it does not advance without my review. Years with fewer
than 120 days of data are shown (with n and days covered) but not judged: they stay in the pooled
estimate and are excluded from leave-one-year-out and year-by-year sign statements.

Rule evaluator (research-layer tool; build when a slope candidate first passes discovery and
stability, since step 3 needs it immediately afterward): vectorized long/flat rule on closed bars,
entry/exit at the next bar's open, fees per side 0.10% + slippage 0.02% (stress 0.12% + 0.03%),
end-of-segment handling as in step 5 above, window-return mechanics as in step 3 above. Outputs:
trades, hit rate, mean gross and net per trade; per-block and pooled growth per week, max drawdown,
share of positive blocks; by-year table; benchmarks buy-and-hold and cash. Self-tests on synthetic
data with known truth (a random walk must be net-negative after costs; an injected drift must be
recovered; a position spanning a block boundary must be charged costs once, not twice).

## 7. Pre-registered tasks (ETH/USDT unless stated)

Order: S2 and S1 first (cheap, slow), then T3; Task 4 and the evaluator only if a candidate exists.

S2 funding_extreme (ETHUSDT USD-M perpetual funding; ETH/USDT spot prices; family 2 primary)
- Predictor: funding rate at each settlement s. Observations are the 8h-aligned settlements only
  (00:00/08:00/16:00 UTC); an observation's rate is the sum of native rates settled in (s-8h, s]
  (equal to the native rate whenever the interval is already 8h, which both ETHUSDT and BTCUSDT show
  throughout, with no interval changes observed to date -- section 4). A window with a missing native
  settlement is masked and counted. rank = MID-RANK: (count of the previous 270 observations strictly
  below the current value + 0.5 x count exactly tied) / 270, current excluded. Report the tie share
  (fraction of observations at the modal value; 39.6% ETH / 40.1% BTC up to the cutoff -- section 4).
  Strict-below and at-or-below rank are reported only as labeled robustness columns, never as the
  primary statistic.
- Target: ETH/USDT spot log return; entry = open of the 1h bar labeled s+1h, exit = open of the 1h
  bar labeled s+1h+H, with H = 24h and 72h in clock time.
- Test: OLS slope of forward return on rank, all settlements, Newey-West HAC (3 lags for 24h, 9 for
  72h; if any interval other than 8h ever appears, use ceil(H / shortest interval) -- moot at present
  since none has appeared); direction negative (higher funding, lower forward return). Primary: 72h.
- Pre-registered rule for the economic gate: long from the open of the 1h bar at s+1h while the
  latest rank <= 0.5, otherwise cash; re-evaluated at each settlement.
- Descriptive, exploratory: mean forward return and excess vs the unconditional mean in rank <= 0.10
  and >= 0.90.
- Gut-check: the rate is known at s and the target starts one bar later. Plausible if real:
  correlation -0.03 to -0.08; anything above 0.2 means a bug.
- BTC/USDT (Work Order 1.4): runs as its own full family, `S2-BTCUSDT`, same definitions, own gate and
  freeze. "Replicate the sign on BTC, report only" is retired. When either pair's S2 candidate
  freezes, report the other pair's same-cell point estimate, sign and discovery p-value as a labeled
  context column -- informative, not gating.

S1 trend_slope (1d; family 10)
- Predictor at the close of day t: x = ln(C_t / C_{t-L}) / sigma30, sigma30 = std of the last 30 daily
  log returns ending at t; L in {10, 20, 40, 80, 160}.
- Target: ln(C_{t+h} / C_t), h in {1, 5}; entry is the open of day t+1 (a close-of-day-t predictor
  never trades at t's own close); all daily origins; Newey-West HAC (5 lags for h = 1, 10 for h = 5).
  Direction positive.
- Primary: L = 40, h = 5. The other nine cells are exploratory; Holm within the 10. Pre-registered
  rule for the economic gate: long from the next open if x > 0 at the day's close, otherwise cash.
- Gut-check: x uses closes <= t, y uses closes > t; overlap in x is handled by HAC.
- BTC/USDT (Work Order 1.4): runs as its own full family, `S1-BTCUSDT`, same definitions, own gate and
  freeze. "Replicate the sign on BTC, report only" is retired. When either pair's S1 candidate
  freezes, report the other pair's same-cell point estimate, sign and discovery p-value as a labeled
  context column -- informative, not gating.

Task 3 shock_response (5m primary, 15m secondary; family 48 per pair = 2 timeframes x 12 lags x 2
sides; ETH/USDT now, BTC/USDT once its 5m/15m data lands -- Work Order 1.4, outstanding -- as a
separate family `Task3-BTCUSDT`, same definitions)
- Event: closed bar with |z| >= 3, z = its return / std of the prior 24h of same-timeframe returns
  (bar excluded). Keep the first event; ignore events until 13 bars later so 12-bar windows never
  overlap.
- Target: return from the next bar's open to the close of bar k, k = 1..12, separately after
  down-shocks (z <= -3) and up-shocks (z >= +3). mu = the mean same-horizon return over ALL discovery
  origins of that timeframe (event bars included), treated as a constant; report both the raw mean and
  the excess (mean minus mu). The one-sided t-test runs on the event excesses, which do not overlap by
  construction; MDE comes from that same SE. A labeled robustness variant recomputes mu from non-event
  origins only.
- Primary: k = 6, each side, at 5m. BOTH cells are PRE-REGISTERED ONE-SIDED POSITIVE excess -- buy
  after a down-shock is a reversal bet, buy after an up-shock is a continuation bet, and spot is
  long-only either way. This is a fixed direction, not fit-window sign (which I had wrongly applied to
  these two cells earlier -- corrected; see mistake #13). Everything else in the family of 48 is an
  interpretive curve with no pre-registered direction and cannot pass any gate.
- Dose-response check (not a test; a discard rule): apply a FRESH 13-bar de-clustering at threshold
  |z| >= 4 (a new event set, not the subset of kept |z| >= 3 events) and compare its k = 6 point
  estimate, per side, against the |z| >= 3 estimate. Discard the |z| >= 3 result if the |z| >= 4
  estimate is smaller AND the |z| >= 4 sample has at least 30 events. With fewer than 30 |z| >= 4
  events, mark the check "not evaluable" and flag it for my review rather than discarding.
- Classification: the three-way rule (section 6) with M = 0.35% applied to the excess, not the raw
  mean. An effect above about 1% at 60 minutes means a bug.
- Gut-check: the volatility estimate excludes the event bar, and the target starts after the event
  bar closes.

Task 4 vol_forecast (deferred; needed for sizing and gating, not a candidate)
- Pair and sample: ETH/USDT and BTC/USDT (Work Order 1.4, once BTC/USDT 5m lands), each its own
  family, same cutoff and holdout, walk-forward fit 365 / validate 90.
- Target: log realized variance over the next 60 minutes (RV from 5m returns on the long history),
  origins 60 minutes apart. Baseline: trailing 1h/4h/24h log RV, hour-of-day and day-of-week effects,
  trailing 5-day average high-low range from closed daily bars. Test variable: log(last-60-min volume /
  median volume for the same hour over the prior 14 days). Report baseline out-of-sample R^2, gain from
  volume in every split, decile calibration table; save the forecast column. Primary: gain > 0 in every
  split.

Retired (do not resurrect): Task 1 in all versions and its gate; Task 5; Task 2 follow-ups; the
liquidity monitor as a gating tool (the 2026 liquidity table in section 4 is descriptive context, kept);
fill-rule reporting; Scenario A and A-stress; the re-costing tool; the 0.05% maker band; the 0.04%
filter threshold; fit-window-sign orientation for Task 3's two primary cells.

## 8. Mistake log (all are ways to fake a result)

1. pandas weekly resample anchors Sunday; Binance weeks anchor Monday: use W-MON.
2. Joining different-frequency series by row position collapses to the coarser spacing.
3. Fine return vs the coarse return of its own window gives about 1.0 correlation (same move twice).
4. Shifting by one coarse width re-enters the source window; capping lags is incomplete (contamination
   is diluted at every lag in between). Use event_anchored_lead_lag; tell-tale sign: best lag at the
   edge of the range.
5. Pairing coarse and fine series by row position when date ranges differ (about 84% of early coarse
   bars mis-paired): strict time alignment; keep a range-mismatch case in the self-tests.
6. Comparing fingerprints across timeframes on different spans: use equal spans.
7. A column named lag_minutes_after_close counted fine bars: name columns by unit.
8. Carried-forward OHLC of zero-trade minutes polluted resampled open/high/low: traded minutes only.
9. Walk-forward reference sign from the full sample contains the validate windows: orient by the
   pre-registered direction or the split's fit sign.
10. Stale last-trade prices in a thin pair make lag-1 effects strong and untradable.
11. Raw forward returns in a drifting market pass a threshold on drift alone: measure the excess over
    the unconditional mean at the same horizon.
12. Planning around a promotional fee (my own error): the planning fee is the default schedule.
13. Defaulting a long-only formula to two-sided/fit-window-sign orientation when the trading
    constraint itself already fixes the sign (my own error, on Task 3's two primary cells -- corrected
    in section 7): check whether "long-only" pins the direction before treating a cell as exploratory.

## 9. Status and outstanding orders

- Item 1 (selection-rule change): DONE, self-tested, documented (section 4). No further action.
- Data batch: DONE and internally verified (section 4: row counts, missing-bar counts and the
  128-hour BTC coincidence all reconcile). Loose end: request the first-settlement dates for the
  ETHUSDT and BTCUSDT funding series.
- Item 2 (pass-rule machinery): IN PROGRESS, NOT YET DELIVERED. Scope: --end-date guard with hard
  truncation, holdout lock, registry (empty start; ETH/FDUSD imported as history/void_pre_fix),
  by-year/leave-one-year-out machinery (120-day rule), freeze manifest, one-shot forward-test command
  (SE-scaling and minimum-sample rules from section 6). Also outstanding: confirmation of whether
  Task 3's walk-forward fit window rolls or expands (asked in Answers 1.6, not yet answered). When
  item 2's report arrives, check it in full against section 6 before trusting any verdict it produces.
- After item 2: S1 can start immediately (ETH/USDT 1d already on disk). S2 needs the funding
  first-settlement dates first. Then Task 3. The rule evaluator is built when a slope candidate first
  clears discovery and stability (needed immediately after, for the economic gate); Task 4 waits for
  any candidate.
- Handoff status: v2.2 was confirmed installed from the owner's manual uploads on 2026-09-20 (Section
  7 verbatim against my order, Section 3 sizes matched tree-02.txt, self-tests passed per
  terminal-05.txt). Answers 1.5 and 1.6 (S2 rank/tie convention, gate and stability windows, funding-
  interval handling, holdout scope, entry-time convention, full Task 3 spec, dose-response,
  unconditional mean, guard scope, forced exit) were relayed as messages and are NOT yet folded into a
  written handoff revision. Until a v2.3-equivalent handoff exists, this context document is
  authoritative over the handoff file for those items -- cross-check section 6 and 7 here rather than
  trusting HANDOFF_developer.md alone. The GitHub repo does not hold the real project files; the owner
  uploads copies by hand, so check internal evidence (version note, byte sizes) before trusting any
  uploaded file, not just its filename.
- RESOLVED 2026-09-23: ETH/FDUSD is retired as execution pair; ETH/USDT is confirmed execution pair;
  BTC/USDT is added as a full second research-and-execution pair. See Work Order 1.4 below.
- Repository consolidation (verified 2026-09-23): the new repo (see REPOSITORY note above) matches the
  structure the developer described. context/STATUS.md (read this first every session) confirmed the
  same item-1/data-batch/item-2 status as message-05, with no discrepancy. docs/work-orders/1.3.md and
  docs/handoffs/v2.2.md, as migrated, are byte-for-byte the same content I already reviewed — terms
  specific to Answers 1.5/1.6 (mid-rank, 8h-aligned, end-of-sample exit, the legacy-rule name) are
  absent from both, confirming no written handoff revision folding those in exists yet; this notes file
  remains authoritative over the repo's handoff file for those items until one is written. File naming
  going forward is settled -- see the top of this document.
- Authority structure: RESOLVED 2026-09-23. The owner confirmed the three-way split directly (not
  just via the developer's summary): I decide research design outright; the developer owns ordinary
  code/architecture decisions; the owner signs off on objectives, strategy principles, project-level
  architecture, risk/capital exposure and direction changes, and has final say on any disagreement.
  Recorded in section 1. The two docs/architecture files (idea-01-proposal.md, idea-02-ratification.md)
  remain useful background on why the consolidation happened and confirm the repo is intentionally
  public, but the specific split itself came from the owner directly in conversation, not from those
  documents verbatim.
- Work Order 1.4 (pair expansion, issued and owner-approved 2026-09-23): ETH/USDT and BTC/USDT become
  the two live pairs; ETH/FDUSD retired from execution (historical reference only). Outstanding before
  BTC/USDT can run the full pipeline: BTC/USDT 5m and 15m data (Task 3 needs it, currently only has
  1h/1d), and the ETH/USDT-vs-BTC/USDT realized-volatility comparison (to check section 3's break-even
  table). Also outstanding: fold pair-qualified family naming (section 6) into item 2's registry schema
  while it's still being built. S1 and S2 can run on BTC/USDT as soon as item 2 lands, since their data
  (1d, funding) already exists for both pairs; Task 3 and Task 4 on BTC/USDT wait for the 5m/15m pull.

## 10. Strategic assessment (2026-09-23)

- Nothing to compound yet: no tradable edge has been found. Lead-lag is dead; the passive baseline is
  moot under symmetric fees.
- Under 0.10%/0.10% the fast-small route is closed. Task 3 is the one intraday class that could still
  work (rare large shocks) and has enough events to return a decisive "dead" if it does not.
- Slow signals (S1, S2) have limited power: about 8-9 years of daily data can only prove effects near a
  Sharpe of 0.6 or better, so expect "inconclusive" for weaker ones. That is a data-length limit, not a
  failure of the design.
- Honest expectation: a validated slow or medium-horizon strategy, if one exists, plausibly delivers
  something like 20-60% a year with double-digit drawdowns (my judgment, not a forecast). The owner's
  1%/week target sits at the top of that range. Odds that at least one candidate survives the holdout:
  roughly even; odds that it also gives the fast compounding wanted: well under one in four.
- Execution quality: the liquidity gap (ETH/FDUSD at a few percent of ETH/USDT's activity all year)
  is why ETH/FDUSD is now retired from execution (Work Order 1.4) rather than just a reason to favor
  the alternative -- the owner acted on it directly.
- Doubling the pairs (ETH/USDT + BTC/USDT, Work Order 1.4) roughly doubles the number of independent
  shots at finding a validated candidate, treating the two as semi-independent given ETH and BTC are
  correlated but not identical. It does NOT improve any single candidate's odds -- a formula that's
  dead on one pair is not more likely to be alive on the other because we're now looking at both.
- Process note: item 1 and the full data batch landed clean, with every number reconciling on
  independent re-derivation, and the missing-hours result turned out to be an exchange-wide pattern
  rather than an ETH-specific data problem -- a reasonable positive signal on data quality generally,
  though it says nothing yet about whether any signal exists.
- Fallback if all candidates die: volatility-managed exposure (Task 4 forecast) to improve consistency,
  and further exogenous data (open interest, long/short ratios) once the pipeline is proven.
- FDUSD, if kept as the cash leg, briefly traded below $0.90 in April 2025; size accordingly.

## 11. First actions in the new chat

1. Read the developer's latest message; check it against sections 6-9 and recompute its numbers,
   including any row counts, missing-data figures, or Holm p-values it reports, per pair where two
   pairs are now in play.
2. If item 2's delivery report has arrived, this is the highest-priority check: verify the guard,
   holdout lock, registry semantics (including pair-qualified family names), by-year machinery, and
   forward-test command against section 6 in full before treating anything it produces as trustworthy.
3. Check whether Work Order 1.4's outstanding items have landed: BTC/USDT 5m/15m data, and the
   ETH/USDT-vs-BTC/USDT volatility comparison (section 4/9).
4. Confirm which version of the handoff, or which messages, the developer's understanding rests on. As
   of 2026-09-23 no handoff revision folding in Answers 1.5/1.6 or Work Order 1.4 exists in the repo yet
   (section 9); treat this notes file as authoritative for those items until one is written.
5. Interpret S1 and S2 results first, on whichever pair(s) have working data (they can start soonest),
   then Task 3.