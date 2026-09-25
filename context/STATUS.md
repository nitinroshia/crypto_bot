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

## What's built and self-tested (`user_data/analysis/`, 21 tools, all passing via `selftest_all.sh`)
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
- **Item 2 (not started):** `--end-date` guard, holdout lock, registry (pair-qualified naming
  `<task>-ETHUSDT`/`<task>-BTCUSDT` already decided, not yet built), by-year/leave-one-year-out,
  the section-6 stability check (90-day tiling + one-sided Stouffer -- **confirmed in scope for
  item 2**, since it's what replaces the current wrong `research_cli.evaluate_fixed_lag` verdict,
  not separate follow-on work), freeze manifest, forward-test command. The forward-test command
  must report step 5's statistical criteria and step 3's holdout requirement as two separate
  labeled results (never collapsed into one pass/fail), and must auto-log the ETH/FDUSD
  holdout-exposure disclosure note on every run. This is the next thing to build.

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
The owner was asked to rerun `breakeven_table.py` once more (median |return| was just added) --
`wo1.4_breakeven_v4.log` may already be at the repo root or about to be. If so, just confirm the
median figures look sane (same shape as before: reasonable at 1d/4h/1h, the 15m story unchanged)
and consider this thread done; no action needed unless something looks off. After that: **start
item 2**, beginning with the registry and `--end-date` guard.

## Open questions awaiting the mathematician
See `docs/correspondence/` for the full history (currently `message-01` through `message-07`,
plus `answer-01/02`, `question-01`, `reply-1.4`). Nothing is currently blocking item 2.
