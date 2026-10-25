#!/bin/bash
# deliveries/9/apply.sh -- D2, Work Order 1.6: M2's rulings of 2026-10-23 applied, ruled dry run, equality check, and (ONLY with
# --go-live-s2) the live S2 run, once per pair.
#
# Put apply.sh, check_equal.py, formula_s2.py, run_s2.py, STATUS.md, NOTES.md and message-21.md together in
# ~/apps/crypto_bot/deliveries/9/ and run:
#     bash ~/apps/crypto_bot/deliveries/9/apply.sh --go-live-s2        (the live run; the owner's message said "go live S2")
#     bash ~/apps/crypto_bot/deliveries/9/apply.sh                      (steps 1-6 only, commits nothing, writes nothing live)
# What it does:
#   1. checks hashes, the folder (clean, on main, user_data/analysis byte-identical to commit 901ef7f), the live registry (20 lines),
#      and refuses everything if temp/secret_keys.txt is tracked or was ever committed (it never opens that file);
#   2. backs up, puts the new code in place, runs ALL self-tests (38, including M2's persistent null);
#   3. S1 regression BEFORE: the S1 report is regenerated read-only and its summary table must equal the committed one;
#   4. a new scratch dry run of both pairs with the ruled settings;
#   5. an equality check against delivery 8's dry-run records on every figure the HAC lags cannot change;
#   6. without --go-live-s2: stop here (everything put back, nothing committed). With it:
#   7. the live run (once per pair, three records each); the live records must equal the ruled dry run apart from timestamps and the first
#      20 registry lines must be byte-identical; S1 regression AFTER (summary table identical; only the across-candidate Holm rows and the
#      cumulative counts may change, by design: R1);
#   8. commits exact paths and pushes. On any failure before the commit it puts everything back, the live registry included.
set -e

LIVE=0; REPO_ARG=""
for a in "$@"; do
  case "$a" in
    --go-live-s2) LIVE=1 ;;
    *) REPO_ARG="$a" ;;
  esac
done
REPO="${REPO_ARG:-$HOME/apps/crypto_bot}"
EXP_FORMULA_S2="303e47b9c7c15f09529abf0a2abce9ab118cb5231c0835f3bd7c9e351964348d"
EXP_RUN_S2="908b43656159d7016ecfe553fa8bded27dcb42f490eaa856b16eaeffbead1d5d"
EXP_STATUS="2a8e8a15bf90f903a08b33ffedf6a47fff0807380fabb1392fe635d53879ce29"
EXP_NOTES="7a39c6c76be2dd590ae62e8b0678a9ab94996f3a25702ef2ded528f817b793d5"
EXP_MSG21="74cbf1a3e12437651f0621de620d11a151c11dc6bc32dc3abb19e880e23fb2a1"
EXP_CHECK="85c605c1376bd9389f815f86f87e0f97ffbb69d2de536dc3a28b86aa465d8eca"
OLD_FORMULA_S2="62e27d0b372ff03a8e26cfac4aab53f744ead20f380c2bdc1960da556416182e"
OLD_RUN_S2="2e46e2b51a32357776a6586ff669f6a0796715c68ecc9826c53b1c63ce245989"
OLD_STATUS="2e99a2a212d4a4db142e78c51c75462ea4b6065f75f1d70b8916a74fca835260"
OLD_NOTES="20d1c4866a17460a003d37c463edffcf51038936ddaea24ee56ba14040d31651"
LIVE_REG_SHA="5ad0607c5bfd6ab24d7438a2c5edbdd5cb845d7cff28b4846b640c663c242779"
BASE_COMMIT="901ef7f"
RUN_COMMIT="4487f1e"
REG="user_data/analysis/results/registry.jsonl"
OLD_REC="docs/reports/s2-dry-run-records-step2.jsonl"
R_DRY="docs/reports/s2-dry-run-ruled-step3.txt"
R_REC="docs/reports/s2-dry-run-records-ruled-step3.jsonl"
R_EQ="docs/reports/s2-equality-check-step3.txt"
R_S1="docs/reports/s1-regression-after-s2-step3.txt"
NEWFILES="docs/correspondence/message-21.md $R_DRY $R_REC $R_EQ $R_S1"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/formula_s2.py user_data/analysis/run_s2.py context/STATUS.md context/developer/NOTES.md "$REG" 2>/dev/null
  rm -f $NEWFILES
  echo "Rolled back: every file this script touched, the live registry included, is exactly as before it ran."
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
secret_guard() {  # M2's item 7: never opens the file
  if git ls-files --error-unmatch temp/secret_keys.txt >/dev/null 2>&1; then die "temp/secret_keys.txt is TRACKED by git; refusing to push. Tell the owner (do not paste the file)."; fi
  if [ -n "$(git log --all --oneline -- temp/secret_keys.txt 2>/dev/null)" ]; then die "temp/secret_keys.txt appears in a commit; refusing to push. Tell the owner (do not paste the file)."; fi
  if ! git check-ignore -q temp/secret_keys.txt 2>/dev/null; then echo "WARNING: temp/secret_keys.txt is not git-ignored; D2 will add temp/ to .gitignore in the next delivery (this script adds nothing but its own exact paths)."; fi
}

