#!/usr/bin/env bash
set -e

# ---- Things you'll change most often ----
PAIR="ETH/FDUSD"
TIMEFRAME="1m"
DAYS=180
# ------------------------------------------

docker compose run --rm freqtrade download-data \
  --config user_data/config.json \
  --pairs "$PAIR" \
  --timeframe "$TIMEFRAME" \
  --days "$DAYS"
