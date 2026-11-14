#!/bin/bash
# deliveries/16/apply.sh -- D2, Work Order 1.8 step 1 (first part): AMFI conversion, summary and draw, Upstox client (canned responses), rules files, loader, .env.example.
#
# Put apply.sh and all the files of deliveries/16 together in ~/apps/crypto_bot/deliveries/16/ and run:   bash ~/apps/crypto_bot/deliveries/16/apply.sh
# No database, no token, no network call to Upstox and no registry write. It may run ONE command that uses the network: `pip install openpyxl` into the project's venv, only if openpyxl is
# missing (free; needed to read the AMFI workbook). What it does:
#   1. checks hashes, the folder (clean, on main, user_data/analysis byte-identical to commit 8714b48), the live registry (30 lines), and refuses everything if temp/secret_keys.txt or .env
#      is tracked or was ever committed (it never opens either file);
#   2. backs up what it replaces, puts the new code, rules files and .env.example in place and runs ALL self-tests (47);
#   3. converts docs/amfi/AverageMarketCapitalization30Jun2025.xlsx (ONLY that workbook) to CSV, writes the summary and the draw universe/nse-midcap-draw-v1.csv, and re-checks the draw order
#      with an independent ten-line recomputation inside this script;
#   4. commits exactly 30 paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_NSE_COMMON="8f1e82483de9a34d813efa19f1609c66390d9d8d7b7d57b5780bb741e3d61b37"
EXP_NSE_AMFI="3091dbdada0ec3abf696dedf2b7c7a756df09d256b3bcbf29d60c87616c7acea"
EXP_NSE_RULES="b7c9e02d33a72c5ee9c571b5841e70b1fbb6d81d4b0d1399ccbf2ae41b390880"
EXP_NSE_LOADER="9d5b7464799272c607719a1c6180539ae4535fe552f617e82a41a8e0fee2f6b5"
EXP_NSE_UPSTOX="266702127af79c7482d9ff64ef65a198d78ab872b29de4d3301e2e54ff75db4e"
EXP_SELFTEST_ALL="3073f4b952af9d35a0dd7c311c926e918b837323292833e0e6428a6b85f3b975"
EXP_REQ="7909d362b6d288e146fd2515bbf3dcb8117c6dc8223ce94513ecbcc6b835aae6"
EXP_COSTS="bea306b68ce3a43b7b777d1a28bbe709dd32d131e8501dc0211c1e94e5b49c62"
EXP_TAX="5042fe86f642a1063622c17a6b69f047c4d4a71fd93b8aacc0c44c8bb9bae329"
EXP_ENVEX="259457a6f7e8a1f7b9049c13b2364cf9e37781b0e272ac52d3f4746ebc38d538"
EXP_STATUS="2cc11814b140cbf8cef6b5b04083e7ecbedb37e7ffff26e1b6546b8e40b5fcd5"
EXP_NOTES="3b0214b31fdfc68ae9c4ae444287e2c1c2cf6f8e875255c5f9a27d48ac9d5737"
EXP_MSG26="4e62b3f52f9ed5270c6a09f0b569e61b72325ef2c70608ebf51858ed9da19d73"
OLD_SELFTEST_ALL="ff93a72c3d41e0c52bb0c0ab46fc69c97e7185aa70f86e21c9f50cb2aff900b0"
OLD_REQ="29f40f4ad05b9336887a0e5e8983643b34d617cd9dc085f7f7bf963184e50d6d"
OLD_STATUS="3a44b1f745ca18d0101acc5f8390ddba61623e8aaab0e6f4a3f89e909d0c6910"
OLD_NOTES="f5271e60d0bb7e948bc0276c20e7ec58470bc86f239ea1a981293894ac3e07b7"
LIVE_REG_SHA="ffd462e08c181f446aeb2de72964fef972e23719fa367ff6c3cd1e55aa402755"
BASE_COMMIT="8714b48"
REG="user_data/analysis/results/registry.jsonl"
XLSX="docs/amfi/AverageMarketCapitalization30Jun2025.xlsx"
AMFI_CSV="docs/amfi/AverageMarketCapitalization30Jun2025.csv"
AMFI_SUM="docs/amfi/summary-30Jun2025.txt"
DRAW="universe/nse-midcap-draw-v1.csv"
NSE_PY="user_data/analysis/nse_common.py user_data/analysis/nse_amfi.py user_data/analysis/nse_rules.py user_data/analysis/nse_loader.py user_data/analysis/nse_upstox.py"
NEWFILES="$NSE_PY rules/IN-equity-costs-v1.json rules/IN-tax-v1.json .env.example $AMFI_CSV $AMFI_SUM $DRAW docs/correspondence/message-26.md"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/selftest_all.sh user_data/analysis/requirements.txt context/STATUS.md context/developer/NOTES.md 2>/dev/null
  rm -f $NEWFILES
  rmdir rules universe 2>/dev/null
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
secret_guard() {  # never opens either file
  for f in temp/secret_keys.txt .env; do
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then die "$f is TRACKED by git; refusing to push. Tell the owner (do not paste the file)."; fi
    if [ -n "$(git log --all --oneline -- "$f" 2>/dev/null)" ]; then die "$f appears in a commit; refusing to push. Tell the owner (do not paste the file)."; fi
    if ! git check-ignore -q "$f" 2>/dev/null; then echo "WARNING: $f is not git-ignored; D2 will add it to .gitignore in the next delivery (this script adds nothing but its own exact paths)."; fi
  done
}

