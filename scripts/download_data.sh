#!/usr/bin/env bash
set -e

# ---- Things you'll change most often ----
PAIR="ETH/FDUSD"
TIMEFRAMES=(1m 5m 15m 30m 1h 1d 1w)   # 10m dropped: not a native Binance interval
DAYS=1825                          # ~5 years - pull max available; freqtrade
                                    # will just start from the pair's actual
                                    # listing date if it's younger than this.
                                    # We deliberately do NOT limit this to the
                                    # 52-week analysis window: 1w candles need
                                    # much deeper history than 52 weeks to be
                                    # statistically usable (52 weeks = only 52
                                    # weekly candles).
# ------------------------------------------

docker compose run --rm freqtrade download-data \
  --config user_data/config.json \
  --pairs "$PAIR" \
  --timeframes "${TIMEFRAMES[@]}" \
  --days "$DAYS"

echo ""
echo "Downloaded timeframes: ${TIMEFRAMES[*]}"
echo "Check the log above for each timeframe's actual start date -- Binance"
echo "may not have ETH/FDUSD history going back the full $DAYS days, since"
echo "FDUSD is a newer stablecoin pair. Record whatever the real start date"
echo "turns out to be; that's the true depth of history we have to work with."