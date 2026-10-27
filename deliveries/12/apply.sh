#!/bin/bash
# deliveries/12/apply.sh -- D2, Work Order 1.7 step 2: run_t3.py, the S1/S2 report regressions, the Task 3 origin facts and a SCRATCH dry run of both pairs.
#
# Put apply.sh, run_t3.py, registry.py, selftest_all.sh, check_reports.py, STATUS.md and NOTES.md together in
# ~/apps/crypto_bot/deliveries/12/ and run:   bash ~/apps/crypto_bot/deliveries/12/apply.sh
# It NEVER writes the live registry (hashed before and after; the dry run uses a fresh scratch file in temp/), never freezes, never touches the holdout.
#   1. checks hashes, the folder (clean, on main, user_data/analysis byte-identical to commit 0d8e318), the live registry (26 lines) and the secret-keys guard;
#   2. backs up what it replaces, puts the code in place (registry.py gets one backward-compatible extension) and runs ALL self-tests (41);
#   3. regression BEFORE: the S1 and S2 reports are regenerated read-only with the new registry code: S2 must equal the committed report (stamp aside); S1 must reproduce delivery 9's recorded post-S2 state (the committed S1 report predates S2) with its summary table identical;
#   4. prints and keeps the read-only Task 3 origin facts of both pairs;
#   5. dry-runs both pairs (48 cells, classification, dose-response, stability, by-year, robustness) on a fresh scratch registry;
#   6. commits exactly 15 paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_RUN_T3="1e6f3ab9cf9b4a919cd8cd26a7026852d007bc51c68621b2e4b5118678536830"
EXP_REGISTRY="c8d1f0ed828d89c24bbd6fbf9cf3aef9b92c2769342ac4b5387631b7191993e9"
EXP_SELFTEST_ALL="d512f607a773cc53dbe34b646bddfe3793feaeb2f2fe41a7514e8556d073503c"
EXP_CHECK="6d379e65d07ef57161f438f6bcc589174953ccbd0174dd7daddd4118c0558f07"
EXP_STATUS="49906176bb0ad372c0ee898e91eee6ca7e415a30eee651be9df6cc48e7e0de6f"
EXP_NOTES="257c9c53fb60240d5fde39443cabace9eb7292093871592892d9c7417da2e676"
OLD_REGISTRY="1ebb3316e3c5eadcd678d6b0afd05559efa21ae39d41af57f38aaef990dd0751"
OLD_SELFTEST_ALL="2573c075b7bdb674ea2cb4a03f61f92b926710c27b1c454137c42e44392a20c6"
OLD_STATUS="6983fc505a01180daefa8572bf9ec4f5b8793ca31ffe3648d8ea1b1b346352c0"
OLD_NOTES="c4f478e8c7deeadf964dce0058632be41ac77444fdde686dcf7f9036848ff294"
LIVE_REG_SHA="c26ad4811f76752007ce803b4f2c62d45f5cf6c91be08cf19193c67f589b696b"
BASE_COMMIT="0d8e318"
REG="user_data/analysis/results/registry.jsonl"
R_FACTS="docs/reports/t3-origin-facts-step2.txt"
R_DRY="docs/reports/t3-dry-run-step2.txt"
R_REC="docs/reports/t3-dry-run-records-step2.jsonl"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/registry.py user_data/analysis/selftest_all.sh context/STATUS.md context/developer/NOTES.md 2>/dev/null
  rm -f user_data/analysis/run_t3.py "$R_FACTS" "$R_DRY" "$R_REC"
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

