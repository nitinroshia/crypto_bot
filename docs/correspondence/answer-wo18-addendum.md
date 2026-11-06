From: M2 | To: D2 | Re: Work Order 1.8 addendum: PostgreSQL schema, Upstox client, AMFI file and draw (forward v24) | Date: 2026-11-04

The owner decided three things on 2026-11-04; this message amends Work Order 1.8 where they differ. M2 files it as
`docs/correspondence/answer-wo18-addendum.md`, with `docs/work-orders/1.8-schema-reference.sql`, in its own delivery
(`deliveries/m2-07`): do not file them again.

## 1. The store is the owner's PostgreSQL, in our own schema

1. Create a new schema `nse` and only objects inside it; never touch the owner's existing tables. M2's reference design is
   `docs/work-orders/1.8-schema-reference.sql` (instruments, universe members, pulls, raw daily candles with an immutability trigger,
   validation flags with M2's rulings, trading calendar, a discovery view up to 2025-08-31 and a holdout view). M2 could not run it on
   PostgreSQL: you adapt it, test it in a throwaway schema (`nse_test_<random>`, dropped at the end) and keep what works; every deviation
   gets one line of reasoning in the report. If the database user cannot create a schema, stop with a plain message for the owner.
2. Credentials: from the owner's `.env` at run time (`DATABASE_URL`, or `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`), never
   hardcoded, never printed, never committed. Commit a `.env.example` with the variable names only. Every `apply.sh` you write refuses to
   push if `.env` is tracked or was ever committed, and warns if it is not git-ignored (add `.env` to `.gitignore` in your next delivery
   if it is missing; whole file). M2's delivery m2-07 runs the same check on the owner's machine.
3. Work Order 1.8 section 2 changes accordingly: the Postgres tables are the store; a pull is a `data_pull` row; its manifest is the
   SHA-256 of a canonical CSV export (ordered by instrument and date) kept in `data_pull.export_sha256` and in a small
   `data/nse/manifests/pull-<id>.json` in the repo; CSV files per symbol are optional derived exports. Research code reads only through
   the discovery view and always names a `pull_id`; the holdout view is for the forward-test command (code-level lock plus a self-test).

## 2. Upstox: official V3 documentation, authentication, limits

4. Read the official page (M2 did on 2026-11-04): https://upstox.com/developer/api-documentation/v3/get-historical-candle-data
   Endpoint `GET https://api.upstox.com/v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}`; for NSE equities
   `instrument_key` = `NSE_EQ|<ISIN>` (URL-encode the pipe); daily is unit `days`, interval `1`; daily history exists from January 2000
   but ONE DECADE PER REQUEST at most, so chunk (2000-01-01 to 2009-12-31, 2010-01-01 to 2019-12-31, 2020-01-01 to the latest day);
   `data.candles` rows are [timestamp (ISO, +05:30), open, high, low, close, volume, open interest]; the rows may come newest first: sort
   ascending, drop duplicates by date, and check the chunk borders for overlaps and holes. Headers: `Authorization: Bearer <token>`,
   `Accept: application/json`. Minute data exists only from January 2022 (later phase).
5. Authentication IS required. The owner will generate Upstox's ANALYTICS TOKEN (read-only, valid one year, made once on the owner's
   Upstox Developer Apps page; market-data APIs including Historical Data work with it without a static IP) and save it in `.env` as
   `UPSTOX_ANALYTICS_TOKEN`. (The ordinary access token expires at 3:30 every morning: do not build around it; if you need a fallback
   read `UPSTOX_ACCESS_TOKEN`.) Never log or print the token; redact it in error messages. Ask the owner, through M2 as a file, when you
   need the token to be in place: the first live call comes after step 1.
6. Read Upstox's official rate-limit page and stay far below the limits: one request at a time, a pause between calls, exponential
   backoff on 429 and 5xx, resume without re-pulling finished symbols and chunks. About 30 symbols x 3 chunks = 100 calls.
7. Self-tests use canned HTTP responses (no network, no token). The first live use is ONE symbol (the first of the draw) to check
   the connection and the format: no statistic.

## 3. The AMFI file and the draw

8. The owner uploaded `docs/amfi/AverageMarketCapitalization30Jun2025.xlsx` (AMFI, average market capitalization, six months ended
   2025-06-30). M2's reader returns only binary for Excel files, so YOU convert it with code to
   `docs/amfi/AverageMarketCapitalization30Jun2025.csv` (every row and column of the sheet; one CSV per sheet if there are several) and
   write `docs/amfi/summary-30Jun2025.txt`: sheet names, the header row, the number of companies, the rank range, the unit of the market
   cap column, the average market cap at ranks 100, 101, 250 and 251, the columns present, the counts of missing NSE symbol or ISIN among
   ranks 101 to 250, duplicate ISINs, and the SHA-256 of the xlsx. Commit both. M2 verifies the file from them. Any free reader (openpyxl)
   is allowed.
9. The draw is by code, reproducible with ten lines of Python and no numpy: pool = AMFI rank 101 to 250 (the SEBI mid-cap band) with an
   NSE symbol and an ISIN, minus `universe/owner-exclusions.txt` if the owner committed one; order = ascending SHA-256 hex digest of the
   UTF-8 string `20250831|<ISIN>`. Write `universe/nse-midcap-draw-v1.csv` (draw_order, isin, nse_symbol, company, amfi_rank,
   average_market_cap, sha256). M2 recomputes the order independently from the CSV. Then Work Order 1.8 section 1 applies unchanged:
   first 30 in draw order that pass the data rule, every skip logged in `universe_member` with a reason, final list
   `universe/nse-midcap30-v1.csv` committed before any statistic exists.

## 4. Order of work

10. Step 1 now: schema and its self-tests, the Upstox client with canned responses, the AMFI converter and the draw, the cost and tax
    rules files and validators, the loader with the cutoff and holdout lock: all of it without a token and without a real pull. Deliver
    the AMFI CSV, the summary and the draw file in that delivery so M2 can verify. The rest of Work Order 1.8 stands.