echo "== delivery 9 (D2, WO 1.6: rulings of 2026-10-23, ruled dry run, equality check$( [ "$LIVE" = "1" ] && echo ', LIVE run' )) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/9" ] || die "apply.sh must sit in $REPO/deliveries/9/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "formula_s2.py:$EXP_FORMULA_S2" "run_s2.py:$EXP_RUN_S2" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES" "message-21.md:$EXP_MSG21" "check_equal.py:$EXP_CHECK"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/9/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
secret_guard
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; secret_guard; fi
git merge-base --is-ancestor "$BASE_COMMIT" HEAD || die "commit $BASE_COMMIT (delivery 8) is not in your history; run delivery 8 first"
git diff --quiet "$BASE_COMMIT" -- user_data/analysis || die "user_data/analysis differs from commit $BASE_COMMIT (the verified code); refusing to continue"
CODE_COMMIT="$(git rev-parse --short HEAD)"
echo "folder clean, on main, HEAD $CODE_COMMIT; user_data/analysis is byte-identical to $BASE_COMMIT"
[ "$(sha user_data/analysis/formula_s2.py)" = "$OLD_FORMULA_S2" ] || die "formula_s2.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/run_s2.py)" = "$OLD_RUN_S2" ] || die "run_s2.py is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
for f in $NEWFILES; do [ ! -e "$f" ] || die "$f already exists"; done
[ -f "$OLD_REC" ] && [ "$(wc -l < $OLD_REC | tr -d ' ')" = "6" ] || die "delivery 8's dry-run records ($OLD_REC) are missing or not 6 lines"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] && [ "$(wc -l < $REG | tr -d ' ')" = "20" ] || die "the live registry is not the 20-line file from the S1 live run ($RUN_COMMIT); refusing to continue (a second S2 live run is not allowed)"
echo "live registry: 20 lines, unchanged since the S1 live run"
if [ -f docs/correspondence/answer-s2-rulings.md ]; then echo "M2's rulings are filed: docs/correspondence/answer-s2-rulings.md"; else echo "NOTE: docs/correspondence/answer-s2-rulings.md is not in your folder yet (M2's own delivery m2-03 files it); this does not block the run"; fi
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"

echo "-- 2. backup, new code in place, then ALL self-tests"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/formula_s2.py user_data/analysis/run_s2.py "$BK/"
cp context/STATUS.md "$BK/STATUS.md"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"
APPLIED=1
cp "$HERE/formula_s2.py" user_data/analysis/formula_s2.py
cp "$HERE/run_s2.py" user_data/analysis/run_s2.py
[ "$(sha user_data/analysis/formula_s2.py)" = "$EXP_FORMULA_S2" ] && [ "$(sha user_data/analysis/run_s2.py)" = "$EXP_RUN_S2" ] || die "a copy failed verification"
echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"
LOG="$REPO/temp/selftest-step9-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
if [ "$ST_CODE" -ne 0 ]; then
  echo "last 30 lines of the log:"; tail -30 "$LOG"
  if grep -q 'persistent null' "$LOG" && grep -q 'exceeds 8%' "$LOG"; then echo "The persistent-null band was missed: D2 stops and reports to M2 as a file; the lags and the statistic are not changed."; fi
  die "self-tests failed (exit $ST_CODE)"
