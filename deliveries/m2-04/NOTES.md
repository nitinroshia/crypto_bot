# Mathematician notes

This file IS `context/mathematician/NOTES.md` in the project repo. The owner attaches it to a fresh mathematician chat; there is
no separate context document. Version by the Snapshot line, not by filename. When this changes, the copy in the repo is
overwritten (same path) and git history carries the diff. Only mathematicians edit this file (PROTOCOL section 3).

Snapshot: 2026-10-25 (revision 4), written by M2 (second mathematician) from M1's handoff (`docs/handoffs/M1-handoff.md`,
2026-10-19), the documents it lists, M2's own recomputation of the S1 report, Work Order 1.6 and the S2 report, the owner's roadmap of
2026-10-20 (section 10; it overrides the "Next" lines of the handoff) and D2's message-22. It replaces revision 3 (2026-10-23),
which never reached main. Supersedes the 2026-09-23 snapshot and every earlier context file.

STATE IN ONE PARAGRAPH. The research pipeline is built and verified on the owner's machine (cutoff guard, holdout lock, registry
with voiding, by-year / leave-one-year-out, amended stability statistic, economic gate, S1 and S2 formulas, read-only report
generators). S1 (daily trend) and S2 (funding extreme) are both CLOSED, not advanced, on both pairs (section 5); nothing is frozen,
nothing was forward-tested, the holdout is untouched, and the live registry has 26 lines (S1 lines 15-20, S2 lines 21-26). M2 accepted
the S2 report on 2026-10-25 and D2 starts Task 3 (shock_response, both pairs) under Work Order 1.7 (`docs/work-orders/1.7.md` and its
reference script). Next: M2 recomputes the Task 3 report; then the owner's roadmap (section 10): expansion to other timeframes and
markets only after Task 3 is reported, proposed as a short work order.

REPOSITORY: public, https://github.com/nitinroshia/crypto_bot (main). To read a file use
https://raw.githubusercontent.com/nitinroshia/crypto_bot/refs/heads/main/<path> . GitHub /tree/ directory pages refuse automated
fetching: fetch a known file path, or ask for the path.

FILES AND NAMING
- Work orders (mathematician -> developer): `docs/work-orders/`, continuing at 1.8 (1.7 is the latest; its reference script is
  `docs/work-orders/1.7-task3_reference.py`).
- Messages: `docs/correspondence/`. First line: `From: <ID> | To: <ID> | Re: <subject> | Date: <yyyy-mm-dd>`. Names are free-form
  (`answer-<topic>`, `message-NN`) where the numbering is unclear. A message the owner forwards carries a version label (v21, ...).
- Deliveries: `deliveries/<n>/` with `apply.sh` (PROTOCOL section 4). M2 uses `deliveries/m2-NN/` (m2-01 first) so the numbers
  never collide with the developers'.
- Handoffs: `docs/handoffs/<ID>-handoff.md`. Reports: `docs/reports/`. History and sandbox records: `docs/history/`.
- Developers' files (`context/developer/NOTES.md`, `context/STATUS.md`) are never edited by a mathematician.
- Stale terms. If a report or an old message mentions Scenario A, A-stress, the maker-candidate band, the 0.04% filter,
  "largest |beta| among significant lags" as the live default (it survives only as
  `select="legacy_max_abs_effect_among_significant"`), fit-window-sign orientation for Task 3's two primary cells, walk-forward
  validate windows for the S1/S2 gate or stability check or for Task 3's stability check, the per-block HAC/Stouffer stability test, the opposite-block veto,
  `combined_z > 3`, Task 1 or Task 5: all of them are retired or superseded.

## 1. Role and working contract

- I am M2, the math designer (senior quant statistician). Developers (D2 now) share no memory with me; nobody relies on anybody's
  chat. The owner is the bridge, not a message router.
- The three hard limits are the owner's and are not negotiable (PROTOCOL section 1).
  (1) NO MONEY: never propose, require or nudge toward anything that costs money (tools, subscriptions, paid agents, data feeds,
  servers, API plans) until the project has earned money. If work is blocked for lack of something paid, write
  `BLOCKED: <what is missing>` and stop; the owner decides whether to raise it. Free tools and what the owner already has are fine.
  (2) THE LOOP: I give the owner whole files plus one runner script per delivery (`deliveries/<n>/apply.sh`: starts with `set -e`,
  compatible with macOS bash 3.2, no placeholders; prints the SHA-256 of every file and stops on a mismatch; copies the files into
  place inside the repo; runs the relevant self-test; only if everything passed git-adds exactly those paths, commits, pushes and
  prints PASS and the commit hash; on any failure prints FAIL and commits nothing). The owner runs it and pushes; I read what was
  pushed. Never patches, diffs or pasted code. Every delivery ends with one sentence: what changed, the one command to run, what
  PASS looks like.
  (3) AGENTS TALK ONLY THROUGH FILES IN THE REPO (mathematician to developer, developer to developer, mathematician to
  mathematician).
