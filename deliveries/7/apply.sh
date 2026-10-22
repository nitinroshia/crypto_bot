#!/bin/bash
# deliveries/7/apply.sh -- D2, Work Order 1.6, step 1: formula_s2.py with self-tests, the S2 acceptance confirmation run.
#
# Put apply.sh, formula_s2.py, stability_acceptance.py, selftest_all.sh, diag_state.sh, PROTOCOL.md, STATUS.md, NOTES.md and
# message-20.md together in ~/apps/crypto_bot/deliveries/7/ and run:   bash ~/apps/crypto_bot/deliveries/7/apply.sh
# It does not touch the live registry, the holdout or any data file; it does not freeze or forward-test. What it does:
#   1. checks the SHA-256 of the delivered files, the state of the folder (clean, on main, user_data/analysis byte-identical
#      to commit a787d41) and that the live registry is the 20-line file from the S1 live run;
#   2. backs up what it replaces, puts the new code in place and runs ALL self-tests (37), including the new formula_s2.py;
#   3. regenerates the S1 report read-only (it refuses unless every recomputed S1 figure reproduces the registry) and requires
#      its summary table to equal the committed one: the regression check for this delivery;
#   4. runs the S2 false-pass confirmation (1000 paths per row, R 2000, a few minutes) and keeps its output;
#   5. commits exactly 18 paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
# Everything it writes stays inside the project root (backups and logs go to temp/).
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_FORMULA_S2="73ba9b2f0069a5138eed36df509017599719d14055d7607557e4264d1d70dcba"
EXP_ACCEPT="1142b4f4a0c14b48306cd64978867cb63405086229e33a2caf6925a1c94427f3"
EXP_SELFTEST_ALL="61f23574127474ce98155166440d0d4ca69b39ac059530c667954dda7b610252"
EXP_DIAG="728340bb09b970299a1ca2d919a7cebc523f2029b8c4a91f0d15511f15de6936"
EXP_PROTOCOL="ce3ee7f9b85fd4c3c3235b38fd12004487ec985a83f3f309f20af6a3a7e9aa58"
EXP_STATUS="c505f1384fe54e866661693a239ef082714e77351d0e3c1adabf030f49fd0c5b"
EXP_NOTES="b6273a0e8294d71c65ff6feefca2d50fff29878b5d371632067f100bb712b8ae"
EXP_MSG20="642b1d01e41b639e3405bb0d3e67e2ac331522a83702b1bd9fa9a85d81304e33"
OLD_ACCEPT="c95a5342a39b81ebfb6f442d644e5b0da81ed8b18e7d277782438d2293c4d5ba"
OLD_SELFTEST_ALL="9974f5d234212e423151ca67ea8181a0e857ebdbaee3ad08b3247eda9fcac826"
OLD_DIAG="ed1f3821708be7c7fe6e25361d30506e47ee3c454a75562794e42e282cc99b91"
OLD_PROTOCOL="0c85442f3ade3af192d9a02a0e4d071caf4b081c9f9e1c8ac39640a5f3503114"
OLD_STATUS="c7a44a56ef062d47546657fb636c33df021003ff2f8db7bb019322730b0e2d49"
OLD_NOTES="a921f4da78fd86620739a31afa5762f9884e5a3f5ba80f1adc1c682f58e21ae6"
LIVE_REG_SHA="5ad0607c5bfd6ab24d7438a2c5edbdd5cb845d7cff28b4846b640c663c242779"
BASE_COMMIT="a787d41"
RUN_COMMIT="4487f1e"
REG="user_data/analysis/results/registry.jsonl"
CONF_FILE="docs/history/2026-10-21_s2-null-confirmation.txt"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/selftest_all.sh user_data/analysis/stability_acceptance.py scripts/diag_state.sh docs/PROTOCOL.md context/STATUS.md context/developer/NOTES.md 2>/dev/null
  rm -f user_data/analysis/formula_s2.py docs/correspondence/message-20.md "$CONF_FILE"
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