echo "== delivery 12 (D2, WO 1.7 step 2: run_t3.py, regressions, origin facts, scratch dry run) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/12" ] || die "apply.sh must sit in $REPO/deliveries/12/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "run_t3.py:$EXP_RUN_T3" "registry.py:$EXP_REGISTRY" "selftest_all.sh:$EXP_SELFTEST_ALL" "check_reports.py:$EXP_CHECK" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/12/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
secret_guard
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; secret_guard; fi
git merge-base --is-ancestor "$BASE_COMMIT" HEAD || die "commit $BASE_COMMIT (delivery 11) is not in your history; run delivery 11 first"
git diff --quiet "$BASE_COMMIT" -- user_data/analysis || die "user_data/analysis differs from commit $BASE_COMMIT (the verified code); refusing to continue"
CODE_COMMIT="$(git rev-parse --short HEAD)"
echo "folder clean, on main, HEAD $CODE_COMMIT; user_data/analysis is byte-identical to $BASE_COMMIT"
[ "$(sha user_data/analysis/registry.py)" = "$OLD_REGISTRY" ] || die "registry.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
for f in user_data/analysis/run_t3.py "$R_FACTS" "$R_DRY" "$R_REC"; do [ ! -e "$f" ] || die "$f already exists"; done
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] && [ "$(wc -l < $REG | tr -d ' ')" = "26" ] || die "the live registry is not the 26-line file from the S2 live run; refusing to continue"
echo "live registry: 26 lines, unchanged since the S2 live run"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
for f in ETH_USDT BTC_USDT; do ls user_data/data/binance*/"$f-5m.feather" >/dev/null 2>&1 || die "data file $f-5m.feather not found under user_data/data/"; done
echo "5m data files present for both pairs"

echo "-- 2. backup, code in place, then ALL self-tests"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/registry.py user_data/analysis/selftest_all.sh "$BK/"
cp context/STATUS.md "$BK/STATUS.md"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"
APPLIED=1
cp "$HERE/run_t3.py" user_data/analysis/run_t3.py
cp "$HERE/registry.py" user_data/analysis/registry.py
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
[ "$(sha user_data/analysis/run_t3.py)" = "$EXP_RUN_T3" ] && [ "$(sha user_data/analysis/registry.py)" = "$EXP_REGISTRY" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] || die "a copy failed verification"
echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"
LOG="$REPO/temp/selftest-step12-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 30 lines of the log:"; tail -30 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q 'Self-test passed: run_t3' "$LOG" || die "the run_t3 self-test did not report success"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"

echo "-- 3. regression BEFORE any Task 3 record: S1 (equal to delivery 9's post-S2 state, summary table identical) and S2 (equal to the committed report)"
OUT1="$REPO/temp/s1-report-regression-$STAMP.md"
( cd user_data/analysis && "$PYBIN" s1_report.py --pair ETH_USDT --pair BTC_USDT --out "$OUT1" --void-commit ac63ff2 --run-commit 4487f1e --code-commit "$CODE_COMMIT" ) || die "the S1 report generator refused (regression)"
"$PYBIN" "$HERE/check_reports.py" docs/reports/s1-report-step6.md "$OUT1" --kind s1 --mode after --ref-diff docs/reports/s1-regression-after-s2-step3.txt || die "S1 regression: the regenerated S1 report differs from the committed one or from delivery 9's recorded post-S2 state"
OUT2="$REPO/temp/s2-report-regression-$STAMP.md"
( cd user_data/analysis && "$PYBIN" s2_report.py --pair ETH_USDT --pair BTC_USDT --out "$OUT2" --trades-dir "$REPO/temp/s2-trades-regression-$STAMP" --run-commit 294afb8 --code-commit "$CODE_COMMIT" --skip-null ) || die "the S2 report generator refused (regression)"
"$PYBIN" "$HERE/check_reports.py" docs/reports/s2-report-step3.md "$OUT2" --kind s2 --mode before || die "S2 regression: the regenerated S2 report differs from the committed one"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the regression"
echo "S1 and S2 reports reproduce: every recorded figure unchanged, the across-candidate Holm rows as recorded in delivery 9"

