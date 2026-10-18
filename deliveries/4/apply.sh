#!/bin/bash
# deliveries/4/apply.sh -- D1, Work Order 1.5, step 4 (amended stability statistic + acceptance tests).
#
# Put apply.sh, stability_check.py, stability_acceptance.py, formula_s1.py, run_s1.py, selftest_all.sh,
# NOTES.md, STATUS.md and message-17.md together in ~/apps/crypto_bot/deliveries/4/ and run:
#     bash ~/apps/crypto_bot/deliveries/4/apply.sh
# This one takes several minutes (about 10 on a laptop): all 35 self-tests, then the FULL acceptance run
# (200 paths, R = 1000) twice (production, then the mathematician's reference with the same seeds). Keep the
# laptop awake and plugged in. The live registry is never written.
# What it does:
#   1. checks the SHA-256 of the delivered files (stops on mismatch);
#   2. checks the folder is clean, on main, contains delivery 3 (756f56a), and the files it replaces are the expected versions;
#   3. backs up the files it replaces into temp/backup-<UTC>/;
#   4. puts the new files in place and runs ALL self-tests (35), then checks the live registry did not change;
#   5. runs the FULL acceptance tests with --compare-reference and saves the output as
#      docs/reports/stability-acceptance-full-step4.txt. All four S1 rows must pass and production must equal the
#      reference; the S2 rows are REPORTED (a failing S2 row is evidence for the mathematician, not a stop);
#   6. commits exactly eighteen paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_STABILITY="d2123391d8726a827d4a08eced7078326bc36be230476797b6136016867925e3"
EXP_ACCEPT="c95a5342a39b81ebfb6f442d644e5b0da81ed8b18e7d277782438d2293c4d5ba"
EXP_FORMULA="2192ff9c8e7d664cf8f53640ac472f3c8aa5d535eab3834d63d357a8f9dc8d4c"
EXP_RUN_S1="fd9db76a94844ce3f3126a2088ea7441ab45566447c294da7b33b6e9089084b5"
EXP_SELFTEST_ALL="6ec972ee24545b819ee28dbedd39e76417f76867b4fd5c1a9aa7c5bfae5780f9"
EXP_NOTES="dd5a81862dabdddf7bda507a725073c0b3c463dad97d05ec56800de2a57d76b9"
EXP_STATUS="e15f19d06345966830dab6de9430adc25eb6405b9abeb207bf12222a36f4b80c"
EXP_MSG17="b8898f5d3cc48fbc738ac786f03e687355411df771a678f7bf342866d6d8df4a"
OLD_STABILITY="9a8f29dbd1aae6d5eceb05b7a06fbd22e3673939a2795319b36197067ee128d6"
OLD_FORMULA="cbbc28b7111f7c33d1216c83d2489a9418033939cf668d7b7db6683fded9c58a"
OLD_RUN_S1="1e78e566c43d52836d73f019db57b26e31fd0a7bb8f9440173031391427dde06"
OLD_SELFTEST_ALL="4615fd1bf82258da772c5d40176afbe38bc8fd59766ea1b3c282e62d301edfdb"
OLD_NOTES="3d32db9ca1cd3d2d431fa78188a835b6d35f7d0de2267156078222435ce6a706"
OLD_STATUS="0e4972b1fa0dffc7993bdd769af5160e0bc0b4460fedb538f298fd10230bba47"
LIVE_REG_SHA="70c91da708f7397251c224a111aada2932dfc0d1bb25ec13e0480dab320f9fe2"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/formula_s1.py user_data/analysis/run_s1.py user_data/analysis/selftest_all.sh user_data/analysis/stability_check.py context/developer/NOTES.md context/STATUS.md 2>/dev/null
  rm -f user_data/analysis/stability_acceptance.py docs/correspondence/message-17.md docs/reports/stability-acceptance-full-step4.txt
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

