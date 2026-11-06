-- Work Order 1.8: reference PostgreSQL schema for the NSE panel (M2, 2026-11-04).
-- REFERENCE ONLY. M2 could not run it on PostgreSQL (no database in M2's sandbox): D2 adapts it, tests it in a throwaway schema
-- on the owner's machine, and keeps what works; every deviation gets a one-line reason in the report. Needs PostgreSQL 11 or later.
-- Everything lives in the new schema "nse": no object of the owner's existing tables is touched.
-- Credentials are never in this file or in any script: they come from the owner's .env at run time.

CREATE SCHEMA IF NOT EXISTS nse;

-- One row per company (ISIN is the key; Upstox's instrument_key for NSE equities is 'NSE_EQ|' || isin).
CREATE TABLE IF NOT EXISTS nse.instrument (
    instrument_id     bigserial PRIMARY KEY,
    isin              text NOT NULL UNIQUE,
    nse_symbol        text,
    company           text NOT NULL,
    instrument_key    text NOT NULL UNIQUE,
    amfi_rank         integer,            -- rank in the AMFI list for the six months ended 2025-06-30
    amfi_avg_mcap     numeric(24,4),      -- as in the file (the unit is stated in docs/amfi/summary-30Jun2025.txt)
    first_candle_date date,               -- filled from the data after a pull
    CHECK (instrument_key = 'NSE_EQ|' || isin)
);

-- The seeded draw and what happened to each company (no hand picking: every skip has a reason).
CREATE TABLE IF NOT EXISTS nse.universe_member (
    universe_version  text    NOT NULL,   -- e.g. 'nse-midcap30-v1'
    instrument_id     bigint  NOT NULL REFERENCES nse.instrument (instrument_id),
    draw_order        integer NOT NULL,   -- 1 = first in ascending SHA-256 of '20250831|<ISIN>'
    status            text    NOT NULL CHECK (status IN ('candidate', 'selected', 'skipped')),
    reason            text,
    decided_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (universe_version, instrument_id),
    UNIQUE (universe_version, draw_order),
    CHECK (status <> 'skipped' OR reason IS NOT NULL)
);

-- One row per pull. A re-pull is a new row; candles are never overwritten (Upstox re-adjusts history over time).
CREATE TABLE IF NOT EXISTS nse.data_pull (
    pull_id           bigserial PRIMARY KEY,
    pulled_at         timestamptz NOT NULL DEFAULT now(),
    source            text  NOT NULL,     -- 'upstox_v3_daily'
    params            jsonb NOT NULL,     -- unit, interval, date range, chunking, client version
    export_sha256     text,               -- SHA-256 of the canonical CSV export of this pull, filled when the pull is complete
    note              text
);

-- Daily candles exactly as delivered (raw). No masking, no adjustment, no CHECK on OHLC consistency:
-- inconsistencies are stored and then flagged in nse.candle_flag by the validation step.
CREATE TABLE IF NOT EXISTS nse.daily_candle (
    pull_id           bigint  NOT NULL REFERENCES nse.data_pull (pull_id),
    instrument_id     bigint  NOT NULL REFERENCES nse.instrument (instrument_id),
    trade_date        date    NOT NULL,   -- the IST trading date (Upstox: timestamp at 00:00+05:30)
    open              numeric(16,4) NOT NULL,
    high              numeric(16,4) NOT NULL,
    low               numeric(16,4) NOT NULL,
    close             numeric(16,4) NOT NULL,
    volume            bigint  NOT NULL,
    PRIMARY KEY (pull_id, instrument_id, trade_date)
);
CREATE INDEX IF NOT EXISTS daily_candle_instrument_date ON nse.daily_candle (instrument_id, trade_date);

-- Candles are immutable once inserted.
CREATE OR REPLACE FUNCTION nse.forbid_change() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    RAISE EXCEPTION 'nse.% is immutable: % is not allowed', TG_TABLE_NAME, TG_OP;
END;
$fn$;
DROP TRIGGER IF EXISTS daily_candle_immutable ON nse.daily_candle;
CREATE TRIGGER daily_candle_immutable BEFORE UPDATE OR DELETE ON nse.daily_candle
    FOR EACH ROW EXECUTE FUNCTION nse.forbid_change();

-- Validation flags (descriptive) and M2's ruling per flag. An unresolved jump excludes the symbol; a genuine crash is never masked.
CREATE TABLE IF NOT EXISTS nse.candle_flag (
    flag_id           bigserial PRIMARY KEY,
    pull_id           bigint  NOT NULL REFERENCES nse.data_pull (pull_id),
    instrument_id     bigint  NOT NULL REFERENCES nse.instrument (instrument_id),
    trade_date        date    NOT NULL,
    flag              text    NOT NULL CHECK (flag IN ('zero_volume', 'jump', 'ohlc_inconsistent', 'missing_day', 'duplicate_date', 'non_monotone_date')),
    value             numeric,            -- e.g. the daily return of a jump
    ruling            text CHECK (ruling IN ('genuine', 'unadjusted_event', 'unresolved')),
    ruled_by          text,
    ruled_at          timestamptz,
    note              text,
    UNIQUE (pull_id, instrument_id, trade_date, flag)
);

-- The trading calendar of a pull: a date counts when at least half of the pulled symbols have a candle.
CREATE TABLE IF NOT EXISTS nse.trading_calendar (
    pull_id           bigint  NOT NULL REFERENCES nse.data_pull (pull_id),
    trade_date        date    NOT NULL,
    n_symbols         integer NOT NULL,
    is_trading_day    boolean NOT NULL,
    PRIMARY KEY (pull_id, trade_date)
);

-- Cutoff and holdout. Research code reads ONLY the discovery view (always with a pull_id); the holdout view is read only by the
-- forward-test command. A self-test must show that no research module selects from nse.daily_candle or the holdout view.
CREATE OR REPLACE VIEW nse.daily_candle_discovery AS
    SELECT * FROM nse.daily_candle WHERE trade_date <= DATE '2025-08-31';
CREATE OR REPLACE VIEW nse.daily_candle_holdout AS
    SELECT * FROM nse.daily_candle WHERE trade_date > DATE '2025-08-31';
