#!/bin/bash
# deliveries/0/apply.sh -- D1, Work Order 1.5, step 0 (bring the owner's folder in line with GitHub).
#
# Put apply.sh, STATUS.md and message-13.md together in ~/apps/crypto_bot/deliveries/0/ and run:
#     bash ~/apps/crypto_bot/deliveries/0/apply.sh
# What it does (nothing is ever deleted):
#   1. checks the SHA-256 of STATUS.md and message-13.md against the list below (stops on mismatch);
#   2. checks the folder is clean, on main, and that your HEAD is an ancestor of GitHub's main;
#   3. backs up registry.jsonl, STATUS.md, developer/NOTES.md, HEAD and status text into temp/backup-<UTC>/;
#   4. git fetch + git merge --ff-only origin/main (cannot overwrite or lose anything);
#   5. runs the existing self-tests (scratch redirected into <repo>/temp/), and checks registry.jsonl did not change;
#   6. only if everything passed: copies the two files into place, commits exactly five paths, pushes.
# Prints PASS and the commit hash, or FAIL (nothing is committed on failure).
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXPECT_STATUS="1d83de0c0aeb1fc4c4bb11431724970441f16e1d915fe6e5b52153abf416e3b0"
EXPECT_MSG13="541661659e65f8f1c33454367af91042c5772578391f1a65c7c790fee99a6524"
EXPECT_OLD_STATUS="bfa948c2f9fdf3d89c9a540379d51be5c9fdb9772f88d900f2557b738eb81524"

FINISHED=0
on_exit() {
  rc=$?
  if [ "$FINISHED" != "1" ]; then
    echo
    echo "FAIL (exit $rc). Nothing was committed or pushed by this script."
    echo "If the line 'fast-forwarded' was printed above, your folder was updated to GitHub's state; that is safe."
    echo "Paste this whole output into the chat."
  fi
}
trap on_exit EXIT

die() { echo "STOP: $1"; exit 1; }
sha() { shasum -a 256 "$1" | awk '{print $1}'; }

echo "== delivery 0 (D1, WO 1.5 step 0) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository (run: bash apply.sh /path/to/crypto_bot)"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/0" ] || die "apply.sh must sit in $REPO/deliveries/0/ (it is in $HERE)"

echo "-- 1. SHA-256 of the delivered files"
for f in STATUS.md message-13.md; do
  [ -f "$HERE/$f" ] || die "missing file $HERE/$f"
done
H_STATUS="$(sha "$HERE/STATUS.md")"
H_MSG13="$(sha "$HERE/message-13.md")"
echo "STATUS.md      $H_STATUS"
echo "message-13.md  $H_MSG13"
if [ "$H_STATUS" != "$EXPECT_STATUS" ] || [ "$H_MSG13" != "$EXPECT_MSG13" ]; then
  die "HASH MISMATCH - nothing was applied. Download the two files again into $HERE"
fi
echo "hashes match"

cd "$REPO"
echo "-- 2. state checks"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "main" ] || die "branch is '$BRANCH', expected main"
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/0/' || true)"
if [ -n "$DIRTY" ]; then
  echo "$DIRTY"
  die "the folder has modified or untracked files (listed above). Nothing touched. Paste this output."
fi
echo "folder is clean (apart from this delivery's own files); branch main; HEAD $(git rev-parse --short HEAD)"
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured; nothing touched"

echo "-- 3. backup (inside the project, never outside)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp user_data/analysis/results/registry.jsonl "$BK/registry.jsonl"
cp context/STATUS.md "$BK/STATUS.md"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
git rev-parse HEAD > "$BK/HEAD.txt"
git status > "$BK/git-status.txt"
git stash list > "$BK/stash-list.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
REG_HASH_0="$(sha user_data/analysis/results/registry.jsonl)"
[ "$REG_HASH_0" = "$(sha "$BK/registry.jsonl")" ] || die "backup of registry.jsonl differs from the original"
echo "backup written: $BK"
echo "registry.jsonl lines: $(wc -l < user_data/analysis/results/registry.jsonl | tr -d ' ')  sha256 $REG_HASH_0"

