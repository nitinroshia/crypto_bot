#!/bin/bash
# deliveries/2/apply.sh -- D1, Work Order 1.5, step 2 (registry hygiene: live writes only with an explicit flag).
#
# Put apply.sh, registry.py, run_s1.py, selftest_all.sh, selftest_registry_hygiene.py, NOTES.md, STATUS.md and
# message-15.md together in ~/apps/crypto_bot/deliveries/2/ and run:   bash ~/apps/crypto_bot/deliveries/2/apply.sh
# What it does (the live registry is never written by this script):
#   1. checks the SHA-256 of the delivered files (stops on mismatch);
#   2. checks the folder is clean, on main, contains delivery 1 (ac63ff2), and the files it replaces are the expected versions;
#   3. backs up the files it replaces into temp/backup-<UTC>/;
#   4. puts the new files in place and runs ALL self-tests (now 34), then checks the live registry did not change;
#   5. read-only checks of the live-registry guard against the REAL file (no write is attempted);
#   6. commits exactly fifteen paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_REGISTRY_PY="1ebb3316e3c5eadcd678d6b0afd05559efa21ae39d41af57f38aaef990dd0751"
EXP_RUN_S1="233c3a1177662048f1442a7a251c96b8490aabce3513210a92e8bb1d6e42c355"
EXP_SELFTEST_ALL="4615fd1bf82258da772c5d40176afbe38bc8fd59766ea1b3c282e62d301edfdb"
EXP_HYGIENE="b5e4615ecb3123731fa5bb6bdeac2f20be2a113e493b86a608b7c888f7b414a7"
EXP_NOTES="b816c9eb50ea89dece94bf4f913b6455597da3ed87baef9259ea60615c19b16b"
EXP_STATUS="2f892141b40c20e20f1caf1d2b22640210d1f03b84155f694a3dfff18fe8d773"
EXP_MSG15="33819c9c96a73e1b0af17389faaf0130be8fe40376c6e3adb4ce0d75967ef492"
OLD_REGISTRY_PY="d0893ecb7ddc283d5ad6c64b1fdda3ad17a68c0617f727573b9a64a8260b08ba"
OLD_RUN_S1="a5c6bf30379d5a623ee385de686fc2aa46190bb6047d47d01cba087116d1dac8"
OLD_SELFTEST_ALL="d6cac321ad42661946b68ac7e8f25945804d19f9f121b74cfbf83d7f52c3eb60"
OLD_NOTES="da4b039d00174255c2a0a70ed73f27011d45364383f44680ec45102d32856419"
OLD_STATUS="9d1178ff2004d99add18d32b4aecbed5aac8010011635b376dde419b2a98474c"
LIVE_REG_SHA="70c91da708f7397251c224a111aada2932dfc0d1bb25ec13e0480dab320f9fe2"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/registry.py user_data/analysis/run_s1.py user_data/analysis/selftest_all.sh context/developer/NOTES.md context/STATUS.md 2>/dev/null
  rm -f user_data/analysis/selftest_registry_hygiene.py docs/correspondence/message-15.md
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

echo "== delivery 2 (D1, WO 1.5 step 2) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/2" ] || die "apply.sh must sit in $REPO/deliveries/2/ (it is in $HERE)"

echo "-- 1. SHA-256 of the delivered files"
BAD=0
for pair in "registry.py:$EXP_REGISTRY_PY" "run_s1.py:$EXP_RUN_S1" "selftest_all.sh:$EXP_SELFTEST_ALL" "selftest_registry_hygiene.py:$EXP_HYGIENE" "NOTES.md:$EXP_NOTES" "STATUS.md:$EXP_STATUS" "message-15.md:$EXP_MSG15"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/2/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; fi
git merge-base --is-ancestor ac63ff2 HEAD || die "delivery 1 (ac63ff2) is not in your history; run delivery 1 first"
echo "folder clean, on main, HEAD $(git rev-parse --short HEAD), contains delivery 1 (ac63ff2)"
[ "$(sha user_data/analysis/registry.py)" = "$OLD_REGISTRY_PY" ] || die "registry.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/run_s1.py)" = "$OLD_RUN_S1" ] || die "run_s1.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "developer/NOTES.md is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ ! -e user_data/analysis/selftest_registry_hygiene.py ] && [ ! -e docs/correspondence/message-15.md ] || die "selftest_registry_hygiene.py or message-15.md already exists"
REG="user_data/analysis/results/registry.jsonl"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the live registry is not the 14-line file committed in ac63ff2 (hash differs); nothing touched"
echo "files to replace are the expected versions; live registry is the 14-line file from ac63ff2"

