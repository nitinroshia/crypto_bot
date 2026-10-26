#!/bin/bash
# deliveries/11/apply.sh -- D2, Work Order 1.7 step 1: formula_t3.py with self-tests and the FULL Task 3 acceptance run.
#
# Put apply.sh, formula_t3.py, selftest_all.sh, STATUS.md, NOTES.md and message-23.md together in
# ~/apps/crypto_bot/deliveries/11/ and run:   bash ~/apps/crypto_bot/deliveries/11/apply.sh
# It writes NO registry record and touches no data file or the holdout (the live registry is hashed before and after). What it does:
#   1. checks the SHA-256 of the delivered files, the folder (clean, on main, user_data/analysis byte-identical to commit 63edecf),
#      that the live registry is the 26-line file, and refuses if temp/secret_keys.txt is tracked or committed (it never opens it);
#   2. backs up what it replaces, puts formula_t3.py in place and runs ALL self-tests (40, the new one takes about a minute);
#   3. runs the FULL Task 3 acceptance (200 null paths per kind, 100 edge paths per delta; a null row above 7% triggers the automatic
#      1000-path confirmation; this takes several minutes) and keeps its output;
#   4. commits exactly 11 paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_FORMULA_T3="5726e02f0839432a390e75cf11b68631660d3a7fb9d69242cdbfb2274ea56edc"
EXP_SELFTEST_ALL="2573c075b7bdb674ea2cb4a03f61f92b926710c27b1c454137c42e44392a20c6"
EXP_STATUS="6983fc505a01180daefa8572bf9ec4f5b8793ca31ffe3648d8ea1b1b346352c0"
EXP_NOTES="c4f478e8c7deeadf964dce0058632be41ac77444fdde686dcf7f9036848ff294"
EXP_MSG23="4ceb8c9e8cc02bd4e4c14033d00e4fda975a80125b3629c5d87e09ff704bcf0a"
OLD_SELFTEST_ALL="f0db1bbedaab4ad0cd84ca53c1d12c9061e0acb12ed461c17c95b2e01c88eb13"
OLD_STATUS="2adba1de2406422759939dd3fbdfe1fce5977a1e79da99c2ee71d7d6914f5532"
OLD_NOTES="d87ae86141a1d37741c81c074467197f6044f8b017bbf110089549cbf0cb435f"
LIVE_REG_SHA="c26ad4811f76752007ce803b4f2c62d45f5cf6c91be08cf19193c67f589b696b"
BASE_COMMIT="63edecf"
REG="user_data/analysis/results/registry.jsonl"
ACC="docs/reports/t3-acceptance-full-step1.txt"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/selftest_all.sh context/STATUS.md context/developer/NOTES.md 2>/dev/null
  rm -f user_data/analysis/formula_t3.py docs/correspondence/message-23.md "$ACC"
  echo "Rolled back: every file this script touched is exactly as before it ran."
}
on_exit() {
  rc=$?
  if [ "$FINISHED" != "1" ]; then
    echo
    if [ "$COMMITTED" = "1" ]; then
      echo "FAIL (exit $rc): the commit exists locally but was NOT pushed. Run:  git -C $REPO push origin main  and paste its output."
    else
      if [ "$APPLIED" = "1" ]; then cd "$REPO" && rollback; fi
      echo "FAIL (exit $rc). Nothing was committed or pushed."
      echo "Paste this whole output into the chat."
    fi
  fi
}
trap on_exit EXIT

die() { echo "STOP: $1"; exit 1; }
sha() { shasum -a 256 "$1" | awk '{print $1}'; }
secret_guard() {  # never opens the file
  if git ls-files --error-unmatch temp/secret_keys.txt >/dev/null 2>&1; then die "temp/secret_keys.txt is TRACKED by git; refusing to push. Tell the owner (do not paste the file)."; fi
  if [ -n "$(git log --all --oneline -- temp/secret_keys.txt 2>/dev/null)" ]; then die "temp/secret_keys.txt appears in a commit; refusing to push. Tell the owner (do not paste the file)."; fi
  if ! git check-ignore -q temp/secret_keys.txt 2>/dev/null; then echo "WARNING: temp/secret_keys.txt is not git-ignored; D2 will add temp/ to .gitignore in the next delivery (this script adds nothing but its own exact paths)."; fi
}

echo "== delivery 11 (D2, WO 1.7 step 1: formula_t3.py, self-tests, FULL Task 3 acceptance) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/11" ] || die "apply.sh must sit in $REPO/deliveries/11/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "formula_t3.py:$EXP_FORMULA_T3" "selftest_all.sh:$EXP_SELFTEST_ALL" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES" "message-23.md:$EXP_MSG23"; do
  f="${pair%%:*}"; want="${pair##*:}"
  [ -f "$HERE/$f" ] || die "missing file $HERE/$f"
  got="$(sha "$HERE/$f")"
  echo "$f  $got"
  [ "$got" = "$want" ] || BAD=1