echo "== delivery 16 (D2, WO 1.8 step 1a: AMFI file and draw, Upstox client, rules, loader) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/16" ] || die "apply.sh must sit in $REPO/deliveries/16/ (it is in $HERE)"

echo "-- 1. checks"
BAD=0
for pair in "nse_common.py:$EXP_NSE_COMMON" "nse_amfi.py:$EXP_NSE_AMFI" "nse_rules.py:$EXP_NSE_RULES" "nse_loader.py:$EXP_NSE_LOADER" "nse_upstox.py:$EXP_NSE_UPSTOX" "selftest_all.sh:$EXP_SELFTEST_ALL" "requirements.txt:$EXP_REQ" \
            "IN-equity-costs-v1.json:$EXP_COSTS" "IN-tax-v1.json:$EXP_TAX" "env.example:$EXP_ENVEX" "STATUS.md:$EXP_STATUS" "NOTES.md:$EXP_NOTES" "message-26.md:$EXP_MSG26"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/16/' || true)"
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
[ "$(sha user_data/analysis/selftest_all.sh)" = "$OLD_SELFTEST_ALL" ] || die "selftest_all.sh is not the version this delivery replaces"
[ "$(sha user_data/analysis/requirements.txt)" = "$OLD_REQ" ] || die "requirements.txt is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "context/developer/NOTES.md is not the version this delivery replaces"
for f in $NEWFILES; do [ ! -e "$f" ] || die "$f already exists"; done
[ -f "$XLSX" ] || die "$XLSX is missing"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] && [ "$(wc -l < $REG | tr -d ' ')" = "30" ] || die "the live registry is not the 30-line file; refusing to continue"
echo "live registry: 30 lines, unchanged"
[ -f universe/owner-exclusions.txt ] && echo "universe/owner-exclusions.txt exists and will be applied to the pool" || echo "no universe/owner-exclusions.txt: no owner exclusions"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
if "$PYBIN" -c 'import openpyxl' 2>/dev/null; then echo "openpyxl: present ($("$PYBIN" -c 'import openpyxl; print(openpyxl.__version__)'))"; else
  echo "openpyxl is missing: installing it into the project's venv (free; the only network use of this script)"
  "$PYBIN" -m pip install -q "openpyxl>=3.1" || die "pip install openpyxl failed"
fi

echo "-- 2. backup, new code in place, then ALL self-tests"
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
for f in nse_common.py nse_amfi.py nse_rules.py nse_loader.py nse_upstox.py; do cp "$HERE/$f" "user_data/analysis/$f"; done
cp "$HERE/selftest_all.sh" user_data/analysis/selftest_all.sh
cp "$HERE/requirements.txt" user_data/analysis/requirements.txt
mkdir -p rules
cp "$HERE/IN-equity-costs-v1.json" rules/IN-equity-costs-v1.json
cp "$HERE/IN-tax-v1.json" rules/IN-tax-v1.json
cp "$HERE/env.example" .env.example
[ "$(sha user_data/analysis/nse_common.py)" = "$EXP_NSE_COMMON" ] && [ "$(sha user_data/analysis/nse_amfi.py)" = "$EXP_NSE_AMFI" ] && [ "$(sha user_data/analysis/nse_rules.py)" = "$EXP_NSE_RULES" ] \
  && [ "$(sha user_data/analysis/nse_loader.py)" = "$EXP_NSE_LOADER" ] && [ "$(sha user_data/analysis/nse_upstox.py)" = "$EXP_NSE_UPSTOX" ] && [ "$(sha user_data/analysis/selftest_all.sh)" = "$EXP_SELFTEST_ALL" ] \
  && [ "$(sha user_data/analysis/requirements.txt)" = "$EXP_REQ" ] && [ "$(sha rules/IN-equity-costs-v1.json)" = "$EXP_COSTS" ] && [ "$(sha rules/IN-tax-v1.json)" = "$EXP_TAX" ] && [ "$(sha .env.example)" = "$EXP_ENVEX" ] || die "a copy failed verification"