fi
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep 'persistent null' "$LOG" | head -2 || true
grep -q 'Self-test passed in [0-9]*s: formula_s2.py' "$LOG" || die "the formula_s2 self-test did not report success"
grep -q 'Self-test passed: run_s2' "$LOG" || die "the run_s2 self-test did not report success"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"

s1_regression() {  # $1 = before|after
  OUTMD="$REPO/temp/s1-report-regression-$1-$STAMP.md"
  ( cd user_data/analysis && "$PYBIN" s1_report.py --pair ETH_USDT --pair BTC_USDT --out "$OUTMD" --void-commit ac63ff2 --run-commit "$RUN_COMMIT" --code-commit "$CODE_COMMIT" ) || die "the S1 report generator refused ($1): a recomputed S1 figure does not match the registry, or data is missing"
  [ -s "$OUTMD" ] || die "the S1 regression report was not written ($1)"
  sed -n '/^### Summary of recorded outcomes/,/^## ETH_USDT/p' "$OUTMD" > "$BK/s1-summary-$1.txt"
  sed -n '/^### Summary of recorded outcomes/,/^## ETH_USDT/p' docs/reports/s1-report-step6.md > "$BK/s1-summary-committed.txt"
  [ -s "$BK/s1-summary-$1.txt" ] && cmp -s "$BK/s1-summary-$1.txt" "$BK/s1-summary-committed.txt" || die "S1 regression ($1): the regenerated S1 summary table differs from the committed S1 report"
}

echo "-- 3. S1 regression BEFORE any S2 record exists"
s1_regression before
echo "S1 report regenerated read-only: every recomputed figure reproduces the registry; summary table (slopes, p, T, p_stab, gate returns) equals the committed one"

echo "-- 4. ruled dry run of both pairs on a fresh SCRATCH registry"
DRY="$REPO/temp/s2-dryrun-ruled-$STAMP.jsonl"
DRYOUT="$REPO/temp/s2-dryrun-ruled-$STAMP.txt"
[ ! -e "$DRY" ] || die "$DRY already exists"
( cd user_data/analysis && for P in ETH_USDT BTC_USDT; do "$PYBIN" run_s2.py --pair "$P" --registry-path "$DRY" || exit 1; done ) > "$DRYOUT" 2>&1 || { cat "$DRYOUT"; die "the ruled dry run failed; nothing committed. Paste this output into the chat."; }
cat "$DRYOUT"
[ "$(wc -l < "$DRY" | tr -d ' ')" = "6" ] || die "the scratch registry does not hold exactly six records"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the dry run"

echo "-- 5. equality check against delivery 8's dry-run records (figures the lags cannot change)"
set +e
"$PYBIN" "$HERE/check_equal.py" "$OLD_REC" "$DRY" --mode lagsafe > "$REPO/temp/s2-equality-$STAMP.txt" 2>&1
EQ=$?
set -e
cat "$REPO/temp/s2-equality-$STAMP.txt"
[ "$EQ" -eq 0 ] || die "a figure the lags cannot change differs from delivery 8's dry run; nothing committed. Paste this output into the chat."

if [ "$LIVE" != "1" ]; then
  echo
  echo "STOP (by design): started without --go-live-s2, so the live run is not executed. Steps 1-5 passed. Everything is put back and nothing is committed."
  echo "When ready:  bash $HERE/apply.sh --go-live-s2"
  rollback
  FINISHED=1
  echo "OK (dry steps only)"
  exit 0
fi

