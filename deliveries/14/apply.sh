#!/bin/bash
# deliveries/14/apply.sh -- D2, Work Order 1.7, M2's rulings of 2026-10-27: masked primary, scratch dry run, automatic checks, and (ONLY with --go-live-t3)
# the live Task 3 run, once per pair.
#
# Put apply.sh, check_t3.py, formula_t3.py, run_t3.py, STATUS.md and NOTES.md together in ~/apps/crypto_bot/deliveries/14/ and run:
#     bash ~/apps/crypto_bot/deliveries/14/apply.sh                  (steps 1-5 only: commits nothing, writes nothing live)
#     bash ~/apps/crypto_bot/deliveries/14/apply.sh --go-live-t3     (only when the owner's message says "go live T3")
# What it does:
#   1. checks hashes, the folder (clean, on main, user_data/analysis byte-identical to commit 090d55b), the live registry (26 lines) and the secret-keys guard;
#   2. backs up, puts the code in place, runs ALL self-tests (41; includes "a zero-volume bar behaves exactly like a missing bar");
#   3. regression BEFORE: the S1 report (equal to delivery 9's post-S2 state) and the S2 report (equal to the committed one) are regenerated read-only;
#   4. variant output with the masked reading as PRIMARY: must equal the delivery-13 variant file (masked rows and the literal-reading sensitivity rows) to the printed digits;
#   5. a scratch dry run of both pairs (masked primary): its four primary cells must equal the masked rows to the printed digits;
#   6. without --go-live-t3: stop, put everything back, commit nothing. With it:
#   7. the live run (once per pair, two records each): live equals the dry run apart from timestamps, the first 26 registry lines byte-identical; S1 and S2 regressions AFTER
#      (summary tables identical; only the across-candidate Holm rows and cumulative counts change, by design: R1);
#   8. commits exact paths and pushes. On any failure before the commit it puts everything back, the live registry included.
set -e

LIVE=0; REPO_ARG=""
for a in "$@"; do
  case "$a" in
    --go-live-t3) LIVE=1 ;;
    *) REPO_ARG="$a" ;;
  esac
done
REPO="${REPO_ARG:-$HOME/apps/crypto_bot}"
EXP_CHECK_T3="481dbbff72df00aee1d9c5a6d0287f5a9626a209b68faa640a4c0f01dc0145b8"
EXP_FORMULA_T3="a3f081bf034a007a4b1fa6f7238aef06ce5e727935cdd4e31454ce941e40759f"
EXP_RUN_T3="7b6e736201955a81f8614ebb56c4fbea10d85eb001a102e18c35c4b6674277ec"
EXP_STATUS="26debf5a06d21597e3b28bf993069f03b568105dd554a5ff38d44ea365c2faf6"
EXP_NOTES="8dc01c41222e7fccf17560b50f51ffd2d75964d5acb12c9a58519c26a3d6f163"
EXP_CHECK_REPORTS="6d379e65d07ef57161f438f6bcc589174953ccbd0174dd7daddd4118c0558f07"
OLD_FORMULA_T3="080902171f034d9529e253a2d4466464b9e4feb81093c9a295fc92ca3d82a261"
OLD_RUN_T3="446438c679073fe3b42bbee8f83173b3a9246020ff52848fac771b949eef0c63"
OLD_STATUS="b324b5632a66085b304b32d13d8065c3a5043a01943072bad47c5e421701ef85"
OLD_NOTES="817a38947f58456e93f850a6942ef45e61064a5a199ff0f8f2fc10c50bea3bc8"
LIVE_REG_SHA="c26ad4811f76752007ce803b4f2c62d45f5cf6c91be08cf19193c67f589b696b"
BASE_COMMIT="090d55b"
REG="user_data/analysis/results/registry.jsonl"
OLD_VARIANT="docs/reports/t3-variant-zero-volume-step2.txt"
R_DRY="docs/reports/t3-dry-run-masked-step3.txt"
R_REC="docs/reports/t3-dry-run-records-masked-step3.jsonl"
R_VAR="docs/reports/t3-variant-masked-step3.txt"
R_CHK="docs/reports/t3-checks-step3.txt"
R_REG="docs/reports/t3-regression-after-t3-step3.txt"
NEWFILES="$R_DRY $R_REC $R_VAR $R_CHK $R_REG"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/formula_t3.py user_data/analysis/run_t3.py context/STATUS.md context/developer/NOTES.md "$REG" 2>/dev/null
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
secret_guard() {  # never opens the file
  if git ls-files --error-unmatch temp/secret_keys.txt >/dev/null 2>&1; then die "temp/secret_keys.txt is TRACKED by git; refusing to push. Tell the owner (do not paste the file)."; fi
  if [ -n "$(git log --all --oneline -- temp/secret_keys.txt 2>/dev/null)" ]; then die "temp/secret_keys.txt appears in a commit; refusing to push. Tell the owner (do not paste the file)."; fi
  if ! git check-ignore -q temp/secret_keys.txt 2>/dev/null; then echo "WARNING: temp/secret_keys.txt is not git-ignored; D2 will add temp/ to .gitignore in the next delivery (this script adds nothing but its own exact paths)."; fi
}

