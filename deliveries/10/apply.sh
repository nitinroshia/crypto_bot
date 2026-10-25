#!/bin/bash
# deliveries/10/apply.sh -- D2, Work Order 1.6 step 3: the S2 report (read-only generator) with its trade-list CSVs.
#
# Put apply.sh, s2_report.py, selftest_all.sh, STATUS.md, NOTES.md and message-22.md together in
# ~/apps/crypto_bot/deliveries/10/ and run:   bash ~/apps/crypto_bot/deliveries/10/apply.sh
# It writes NO registry record and never touches the holdout (the live registry is hashed before and after). What it does:
#   1. checks the SHA-256 of the delivered files, the folder (clean, on main, user_data/analysis byte-identical to commit 294afb8),
#      that the live registry is the 26-line file from the S2 live run, and refuses if temp/secret_keys.txt is tracked or committed;
#   2. backs up what it replaces, puts s2_report.py in place and runs ALL self-tests (39);
#   3. generates the S2 report (it refuses unless every recomputed figure reproduces the registry) and the trade-list CSVs;
#   4. commits exactly 16 paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_S2_REPORT="75f259ca2bebbfcf3c182675bbdd4b66d56185d12620fae5c26d70b21214d8b3"
EXP_SELFTEST_ALL="f0db1bbedaab4ad0cd84ca53c1d12c9061e0acb12ed461c17c95b2e01c88eb13"
EXP_STATUS="2adba1de2406422759939dd3fbdfe1fce5977a1e79da99c2ee71d7d6914f5532"
EXP_NOTES="d87ae86141a1d37741c81c074467197f6044f8b017bbf110089549cbf0cb435f"
EXP_MSG22="2c54994a6972ab2d9cbebfa9510e86302c148cada04a0bf2d302f481ff2018e0"
OLD_SELFTEST_ALL="41b11210b6bc34d3b49d72b627ba68c97347f9ac93fc3311b8ee6263548f1f52"
OLD_STATUS="2a8e8a15bf90f903a08b33ffedf6a47fff0807380fabb1392fe635d53879ce29"
OLD_NOTES="7a39c6c76be2dd590ae62e8b0678a9ab94996f3a25702ef2ded528f817b793d5"
LIVE_REG_SHA="c26ad4811f76752007ce803b4f2c62d45f5cf6c91be08cf19193c67f589b696b"
BASE_COMMIT="294afb8"
RUN_COMMIT="294afb8"
REG="user_data/analysis/results/registry.jsonl"
REPORT="docs/reports/s2-report-step3.md"
TRADES="docs/reports/s2-trades"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/selftest_all.sh context/STATUS.md context/developer/NOTES.md 2>/dev/null
  rm -rf user_data/analysis/s2_report.py "$REPORT" "$TRADES" docs/correspondence/message-22.md
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

echo "== delivery 10 (D2, WO 1.6 step 3: the S2 report, PRE-TAX, with trade lists) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/10" ] || die "apply.sh must sit in $REPO/deliveries/10/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "s2_report.py:$EXP_S2_REPORT" "selftest_all.sh:$EXP_SELFTEST_ALL" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES" "message-22.md:$EXP_MSG22"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/10/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
secret_guard
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; secret_guard; fi
git merge-base --is-ancestor "$BASE_COMMIT" HEAD || die "commit $BASE_COMMIT (delivery 9) is not in your history; run delivery 9 first"
git diff --quiet "$BASE_COMMIT" -- user_data/analysis || die "user_data/analysis differs from commit $BASE_COMMIT (the verified code); refusing to continue"
CODE_COMMIT="$(git rev-parse --short HEAD)"
echo "folder clean, on main, HEAD $CODE_COMMIT; user_data/analysis is byte-identical to $BASE_COMMIT"
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
for f in user_data/analysis/s2_report.py "$REPORT" "$TRADES" docs/correspondence/message-22.md; do [ ! -e "$f" ] || die "$f already exists"; done
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] && [ "$(wc -l < $REG | tr -d ' ')" = "26" ] || die "the live registry is not the 26-line file from the S2 live run; refusing to continue"
echo "live registry: 26 lines, unchanged since the S2 live run"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
for f in ETH_USDT BTC_USDT; do
  for kind in 1h 1d funding; do
    ls user_data/data/binance*/"$f-$kind.feather" >/dev/null 2>&1 || die "data file $f-$kind.feather not found under user_data/data/"
  done