echo "-- 6. LIVE run, once per pair (explicit --go-live-s2)"
secret_guard
( cd user_data/analysis && for P in ETH_USDT BTC_USDT; do "$PYBIN" run_s2.py --pair "$P" --commit-to-registry || exit 1; done ) > "$REPO/temp/s2-live-$STAMP.txt" 2>&1 || { cat "$REPO/temp/s2-live-$STAMP.txt"; die "the live run failed; the registry is put back; nothing committed. Paste this output into the chat."; }
grep -E '^REGISTRY: ' "$REPO/temp/s2-live-$STAMP.txt" || true
[ "$(wc -l < $REG | tr -d ' ')" = "26" ] || die "the live registry does not hold exactly 26 lines after the live run"
head -n 20 $REG | cmp -s - "$BK/registry.jsonl" || die "the first 20 live registry lines are not byte-identical to the backup"
tail -n 6 $REG > "$REPO/temp/s2-live-records-$STAMP.jsonl"
"$PYBIN" "$HERE/check_equal.py" "$DRY" "$REPO/temp/s2-live-records-$STAMP.jsonl" --mode exact || die "the live records differ from the ruled dry run"
"$PYBIN" - "$REG" <<'PYEOF' || die "the live registry holds an unexpected record"
import json, sys
recs = [json.loads(l) for l in open(sys.argv[1])]
tail = [(r["family"], r["status"]) for r in recs[20:]]
want = [(f, s) for f in ("S2-ETHUSDT", "S2-BTCUSDT") for s in ("discovery", "stability", "economic_gate")]
assert tail == want, tail
assert not any(r["status"] in ("frozen", "holdout_consumed") for r in recs[20:]), "frozen or holdout record"
print("live registry: 26 lines; records 21-26 =", tail)
PYEOF
echo "live registry: first 20 lines byte-identical; records 21-26 equal the ruled dry run apart from timestamps"

echo "-- 7. S1 regression AFTER the live S2 records"
s1_regression after
{
  echo "S1 report regenerated after the S2 live records (registry 26 lines) against the committed S1 report (registry 20 lines): lines that differ."
  echo "The summary table (slopes, p, T, p_stab, gate returns) is identical. Allowed by design (R1, two candidates per step): the across-candidate Holm rows, the cumulative counts, the generation stamp."
  diff docs/reports/s1-report-step6.md "$OUTMD" | grep '^[<>]' || true
} > "$R_S1"
DISALLOWED="$(diff docs/reports/s1-report-step6.md "$OUTMD" | grep '^[<>]' | grep -v -E '^[<>] Generated |^[<>] \| (discovery|stability|economic_gate) \||cumulative_count' || true)"
if [ -n "$DISALLOWED" ]; then echo "$DISALLOWED" | head -20; die "S1 regression (after): the regenerated S1 report differs outside the Holm rows and cumulative counts"; fi
cat "$R_S1" | cut -c1-200

echo "-- 8. place documents, commit, push"
mkdir -p docs/reports
{ echo "S2 dry run with M2's rulings of 2026-10-23 (HAC lags 12 and 36, primary gate rule), scratch registry, produced by deliveries/9/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $CODE_COMMIT)"; echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"; echo "command: python3 run_s2.py --pair <PAIR> --registry-path <scratch file>"; cat "$DRYOUT"; } > "$R_DRY"
cp "$DRY" "$R_REC"
{ echo "Equality check, delivery 8 dry-run records against the ruled dry run (lagsafe), produced by deliveries/9/apply.sh"; cat "$REPO/temp/s2-equality-$STAMP.txt"; } > "$R_EQ"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-21.md" docs/correspondence/message-21.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-21.md)" = "$EXP_MSG21" ] || die "a document copy failed verification"
secret_guard
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
git add user_data/analysis/formula_s2.py user_data/analysis/run_s2.py context/developer/NOTES.md context/STATUS.md "$REG" docs/correspondence/message-21.md "$R_DRY" "$R_REC" "$R_EQ" "$R_S1" deliveries/9/apply.sh deliveries/9/check_equal.py deliveries/9/formula_s2.py deliveries/9/run_s2.py deliveries/9/NOTES.md deliveries/9/STATUS.md deliveries/9/message-21.md
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="$(printf '%s\n' user_data/analysis/formula_s2.py user_data/analysis/run_s2.py context/developer/NOTES.md context/STATUS.md "$REG" docs/correspondence/message-21.md "$R_DRY" "$R_REC" "$R_EQ" "$R_S1" deliveries/9/apply.sh deliveries/9/check_equal.py deliveries/9/formula_s2.py deliveries/9/run_s2.py deliveries/9/NOTES.md deliveries/9/STATUS.md deliveries/9/message-21.md | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected sixteen: $STAGED"
git commit -q -m "[D2] WO 1.6 step 2: M2's rulings (HAC 12/36, primary gate rule), ruled dry run equal to delivery 8 on lag-invariant figures, LIVE S2 run once per pair (registry 20 -> 26 lines), S1 regression before and after, STATUS and NOTES refreshed, message-21"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
secret_guard
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