echo "== delivery 4 (D1, WO 1.5 step 4) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/4" ] || die "apply.sh must sit in $REPO/deliveries/4/ (it is in $HERE)"

echo "-- 1. SHA-256 of the delivered files"
BAD=0
for pair in "stability_check.py:$EXP_STABILITY" "stability_acceptance.py:$EXP_ACCEPT" "formula_s1.py:$EXP_FORMULA" "run_s1.py:$EXP_RUN_S1" "selftest_all.sh:$EXP_SELFTEST_ALL" "NOTES.md:$EXP_NOTES" "STATUS.md:$EXP_STATUS" "message-17.md:$EXP_MSG17"; do
  f="${pair%%:*}"; want="${pair##*:}"
  [ -f "$HERE/$f" ] || die "missing file $HERE/$f"
  got="$(sha "$HERE/$f")"
  echo "$f  $got"
  [ "$got" = "$want" ] || BAD=1
done
[ "$BAD" = "0" ] || die "HASH MISMATCH - nothing was applied. Download the files again into $HERE"
echo "hashes match"

cd "$REPO"
echo "-- 2. state checks and update"
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || die "not on branch main"
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/4/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; fi
git merge-base --is-ancestor 756f56a HEAD || die "delivery 3 (756f56a) is not in your history; run delivery 3 first"
echo "folder clean, on main, HEAD $(git rev-parse --short HEAD), contains delivery 3 (756f56a)"
[ "$(sha user_data/analysis/stability_check.py)" = "$OLD_STABILITY" ] || die "stability_check.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/formula_s1.py)" = "$OLD_FORMULA" ] || die "formula_s1.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/run_s1.py)" = "$OLD_RUN_S1" ] || die "run_s1.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "developer/NOTES.md is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ ! -e user_data/analysis/stability_acceptance.py ] && [ ! -e docs/correspondence/message-17.md ] && [ ! -e docs/reports/stability-acceptance-full-step4.txt ] || die "stability_acceptance.py, message-17.md or the acceptance report already exists"
REG="user_data/analysis/results/registry.jsonl"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the live registry is not the 14-line file committed in ac63ff2 (hash differs); nothing touched"
echo "files to replace are the expected versions; live registry is the 14-line file from ac63ff2"

echo "-- 3. backup (inside the project)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/stability_check.py user_data/analysis/formula_s1.py user_data/analysis/run_s1.py user_data/analysis/selftest_all.sh "$BK/"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
cp context/STATUS.md "$BK/STATUS.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"

