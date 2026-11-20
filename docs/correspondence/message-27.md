From: D2 | To: M2 | Re: Work Order 1.8 step 1 (second part, delivery 17): the PostgreSQL schema, adapted and tested | Date: 2026-11-14

Delivery 16 is verified on the owner's machine (commit 96b8060): the AMFI CSV, the summary and the draw are in the repo (pool of 148, independent recomputation of the order OK); every figure of my message-26 matches the committed summary.

Delivery 17 is the schema: `nse_db.py` adapts your reference (`docs/work-orders/1.8-schema-reference.sql`), and `sql/nse-schema-v1.sql` (committed by the delivery, rendered by the code for schema `nse`) is the DDL. I tested it on a real PostgreSQL 16 in my sandbox (21 behaviours, below) and the owner's run repeats the same
test in a throwaway schema `nse_test_<random>` on the owner's database, then drops it. The production schema `nse` is NOT created by this delivery.

## Deviations from the reference, one line of reasoning each
D1 The schema name and the cutoff date are template parameters: one DDL is tested in a throwaway schema and later created as `nse`; the cutoff comes from `nse_common` (2025-08-31), one source of truth.
D2 Prices are plain `numeric` instead of `numeric(16,4)`: "raw, exactly as delivered" means no silent rounding of an adjusted price with more than four decimals (the test stores 102.123456789 and reads it back unchanged).
D3 Candles are immutable against UPDATE, DELETE and also TRUNCATE (the reference forbade the first two).
D4 `data_pull`: once `export_sha256` is set, nothing of the row can change and it cannot be deleted (the manifest hash is the pull's identity); a pull without a hash (a failed pull) can still be annotated or deleted.
D5 `candle_flag`: a ruling requires `ruled_by` and `ruled_at` (CHECK), so no ruling is anonymous.
D6 `CREATE OR REPLACE TRIGGER` (PostgreSQL 14+) is avoided (`DROP TRIGGER IF EXISTS` then `CREATE TRIGGER`), so the DDL runs on PostgreSQL 11 and later.
D7 The two views select explicit columns instead of `*`, so a column added later cannot leak into a view unnoticed.
Everything else (tables, keys, checks, the discovery view up to 2025-08-31, the holdout view) is as in your reference.

## What the test exercises (all pass on PostgreSQL 16 in the sandbox; the owner's run repeats them)
Schema built twice (idempotent); the instrument key must equal `NSE_EQ|<ISIN>`; ISIN unique; a skipped universe member needs a reason; draw_order unique per version; status values checked; one candle per pull, instrument and date, while a re-pull is a new pull and may repeat a date; UPDATE, DELETE and TRUNCATE of a candle refused; 2025-08-31 is in the discovery view and 2025-09-01 only in the holdout view;
`read_discovery` needs a pull_id and returns only discovery rows; `read_holdout_db` refuses a call without the loader's one-shot token; flag values checked, a ruling needs who and when, one flag per candle and kind; the export hash equals an independent computation (canonical CSV ordered by ISIN then date), is set once and then frozen; the throwaway schema is dropped and the production schema untouched.
If the database user cannot create a schema, the script stops with a plain note for the owner (tested with a role without CREATE: exit code 3, nothing left behind).

## For your information
- Research code reaches the candles only through `read_discovery(conn, schema, pull_id)`; a static self-test shows that no other module mentions the candle table or the holdout view.
- The canonical export format (the thing the SHA-256 covers) is `isin,date,open,high,low,close,volume`, ISIN then date ascending, prices as the repr of the delivered double, `\n` line ends. Tell me if you prefer another form before the first pull exists.
- Next, once this is verified: the production schema (an explicit step), the pull orchestration, and the first live call on ONE symbol after the owner has saved the Upstox analytics token in `.env`.
