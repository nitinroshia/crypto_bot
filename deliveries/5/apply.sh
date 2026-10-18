#!/bin/bash
# deliveries/5/apply.sh -- D1, Work Order 1.5, step 5: the first LIVE run of S1 (ETH_USDT, then BTC_USDT).
#
# Put apply.sh, STATUS.md and message-18.md together in ~/apps/crypto_bot/deliveries/5/ and run:
#     bash ~/apps/crypto_bot/deliveries/5/apply.sh
# This is the one step that writes S1 results into the LIVE registry (three records per pair: discovery, stability,
# economic_gate). It runs the delivery-4 code unchanged and STOPS BEFORE freeze and forward-test: nothing is frozen,
# the holdout is not unlocked. What it does:
#   1. checks the SHA-256 of the delivered files, the state of the folder, that user_data/analysis is byte-identical to
#      commit f5a883a, and (read-only) that the live registry is the 14-line file with no live S1 records;
#   2. backs up the registry and STATUS.md into temp/backup-<UTC>/, runs ALL self-tests (35);
#   3. DRY RUN of each pair into a scratch registry (proves the pipeline completes before anything live is written);
#   4. the LIVE run, once per pair, with --commit-to-registry;
#   5. checks the result: 14 -> 20 lines, first 14 byte-identical, every live record equals its dry-run record,
#      cumulative_count 1 per pair, holm_at_step one family per step, no frozen/holdout record;
#   6. commits exactly seven paths and pushes. On any failure BEFORE the commit it restores the registry from git.
set -e

REPO="${1:-$HOME/apps/crypto_bot}"
EXP_STATUS="aa02f7de152f39baf14bbafe2ba3d1b25ca269362d094101a75b1cb04db2adb5"
EXP_MSG18="391d5c7b8cbefa7d21c4a63a1c56ba73fce671c6305c86c6cc54981b2f219826"
OLD_STATUS="e15f19d06345966830dab6de9430adc25eb6405b9abeb207bf12222a36f4b80c"
LIVE_REG_SHA="70c91da708f7397251c224a111aada2932dfc0d1bb25ec13e0480dab320f9fe2"
REG="user_data/analysis/results/registry.jsonl"