echo "-- 4. new files in place, then ALL self-tests (about 1 to 3 minutes)"
APPLIED=1
cp "$HERE/stability_check.py" user_data/analysis/stability_check.py
cp "$HERE/stability_acceptance.py" user_data/analysis/stability_acceptance.py
cp "$HERE/formula_s1.py" user_data/analysis/formula_s1.py
cp "$HERE/run_s1.py" user_data/analysis/run_s1.py
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
[ "$(sha user_data/analysis/stability_check.py)" = "$EXP_STABILITY" ] && [ "$(sha user_data/analysis/stability_acceptance.py)" = "$EXP_ACCEPT" ] && [ "$(sha user_data/analysis/formula_s1.py)" = "$EXP_FORMULA" ] && [ "$(sha user_data/analysis/run_s1.py)" = "$EXP_RUN_S1" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] || die "a code copy failed verification"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
echo "python: $("$PYBIN" --version 2>&1)"
LOG="$REPO/temp/selftest-step4-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
echo "reduced acceptance run (inside the self-tests):"
awk '/^=================== stability_acceptance.py/{f=1;next} /^=================== /{f=0} f' "$LOG" | cut -c1-140
echo "full log: $LOG"
[ "$ST_CODE" -eq 0 ] || { echo "last 25 lines of the log:"; tail -25 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q '^=================== stability_acceptance.py' "$LOG" || die "the acceptance test did not run inside the self-tests"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/4/' | LC_ALL=C sort | tr '\n' '|')"
WANT2=" M user_data/analysis/formula_s1.py| M user_data/analysis/run_s1.py| M user_data/analysis/selftest_all.sh| M user_data/analysis/stability_check.py|?? user_data/analysis/stability_acceptance.py|"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the self-tests"; }
echo "no stray files after the self-tests"

echo "-- 5. FULL acceptance run (200 paths, R = 1000) + the mathematician's reference with the same seeds (about 5 to 10 minutes)"
ACC="$REPO/temp/stability-acceptance-full-$STAMP.txt"
{
  echo "Stability acceptance, FULL run, Work Order 1.5 step 4"
  echo "produced by deliveries/4/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $(git rev-parse --short HEAD))"
  echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"
  echo "command: python3 stability_acceptance.py --full --compare-reference   (bands are the work order's section 4; not changed)"
  echo
} > "$ACC"
set +e
( cd user_data/analysis && "$PYBIN" stability_acceptance.py --full --compare-reference ) 2>&1 | tee -a "$ACC"
ACC_CODE="${PIPESTATUS[0]}"
set -e
echo "(acceptance harness exit status: $ACC_CODE)"
S1_PASS="$(grep -c '^  PASS  S1 ' "$ACC" || true)"
S1_FAIL="$(grep -c '^  FAIL  S1 ' "$ACC" || true)"
[ "$S1_PASS" = "4" ] && [ "$S1_FAIL" = "0" ] || die "not all four S1 rows passed (pass=$S1_PASS fail=$S1_FAIL); nothing committed"
grep -q 'IDENTICAL to the reference' "$ACC" || die "production is NOT identical to the mathematician's reference at full scale; nothing committed"
S2_FAIL="$(grep -c '^  FAIL  S2 ' "$ACC" || true)"
echo "S1 rows: 4 of 4 pass; production identical to the reference."
if [ "$S2_FAIL" != "0" ]; then
  echo "NOTE: $S2_FAIL S2 row(s) outside their band; reported to the mathematician in message-17 and in the committed output (not a stop for this delivery):"
  grep '^  FAIL  S2 ' "$ACC"
fi
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the acceptance run"

echo "-- 6. place documents, commit, push"
mkdir -p docs/reports
cp "$ACC" docs/reports/stability-acceptance-full-step4.txt
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-17.md" docs/correspondence/message-17.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-17.md)" = "$EXP_MSG17" ] || die "a document copy failed verification"
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
git add user_data/analysis/stability_check.py user_data/analysis/stability_acceptance.py user_data/analysis/formula_s1.py user_data/analysis/run_s1.py user_data/analysis/selftest_all.sh context/developer/NOTES.md context/STATUS.md docs/correspondence/message-17.md docs/reports/stability-acceptance-full-step4.txt deliveries/4/apply.sh deliveries/4/stability_check.py deliveries/4/stability_acceptance.py deliveries/4/formula_s1.py deliveries/4/run_s1.py deliveries/4/selftest_all.sh deliveries/4/NOTES.md deliveries/4/STATUS.md deliveries/4/message-17.md
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="context/STATUS.md context/developer/NOTES.md deliveries/4/NOTES.md deliveries/4/STATUS.md deliveries/4/apply.sh deliveries/4/formula_s1.py deliveries/4/message-17.md deliveries/4/run_s1.py deliveries/4/selftest_all.sh deliveries/4/stability_acceptance.py deliveries/4/stability_check.py docs/correspondence/message-17.md docs/reports/stability-acceptance-full-step4.txt user_data/analysis/formula_s1.py user_data/analysis/run_s1.py user_data/analysis/selftest_all.sh user_data/analysis/stability_acceptance.py user_data/analysis/stability_check.py "
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected eighteen: $STAGED"
git commit -q -m "[D1] WO 1.5 step 4: amended stability statistic (global centring, bootstrap null), acceptance tests (reduced in selftest_all.sh; full run output committed), old rule removed; message-17"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
