#!/bin/bash
# deliveries/6/apply.sh -- D1, Work Order 1.5, step 6: the S1 report.
#
# Put apply.sh, s1_report.py, selftest_all.sh, NOTES.md, STATUS.md and message-19.md together in
# ~/apps/crypto_bot/deliveries/6/ and run:   bash ~/apps/crypto_bot/deliveries/6/apply.sh
# READ-ONLY with respect to the registry and the data: it generates docs/reports/s1-report-step6.md from your real
# daily files and the live registry, and refuses to commit unless every recomputed figure reproduces the registry's
# recorded figure. It does not freeze, unlock the holdout, forward-test or write the registry. What it does:
#   1. checks the SHA-256 of the delivered files, the state of the folder, that user_data/analysis is byte-identical to
#      commit 4487f1e, and that the live registry is the 20-line file from the live run;
#   2. backs up what it replaces, puts s1_report.py and selftest_all.sh in place, runs ALL self-tests (36);
#   3. generates the report (consistency-checked against the registry) and prints its summary table;
#   4. commits exactly twelve paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_REPORT_PY="34aa495c301c3314d7753d24e97f7afae12ea53c0cfade6938fdf9c6429735cd"
EXP_SELFTEST_ALL="9974f5d234212e423151ca67ea8181a0e857ebdbaee3ad08b3247eda9fcac826"
EXP_NOTES="a921f4da78fd86620739a31afa5762f9884e5a3f5ba80f1adc1c682f58e21ae6"
EXP_STATUS="c7a44a56ef062d47546657fb636c33df021003ff2f8db7bb019322730b0e2d49"
EXP_MSG19="14a860ca889027dc26edecca22497b8a310dbb0632bf0eda2024e5ca32e19274"
OLD_SELFTEST_ALL="6ec972ee24545b819ee28dbedd39e76417f76867b4fd5c1a9aa7c5bfae5780f9"
OLD_NOTES="dd5a81862dabdddf7bda507a725073c0b3c463dad97d05ec56800de2a57d76b9"
OLD_STATUS="aa02f7de152f39baf14bbafe2ba3d1b25ca269362d094101a75b1cb04db2adb5"
LIVE_REG_SHA="5ad0607c5bfd6ab24d7438a2c5edbdd5cb845d7cff28b4846b640c663c242779"
RUN_COMMIT="4487f1e"
REG="user_data/analysis/results/registry.jsonl"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/selftest_all.sh context/developer/NOTES.md context/STATUS.md 2>/dev/null
  rm -f user_data/analysis/s1_report.py docs/correspondence/message-19.md docs/reports/s1-report-step6.md
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

echo "== delivery 6 (D1, WO 1.5 step 6: the S1 report) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/6" ] || die "apply.sh must sit in $REPO/deliveries/6/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "s1_report.py:$EXP_REPORT_PY" "selftest_all.sh:$EXP_SELFTEST_ALL" "NOTES.md:$EXP_NOTES" "STATUS.md:$EXP_STATUS" "message-19.md:$EXP_MSG19"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/6/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; fi
git merge-base --is-ancestor "$RUN_COMMIT" HEAD || die "delivery 5 ($RUN_COMMIT) is not in your history; run delivery 5 first"
git diff --quiet "$RUN_COMMIT" -- user_data/analysis || die "user_data/analysis differs from commit $RUN_COMMIT (the verified code); refusing to continue"
echo "folder clean, on main, HEAD $(git rev-parse --short HEAD); user_data/analysis is byte-identical to $RUN_COMMIT"
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "developer/NOTES.md is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ ! -e user_data/analysis/s1_report.py ] && [ ! -e docs/correspondence/message-19.md ] && [ ! -e docs/reports/s1-report-step6.md ] || die "s1_report.py, message-19.md or the report already exists"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the live registry is not the 20-line file from the live run ($RUN_COMMIT); refusing to continue"
echo "live registry: $(wc -l < $REG | tr -d ' ') lines, identical to the file committed in $RUN_COMMIT"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"

echo "-- 2. backup, new files in place, then ALL self-tests"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/selftest_all.sh "$BK/"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
cp context/STATUS.md "$BK/STATUS.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"
APPLIED=1
cp "$HERE/s1_report.py" user_data/analysis/s1_report.py
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
[ "$(sha user_data/analysis/s1_report.py)" = "$EXP_REPORT_PY" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] || die "a code copy failed verification"
echo "python: $("$PYBIN" --version 2>&1)"
LOG="$REPO/temp/selftest-step6-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 25 lines of the log:"; tail -25 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q '^=================== s1_report.py' "$LOG" || die "the report self-test did not run"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/6/' | LC_ALL=C sort | tr '\n' '|')"
WANT2=" M user_data/analysis/selftest_all.sh|?? user_data/analysis/s1_report.py|"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the self-tests"; }
echo "live registry byte-identical after the self-tests; no stray files"

echo "-- 3. generate the S1 report (read-only; refuses unless every figure reproduces the registry)"
REPORT="$REPO/temp/s1-report-step6-$STAMP.md"
CODE_COMMIT="$(git rev-parse --short HEAD)"
( cd user_data/analysis && "$PYBIN" s1_report.py --pair ETH_USDT --pair BTC_USDT --out "$REPORT" --void-commit ac63ff2 --run-commit "$RUN_COMMIT" --code-commit "$CODE_COMMIT" ) || die "the report generator refused (a recomputed figure does not match the registry, or data is missing); nothing committed"
[ -s "$REPORT" ] || die "the report file was not written"
grep -q '^## ETH_USDT' "$REPORT" && grep -q '^## BTC_USDT' "$REPORT" || die "the report lacks a pair section"
grep -q '^## 8. Interpretation choices' "$REPORT" || die "the report lacks the interpretation-choices section"
[ "$(grep -c '| primary |' "$REPORT")" = "2" ] && [ "$(grep -c '| exploratory |' "$REPORT")" = "18" ] || die "the report does not have ten tagged cells per pair"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed while generating the report"
echo "report generated: $(wc -l < "$REPORT" | tr -d ' ') lines; every recomputed figure reproduces the registry; live registry byte-identical"
echo
sed -n '/^### Summary of recorded outcomes/,/^## ETH_USDT/p' "$REPORT" | sed '$d' | cut -c1-400
echo

echo "-- 4. place documents, commit, push"
mkdir -p docs/reports
cp "$REPORT" docs/reports/s1-report-step6.md
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-19.md" docs/correspondence/message-19.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-19.md)" = "$EXP_MSG19" ] || die "a document copy failed verification"
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
git add user_data/analysis/s1_report.py user_data/analysis/selftest_all.sh context/developer/NOTES.md context/STATUS.md docs/correspondence/message-19.md docs/reports/s1-report-step6.md deliveries/6/apply.sh deliveries/6/s1_report.py deliveries/6/selftest_all.sh deliveries/6/NOTES.md deliveries/6/STATUS.md deliveries/6/message-19.md
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="context/STATUS.md context/developer/NOTES.md deliveries/6/NOTES.md deliveries/6/STATUS.md deliveries/6/apply.sh deliveries/6/message-19.md deliveries/6/s1_report.py deliveries/6/selftest_all.sh docs/correspondence/message-19.md docs/reports/s1-report-step6.md user_data/analysis/s1_report.py user_data/analysis/selftest_all.sh "
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected twelve: $STAGED"
git commit -q -m "[D1] WO 1.5 step 6: S1 report (read-only generator cross-checked against the registry), report file, message-19"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