echo "== delivery 14 (D2, WO 1.7: masked primary, dry run, checks$( [ "$LIVE" = "1" ] && echo ', LIVE run' )) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/14" ] || die "apply.sh must sit in $REPO/deliveries/14/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "check_t3.py:$EXP_CHECK_T3" "formula_t3.py:$EXP_FORMULA_T3" "run_t3.py:$EXP_RUN_T3" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/14/' || true)"
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
[ "$(sha user_data/analysis/formula_t3.py)" = "$OLD_FORMULA_T3" ] || die "formula_t3.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/run_t3.py)" = "$OLD_RUN_T3" ] || die "run_t3.py is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
[ "$(sha deliveries/12/check_reports.py)" = "$EXP_CHECK_REPORTS" ] || die "deliveries/12/check_reports.py is not the verified version"
for f in $NEWFILES; do [ ! -e "$f" ] || die "$f already exists"; done
[ -f "$OLD_VARIANT" ] || die "$OLD_VARIANT (delivery 13) is missing"
[ -f docs/correspondence/answer-t3-rulings.md ] || die "docs/correspondence/answer-t3-rulings.md (M2's rulings) is missing"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] && [ "$(wc -l < $REG | tr -d ' ')" = "26" ] || die "the live registry is not the 26-line file; refusing to continue (a second Task 3 live run is not allowed)"
echo "live registry: 26 lines, unchanged since the S2 live run"
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
LOG="$REPO/temp/selftest-step14-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 30 lines of the log:"; tail -30 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q 'exact reproduction' "$LOG" && grep -q 'zero-volume bar (primary, masked)' "$LOG" && grep -q 'Self-test passed: run_t3' "$LOG" || die "the formula_t3 / run_t3 self-tests did not report success"
grep -E 'exact reproduction|zero-volume bar' "$LOG" | cut -c1-300 || true
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"

regress() {  # $1 = before|after
  OUT1="$REPO/temp/s1-report-$1-$STAMP.md"
  ( cd user_data/analysis && "$PYBIN" s1_report.py --pair ETH_USDT --pair BTC_USDT --out "$OUT1" --void-commit ac63ff2 --run-commit 4487f1e --code-commit "$CODE_COMMIT" ) || die "the S1 report generator refused ($1)"
  OUT2="$REPO/temp/s2-report-$1-$STAMP.md"
  ( cd user_data/analysis && "$PYBIN" s2_report.py --pair ETH_USDT --pair BTC_USDT --out "$OUT2" --trades-dir "$REPO/temp/s2-trades-$1-$STAMP" --run-commit 294afb8 --code-commit "$CODE_COMMIT" --skip-null ) || die "the S2 report generator refused ($1)"
  if [ "$1" = "before" ]; then
    "$PYBIN" deliveries/12/check_reports.py docs/reports/s1-report-step6.md "$OUT1" --kind s1 --mode after --ref-diff docs/reports/s1-regression-after-s2-step3.txt || die "S1 regression ($1)"
    "$PYBIN" deliveries/12/check_reports.py docs/reports/s2-report-step3.md "$OUT2" --kind s2 --mode before || die "S2 regression ($1)"
  else
    { echo "S1 and S2 reports regenerated after the Task 3 live records (registry 30 lines) against the committed reports: differing lines. Allowed by design (R1): the across-candidate Holm rows, the cumulative counts, the generation stamp; summary tables identical (S2: but for the Holm-across-candidates column)."
      "$PYBIN" deliveries/12/check_reports.py docs/reports/s1-report-step6.md "$OUT1" --kind s1 --mode after || true
      "$PYBIN" deliveries/12/check_reports.py docs/reports/s2-report-step3.md "$OUT2" --kind s2 --mode after || true; } > "$R_REG" 2>&1
    grep -q "REGRESSION CHECK PASSED" "$R_REG" && [ "$(grep -c 'REGRESSION CHECK PASSED' "$R_REG")" = "2" ] && ! grep -q "REGRESSION CHECK FAILED" "$R_REG" || { cat "$R_REG" | cut -c1-220; die "S1/S2 regression ($1) failed"; }
  fi
}

echo "-- 3. regression BEFORE any Task 3 record: S1 (delivery 9's post-S2 state) and S2 (the committed report)"
regress before
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the regression"
echo "S1 and S2 reports reproduce: every recorded figure unchanged"

echo "-- 4. variant output with the MASKED reading as primary against the delivery-13 variant file"
( cd user_data/analysis && for P in ETH_USDT BTC_USDT; do "$PYBIN" run_t3.py --pair "$P" --variant-zero-volume || exit 1; done ) > "$R_VAR" 2>&1 || { cat "$R_VAR"; die "the variant run failed"; }
cat "$R_VAR"
{ echo "== check 1: masked-primary variant output against $OLD_VARIANT"; "$PYBIN" "$HERE/check_t3.py" variant "$OLD_VARIANT" "$R_VAR"; } > "$R_CHK" 2>&1 || { cat "$R_CHK"; die "the masked primary does not reproduce the delivery-13 variant rows"; }
cat "$R_CHK"

