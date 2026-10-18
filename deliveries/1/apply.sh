#!/bin/bash
# deliveries/1/apply.sh -- D1, Work Order 1.5, step 1 (registry: void markers, R1 Holm; void the pre-fix S1 families).
#
# Put apply.sh, registry.py, answer-04.md, message-14.md and STATUS.md together in
# ~/apps/crypto_bot/deliveries/1/ and run:   bash ~/apps/crypto_bot/deliveries/1/apply.sh
# What it does (the original registry lines are never edited or deleted):
#   1. checks the SHA-256 of the five files against the list below (stops on mismatch);
#   2. checks the folder is clean, on main, and a strict ancestor of (or equal to) GitHub's main; fast-forwards if behind;
#   3. checks the files it replaces are exactly the versions this delivery was written against;
#   4. backs up registry.jsonl, registry.py, STATUS.md into temp/backup-<UTC>/;
#   5. puts the new registry.py in place and runs ALL existing self-tests (scratch inside temp/);
#   6. appends the two void markers to the live registry (S1-ETHUSDT, S1-BTCUSDT) and checks the result;
#   7. commits exactly ten paths and pushes. On any failure BEFORE the commit it puts everything back as it was.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_REGISTRY_PY="d0893ecb7ddc283d5ad6c64b1fdda3ad17a68c0617f727573b9a64a8260b08ba"
EXP_ANSWER04="849fe500f996a2cef65d6f150900f307cfbf71d47b0b07697726a70145b9031c"
EXP_MSG14="aa1656329c9cbdbed4bcd73a5136611a3ad1a7b651ada0c200ded03f5f8b43cc"
EXP_STATUS="9d1178ff2004d99add18d32b4aecbed5aac8010011635b376dde419b2a98474c"
OLD_REGISTRY_PY="4c63912f4686b765d3b5b770f848da57a36d4f57f7032cbb857139ea2401538c"
OLD_STATUS="1d83de0c0aeb1fc4c4bb11431724970441f16e1d915fe6e5b52153abf416e3b0"
OLD_REGISTRY_JSONL="7a3da81c5f60734d88b63a91805bed9cb5a7b967ff7105fa998957a14920ff89"
VOID_REASON="S1 run before Work Order 1.5: wrong origin sets, block test dropped origins (void_pre_fix)"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/registry.py user_data/analysis/results/registry.jsonl context/STATUS.md 2>/dev/null
  rm -f docs/correspondence/answer-04.md docs/correspondence/message-14.md
  echo "Rolled back: registry.py, registry.jsonl and STATUS.md are exactly as before this script ran."
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

echo "== delivery 1 (D1, WO 1.5 step 1) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/1" ] || die "apply.sh must sit in $REPO/deliveries/1/ (it is in $HERE)"

echo "-- 1. SHA-256 of the delivered files"
BAD=0
for pair in "registry.py:$EXP_REGISTRY_PY" "answer-04.md:$EXP_ANSWER04" "message-14.md:$EXP_MSG14" "STATUS.md:$EXP_STATUS"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/1/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; fi
git merge-base --is-ancestor cd0a0a1 HEAD || die "delivery 0 (cd0a0a1) is not in your history; run delivery 0 first"
echo "folder clean, on main, HEAD $(git rev-parse --short HEAD)"
[ "$(sha user_data/analysis/registry.py)" = "$OLD_REGISTRY_PY" ] || die "registry.py is not the version this delivery replaces; nothing committed"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces; nothing committed"
[ "$(sha user_data/analysis/results/registry.jsonl)" = "$OLD_REGISTRY_JSONL" ] || die "registry.jsonl is not the 12-line file this delivery expects; nothing committed"
[ ! -e docs/correspondence/answer-04.md ] && [ ! -e docs/correspondence/message-14.md ] || die "answer-04.md or message-14.md already exists"
echo "files to replace are the expected versions; registry.jsonl: $(wc -l < user_data/analysis/results/registry.jsonl | tr -d ' ') lines"

echo "-- 3. backup (inside the project)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp user_data/analysis/results/registry.jsonl "$BK/registry.jsonl"
cp user_data/analysis/registry.py "$BK/registry.py"
cp context/STATUS.md "$BK/STATUS.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"

