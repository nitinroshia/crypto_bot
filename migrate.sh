#!/bin/bash
set -euo pipefail
cd ~/apps/crypto_bot
echo "Running in: $(pwd)"

# Capture the pre-item-1 baseline for Part 3 BEFORE Part 1 deletes temp/sample-bot.
mkdir -p /tmp/pre-item1-baseline
if [ -d temp/sample-bot ]; then
  cp temp/sample-bot/README.md temp/sample-bot/project_context.md temp/sample-bot/leadlag.py \
     temp/sample-bot/multitest.py temp/sample-bot/research_cli.py temp/sample-bot/selftest_all.sh \
     /tmp/pre-item1-baseline/
  echo "Captured pre-item-1 baseline from temp/sample-bot for Part 3."
else
  echo "temp/sample-bot not found -- Part 3 (baseline commit) will be skipped."
fi

# =====================================================================================
# PART 1 -- reorganize docs/ out of temp/, discontinue temp/ for the audit repos
# =====================================================================================
mkdir -p docs/work-orders docs/handoffs docs/closeouts docs/architecture \
         docs/correspondence docs/history docs/archive/owner-notes \
         context/developer context/mathematician

mv temp/dump-sept/workorder-01.md   docs/work-orders/01.md
mv temp/dump-sept/workorder-1.1.md  docs/work-orders/1.1.md
mv temp/dump-sept/workorder-1.2.md  docs/work-orders/1.2.md
mv temp/dump-sept/workorder-1.3.md  docs/work-orders/1.3.md

mv temp/dump-sept/HANDOFF_developer.md      docs/handoffs/v2.1.md
mv temp/dump-sept/HANDOFF_developer-1.3.md  docs/handoffs/v2.2.md

mv temp/dump-sept/workorder-01-complete.md   docs/closeouts/01.md
mv temp/dump-sept/CLOSEOUT_workorder-1.2.md  docs/closeouts/1.2.md
mv temp/dump-sept/CLOSEOUT_workorder-1.3.md  docs/closeouts/1.3.md

mv temp/dump-sept/idea-01.md docs/architecture/idea-01-proposal.md
mv temp/dump-sept/idea-02.md docs/architecture/idea-02-ratification.md

mv temp/dump-sept/question-01.txt docs/correspondence/question-01.md
mv temp/dump-sept/answer-01.txt   docs/correspondence/answer-01.md
mv temp/dump-sept/answer-02.txt   docs/correspondence/answer-02.md
mv temp/dump-sept/message-01.txt  docs/correspondence/message-01.md
mv temp/dump-sept/message-02.txt  docs/correspondence/message-02.md
mv temp/dump-sept/message-03.txt  docs/correspondence/message-03.md
mv temp/dump-sept/message-04.txt  docs/correspondence/message-04.md
mv temp/dump-sept/message-05.txt  docs/correspondence/message-05.md

mv temp/dump-sept/terminal-01.txt         docs/history/2026-09-19_wo1.1-terminal-01.txt
mv temp/dump-sept/terminal-02.txt         docs/history/2026-09-19_wo1.1-terminal-02.txt
mv temp/dump-sept/terminal-03.txt         docs/history/2026-09-19_wo1.1-terminal-03.txt
mv temp/dump-sept/terminal-04.txt         docs/history/2026-09-19_wo1.1-terminal-04.txt
mv temp/dump-sept/self-test_result-01.txt docs/history/2026-09-19_wo1.1-self-test-result.txt
mv temp/dump-sept/symbol_filters.json     docs/history/2026-09-19_symbol-filters-snapshot.json
mv temp/dump-sept/tree-01.txt             docs/history/2026-09-19_tree-before-resample-fix.txt
mv temp/dump-sept-01/tree-01.txt          docs/history/2026-09-19_tree-after-resample-fix.txt
mv temp/dump-sept-02/extension_dryrun.log docs/history/2026-09-19_extension-dryrun.log
mv temp/dump-sept-02/extension_run.log    docs/history/2026-09-19_extension-run.log

mv temp/dump-sept/resample_checks.json    docs/history/2026-09-19_resample-checks-snapshot-A.json
mv temp/dump-sept-02/resample_checks.json docs/history/2026-09-19_resample-checks-snapshot-B.json
mv temp/dump-sept/task0_report.json       docs/history/2026-09-19_task0-report-snapshot-A.json
mv temp/dump-sept/task0_report-01.json    docs/history/2026-09-19_task0-report-snapshot-B.json
rm  temp/dump-sept/task0_report-02.json
mv temp/dump-sept-02/task0_report.json    docs/history/2026-09-20_task0-report-snapshot-C.json
mv temp/dump-sept/leadlag_summary.json    docs/history/2026-09-19_leadlag-summary-pre-rename.json
mv temp/dump-sept-02/fingerprints.json    docs/history/2026-09-20_fingerprints-snapshot.json
mv temp/dump-sept/backtest.sh             docs/history/2026-09-19_backtest-pre-addendum.sh
mv temp/dump-sept/data_ranges.json        docs/history/2026-09-19_data-ranges-snapshot.json