echo "-- 5. scratch dry run of both pairs (masked primary); the primary cells must equal the masked variant rows"
DRY="$REPO/temp/t3-dryrun-masked-$STAMP.jsonl"
DRYOUT="$REPO/temp/t3-dryrun-masked-$STAMP.txt"
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
assert all(r["detail"]["masked_zero_volume"] > 0 for r in recs if r["status"] == "discovery")
print("scratch records:", got)
PYEOF
{ echo; echo "== check 2: dry-run primary cells against the masked variant rows"; "$PYBIN" "$HERE/check_t3.py" dry-vs-variant "$DRY" "$R_VAR"; } >> "$R_CHK" 2>&1 || { tail -12 "$R_CHK"; die "the dry-run primary cells differ from the masked variant rows"; }
tail -3 "$R_CHK"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the dry run"

if [ "$LIVE" != "1" ]; then
  echo
  echo "STOP (by design): started without --go-live-t3, so the live run is not executed. Steps 1-5 passed. Everything is put back and nothing is committed."
  echo "When the owner says \"go live T3\":  bash $HERE/apply.sh --go-live-t3"
  rollback
  FINISHED=1
  echo "OK (dry steps only)"
  exit 0
fi

echo "-- 6. LIVE run, once per pair (explicit --go-live-t3)"
secret_guard
( cd user_data/analysis && for P in ETH_USDT BTC_USDT; do "$PYBIN" run_t3.py --pair "$P" --commit-to-registry || exit 1; done ) > "$REPO/temp/t3-live-$STAMP.txt" 2>&1 || { cat "$REPO/temp/t3-live-$STAMP.txt"; die "the live run failed; the registry is put back; nothing committed. Paste this output into the chat."; }
grep -E '^REGISTRY: ' "$REPO/temp/t3-live-$STAMP.txt" || true
[ "$(wc -l < $REG | tr -d ' ')" = "30" ] || die "the live registry does not hold exactly 30 lines after the live run"
head -n 26 $REG | cmp -s - "$BK/registry.jsonl" || die "the first 26 live registry lines are not byte-identical to the backup"
tail -n 4 $REG > "$REPO/temp/t3-live-records-$STAMP.jsonl"
{ echo; echo "== check 3: live records against the dry-run records"; "$PYBIN" "$HERE/check_t3.py" live-vs-dry "$DRY" "$REPO/temp/t3-live-records-$STAMP.jsonl"; } >> "$R_CHK" 2>&1 || { tail -10 "$R_CHK"; die "the live records differ from the dry run"; }
tail -3 "$R_CHK"
"$PYBIN" - "$REG" <<'PYEOF' || die "the live registry holds an unexpected record"
import json, sys
recs = [json.loads(l) for l in open(sys.argv[1])]
tail = [(r["family"], r["status"]) for r in recs[26:]]
want = [(f, s) for f in ("Task3-ETHUSDT", "Task3-BTCUSDT") for s in ("discovery", "stability")]
assert tail == want, tail
assert not any(r["status"] in ("frozen", "holdout_consumed") for r in recs[26:])
print("live registry: 30 lines; records 27-30 =", tail)
PYEOF
echo "live registry: first 26 lines byte-identical; records 27-30 equal the dry run apart from timestamps"

echo "-- 7. S1 and S2 regression AFTER the live Task 3 records"
regress after
cut -c1-200 "$R_REG" | grep -E "regression|PASSED" | head -6

echo "-- 8. place documents, commit, push"
mkdir -p docs/reports
{ echo "Task 3 dry run with the MASKED primary (M2's ruling 2 of 2026-10-27), scratch registry, produced by deliveries/14/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $CODE_COMMIT)"; echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"; echo "command: python3 run_t3.py --pair <PAIR> --registry-path <scratch file>"; cat "$DRYOUT"; } > "$R_DRY"
cp "$DRY" "$R_REC"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] || die "a document copy failed verification"
secret_guard
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
PATHS="user_data/analysis/formula_t3.py user_data/analysis/run_t3.py context/developer/NOTES.md context/STATUS.md $REG $R_DRY $R_REC $R_VAR $R_CHK $R_REG deliveries/14/apply.sh deliveries/14/check_t3.py deliveries/14/formula_t3.py deliveries/14/run_t3.py deliveries/14/STATUS.md deliveries/14/NOTES.md"
git add $PATHS
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="$(printf '%s\n' $PATHS | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected sixteen: $STAGED"
git commit -q -m "[D2] WO 1.7: masked primary (M2 ruling 2), dose-response ruling 4, checks against the variant rows, LIVE Task 3 run once per pair (registry 26 -> 30 lines), S1/S2 regressions before and after, STATUS/NOTES"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
secret_guard
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