echo "-- 4. new registry.py in place, then ALL self-tests (existing ones unchanged except registry.py's own)"
APPLIED=1
cp "$HERE/registry.py" user_data/analysis/registry.py
[ "$(sha user_data/analysis/registry.py)" = "$EXP_REGISTRY_PY" ] || die "copy of registry.py failed verification"
mkdir -p "$REPO/temp/tmp-selftest"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
LOG="$REPO/temp/selftest-step1-$STAMP.log"
set +e
TMPDIR="$REPO/temp/tmp-selftest" GIT_CEILING_DIRECTORIES="$REPO/temp" PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
echo "full log: $LOG"
[ "$ST_CODE" -eq 0 ] || { echo "last 25 lines of the log:"; tail -25 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
[ "$(sha user_data/analysis/results/registry.jsonl)" = "$OLD_REGISTRY_JSONL" ] || die "registry.jsonl CHANGED during the self-tests"
echo "registry.jsonl byte-identical after the self-tests"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/1/' | grep -v '^ M user_data/analysis/registry.py$' || true)"
if [ -n "$DIRTY2" ]; then echo "$DIRTY2"; die "the self-tests left unexpected modified or untracked files"; fi
echo "no stray files after the self-tests"

echo "-- 5. void the two pre-fix S1 families in the live registry"
CODE_COMMIT="$(git rev-parse HEAD)"
REG="user_data/analysis/results/registry.jsonl"
for fp in "S1-ETHUSDT ETHUSDT" "S1-BTCUSDT BTCUSDT"; do
  set -- $fp
  "$PYBIN" user_data/analysis/registry.py --void-family "$1" --pair "$2" --reason "$VOID_REASON" --registry-path "$REG" --code-commit "$CODE_COMMIT"
done
echo "(dry run above; now writing)"
for fp in "S1-ETHUSDT ETHUSDT" "S1-BTCUSDT BTCUSDT"; do
  set -- $fp
  "$PYBIN" user_data/analysis/registry.py --void-family "$1" --pair "$2" --reason "$VOID_REASON" --registry-path "$REG" --code-commit "$CODE_COMMIT" --commit-to-registry
done
OLD_BYTES="$(wc -c < "$BK/registry.jsonl" | tr -d ' ')"
head -c "$OLD_BYTES" "$REG" | cmp -s - "$BK/registry.jsonl" || die "the first 12 lines of registry.jsonl are NOT byte-identical to the backup"
echo "first 12 lines byte-identical to the backup"
CHECK="$("$PYBIN" - <<PYEOF
import sys
sys.path.insert(0, "user_data/analysis")
import registry
recs = registry.load_records("$REG")
assert len(recs) == 14, len(recs)
out = ["lines=%d" % len(recs)]
for pair in ("ETHUSDT", "BTCUSDT"):
    n = registry.cumulative_count(recs, pair)
    c = registry.cumulative_cells(recs, pair)
    holm = {s: len(registry.holm_at_step(recs, pair, s)) for s in ("discovery", "stability", "economic_gate")}
    assert n == 0 and c == 0 and sum(holm.values()) == 0, (pair, n, c, holm)
    out.append("%s live_families=%d cells=%d holm_members=%s" % (pair, n, c, holm))
m1, m2 = recs[-2], recs[-1]
assert registry.is_void_marker(m1) and registry.is_void_marker(m2)
assert m1["detail"]["target_record_numbers"] == [1, 2, 3, 7, 8, 9], m1["detail"]["target_record_numbers"]
assert m2["detail"]["target_record_numbers"] == [4, 5, 6, 10, 11, 12], m2["detail"]["target_record_numbers"]
print("\n".join(out))
PYEOF
)" || die "post-void verification failed"
echo "$CHECK"
git status --porcelain --untracked-files=all | grep -v '^?? deliveries/1/' | sort | tr '\n' ' ' | grep -q '^ M user_data/analysis/registry.py  M user_data/analysis/results/registry.jsonl $' || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the void"; }

echo "-- 6. place documents, commit, push"
cp "$HERE/answer-04.md" docs/correspondence/answer-04.md
cp "$HERE/message-14.md" docs/correspondence/message-14.md
cp "$HERE/STATUS.md" context/STATUS.md
[ "$(sha docs/correspondence/answer-04.md)" = "$EXP_ANSWER04" ] && [ "$(sha docs/correspondence/message-14.md)" = "$EXP_MSG14" ] && [ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] || die "a document copy failed verification"
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
git add user_data/analysis/registry.py user_data/analysis/results/registry.jsonl docs/correspondence/answer-04.md docs/correspondence/message-14.md context/STATUS.md deliveries/1/apply.sh deliveries/1/registry.py deliveries/1/answer-04.md deliveries/1/message-14.md deliveries/1/STATUS.md
STAGED="$(git diff --cached --name-only | sort | tr '\n' ' ')"
WANT="context/STATUS.md deliveries/1/STATUS.md deliveries/1/answer-04.md deliveries/1/apply.sh deliveries/1/message-14.md deliveries/1/registry.py docs/correspondence/answer-04.md docs/correspondence/message-14.md user_data/analysis/registry.py user_data/analysis/results/registry.jsonl "
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected ten: $STAGED"
git commit -q -m "[D1] WO 1.5 step 1: registry void markers + R1 Holm; void pre-fix S1-ETHUSDT and S1-BTCUSDT; answer-04, message-14"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
git push origin main
FINISHED=1
echo
echo "last two registry lines (the void markers):"
tail -n 2 "$REG" | cut -c1-230
echo
echo "PASS  commit $HASH"