done
[ "$BAD" = "0" ] || die "HASH MISMATCH - nothing was applied. Download the files again into $HERE"
echo "hashes match"
cd "$REPO"
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || die "not on branch main"
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/11/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
secret_guard
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; secret_guard; fi
git merge-base --is-ancestor "$BASE_COMMIT" HEAD || die "commit $BASE_COMMIT is not in your history"
git diff --quiet "$BASE_COMMIT" -- user_data/analysis || die "user_data/analysis differs from commit $BASE_COMMIT (the verified code); refusing to continue"
CODE_COMMIT="$(git rev-parse --short HEAD)"
echo "folder clean, on main, HEAD $CODE_COMMIT; user_data/analysis is byte-identical to $BASE_COMMIT"
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
for f in user_data/analysis/formula_t3.py docs/correspondence/message-23.md "$ACC"; do [ ! -e "$f" ] || die "$f already exists"; done
[ -f docs/work-orders/1.7-task3_reference.py ] || die "docs/work-orders/1.7-task3_reference.py is missing (M2's file)"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] && [ "$(wc -l < $REG | tr -d ' ')" = "26" ] || die "the live registry is not the 26-line file from the S2 live run; refusing to continue"
echo "live registry: 26 lines, unchanged since the S2 live run"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"

echo "-- 2. backup, formula_t3.py in place, then ALL self-tests"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/selftest_all.sh "$BK/"
cp context/STATUS.md "$BK/STATUS.md"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"
APPLIED=1
cp "$HERE/formula_t3.py" user_data/analysis/formula_t3.py
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
[ "$(sha user_data/analysis/formula_t3.py)" = "$EXP_FORMULA_T3" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] || die "a copy failed verification"
echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)'); scipy: $("$PYBIN" -c 'import scipy; print(scipy.__version__)')"
LOG="$REPO/temp/selftest-step11-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 30 lines of the log:"; tail -30 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q 'Self-test passed in [0-9]*s: formula_t3.py' "$LOG" || die "the formula_t3 self-test did not report success"
grep -E 'exact reproduction|acceptance \(' "$LOG" | cut -c1-600 || true
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"

echo "-- 3. FULL Task 3 acceptance (200 null / 100 edge paths; several minutes)"
ACCOUT="$REPO/temp/t3-acceptance-full-$STAMP.txt"
set +e
( cd user_data/analysis && "$PYBIN" formula_t3.py --full ) > "$ACCOUT" 2>&1
AC=$?
set -e
cat "$ACCOUT"
[ "$AC" -eq 0 ] || die "the FULL Task 3 acceptance failed; nothing committed. Paste this output into the chat (D2 then reports to M2 as a file and changes neither the statistic nor the bands)."
grep -q '^ALL TASK 3 ACCEPTANCE TESTS PASSED' "$ACCOUT" || die "the acceptance output lacks its PASS line"
mkdir -p docs/reports
{ echo "Task 3 acceptance, FULL (Work Order 1.7 section 4), produced by deliveries/11/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $CODE_COMMIT)"; echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)'); scipy: $("$PYBIN" -c 'import scipy; print(scipy.__version__)')"; echo "command: python3 formula_t3.py --full"; echo; cat "$ACCOUT"; } > "$ACC"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the acceptance run"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/11/' | LC_ALL=C sort | tr '\n' '|')"
WANT2="$(printf '%s\n' ' M user_data/analysis/selftest_all.sh' '?? user_data/analysis/formula_t3.py' "?? $ACC" | LC_ALL=C sort | tr '\n' '|')"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the acceptance run"; }

echo "-- 4. place documents, commit, push"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-23.md" docs/correspondence/message-23.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-23.md)" = "$EXP_MSG23" ] || die "a document copy failed verification"
secret_guard
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
PATHS="user_data/analysis/formula_t3.py user_data/analysis/selftest_all.sh context/developer/NOTES.md context/STATUS.md docs/correspondence/message-23.md $ACC deliveries/11/apply.sh deliveries/11/formula_t3.py deliveries/11/selftest_all.sh deliveries/11/STATUS.md deliveries/11/NOTES.md deliveries/11/message-23.md"
git add $PATHS
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="$(printf '%s\n' $PATHS | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected twelve: $STAGED"
git commit -q -m "[D2] WO 1.7 step 1: formula_t3.py (reference reproduced exactly), self-tests, FULL Task 3 acceptance, STATUS/NOTES (S2 delivery verified), message-23; no registry write"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
secret_guard
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