mv temp/dump-sept/terminal-05.txt     docs/history/2026-09-20_wo1.2-terminal-05.txt
mv temp/dump-sept/terminal-06.txt     docs/history/2026-09-20_wo1.2-terminal-06.txt
mv temp/dump-sept/terminal-07.txt     docs/history/2026-09-20_wo1.3-terminal-07.txt
mv temp/dump-sept/terminal-08.txt     docs/history/2026-09-21_wo1.3-terminal-08.txt
mv temp/dump-sept/tree-02.txt         docs/history/2026-09-20_tree-verification.txt
mv temp/handover-2026-09-20/ls_lR.txt docs/history/2026-09-21_handover-snapshot-ls-lR.txt

mv temp/klines_batch_dryrun.log           docs/history/2026-09-21_klines-batch-dryrun.log
mv temp/klines_batch_run.log              docs/history/2026-09-21_klines-batch-run.log
mv temp/dump-sept/klines_batch_verify.log docs/history/2026-09-21_klines-batch-verify.log
mv temp/dump-sept/funding_dryrun.log      docs/history/2026-09-21_funding-dryrun.log
mv temp/dump-sept/funding_run.log         docs/history/2026-09-21_funding-run.log
mv temp/dump-sept/gaps_eth_1h.log         docs/history/2026-09-21_gaps-eth-1h.log
mv temp/dump-sept/liquidity_2026.log      docs/history/2026-09-21_liquidity-2026.log
mv temp/dump-sept/selftest_run.log        docs/history/2026-09-21_selftest-run.log
mv temp/ls-l.txt                          docs/history/2026-09-21_ls-l.txt
mv temp/python-version.txt                docs/history/2026-09-21_python-version.txt

mv grep_stale.txt                 docs/archive/owner-notes/grep_stale.txt
mv wo13_verify.log                docs/archive/owner-notes/wo13_verify.log
mv temp/dev/README_workorder01.md docs/archive/owner-notes/dev-README_workorder01.md
mv temp/dev/README_workorder12.md docs/archive/owner-notes/dev-README_workorder12.md
mv temp/phd/README_workorder01.md docs/archive/owner-notes/phd-README_workorder01.md

rm -rf temp/dump-sept temp/dump-sept-01 temp/dump-sept-02 temp/handover-2026-09-20 \
       temp/sample-bot temp/incoming temp/dev temp/phd temp/selftest \
       temp/funding_dryrun.log temp/funding_run.log temp/gaps_eth_1h.log \
       temp/klines_batch_verify.log temp/liquidity_2026.log temp/selftest_run.log
rm -f extension_dryrun.log extension_run.log

echo "PART 1 done. temp/ remaining (should be empty):"; find temp -mindepth 1 2>/dev/null

# =====================================================================================
# PART 2 -- .gitignore, then git init (safe/idempotent if a repo already exists here)
# =====================================================================================
cat > .gitignore <<'GITIGNORE'
# Python / compiled / cache

 **pycache**/\
 \*.py\[cod\]\
 \*.pyo\
 .pytest\_cache/

 # Python virtual environments

 .venv/\
 venv/\
 env/\
 ENV/

 # Python packaging

 \*.egg-info/\
 dist/\
 build/\
 \*.egg

 # Backup copies made during data-batch runs

 \*.bak

 # Freqtrade generated data -- regeneratable or purely local

 user\_data/data/\
 user\_data/logs/\
 user\_data/backtest\_results/\
 user\_data/hyperopt\_results/\
 user\_data/hyperopts/\
 user\_data/freqaimodels/\
 user\_data/notebooks/\
 user\_data/plot/

 # Freqtrade runtime databases

 user\_data/_.sqlite\
 user\_data/_.sqlite-shm\
 user\_data/\*.sqlite-wal

 # Order-level backtest artifacts -- git/LFS policy not yet decided

 # (owner, 2026-09-22: "keep these files for now").

 # Left on disk, untracked, until that call is made.

 user\_data/analysis/results/runs/\*\_orders.csv

 # Analysis results

 # Other analysis results remain tracked intentionally for now.

 # Local secrets

 .env\
 .env.\*\
 !.env.example

 # OS / editor files

 .DS\_Store\
 .vscode/\
 .idea/

 # Temporary / editor files

 \*.tmp\
 \*.swp\
 \*.swo\
 \*\~\
 temp/
GITIGNORE

git init
git add .gitignore docs/ context/
git commit -m "[dev] docs: import work orders, handoffs, closeouts, correspondence and history from the legacy repos; add .gitignore" || echo "(nothing to commit -- check if this repo already has these files)"

echo "PART 2 done."

