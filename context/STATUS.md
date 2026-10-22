# Project status

Last updated: 2026-10-22, by D2 (developer), Work Order 1.6 step 2 (delivery 8, dry run). The first section below is the
current state. "Current state (D1, 2026-10-18)" is D1's text, kept verbatim as history (S1 is now closed; see
below). Everything under "Historical status" is the 2026-09-25 text, also verbatim, and is STALE wherever it
conflicts with the sections above it.

## Current state (D2, 2026-10-22)
- Rules: `docs/PROTOCOL.md` (the owner's three hard limits and the delivery contract). Task: `docs/work-orders/1.6.md`
  (S2 `funding_extreme` for both pairs, through the economic gate; stop after the S2 report is committed). Work Order
  1.5 (R1-R4, A1-A6), `docs/correspondence/answer-04.md` and `answer-to-message-19.md` stay in force. Agents: M2
  (mathematician), D2 (developer, this role); D1 ended with message-19.
- S1 is closed without advancing on either pair (`docs/reports/s1-report-step6.md`, accepted by M1). Nothing is frozen,
  nothing is forward-tested, the holdout unlock (one-shot) has never been used; S2 must not change that.
- Verified by output from the owner's machine (diag run 2026-10-20T14:18:59Z, Step 0): folder clean at `a787d41`,
  equal to `origin/main`, no stashes, `registry.jsonl` 20 lines equal to GitHub, venv Python 3.12.7. Raw data present for
  both pairs: `*-1h`, `*-1d`, `*-funding` feather files.
- Verified by output from the owner's machine (delivery 7, 2026-10-22): `PASS commit 11a5fbb`; 37 self-tests passed (including
  `formula_s2.py`); the live registry stayed byte-identical (20 lines); the S1 report generator, regenerated read-only,
  reproduced every recorded S1 figure and its summary table equals the committed one (the regression check: no shared
  module changed except `stability_acceptance.py`, not used by the S1 report); the S2 false-pass confirmation (1000 fresh null
  paths per row, R 2000, Python 3.12.7, numpy 2.5.3) gave Gaussian 56/1000 = 0.056 and t3 + volatility cluster 53/1000 = 0.053,
  both within the 7% band; output committed as `docs/history/2026-10-21_s2-null-confirmation.txt`. `scripts/diag_state.sh` now writes
  its copy to `temp/crypto_bot_diag.txt`. The D2 row is in `docs/PROTOCOL.md`; `message-20.md` (D2 to M2) lists the
  interpretation choices.
- Delivery 8 (Work Order 1.6 step 2, dry run) is prepared in `deliveries/8/`: `run_s2.py` (read-only `--origin-facts`; the run
  writes exactly three records per pair, discovery / stability / economic_gate, to a SCRATCH registry unless
  `--commit-to-registry`), `formula_s2.py` (adds a `horizon` parameter to `s2_stability` for the labeled 24h variant),
  `selftest_all.sh` (runs `run_s2.py --self-test`, 38 tests). Its apply script prints and commits the origin facts of both
  pairs (`docs/reports/s2-origin-facts-step2.txt`), then a dry run of both pairs on a fresh scratch registry
  (`docs/reports/s2-dry-run-step2.txt` and `docs/reports/s2-dry-run-records-step2.jsonl`). NOT VERIFIED until the owner's
  PASS output comes back. It never touches the live registry.
- RULE for the dry run and the live run: after the dry-run numbers are seen, code changes are bug fixes only; no reading of the
  order is changed because of an outcome. The live run (delivery 9) happens only after the owner's explicit flag, once per
  pair, and its records must equal the dry-run records (timestamps aside) with the first 20 registry lines byte-identical.