LOG="$REPO/temp/selftest-step16-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 30 lines of the log:"; tail -30 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
for k in "Self-test passed: nse_common" "Self-test passed: nse_amfi" "Self-test passed: nse_rules" "Self-test passed: nse_loader" "Self-test passed: nse_upstox"; do grep -q "$k" "$LOG" || die "missing: $k"; done
grep -h "Self-test passed: nse_rules" "$LOG" | cut -c1-260
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"

echo "-- 3. AMFI: convert the 30 June 2025 workbook, write the summary and the draw"
XSHA="$(sha $XLSX)"
( cd user_data/analysis && "$PYBIN" nse_amfi.py all ) || die "the AMFI conversion / draw failed; nothing committed. Paste this output into the chat."
[ "$(sha $XLSX)" = "$XSHA" ] || die "the xlsx changed (it must stay read-only input)"
[ -s "$AMFI_CSV" ] && [ -s "$AMFI_SUM" ] && [ -s "$DRAW" ] || die "an AMFI output is missing"
grep -q "$XSHA" "$AMFI_SUM" || die "the summary does not carry the SHA-256 of the xlsx"
echo "--- summary (docs/amfi/summary-30Jun2025.txt) ---"
cut -c1-400 "$AMFI_SUM"
echo "--- draw (first 5 and the 30th row of universe/nse-midcap-draw-v1.csv; $(( $(wc -l < $DRAW) - 1 )) names in the pool) ---"
head -6 "$DRAW" | cut -c1-200
sed -n '31p' "$DRAW" | cut -c1-200
"$PYBIN" - "$DRAW" <<'PYEOF' || die "the independent ten-line recomputation of the draw order disagrees"
import csv, hashlib, sys
rows = list(csv.DictReader(open(sys.argv[1])))
dig = [hashlib.sha256(("20250831|" + r["isin"]).encode("utf-8")).hexdigest() for r in rows]
assert dig == [r["sha256"] for r in rows] and dig == sorted(dig), "digest or order"
assert [int(r["draw_order"]) for r in rows] == list(range(1, len(rows) + 1)), "draw_order"
assert all(101 <= int(r["amfi_rank"]) <= 250 and r["isin"] and r["nse_symbol"] for r in rows) and len({r["isin"] for r in rows}) == len(rows), "pool"
print(f"independent recomputation: {len(rows)} rows, ascending SHA-256 of '20250831|ISIN', draw_order 1..{len(rows)}, ranks within 101..250, no duplicate ISIN: OK")
PYEOF
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed"
CHK_A="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/16/' | LC_ALL=C sort | tr '\n' '|')"
CHK_B="$( ( echo ' M user_data/analysis/selftest_all.sh'; echo ' M user_data/analysis/requirements.txt'; for p in $NEWFILES; do [ "$p" = "docs/correspondence/message-26.md" ] || echo "?? $p"; done ) | LC_ALL=C sort | tr '\n' '|')"
[ "$CHK_A" = "$CHK_B" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the AMFI step"; }

echo "-- 4. place documents, commit, push"
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-26.md" docs/correspondence/message-26.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-26.md)" = "$EXP_MSG26" ] || die "a document copy failed verification"
secret_guard
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
DELIV="deliveries/16/apply.sh deliveries/16/nse_common.py deliveries/16/nse_amfi.py deliveries/16/nse_rules.py deliveries/16/nse_loader.py deliveries/16/nse_upstox.py deliveries/16/selftest_all.sh deliveries/16/requirements.txt deliveries/16/IN-equity-costs-v1.json deliveries/16/IN-tax-v1.json deliveries/16/env.example deliveries/16/STATUS.md deliveries/16/NOTES.md deliveries/16/message-26.md"
PATHS="$NSE_PY user_data/analysis/selftest_all.sh user_data/analysis/requirements.txt rules/IN-equity-costs-v1.json rules/IN-tax-v1.json .env.example $AMFI_CSV $AMFI_SUM $DRAW context/developer/NOTES.md context/STATUS.md docs/correspondence/message-26.md $DELIV"
git add $PATHS
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="$(printf '%s\n' $PATHS | LC_ALL=C sort | tr '\n' ' ')"
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected thirty: $STAGED"
if git diff --cached --name-only | grep -q -E '(^|/)\.env$'; then die ".env is staged; refusing"; fi
git commit -q -m "[D2] WO 1.8 step 1a: AMFI csv, summary and draw (30 Jun 2025 file only), Upstox V3 client (canned responses), cost and tax rules with validators, NSE loader with cutoff and holdout lock, .env.example, STATUS/NOTES, message-26; no database, no token, no registry write"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
secret_guard
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
