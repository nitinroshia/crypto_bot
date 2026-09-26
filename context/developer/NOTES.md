# Developer notes

Working scratch for the developer role. Never authoritative on its own -- if anything here
conflicts with `docs/` or `context/STATUS.md`, those win. This file exists for technical
continuity across sessions: conventions, gotchas, and decisions that don't belong in a status
summary but matter for not repeating past mistakes.

## Engineering conventions (apply to every new tool)
- Argparse CLI + a `--self-test` flag, synthetic data with known ground truth, wired into
  `selftest_all.sh`. 21 tools pass as of this writing. Never skip the self-test to save time --
  it's caught real bugs every single time it's been taken seriously (see gotchas below).
- Self-test scratch uses the system temp dir (`tempfile.TemporaryDirectory()`, no `dir=`
  override). Project-local `temp/` is discontinued; don't reintroduce a `_selftest_tmp()`-style
  helper that points back at it.
- State every interpretive choice explicitly in the docstring, run both readings and label them
  when a spec genuinely allows two, never silently pick one. This project's culture rewards
  showing your work over being fast.
- Discovery cutoff is `2025-08-31 23:59:59 UTC`, everywhere. Always filter the base series to
  `<= cutoff` *before* computing any derived return -- never filter the return series after the
  fact, or a return spanning the boundary can leak in.
- Cost assumptions (from `costs.py`): base round trip 0.24%, stress round trip 0.30%.

## Gotchas actually hit (don't re-discover these)
- **`stats_fingerprint.get_nonoverlapping_returns`'s returned Series index is a raw row
  *position* from the source dataframe (`df[col].iloc[::k]` preserves original positional
  labels), not a date.** Printing it directly as if it were a date is a real bug I made and
  fixed in `breakeven_table.py` -- map back through the source dataframe (`df.loc[idx, "date"]`)
  to get an actual calendar date. If you see a suspiciously large or small integer where a date
  should be, this is almost certainly why.
- `resample.resample_ohlcv_traded`'s parameter is named `df_1m` but the function has no actual
  1-minute assumption in it -- confirmed on synthetic data that it generalizes correctly to any
  finer-than-target source (used for BTC/USDT 15m, derived from its native 5m, since nothing in
  the queue needs BTC/USDT 1m). Don't assume a tool's parameter name is a hard constraint;
  check the actual logic.
- `walkforward.py` is explicitly "structure only" (its own module docstring) -- a generic
  splitter with no fit/validate values wired in. Its self-test uses 270/90 days as a round-number
  demo ("9-month fit / 3-month validate"), which is NOT the production 365/90. Item 2 is what
  wires in the real values; don't assume they're already there.
- `_mk_1d`-style synthetic-price helpers that build `close = 100 * exp(cumsum(returns))` are
  compounding LOG returns, but `get_nonoverlapping_returns` measures SIMPLE returns
  (`.pct_change()`). Negligible difference for small returns, NOT negligible for a deliberately
  large injected test value (e.g. a synthetic outlier) -- convert with `exp(x) - 1` when asserting
  an exact match.
- `sample-bot`, `handover-2026-09-20`, and the other four legacy repos are gone from GitHub
  (owner removed them once migrated). Don't reference them as a source for anything going
  forward; everything that mattered is under `docs/` in this repo now.

## Naming conventions worth knowing
- `docs/handoffs/HANDOFF_developer-*.md` (now `v2.1.md`, `v2.2.md`) are **mathematician-authored**
  documents addressed to the developer -- the developer does not add a "v2.3" to this sequence.
  Developer-authored replies go in `docs/correspondence/` instead.
- `docs/correspondence/message-NN.md` is the developer's own numbered sequence (currently
  01 through 07); the mathematician's own outgoing messages use their own "vN" numbering
  (seen up to v6) and sometimes land as `answer-NN`/`question-NN`. These are two different
  counters -- don't try to unify them.
- `context/mathematician/NOTES.md` is the mathematician's actively-maintained working file.
  The developer reads it when needed (e.g. it was the actual source of the "section 3" break-even
  table the mathematician referenced) but never edits it directly -- respond via
  `docs/correspondence/` instead and let the mathematician fold it in on their end.

## Decided but not yet built
- Forward-test command must report step 5's statistical criteria (one-sided p<0.05, estimate
  >= half the discovery estimate) and step 3's holdout requirement (frozen rule net-positive at
  stress cost) as two separate labeled results, and must auto-log the ETH/FDUSD holdout-exposure
  disclosure note on every run, unconditionally.
- The actual holdout lock is now built (`holdout_lock.py`, see below) -- this bullet used to flag
  it as open; it isn't anymore, but nothing has called it for a real candidate yet.