echo "-- 4. update to GitHub (fast-forward only)"
git fetch origin
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
if ! git merge-base --is-ancestor "$LOCAL" "$REMOTE"; then
  die "your HEAD ($LOCAL) is not an ancestor of origin/main ($REMOTE): your folder has commits GitHub lacks. Nothing touched."
fi
if [ "$LOCAL" = "$REMOTE" ]; then
  echo "already equal to origin/main ($(git rev-parse --short HEAD))"
else
  git merge --ff-only origin/main
  echo "fast-forwarded to $(git rev-parse --short HEAD)"
fi
for f in docs/PROTOCOL.md docs/work-orders/1.5.md user_data/analysis/stability_reference.py scripts/diag_state.sh; do
  [ -f "$f" ] || die "after the update $f is still missing: GitHub does not have the files of work order 1.5 yet"
done
if ls temp_s1_*.log wo1.4_*.log >/dev/null 2>&1; then die "loose logs still sit at the repo root after the update"; fi
echo "work-order files present; loose root logs are gone"
[ "$(sha context/STATUS.md)" = "$EXPECT_OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery was written against; nothing committed"
[ ! -e docs/correspondence/message-13.md ] || die "docs/correspondence/message-13.md already exists; nothing committed"
[ "$(sha user_data/analysis/results/registry.jsonl)" = "$REG_HASH_0" ] || die "registry.jsonl changed during the update"

echo "-- 5. self-tests (existing 33, unchanged; scratch redirected into temp/, hidden from git so freeze_manifest.py sees a non-repo dir)"
mkdir -p "$REPO/temp/tmp-selftest"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
echo "python: $("$PYBIN" --version 2>&1)"
LOG="$REPO/temp/selftest-step0-$STAMP.log"
set +e
TMPDIR="$REPO/temp/tmp-selftest" GIT_CEILING_DIRECTORIES="$REPO/temp" PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
echo "full log: $LOG"
[ "$ST_CODE" -eq 0 ] || { echo "last 25 lines of the log:"; tail -25 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
[ "$(sha user_data/analysis/results/registry.jsonl)" = "$REG_HASH_0" ] || die "registry.jsonl CHANGED during the self-tests (a self-test wrote to the live registry)"
echo "registry.jsonl byte-identical after the self-tests"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/0/' || true)"
if [ -n "$DIRTY2" ]; then echo "$DIRTY2"; die "the self-tests left modified or untracked files (listed above)"; fi
echo "no stray files after the self-tests"

echo "-- 6. place files, commit, push"
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-13.md" docs/correspondence/message-13.md
[ "$(sha context/STATUS.md)" = "$EXPECT_STATUS" ] || die "copy of STATUS.md failed verification"
[ "$(sha docs/correspondence/message-13.md)" = "$EXPECT_MSG13" ] || die "copy of message-13.md failed verification"
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
git add context/STATUS.md docs/correspondence/message-13.md deliveries/0/apply.sh deliveries/0/STATUS.md deliveries/0/message-13.md
STAGED="$(git diff --cached --name-only | sort | tr '\n' ' ')"
WANT="context/STATUS.md deliveries/0/STATUS.md deliveries/0/apply.sh deliveries/0/message-13.md docs/correspondence/message-13.md "
[ "$STAGED" = "$WANT" ] || { git reset -q; die "staged paths differ from the expected five: $STAGED"; }
if ! git commit -q -m "[D1] WO 1.5 step 0: align folder with GitHub (ff-only), STATUS.md current state, message-13 to M1"; then
  git reset -q
  git checkout -- context/STATUS.md
  rm -f docs/correspondence/message-13.md
  die "git commit failed; the two files were put back as they were"
fi
HASH="$(git rev-parse --short HEAD)"
if ! git push origin main; then
  FINISHED=1
  echo "FAIL: committed locally as $HASH but the push failed. Paste this output; do not run anything else."
  exit 1
fi
FINISHED=1
echo
echo "PASS  commit $HASH"
