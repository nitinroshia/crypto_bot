## Work order #1 (for the developer)

**Conventions for every task**
- Bars are left-labeled and usable only after they close. The earliest action is the next bar's open.
- Always report two cost scenarios:
  - **A:** maker entry and profit exit at 0%, with stops and time exits as taker at 0.10%.
  - **B:** all-taker, 0.10% per side.
  - freqtrade's single fee can't express A, so backtest at fee 0 and re-cost each trade by exit type. Maker orders must be post-only (LIMIT_MAKER).
- Fill rule, conservative: a resting buy fills only if a later 1m low is at least one tick below the limit (for sells, a high above it). It never fills in the bar it was placed. If a stop and a target are both hit in one bar, count the stop.
- Walk-forward: use `--fit-days 90 --validate-days 30` until Task 0 confirms the history length, since the README's 270+90 needs 360 days. Test only the fit-selected lag in validate. If `research_cli.py` rescans all lags, change it.
- Every result states its family size and adjusted p.

**Task 0: prerequisites**
- Report first/last timestamp and row count for every timeframe, including 1d. Confirm 1d built from 1m matches the native file (Binance days open 00:00 UTC).
- Report the account's actual ETH/FDUSD maker and taker fee from the fee page.
- Download ETH/USDT (1m, 5m, 1h, 1d) and FDUSD/USDT (1m) for the same span. Add the raw kline fields `taker buy base volume` and `number of trades` for both pairs (Binance API or data.binance.vision). Also pull ETH/USDT 1h and 1d back to 2017 for Wave 2.
- Extend `data` keys to `PAIR:timeframe`; existing formulas keep working on the default pair.
- Treat 2026-01-29 as a break for ETH/FDUSD, since taker fees returned for everyone that day and likely changed who trades it. Fast-signal validation uses post-break data only. The current sample should be entirely post-break; confirm.
- Re-run `run_fingerprint.py` in full (no `--fast`) with 1d included. Send `event_anchored_best` for the three standard pairs, with family size.

**Task 1: `cross_pair_lead` (my first bet)**
ETH/USDT is the deep market and ETH/FDUSD is the thin one (about 12% flat minutes), so the thin pair should follow.
- Predictor: ETH/USDT 1m return of closed bar t.
- Target: ETH/FDUSD 1m return in bar t+k, for k = 1…10, controlling for ETH/FDUSD's own returns at t, t−1, t−2. Report separately for flat vs traded ETH/FDUSD bars at t.
- Reuse the same-timeframe path of `hac_lagged_regression`. Keep flat bars on the grid (mask them, don't drop them).
- Three controls must pass before I read anything:
  - Same-minute correlation is very high, otherwise timestamps are misaligned.
  - The reversed direction (ETH/FDUSD → ETH/USDT, k = 1…10) is about 0.
  - ETH/USDT shifted by a random whole day is about 0.
- Gut-check: different order books, so no shared raw data. If real, I'd expect 0.05–0.30 in the flat state and about 0 when traded. Anything ≥0.6 is an alignment bug. Family: 20.

**Task 2: `passive_fill_baseline` (negative control, not a hypothesis test)**
Every 60 minutes, rest a buy at the last close minus d (d = 0.05%, 0.10%, 0.20%) for 15 minutes. Apply the fill rule. Record the fill rate and mean forward return from the limit price at +15/+30/+60 minutes after the fill, before fees. Mirror it for sells. A mean near zero means the simulator is honest. Clearly positive means it's optimistic. Clearly negative is adverse selection that every later signal has to beat.

**Task 3: `shock_response`**
- Event: a closed bar with |z| ≥ 3, where z is its return divided by the standard deviation of the prior 24h of same-timeframe returns (the bar itself excluded). Keep the first event in any 12-bar window and drop the rest.
- Target: return from the next bar's open to the close of bar k, k = 1…12. Report after down-shocks and up-shocks separately, since spot is long-only and those are the two tradable questions.
- Timeframes: 5m primary, 15m secondary. Primary tests are k = 6 for each side at 5m; everything else is a curve for interpretation. The effect at z ≥ 4 must be larger than at z ≥ 3, otherwise discard the result.
- Triage:
  - Mean ≥0.20%: viable even as a taker.
  - 0.05–0.20%: maker candidate for Wave 2.
  - Below 0.05%: dead.
- Gut-check: the volatility estimate excludes the event bar, and the target starts after that bar closes. An effect above ~1% at 60 minutes means a bug. Family: 48.

**Task 4: `vol_forecast`**
- Target: log realized variance (sum of squared 1m returns) over the next 60 minutes, with origins spaced 60 minutes apart so targets don't overlap.
- Baseline: trailing 1h, 4h, and 24h log realized variance, half-hour-of-day and day-of-week effects, and the trailing 5-day average high–low range from the 1d bars.
- Test variable: log of last-60-minute volume ÷ the median volume for the same half-hour over the prior 14 days.
- Report the baseline out-of-sample R², the gain from adding volume in every split, and a forecast-decile calibration table. Save the forecast as a column, because it will gate and size trades later. Family: 1 primary (gain > 0 in every split).

**Send back, per task:** family size, n, the effect (in % or correlation) beside the 0.20% and 0.05% hurdles, the walk-forward table (sign, p, lag per split), and a one-line verdict. Send Tasks 0 and 2 first, without waiting for the rest.

**What comes next.** Anything that misses the bar after one pre-declared revision is killed, not tuned. Survivors go to Wave 2:
- Passive-entry versions built on the Task 2 fill model.
- Order-flow imbalance as an adverse-selection filter.
- Funding-rate and long-history slow signals on ETH/USDT.
- Fractional-Kelly sizing. Spot means no leverage, so growth comes from trade frequency, not position size.

One risk sits outside the math: FDUSD is the cash leg, and it briefly traded below $0.90 in April 2025 before recovering, so size positions accordingly.