echo "== delivery 7 (D2, WO 1.6 step 1: formula_s2.py, self-tests, S2 acceptance confirmation) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/7" ] || die "apply.sh must sit in $REPO/deliveries/7/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "formula_s2.py:$EXP_FORMULA_S2" "stability_acceptance.py:$EXP_ACCEPT" "selftest_all.sh:$EXP_SELFTEST_ALL" "diag_state.sh:$EXP_DIAG" "PROTOCOL.md:$EXP_PROTOCOL" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES" "message-20.md:$EXP_MSG20"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/7/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; fi
git merge-base --is-ancestor "$BASE_COMMIT" HEAD || die "commit $BASE_COMMIT is not in your history"
git diff --quiet "$BASE_COMMIT" -- user_data/analysis || die "user_data/analysis differs from commit $BASE_COMMIT (the verified code); refusing to continue"
CODE_COMMIT="$(git rev-parse --short HEAD)"
echo "folder clean, on main, HEAD $CODE_COMMIT; user_data/analysis is byte-identical to $BASE_COMMIT"
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha user_data/analysis/stability_acceptance.py)" = "$OLD_ACCEPT" ] || die "stability_acceptance.py is not the version this delivery replaces"
[ "$(sha scripts/diag_state.sh)" = "$OLD_DIAG" ] || die "scripts/diag_state.sh is not the version this delivery replaces"
[ "$(sha docs/PROTOCOL.md)" = "$OLD_PROTOCOL" ] || die "docs/PROTOCOL.md is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
[ ! -e user_data/analysis/formula_s2.py ] && [ ! -e docs/correspondence/message-20.md ] && [ ! -e "$CONF_FILE" ] || die "formula_s2.py, message-20.md or the confirmation file already exists"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the live registry is not the 20-line file from the S1 live run ($RUN_COMMIT); refusing to continue"
echo "live registry: $(wc -l < $REG | tr -d ' ') lines, identical to the file committed in $RUN_COMMIT"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
for f in ETH_USDT BTC_USDT; do
  for kind in 1h 1d funding; do
    ls user_data/data/binance*/"$f-$kind.feather" >/dev/null 2>&1 || die "data file $f-$kind.feather not found under user_data/data/"
  done
done
echo "data files present for both pairs (1h, 1d, funding)"

echo "-- 2. backup, new code in place, then ALL self-tests"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/selftest_all.sh user_data/analysis/stability_acceptance.py scripts/diag_state.sh docs/PROTOCOL.md "$BK/"
cp context/STATUS.md "$BK/STATUS.md"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"
APPLIED=1
cp "$HERE/formula_s2.py" user_data/analysis/formula_s2.py
cp "$HERE/stability_acceptance.py" user_data/analysis/stability_acceptance.py
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
cp "$HERE/diag_state.sh" scripts/diag_state.sh
cp "$HERE/PROTOCOL.md" docs/PROTOCOL.md
[ "$(sha user_data/analysis/formula_s2.py)" = "$EXP_FORMULA_S2" ] && [ "$(sha user_data/analysis/stability_acceptance.py)" = "$EXP_ACCEPT" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] && [ "$(sha scripts/diag_state.sh)" = "$EXP_DIAG" ] && [ "$(sha docs/PROTOCOL.md)" = "$EXP_PROTOCOL" ] || die "a copy failed verification"
echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"
LOG="$REPO/temp/selftest-step7-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 25 lines of the log:"; tail -25 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q '^=================== formula_s2.py' "$LOG" || die "the formula_s2 self-test did not run"
grep -q 'Self-test passed in [0-9]*s: formula_s2.py' "$LOG" || die "the formula_s2 self-test did not report success"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/7/' | LC_ALL=C sort | tr '\n' '|')"
WANT2=" M scripts/diag_state.sh| M docs/PROTOCOL.md| M user_data/analysis/selftest_all.sh| M user_data/analysis/stability_acceptance.py|?? user_data/analysis/formula_s2.py|"
DIRTY2="$(echo "$DIRTY2" | tr '|' '\n' | sed '/^$/d' | LC_ALL=C sort | tr '\n' '|')"
WANT2="$(echo "$WANT2" | tr '|' '\n' | sed '/^$/d' | LC_ALL=C sort | tr '\n' '|')"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the self-tests"; }
echo "live registry byte-identical after the self-tests; no stray files"

