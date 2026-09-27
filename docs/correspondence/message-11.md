# Developer report: item 2 complete

2026-09-26.

Item 2 is fully built and self-tested: all ~6 pieces from section 6 landed, 31 self-tests passing
via `selftest_all.sh` (up from 21 at the start of this work). Summary, in build order:

1. `cutoff.py` -- the `--end-date` guard (hard truncation to the discovery cutoff, wired into
   `research_cli.py`) and `origin_window_side` (discovery/holdout/straddle classification).
2. `registry.py` -- the append-only JSONL registry, pair-qualified family naming, `cumulative_count`
   and `holm_at_step` (excluding history/void_pre_fix/descriptive_access from both).
3. `holdout_lock.py` -- `unlock_holdout_for_forward_test` (one-shot per candidate, auto-logs the
   ETH/FDUSD 2026-exposure disclosure note for ETHUSDT) and `log_descriptive_access` for the
   non-hypothesis-specific reads.
4. `nonstationarity.py` -- by-year/leave-one-year-out, the year-driven red flag (magnitude-halving
   or sign-flipping), and the 120-day partial-year exemption.
5. `blocks.py` + `stability_check.py` -- the 90-day tiling shared with the economic gate, and the
   Stouffer-combination stability check with the opposite-block veto.
6. `rule_evaluator.py` + `economic_gate.py` -- the position/cost/return engine and the S1/S2
   economic gate (pooled net return + 70%-of-blocks pass rate). The evaluation-segment/block-boundary
   question from `message-10.md` is resolved (`answer-03.md`) and recorded directly in
   `rule_evaluator.py`'s own docstring, including the confirmed guidance for the holdout (below).
7. `freeze_manifest.py` + `forward_test.py` -- the one-shot freeze (timestamp/commit/direction/
   estimate/dispersion) and the two-phase forward-test command (a descriptive readiness check that
   never burns the one-shot holdout look, then the actual test: SE scaled from the frozen
   dispersion, one-sided significance + magnitude, and the step-3-at-holdout economic check --
   reported as two separate results, never merged into one verdict, per the standing requirement).

## What this is, and isn't, yet

All of this is machinery, proven against synthetic data in each module's own self-test. **Nothing
has been run on a real candidate** -- there is no S1/S2 or Task 3 formula in `research_cli.py`'s
`FORMULAS` dict yet, so none of item 2's registry writes, holdout access, or freeze/forward-test
calls have happened for real. Every generic hook a real formula will need to supply is already
identified in the code (an `estimator`, a `count_origins`, a `signal_fn`/rule, a `block_test` for
the stability check) -- this was deliberate, so item 2's machinery doesn't need touching once a
formula exists to plug into it.

## The ask

What's the priority now -- building an actual S1/S2 formula through this pipeline end to end (which
would be the first real exercise of everything above), something else in the backlog, or is there a
review you want to do on item 2 itself before anything is built on top of it?