echo "-- 4. read-only Task 3 origin facts of both pairs"
FACTS="$REPO/temp/t3-origin-facts-$STAMP.txt"
( cd user_data/analysis && for P in ETH_USDT BTC_USDT; do "$PYBIN" run_t3.py --pair "$P" --origin-facts || exit 1; done ) > "$FACTS" 2>&1 || { cat "$FACTS"; die "the origin facts failed; nothing committed. Paste this output into the chat."; }
cat "$FACTS"
[ "$(grep -c '^=== Task 3 origin facts: ' "$FACTS")" = "2" ] || die "origin facts missing for a pair"

echo "-- 5. dry run of both pairs on a fresh SCRATCH registry (live registry untouched)"
DRY="$REPO/temp/t3-dryrun-$STAMP.jsonl"
DRYOUT="$REPO/temp/t3-dryrun-$STAMP.txt"
[ ! -e "$DRY" ] || die "$DRY already exists"
( cd user_data/analysis && for P in ETH_USDT BTC_USDT; do "$PYBIN" run_t3.py --pair "$P" --registry-path "$DRY" || exit 1; done ) > "$DRYOUT" 2>&1 || { cat "$DRYOUT"; die "the dry run failed; nothing committed. Paste this output into the chat."; }
cat "$DRYOUT"
[ "$(wc -l < "$DRY" | tr -d ' ')" = "4" ] || die "the scratch registry does not hold exactly four records"
"$PYBIN" - "$DRY" <<'PYEOF' || die "the scratch records are not the expected two per pair"
import json, sys
recs = [json.loads(l) for l in open(sys.argv[1])]
got = [(r["family"], r["status"]) for r in recs]
want = [(f, s) for f in ("Task3-ETHUSDT", "Task3-BTCUSDT") for s in ("discovery", "stability")]
assert got == want, got
assert all(len(r["detail"]["entries"]) == 2 for r in recs) and all(r["status"] not in ("frozen", "holdout_consumed") for r in recs)
print("scratch records:", got)
PYEOF
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the dry run"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/12/' | LC_ALL=C sort | tr '\n' '|')"
WANT2="$(printf '%s\n' ' M user_data/analysis/registry.py' ' M user_data/analysis/selftest_all.sh' '?? user_data/analysis/run_t3.py' | LC_ALL=C sort | tr '\n' '|')"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the dry run"; }
echo "live registry byte-identical after the dry run; no stray files"

echo "-- 6. place documents, commit, push"
mkdir -p docs/reports
{ echo "Task 3 origin facts (read-only), Work Order 1.7 step 2, produced by deliveries/12/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $CODE_COMMIT)"; echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"; echo "command: python3 run_t3.py --pair <PAIR> --origin-facts"; cat "$FACTS"; } > "$R_FACTS"
{ echo "Task 3 dry run on a scratch registry (not live), Work Order 1.7 step 2, produced by deliveries/12/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $CODE_COMMIT)"; echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"; echo "command: python3 run_t3.py --pair <PAIR> --registry-path <scratch file>; labeled variants are not recorded"; cat "$DRYOUT"; } > "$R_DRY"
cp "$DRY" "$R_REC"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] || die "a document copy failed verification"
secret_guard
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
PATHS="user_data/analysis/run_t3.py user_data/analysis/registry.py user_data/analysis/selftest_all.sh context/developer/NOTES.md context/STATUS.md $R_FACTS $R_DRY $R_REC deliveries/12/apply.sh deliveries/12/run_t3.py deliveries/12/registry.py deliveries/12/selftest_all.sh deliveries/12/check_reports.py deliveries/12/STATUS.md deliveries/12/NOTES.md"
git add $PATHS
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="$(printf '%s\n' $PATHS | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected fifteen: $STAGED"
git commit -q -m "[D2] WO 1.7 step 2: run_t3.py, per-primary-cell Holm entries in registry.holm_at_step (S1/S2 unchanged), S1/S2 report regressions, Task 3 origin facts and scratch dry run of both pairs (live registry untouched)"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
secret_guard
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