echo "-- 3. backup (inside the project)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/registry.py user_data/analysis/run_s1.py user_data/analysis/selftest_all.sh "$BK/"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
cp context/STATUS.md "$BK/STATUS.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"

echo "-- 4. new files in place, then ALL self-tests"
APPLIED=1
cp "$HERE/registry.py" user_data/analysis/registry.py
cp "$HERE/run_s1.py" user_data/analysis/run_s1.py
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
cp "$HERE/selftest_registry_hygiene.py" user_data/analysis/selftest_registry_hygiene.py
[ "$(sha user_data/analysis/registry.py)" = "$EXP_REGISTRY_PY" ] && [ "$(sha user_data/analysis/run_s1.py)" = "$EXP_RUN_S1" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] && [ "$(sha user_data/analysis/selftest_registry_hygiene.py)" = "$EXP_HYGIENE" ] || die "a code copy failed verification"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
echo "python: $("$PYBIN" --version 2>&1)"
LOG="$REPO/temp/selftest-step2-$STAMP.log"
# Note: no TMPDIR / GIT_CEILING_DIRECTORIES set here on purpose: the new selftest_all.sh sets them itself.
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
echo "full log: $LOG"
[ "$ST_CODE" -eq 0 ] || { echo "last 25 lines of the log:"; tail -25 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q '^=================== selftest_registry_hygiene.py' "$LOG" || die "the new hygiene self-test did not run"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/2/' | sort | tr '\n' '|')"
WANT2=" M user_data/analysis/registry.py| M user_data/analysis/run_s1.py| M user_data/analysis/selftest_all.sh|?? user_data/analysis/selftest_registry_hygiene.py|"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the self-tests"; }
echo "no stray files after the self-tests"

echo "-- 5. read-only checks of the guard against the REAL live registry (nothing is written)"
mkdir -p "$REPO/temp"
(cd "$REPO/temp" && "$PYBIN" - <<PYEOF
import sys
sys.path.insert(0, "$REPO/user_data/analysis")
from pathlib import Path
import registry
live = registry.LIVE_REGISTRY_PATH
assert registry.is_live_registry(live)
assert registry.is_live_registry(Path("../user_data/analysis/results/registry.jsonl")), "relative spelling, other cwd"
assert registry.is_live_registry(Path("../user_data/analysis/../analysis/results/registry.jsonl")), "other spelling"
assert not registry.is_live_registry(registry.DEFAULT_REGISTRY_PATH), "default must be scratch"
assert str(registry.DEFAULT_REGISTRY_PATH).startswith("$REPO/temp/"), registry.DEFAULT_REGISTRY_PATH
print("live registry recognised under 3 spellings from another cwd; default registry = scratch:", registry.DEFAULT_REGISTRY_PATH)
PYEOF
) || die "read-only guard check against the real registry failed"
"$PYBIN" user_data/analysis/registry.py --void-family S1-ETHUSDT --pair ETHUSDT --reason "dry run check" --registry-path "$REG" | head -2
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the read-only checks"
echo "live registry still byte-identical (the void CLI is a no-op on the already-voided family)"

echo "-- 6. place documents, commit, push"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-15.md" docs/correspondence/message-15.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-15.md)" = "$EXP_MSG15" ] || die "a document copy failed verification"
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
git add user_data/analysis/registry.py user_data/analysis/run_s1.py user_data/analysis/selftest_all.sh user_data/analysis/selftest_registry_hygiene.py context/developer/NOTES.md context/STATUS.md docs/correspondence/message-15.md deliveries/2/apply.sh deliveries/2/registry.py deliveries/2/run_s1.py deliveries/2/selftest_all.sh deliveries/2/selftest_registry_hygiene.py deliveries/2/NOTES.md deliveries/2/STATUS.md deliveries/2/message-15.md
STAGED="$(git diff --cached --name-only | sort | tr '\n' ' ')"
WANT="context/STATUS.md context/developer/NOTES.md deliveries/2/NOTES.md deliveries/2/STATUS.md deliveries/2/apply.sh deliveries/2/message-15.md deliveries/2/registry.py deliveries/2/run_s1.py deliveries/2/selftest_all.sh deliveries/2/selftest_registry_hygiene.py docs/correspondence/message-15.md user_data/analysis/registry.py user_data/analysis/run_s1.py user_data/analysis/selftest_all.sh user_data/analysis/selftest_registry_hygiene.py "
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected fifteen: $STAGED"
git commit -q -m "[D1] WO 1.5 step 2: registry hygiene (live writes need --commit-to-registry; scratch registry by default; self-tests in temp/, live-registry hash guard); NOTES corrected, message-15"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
