#!/bin/bash
# deliveries/17/apply.sh -- D2, Work Order 1.8 step 1 (second part): the PostgreSQL schema (adapted from M2's reference) and its self-test in a THROWAWAY schema.
#
# Before you run it you need: a PostgreSQL 11 or later that this machine can reach, and ~/apps/crypto_bot/.env with DATABASE_URL (or PGHOST, PGDATABASE, PGUSER and PGPASSWORD), created from .env.example.
# Never paste .env. The database user must be allowed to create a schema; if not, this script stops with a plain note for you. It creates ONLY a schema named nse_test_<random> and drops it
# at the end; it does NOT create the production schema nse and never touches your existing tables.
# Put apply.sh, nse_db.py, selftest_all.sh, requirements.txt, STATUS.md, NOTES.md and message-27.md in ~/apps/crypto_bot/deliveries/17/ and run:   bash ~/apps/crypto_bot/deliveries/17/apply.sh
#   1. checks hashes, the folder (clean, on main, user_data/analysis byte-identical to commit 96b8060), the live registry (30 lines), that .env exists with database settings (names only, values never read
#      by this script), and refuses everything if temp/secret_keys.txt or .env is tracked or was ever committed;
#   2. may install psycopg2-binary into the venv (free) if it is missing; backs up what it replaces, puts nse_db.py in place and runs ALL self-tests (48);
#   3. runs the database self-test (throwaway schema, about 20 behaviours, dropped at the end) and keeps its output;
#   4. renders the DDL for schema nse into sql/nse-schema-v1.sql; commits exactly 15 paths and pushes. On any failure BEFORE the commit it puts everything back.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_NSE_DB="c5f76f00ac69e6156eb416a3cfa296af52f865df8df3eabc8db96ea6b2788fe5"
EXP_SELFTEST_ALL="bed2b31023c3b9f26ee787a7e8068d650f1214ddcd896cacb5fbbe54c59dba7c"
EXP_REQ="b090fcf507e3695b20a93a9650d4293b8df6c0988fea763bd33c9f216b5809dc"
EXP_STATUS="03ab71e2eaf180d56e6575db017497f13e2d91813ef1e4a7ddc7d380ca473765"
EXP_NOTES="72867bd9773ecf12b2282ebc2fed0a654641990e21b650d5de330d58398c1086"
EXP_MSG27="3c04d714c769e4929adf88849f8d88e0be26ca2aca4fbeba8121afd085e3c40f"
OLD_SELFTEST_ALL="3073f4b952af9d35a0dd7c311c926e918b837323292833e0e6428a6b85f3b975"
OLD_REQ="7909d362b6d288e146fd2515bbf3dcb8117c6dc8223ce94513ecbcc6b835aae6"
OLD_STATUS="2cc11814b140cbf8cef6b5b04083e7ecbedb37e7ffff26e1b6546b8e40b5fcd5"
OLD_NOTES="3b0214b31fdfc68ae9c4ae444287e2c1c2cf6f8e875255c5f9a27d48ac9d5737"
LIVE_REG_SHA="ffd462e08c181f446aeb2de72964fef972e23719fa367ff6c3cd1e55aa402755"
BASE_COMMIT="96b8060"
REG="user_data/analysis/results/registry.jsonl"
DDL_FILE="sql/nse-schema-v1.sql"
DBREP="docs/reports/nse-schema-selftest-step1b.txt"
NEWFILES="user_data/analysis/nse_db.py $DDL_FILE $DBREP docs/correspondence/message-27.md"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/selftest_all.sh user_data/analysis/requirements.txt context/STATUS.md context/developer/NOTES.md 2>/dev/null
  rm -f $NEWFILES
  rmdir sql 2>/dev/null
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
      echo "Paste this whole output into the chat (it contains no credentials)."
    fi
  fi
}
trap on_exit EXIT

die() { echo "STOP: $1"; exit 1; }
sha() { shasum -a 256 "$1" | awk '{print $1}'; }
secret_guard() {  # never opens either file
  for f in temp/secret_keys.txt .env; do
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then die "$f is TRACKED by git; refusing to push. Tell the owner (do not paste the file)."; fi
    if [ -n "$(git log --all --oneline -- "$f" 2>/dev/null)" ]; then die "$f appears in a commit; refusing to push. Tell the owner (do not paste the file)."; fi
    if ! git check-ignore -q "$f" 2>/dev/null; then echo "WARNING: $f is not git-ignored; D2 will add it to .gitignore in the next delivery (this script adds nothing but its own exact paths)."; fi
  done
}

