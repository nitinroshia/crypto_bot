# Project status

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

## What's built and self-tested (`user_data/analysis/`, 25 tools, all passing via `selftest_all.sh`)
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
- **Item 2 (in progress, 4 of ~6 pieces landed 2026-09-26):**
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
  - NOT YET BUILT: the section-6 stability check (90-day tiling + one-sided Stouffer --
    **confirmed in scope for item 2**, since it's what replaces the current wrong
    `research_cli.evaluate_fixed_lag` verdict, not separate follow-on work), the S1/S2 economic
    gate, freeze manifest, forward-test command (which will be the first real caller of
    `holdout_lock.unlock_holdout_for_forward_test`). The forward-test command must report step 5's
    statistical criteria and step 3's holdout requirement as two separate labeled results (never
    collapsed into one pass/fail). This is the next thing to build.

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
The breakeven-median rerun thread is closed (see "Live finding" above; `wo1.4_breakeven_v4.log`
was reviewed, shape as expected). The mathematician's platform (Claude, not ChatGPT) is corrected
in this file's own "Repo and roles" section (v7, 2026-09-25) -- see `docs/correspondence/message-09.md`.
Item 2's registry, `--end-date` guard, holdout lock, and by-year/leave-one-year-out machinery are
now built and self-tested (above). Next: the section-6 stability check (90-day tiling + one-sided
Stouffer).

## Open questions awaiting the mathematician
See `docs/correspondence/` for the full history (currently `message-01` through `message-07`,
plus `answer-01/02`, `question-01`, `reply-1.4`). Nothing is currently blocking item 2.
