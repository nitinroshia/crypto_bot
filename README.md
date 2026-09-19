# Crypto strategy backtest lab

A freqtrade project for backtesting rules-based strategies on Binance data
before risking any real money. Everything runs in Docker, so you don't need
to install Python packages, TA-Lib, or worry about your system's Python
version at all.

## What's in here

- `docker-compose.yml` - runs freqtrade in a container
- `user_data/config.json` - exchange, pair, stake, and fee settings
- `user_data/test_params.json` - every value you'd want to change between
  test runs on `MomentumTrailing.py` (timeframe, entry threshold, stoploss,
  trailing stop) lives here, not in the strategy file or `backtest.sh` -
  see "Getting your first backtest result" below
- `user_data/strategies/MomentumTrailing.py` - strategy #1: enter on a rise
  in the last candle, exit on a pullback from the peak (trailing stop)
- `scripts/download_data.sh` - pulls free historical candles from Binance
- `scripts/backtest.sh` - runs a backtest
- `user_data/analysis/` - a separate math/statistics toolkit that studies
  the downloaded price data itself (see "Workflow" and "The analysis
  toolkit" below) - this does not touch the strategy or the backtest; it's
  a research step that runs before deciding what any strategy's rules
  should even be. `research_cli.py` inside it is the single entry point
  for testing a mathematical idea against real data.

## Workflow: research first, strategy second

Two layers, kept deliberately separate:

**Research layer** (`user_data/analysis/`, plain Python, a run takes
seconds) - this is where a mathematical idea gets tested as *math*: does
this signal have predictive structure, yes or no, with a real p-value and
a real out-of-sample check. No freqtrade, no Docker, no simulated trades.

- A new formula = one function in `research_cli.py`, registered with
  `@register("name", "description")`. Nothing else in that file needs to
  change.
- Test it: `python3 research_cli.py --formula name --param pair=5m:15m --max-lag 20` (params are formula-specific -- see "Formula contract" in `project_context.md`)
- Validate it before trusting it:
  `... --walkforward --fit-days 270 --validate-days 90`. A result that
  doesn't replicate across walk-forward splits is noise, not a rule to
  build a strategy on - see `research_cli.py`'s own module docstring for
  how the replication check works.
- Every run (guided or flagged) writes a manifest to
  `analysis/results/runs/` - that folder is the record of what's already
  been tried and what survived, so it doesn't need to be re-derived from
  memory or from scrolling back through a chat.

**Strategy layer** (`user_data/strategies/`, freqtrade + Docker, one
backtest run takes longer and reports trade counts, not statistical
significance) - only once a formula has survived the research layer does
it get promoted here, as entry/exit rules in a strategy file.

**The mistake to avoid:** testing a mathematical idea by editing a
freqtrade strategy and running a backtest. A backtest mixes in fees, exits,
and position sizing, and with a handful of trades you learn nothing about
whether the underlying math has an edge - `MomentumTrailing.py`'s current
backtest (3 trades over ~165 days) is a real example of this: not wrong,
just far too small a sample to be evidence of anything either way. Test
the math in the research layer first; only bring it to the strategy layer
once it's proven itself there.

**For anyone (AI or human) about to add a new formula:** read
`project_context.md`'s mistake log first. Every entry there is a specific,
already-paid-for lesson about how naive lead-lag/correlation tests silently
manufacture fake findings out of overlapping time windows. Skipping this
is the fastest way to spend a session rediscovering one of those from
scratch.

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

3. To test a different parameter, open `user_data/test_params.json` and
   change a value - for example `"entry_pct_threshold": 0.01` to `0.005`,
   or `"timeframe": "5m"` to `"15m"`. Save, then re-run
   `./scripts/backtest.sh`. Nothing in `MomentumTrailing.py` or
   `backtest.sh` needs touching for this - see that file's own docstring
   for how the override reaches the strategy.

4. To test a genuinely different rule (not just a different number), copy
   the strategy file to a new name (e.g. `Candlestick5m.py`), rename the
   class inside it to match, and point `--strategy` at the new class name
   in `scripts/backtest.sh`. We'll build the candlestick and multi-indicator
   versions the same way as we go - and per the workflow above, any new
   rule's underlying math should already have survived the research layer
   before it gets written here.

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

## The analysis toolkit (`user_data/analysis/`)

Before writing or tuning any strategy rule, this project's approach is to
study the raw price data mathematically first, and only set a rule's
numbers once the data itself justifies them - not because a number "looks
right" on a chart. That study happens separately from the strategy/backtest
files above, in its own set of scripts. See "Workflow" above for how this
connects to the strategy layer.

**Setup (one-time):** these scripts run as plain Python on your machine
(not inside the freqtrade Docker container), so they need their own small
environment:
```
pyenv install 3.11.9        # if you don't already have a recent Python via pyenv
pyenv local 3.11.9
python3 -m venv .venv
source .venv/bin/activate
pip install -r user_data/analysis/requirements.txt
```

**First, pull the extra timeframes** the analysis needs (1m, 5m, 15m, 30m,
1h, 1d, 1w - the regular `download_data.sh` above only pulls 1m):
```
./scripts/download_data.sh
```

**Running the full, fixed battery of checks:**
```
python3 user_data/analysis/run_fingerprint.py
```
This produces `user_data/analysis/results/`, containing:
- `fingerprints.json` - statistics for each timeframe (is it stable over
  time, is it randomly distributed, is bigger volume tied to bigger price
  moves, how many candles have zero trading activity, etc.)
- `leadlag_summary.json` and several `leadlag_*.csv` files - tests of
  whether one timeframe's price moves predict another's, against the
  three standard pairs (`1m:5m`, `5m:15m`, `5m:1h`)
- `resample_checks.json` - a data-quality check comparing two independently
  computed versions of the same data, to catch bugs before trusting anything
  built on top of them

Add `--fast` to the command above for a much quicker run while testing that
things work - but don't read conclusions from a `--fast` run, only use the
full version's output for anything you intend to trust.

**Testing one formula at a time, or a new idea:** `run_fingerprint.py`
above always runs the same fixed battery against the three standard pairs.
For anything more exploratory - a new formula, a different lag range, or
checking whether a finding actually holds out-of-sample - use
`research_cli.py` instead:
```
python3 user_data/analysis/research_cli.py                     # guided mode -- answers prompts, no file editing
python3 user_data/analysis/research_cli.py --list-formulas
python3 user_data/analysis/research_cli.py --formula event_anchored --param pair=5m:15m \
    --max-lag 20 --walkforward --fit-days 270 --validate-days 90
```
A formula isn't limited to comparing two timeframes -- `--param` is
repeatable and formula-specific (`volume_leads_volatility`, for instance,
takes `--param timeframe=5m` instead of a pair). See `project_context.md`'s
"Formula contract" section for the full spec on what a new formula needs
to accept and return, written to be readable whether you're proposing an
idea in plain language or writing the Python for it, and
`research_cli.py`'s own module docstring for the mechanical detail. See
the "Workflow" section above for how a formula proven here is meant to
reach the strategy layer.

See `project_context.md` for a full explanation of what's been found so
far, what each piece of the toolkit does, and what mistakes were already
made and fixed along the way - required reading (or hand it to a fresh AI
chat) before designing any new calculation on this data.

## On AI's role in this project

Claude (and any local model you add later) is used only to help write and
debug the code. The bot itself stays fully rules-based - every entry and
exit is a plain condition in the strategy file, decided in advance and
checked in the backtest, with no model making live trading decisions. A
formula an AI proposes is a hypothesis to test through the research layer
above, not a finding - it gets the same walk-forward scrutiny as an idea
from anywhere else before it's trusted.

## Git

This folder is meant to be committed as-is (the `.gitignore` already
excludes downloaded data, logs, and the trade database, which don't
belong in version control):
```
git init
git add .
git commit -m "Initial freqtrade project: strategy 1 (momentum + trailing stop)"
```