echo "== delivery 17 (D2, WO 1.8 step 1b: the PostgreSQL schema and its throwaway-schema self-test) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/17" ] || die "apply.sh must sit in $REPO/deliveries/17/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "nse_db.py:$EXP_NSE_DB" "selftest_all.sh:$EXP_SELFTEST_ALL" "requirements.txt:$EXP_REQ" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES" "message-27.md:$EXP_MSG27"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/17/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
secret_guard
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; secret_guard; fi
git merge-base --is-ancestor "$BASE_COMMIT" HEAD || die "commit $BASE_COMMIT (delivery 16) is not in your history; run delivery 16 first"
git diff --quiet "$BASE_COMMIT" -- user_data/analysis || die "user_data/analysis differs from commit $BASE_COMMIT (the verified code); refusing to continue"
CODE_COMMIT="$(git rev-parse --short HEAD)"
echo "folder clean, on main, HEAD $CODE_COMMIT; user_data/analysis is byte-identical to $BASE_COMMIT"
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha user_data/analysis/requirements.txt)" = "$OLD_REQ" ] || die "requirements.txt is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
for f in $NEWFILES; do [ ! -e "$f" ] || die "$f already exists"; done
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] && [ "$(wc -l < $REG | tr -d ' ')" = "30" ] || die "the live registry is not the 30-line file; refusing to continue"
echo "live registry: 30 lines, unchanged"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
[ -f .env ] || die "NOTE FOR THE OWNER: there is no .env in $REPO. Copy .env.example to .env and fill DATABASE_URL (or PGHOST, PGDATABASE, PGUSER, PGPASSWORD): the schema test needs a PostgreSQL 11 or later that this machine can reach. Nothing was applied."
DBSET="$( cd user_data/analysis && "$PYBIN" - <<'PYEOF'
from nse_common import read_env
e = read_env()
print("yes" if e.get("DATABASE_URL") or all(e.get(k) for k in ("PGHOST", "PGDATABASE", "PGUSER")) else "no")
PYEOF
)"
[ "$DBSET" = "yes" ] || die "NOTE FOR THE OWNER: .env has no database settings: fill DATABASE_URL (or PGHOST, PGDATABASE, PGUSER, PGPASSWORD). Nothing was applied."
echo ".env found with database settings (values not read here, never printed)"
if "$PYBIN" -c 'import psycopg2' 2>/dev/null; then echo "psycopg2: present"; else
  echo "psycopg2 is missing: installing psycopg2-binary into the project's venv (free; the only network use of this script)"
  "$PYBIN" -m pip install -q "psycopg2-binary>=2.9" || die "pip install psycopg2-binary failed"
fi

echo "-- 2. backup, nse_db.py in place, then ALL self-tests"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/selftest_all.sh user_data/analysis/requirements.txt "$BK/"
cp context/STATUS.md "$BK/STATUS.md"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' -o -name '.env*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"
APPLIED=1
cp "$HERE/nse_db.py" user_data/analysis/nse_db.py
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
cp "$HERE/requirements.txt" user_data/analysis/requirements.txt
[ "$(sha user_data/analysis/nse_db.py)" = "$EXP_NSE_DB" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] && [ "$(sha user_data/analysis/requirements.txt)" = "$EXP_REQ" ] || die "a copy failed verification"
LOG="$REPO/temp/selftest-step17-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 30 lines of the log:"; tail -30 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
grep -q "Self-test passed: nse_db" "$LOG" || die "the nse_db self-test did not report success"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"

echo "-- 3. database self-test in a throwaway schema (dropped at the end)"
DBOUT="$REPO/temp/nse-db-selftest-$STAMP.txt"
set +e
( cd user_data/analysis && "$PYBIN" nse_db.py --self-test-db ) > "$DBOUT" 2>&1
DBC=$?
set -e
cat "$DBOUT"
if [ "$DBC" -ne 0 ]; then die "the database self-test did not pass (exit $DBC; see the NOTE FOR THE OWNER above if there is one). Nothing was committed."; fi
grep -q "^Database self-test passed" "$DBOUT" || die "the database self-test output lacks its PASS line"

echo "-- 4. render the DDL for schema nse, commit, push"
mkdir -p sql
( cd user_data/analysis && "$PYBIN" nse_db.py --render-ddl ) > "$DDL_FILE"
grep -q "CREATE SCHEMA IF NOT EXISTS nse;" "$DDL_FILE" && grep -q "DATE '2025-08-31'" "$DDL_FILE" || die "the rendered DDL is not as expected"
{ echo "Database self-test of the adapted schema (Work Order 1.8 step 1b), produced by deliveries/17/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $CODE_COMMIT)"; echo "command: python3 nse_db.py --self-test-db (throwaway schema, dropped at the end; no credentials in this file)"; echo; cat "$DBOUT"; } > "$DBREP"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed"
CHK_A="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/17/' | LC_ALL=C sort | tr '\n' '|')"
CHK_B="$( ( echo ' M user_data/analysis/selftest_all.sh'; echo ' M user_data/analysis/requirements.txt'; for p in $NEWFILES; do [ "$p" = "docs/correspondence/message-27.md" ] || echo "?? $p"; done ) | LC_ALL=C sort | tr '\n' '|')"
[ "$CHK_A" = "$CHK_B" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files"; }
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-27.md" docs/correspondence/message-27.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-27.md)" = "$EXP_MSG27" ] || die "a document copy failed verification"
secret_guard
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
DELIV="deliveries/17/apply.sh deliveries/17/nse_db.py deliveries/17/selftest_all.sh deliveries/17/requirements.txt deliveries/17/STATUS.md deliveries/17/NOTES.md deliveries/17/message-27.md"
PATHS="user_data/analysis/nse_db.py user_data/analysis/selftest_all.sh user_data/analysis/requirements.txt $DDL_FILE $DBREP context/developer/NOTES.md context/STATUS.md docs/correspondence/message-27.md $DELIV"
git add $PATHS
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="$(printf '%s\n' $PATHS | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected fifteen: $STAGED"
if git diff --cached --name-only | grep -q -E '(^|/)\.env$'; then die ".env is staged; refusing"; fi
git commit -q -m "[D2] WO 1.8 step 1b: PostgreSQL schema adapted from M2's reference (7 documented deviations), throwaway-schema self-test, DDL for schema nse, STATUS/NOTES, message-27; production schema not created, no registry write"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
secret_guard
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
