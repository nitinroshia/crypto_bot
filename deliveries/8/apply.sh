#!/bin/bash
# deliveries/8/apply.sh -- D2, Work Order 1.6, step 2 (dry run): run_s2.py, origin facts and a SCRATCH dry run of both pairs.
#
# Put apply.sh, run_s2.py, formula_s2.py, selftest_all.sh, STATUS.md and NOTES.md together in
# ~/apps/crypto_bot/deliveries/8/ and run:   bash ~/apps/crypto_bot/deliveries/8/apply.sh
# It NEVER writes the live registry (the dry run uses a fresh scratch file in temp/), never freezes, never touches the holdout.
#   1. checks the SHA-256 of the delivered files, the folder (clean, on main, user_data/analysis byte-identical to commit 11a5fbb)
#      and that the live registry is still the 20-line file from the S1 live run;
#   2. backs up what it replaces, puts the code in place and runs ALL self-tests (38);
#   3. prints and keeps the read-only origin facts of both pairs (no p-values, no returns);
#   4. dry-runs both pairs (discovery, stability, economic gate) on a fresh scratch registry, prints and keeps the report and the
#      six scratch records;
#   5. commits exactly 14 paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_RUN_S2="2e46e2b51a32357776a6586ff669f6a0796715c68ecc9826c53b1c63ce245989"
EXP_FORMULA_S2="62e27d0b372ff03a8e26cfac4aab53f744ead20f380c2bdc1960da556416182e"
EXP_SELFTEST_ALL="41b11210b6bc34d3b49d72b627ba68c97347f9ac93fc3311b8ee6263548f1f52"
EXP_STATUS="2e99a2a212d4a4db142e78c51c75462ea4b6065f75f1d70b8916a74fca835260"
EXP_NOTES="20d1c4866a17460a003d37c463edffcf51038936ddaea24ee56ba14040d31651"
OLD_FORMULA_S2="73ba9b2f0069a5138eed36df509017599719d14055d7607557e4264d1d70dcba"
OLD_SELFTEST_ALL="61f23574127474ce98155166440d0d4ca69b39ac059530c667954dda7b610252"
OLD_STATUS="c505f1384fe54e866661693a239ef082714e77351d0e3c1adabf030f49fd0c5b"
OLD_NOTES="b6273a0e8294d71c65ff6feefca2d50fff29878b5d371632067f100bb712b8ae"
LIVE_REG_SHA="5ad0607c5bfd6ab24d7438a2c5edbdd5cb845d7cff28b4846b640c663c242779"
BASE_COMMIT="11a5fbb"
REG="user_data/analysis/results/registry.jsonl"
R_FACTS="docs/reports/s2-origin-facts-step2.txt"
R_DRY="docs/reports/s2-dry-run-step2.txt"
R_REC="docs/reports/s2-dry-run-records-step2.jsonl"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/selftest_all.sh user_data/analysis/formula_s2.py context/STATUS.md context/developer/NOTES.md 2>/dev/null
  rm -f user_data/analysis/run_s2.py "$R_FACTS" "$R_DRY" "$R_REC"
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

echo "== delivery 8 (D2, WO 1.6 step 2: run_s2.py, origin facts, scratch dry run) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/8" ] || die "apply.sh must sit in $REPO/deliveries/8/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "run_s2.py:$EXP_RUN_S2" "formula_s2.py:$EXP_FORMULA_S2" "selftest_all.sh:$EXP_SELFTEST_ALL" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/8/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; fi
git merge-base --is-ancestor "$BASE_COMMIT" HEAD || die "commit $BASE_COMMIT (delivery 7) is not in your history; run delivery 7 first"
git diff --quiet "$BASE_COMMIT" -- user_data/analysis || die "user_data/analysis differs from commit $BASE_COMMIT (the verified code); refusing to continue"
CODE_COMMIT="$(git rev-parse --short HEAD)"
echo "folder clean, on main, HEAD $CODE_COMMIT; user_data/analysis is byte-identical to $BASE_COMMIT"
[ "$(sha user_data/analysis/formula_s2.py)" = "$OLD_FORMULA_S2" ] || die "formula_s2.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
[ ! -e user_data/analysis/run_s2.py ] && [ ! -e "$R_FACTS" ] && [ ! -e "$R_DRY" ] && [ ! -e "$R_REC" ] || die "run_s2.py or one of the step-2 reports already exists"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the live registry is not the 20-line file from the S1 live run; refusing to continue"
echo "live registry: $(wc -l < $REG | tr -d ' ') lines, unchanged since the S1 live run"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"

