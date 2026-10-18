#!/bin/bash
# deliveries/3/apply.sh -- D1, Work Order 1.5, step 3 (fix S1: one common origin set, calendar blocks).
#
# Put apply.sh, formula_s1.py, run_s1.py, NOTES.md, STATUS.md and message-16.md together in
# ~/apps/crypto_bot/deliveries/3/ and run:   bash ~/apps/crypto_bot/deliveries/3/apply.sh
# What it does (the live registry is never written, and no p-value or return is computed):
#   1. checks the SHA-256 of the delivered files (stops on mismatch);
#   2. checks the folder is clean, on main, contains delivery 2 (bd0c8cb), and the files it replaces are the expected versions;
#   3. backs up the files it replaces into temp/backup-<UTC>/;
#   4. puts the new files in place and runs ALL self-tests (34), then checks the live registry did not change;
#   5. READ-ONLY run on your real ETH_USDT and BTC_USDT daily files: prints the S1 origin facts and the cutoff check,
#      and saves them as docs/reports/s1-origin-facts-step3.txt;
#   6. commits exactly twelve paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_FORMULA="cbbc28b7111f7c33d1216c83d2489a9418033939cf668d7b7db6683fded9c58a"
EXP_RUN_S1="1e78e566c43d52836d73f019db57b26e31fd0a7bb8f9440173031391427dde06"
EXP_NOTES="3d32db9ca1cd3d2d431fa78188a835b6d35f7d0de2267156078222435ce6a706"
EXP_STATUS="0e4972b1fa0dffc7993bdd769af5160e0bc0b4460fedb538f298fd10230bba47"
EXP_MSG16="fa1f1fc78315ae9a9f4c4eb28506d7497b96bbcfa1a7ee6345ffdad355f88057"
OLD_FORMULA="4e9cbfe977884e6706a5570259da849d8e1b78b3c174b16cbeba7c10baf2abc4"
OLD_RUN_S1="233c3a1177662048f1442a7a251c96b8490aabce3513210a92e8bb1d6e42c355"
OLD_NOTES="b816c9eb50ea89dece94bf4f913b6455597da3ed87baef9259ea60615c19b16b"
OLD_STATUS="2f892141b40c20e20f1caf1d2b22640210d1f03b84155f694a3dfff18fe8d773"
LIVE_REG_SHA="70c91da708f7397251c224a111aada2932dfc0d1bb25ec13e0480dab320f9fe2"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/formula_s1.py user_data/analysis/run_s1.py context/developer/NOTES.md context/STATUS.md 2>/dev/null
  rm -f docs/correspondence/message-16.md docs/reports/s1-origin-facts-step3.txt
  rmdir docs/reports 2>/dev/null
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

echo "== delivery 3 (D1, WO 1.5 step 3) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/3" ] || die "apply.sh must sit in $REPO/deliveries/3/ (it is in $HERE)"

echo "-- 1. SHA-256 of the delivered files"
BAD=0
for pair in "formula_s1.py:$EXP_FORMULA" "run_s1.py:$EXP_RUN_S1" "NOTES.md:$EXP_NOTES" "STATUS.md:$EXP_STATUS" "message-16.md:$EXP_MSG16"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/3/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; fi
git merge-base --is-ancestor bd0c8cb HEAD || die "delivery 2 (bd0c8cb) is not in your history; run delivery 2 first"
echo "folder clean, on main, HEAD $(git rev-parse --short HEAD), contains delivery 2 (bd0c8cb)"
[ "$(sha user_data/analysis/formula_s1.py)" = "$OLD_FORMULA" ] || die "formula_s1.py is not the version this delivery replaces"
[ "$(sha user_data/analysis/run_s1.py)" = "$OLD_RUN_S1" ] || die "run_s1.py is not the version this delivery replaces"
[ "$(sha context/developer/NOTES.md)" = "$OLD_NOTES" ] || die "developer/NOTES.md is not the version this delivery replaces"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ ! -e docs/correspondence/message-16.md ] && [ ! -e docs/reports/s1-origin-facts-step3.txt ] || die "message-16.md or the origin-facts report already exists"
REG="user_data/analysis/results/registry.jsonl"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the live registry is not the 14-line file committed in ac63ff2 (hash differs); nothing touched"
echo "files to replace are the expected versions; live registry is the 14-line file from ac63ff2"

echo "-- 3. backup (inside the project)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp user_data/analysis/formula_s1.py user_data/analysis/run_s1.py "$BK/"
cp context/developer/NOTES.md "$BK/developer-NOTES.md"
cp context/STATUS.md "$BK/STATUS.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"