FINISHED=0; APPLIED=0; COMMITTED=0
rollback() {
  set +e
  git reset -q 2>/dev/null
  git checkout -- user_data/analysis/results/registry.jsonl context/STATUS.md 2>/dev/null
  rm -f docs/correspondence/message-18.md docs/reports/s1-run-step5.txt
  echo "Rolled back: the live registry and STATUS.md are exactly as before this script ran (restored from git)."
}
on_exit() {
  rc=$?
  if [ "$FINISHED" != "1" ]; then
    echo
    if [ "$COMMITTED" = "1" ]; then
      echo "FAIL (exit $rc): the commit exists locally but was NOT pushed. Run:  git -C $REPO push origin main  and paste its output."
      echo "Do NOT run this script again."
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

echo "== delivery 5 (D1, WO 1.5 step 5: first LIVE S1 run) =="
HERE="$(cd "$(dirname "$0")" && pwd -P)"
[ -d "$REPO/.git" ] || die "$REPO is not a git repository"
REPO="$(cd "$REPO" && pwd -P)"
[ "$HERE" = "$REPO/deliveries/5" ] || die "apply.sh must sit in $REPO/deliveries/5/ (it is in $HERE)"

echo "-- 1. checks (nothing is written yet)"
BAD=0
for pair in "STATUS.md:$EXP_STATUS" "message-18.md:$EXP_MSG18"; do
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
DIRTY="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/5/' || true)"
if [ -n "$DIRTY" ]; then echo "$DIRTY"; die "the folder has modified or untracked files (listed above). Nothing touched."; fi
[ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ] || die "git has no user.name / user.email configured"
git fetch origin
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
git merge-base --is-ancestor "$LOCAL" "$REMOTE" || die "your HEAD is not an ancestor of origin/main: your folder has commits GitHub lacks. Nothing touched."
if [ "$LOCAL" != "$REMOTE" ]; then git merge --ff-only origin/main; echo "fast-forwarded to $(git rev-parse --short HEAD)"; fi
git merge-base --is-ancestor f5a883a HEAD || die "delivery 4 (f5a883a) is not in your history; run delivery 4 first"
git diff --quiet f5a883a -- user_data/analysis || die "user_data/analysis differs from commit f5a883a (the verified delivery-4 code); refusing to run live"
echo "folder clean, on main, HEAD $(git rev-parse --short HEAD); user_data/analysis is byte-identical to f5a883a"
[ "$(sha context/STATUS.md)" = "$OLD_STATUS" ] || die "context/STATUS.md is not the version this delivery replaces"
[ ! -e docs/correspondence/message-18.md ] && [ ! -e docs/reports/s1-run-step5.txt ] || die "message-18.md or the step-5 run report already exists (this step must run once)"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the live registry is not the 14-line file committed in ac63ff2 (hash differs); nothing touched"
PYBIN="$REPO/.venv/bin/python3"
[ -x "$PYBIN" ] || die "$PYBIN not found"
"$PYBIN" - "$REPO" <<'PYEOF' || die "the live registry is not in the expected pre-run state"
import sys
sys.path.insert(0, sys.argv[1] + "/user_data/analysis")
import registry
recs = registry.load_records(registry.LIVE_REGISTRY_PATH)
assert len(recs) == 14, len(recs)
for pair in ("ETHUSDT", "BTCUSDT"):
    assert registry.cumulative_count(recs, pair) == 0, f"{pair} already has live S1 records"
assert not any(r["status"] in ("frozen", "holdout_consumed") for r in recs), "a lock record exists"
print("live registry: 14 lines, 0 live families for ETHUSDT and BTCUSDT, no frozen/holdout record")
PYEOF

echo "-- 2. backup (inside the project), then ALL self-tests"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$REPO/temp/backup-$STAMP"
mkdir -p "$BK"
cp $REG "$BK/registry.jsonl"
cp context/STATUS.md "$BK/STATUS.md"
git rev-parse HEAD > "$BK/HEAD.txt"
if find "$BK" -name '*secret*' | grep -q .; then die "a secrets file ended up in the backup; aborting"; fi
echo "backup written: $BK"
echo "python: $("$PYBIN" --version 2>&1)"
LOG="$REPO/temp/selftest-step5-$STAMP.log"
set +e
PYTHON="$PYBIN" bash user_data/analysis/selftest_all.sh > "$LOG" 2>&1
ST_CODE=$?
set -e
echo "tests started: $(grep -c '^=================== ' "$LOG")"
grep -E '^\*\*\* FAILED|^ALL SELF-TESTS|^SOME SELF-TESTS' "$LOG" || true
[ "$ST_CODE" -eq 0 ] || { echo "last 25 lines of the log:"; tail -25 "$LOG"; die "self-tests failed (exit $ST_CODE)"; }
grep -q '^ALL SELF-TESTS PASSED' "$LOG" || die "self-test output lacks 'ALL SELF-TESTS PASSED'"
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the self-tests"
DIRTY2="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/5/' || true)"
[ -z "$DIRTY2" ] || { echo "$DIRTY2"; die "the self-tests left modified or untracked files"; }
echo "live registry byte-identical after the self-tests; no stray files"

echo "-- 3. DRY RUN of each pair into a scratch registry (nothing live is written)"
RUNDIR="$REPO/temp/step5-$STAMP"
mkdir -p "$RUNDIR"
for P in ETH_USDT BTC_USDT; do
  ( cd user_data/analysis && "$PYBIN" run_s1.py --pair "$P" --registry-path "$RUNDIR/dryrun-$P.jsonl" ) > "$RUNDIR/dryrun-$P.out" 2>&1 || { tail -20 "$RUNDIR/dryrun-$P.out"; die "the dry run of $P failed"; }
  [ "$(wc -l < "$RUNDIR/dryrun-$P.jsonl" | tr -d ' ')" = "3" ] || die "the dry run of $P did not write exactly three scratch records"
  echo "dry run $P: ok, 3 scratch records"
done
[ "$(sha $REG)" = "$LIVE_REG_SHA" ] || die "the LIVE registry changed during the dry runs"

echo "-- 4. LIVE run, once per pair, with --commit-to-registry (discovery, stability, economic_gate; no freeze, no forward test)"
APPLIED=1
for P in ETH_USDT BTC_USDT; do
  echo "   live run: $P"
  ( cd user_data/analysis && "$PYBIN" run_s1.py --pair "$P" --commit-to-registry ) > "$RUNDIR/live-$P.out" 2>&1 || { tail -20 "$RUNDIR/live-$P.out"; die "the LIVE run of $P failed"; }
  head -1 "$RUNDIR/live-$P.out"
done

echo "-- 5. checks on the live registry"
OLD_BYTES="$(wc -c < "$BK/registry.jsonl" | tr -d ' ')"
head -c "$OLD_BYTES" "$REG" | cmp -s - "$BK/registry.jsonl" || die "the first 14 lines of registry.jsonl are NOT byte-identical to the backup"
echo "first 14 lines byte-identical to the backup"
"$PYBIN" - "$REPO" "$RUNDIR" <<'PYEOF' || die "post-run verification of the live registry failed"
import json, sys
sys.path.insert(0, sys.argv[1] + "/user_data/analysis")
import registry
from pathlib import Path

rundir = Path(sys.argv[2])
live = registry.load_records(registry.LIVE_REGISTRY_PATH)
assert len(live) == 20, f"{len(live)} lines, expected 20"
steps = ["discovery", "stability", "economic_gate"]
for pair_dir, pair, family, start in (("ETH_USDT", "ETHUSDT", "S1-ETHUSDT", 14), ("BTC_USDT", "BTCUSDT", "S1-BTCUSDT", 17)):
    new = live[start : start + 3]
    assert [r["status"] for r in new] == steps, [r["status"] for r in new]
    assert all(r["family"] == family and r["pair"] == pair for r in new)
    dry = registry.load_records(rundir / f"dryrun-{pair_dir}.jsonl")
    for a, b in zip(new, dry):
        assert a["status"] == b["status"]
        assert json.dumps(a["detail"], sort_keys=True, default=str) == json.dumps(b["detail"], sort_keys=True, default=str), \
            f"{pair}: live {a['status']} record differs from the dry-run record"
    assert registry.cumulative_count(live, pair) == 1, "cumulative_count"
    assert registry.cumulative_cells(live, pair) == 10, "cumulative_cells"
    holm = {s: registry.holm_at_step(live, pair, s) for s in steps}
    import math
    for s, h in holm.items():
        assert list(h) == [family], f"holm_at_step {s}: {list(h)}"
        if s == "economic_gate":
            # The gate is a pass/fail rule, not a test: its record has no p-value, so Holm is undefined (NaN) here.
            assert math.isnan(h[family]["p_raw"]), "the economic_gate record is expected to carry no p-value"
        else:
            assert math.isfinite(h[family]["p_raw"]) and abs(h[family]["p_holm"] - h[family]["p_raw"]) < 1e-15, \
                f"holm_at_step {s}: a family of one must have p_holm == p_raw (finite)"
    d, st, g = (r["detail"] for r in new)
    print(f"{pair}: records {start + 1}-{start + 3} written; cumulative_count 1, cells 10; Holm family of one at discovery and stability (the economic gate has no p-value)")
    print(f"   discovery (primary cell L=40,h=5, own-family Holm of 10): slope {d['slope']:.6g}  n {d['n']}  one-sided p {d['p_value']:.6g}  Holm-in-family p {d['family_p_holm']:.6g}")
    print(f"   stability: T {st['T']:.4f}  p_stab {st['p_value']:.6g}  passes {st['passes']}  blocks with s_b>0 {st['share_blocks_positive']:.1%}")
    print(f"   economic gate (stress): pooled net {g['pooled_net_return']:.6g}  non-negative full blocks {g['pass_rate']:.1%}  passes {g['passes']}")
assert sum(1 for r in live if r["status"] in ("frozen", "holdout_consumed")) == 0, "a lock record was written"
assert sum(1 for r in live if registry.is_void_marker(r)) == 2, "the two void markers must still be there"
print("no frozen or holdout_consumed record; the two void markers are intact; 20 lines in all")
PYEOF
DIRTY3="$(git status --porcelain --untracked-files=all | grep -v '^?? deliveries/5/' | tr '\n' '|')"
[ "$DIRTY3" = " M user_data/analysis/results/registry.jsonl|" ] || { git status --porcelain --untracked-files=all; die "unexpected set of changed files after the live runs"; }

echo "-- 6. place documents, commit, push"
mkdir -p docs/reports
{
  echo "S1 live run, Work Order 1.5 step 5"
  echo "produced by deliveries/5/apply.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ) (repo HEAD before this commit: $(git rev-parse --short HEAD); void commit of step 1: ac63ff2)"
  echo "python: $("$PYBIN" --version 2>&1). Each pair was run once into the LIVE registry with --commit-to-registry; no freeze, no forward test."
  for P in ETH_USDT BTC_USDT; do
    echo
    echo "################################ $P"
    cat "$RUNDIR/live-$P.out"
  done
} > docs/reports/s1-run-step5.txt
cp "$HERE/STATUS.md" context/STATUS.md
cp "$HERE/message-18.md" docs/correspondence/message-18.md
[ "$(sha context/STATUS.md)" = "$EXP_STATUS" ] && [ "$(sha docs/correspondence/message-18.md)" = "$EXP_MSG18" ] || die "a document copy failed verification"
git push --dry-run origin main >/dev/null 2>&1 || die "cannot reach GitHub for a push (checked before committing)"
git add user_data/analysis/results/registry.jsonl docs/reports/s1-run-step5.txt context/STATUS.md docs/correspondence/message-18.md deliveries/5/apply.sh deliveries/5/STATUS.md deliveries/5/message-18.md
STAGED="$(git diff --cached --name-only | LC_ALL=C sort | tr '\n' ' ')"
WANT="context/STATUS.md deliveries/5/STATUS.md deliveries/5/apply.sh deliveries/5/message-18.md docs/correspondence/message-18.md docs/reports/s1-run-step5.txt user_data/analysis/results/registry.jsonl "
[ "$STAGED" = "$WANT" ] || die "staged paths differ from the expected seven: $STAGED"
git commit -q -m "[D1] WO 1.5 step 5: first live S1 run (ETH_USDT, BTC_USDT): discovery, stability, economic_gate records, once per pair; no freeze, no forward test; run report, message-18"
COMMITTED=1
HASH="$(git rev-parse --short HEAD)"
git push origin main
FINISHED=1
echo
echo "PASS  commit $HASH"
