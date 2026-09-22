## For the new developer (forward as is): Answers 1.5

Your orientation reply is accepted. Three of your questions changed my orders; the rest confirm your working readings.

**A1–A5**
- **A1. S2 rank is the mid-rank.**
  - rank = (number of the previous 270 observations strictly below + 0.5 × number equal) ÷ 270, current excluded.
  - Report the tie share (the fraction of observations equal to the modal funding value).
  - Strict-below and at-or-below are labeled robustness variants only: no gate, no extra family.
- **A2. Gate windows.**
  - Use non-overlapping 90-day windows tiling the discovery sample from the first origin (your option b). A final partial window is dropped from the 70% count but stays in the pooled figure.
  - Pooled means first origin to the cutoff.
  - Window return is the compounded net strategy return inside the window at stress cost. The position carries across boundaries, and costs are charged when it changes.
  - Report the walk-forward validate windows (your option a) for information only.
- **A3. Funding interval changes.**
  - Observations are the 8h-aligned settlements only (00:00, 08:00, 16:00 UTC). Each observation's rate is the sum of the native rates settled in (s−8h, s], which equals the native rate when the interval is 8h.
  - The rank window therefore stays 270 observations and HAC lags stay 3 and 9. The ceil() rule in 7.8 is superseded.
  - Report the dates of any interval change and how many observations it touches.
- **A4. Holdout.**
  - (a) Agreed: truncate the freqtrade export at the cutoff. The forward-test command reads the raw store only, and may create a holdout-period export at test time.
  - (b) Treat the holdout as unseen for the pre-registered cells, with one disclosed exposure: aggregate ETH/FDUSD statistics for 2026 (fingerprint, lead-lag, Task 2). None of them was hypothesis-specific. Record that note in the registry for every holdout test. No hypothesis-specific statistic may be computed on post-cutoff data of any series (ETH/USDT, BTC/USDT, funding) outside the forward-test command, including the BTC replication signs.
  - (c) Yes: the holdout is everything after the cutoff up to the latest data at test time. The manifest records the data end date.
- **A5.** The execution pair is the owner's decision; the default is ETH/USDT. Nothing depends on it yet.

**Rulings on your working readings**
- **B1.** Confirmed. With A3 the rank window is always 270 observations.
- **B2. Entry time is the next open.**
  - The S1 target ln(C_{t+h}/C_t) is measured from the close of day t, which is the open of day t+1.
  - So origin t = 2025-08-31 belongs to the holdout (entry 2025-09-01 00:00).
  - The last discovery origin is t = 2025-08-30 for h = 1 and t = 2025-08-26 for h = 5. The family's common set ends 2025-08-26.
  - S2 follows the same rule: entry is the open of the bar labeled s+1h, and the first holdout origin is the settlement at 2025-09-01 00:00.
- **B3.** Clarification 1.4 governs.
- **B4.** Approved: SE_holdout = SE_discovery × sqrt(N_discovery / N_holdout), with N the primary cell's origins after purge. State it in the docstring.
- **B5.** 132 = 4 leading hours + 128 interior gaps is plausible; I recall the first ETHUSDT candle at 04:00 on 2017-08-17. The locator confirms it. Report the leading partial day separately, and quote `ls -l` bytes.

**Task 3 `shock_response`** (full spec; `workorder-01.md` is not needed). ETH/USDT; 5m primary, 15m secondary; family 48 = 2 timeframes × 12 lags × 2 sides.
- **Event:** a closed bar with |z| ≥ 3, where z is the bar's return divided by the standard deviation of the prior 24 hours of same-timeframe returns (the bar itself excluded; 288 bars at 5m, 96 at 15m). Keep the first event and ignore events until 13 bars later, so 12-bar forward windows never overlap.
- **Target:** the return from the open of the first bar after the event bar to the close of the k-th bar after it, for k = 1..12. Report it separately after down-shocks (z ≤ −3) and up-shocks (z ≥ +3), as the raw mean and as the excess over the unconditional mean at the same horizon.
- **Primary cells:** k = 6, each side, at 5m (two tests). Every other cell is an exploratory curve inside the family of 48.
- **Dose-response check** (not a test): the effect at |z| ≥ 4 must be larger than at |z| ≥ 3, otherwise discard the result.
- **Classification:** the three-way rule with M = 0.35% on the excess. An effect above about 1% at 60 minutes means a bug.
- **Gut-check:** the volatility estimate excludes the event bar, and the target starts after the event bar closes.

**Order of work.** Start with the data-batch tools and hand the owner the commands first, so the downloads run while you build items 1 and 2. S1 can run as soon as the machinery exists, since ETH/USDT 1d is on disk. S2 waits for the funding data.

**Snapshot.**
- Give the owner one command that copies the real files into `~/handover-2026-09-20/`: README.md, project_context.md, scripts/, user_data/analysis/ (without `__pycache__` and the large `*_orders.csv`) and test_params.json. It also writes `ls -lR` to `ls_lR.txt` inside that folder.
- The owner uploads that folder.
- Read every file in it in full before building anything, and report what you did not see.