- Design of S2 (all in `formula_s2.py`'s docstring; every interpretation choice is repeated in message-20): one common origin
  set per pair on the 8h settlement grid (slot 272 on; last settlement with s+1h+72h <= the last 1h bar); mid-rank over the 270
  previous slots with R2 masking; target = ln(open[s+1h+H]/open[s+1h]), H 24h and 72h; two cells, primary 72h; stability on the
  72h cell with `stability_check.stability_s2`; the gate is the existing `economic_gate` on the 1h frame with the rule "long while the
  latest valid rank <= 0.5", recorded in mode A (literal reading of the order), mode B (only an invalid rank forces cash) as a
  labeled variant, never recorded.
- NEXT: delivery 9 = the live run (after the owner's flag), then delivery 10 = the S2 report (`s2_report.py`, read-only,
  refuses unless every recomputed figure reproduces the registry).

## Current state (D1, 2026-10-18)
- Rules: `docs/PROTOCOL.md` (owner's three hard limits and the delivery contract). Task: `docs/work-orders/1.5.md`
  (steps 0-6; section 8 amendments win). Agents: M1 (mathematician), D1 (developer, this role).
- **The first valid S1 results are in the live registry (delivery 5, records 15-20).** The OLD S1 records in
  `registry.jsonl` (lines 1-12: two identical runs, 2026-09-28 and 2026-09-30, for S1-ETHUSDT and S1-BTCUSDT) came from code that did not implement the section 6 common origin set (each
  cell ran on its own sample; tiling started at the primary cell's own first origin) and used a block test that dropped
  origins (Work Order 1.5 section 0). Their numbers are void; do not cite them.
  They are void: commit `ac63ff2` (verified on the owner's machine) appended one void marker per family; the 12
  original lines are still in the file, unedited. `ac63ff2` is the void commit to quote in the S1 report. The live run is commit `4487f1e`.
- Commit `92d9986` ("Fix S1 common-origin-set bug") contains no code fix; see `docs/handoffs/v2.3.md`. `formula_s1.py` /
  `run_s1.py` now have the common origin set and calendar blocks (delivery 3, verified) and the amended stability
  statistic (delivery 4, verified). `registry.py` has voiding and the R1 Holm rule (delivery 1, verified).
- The old stability test (combined Stouffer z plus opposite-block veto) is retired by Work Order 1.5; the new
  statistic is defined in section 3 of the work order and ruled on in `docs/correspondence/answer-04.md` (filed
  in delivery 1). The retired rule is gone from the code (delivery 4); the amended
  statistic lives in `stability_check.py` and `formula_s1.s1_stability`; its acceptance tests are `stability_acceptance.py`
  (reduced size wired into `selftest_all.sh`; `--full` is the real acceptance run).
- Verified by output from the owner's machine (diag run 2026-10-17T14:05:49Z): folder was clean at `1b776f4`, equal to
  `origin/main` at that moment; local `registry.jsonl` had the same 12 lines as GitHub (no local-only lines); no
  stashes; venv Python 3.12.7.
- Verified by output from the owner's machine (delivery 0, 2026-10-17): `PASS commit cd0a0a1`; the folder was already
  at `7aa4c99`; all 33 self-tests passed; `registry.jsonl` byte-identical before and after (12 lines).
- Verified by output from the owner's machine (delivery 1, 2026-10-18): `PASS commit ac63ff2`; 33 self-tests passed;
  `registry.jsonl` 12 -> 14 lines, first 12 byte-identical to the backup; `cumulative_count` 0 for ETHUSDT and BTCUSDT;
  no record at discovery, stability or economic_gate enters any Holm family.
- Verified by output from the owner's machine (delivery 2, 2026-10-18): `PASS commit bd0c8cb`; 34 self-tests passed;
  the live registry stayed byte-identical; the guard recognised the live file under three spellings from another
  working directory; the default registry is `temp/scratch-registry.jsonl`.
- Verified by output from the owner's machine (delivery 3, 2026-10-18): `PASS commit 756f56a`; 34 self-tests passed;
  live registry byte-identical. Real-data S1 origin facts (`docs/reports/s1-origin-facts-step3.txt`), identical for
  ETH_USDT and BTC_USDT: first origin 2018-01-24, last origin 2025-08-26, 2,772 origins, 0 gap exclusions, 0 missing
  calendar days, 30 full 90-day blocks of 90 origins plus a partial block of 72; every cell n = 2772; no discovery
  row after the cutoff; the economic gate's full blocks equal the origin-based ones (its partial block runs 77 days).
- Verified by output from the owner's machine (delivery 4, 2026-10-18): `PASS commit f5a883a`; 35 self-tests passed;
  the live registry stayed byte-identical. Full acceptance run on the owner's machine (200 paths, R 1000), identical to
  my sandbox: S1 null 0.010, S1 t3+SV null 0.005, S1 edge 0.850, S1 strong edge 1.000, S2 null t3+SV 0.045, S2 edge 1.000
  all within band; S2 null Gaussian 0.085 outside its band (<= 0.07); production equals M1's reference in all seven rows.
  Output committed as `docs/reports/stability-acceptance-full-step4.txt`.
- Verified by output from the owner's machine (delivery 5, 2026-10-18): `PASS commit 4487f1e`; 35 self-tests passed; a
  scratch dry run of each pair preceded the live run; the live registry went from 14 to 20 lines (first 14 byte-identical),
  records 15-17 = S1-ETHUSDT (discovery, stability, economic_gate), 18-20 = S1-BTCUSDT; each live record equals its dry-run
  record; no frozen or holdout record. RECORDED OUTCOMES as printed by the runner (the report has the full tables):
  ETHUSDT primary cell slope 0.000715415, n 2772, one-sided p 0.128192, Holm-in-family 0.769151; stability T 0.7082,
  p_stab 0.230385, passes False, 56.7% of blocks s_b>0; economic gate pooled net 4.92255, 40.0% non-negative full
  blocks, passes False. BTCUSDT slope 0.0010087, p 0.0145107, Holm-in-family 0.145107; stability T 1.6966, p_stab
  0.0554723, passes False, 50.0%; gate pooled net 34.5543, 50.0%, passes False. No interpretation here; see the report.
- Work Order 1.5 progress: steps 0 to 5 done and verified (`deliveries/0/`; `deliveries/1/` = commit `ac63ff2`;
  `deliveries/2/` = commit `bd0c8cb`; `deliveries/3/` = commit `756f56a`; `deliveries/4/` = commit `f5a883a`;
  `deliveries/5/` = commit `4487f1e`). Step 6 delivered (`deliveries/6/`): the S1 report
  `docs/reports/s1-report-step6.md`, generated read-only by `s1_report.py` and cross-checked against the registry;
  NOT verified until the owner's PASS output comes back. Then the owner forwards the report to M1. S1 stops here: no
  freeze, no forward test; S2 only after M1 accepts the S1 report. S1 stops after the report;
  no freeze, no forward test (the holdout unlock is one-shot and unused). S2 only after M1 accepts the S1 report.
- S1 as of delivery 4 (verified): one common origin set for all ten cells on a complete
  daily calendar (positions 160 .. N-1-5, gap-excluded origins counted); 90-calendar-day blocks tiled from the first
  origin; stability = global-centred block scores + stationary-bootstrap null (R 2000, mean block 20, seed 12345),
  T and p_stab stored in the registry record; `run_s1.py --origin-facts` is read-only; `--commit-to-registry` is allowed
  again (`STABILITY_REPLACED = True`); used once per pair in delivery 5 (verified). The economic gate is unchanged (R4).
- OPEN FOR M1 (not blocking S1 steps 5-6): the `--full` acceptance run's row "S2 null, Gaussian" gave 0.085 (17/200)
  against the band <= 0.07 (on the owner's machine too, delivery 4). M1's own `stability_reference.py` self-test gives the identical 0.085 with the same seeds, and
  production equals the reference path by path; over 2,000 fresh paths the rate is about 5.3%. See
  `docs/correspondence/message-17.md` and `docs/reports/stability-acceptance-full-step4.txt`. Bands are not moved.
- Registry rules after delivery 1 (`registry.py`): a void marker (`void_pre_fix` with `detail.voids_earlier_records`)
  voids every earlier record of that (family, pair); `cumulative_count`, `cumulative_cells` and `holm_at_step` ignore
  voided records; `holm_at_step` keys by (family, step) per ruling R1; a family with a live `frozen` or
  `holdout_consumed` record cannot be voided. Hygiene (step 2): `append_record` refuses the live registry file
  unless `commit_to_registry=True`; the default registry of every tool is scratch (`temp/scratch-registry.jsonl`);
  live writers today: `run_s1.py --commit-to-registry` and the void CLI. `freeze_manifest`, `holdout_lock` and
  `forward_test` fail closed against the live file (not given the flag; not needed in WO 1.5).
- Scratch and backups go in `<repo>/temp/` (gitignored), never outside the project root; this reverses the
  old convention of using the system temp directory (NOTES.md corrected). `selftest_all.sh` enforces it (TMPDIR) and
  fails if the live registry's hash changes. `temp/secret_keys.txt` is never opened, copied or backed up.

---

## Historical status (2026-09-25 text, verbatim below this line; stale where it conflicts with the section above)


Last updated: 2026-09-25, by the developer (Claude), at a session handoff (context limit).
The previous developer session judged its own conversation too long to safely continue and
handed off here rather than risk losing coherence mid-task. Nothing about the project is
paused because of this -- a new developer session should read this file plus
`context/developer/NOTES.md`, then carry straight on.

## Current pairs
**ETH/USDT and BTC/USDT are the project's two live pairs, for both research and execution**
(work order 1.4, owner-approved, 2026-09-23). ETH/FDUSD is retired as an execution-pair
candidate on liquidity grounds; its existing results stay as historical reference, and no
further formula work targets it. See `docs/work-orders/1.4.md` and `project_context.md`'s
"Current pairs" section.

## Repo and roles
- Single repo: `https://github.com/nitinroshia/crypto_bot` (public). Replaces five earlier
  repos (`dump-sept`, `dump-sept-01/02`, `handover-2026-09-20`, `sample-bot`), all removed
  from GitHub by the owner after their contents were migrated into `docs/` here.
- Three parties: **Owner** (Shachō/final authority on cross-domain or major decisions --
  objectives, strategy principles, architecture, risk/capital exposure, direction changes),
  **Developer** (this role -- Claude, autonomous on implementation/default-choice questions),
  **Mathematician** (runs on Claude, continued each session via `context/mathematician/NOTES.md`,
  not a human -- autonomous on research-design questions).
  If developer and mathematician disagree, the owner is final. The owner relays everything
  between the two AI roles manually (copy-paste), runs every terminal command themselves, and
  has asked for terminal commands rather than descriptions whenever something needs doing on
  their machine.
- Layout: `docs/work-orders/` (mathematician's specs), `docs/handoffs/` (mathematician's
  versioned handoffs to the developer, v2.1/v2.2 -- **not** something the developer adds to;
  see NOTES.md), `docs/closeouts/`, `docs/correspondence/` (the full back-and-forth, numbered
  `message-01.md` onward, plus `answer-*`, `question-*`, `reply-*`), `docs/architecture/`
  (the redesign proposal and ratification), `docs/history/` (dated forensic snapshots),
  `docs/archive/owner-notes/` (files moved during migration but never read/classified --
  check `grep_stale.txt` and the two `README_workorder*.md` files there if curious, still
  unexplained as of this writing). `context/STATUS.md` (this file), `context/developer/NOTES.md`,
  `context/mathematician/NOTES.md` (the mathematician's own actively-maintained working file --
  528+ lines as of 2026-09-23, **never edited by the developer**, only responded to via
  `docs/correspondence/`).
- `temp/` is fully discontinued (2026-09-22). No tool should write there; self-tests use the
  system temp directory. If a new tool is ever found reintroducing a project-local temp
  dependency, that's a regression -- see NOTES.md.

## What's built and self-tested (`user_data/analysis/`, 33 tools, all passing via `selftest_all.sh`)
- **Item 1 (done):** `leadlag.summarize_best_lag` defaults to min-p selection (smallest p, no
  significance pre-filter; ties broken by |HAC t| then smaller lag). Old rule kept as
  `select="legacy_max_abs_effect_among_significant"` to reproduce frozen ETH/FDUSD results only.
- **Data-batch tools (done):** `funding.py`/`fetch_funding.py` (REST-first, monthly-file
  fallback), `locate_gaps.py`, `liquidity_table.py`, `build_derived_raw.py` (derives a coarser
  raw-store timeframe via `resample_ohlcv_traded`, confirmed to generalize beyond a 1-minute
  source), `volatility_report.py` (annualized realized vol, discovery-sample only, sqrt365
  default + sqrt252 labeled alternate), `breakeven_table.py` (break-even hit-rate table from
  empirical return distributions, replacing an old symmetric-Gaussian assumption -- see "Live
  finding" below).
- **Item 2 (DONE, all ~6 pieces landed 2026-09-26):**
  - DONE: `cutoff.py` (the `--end-date` guard) -- hard-truncates a loaded bundle so a formula
    structurally cannot see a post-cutoff row, plus `origin_window_side` for classifying an
    origin as discovery/holdout/straddle. Wired into `research_cli.load_all_dataframes`
    (`end_date=` param) and the CLI's new `--end-date` flag, threaded through both `run_once`
    and `run_walkforward`, logged in every manifest as `end_date_guard`. Verified end-to-end
    (not just cutoff.py's own self-test): `selftest_research_cli.py` proves the guard drops rows
    from the actual returned DataFrame, and a live CLI invocation confirms the same.
  - DONE: `registry.py` -- append-only JSONL, pair-qualified family names (`<TASK>-ETHUSDT` /
    `<TASK>-BTCUSDT`, Work Order 1.4) enforced for every status except the two used for importing
    ETH/FDUSD-era runs (`history`, `void_pre_fix`, which predate the naming scheme and are
    exempt); `cumulative_count` and `holm_at_step` both exclude those two statuses per section 6.
    `holm_at_step` reads each family's single most-recent record so a superseded checkpoint
    p-value (e.g. discovery, once a candidate has moved on to stability) never double-counts.
    Nothing has actually been imported or appended into the real registry yet -- this is the
    mechanism, not populated data.
  - DONE: `holdout_lock.py` -- the actual one-shot enforcement, not just an audit log.
    `unlock_holdout_for_forward_test` is the ONLY sanctioned way to get the untruncated series for
    a hypothesis-specific test; it refuses outright (`HoldoutAlreadyConsumedError`) if that
    (family, pair) has already consumed its one holdout look, and it is impossible to get data
    from it without the required registry disclosure landing first. Logs the verbatim ETH/FDUSD
    2026-exposure note (mathematician NOTES.md section 6) for ETHUSDT candidates specifically
    (BTCUSDT gets an audit entry but no ETH/FDUSD note -- it was never exposed to that data).
    `log_descriptive_access` covers the OTHER kind of post-cutoff read section 6 allows (purely
    descriptive, no returns computed -- gap locators, liquidity tables, etc.) with its own fixed
    note, excluded from cumulative_count/holm_at_step like history imports. Not yet wired into
    any actual data-batch tool or into research_cli.py -- this is the mechanism, and nothing has
    called it for a real candidate yet.
  - DONE: `nonstationarity.py` -- the by-year/leave-one-year-out machinery (section 6's
    "non-stationarity rule"). `by_year_table` shows every calendar period (n, days covered, own
    estimate, judged) with "days covered" defined as distinct calendar dates present, not a row
    count; a period below 120 days is shown but never itself droppable in `leave_one_out` -- its
    data stays in the pooled estimate and in every OTHER period's leave-one-out subset regardless.
    `non_stationarity_report` bundles the pooled estimate, the table, leave-one-out estimates, and
    the section-6 red flag (year-driven: dropping a period more than halves the pooled estimate's
    magnitude OR flips its sign -- either alone triggers it), plus a year-by-year sign-agreement
    statement. `estimator` is caller-supplied and generic (S1's mean effect, S2's OLS slope,
    whatever a given cell's estimate actually is) -- this module has no opinion on how it's
    computed, only on how it's sliced by calendar period. Also supports `period="M"` for
    ETH/FDUSD's by-month convention. Self-tested against hand-computed pooled/LOYO arithmetic for
    both a magnitude-halving year and a sign-flipping year (isolated separately), a stationary
    series that must never trigger the flag, and the partial-year exemption. Not yet wired into
    any actual candidate's reporting -- this is the mechanism, and no primary cell has run through
    it for real yet.
  - DONE: `blocks.py` + `stability_check.py` -- the section-6 stability check for S1/S2.
    `blocks.py`'s `tile_blocks` is the SAME tiling step 3 (economic gate) will reuse, non-overlapping
    90-day blocks from the family's own first origin, with the last block flagged
    `is_final_partial` using an inferred bar-width (not an assumed 1-day constant, so it works for
    any timeframe) to correctly distinguish "genuinely calendar-short" from "just sparser". A real
    bug the self-test caught: without that inference, an EXACT multiple of 90 days (e.g. 270 daily
    rows) was wrongly flagged partial on its last block, since bar labels understate coverage by
    one bar-width (same class of trap as cutoff.py's label-vs-close-time issue). `stability_check`
    Stouffer-combines every judged block's caller-supplied z-score (oriented to the pre-registered
    direction, so S1-positive and S2-negative both read the same way), requires one-sided p<0.05,
    AND separately vetoes the whole candidate if any judged block is significantly (p<0.05) opposite
    in sign -- this veto can fail a candidate even when the combined result would otherwise pass, by
    design. The final partial block is excluded from both the combination and the veto entirely,
    however extreme its own value. `evaluate_fixed_lag` (research_cli.py) is untouched and still
    correctly serves its own, unrelated purpose (Item 1's single fit/validate lag-replication
    check) -- it was never actually wired up as an S1/S2 stability substitute in code (no S1/S2
    formula exists yet), so there was nothing to migrate off; the STATUS.md/NOTES.md warning was
    about not making that mistake once S1/S2 are built, not about removing anything today. Neither
    module is wired into research_cli.py or the registry yet.
  - DONE: `rule_evaluator.py` + `economic_gate.py` -- the section-6 step-3 economic gate.
    `rule_evaluator.py` is the core position/cost/return engine (entry/exit at next bar's open,
    starts flat, costs charged only on position change, end-of-segment forced exit at the
    segment's own last close); `economic_gate.py` applies it: pooled net return computed as ONE
    continuous run over the whole discovery sample, per-block returns obtained by SLICING that one
    continuous per-bar series (not by independently re-running the evaluator per block), so a
    position spanning a block boundary is charged nothing extra there -- verified in both modules'
    self-tests, including that the product of every block's own return (full and partial together)
    reproduces the pooled figure exactly. Requires pooled net return > 0 AND >=70% of FULL blocks
    net >= 0 (>=, not >; the final partial block is excluded from that count but its return still
    feeds the pooled figure). **CONFIRMED BY THE MATHEMATICIAN** (`docs/correspondence/answer-03.md`,
    2026-09-26): the continuous-run-then-slice reading is correct, on two independent grounds --
    step 3's own sentence already distinguishes "evaluation segment" from "block" (block boundaries
    sit inside a segment; only the segment's own start/end force flat), and the self-test
    requirement is a second, independent confirmation. General principle for reuse, stated by the
    mathematician: an evaluation segment is whatever spans ONE CONTINUOUS, UNCHANGING RULE -- the
    economic gate's tiles are reporting slices of one rule (not separate segments), Task 3's
    walk-forward validate windows ARE separate segments (a fresh fit each time), and **the holdout
    (step 5) is confirmed to follow the SAME continuous-segment logic as the discovery sample** --
    one flat-start/forced-exit run over the whole holdout window, no internal tiling, just a single
    pooled pass/fail (simpler than discovery -- no 70%-of-blocks statistic at the holdout). This is
    now recorded in `rule_evaluator.py`'s own docstring so the forward-test command gets it right
    without re-deriving it. Step 2 (stability) is confirmed UNAFFECTED -- no simulated position, so
    "boundary cost" doesn't apply there at all.
  - NOT YET WIRED IN: no S1/S2/Task-3 formula exists yet in `research_cli.py`'s `FORMULAS` dict,
    so none of item 2's machinery (registry, cutoff guard, holdout lock, stability check, economic
    gate, freeze manifest, forward-test command) has been called for a real candidate. That's
    formula-building work, not item 2's own scope -- item 2 was building the RULES machinery that
    every future candidate must go through, and that machinery is now complete and self-tested.
  - DONE: `freeze_manifest.py` + `forward_test.py` -- step 4 (freeze) and step 5 (holdout/forward
    test), completing item 2.
    - `freeze_manifest.py`: one-shot, like the holdout lock -- `freeze_candidate` refuses a second
      freeze of the same (family, pair) with `AlreadyFrozenError`, so a committed discovery estimate
      can't be quietly moved after an early holdout peek. Records timestamp, git commit (degrades to
      `"unknown"` rather than raising if commit info can't be captured), direction, discovery
      estimate, dispersion (SE_discovery), and n_discovery -- as its own `registry.jsonl` record
      (`status="frozen"`), not a separate manifest format.
    - `forward_test.py`: two-phase, so the minimum-sample check never burns the one-shot holdout
      look. Phase 1 (`check_holdout_readiness`) is a DESCRIPTIVE read (`holdout_lock.log_descriptive_access`)
      -- counting available holdout days/observations relates no predictor to any return, so it's
      repeatable while waiting for more data (verified: a "wait" result never touches the one-shot
      lock). Phase 2 (`run_forward_test`) only calls `holdout_lock.unlock_holdout_for_forward_test`
      once Phase 1's minimums (45 days, 100 observations, SE_holdout <= half the claimed effect) are
      met. SE_holdout is SCALED from the frozen manifest's own dispersion via the exact formula
      (`SE_discovery * sqrt(n_discovery/n_holdout)`) -- never independently re-estimated at the
      holdout. Reads the frozen manifest for direction/estimate/dispersion/n_discovery rather than
      accepting them as fresh parameters, so step 5 tests "exactly the frozen primary cell." Applies
      the confirmed evaluation-segment ruling (`answer-03.md`) for the economic check: ONE continuous
      `rule_evaluator.evaluate_rule` call over the whole holdout window, no tiling. Reports step 5's
      statistical result and the step-3-at-holdout economic result as two SEPARATE dicts
      (`step5`/`step3_holdout`) with no merged top-level verdict, per the standing requirement --
      self-tested with a constructed case where one passes while the other fails on the SAME
      underlying series, to prove they're genuinely independent, not just two labels on one number.
      Binary pass/dead classification when `m_threshold` is omitted (S1/S2); the three-way
      pass/dead/inconclusive classification (one-sided 95% upper bound vs. M) when it's given
      (event-type cells). Completes the two-step registry pattern `holdout_lock.py` documented: the
      access-log record from `unlock_holdout_for_forward_test` (p_value=None) is followed by a second
      `holdout_consumed` record here carrying the real verdict.
- **First real candidate: S1 (formula_s1.py + run_s1.py), 2026-09-26.** The first formula to
  actually exercise item 2's machinery. Per the mathematician's explicit instruction: build S1
  through the pipeline for both pairs, but STOP after the economic gate -- freeze_manifest.py and
  forward_test.py are deliberately NOT called by `run_s1.py`, since `holdout_lock.unlock_holdout_for_forward_test`
  is one-shot and this would be its first real use for any candidate. Results are for review first.
  - `formula_s1.py`: section 7's S1 trend_slope, verbatim -- `x = ln(C_t/C_{t-L})/sigma30`, `y =
    ln(C_{t+h}/C_t)`, L in {10,20,40,80,160}, h in {1,5}, OLS+HAC (matching leadlag.py's own
    convention), direction positive, primary cell L=40/h=5, own-family Holm across the 10 cells
    (`multitest.annotate_family`, separate from registry.py's across-candidate Holm). Pre-registered
    economic rule: long from next open if x_40>0 at the day's close, else cash.
    **A real bug caught and fixed during development:** `stability_check.py` (and, if ever wired in,
    `nonstationarity.py`) hands `block_test`/`estimator` only a narrow date-range SLICE of the price
    series -- naively recomputing `predictor`/`target` fresh from that slice starves the first
    `max(L, SIGMA_WINDOW)` rows of real lookback context, silently dropping ~40-45% of a 90-day
    block's origins and corrupting the rest, which flipped an unambiguous injected positive edge
    into apparent per-block NEGATIVE signs. Fixed with `make_primary_estimator`/`make_primary_block_test`
    factories that precompute x/y ONCE over the FULL series and select by date -- same "continuous
    computation, sliced afterward" principle as `economic_gate.py`'s own confirmed design. A second,
    smaller bug: the warmup is `max(L, SIGMA_WINDOW)`, not `L+SIGMA_WINDOW` (sigma30's own 30-day
    requirement doesn't stack with L for lookbacks under 30).
  - `run_s1.py`: orchestrates discovery (10 cells) -> stability check -> economic gate for a given
    pair, appending each step to the registry (family `S1-ETHUSDT`/`S1-BTCUSDT`). Nothing here is
    one-shot -- safe to re-run freely while results are under review. Offline self-test (`--self-test`,
    synthetic data, no real files needed) passes; **not yet run against real market data** -- see
    below.

## Live finding, closed out (2026-09-24)
Rebuilding the break-even hit-rate table with empirical (not Gaussian-assumed) return
distributions surfaced a genuine result: at 15-minute resolution, the typical |return| for both
pairs is close to or smaller than the round-trip trading cost itself, making break-even
mathematically impossible (>100% required hit rate) under a symmetric-payoff, trade-every-bar
model. This was checked hard before being trusted -- an outlier-sensitivity diagnostic showed
dropping the most extreme observations makes it *worse*, not better, ruling out a data artifact.
The extreme moves driving the tail were confirmed by the mathematician as three real, documented
market events (2020-03-12 COVID crash, 2021-05-19 flash crash, 2017-09 China ICO ban). Full
writeup in `docs/correspondence/message-07.md`. **Implication for the pipeline:** this doesn't
touch S1 or S2 (daily/8h-based). It's a real constraint on any 15m symmetric trade-every-bar
model, but not on Task 3, which conditions on |z|>=3 shocks rather than assuming a small edge
every ordinary bar -- if anything it's a point in favor of Task 3's event-conditional design.
This thread is fully closed; nothing further expected from either the owner or mathematician on it.

## Immediate next step
Item 2 is done (31 tools, all self-tested against synthetic data). **S1 is now built** (above) and
self-tested offline, but **not yet run against real ETH/USDT or BTC/USDT market data** -- this
sandboxed environment has no network access to Binance, so `run_s1.py` needs to be run by the owner
against the real, already-fetched local data for both pairs:
```
python3 user_data/analysis/run_s1.py --pair ETH_USDT
python3 user_data/analysis/run_s1.py --pair BTC_USDT
```
Per the mathematician's instruction, this deliberately stops after the economic gate -- the results
(discovery/stability/economic-gate) need to come back for review before freeze/forward-test proceed
(the holdout is one-shot; this would be the first real use).

**Funding first-settlement dates (parallel question): confirmed, no fresh pull needed.** `funding.py`'s
`describe_native()` computes `first_settlement` from whatever native funding DataFrame it's given --
a pure, offline function (see its own self-test), with no dependency on when that data was fetched.
The current dates on record (ETHUSDT 2019-11-27, BTCUSDT 2019-09-10, `docs/correspondence/message-06.md`)
already came from the owner's 2026-09-21 REST fetch -- already on disk, no new pull was needed even
then. This unblocks S2 to start alongside S1, per the mathematician's own conditional -- not started
in this pass (S1 alone surfaced two real bugs worth getting right first), but ready to begin next.

## Open questions awaiting the mathematician
See `docs/correspondence/` for the full history (currently `message-01` through `message-11`,
plus `answer-01/02/03`, `question-01`, `reply-1.4`). Nothing is currently blocking further work;
S1's discovery/stability/economic-gate results (once run against real data) are what's pending
review before freeze/forward-test.
