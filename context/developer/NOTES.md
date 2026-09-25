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
- Registry naming for item 2: `<task>-ETHUSDT`, `<task>-BTCUSDT` (e.g. `S1-ETHUSDT`). Settled
  in work order 1.4 so item 2 doesn't need to retrofit it.
- Forward-test command must report step 5's statistical criteria (one-sided p<0.05, estimate
  >= half the discovery estimate) and step 3's holdout requirement (frozen rule net-positive at
  stress cost) as two separate labeled results, and must auto-log the ETH/FDUSD holdout-exposure
  disclosure note on every run, unconditionally.

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
