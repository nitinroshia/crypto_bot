#!/bin/bash
# deliveries/15/apply.sh -- D2, Work Order 1.7 step 3: the Task 3 report (read-only generator) with the trade lists. PRE-TAX.
#
# Put apply.sh, t3_report.py, selftest_all.sh, STATUS.md, NOTES.md and message-25.md together in ~/apps/crypto_bot/deliveries/15/ and run:
#     bash ~/apps/crypto_bot/deliveries/15/apply.sh
# It writes NO registry record and never touches the holdout (the live registry is hashed before and after). What it does:
#   1. checks hashes, the folder (clean, on main, user_data/analysis byte-identical to commit 3143fd8), that the live registry is the 30-line file from the Task 3 live run, the secret-keys guard;
#   2. backs up what it replaces, puts t3_report.py in place and runs ALL self-tests (42);
#   3. generates the Task 3 report (it recomputes both pairs and refuses unless the recomputed records equal the live ones) and the four trade-list CSVs (a few minutes);
#   4. commits exactly 16 paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_T3_REPORT="e4345169ab3a718de75a6bf54d5383c3d2163533deace541c4980af3cc5bb91c"
EXP_SELFTEST_ALL="ff93a72c3d41e0c52bb0c0ab46fc69c97e7185aa70f86e21c9f50cb2aff900b0"
EXP_STATUS="3a44b1f745ca18d0101acc5f8390ddba61623e8aaab0e6f4a3f89e909d0c6910"
EXP_NOTES="f5271e60d0bb7e948bc0276c20e7ec58470bc86f239ea1a981293894ac3e07b7"
EXP_MSG25="c9614726db627fc720348dacb38efe53da9bcf4273b8499734d31fd92c5c4b0b"
OLD_SELFTEST_ALL="d512f607a773cc53dbe34b646bddfe3793feaeb2f2fe41a7514e8556d073503c"
OLD_STATUS="26debf5a06d21597e3b28bf993069f03b568105dd554a5ff38d44ea365c2faf6"
OLD_NOTES="8dc01c41222e7fccf17560b50f51ffd2d75964d5acb12c9a58519c26a3d6f163"
LIVE_REG_SHA="ffd462e08c181f446aeb2de72964fef972e23719fa367ff6c3cd1e55aa402755"
BASE_COMMIT="3143fd8"
RUN_COMMIT="3143fd8"
REG="user_data/analysis/results/registry.jsonl"
REPORT="docs/reports/t3-report-step3.md"
TRADES="docs/reports/t3-trades"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/selftest_all.sh context/STATUS.md context/developer/NOTES.md 2>/dev/null
  rm -rf user_data/analysis/t3_report.py "$REPORT" "$TRADES" docs/correspondence/message-25.md
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

echo "== delivery 15 (D2, WO 1.7 step 3: the Task 3 report, PRE-TAX, with trade lists) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/15" ] || die "apply.sh must sit in $REPO/deliveries/15/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "t3_report.py:$EXP_T3_REPORT" "selftest_all.sh:$EXP_SELFTEST_ALL" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES" "message-25.md:$EXP_MSG25"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/15/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
secret_guard
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; secret_guard; fi
git merge-base --is-ancestor "$BASE_COMMIT" HEAD || die "commit $BASE_COMMIT (delivery 14) is not in your history; run delivery 14 first"
git diff --quiet "$BASE_COMMIT" -- user_data/analysis || die "user_data/analysis differs from commit $BASE_COMMIT (the verified code); refusing to continue"
CODE_COMMIT="$(git rev-parse --short HEAD)"
echo "folder clean, on main, HEAD $CODE_COMMIT; user_data/analysis is byte-identical to $BASE_COMMIT"
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
for f in user_data/analysis/t3_report.py "$REPORT" "$TRADES" docs/correspondence/message-25.md; do [ ! -e "$f" ] || die "$f already exists"; done
for f in docs/reports/t3-acceptance-full-step1.txt docs/reports/t3-checks-step3.txt docs/reports/t3-regression-after-t3-step3.txt; do [ -f "$f" ] || die "$f is missing"; done
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] && [ "$(wc -l < $REG | tr -d ' ')" = "30" ] || die "the live registry is not the 30-line file from the Task 3 live run; refusing to continue"
echo "live registry: 30 lines, unchanged since the Task 3 live run"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
for f in ETH_USDT BTC_USDT; do ls user_data/data/binance*/"$f-5m.feather" >/dev/null 2>&1 || die "data file $f-5m.feather not found under user_data/data/"; done