- Agent IDs: M0/D0 earlier sessions; M1 (ended 2026-10-19); D1 (completed Work Order 1.5); M2 (me); D2 (Work Order 1.6).
- "Verified" means output from the owner's machine says so, pasted or committed. Anything run only in an agent's sandbox
  (including M2's own simulations and recomputations) is labelled "sandbox only". Self-tests and exploratory runs never write to
  the live registry.
- Same problem twice: stop and write down what is blocking, in `docs/correspondence/`. When a conversation gets long or confused:
  write the handoff file and say so; do not push on.
- Developers' sandboxes have no route to Binance: data work runs on the owner's machine, batched into single owner runs with
  copy-pasteable commands (no placeholders).
- Developer's hard rules: never assume anything that touches the financial model; where a spec allows two readings, run both and
  label them; interpretations go in docstrings and reports. So my orders must be unambiguous: exact definitions, family size,
  primary cell, direction, and for any rule exactly what it may know at decision time. If a developer session seems to have lost
  track of something specific, say so directly; do not assume it was intentional (owner's instruction).
- Owner's goal: consistent results and fast compounding; a small consistent gain compounded quickly is fine. I never promise
  results, say plainly when nothing has been found, and keep notes to the owner short (results, not derivations).
- Stance: aggressive with ideas, strict with validation. No martingale, grids, averaging down or leverage; nothing that buys
  smoothness by selling tail risk. Failed ideas are killed, not retuned.
- Check every developer report: recompute row counts, split counts, missing-data arithmetic, Holm p-values, block counts and
  compounded block returns before trusting any figure (recipes in section 11).
- Reply format: a short plain-language note to the owner, then "For the developer (forward as is) - v<n>" only if something must go
  to the developer. Last forward-as-is message: v21 (to D2: S2 accepted, start Work Order 1.7); the next is v22. Orders state: predictor (exact computation,
  availability time), target, timeframes, lags, gut-check, plausible effect scale, family size, primary cell, direction.
- Mandatory gut-checks for every formula and rule: (a) can the same raw price data appear on both sides? (b) does a shared latent
  state (volatility clustering, seasonality, stale last-trade prices, market drift) make the comparison trivially significant?
  (c) is every input of a trading rule known at decision time, INCLUDING whether the data exist (mistake 19)? (d) has the test been
  null-calibrated on synthetic data with the real predictor's persistence and the target's overlap, and power-checked, BEFORE it is
  pre-registered (mistakes 14, 15, 18)?
- Plausibility bands (correlation units): same-asset autocorrelation 0.004-0.011; credible new effect 0.01-0.05 (S2: -0.03 to
  -0.08); 0.5+ presume an artifact (S2: above 0.2 in absolute value means a bug). Beta is not on this scale; ask for correlation too.
- Long-only formulas: check whether the trading constraint itself already fixes the pre-registered direction before defaulting to
  two-sided or fit-window-sign orientation (mistake 13).
- Authority (owner-confirmed 2026-09-23): I decide research design outright (formulas, thresholds, sample splits, gates, ambiguity
  rulings). Ordinary code and architecture decisions are the developer's. Project-level decisions (objectives, strategy principles,
  system architecture such as which pairs, risk or capital exposure, a change of direction) need the owner's sign-off; on a genuine
  disagreement the owner has the final say. The owner is asked only for decisions that are the owner's.
- Scratch lives under `<repo>/temp/` (gitignored); nothing is written outside the project root. `temp/secret_keys.txt` exists in the
  owner's folder: it is never opened, copied or backed up by anyone, and runner scripts git-add exact paths only.
- I am not a tax advisor and say so whenever tax rules come up; the owner confirms every tax rule with a tax professional
  (section 10).
- The owner: not a coder; runs commands on a Mac; time is the scarce resource; was highly dissatisfied with past efficiency (8 to
  10 days were lost to code pasted through chat). Wants short plain-language notes, then one forward-as-is block labelled with a
  version number.

## 2. Scoreboard (out-of-sample, net of costs)

- Consistency: at least 70% of 4-week windows positive, worst window no worse than -3%, max drawdown at most 10%, still
  profitable after removing the best 5% of trades.
- Compounding: geometric growth per week with days-to-double. Target at least 1%/week, but under the 0.10%/0.10% fee schedule that
  is a stretch; the realistic centre is lower. Say so plainly.
- Robustness: same verdict under the stress cost (section 3), with parameters +-20%, and one bar late.

## 3. Economics (owner's instruction, final)

- Planning fee: 0.10% maker and 0.10% taker on every fill (Binance default). Promotions are ignored and never modelled, including
  the zero maker fee once shown on ETH/FDUSD (mistake 12).
- Slippage allowance: 0.02% per side (an assumption; replace with a measured value in dry-run). Base: 0.12% per side, round trip
  0.24%. Stress: fee 0.12% + slippage 0.03% = 0.15% per side, round trip 0.30%.
- Execution: taker at the next bar's open; no fill-probability modelling. Freqtrade has no slippage setting, so strategy-layer
  backtests pass the per-side figure as the fee: `--fee 0.0012` (base) and `--fee 0.0015` (stress). `scripts/backtest.sh` selects
  the case with COST_CASE (default base) and caps the default TIMERANGE at 20250831 (the holdout lock covers strategy backtests).
- Materiality M = 0.35% gross per round trip (stress cost 0.30% + 0.05% margin), measured as the EXCESS over the unconditional
  mean forward return at the same horizon, so drift cannot pass on its own. M applies to event-type effects (Task 3); it does not
  apply to the S1/S2 economic gate, which requires net-positive strategy return (section 6).
- Break-even hit rate for symmetric payoffs: p* = (1 + c / E|r|) / 2, with c the round-trip cost and E|r| the mean absolute return
  over the trade horizon. The old table (15m 90%, 1h 70%, 4h 60%, 1d 54%; ETH at 70% volatility, Gaussian) is SUPERSEDED by the
  empirical figures from the owner's discovery data (M1 handoff; M2 did not recompute them, but they are internally consistent: the
  implied E|r| scales with volatility and with the square root of time):
  - 15m: BTC base 101.7%, stress 114.7%; ETH stress 100.7% (base about 90.6% by mean, M2 arithmetic); median-based figures are
    worse (ETH base 117%). Above 100% means no hit rate can pay for the costs. The extremes are real market history (Black Thursday
    2020-03-12, 2021-05-19, China 2017-09), not data errors.
  - 1h by mean (base/stress): ETH 70%/75%, BTC 76%/83%. Very demanding.
  - Implied mean absolute returns (M2 arithmetic): 15m BTC 0.232%, ETH 0.296%; 1h ETH 0.60%, BTC 0.46%. 4h and 1d were not
    re-measured.
  - Annualised volatility, discovery sample, sqrt(365): ETH 90.1%, BTC 70.1%.
- Consequence: the small-gain high-frequency route is closed. The feasible domain is hours-to-days horizons, rare large
  conditional moves, and information beyond price (funding).

## 4. Data and infrastructure