echo "-- 4. new files in place, then ALL self-tests"
APPLIED=1
cp "$HERE/formula_s1.py" user_data/analysis/formula_s1.py
cp "$HERE/run_s1.py" user_data/analysis/run_s1.py
[ "$(sha user_data/analysis/formula_s1.py)" = "$EXP_FORMULA" ] && [ "$(sha user_data/analysis/run_s1.py)" = "$EXP_RUN_S1" ] || die "a code copy failed verification"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
echo "python: $("$PYBIN" --version 2>&1)"
LOG="$REPO/temp/selftest-step3-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
echo "full log: $LOG"
[ "$ST_CODE" -eq 0 ] || { echo "last 25 lines of the log:"; tail -25 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
echo "live registry byte-identical after the self-tests"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/3/' | LC_ALL=C sort | tr '\n' '|')"
WANT2=" M user_data/analysis/formula_s1.py| M user_data/analysis/run_s1.py|"
[ "$DIRTY2" = "$WANT2" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the self-tests"; }
echo "no stray files after the self-tests"

echo "-- 5. READ-ONLY S1 origin facts on your real daily files (no registry, no p-values, no returns)"
FACTS="$REPO/temp/s1-origin-facts-$STAMP.txt"
CODE_BEFORE="$(git rev-parse --short HEAD)"
"$PYBIN" - "$REPO" "$FACTS" "$CODE_BEFORE" <<'PYEOF'
import contextlib, datetime, hashlib, io, os, sys
from pathlib import Path

repo, out_path, code_before = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(repo / "user_data" / "analysis"))
import run_s1

data_dir = repo / "user_data" / "data" / "binance"
raw_dir = repo / "user_data" / "data" / "binance_raw"
buf = io.StringIO()
buf.write("S1 origin facts, Work Order 1.5 step 3\n")
buf.write(f"produced by deliveries/3/apply.sh on {datetime.datetime.now(datetime.timezone.utc).isoformat()} "
          f"(repo HEAD before this commit: {code_before})\n")
buf.write("READ-ONLY: no registry write, no p-values, no returns computed.\n")
problems = []
for pair in ("ETH_USDT", "BTC_USDT"):
    path = next((p for p in (data_dir / f"{pair}-1d.feather", raw_dir / f"{pair}-1d.feather") if p.exists()), None)
    if path is None:
        problems.append(f"{pair}: no 1d feather file in {data_dir} or {raw_dir}")
        continue
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    f = run_s1.origin_facts_for(pair, data_dir, raw_dir=raw_dir)
    buf.write(f"\n[{pair}] file {os.path.relpath(path, repo)}  {path.stat().st_size} bytes  sha256 {sha}\n")
    with contextlib.redirect_stdout(buf):
        run_s1.print_origin_facts_report(f)
    o = f["origins"]
    if f["rows_after_cutoff_in_discovery"] != 0:
        problems.append(f"{pair}: {f['rows_after_cutoff_in_discovery']} rows after the cutoff in the discovery frame")
    if len(f["cell_n_values"]) != 1 or f["cell_n_values"][0] != o["n_origins"]:
        problems.append(f"{pair}: cells are not all on the common origin set: {f['cell_n_values']} vs {o['n_origins']}")
    if o["n_origins"] <= 0:
        problems.append(f"{pair}: no origins")
    # Soft notes (NOT failures): differences from the work order's rough expectation, to be explained in the report.
    notes = []
    if abs(o["n_origins"] - 2770) > 5:
        notes.append(f"origin count {o['n_origins']} differs from the work order's 'about 2,770' by {o['n_origins'] - 2770}")
    if o["n_full_blocks"] != 30:
        notes.append(f"{o['n_full_blocks']} full blocks, the work order expects 30")
    if o["first_origin"].date().isoformat() != "2018-01-24":
        notes.append(f"first origin {o['first_origin'].date()} (work order: about 2018-01-24 if the file starts 2017-08-17; this file starts {f['file_first_label'].date()})")
    if not f["gate_blocks_same_as_origin_blocks"]:
        notes.append("the economic gate's full blocks DIFFER from the origin-based full blocks")
    buf.write(("NOTES for M1 (explain in the report): " + "; ".join(notes) + "\n") if notes else "No differences from the work order's rough expectations.\n")
text = buf.getvalue()
print(text)
out_path.write_text(text)
if problems:
    print("PROBLEMS:\n  " + "\n  ".join(problems))
    sys.exit(1)
PYEOF
[ -s "$FACTS" ] || die "the origin-facts file was not written"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the origin-facts run"
echo "live registry still byte-identical; origin facts saved to $FACTS"

echo "-- 6. place documents, commit, push"
mkdir -p docs/reports
cp "$FACTS" docs/reports/s1-origin-facts-step3.txt
cp "$HERE/NOTES.md" context/developer/NOTES.md
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-16.md" docs/correspondence/message-16.md
[ "$(sha context/developer/NOTES.md)" = "$EXP_NOTES" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-16.md)" = "$EXP_MSG16" ] || die "a document copy failed verification"
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
git add user_data/analysis/formula_s1.py user_data/analysis/run_s1.py context/developer/NOTES.md context/STATUS.md docs/correspondence/message-16.md docs/reports/s1-origin-facts-step3.txt deliveries/3/apply.sh deliveries/3/formula_s1.py deliveries/3/run_s1.py deliveries/3/NOTES.md deliveries/3/STATUS.md deliveries/3/message-16.md
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="context/STATUS.md context/developer/NOTES.md deliveries/3/NOTES.md deliveries/3/STATUS.md deliveries/3/apply.sh deliveries/3/formula_s1.py deliveries/3/message-16.md deliveries/3/run_s1.py docs/correspondence/message-16.md docs/reports/s1-origin-facts-step3.txt user_data/analysis/formula_s1.py user_data/analysis/run_s1.py "
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected twelve: $STAGED"
git commit -q -m "[D1] WO 1.5 step 3: S1 common origin set (all cells), calendar-day blocks, read-only --origin-facts; origin facts from real data; NOTES/STATUS corrected, message-16"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
