#!/usr/bin/env bash
# Runs every self-test in user_data/analysis (all offline, synthetic data with
# known ground truth). Run from user_data/analysis:   bash selftest_all.sh
# Paste the whole output back if anything fails.
set -u
cd "$(dirname "$0")"
# Scratch rule (owner, 2026-10): nothing is written outside the project root. All self-test
# scratch therefore goes to <repo>/temp/tmp-selftest (temp/ is gitignored); this reverses the
# 2026-09-22 convention of using the system temp dir. GIT_CEILING_DIRECTORIES makes git treat
# directories under temp/ as non-repos (freeze_manifest.py's self-test needs a non-repo dir).
REPO_ROOT="$(cd ../.. && pwd -P)"
mkdir -p "$REPO_ROOT/temp/tmp-selftest"
export TMPDIR="$REPO_ROOT/temp/tmp-selftest"
export GIT_CEILING_DIRECTORIES="$REPO_ROOT/temp"
# Registry hygiene (Work Order 1.5 step 2): no self-test may change the LIVE registry.
LIVE_REG="results/registry.jsonl"
reg_hash() {
  if [ -f "$LIVE_REG" ]; then (shasum -a 256 "$LIVE_REG" 2>/dev/null || sha256sum "$LIVE_REG") | awk '{print $1}'; else echo none; fi
}
REG_BEFORE="$(reg_hash)"
fail=0
run() {
  echo "=================== $*"
  out=$(${PYTHON:-python3} "$@" 2>&1); code=$?
  echo "$out" | tail -${TAIL:-40}
  if [ "$code" -ne 0 ]; then echo "*** FAILED (exit $code): $*"; fail=1; fi
}
run resample.py
run resample_rule_test.py --self-test
run stats_fingerprint.py
run walkforward.py
run config_schema.py
run leadlag.py
run costs.py
run retired/costs_scenarios_AB.py
run multitest.py
run registry.py
run databundle.py
run cutoff.py
run holdout_lock.py
run nonstationarity.py
run blocks.py
run stability_check.py
run stability_acceptance.py
run s1_report.py --self-test
run rule_evaluator.py
run economic_gate.py
run freeze_manifest.py
run forward_test.py
run formula_s1.py
run formula_s2.py
run run_s1.py --self-test
run run_s2.py --self-test
run s2_report.py --self-test
run formula_t3.py
run selftest_registry_hygiene.py
run selftest_research_cli.py
run fetch_klines.py --self-test
run task0_report.py --self-test
run passive_fill_baseline.py --self-test
run funding.py
run fetch_funding.py --self-test
run locate_gaps.py --self-test
run liquidity_table.py --self-test
run build_derived_raw.py --self-test
run volatility_report.py --self-test
run breakeven_table.py --self-test
REG_AFTER="$(reg_hash)"
if [ "$REG_BEFORE" != "$REG_AFTER" ]; then
  echo "*** FAILED: the LIVE registry changed during the self-tests (before $REG_BEFORE, after $REG_AFTER)"
  fail=1
fi
echo
if [ "$fail" -eq 0 ]; then echo "ALL SELF-TESTS PASSED"; else echo "SOME SELF-TESTS FAILED (see *** lines above)"; fi
exit $fail