- Pairs: ETH/USDT and BTC/USDT are the project's two live pairs, for research AND execution (Work Order 1.4, 2026-09-23). Each
  runs the complete pipeline in its own right under pair-qualified family names (`S1-ETHUSDT`, `S2-BTCUSDT`, `Task3-ETHUSDT`, ...).
  ETH/FDUSD is retired from execution (2.0-4.5% of ETH/USDT's activity in 2026); its results are historical reference only.
- Cutoff: discovery and walk-forward use data up to and including 2025-08-31, the same for both pairs (section 6). Everything after
  is the locked holdout.
- Stores (owner's machine, as of the 2026-09 pulls): ETH_USDT and BTC_USDT 1d, 1h, 5m (BTC 15m derived from 5m by the validated
  resampling rule); funding for both. ETH/USDT also has 1m from 2026-01-30 (holdout period: descriptive reads only).
  - 1d: ETH 3,321 rows 2017-08-17 to 2026-09-19 (2,937 discovery rows to 2025-08-31); BTC 3,322 rows to 2026-09-20; no missing days.
  - 1h: 128 missing hours, identical in both pairs (an exchange-wide gap pattern, not pair-specific).
  - 5m: ETH 2017-08-17 04:00 to 2026-09-21 06:00 has 955,046 rows against 956,761 for a gap-free series; 1,715 missing bars,
    1,536 of them inside the 128 missing hours (12 per hour) and 179 scattered; the missing bars coincide across the pairs. The old
    132-versus-128 discrepancy: 4 leading hours before the series start plus 128 interior gaps.
  - Gaps are masked, never dropped; an S1/S2 origin whose entry or exit bar falls in a gap is excluded and counted, never imputed.
  - Funding (ETHUSDT and BTCUSDT USD-M perpetuals, REST): a constant 8h settlement interval since each series' first settlement, no
    interval change observed. First settlements: ETH 2019-11-27 08:00 UTC, BTC 2019-09-10 08:00 UTC (confirmed by D2's delivery 8;
    the example timestamps of Work Order 1.6 assumed 00:00). One observation per symbol is masked: the first (its preceding span is
    unknown). Tie share (fraction at the modal value) up to the cutoff: 39.6% ETH, 40.1% BTC (D2: 0.3963 and 0.4005).
- Raw columns: date, open, high, low, close, volume, quote_volume, n_trades, taker_buy_base, taker_buy_quote. Freqtrade's data
  dir holds OHLCV only (on purpose).
- Resampling rule (validated, zero mismatches against native on every timeframe): coarse bars from TRADED minutes only (open =
  first traded minute, high/low = extremes of traded minutes, close = last traded; an empty bin carries the previous close). Weeks
  anchor Monday.
- Research layer (Python 3.12.7 venv; repo `~/apps/crypto_bot`, code in `user_data/analysis/`): `research_cli.py`, `leadlag.py`,
  `walkforward.py`, `stats_fingerprint.py`, `run_fingerprint.py`, `resample.py`, `fetch_klines.py`, `funding.py`, `databundle.py`,
  `multitest.py` (Holm/Bonferroni), `costs.py`, `nonstationarity.py`, the cutoff loader and holdout lock, the registry
  (`user_data/analysis/results/registry.jsonl`, written only with `--commit-to-registry`), the S1 formula and the read-only report
  generator `s1_report.py` (refuses to run unless every figure it recomputes reproduces the registry), `selftest_all.sh`,
  `scripts/diag_state.sh`, `scripts/backtest.sh`. Strategy layer: freqtrade in Docker; `MomentumTrailing` is a naive placeholder.
  Cardinal sin: testing a math idea by editing a strategy and backtesting it.
- Lag-selection rule (exploratory lag scans, Task 3): `leadlag.summarize_best_lag` uses min-p (smallest p, i.e. largest |HAC t|),
  no "significant" pre-filter, never the largest |beta| or |correlation|; ties from p underflowing to 0.0 are broken by the larger
  |HAC t| (or |Fisher z|), then the smaller lag. The pre-1.2 rule survives only as
  `select="legacy_max_abs_effect_among_significant"` to reproduce frozen ETH/FDUSD numbers; no new candidate may use it.
  Open: confirm `research_cli.evaluate_fixed_lag` (the old live walk-forward verdict) is removed or fully superseded (unverified).

## 5. Results so far

S1 trend_slope (daily, both pairs): CLOSED, NOT ADVANCED. Accepted by M1 as the record in
`docs/correspondence/answer-to-message-19.md`; report `docs/reports/s1-report-step6.md` (generated 2026-10-19 by `s1_report.py` at
commit 4487f1e); the pre-fix S1 records were voided by commit ac63ff2; live registry records: ETH lines 15-17, BTC lines 18-20.
M2 recomputed every figure below from the report (sandbox arithmetic): all reproduce.

                                  ETH_USDT                       BTC_USDT
  origins (both pairs)            2,772: 2018-01-24 .. 2025-08-26; 30 full 90-day blocks + a 72-origin partial block
  primary cell L=40, h=5          slope 0.000715, raw p 0.1282   slope 0.001009, raw p 0.01451
  Holm within the 10 cells        0.769                          0.145
  MDE (slope units)               0.00157                        0.00115  (above the observed slopes)
  stability T / p_stab            0.708 / 0.2304                 1.696 / 0.0555
  blocks with s_b > 0             17 of 30                       15 of 30 (blocks 5 and 11 supply 7.5 of the 9.3 total)
  gate, pooled net (stress)       4.92  (buy-and-hold 3.13)      34.55  (buy-and-hold 8.51)
  gate, non-negative full blocks  12 of 30 = 40% (B&H 18)        15 of 30 = 50% (B&H 13); the gate needs 21 of 30
  gate, round trips / hit rate    74 / 36.5%                     77 / 42.9%
  any year-driven                 no                             no
  verdict                         not advanced                   not advanced

How to read it, without retuning anything: "not shown", not "shown absent" (the MDE is above the observed slopes). BTC's raw p
of 0.0145 does not survive the 10-cell family. BTC's large pooled outperformance of buy-and-hold comes mainly from sitting out the
2018, mid-2021 and 2022 drawdowns, and its stability evidence is concentrated. BTC's p_stab (0.0555) is within Monte Carlo error of
0.05 (SE about 0.005 at R = 2000); the stored seed 12345 stands and nothing else would change the verdict. No freeze, no forward
test, holdout untouched. M2's sandbox check of S1's HAC settings (10 lags for the 5-day overlap) gave a 5.0% false-positive rate
at nominal 5%, so S1's p-values are not inflated.

S2 funding_extreme (both pairs): CLOSED, NOT ADVANCED. Report `docs/reports/s2-report-step3.md` (D2's message-22; generated 2026-10-25 07:14Z
by the read-only `s2_report.py` at commit 294afb8; pre-tax); live registry lines 21-23 (ETH) and 24-26 (BTC), written 2026-10-25 06:44Z
by D2's delivery 9; trade lists in `docs/reports/s2-trades/`. M2 recomputed every figure of the report on 2026-10-25 (sandbox
arithmetic): all reproduce, and M2 accepted it as the record.

                                  ETH_USDT                           BTC_USDT
  first settlement                2019-11-27 08:00 UTC               2019-09-10 08:00 UTC
  origins nominal / used          6,034 / 6,031                      6,268 / 6,265 (3 gap-excluded each: one entry bar, one 24h exit, one 72h exit)
  first / last origin             2020-02-25 16:00 / 2025-08-28 16:00   2019-12-09 16:00 / 2025-08-28 16:00
  full blocks (+ partial)         22 (+94; one block has 267)        23 (+58; one block has 267)
  primary 72h: slope / corr       -0.000662 / -0.0026                -0.00540 / -0.0287
  HAC SE (36 lags) / MDE          0.00725 / 0.0180                   0.00539 / 0.0134
  one-sided p / Holm within 2     0.4637 / 0.610                     0.158 / 0.158
  24h cell p (12 lags) / Holm     0.305 / 0.610                      0.0316 / 0.0633
  stability T / p_stab            0.271 / 0.3843                     1.141 / 0.0994
  p_stab, Holm across candidates  0.461 (raw must be < 0.025)        0.111
  blocks with s_b > 0             12 of 22                           14 of 23
  gate pooled net (stress)        0.432 (buy-and-hold 16.72)         0.262 (buy-and-hold 13.56)
  non-negative full blocks        14 of 22, needs 16 (B&H 13)        11 of 23, needs 17 (B&H 16)
  round trips / hit rate          518 / 49.4%                        510 / 42.9%
  any year-driven                 yes (pooled slope near zero)       no
  verdict                         not advanced                       not advanced

How to read it, without retuning anything: there is no discovery signal (p 0.46 and 0.16; the BTC 24h cell, p 0.032, Holm 0.063, does not
survive), stability fails (BTC's raw 0.0994 is not even below 0.05 before Holm), and the long/flat rank rule churns (about one round trip
every four days: 518 and 510 round trips at 0.30% cut the final wealth multiple to about a fifth of its gross value) and loses to
buy-and-hold on both pairs. ETH's year-driven flag only reflects a pooled slope near zero (dropping 2020, 2022 or 2023 flips its sign).
Calibration (D2, production code, 1,000 paths, persistent null): the 72h cell with 36 lags rejects 7.8% (band 8%), the 24h cell with 12
lags 6.7%; with the superseded lags 8.5% and 10.5% (information only). M2's own 4,000-path sandbox run puts the 36-lag test near 6%: the
ruled lags help but HAC with a persistent predictor stays mildly lenient; nothing in S2 depends on it. The superseded-lag p-values stay in
the report as a labelled sensitivity column (ETH 0.461, BTC 0.137, BTC 24h 0.0267). No freeze, no forward test.

ETH/FDUSD (historical reference only; no new formula work): the open-price mismatch was fully explained by flat minutes (the
traded-minutes rule gives zero mismatch); event-anchored lead-lag (post-break, family of 66) is DEAD (best raw p 0.0019, Holm 0.068
within its own family, 0.124 across 66), computed under the pre-1.2 selection rule and kept reproducible through the legacy selector
(never recompute under min-p and compare); the Task 2 passive-fill baseline was negative in all 36 cells and is moot under
symmetric fees; the pair's activity fell after the 2026-01-29 fee change.

## 6. Current rules (settled unless data contradict)

Conventions
- Bars are left-labelled and usable only after they close; the earliest action is the next bar's open. A close-of-day-t predictor
  enters at the open of day t+1, never at t's own close.
- Holm is the gate (Bonferroni for reference). Within a family: the 10 S1 cells, the 2 S2 cells, the 48 Task 3 cells (per pair).
  Every result states family size and adjusted p; HAC or clustered SEs; correlation beside beta; MDE from the standard error, never
  post-hoc power. Cells are tagged pre-registered or exploratory.
- ACROSS candidates (R1, Work Order 1.5): at every step that uses an across-candidate Holm (stability, holdout), the family is every
  non-void candidate that has a record at that step, per pair, whatever its outcome and whether or not it later advanced; a failed
  candidate stays in every later family. Records are keyed by (family, step); `holm_at_step` uses each live family's latest record
  AT THAT STEP, not its latest record overall. The discovery step uses each candidate's primary-cell raw p (as in the S1 report).
  `cumulative_count` = distinct non-void families (also report the number of cells). Consequence: with S1 on record, an S2
  candidate needs a raw p_stab below 0.025 to survive the two-candidate Holm. The discovery-step across-candidate Holm uses raw
  primary-cell p's and is NOT the discovery pass criterion (the own-family Holm is): after S2, S1-BTCUSDT shows 0.029 there while its own
  family's Holm(10) is 0.145; S1 stays not advanced.
