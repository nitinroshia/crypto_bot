#!/usr/bin/env bash
set -e

# ---- Edit these as you test parameters ----
STRATEGY="MomentumTrailing"

# The range ends 20250831, the discovery cutoff. Data after 2025-08-31 is a
# locked holdout, read only by the forward-test command, once per candidate.
# The holdout lock covers strategy backtests too: do not extend this range.
TIMERANGE="20250301-20250831"

PARAMS_FILE="user_data/test_params.json"    # <- timeframe, entry threshold,
                                            #    stoploss, and trailing-stop
                                            #    values all live here now,
                                            #    not in the strategy file.

# Cost case: base or stress (user_data/analysis/costs.py). Choose it with the
# COST_CASE environment variable, e.g.  COST_CASE=stress bash scripts/backtest.sh
COST_CASE="${COST_CASE:-base}"

# Trading fee PER SIDE, as a ratio. freqtrade applies it once on entry and
# once on exit, so a round trip pays it twice.
#
# The number comes from costs.py, which owns the project's cost model:
#   base   = fee 0.10% + slippage 0.02% per side -> 0.0012
#   stress = fee 0.12% + slippage 0.03% per side -> 0.0015
# 0.10% is the project's planning fee for makers AND takers. The account's
# current maker fee of 0% is a promotion and is ignored; promotions are never
# modeled.
#
# freqtrade has no slippage setting, so the per-side fee plus slippage is
# passed to it as the fee. That agrees with costs.py net_return within 1e-8.
FEE=$(python3 user_data/analysis/costs.py --per-side "$COST_CASE")
# --------------------------------------------

CMD=(docker compose run --rm freqtrade backtesting
  --config user_data/config.json
  --config "$PARAMS_FILE"
  --strategy "$STRATEGY"
  --timerange "$TIMERANGE"
  --fee "$FEE"
  --cache none)

# PRINT_ONLY=1 prints the resolved command and exits without running Docker.
if [ "${PRINT_ONLY:-0}" = "1" ]; then
  printf '%s ' "${CMD[@]}"
  printf '\n'
  exit 0
fi

"${CMD[@]}"