done
echo "data files present for both pairs (1h, 1d, funding)"

echo "-- 2. backup, s2_report.py in place, then ALL self-tests"
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
cp "$HERE/s2_report.py" user_data/analysis/s2_report.py
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
[ "$(sha user_data/analysis/s2_report.py)" = "$EXP_S2_REPORT" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] || die "a copy failed verification"
echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"
LOG="$REPO/temp/selftest-step10-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 25 lines of the log:"; tail -25 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q 'Self-test passed: s2_report' "$LOG" || die "the s2_report self-test did not report success"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"

echo "-- 3. generate the S2 report (refuses unless every recomputed figure reproduces the registry) and the trade lists"
( cd user_data/analysis && "$PYBIN" s2_report.py --pair ETH_USDT --pair BTC_USDT --out "$REPO/$REPORT" --trades-dir "$REPO/$TRADES" --run-commit "$RUN_COMMIT" --code-commit "$CODE_COMMIT" ) || die "the S2 report generator refused (a recomputed figure does not match the registry, or data is missing); nothing committed. Paste this output into the chat."
[ -s "$REPORT" ] || die "the report was not written"
[ "$(ls $TRADES/*.csv | wc -l | tr -d ' ')" = "4" ] || die "expected four trade-list CSVs"
grep -q 'PRE-TAX' "$REPORT" || die "the report lacks the pre-tax label"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed while generating the report"
echo "report written: $REPORT ($(wc -l < $REPORT | tr -d ' ') lines); trade lists:"
for f in $TRADES/*.csv; do echo "  $f: $(( $(wc -l < "$f") - 1 )) trades"; done
echo "--- summary of recorded outcomes (from the report) ---"
sed -n '/^### Summary of recorded outcomes/,/^### Persistent-null/p' "$REPORT" | cut -c1-400
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/10/' | LC_ALL=C sort | tr '\n' '|')"
WANT2="$(printf '%s\n' ' M user_data/analysis/selftest_all.sh' '?? user_data/analysis/s2_report.py' "?? $REPORT" "?? $TRADES/s2-trades-BTC_USDT-buy-and-hold-stress.csv" "?? $TRADES/s2-trades-BTC_USDT-strategy-stress.csv" "?? $TRADES/s2-trades-ETH_USDT-buy-and-hold-stress.csv" "?? $TRADES/s2-trades-ETH_USDT-strategy-stress.csv" | LC_ALL=C sort | tr '\n' '|')"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the report"; }

echo "-- 4. place documents, commit, push"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-22.md" docs/correspondence/message-22.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-22.md)" = "$EXP_MSG22" ] || die "a document copy failed verification"
secret_guard
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
PATHS="user_data/analysis/s2_report.py user_data/analysis/selftest_all.sh context/developer/NOTES.md context/STATUS.md docs/correspondence/message-22.md $REPORT $TRADES/s2-trades-BTC_USDT-buy-and-hold-stress.csv $TRADES/s2-trades-BTC_USDT-strategy-stress.csv $TRADES/s2-trades-ETH_USDT-buy-and-hold-stress.csv $TRADES/s2-trades-ETH_USDT-strategy-stress.csv deliveries/10/apply.sh deliveries/10/s2_report.py deliveries/10/selftest_all.sh deliveries/10/STATUS.md deliveries/10/NOTES.md deliveries/10/message-22.md"
git add $PATHS
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="$(printf '%s\n' $PATHS | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected sixteen: $STAGED"
git commit -q -m "[D2] WO 1.6 step 3: S2 report (pre-tax, read-only generator cross-checked against the registry), trade lists, STATUS, message-22; no registry write"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
secret_guard
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
