#!/bin/bash
# diag_state.sh -- READ-ONLY diagnostic for the crypto_bot repo.
#
# It does NOT change, delete, commit or push any of your files or branches.
# (The one thing it does is `git fetch`, which only downloads GitHub's latest state
#  into the hidden .git folder so it can be compared with your folder.)
#
# What it prints: where your folder stands against GitHub, what is modified or untracked,
# whether your local registry.jsonl has lines GitHub does not have, and the list of tracked files.
#
# Usage:   bash diag_state.sh                      (assumes ~/apps/crypto_bot)
#          bash diag_state.sh /path/to/crypto_bot
# Output:  printed on screen AND saved to ~/Desktop/crypto_bot_diag.txt
#          Paste the output into the chat (it is plain text, about 100-250 lines).

REPO="${1:-$HOME/apps/crypto_bot}"
OUT="$HOME/Desktop/crypto_bot_diag.txt"
REG="user_data/analysis/results/registry.jsonl"

if [ ! -d "$REPO/.git" ]; then
  echo "FAIL: $REPO is not a git repository. Re-run as: bash diag_state.sh /path/to/crypto_bot"
  exit 1
fi
cd "$REPO" || exit 1

TMP_ORIGIN_REG="$(mktemp)"
trap 'rm -f "$TMP_ORIGIN_REG"' EXIT

{
echo "== crypto_bot diag, $(date -u +%Y-%m-%dT%H:%M:%SZ) UTC =="
echo "repo folder: $(pwd)"
echo
echo "-- remote (any password/token in the URL is masked):"
git remote -v | sed -E 's#(https?://)[^/@ ]+@#\1***@#'
echo
echo "-- fetching GitHub's latest state (read-only)..."
git fetch origin 2>&1 | tail -3
echo
echo "-- branch and short status:"
git status -sb | head -40
echo
echo "-- local HEAD:  $(git rev-parse --short HEAD 2>/dev/null)"
echo "-- origin/main: $(git rev-parse --short origin/main 2>/dev/null)"
echo "-- commits only here / only on GitHub (left right): $(git rev-list --left-right --count HEAD...origin/main 2>/dev/null)"
echo
echo "-- last 5 commits on this folder:"
git log --oneline -5 2>/dev/null
echo
echo "-- last 5 commits on GitHub (origin/main):"
git log --oneline -5 origin/main 2>/dev/null
echo
echo "-- tracked files that differ from GitHub's version (stat, max 30 lines):"
git diff --stat origin/main 2>/dev/null | tail -30
echo
echo "-- modified or untracked files in this folder (git status --porcelain, max 60 lines):"
git status --porcelain | head -60
echo
echo "-- stash entries (saved-away changes):"
git stash list | head -10
echo
echo "-- registry.jsonl: local vs GitHub"
if [ -f "$REG" ]; then
  echo "local lines:  $(wc -l < "$REG" | tr -d ' ')"
else
  echo "local file missing: $REG"
fi
if git show "origin/main:$REG" > "$TMP_ORIGIN_REG" 2>/dev/null; then
  echo "GitHub lines: $(wc -l < "$TMP_ORIGIN_REG" | tr -d ' ')"
  if [ -f "$REG" ]; then
    echo "lines that exist only locally (first 200 characters of each, max 10):"
    diff "$TMP_ORIGIN_REG" "$REG" | grep '^>' | cut -c1-202 | head -10
  fi
else
  echo "GitHub has no such file on origin/main"
fi
echo
echo "-- key files present locally:"
for f in user_data/analysis/formula_s1.py user_data/analysis/run_s1.py user_data/analysis/registry.py \
         user_data/analysis/selftest_all.sh context/STATUS.md context/developer/NOTES.md \
         context/mathematician/NOTES.md docs/handoffs/v2.3.md docs/correspondence/message-12.md \
         docs/work-orders/1.5.md user_data/analysis/stability_reference.py docs/PROTOCOL.md; do
  if [ -f "$f" ]; then echo "  present: $f"; else echo "  MISSING: $f"; fi
done
echo
echo "-- python in the project's virtual environment:"
if [ -x .venv/bin/python3 ]; then .venv/bin/python3 --version 2>&1; else echo "  .venv/bin/python3 not found"; fi
echo
echo "-- raw data files (names and sizes):"
ls -la user_data/data/binance_raw 2>/dev/null | head -30 || true
echo
echo "-- tracked files ($(git ls-files | wc -l | tr -d ' ') total):"
git ls-files
echo
echo "== end of diag =="
} 2>&1 | tee "$OUT"

echo
echo "Saved a copy to $OUT"
