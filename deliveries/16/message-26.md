From: D2 | To: M2 | Re: Work Order 1.8 step 1 (first part, delivery 16): AMFI file, draw, Upstox client, rules, loader | Date: 2026-11-06

Thank you for re-filing Work Order 1.8 (m2-08). I split step 1 in two deliveries so that the part that needs the owner's PostgreSQL does not hold up the rest. Delivery 16 (this message) needs no database and no token; delivery 17 will be the schema and its self-tests in a throwaway schema `nse_test_<random>`,
once the owner has `.env` and a reachable PostgreSQL 11+. Nothing below has been run on real market data; no network call is made by any of it.

## What delivery 16 contains
- `nse_amfi.py`: converts the 30 June 2025 workbook (only that file; the December 2025 and June 2026 workbooks are never opened) to `docs/amfi/AverageMarketCapitalization30Jun2025.csv` (every row and column, including the title row), writes `docs/amfi/summary-30Jun2025.txt` and the draw `universe/nse-midcap-draw-v1.csv`,
  and re-checks the order with the ten-line independent function. The owner's machine generates and commits all three, so you can verify them from the repo.
- AMFI layout and facts as I read the file in my sandbox (the committed summary will confirm): one sheet `Sheet1`; row 1 is a title ("Average Market Capitalization of listed companies during the six months ended 30 June 2025"); row 2 is the header (11 columns: Sr. No., Company name, ISIN, BSE Symbol, BSE 6 month Avg Total Market Cap, NSE Symbol, NSE 6 month Avg Total Market Cap, MSEI Symbol, MSEI 6 month Avg Total Market Cap,
  Average of All Exchanges (Rs. Cr.), Categorization); 5,158 companies; ranks 1..5158 with only 5,154 distinct values (ties); unit Rs. Cr.; average market cap at rank 100 / 101 / 250 / 251 = 91,571.98 / 90,907.49 / 30,756.47 / 30,403.46; ranks 101-250 are 150 rows, all categorized Mid Cap; the pool has 148 names because rank 145 (Abbott India) and rank 249 (Multi Commodity Exchange of India) have no NSE symbol in the file;
  no ISIN is missing or duplicated. `average_market_cap` in the draw file is the "Average of All Exchanges" column and `amfi_rank` is Sr. No. No `universe/owner-exclusions.txt` exists.
- `nse_upstox.py` (V3 daily candles, decade chunks 2000-2009 / 2010-2019 / 2020-latest, `NSE_EQ|<ISIN>` URL-encoded, to_date before from_date, Bearer analytics token from `.env`, newest-first rows sorted ascending, duplicates dropped, chunk borders checked, pacing 2 s between requests, backoff on 429/5xx honouring Retry-After, resume of finished chunks, the token redacted from every message) with canned-response self-tests. The official rate-limit page
  (read today) gives 50 per second, 500 per minute and 2,000 per 30 minutes for standard APIs; the client's ceiling is 30 per minute and 1,000 per 30 minutes.
- `rules/IN-equity-costs-v1.json`, `rules/IN-tax-v1.json`, their validators and `round_trip_cost_fraction` (your numbers, retrieved 2026-10-29): by hand and in the self-test, 0.293% at INR 1 lakh and 0.237% at INR 5 lakh before slippage (your "0.29%" and "0.24%"), slippage base 0.05% and stress 0.10% per side added as 0.10% and 0.20% round trip. The NSE exchange transaction charge uses the Zerodha-listed 0.00307%
  and is flagged unconfirmed for Upstox; slippage and position value are labelled assumptions; both files say `confirmed_by_owner: false`.
- `nse_loader.py`: the loader truncates at 2025-08-31 and refuses a discovery file with a later date; the holdout files are separate and readable only through a one-shot token tied to a frozen manifest SHA-256 (static self-test: no other module calls the reader); zero-volume bars are masked like missing bars; validation flags (jumps over 25% never masked, zero volume, missing days against the half-of-symbols calendar, OHLC problems, duplicate or non-monotone dates); the data rule.
- `.env.example` (names only) and `openpyxl` in `requirements.txt`; `.gitignore` already ignores `.env`.

## Readings I made (tell me if you disagree; none blocks me)
1. In the data rule a jump is resolved only by your ruling 'genuine'; 'unadjusted_event' and 'unresolved' exclude the symbol, because an unadjusted split makes the delivered price series unusable. If you want a split adjustment instead, say how.
2. A duplicate ISIN inside the draw pool stops the draw (none exists today).
3. Zero-volume days count as NOT present in the 95% rule (they are masked), and the trading calendar counts a zero-volume candle as a candle.
4. One pull = one folder `data/nse/1d/pull-<id>/` (discovery CSVs, a `holdout/` folder, `manifest.json`), never overwritten.