## Item 2 pieces already built (2026-09-26) -- read before touching either module
- `cutoff.py`: the `--end-date` guard. One rule -- "keep a bar iff its label (open time) <= the
  cutoff" -- reproduces all four of section 6's worked last-usable-bar examples (1d/1h/15m/5m)
  without a per-timeframe table; see its self-test if a fifth timeframe ever needs checking.
  `origin_window_side(entry_time, window_end_label, ...)` takes bar LABELS for both arguments,
  never close timestamps -- passing a close time will wrongly reject legitimate discovery windows
  ending on the last usable bar (see the module docstring's "INTERPRETIVE CHOICE" note). Wired
  into `research_cli.py` as `load_all_dataframes(..., end_date=...)` and the CLI's `--end-date`
  flag; `--end-date` takes any UTC date/timestamp (it's not hardcoded to 2025-08-31), so pass
  `cutoff.CUTOFF`'s value explicitly for a real discovery run.
- `registry.py`: append-only JSONL (`user_data/analysis/results/registry.jsonl`, not yet created
  for real -- nothing has actually been appended to it outside this module's own self-test).
  Family names must be `<TASK>-ETHUSDT`/`<TASK>-BTCUSDT` for every status except `history` and
  `void_pre_fix` (the two used to import pre-existing ETH/FDUSD-era runs, which predate the
  naming scheme -- `validate_family` exempts them on purpose, don't "fix" this later). Gotcha:
  `holm_at_step(records, pair, step)` reads each family's SINGLE MOST RECENT record overall (not
  its most recent record among only-that-step records) -- a family that has moved on to a later
  step no longer counts at an earlier one, so querying an earlier step naturally empties out as
  candidates graduate. This was a real bug caught by the self-test (naive "most recent among
  matching-status records" logic double-counted a family at both its old and new step) --
  don't revert to that simpler-looking version if refactoring this function.
- Neither module has been imported into `research_cli.py`'s formula-running path for actual
  registry writes yet (no formula run currently appends anything) -- that wiring is stability
  check / freeze-manifest work, still ahead.
- `holdout_lock.py`: the actual one-shot enforcement (not just an audit log). Gotcha:
  `unlock_holdout_for_forward_test` checks the registry for a PRIOR `holdout_consumed` record for
  the same (family, pair) and refuses with `HoldoutAlreadyConsumedError` if one exists -- this is
  what makes "once per candidate" real rather than a comment. It deliberately calls
  `databundle.load_bundle` directly (bypassing `cutoff.py`'s guard entirely, on purpose) since the
  whole point is that this is the one place allowed to return the untruncated series. The
  ETH/FDUSD 2026-exposure disclosure note (`DISCLOSURE_NOTE_ETHUSDT`, verbatim from mathematician
  NOTES.md section 6 -- don't paraphrase it if it's ever touched) is logged only for
  `pair="ETHUSDT"`; a BTCUSDT call still gets a `holdout_consumed` audit record, just with
  `detail["note"] = None`. `log_descriptive_access` is unrelated -- it's for the OTHER kind of
  post-cutoff read section 6 allows (purely descriptive tools, no returns computed) and gates
  nothing; it just appends the fixed "descriptive, no returns computed" note. Two-step pattern
  worth knowing before the forward-test command is built: `unlock_holdout_for_forward_test`'s own
  record has `detail["p_value"] = None` (it only gates access, it doesn't compute anything) --
  the forward-test command must append a SECOND `holdout_consumed` record once it has the real
  verdict; `registry.holm_at_step` already picks up each family's most-recent record, so this
  resolves correctly on its own, no special-casing needed. Not yet wired into any data-batch tool
  or into research_cli.py.
- `nonstationarity.py`: by-year/leave-one-year-out. Gotcha worth remembering: a period below the
  120-day threshold is excluded from BEING DROPPED in leave-one-out (it's shown in `by_year_table`
  but `leave_one_out`/`year_driven`/`sign_agreement` never key on it) -- but its rows are NEVER
  removed from any other period's leave-one-out subset, or from the pooled estimate. Don't
  "simplify" this later into filtering sub-threshold rows out of the data entirely; that would
  silently change the pooled estimate itself, which section 6 explicitly says must not happen.
  "days_covered" is distinct calendar dates present, not `n` (row count) and not a period-length
  constant -- the two self-test datasets both use daily-frequency synthetic data specifically so
  n and days_covered happen to be equal there; don't assume that equality holds for intraday data.
  `estimator` takes a DataFrame slice and returns a float; nothing in this module computes an
  actual candidate's estimate itself -- that's every individual formula's own job. Not yet wired
  into any candidate's actual reporting.
- `blocks.py`: `tile_blocks` is shared by the stability check (built) and the economic gate (not
  yet built) -- if step 3 needs its own tiling, reuse this, don't reimplement it. Gotcha that cost
  a real bug during development: `is_final_partial` must compare against the data's inferred
  CALENDAR COVERAGE (last label + inferred bar-width), not the last label itself -- otherwise an
  exact multiple of block_days (e.g. 270 daily rows = 3 full 90-day blocks) gets its last block
  wrongly flagged partial, since bar labels understate coverage by one bar-width. Bar width is
  inferred from the data's own median spacing (works for any timeframe), not assumed to be 1 day.
- `stability_check.py`: built on `blocks.py`. Gotchas: `block_test(subset) -> (z, p_two_sided)`
  must return a genuine standard-normal z (not just any signed magnitude) or the Stouffer
  combination (`sum(oriented_z) / sqrt(k)`) is not statistically valid -- this module can't verify
  that property, it's on whoever writes the real S1/S2 `block_test`. The veto
  (`any_significant_opposite`) is checked independently of the combined result -- it can fail a
  candidate that would otherwise pass, don't merge the two checks into one condition. The final
  partial block never enters either the combination or the veto, however extreme its value.
  `evaluate_fixed_lag` in research_cli.py is UNRELATED to this and was not modified -- it's Item
  1's own single fit/validate lag-replication check for the leadlag formula, not an S1/S2
  stability mechanism; nothing currently routes S1/S2 through it since no S1/S2 formula exists yet.
  Don't wire the two together later on the assumption they're doing the same job.
- `rule_evaluator.py` + `economic_gate.py`: read `rule_evaluator.py`'s module docstring in full
  before touching either -- it documents a real interpretive fork in section 6's own text (the
  "starts flat / forced exit" language for "a discovery block" vs. "a position may carry across a
  block boundary at no cost") and how it was resolved (section 6's own self-test requirement --
  "charged once, not twice" -- only holds under a continuous-run-then-slice design, not independent
  per-block resets). This is flagged to the mathematician (message-10.md, not yet sent as of this
  writing) as a financial-model interpretive choice that should be confirmed, not silently treated
  as settled. Gotcha that cost a real bug during development, twice over: (1) `held_position[0]`
  must be 0 by construction (`signal.shift(1).fillna(0)`) -- the segment "starts flat" and there is
  no bar before it to have supplied a signal, so the FIRST interval of any segment always earns
  zero regardless of what `signal[0]` says; a test that assumes "always-long over n bars compounds
  n-1 intervals" is off by one for exactly this reason (it's n-2 contributing intervals -- see
  `rule_evaluator.py`'s drift self-test for the corrected arithmetic). (2) when building MULTI-BLOCK
  synthetic test data, never concatenate independently-generated per-block price paths that each
  restart at the same base price (e.g. 100) -- that injects a fake, huge discontinuity at every
  seam that swamps any real drift signal. Build ONE continuous price path across all blocks (a
  single cumulative random walk, with per-block DRIFT REGIME allowed to vary) -- see
  `economic_gate.py`'s self-test `make_continuous_path` helper. `economic_gate`'s return dict casts
  every value to native Python `bool`/`float` explicitly -- comparisons on pandas/numpy values
  produce `numpy.bool_`, and `numpy.bool_(True) is True` is `False` in Python; an `is True`
  assertion against an uncast value will silently fail even when the underlying logic is correct
  (this bit the self-test once already). Neither module is wired into research_cli.py, the
  registry, or an actual S1/S2 formula yet -- no such formula exists, so nothing calls either of
  these for a real candidate.

## Loose ends, not blocking anything
- Three files moved during the 2026-09-22 migration were never read/classified:
  `docs/archive/owner-notes/grep_stale.txt`, `dev-README_workorder01.md`,
  `dev-README_workorder12.md`, `phd-README_workorder01.md` (the last one has a different size
  than the `dev-` copy of the same filename, unexplained). Low priority; ask the owner if it
  ever becomes relevant.
- Funding first-settlement dates (already answered, in case asked again): ETHUSDT 2019-11-27,
  BTCUSDT 2019-09-10.

## Working relationship notes
- The owner runs every terminal command themselves and wants exact copy-pasteable commands, not
  descriptions of what to run. They've asked for this explicitly and repeatedly -- always give
  the literal command block.
- The developer has git/network read access (can clone the public repo directly to verify state)
  but no push credentials -- the owner does all `git add`/`commit`/`push` themselves. Prepare
  files and a suggested commit message; never assume something is live until the owner confirms
  it's pushed.
- Python: 3.12.7, pinned in `README.md`.