echo "-- 2. backup, t3_report.py in place, then ALL self-tests"
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
cp "$HERE/t3_report.py" user_data/analysis/t3_report.py
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
[ "$(sha user_data/analysis/t3_report.py)" = "$EXP_T3_REPORT" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] || die "a copy failed verification"
LOG="$REPO/temp/selftest-step15-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 30 lines of the log:"; tail -30 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q 'Self-test passed: t3_report' "$LOG" || die "the t3_report self-test did not report success"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"

echo "-- 3. generate the Task 3 report (recomputes both pairs; refuses unless every record reproduces the registry) and the trade lists"
( cd user_data/analysis && "$PYBIN" t3_report.py --pair ETH_USDT --pair BTC_USDT --out "$REPO/$REPORT" --trades-dir "$REPO/$TRADES" --run-commit "$RUN_COMMIT" --code-commit "$CODE_COMMIT" \
    --acceptance "$REPO/docs/reports/t3-acceptance-full-step1.txt" --regression "$REPO/docs/reports/t3-regression-after-t3-step3.txt" --checks "$REPO/docs/reports/t3-checks-step3.txt" ) || die "the Task 3 report generator refused (a recomputed record differs from the registry, or data is missing); nothing committed. Paste this output into the chat."
[ -s "$REPORT" ] || die "the report was not written"
[ "$(ls $TRADES/*.csv | wc -l | tr -d ' ')" = "4" ] || die "expected four trade-list CSVs"
grep -q 'PRE-TAX' "$REPORT" || die "the report lacks the pre-tax label"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed while generating the report"
echo "report written: $REPORT ($(wc -l < $REPORT | tr -d ' ') lines); trade lists:"
for f in $TRADES/*.csv; do echo "  $f: $(( $(wc -l < "$f") - 1 )) trades"; done
echo "--- summary of the primary cells (from the report) ---"
sed -n '/^### Summary of the primary cells/,/^### Acceptance results/p' "$REPORT" | cut -c1-420
sed -n '/^Exact reproduction of the reference/p' "$REPORT" | cut -c1-500
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/15/' | LC_ALL=C sort | tr '\n' '|')"
WANT2="$(printf '%s\n' ' M user_data/analysis/selftest_all.sh' '?? user_data/analysis/t3_report.py' "?? $REPORT" "?? $TRADES/t3-trades-BTC_USDT-5m_k6_down.csv" "?? $TRADES/t3-trades-BTC_USDT-5m_k6_up.csv" "?? $TRADES/t3-trades-ETH_USDT-5m_k6_down.csv" "?? $TRADES/t3-trades-ETH_USDT-5m_k6_up.csv" | LC_ALL=C sort | tr '\n' '|')"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the report"; }

echo "-- 4. place documents, commit, push"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-25.md" docs/correspondence/message-25.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-25.md)" = "$EXP_MSG25" ] || die "a document copy failed verification"
secret_guard
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
PATHS="user_data/analysis/t3_report.py user_data/analysis/selftest_all.sh context/developer/NOTES.md context/STATUS.md docs/correspondence/message-25.md $REPORT $TRADES/t3-trades-BTC_USDT-5m_k6_down.csv $TRADES/t3-trades-BTC_USDT-5m_k6_up.csv $TRADES/t3-trades-ETH_USDT-5m_k6_down.csv $TRADES/t3-trades-ETH_USDT-5m_k6_up.csv deliveries/15/apply.sh deliveries/15/t3_report.py deliveries/15/selftest_all.sh deliveries/15/STATUS.md deliveries/15/NOTES.md deliveries/15/message-25.md"
git add $PATHS
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="$(printf '%s\n' $PATHS | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected sixteen: $STAGED"
git commit -q -m "[D2] WO 1.7 step 3: Task 3 report (pre-tax, read-only generator cross-checked against the registry), trade lists, STATUS, message-25; no registry write"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
secret_guard
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