echo "-- 2. backup, code in place, then ALL self-tests"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/selftest_all.sh user_data/analysis/formula_s2.py "$BK/"
cp context/STATUS.md "$BK/STATUS.md"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"
APPLIED=1
cp "$HERE/run_s2.py" user_data/analysis/run_s2.py
cp "$HERE/formula_s2.py" user_data/analysis/formula_s2.py
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
[ "$(sha user_data/analysis/run_s2.py)" = "$EXP_RUN_S2" ] && [ "$(sha user_data/analysis/formula_s2.py)" = "$EXP_FORMULA_S2" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] || die "a copy failed verification"
echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"
LOG="$REPO/temp/selftest-step8-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 25 lines of the log:"; tail -25 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q '^=================== run_s2.py' "$LOG" || die "the run_s2 self-test did not run"
grep -q 'Self-test passed: run_s2' "$LOG" || die "the run_s2 self-test did not report success"
grep -q 'Self-test passed in [0-9]*s: formula_s2.py' "$LOG" || die "the formula_s2 self-test did not report success"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"

echo "-- 3. read-only origin facts of both pairs (no p-values, no returns)"
FACTS="$REPO/temp/s2-origin-facts-$STAMP.txt"
( cd user_data/analysis && for P in ETH_USDT BTC_USDT; do "$PYBIN" run_s2.py --pair "$P" --origin-facts || exit 1; done ) > "$FACTS" 2>&1 || { cat "$FACTS"; die "the origin facts failed; nothing committed. Paste this output into the chat."; }
cat "$FACTS"
[ "$(grep -c '^=== S2 origin facts: ' "$FACTS")" = "2" ] || die "origin facts missing for a pair"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed while computing the origin facts"

echo "-- 4. dry run of both pairs on a fresh SCRATCH registry (live registry untouched)"
DRY="$REPO/temp/s2-dryrun-$STAMP.jsonl"
[ ! -e "$DRY" ] || die "$DRY already exists"
DRYOUT="$REPO/temp/s2-dryrun-$STAMP.txt"
( cd user_data/analysis && for P in ETH_USDT BTC_USDT; do "$PYBIN" run_s2.py --pair "$P" --registry-path "$DRY" || exit 1; done ) > "$DRYOUT" 2>&1 || { cat "$DRYOUT"; die "the dry run failed; nothing committed. Paste this output into the chat."; }
cat "$DRYOUT"
[ "$(wc -l < "$DRY" | tr -d ' ')" = "6" ] || die "the scratch registry does not hold exactly six records"
"$PYBIN" - "$DRY" <<'PYEOF' || die "the scratch records are not the expected three per pair"
import json, sys
recs = [json.loads(l) for l in open(sys.argv[1])]
got = [(r["family"], r["status"]) for r in recs]
want = [(f, s) for f in ("S2-ETHUSDT", "S2-BTCUSDT") for s in ("discovery", "stability", "economic_gate")]
assert got == want, got
assert all(r["status"] not in ("frozen", "holdout_consumed") for r in recs)
print("scratch records:", got)
PYEOF
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the dry run"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/8/' | LC_ALL=C sort | tr '\n' '|')"
WANT2="$(printf '%s\n' ' M user_data/analysis/formula_s2.py' ' M user_data/analysis/selftest_all.sh' '?? user_data/analysis/run_s2.py' | LC_ALL=C sort | tr '\n' '|')"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the dry run"; }
echo "live registry byte-identical after the dry run; no stray files"

echo "-- 5. place documents, commit, push"
mkdir -p docs/reports
{ echo "S2 origin facts (read-only), Work Order 1.6 step 2, produced by deliveries/8/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $CODE_COMMIT)"; echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"; echo "command: python3 run_s2.py --pair <PAIR> --origin-facts"; cat "$FACTS"; } > "$R_FACTS"
{ echo "S2 dry run on a scratch registry (not live), Work Order 1.6 step 2, produced by deliveries/8/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $CODE_COMMIT)"; echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"; echo "command: python3 run_s2.py --pair <PAIR> --registry-path <scratch file>; labeled variants are not recorded"; cat "$DRYOUT"; } > "$R_DRY"
cp "$DRY" "$R_REC"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] || die "a document copy failed verification"
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
git add user_data/analysis/run_s2.py user_data/analysis/formula_s2.py user_data/analysis/selftest_all.sh context/developer/NOTES.md context/STATUS.md "$R_FACTS" "$R_DRY" "$R_REC" deliveries/8/apply.sh deliveries/8/run_s2.py deliveries/8/formula_s2.py deliveries/8/selftest_all.sh deliveries/8/NOTES.md deliveries/8/STATUS.md
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="$(printf '%s\n' context/STATUS.md context/developer/NOTES.md deliveries/8/NOTES.md deliveries/8/STATUS.md deliveries/8/apply.sh deliveries/8/formula_s2.py deliveries/8/run_s2.py deliveries/8/selftest_all.sh "$R_FACTS" "$R_DRY" "$R_REC" user_data/analysis/formula_s2.py user_data/analysis/run_s2.py user_data/analysis/selftest_all.sh | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected fourteen: $STAGED"
git commit -q -m "[D2] WO 1.6 step 2: run_s2.py, S2 origin facts and scratch dry run of both pairs (live registry untouched)"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