- HAC bandwidth with a persistent predictor: at least 4 x the overlap length (mistake 18); a new bandwidth is pre-registered only
  after a null calibration with a synthetic predictor of the real persistence. Even at 4 x the overlap the HAC test stays mildly lenient
  with a persistent predictor (M2 sandbox about 6% at 36 lags, D2's production check 7.8%, nominal 5%): for a new persistent-predictor
  candidate prefer a shift/permutation null for the discovery p-value, or accept an 8% band and say so.
- Registry (`registry.jsonl`, append-only, one record per line; per candidate and step: discovery, stability, economic_gate; later
  frozen and holdout). `history`, `void_pre_fix` and `descriptive_access` records, and records targeted by a void, are excluded from
  Holm and from the cumulative count. Voiding (A1): `void_family(family, pair, reason)` appends a `void_pre_fix` marker; a family
  is live unless its latest record is `void_pre_fix`; every record of that (family, pair) written before its latest marker is void;
  it refuses families with a live frozen/holdout_consumed record; original lines are never edited or deleted. Live writes need the
  explicit `commit_to_registry` flag; the default registry is scratch; self-tests use a temp registry. Earlier ETH/FDUSD runs are
  `history` / `void_pre_fix`. Family names are always pair-qualified.

Sample design (ETH/USDT and BTC/USDT alike)
- Discovery and walk-forward use data up to and including 2025-08-31, the same cutoff for both pairs (ETH and BTC returns are
  correlated, so different cutoffs would let one pair's holdout do work inside the other's discovery). Data after the cutoff is a
  LOCKED HOLDOUT, readable only by the forward-test command, once per candidate (Holm across the candidates that reach it, per
  pair). The manifest records the data end date used.
- Cutoff mechanics: 2025-08-31 23:59:59 UTC inclusive (last usable bars: 1d labelled 2025-08-31, 1h labelled 23:00, 15m labelled
  23:45, 5m labelled 23:55; funding settlements up to 16:00). An origin's entry time is the open of its entry bar. Discovery keeps
  an origin only if its entry is at or after the sample start and its whole target window ends at or before the cutoff; otherwise
  it is dropped (no truncation). Holdout origins have entry time >= 2025-09-01 00:00 UTC; their predictors may look back into
  discovery data (A2: the forward-test hooks receive the full history and evaluate only holdout origins, decided by entry time).
  Origins straddling the cutoff belong to neither. The same purge applies at every fit-validate boundary. The discovery loader
  hard-truncates at the cutoff BEFORE any computation (it never returns a post-cutoff row); only the forward-test command loads the
  full series.
- Holdout exposure (disclosed, not a violation): aggregate 2026 ETH/FDUSD statistics (fingerprint, the dead lead-lag result, the Task 2
  baseline) fall inside the holdout window; none relates an ETH/USDT, BTC/USDT or funding predictor to a return. Log this note on every
  holdout test. Outside the forward-test command no statistic that relates a predictor to a return, for any pair or funding in any
  combination, may be computed on data after the cutoff. Purely descriptive reads (counts, spans, gaps, shares, funding tie share,
  interval checks) may use the full range and are logged "descriptive, no returns computed". Live or dry-run freqtrade exports are
  truncated at the cutoff.

Origin sets (one common set per family and pair: the intersection, by entry time, of every cell's usable origins)
- S1: the first usable origin is the 161st daily close (max(L,30) closes behind), 2018-01-24 if the 1d file starts 2017-08-17; the
  last is 2025-08-26 (h=5's last complete window): 2,772 origins = 30 full 90-day blocks + a 72-origin partial block, both pairs.
- S2 (R2, Work Order 1.5): count VALID observations; the masked first settlement is not an observation; the rank needs 270 valid
  previous observations, so the first usable origin is slot 272 counting the masked first settlement as slot 1, i.e. first
  settlement + 271 x 8h (the old "271st settlement" is wrong). The first settlements are at 08:00 UTC (D2, delivery 8), so the first
  origins are BTC 2019-12-09 16:00 and ETH 2020-02-25 16:00 (a 00:00 first settlement would give 08:00 and one more origin). Last
  origin: the last settlement s with s + 1h + 72h <= the last usable 1h bar (label 2025-08-31 23:00), i.e. 2025-08-28 16:00, both
  pairs. Origins before gap exclusions: BTC 6,268 = 23 full blocks + 58; ETH 6,034 = 22 + 94; 270 origins per full block. Gap
  exclusions found by D2: 3 origins per pair (one entry bar, one 24h exit, one 72h exit, all in one block, which has 267 origins). If
  any of the 270 window observations is masked the origin is excluded and counted. First holdout origin: the settlement at
  2025-09-01 00:00 UTC.
- Report first and last origin dates, count, excluded count and block counts per pair; BTC's need not match ETH's.

Pipeline for a candidate (S1 and S2 follow it end to end; Task 3 differs where section 7 says)
1. Discovery (data <= 2025-08-31): pre-registered cells stand on their own p-value (own-family Holm); exploratory cells only
   nominate.
2. Stability (a stability check, NOT independent evidence). Definition (Work Order 1.5 section 3 with answer-04):
   - Blocks: B full non-overlapping blocks of 90 CALENDAR days tiled from the first origin of the common set; block b holds the
     origins whose entry time falls in [t0 + 90b days, t0 + 90(b+1) days); per-block index sets (a gap just leaves a block with
     fewer origins); the final partial block is never scored.
   - Block score c_b = d * sum over the block's origins of xt*yt, with xt and yt deviations from their means over the WHOLE common
     origin set (the partial block's origins included; no per-block intercept); y = forward return / sigma30 at the origin
     (past-only); d = +1 for S1 and -1 for S2, so that positive means "agrees with the pre-registered direction".
   - Null (R = 2000, seed stored). S1: stationary block bootstrap of the daily log returns (mean block 20 days; returns aligned to
     closes, r[j] = ln(C_j/C_{j-1}), r[0] = 0), predictor and target rebuilt with the production code at the same origin positions;
     a time-shift null is NOT valid for S1. S2: circular time-shift of the rank vector against the target vector over the whole common
     origin set, minimum shift 300 settlements.
   - T = sum(s_b)/sqrt(B), s_b = (c_b - mu_b)/sd_b with mu_b, sd_b from the replicates; p_stab = (1 + #{T_r >= T_obs}) / (R + 1).
     Pass: p_stab < 0.05, then Holm across candidates (R1). Stored: T, p_stab, R, seed, mean block length or minimum shift, B.
   - Acceptance of the production code on synthetic data (reduced 60 paths with R = 500; `--full` 200 paths with R = 1000): S1 null
     (Gaussian; t(3) + volatility clustering) false-pass <= 7%; S1 injected edge (pooled HAC t about 5) pass >= 70%, (about 11)
     pass >= 95%; S2 nulls <= 7%; S2 injected edge (correlation about -0.16) pass >= 80%. Ruling (answer-to-message-19): a false-pass
     row passes if the rate is <= 7% at 200 paths OR <= 7% in a confirmation run of >= 1,000 paths (200 paths carries +-1.6 points
     at 5%). Power rows are unchanged. If a band cannot be met, report to me; no one moves the bands.
   - Task 3's two primary cells: the event stability statistic of Work Order 1.7 section 2 (90-day blocks, studentised block
     t's combined as T = sum t_b / sqrt(B'), p_stab = 1 - Phi(T), no simulated null because events are non-overlapping and decided from
     past information only; sandbox false-pass 3.0-5.5%). The old walk-forward line is retired: there is nothing to fit when both
     directions are pre-registered.
   - Orientation of every current primary cell: S1 positive; S2 negative; Task 3's two primary cells positive; Task 4 volume
     coefficient positive. Fit-window-sign orientation applies only to genuinely exploratory cells with no pre-registered direction.
3. Economic gate (S1 and S2; M does not apply): the frozen pre-registered rule at STRESS cost on non-overlapping 90-day blocks tiled
   from the family's first origin (the same tiling as stability; the gate tiles the discovery rows through the last discovery bar, so
   its partial block runs to that bar). The rule starts flat at the segment start; cash returns 0; a block's return is the compounded
   net strategy return, costs charged only when the position changes (a position may carry across a block boundary at no cost). Pass:
   pooled net return > 0 over the whole discovery sample AND net return >= 0 in at least 70% of FULL blocks (S1: 21 of 30; S2: 16 of
   22 for ETH, 17 of 23 for BTC); the partial block is excluded from the count but included in the pooled figure. R4: ALSO report
   buy-and-hold on the same segment, blocks and stress cost (pooled return and share of non-negative blocks): a long/flat rule on a
   rising asset passes "pooled > 0" without skill, so this is how the figures are read. At the holdout the frozen rule must also be
   net-positive at stress cost. Orientation (normal approximation, M2): a 70% non-negative-block rate needs roughly an annual Sharpe
   near 1 at stress cost.
4. Freeze: timestamp, code commit, cell, direction, discovery estimate and dispersion in the manifest.
5. Holdout / forward test (the independent evidence): exactly the frozen primary cell, one-sided in the discovered direction, one
   look, then consumed. Minimum sample at test time: at least 45 days, at least 100 events or observations, SE no larger than half
   the claimed effect; if not met, wait (ask me if it needs more than 120 further days). SE_holdout = SE_discovery x
   sqrt(N_discovery / N_holdout), N the primary cell's origin count after the purge (state the formula in the docstring). Success:
   one-sided p < 0.05 and estimate at least as large as both M (event-type cells) and half the discovery estimate. Failure = dead, no
   retuning. Dry-run follows.
   - End-of-segment handling (all evaluator uses): every evaluation segment (a discovery block, the whole discovery sample, the
     holdout) starts flat and is forced to exit at its last close, charged as an exit cost and labelled "end-of-sample exit"; no
     holdout price ever enters a discovery-side computation through this mechanism. Mark-to-market with no exit cost is a labelled
     variant only, never the default.

Three-way classification for event-type primary cells: pass = one-sided p < 0.05 and excess >= M; dead = one-sided 95% upper bound
below M; otherwise inconclusive. If MDE exceeds M a null is inconclusive.

Non-stationarity rule: for every primary cell report a by-year table and leave-one-year-out estimates. Red flag: if dropping any
single year cuts the estimate by more than half or flips its sign, mark it year-driven; it does not advance without my review. Years
with fewer than 120 days of data are shown (with n and days covered) but not judged: they stay in the pooled estimate and are
excluded from leave-one-year-out and year-by-year sign statements.

Rule evaluator (built and verified): vectorised long/flat rule on closed bars, entry and exit at the next bar's open, fees per side
0.10% + slippage 0.02% (stress 0.12% + 0.03%), end-of-segment handling as in step 5, window-return mechanics as in step 3. Outputs:
trades, hit rate, mean gross and net per trade; per-block and pooled growth, max drawdown, share of non-negative blocks; by-year
table; benchmarks buy-and-hold and cash. Self-tests on synthetic data with known truth (a random walk must be net-negative after
costs; an injected drift must be recovered; a position spanning a block boundary is charged costs once).

## 7. Pre-registered tasks

Order: S1 and S2 are closed; Task 3 is next; Task 4 and anything new only if a candidate exists or the owner's roadmap (section 10) calls for it.

S2 funding_extreme (`S2-ETHUSDT` on ETH/USDT spot, `S2-BTCUSDT` on BTC/USDT spot; same code, own gate and freeze; 2 cells per pair)
STATUS: CLOSED, not advanced (2026-10-25; section 5). What follows remains the record of what was tested.
Governing documents: Work Order 1.6 and `docs/correspondence/answer-s2-rulings.md` (M2, forward v20 including v19), which overrides
the order where they differ. Stop point: after the S2 report is committed; no freeze, no forward test.
- Observations: the 8h-aligned settlements (00:00, 08:00, 16:00 UTC). An observation's rate is the sum of native rates settled in
  (s-8h, s] (the native rate while the interval is 8h); a window with a missing native settlement is masked and counted; the first
  settlement of each series is masked by construction.
- Predictor: rank_s = MID-RANK = (count of the 270 previous slots strictly below the current value + 0.5 x count exactly tied) / 270,
  current excluded; all 270 previous slots must be valid (R2). Strict-below and at-or-below ranks are labelled robustness columns on
  the primary cell only, never the primary statistic. Report the tie share (about 39.6% ETH, 40.1% BTC).
- Target: spot log return from the open of the 1h bar labelled s+1h to the open of the 1h bar labelled s+1h+H, H = 24h and 72h in
  clock time. An origin whose entry or exit 1h bar is missing is excluded and counted, not imputed.
- Test: OLS slope of forward return on rank over all origins of the common set (intercept kept); Newey-West HAC with 12 lags for 24h
  and 36 lags for 72h; direction NEGATIVE (higher funding, lower forward return); one-sided p; Holm within the 2 cells; primary 72h.
  The lags (4 x H/8h; if an interval other than 8h ever appears, 4 x ceil(H / shortest interval), moot at present) are AMENDED by M2
  on 2026-10-20 from 3 and 9 (the order's value, 1 x the overlap): in M2's null simulation (sandbox only;
  persistent funding rank, 8h grid, overlapping returns, about 6,000 origins) a nominal one-sided 5% test rejected 6.6-8.6% of null
  paths with 9 lags and 4.6-6.4% with 36 (the 24h cell: 8.1-8.6% with 3 lags, 6.5-7.0% with 12); record in
  `docs/history/m2-sandbox-calibration-2026-10-20.md`. Report slope, HAC SE, correlation, HAC t, one-sided p, Holm, Bonferroni and
  MDE = 2.486 x HAC SE. Descriptive, exploratory: mean forward return and its excess over the unconditional mean at the same horizon
  for rank <= 0.10 and rank >= 0.90, with counts.
- Stability: on the primary 72h cell only (one stability record per pair): y = 72h forward return / sigma30, sigma30 = sd of the
  target pair's last 30 daily log returns using only daily closes at or before the origin time (for the three settlements of a day,
  the previous day's close); d = -1; null = circular time-shift of the rank vector (section 6, step 2); R = 2000, minimum shift 300.
- By-year and leave-one-year-out on the 72h cell with the 120-day rule (BTC's 2019 has 23 days: shown, not judged).
- Economic gate: stress cost 0.15% per side. Pre-registered rule: long from the open of the 1h bar labelled s+1h while the latest
  rank <= 0.5, otherwise cash, re-evaluated at each settlement. The rule may use only what is known at s: it is cash exactly when
  rank_s is not valid (the current observation or any of the 270 previous slots masked); a missing 1h bar never changes the signal (a
  position change that falls on a missing bar executes at the next available bar's open, counted and reported); settlements after
  the last origin (2025-08-29 00:00 to 2025-08-31 16:00) are evaluated like any other; the segment starts flat at the first origin and
  is forced to exit at the last discovery bar's close ("end-of-sample exit"). Report trades, hit rate, exposure and buy-and-hold on
  the same segment (R4).
- Gut-check: the rate is known at s and the target starts one bar later. Funding reflects recent price moves, so the rank is related to
  PAST returns and possibly to future volatility: hence the past-only volatility scaling of the stability target and the slope with an
  intercept (drift removed). Plausible if real: correlation -0.03 to -0.08; above 0.2 in absolute value is a bug.
- Power (M2, sandbox only): the stability check passes about 20% of the time at a true correlation of -0.03, 60-80% at about -0.08 and
  about 99% at -0.16 (the acceptance edge), so a real but small effect usually returns "inconclusive": a data-length limit, not a defect.
- When either pair's S2 candidate freezes, report the other pair's same-cell point estimate, sign and discovery p as a labelled
  context column (informative, not gating). "Replicate the sign on BTC, report only" is retired.

S1 trend_slope (1d; family of 10 per pair; CLOSED, not advanced; section 5)
- x = ln(C_t / C_{t-L}) / sigma30, sigma30 = std of the last 30 daily log returns ending at t, L in {10, 20, 40, 80, 160}. Target
  ln(C_{t+h} / C_t), h in {1, 5}; entry at the open of day t+1; all daily origins; Newey-West HAC 5 lags (h = 1) and 10 (h = 5);
  direction positive. Primary L = 40, h = 5; the other nine cells are exploratory; Holm within the 10. Rule: long from the next
  open if x > 0 at the day's close, otherwise cash.
- Definitions, cells, rule and thresholds are not changed. Any future trend variant is a NEW candidate: pre-registered before anyone
  looks at its results, with its own family name, and counted in every across-candidate family from then on.

Task 3 shock_response (`Task3-ETHUSDT`, `Task3-BTCUSDT`; 48 cells per pair = 2 timeframes x 12 horizons x 2 sides; 5m primary, 15m
secondary)
Governing document: Work Order 1.7 (M2, 2026-10-23) with `docs/work-orders/1.7-task3_reference.py`; M2 accepted the S2 report on
2026-10-25 and D2 starts it now. Stop point: after the report; no freeze, no forward test. Summary:
- Bars: both timeframes come from the 5m file (15m derived by the validated rule, for both pairs); gaps are masked; a return needs two
  consecutive present bars.
- Event: a closed bar with |z| >= 3, z = r_j / sd of the previous 288 (5m) or 96 (15m) returns (ddof 1, the bar excluded, all
  unmasked). The decision is at the close, the entry at the next open.
- De-clustering: one shared clock per timeframe and pair: keep the first event, ignore event bars until 13 bars later, both sides share
  the clock. The clock uses only past information: an event with an incomplete target window stays on the clock and is dropped from the
  statistics (mistake 19).
- Target: R_k = ln(C_(j+k) / O_(j+1)), k = 1..12, separately after down-shocks and up-shocks. mu_k = the mean of R_k over ALL origins
  of that timeframe (event bars included), a constant; excess = R_k - mu_k.
- Test: the mean excess per cell with the day-clustered SE (the naive SE as a labelled column), normal p. Primary cells: (5m, k = 6,
  down) and (5m, k = 6, up), both pre-registered one-sided POSITIVE (a reversal bet after down-shocks, a continuation bet after
  up-shocks; spot is long-only either way: mistake 13). The other 46 cells: two-sided, descriptive, they cannot pass any gate. Holm over
  the 48 per pair.
- Classification of the primary cells (M = 0.35% on the excess): pass = Holm-adjusted p < 0.05 and excess >= M; dead = one-sided 95%
  upper bound < M and MDE <= M; otherwise inconclusive.
- Dose-response (a discard rule): a fresh clock at |z| >= 4; discard the |z| >= 3 result if the |z| >= 4 estimate is smaller and
  rests on at least 30 events; fewer than 30: "not evaluable", flag for M2.
- Stability: 90-day blocks, T = sum t_b / sqrt(B'), p_stab = 1 - Phi(T) per primary cell (section 6, step 2); by-year and
  leave-one-year-out; robustness columns (one clock per side, baseline from the |z| < 3 origins, entry one bar late, naive SE, the
  |z| >= 4 numbers, costs as information, kept events by UTC hour); trade lists saved for the later after-tax layer; everything in the
  report is pre-tax and labelled so.
- Registry: records at discovery (48 cells; primary ids `5m_k6_down`, `5m_k6_up`) and at stability; no economic-gate record (M is the
  economic criterion); each primary cell is its own entry in the across-candidate families.
- Gut-checks: the sd excludes the event bar; the target starts after the event bar closes; a first-bar reversal may be bid-ask bounce
  or a stale price (mistake 10), hence the late-entry column.
- Expectation (M2 sandbox: ETH-like synthetic 5m returns, about 845,000 bars): about 1,300 (Gaussian) to 6,000 (fat tails) kept events
  per side, MDE about 0.03-0.05% against M = 0.35%, so the answer will be decisive. The likely outcome is "dead": a small or zero
  excess, perhaps statistically significant but far below M. A significant excess below M is descriptive, not a lead. Plausible: an
  excess within -0.2% and +0.2% at k = 6; above 1% at 60 minutes is a bug.

Task 4 vol_forecast (deferred; needed for sizing and gating, not a candidate)
- ETH/USDT and BTC/USDT, each its own family, same cutoff and holdout, walk-forward fit 365 / validate 90. Target: log realised
  variance over the next 60 minutes (RV from 5m returns), origins 60 minutes apart. Baseline: trailing 1h/4h/24h log RV, hour-of-day
  and day-of-week effects, trailing 5-day average high-low range from closed daily bars. Test variable: log(last-60-min volume /
  median volume for the same hour over the prior 14 days). Report baseline out-of-sample R^2, gain from volume in every split, a
  decile calibration table; save the forecast column. Primary: gain > 0 in every split.

Retired (do not resurrect): Task 1 in all versions and its gate; Task 5; Task 2 follow-ups; the liquidity monitor as a gating tool;
fill-rule reporting; Scenario A and A-stress; the re-costing tool; the 0.05% maker band; the 0.04% filter threshold; fit-window-sign
orientation for Task 3's two primary cells; the old per-block HAC/Stouffer stability test and the opposite-block veto (R3);
"replicate the sign on BTC, report only".

## 8. Mistake log (all are ways to fake a result)

1. pandas weekly resample anchors Sunday; Binance weeks anchor Monday: use W-MON.
2. Joining different-frequency series by row position collapses to the coarser spacing.
3. Fine return vs the coarse return of its own window gives about 1.0 correlation (the same move twice).
4. Shifting by one coarse width re-enters the source window; capping lags is incomplete (contamination is diluted at every lag in
   between). Use event_anchored_lead_lag; tell-tale sign: best lag at the edge of the range.
5. Pairing coarse and fine series by row position when date ranges differ (about 84% of early coarse bars mis-paired): strict time
   alignment; keep a range-mismatch case in the self-tests.
6. Comparing fingerprints across timeframes on different spans: use equal spans.
7. A column named lag_minutes_after_close counted fine bars: name columns by unit.
8. Carried-forward OHLC of zero-trade minutes polluted resampled open/high/low: traded minutes only.
9. A walk-forward reference sign from the full sample contains the validate windows: orient by the pre-registered direction or the
   split's fit sign.
10. Stale last-trade prices in a thin pair make lag-1 effects strong and untradable.
11. Raw forward returns in a drifting market pass a threshold on drift alone: measure the excess over the unconditional mean at the
    same horizon.
12. Planning around a promotional fee (M0's own error): the planning fee is the default schedule.
13. Defaulting a long-only formula to two-sided / fit-window-sign orientation when the trading constraint already fixes the sign (M0's
    error on Task 3's two primary cells; corrected): check whether "long-only" pins the direction before treating a cell as exploratory.
14. (M1) A per-block OLS-with-intercept significance test on an overlapping, persistent predictor, plus an opposite-block veto with no
    multiplicity control, fails pure noise (85% of null blocks negative; veto 100%). Any new gate gets a null-calibration and a power
    check on synthetic data BEFORE it is pre-registered.
15. (M1) An acceptance band tighter than the Monte Carlo error of the test (200 paths gives +-1.6 points at 5%): a correct
    implementation fails it about one run in nine. Set bands from the standard error, with a confirmation run.
16. (Process, M1) Accepting "item 2 done" without asking how a bad record is withdrawn: the live registry then held void records with
    no way to remove them. Ask for the failure path of every irreversible mechanism.
17. (Process, M1) The cause of the 8 to 10 lost days was the delivery channel (code pasted through chat), not the research. The
    PROTOCOL fixes it; never reintroduce patches or inline code.
18. (M2 review of Work Order 1.6, before any S2 result) A Newey-West (Bartlett) bandwidth equal to the overlap length (3 and 9 lags for
    24h and 72h returns on an 8h grid) with a persistent predictor (funding rank, lag-1 autocorrelation about 0.95): the kernel taper
    under-estimates the variance and a nominal 5% one-sided test rejected 6.6-8.6% of null paths in simulation. Use a bandwidth of at
    least 4 x the overlap or a shift/permutation null, and null-calibrate with a synthetic predictor that has the real persistence. D2's
    production-code check of the corrected 36-lag test read 7.8% (band 8%) and M2's 4,000-path sandbox run about 6%: the correction
    helps but does not remove the leniency entirely.
19. (M2 review of Work Order 1.6, before any S2 result) The economic rule was specified to go to cash when an origin was "gap-excluded",
    which included a missing exit bar three days later: a trading rule that uses future data availability. Validity flags built for the
    statistics (is the target observable?) must never be reused as inputs of a tradable rule; a rule may use only what is known at
    decision time, including whether data exist. The same holds for sample selection: Task 3's de-clustering clock must not depend on
    whether later bars exist (Work Order 1.7 item 3).
20. (M2 review of the Task 3 plan) Naming a procedure without its statistic ("standard rolling walk-forward" for Task 3's stability
    check): the developer cannot build it and nobody can calibrate it. Every gate in an order states its exact statistic, null and
    acceptance bands; Task 3's stability check was therefore redefined, and calibrated in the sandbox, before the order was issued.

## 9. Status, rulings in force, outstanding

Rulings in force (all in the repo)
- Work Order 1.5 (`docs/work-orders/1.5.md`): R1 across-candidate Holm; R2 S2 first usable origin; R3 the opposite-block veto is
  RETIRED; R4 report buy-and-hold on the same segment. Its section 8: A1 void design, A2 forward-test hooks, A3 the delivery loop,
  A4 `combined_z > 3` is obsolete (the `formula_s1` self-test is rewritten for the new statistic), A5 stale developer files, A6
  step 0 `diag_state.sh`.
- `answer-04`: centre over the whole common origin set including the partial block (the reference's [:B*n] slice is only a
  simplification); blocks are 90 CALENDAR days with per-block index sets; bootstrap returns aligned to closes; scratch under
  `<repo>/temp/`.
- `answer-to-message-19`: the S1 report accepted as the record; S1 closed; the S2 acceptance bands as in section 6; the buy-and-hold
  comparator is the gate's own segment, blocks and stress cost ("same origins" in R4 means the same evaluation segment); a partial
  block is not scored but is in the pooled figure; all eleven interpretation choices of the S1 report accepted.
- Work Order 1.6 (`docs/work-orders/1.6.md`, M1, 2026-10-19) as amended by `docs/correspondence/answer-s2-rulings.md` (M2, forward
  v20, which includes the unsent v19): HAC lags 12/36 with a labelled sensitivity column for the superseded 3/9; the gate rule's
  validity depends on the funding rank only; stability on the 72h cell only; first-settlement time of day (08:00, confirmed); timing
  of the S1 regression check; an ignore check for `temp/secret_keys.txt`; the null self-test of the discovery test with a persistent
  synthetic predictor (false-pass at most 8% at >= 1,000 paths on the primary 72h cell; a correct implementation reads about
  5-6.5%); S2's report carries its trade list and is labelled pre-tax (for the later after-tax layer); D2 refreshes the stale
  developer files (A5); the sequence of delivery 9 (rulings, dry run, equality check against delivery 8, live run only with the
  owner's "go live S2" and only if every check passed, report). D2 applied all of it in delivery 9 and delivery 10 (the report);
  M2 accepted the report on 2026-10-25.
- Work Order 1.7 (`docs/work-orders/1.7.md`, M2, issued 2026-10-23) with `docs/work-orders/1.7-task3_reference.py` (D2 reports both
  filed): D2 starts it after M2's acceptance of the S2 report, i.e. from 2026-10-25.
- `docs/correspondence/answer-s2-accepted.md` (M2, forward v21, 2026-10-25): S2 accepted and closed; D2 starts Work Order 1.7.

Audit trail (what was seen when). M2's two corrections to Work Order 1.6 (HAC lags, gate-rule validity) were written on 2026-10-20 and
2026-10-21 and the owner forwarded none of M2's files before D2's delivery 8, so D2 built and dry-ran S2 under the original order.
M2 saw D2's dry-run figures only afterwards, in the owner's message that led to the 2026-10-23 files: ETH 72h primary slope -0.000662, one-sided p 0.461, correlation -0.003,
p_stab 0.384, gate pooled net +0.43 with 63.6% non-negative blocks (not passed); BTC slope -0.00540, p 0.137, correlation -0.029,
p_stab 0.0995, gate +0.26 with 47.8% (not passed); BTC 24h cell p 0.027 (Holm within 2: 0.053). Nothing in the rulings was chosen from
these figures; none of the quantities that decide S2 (stability, gate) depends on the HAC lags. The live run used the ruled lags; D2's
equality check showed that only the HAC-dependent quantities (SE, t, p, Holm, MDE) differ from the dry run.

M2's own verification, 2026-10-20 (sandbox only; nothing was re-run on the owner's machine)
- S1 report and answer-to-message-19: every figure reproduces (Holm within 10 for both pairs; T = sum s_b / sqrt(30); p_stab =
  (1+k)/2001 with integer k; positive-block counts; origin count 2,772 and the by-year origins; non-negative block counts;
  compounded block returns against the pooled returns within rounding; cost drag 0.80 / 0.79; hit rates; MDE = 2.486 x SE;
  t = slope/SE; one-sided p = normal tail; "one run in nine" = 11.3%; the 17-of-200 false-pass count is a 3.8% tail under a true 5.3%).
- Work Order 1.6: the origin arithmetic reproduces (BTC 6,269 = 23 x 270 + 59, ETH 6,035 = 22 x 270 + 95 for 00:00 first settlements;
  last origin 2025-08-28 16:00; one or two fewer for 08:00 or 16:00). D2's delivery 8 confirmed the 08:00 case exactly: 6,268 and 6,034.
- Two flaws in Work Order 1.6, fixed by ruling before D2 built anything: the discovery HAC test was too lenient (mistake 18) and the
  gate rule used future bar availability (mistake 19). Evidence: `docs/history/m2-sandbox-calibration-2026-10-20.md`.
- M1's S2 power statement holds (20% at -0.03, about 70% at -0.08 for the stability check).
- S2 report (2026-10-25): every figure reproduces from the numbers printed in it: t, one-sided p, Holm within 2 and across candidates,
  Bonferroni, MDE; origin counts by pair, by block and by year; the 267-origin block; block starts and partial-block lengths; T from the
  s_b; p_stab as (1+k)/2001; the compounded block returns against the pooled returns; the 16-of-22 and 17-of-23 counts; the cost drag
  against 518 and 510 round trips; hit rates; row counts at the cutoff. D2's persistent-null reading is consistent with M2's sandbox
  (see section 5).
- Task 3 (Work Order 1.7), calibrated before pre-registration with the reference script: on synthetic fat-tailed 5m series the
  primary-cell test and the block stability check hold their 5% level (false-pass 1.5-4.5% and 3.0-5.5% at 200 paths per row), an
  injected +0.50% excess is classified "pass" in 100% of paths and +0.10% "dead" in 100%.

Outstanding
1. Task 3 (D2, Work Order 1.7): step 0 first; M2 recomputes the report (section 11). Both primary cells are one-sided positive; the answer
   will probably be "dead".
2. D2's STATUS.md marks delivery 10 (the S2 report) "not verified" until the owner shows D2 its PASS output; the report is on GitHub and
   M2 has accepted its figures.
3. D1's messages 13-18 were never shown to M1 or M2: skim once for anything not covered by the S1 report's section 8 (all accepted).
4. `research_cli.evaluate_fixed_lag`: confirm it is removed or superseded.
5. Tax rules (section 10): the owner states which taxes apply and has them confirmed by a tax professional; until a confirmed rules file
   exists every result is pre-tax and labelled so. The tax layer itself is built in the expansion work order.
6. M2's own files: NOTES.md revision 3 (2026-10-23) did not reach main (a fetch on 2026-10-25 still showed the 2026-09-23 snapshot, while
   the PROTOCOL.md roster was verified in place by fetch and D2 reports the rulings and Work Order 1.7 filed). This revision 4 replaces it; after the owner applies delivery
   m2-04, fetch `context/mathematician/NOTES.md` and check the Snapshot line.

## 10. Strategic assessment and the owner's roadmap

Owner's roadmap (decided 2026-10-20; it overrides the "Next" lines of M1's handoff)
1. Finish S2 (Work Order 1.6, D2 building) and Task 3 (Work Order 1.7, issued) first. Developer time is the critical path: after a
   review, M2 writes the next work order before updating this file.
2. Then expand testing to any suitable timeframe (intraday, daily, weekly, longer) and to other markets; the owner is interested in
   Indian equities, indices, commodities and ETFs. Priority rule: broader market coverage over more variants on the same assets. A
   rule applied unchanged to a new market is a NEW pre-registered family (its own name, counted in that market's across-candidate
   families), never a rescue of a closed candidate.
3. Every test stays pre-registered and validated out of sample: the same cutoff, 2025-08-31, for every market, and a one-shot
   holdout per candidate.
4. Backtests include transaction costs, slippage AND applicable taxes. The tax layer is designed before any new result is seen (the
   design below). Zero-cost data only (hard limit 1); if the only source of a market's data is paid, write
   `BLOCKED: <what is missing>` and stop.
5. The expansion does not start before S2 and Task 3 are reported. When the time comes, M2 proposes it as a SHORT work order.

Tax layer (design frozen 2026-10-23, before any new result; built in the expansion work order)
- M2 is not a tax advisor. This is structure, not advice: every number comes from a rules file that the owner confirms with a tax
  professional. No after-tax figure is reported until a rules file marked confirmed (by whom, when) exists; until then every result is
  labelled pre-tax.
- Layers reported side by side: (A) before costs; (B) net of transaction costs and slippage, which is the pre-registered gate; (C)
  after tax, B minus taxes. Gates stay on B. C may only mark a candidate "not deployable under the confirmed rules" (an owner-level
  decision); it never retunes a rule.
- Interface: every evaluator saves a trade list (instrument, asset class, entry and exit times and prices, fraction of capital,
  per-side costs) and the tax layer reads only trade lists, so it can be applied later without re-running any test (hence the
  trade-list requirements of Work Orders 1.6 and 1.7 and of v20).
- Rules file: versioned (version, effective_from and effective_to, source, confirmed_by) and parameterised per asset class (for
  example crypto / virtual digital assets, listed equity, equity-oriented ETF, other funds, index and commodity derivatives): gain tax
  rates by holding-period threshold, surcharge and cess, loss treatment (set-off against which classes, carry-forward years, or
  none), taxes and levies counted as costs (rate, side, base), TDS (rate, threshold, timing, creditable or not), and the April-March
  financial year used for netting, loss carry-forward and payment dates. A change of rule is a new version, never an edit; every
  registry record carries the version (or "pre-tax").
- Modes: "current rules" (primary: today's rules applied to all trades, i.e. what the owner would face going forward) and "as-of"
  (the rules in force at each trade date; a sensitivity).
- Computation: taxes per financial year from the realised trades; the equity curve shows taxes paid at financial-year end and TDS as
  a cash drag until credited; fixed-capital and compounding variants both reported.
- Market cost models (brokerage, exchange and regulatory charges, stamp duty, GST on brokerage, depository charges, spread, impact)
  are versioned inputs of layer B, not taxes. A new market also needs its trading calendar and holidays, session times, price-limit
  rules, lot sizes (derivatives), corporate-action handling (splits, bonuses, dividends), survivorship-free constituent lists where
  relevant, and a free data source: one line each in the short work order.

Strategic assessment (judgment, not a forecast)
- There is nothing to compound yet: no tradable edge has been found. Lead-lag is dead, the passive baseline is moot, S1 and S2 are
  closed (not advanced).
- S2 died where M1 and M2 expected: no discovery signal, failed stability and gate on both pairs; the rank rule churns and loses to
  buy-and-hold. Task 3 is the best remaining shot on the crypto pairs and will be decisive (MDE about 0.03-0.05% against M = 0.35%);
  the likely result is a small or zero excess, "dead". A clean "no edge found with public price and funding data at these horizons" is a
  legitimate end state and saves capital: say so plainly to the owner, never promise.
- Slow signals have limited power: 8-9 years of daily data can only prove effects near an annual Sharpe of 0.6 or better, so expect
  "inconclusive" for weaker ones. That is a data-length limit, not a failure of the design.
- A validated slow or medium-horizon strategy, if one exists, plausibly delivers something like 20-60% a year with double-digit
  drawdowns (judgment). The owner's 1%/week sits at the top of that range. M1's estimate on 2026-09-23 of the odds that a candidate
  survives the holdout was roughly even; after the closure of S1 and S2 M2 judges it lower (not quantified). The odds that a survivor
  also compounds fast are well under one in four. With S1 and S2 closed and Task 3 likely dead, broader markets and timeframes (the
  roadmap) are the main way to add independent shots; each new market starts with its own cost model, calendar, free data source and
  the tax-rules file.
- Two pairs roughly doubled the number of semi-independent shots; they did not improve any single candidate's odds.
- Fallback if every candidate dies: volatility-managed exposure (the Task 4 forecast) to improve consistency; further exogenous data
  (open interest, long/short ratios) only if free.
- FDUSD, if kept as the cash leg, briefly traded below $0.90 in April 2025; size accordingly.

## 11. First actions in the next chat

1. Fetch `context/mathematician/NOTES.md` from GitHub and check that its Snapshot line is 2026-10-25 (revision 4); the 2026-10-23
   revision never reached main. If it does not, tell the owner (delivery m2-04).
2. If a developer report is waiting, read it first. Recompute before trusting (sandbox only, say so). Recipes:
   - Holm: sort the p-values, multiply the i-th smallest by (n - i + 1), take the running maximum, cap at 1; also across candidates
     per pair with every live candidate that has a record at that step (S1 included; for Task 3 each primary cell is an entry).
   - HAC: t = slope / SE; one-sided p = normal tail of t; MDE = 2.486 x SE. Stability: T = sum(s_b) / sqrt(B) (S1/S2) or sum(t_b) /
     sqrt(B') (Task 3); p_stab = (1 + k) / (R + 1) with integer k (R = 2000 gives denominator 2001) for S1/S2 and 1 - Phi(T) for Task 3.
     Binomial standard error of a rate = sqrt(p (1 - p) / n).
   - Task 3: SE_cluster = sqrt(sum over UTC days of (sum of (e_i - mean))^2) / n; t = mean / SE; dead if mean + 1.645 SE < 0.0035;
     845,808 gap-free 5m bars in the discovery frame; B' about 32 full 90-day blocks plus a partial block of about 55 days.
   - Origins and blocks: from the first and last origin dates, origins = number of 8h slots (S2) or days (S1); full blocks = floor(origins
     / 270) for S2 (90 for S1's daily blocks: 30 x 90 + 72); the partial block holds the remainder. First S2 origin = first settlement +
     271 x 8h.
   - Gate: the product of (1 + block return) minus 1 reproduces the pooled return within rounding; count the non-negative FULL blocks
     against 21 of 30 (S1), 16 of 22 (S2 ETH), 17 of 23 (S2 BTC); cost drag (1 + net) / (1 + gross) is about (1 - 0.003)^(round trips)
     at stress cost.
   - Break-even hit rate p* = (1 + c / E|r|) / 2.
3. Task 3 report: check it against Work Order 1.7 section 5: counts and exclusion reasons (5m and 15m, |z| >= 3 and 4); the mu_k
   table; the 48-cell tables with the primary cells one-sided and Holm over 48; the classification; the dose-response result;
   stability (T, p_stab, B', per-block table, across-candidate Holm with S1 and S2); by-year and leave-one-year-out; the robustness
   columns (above all the late-entry column); the trade-list files and their SHA-256; the acceptance rates and the exact-reproduction
   differences; the S1/S2 regression result. A significant excess below M is "dead", not a lead. Then accept, tell the owner in a short
   plain note, and do not recommend a freeze unless a primary cell classifies "pass" and every other check agrees.
4. Then, with the owner, propose the expansion as a short work order (section 10): which market first, the free data source, the cost
   model, the tax-rules file to be confirmed by a tax professional, the cutoff 2025-08-31 and the one-shot holdout.
5. Keep this file current: overwrite `context/mathematician/NOTES.md` through a delivery and say so in the one-sentence delivery line.
