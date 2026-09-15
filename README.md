# Crypto strategy backtest lab

A freqtrade project for backtesting rules-based strategies on Binance data
before risking any real money. Everything runs in Docker, so you don't need
to install Python packages, TA-Lib, or worry about your system's Python
version at all.

## What's in here

- `docker-compose.yml` - runs freqtrade in a container
- `user_data/config.json` - exchange, pair, stake, and fee settings
- `user_data/strategies/MomentumTrailing.py` - strategy #1: enter on a 1%
  rise in the last candle, exit on a 1% pullback from the peak
- `scripts/download_data.sh` - pulls free historical candles from Binance
- `scripts/backtest.sh` - runs a backtest, with the fee/cost assumption as
  one editable variable at the top

## One-time setup

1. Install Docker Desktop: https://www.docker.com/products/docker-desktop/
   (Mac, Windows, and Linux are all supported. On Windows, Docker Desktop
   will ask to enable WSL2 - accept that.)
2. Open a terminal in this folder and pull the freqtrade image:
   ```
   docker compose pull
   ```
3. Turn the two scripts into runnable files (one-time, macOS/Linux only -
   skip this on Windows and just run them with `bash scripts/download_data.sh`):
   ```
   chmod +x scripts/*.sh
   ```

## Getting your first backtest result

1. Download historical 1-minute data for ETH/FDUSD (free, pulled straight
   from Binance's public API - no account or payment needed):
   ```
   ./scripts/download_data.sh
   ```
   This saves the candles under `user_data/data/binance/`.

2. Run the backtest:
   ```
   ./scripts/backtest.sh
   ```
   freqtrade will print a results table: total trades, win rate, profit,
   drawdown, and more. It also writes a detailed results file under
   `user_data/backtest_results/` for later analysis.

3. To test a different parameter, open
   `user_data/strategies/MomentumTrailing.py` and change a number - for
   example `ENTRY_PCT_THRESHOLD = 0.01` to `0.005`, or
   `trailing_stop_positive = 0.01` to `0.015`. Save, then re-run
   `./scripts/backtest.sh`.

4. To test a genuinely different rule (not just a different number), copy
   the strategy file to a new name (e.g. `Candlestick5m.py`), rename the
   class inside it to match, and point `--strategy` at the new class name
   in `scripts/backtest.sh`. We'll build the candlestick + 5-minute and
   multi-indicator versions the same way as we go.

## About the fee/spread/slippage number

You asked where to update this. It's the `FEE` variable at the top of
`scripts/backtest.sh`. freqtrade applies it once on entry and once on
exit. It's currently set to `0.001` (0.10%), which is Binance's regular
(VIP 0) spot rate as of September 2026 - check your own account's fee
page for your actual rate, since VIP tier, the BNB fee discount, and
FDUSD promotions can all change it.

One honest limitation: freqtrade's basic backtester works from OHLCV
candles, so it doesn't separately model bid/ask spread or slippage the
way a real order book would - it assumes your order fills at the price
you asked for, as long as that price was within the candle's high/low
range. The practical workaround for now is to nudge `FEE` up slightly
above your raw exchange fee (e.g. to 0.0012-0.0015) as a rough stand-in
for spread and slippage combined. If a strategy still looks good after
that haircut, it's worth the extra effort later of modeling this more
precisely with finer-grained data - we can do that when we get there.

## Dry-run: the "live sandbox" you asked about

Once a strategy backtests well, the next step is dry-run, not the
Binance Testnet. Dry-run connects to real, live Binance market data and
simulates order fills against it, without ever placing a real order -
so it's a much closer match to real market conditions than the Testnet,
which trades against a mostly-empty practice order book with far less
liquidity than the real market. Save the Testnet, if you ever use it at
all, for checking that your API keys and order-placement code work -
not for judging whether a strategy is any good.

To dry-run: set `"dry_run": true` in `config.json` (already set), add
your Binance API key/secret to `config.json` for live price data
(a read-only key is enough for dry-run - no trading permission needed),
then run:
```
docker compose up -d
```
Watch the logs with `docker compose logs -f freqtrade`. Only after dry-run
results track your backtest over a real stretch of time - and only with
an amount you're fully prepared to lose - would we switch `dry_run` to
`false` and use a real trading-enabled key.

## On AI's role in this project

Claude (and any local model you add later) is used only to help write and
debug the code. The bot itself stays fully rules-based - every entry and
exit is a plain condition in the strategy file, decided in advance and
checked in the backtest, with no model making live trading decisions.

## Git

This folder is meant to be committed as-is (the `.gitignore` already
excludes downloaded data, logs, and the trade database, which don't
belong in version control):
```
git init
git add .
git commit -m "Initial freqtrade project: strategy 1 (momentum + trailing stop)"
```