echo "-- 3. regression: the S1 report generator must still reproduce S1's recorded figures"
REG_REPORT="$REPO/temp/s1-report-regression-$STAMP.md"
( cd user_data/analysis && "$PYBIN" s1_report.py --pair ETH_USDT --pair BTC_USDT --out "$REG_REPORT" --void-commit ac63ff2 --run-commit "$RUN_COMMIT" --code-commit "$CODE_COMMIT" ) || die "the S1 report generator refused (a recomputed S1 figure does not match the registry, or data is missing); nothing committed"
[ -s "$REG_REPORT" ] || die "the regression report was not written"
sed -n '/^### Summary of recorded outcomes/,/^## ETH_USDT/p' "$REG_REPORT" > "$BK/summary-new.txt"
sed -n '/^### Summary of recorded outcomes/,/^## ETH_USDT/p' docs/reports/s1-report-step6.md > "$BK/summary-committed.txt"
[ -s "$BK/summary-new.txt" ] && cmp -s "$BK/summary-new.txt" "$BK/summary-committed.txt" || die "the regenerated S1 summary table differs from the committed S1 report"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed while regenerating the S1 report"
echo "S1 report regenerated read-only: every recomputed figure reproduces the registry and the summary table equals the committed one"

echo "-- 4. S2 false-pass confirmation run (1000 paths per row, R 2000; a few minutes)"
CONF_OUT="$REPO/temp/s2-null-confirmation-$STAMP.out"
set +e
( cd user_data/analysis && "$PYBIN" stability_acceptance.py --confirm-s2-null ) > "$CONF_OUT" 2>&1
CONF_CODE=$?
set -e
cat "$CONF_OUT"
[ "$CONF_CODE" -eq 0 ] || die "the S2 false-pass confirmation run failed (a rate above 7%); nothing committed. Paste this output into the chat."
grep -q '^S2 FALSE-PASS CONFIRMATION PASSED' "$CONF_OUT" || die "the confirmation output lacks its PASS line"
mkdir -p docs/history
{
  echo "S2 false-pass confirmation run (answer-to-message-19 section 3a), produced by deliveries/7/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $CODE_COMMIT)"
  echo "python: $("$PYBIN" --version 2>&1); numpy: $("$PYBIN" -c 'import numpy; print(numpy.__version__)')"
  echo "command: python3 stability_acceptance.py --confirm-s2-null   (rule: a false-pass row passes at <= 7% at 200 paths OR <= 7% in a confirmation of >= 1000 paths)"
  echo
  cat "$CONF_OUT"
} > "$CONF_FILE"
[ -s "$CONF_FILE" ] || die "the confirmation file was not written"

echo "-- 5. place documents, commit, push"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-20.md" docs/correspondence/message-20.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-20.md)" = "$EXP_MSG20" ] || die "a document copy failed verification"
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
git add user_data/analysis/formula_s2.py user_data/analysis/stability_acceptance.py user_data/analysis/selftest_all.sh scripts/diag_state.sh docs/PROTOCOL.md context/developer/NOTES.md context/STATUS.md docs/correspondence/message-20.md "$CONF_FILE" deliveries/7/apply.sh deliveries/7/formula_s2.py deliveries/7/stability_acceptance.py deliveries/7/selftest_all.sh deliveries/7/diag_state.sh deliveries/7/PROTOCOL.md deliveries/7/NOTES.md deliveries/7/STATUS.md deliveries/7/message-20.md
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="context/STATUS.md context/developer/NOTES.md deliveries/7/NOTES.md deliveries/7/PROTOCOL.md deliveries/7/STATUS.md deliveries/7/apply.sh deliveries/7/diag_state.sh deliveries/7/formula_s2.py deliveries/7/message-20.md deliveries/7/selftest_all.sh deliveries/7/stability_acceptance.py docs/PROTOCOL.md docs/correspondence/message-20.md $CONF_FILE scripts/diag_state.sh user_data/analysis/formula_s2.py user_data/analysis/selftest_all.sh user_data/analysis/stability_acceptance.py "
WANT="$(echo "$WANT" | tr ' ' '\n' | sed '/^$/d' | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected eighteen: $STAGED"
git commit -q -m "[D2] WO 1.6 step 1: formula_s2.py with self-tests, S2 acceptance rule and confirmation run, diag output inside the project root, message-20"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