# =====================================================================================
# PART 3 -- two-stage commit so the item-1 change shows up in git history instead of
#           vanishing into one flat import. If you'd rather skip this and just import
#           everything as-is in one commit, delete this whole PART 3 block and run
#           PART 4 directly -- nothing else depends on it.
# =====================================================================================
STALE_SRC=/tmp/pre-item1-baseline
if [ -f "$STALE_SRC/leadlag.py" ]; then
  mkdir -p /tmp/current-snapshot
  cp README.md project_context.md /tmp/current-snapshot/
  cp user_data/analysis/leadlag.py user_data/analysis/multitest.py \
     user_data/analysis/research_cli.py user_data/analysis/selftest_all.sh /tmp/current-snapshot/

  cp "$STALE_SRC/README.md" ./README.md
  cp "$STALE_SRC/project_context.md" ./project_context.md
  cp "$STALE_SRC/leadlag.py" "$STALE_SRC/multitest.py" "$STALE_SRC/research_cli.py" \
     "$STALE_SRC/selftest_all.sh" user_data/analysis/
  git add README.md project_context.md user_data/analysis/leadlag.py \
          user_data/analysis/multitest.py user_data/analysis/research_cli.py \
          user_data/analysis/selftest_all.sh
  git commit -m "[dev] baseline: WO1.2 developer-handoff state (reconstructed from the sample-bot audit, before item 1)"

  cp /tmp/current-snapshot/README.md ./README.md
  cp /tmp/current-snapshot/project_context.md ./project_context.md
  cp /tmp/current-snapshot/leadlag.py /tmp/current-snapshot/multitest.py \
     /tmp/current-snapshot/research_cli.py /tmp/current-snapshot/selftest_all.sh user_data/analysis/
  rm -rf /tmp/current-snapshot
  echo "PART 3 done -- baseline commit created."
else
  echo "PART 3 skipped: $STALE_SRC not found. Edit STALE_SRC above and rerun this block, or just proceed to PART 4."
fi

# =====================================================================================
# PART 4 -- commit the current, live state (item 1 + data-batch tools + everything else)
# =====================================================================================
cat > context/STATUS.md <<'STATUSMD'
# Project status

Last updated: 2026-09-22, by the developer (Claude).

## Where things stand
- Item 1 (selection-rule change: min-p, no significance pre-filter) is built and self-tested.
- Data-batch tools are built and verified: funding fetcher (REST + data.binance.vision fallback),
  gap locator, liquidity table.
- ETH/USDT 5m and BTC/USDT 1h/1d klines extended; funding data fetched for both symbols;
  128 missing ETH/USDT hours confirmed to coincide with 128 missing BTC/USDT hours
  (exchange-wide outage, not ETH-specific).
- The resample "filled vs traded" bug (WO1.1) is fixed and shipped; historical pre-fix
  snapshots are preserved under docs/history/.
- This repo structure (docs/, context/, .gitignore) replaces the five legacy repos
  (dump-sept, dump-sept-01, dump-sept-02, handover-2026-09-20, sample-bot), which the
  owner is removing from GitHub. See docs/architecture/idea-01-proposal.md and
  idea-02-ratification.md for why.

## Next
- Item 2: --end-date guard, holdout lock, registry, by-year/leave-one-year-out checks,
  freeze manifest, forward-test command (work order 1.2/1.3, clarifications 1.4/1.5).
- Open: git/LFS policy for the two large *_orders.csv files in
  user_data/analysis/results/runs/ (currently untracked, see .gitignore).

## Open questions awaiting the mathematician
See docs/correspondence/ for the full A1-A5/B1-B5/N1-N4 history. Nothing is currently
blocking item 2.
STATUSMD

cat > context/open-questions.md <<'OQMD'
# Open questions

Consolidating the full A1-A5/B1-B5/N1-N4 history from docs/correspondence/ into this
indexed format is a separate, upcoming task -- not done automatically as part of this
migration, since it requires reading and cross-linking every prior ruling rather than
just moving a file. Until then, docs/correspondence/ is the source of truth for what
was asked and what was ruled.
OQMD

cat > context/developer/NOTES.md <<'DEVMD'
# Developer notes

Working scratch for the developer role. Never authoritative on its own -- if anything
here conflicts with docs/ or context/STATUS.md, those win (see idea-02-ratification.md
section 5 for the authority order).
DEVMD

cat > context/mathematician/NOTES.md <<'MATHMD'
# Mathematician notes

Working scratch for the mathematician role. Never authoritative on its own -- see
context/developer/NOTES.md for the same rule.
MATHMD

git add -A
git commit -m "[dev] item 1: min-p selection rule (leadlag/multitest/research_cli); WO1.2 data-batch tools (funding, gap locator, liquidity table); README pyenv pin; context/ skeleton (STATUS, open-questions, per-agent notes)"

echo
echo "PART 4 done. Log so far:"
git log --oneline
echo
echo "Working tree status (should be clean or only show ignored/untracked items you expect):"
git status
