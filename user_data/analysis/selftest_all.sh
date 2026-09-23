#!/usr/bin/env bash
# Runs every self-test in user_data/analysis (all offline, synthetic data with
# known ground truth). Run from user_data/analysis:   bash selftest_all.sh
# Paste the whole output back if anything fails.
set -u
cd "$(dirname "$0")"
# Self-tests use the system temp dir (tempfile's default) -- project-local temp/ was
# discontinued in the 2026-09-22 repo restructuring.
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
run databundle.py
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
echo
if [ "$fail" -eq 0 ]; then echo "ALL SELF-TESTS PASSED"; else echo "SOME SELF-TESTS FAILED (see *** lines above)"; fi
exit $fail
