#!/bin/bash
# deliveries/13/apply.sh -- D2, Work Order 1.7 step 2 (continued): the read-only zero-volume variant and message-24 to M2.
#
# Put apply.sh, formula_t3.py, run_t3.py, STATUS.md, NOTES.md and message-24.md together in
# ~/apps/crypto_bot/deliveries/13/ and run:   bash ~/apps/crypto_bot/deliveries/13/apply.sh
# It writes NO registry record and touches no data file or the holdout (the live registry is hashed before and after). What it does:
#   1. checks hashes, the folder (clean, on main, user_data/analysis byte-identical to commit 8273b98), the live registry (26 lines), the secret-keys guard;
#   2. backs up what it replaces, puts the code in place (formula_t3.py gains an optional argument, default off) and runs ALL self-tests (41);
#   3. runs the labeled variant "zero-volume 5m bars masked" for both pairs (read-only; never recorded) and keeps its output;
#   4. commits exactly 12 paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_FORMULA_T3="080902171f034d9529e253a2d4466464b9e4feb81093c9a295fc92ca3d82a261"
EXP_RUN_T3="446438c679073fe3b42bbee8f83173b3a9246020ff52848fac771b949eef0c63"
EXP_STATUS="b324b5632a66085b304b32d13d8065c3a5043a01943072bad47c5e421701ef85"
EXP_NOTES="817a38947f58456e93f850a6942ef45e61064a5a199ff0f8f2fc10c50bea3bc8"
EXP_MSG24="c25faa5a1df23134c270f6ef0b6cb6718f8d200e8f8114cc5e7ff105f0a29f6d"
OLD_FORMULA_T3="5726e02f0839432a390e75cf11b68631660d3a7fb9d69242cdbfb2274ea56edc"
OLD_RUN_T3="1e6f3ab9cf9b4a919cd8cd26a7026852d007bc51c68621b2e4b5118678536830"
OLD_STATUS="49906176bb0ad372c0ee898e91eee6ca7e415a30eee651be9df6cc48e7e0de6f"
OLD_NOTES="257c9c53fb60240d5fde39443cabace9eb7292093871592892d9c7417da2e676"
LIVE_REG_SHA="c26ad4811f76752007ce803b4f2c62d45f5cf6c91be08cf19193c67f589b696b"
BASE_COMMIT="8273b98"
REG="user_data/analysis/results/registry.jsonl"
VAR="docs/reports/t3-variant-zero-volume-step2.txt"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/formula_t3.py user_data/analysis/run_t3.py context/STATUS.md context/developer/NOTES.md 2>/dev/null
  rm -f docs/correspondence/message-24.md "$VAR"
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

echo "== delivery 13 (D2, WO 1.7: zero-volume variant, message-24 to M2) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/13" ] || die "apply.sh must sit in $REPO/deliveries/13/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "formula_t3.py:$EXP_FORMULA_T3" "run_t3.py:$EXP_RUN_T3" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES" "message-24.md:$EXP_MSG24"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/13/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
secret_guard
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; secret_guard; fi
git merge-base --is-ancestor "$BASE_COMMIT" HEAD || die "commit $BASE_COMMIT (delivery 12) is not in your history; run delivery 12 first"
git diff --quiet "$BASE_COMMIT" -- user_data/analysis || die "user_data/analysis differs from commit $BASE_COMMIT (the verified code); refusing to continue"
CODE_COMMIT="$(git rev-parse --short HEAD)"
echo "folder clean, on main, HEAD $CODE_COMMIT; user_data/analysis is byte-identical to $BASE_COMMIT"
[ "$(sha user_data/analysis/formula_t3.py)" = "$OLD_FORMULA_T3" ] || die "formula_t3.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/run_t3.py)" = "$OLD_RUN_T3" ] || die "run_t3.py is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
for f in docs/correspondence/message-24.md "$VAR"; do [ ! -e "$f" ] || die "$f already exists"; done
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] && [ "$(wc -l < $REG | tr -d ' ')" = "26" ] || die "the live registry is not the 26-line file; refusing to continue"
echo "live registry: 26 lines, unchanged"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"

echo "-- 2. backup, code in place, then ALL self-tests"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/formula_t3.py user_data/analysis/run_t3.py "$BK/"
cp context/STATUS.md "$BK/STATUS.md"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"
APPLIED=1
cp "$HERE/formula_t3.py" user_data/analysis/formula_t3.py
cp "$HERE/run_t3.py" user_data/analysis/run_t3.py
[ "$(sha user_data/analysis/formula_t3.py)" = "$EXP_FORMULA_T3" ] && [ "$(sha user_data/analysis/run_t3.py)" = "$EXP_RUN_T3" ] || die "a copy failed verification"
LOG="$REPO/temp/selftest-step13-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 30 lines of the log:"; tail -30 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q 'exact reproduction' "$LOG" && grep -q 'Self-test passed: run_t3' "$LOG" || die "the formula_t3 / run_t3 self-tests did not report success"
grep -E 'exact reproduction' "$LOG" | cut -c1-300 || true
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"

echo "-- 3. labeled variant: zero-volume 5m bars masked (read-only, never recorded), both pairs"
VOUT="$REPO/temp/t3-variant-zero-volume-$STAMP.txt"
( cd user_data/analysis && for P in ETH_USDT BTC_USDT; do "$PYBIN" run_t3.py --pair "$P" --variant-zero-volume || exit 1; done ) > "$VOUT" 2>&1 || { cat "$VOUT"; die "the variant run failed; nothing committed. Paste this output into the chat."; }
cat "$VOUT"
[ "$(grep -c '^=== Task 3 labeled variant' "$VOUT")" = "2" ] || die "variant output missing for a pair"
mkdir -p docs/reports
{ echo "Task 3 labeled variant, zero-volume 5m bars masked (read-only, never recorded), Work Order 1.7 question 2, produced by deliveries/13/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $CODE_COMMIT)"; echo "command: python3 run_t3.py --pair <PAIR> --variant-zero-volume"; cat "$VOUT"; } > "$VAR"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the variant run"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/13/' | LC_ALL=C sort | tr '\n' '|')"
WANT2="$(printf '%s\n' ' M user_data/analysis/formula_t3.py' ' M user_data/analysis/run_t3.py' "?? $VAR" | LC_ALL=C sort | tr '\n' '|')"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the variant run"; }

echo "-- 4. place documents, commit, push"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-24.md" docs/correspondence/message-24.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-24.md)" = "$EXP_MSG24" ] || die "a document copy failed verification"
secret_guard
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
PATHS="user_data/analysis/formula_t3.py user_data/analysis/run_t3.py context/developer/NOTES.md context/STATUS.md docs/correspondence/message-24.md $VAR deliveries/13/apply.sh deliveries/13/formula_t3.py deliveries/13/run_t3.py deliveries/13/STATUS.md deliveries/13/NOTES.md deliveries/13/message-24.md"
git add $PATHS
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="$(printf '%s\n' $PATHS | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected twelve: $STAGED"
git commit -q -m "[D2] WO 1.7: read-only zero-volume variant (never recorded), dry-run facts for M2 (message-24), STATUS/NOTES; no registry write"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
secret_guard
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
