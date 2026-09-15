#!/usr/bin/env bash
set -e

# ---- Edit these as you test parameters ----
STRATEGY="MomentumTrailing"
TIMERANGE="20260319-20260901"


# All-in round-trip trading cost per trade, as a ratio (0.001 = 0.10%).
# freqtrade applies this once on entry and once on exit.
#
# 0.001 is Binance's current regular-tier (VIP 0) spot fee, both maker
# and taker, as of September 2026. freqtrade's basic backtester doesn't
# separately model spread or slippage, so until we add a more detailed
# model, the honest way to account for them is to nudge this number up
# a bit above the raw fee (e.g. 0.0012-0.0015) as a buffer.
#
# Update the 0.001 below once you've checked your account's actual fee
# page (VIP tier, BNB discount, and current ETH/FDUSD promo status all
# change this).
FEE=0.001
# --------------------------------------------

docker compose run --rm freqtrade backtesting \
  --config user_data/config.json \
  --strategy "$STRATEGY" \
  --timerange "$TIMERANGE" \
  --fee "$FEE"
