
CREATE SCHEMA IF NOT EXISTS nse;

CREATE TABLE IF NOT EXISTS nse.instrument (
    instrument_id     bigserial PRIMARY KEY,
    isin              text NOT NULL UNIQUE,
    nse_symbol        text,
    company           text NOT NULL,
    instrument_key    text NOT NULL UNIQUE,
    amfi_rank         integer,
    amfi_avg_mcap     numeric(24,4),
    first_candle_date date,
    CHECK (instrument_key = 'NSE_EQ|' || isin)
);

CREATE TABLE IF NOT EXISTS nse.universe_member (
    universe_version  text    NOT NULL,
    instrument_id     bigint  NOT NULL REFERENCES nse.instrument (instrument_id),
    draw_order        integer NOT NULL,
    status            text    NOT NULL CHECK (status IN ('candidate', 'selected', 'skipped')),
    reason            text,
    decided_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (universe_version, instrument_id),
    UNIQUE (universe_version, draw_order),
    CHECK (status <> 'skipped' OR reason IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS nse.data_pull (
    pull_id           bigserial PRIMARY KEY,
    pulled_at         timestamptz NOT NULL DEFAULT now(),
    source            text  NOT NULL,
    params            jsonb NOT NULL,
    export_sha256     text,
    note              text
);

CREATE TABLE IF NOT EXISTS nse.daily_candle (
    pull_id           bigint  NOT NULL REFERENCES nse.data_pull (pull_id),
    instrument_id     bigint  NOT NULL REFERENCES nse.instrument (instrument_id),
    trade_date        date    NOT NULL,
    open              numeric NOT NULL,
    high              numeric NOT NULL,
    low               numeric NOT NULL,
    close             numeric NOT NULL,
    volume            bigint  NOT NULL,
    PRIMARY KEY (pull_id, instrument_id, trade_date)
);
CREATE INDEX IF NOT EXISTS daily_candle_instrument_date ON nse.daily_candle (instrument_id, trade_date);

CREATE OR REPLACE FUNCTION nse.forbid_change() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    RAISE EXCEPTION '%.% is immutable: % is not allowed', TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP;
END;
$fn$;
DROP TRIGGER IF EXISTS daily_candle_immutable ON nse.daily_candle;
CREATE TRIGGER daily_candle_immutable BEFORE UPDATE OR DELETE ON nse.daily_candle
    FOR EACH ROW EXECUTE FUNCTION nse.forbid_change();
DROP TRIGGER IF EXISTS daily_candle_no_truncate ON nse.daily_candle;
CREATE TRIGGER daily_candle_no_truncate BEFORE TRUNCATE ON nse.daily_candle
    FOR EACH STATEMENT EXECUTE FUNCTION nse.forbid_change();

CREATE OR REPLACE FUNCTION nse.guard_pull() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF OLD.export_sha256 IS NOT NULL THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION '%.% row % has an export hash and cannot be deleted', TG_TABLE_SCHEMA, TG_TABLE_NAME, OLD.pull_id;
        END IF;
        IF NEW.export_sha256 IS DISTINCT FROM OLD.export_sha256 OR NEW.params::text IS DISTINCT FROM OLD.params::text
           OR NEW.source IS DISTINCT FROM OLD.source OR NEW.pulled_at IS DISTINCT FROM OLD.pulled_at THEN
            RAISE EXCEPTION '%.% row % has an export hash: it cannot be changed', TG_TABLE_SCHEMA, TG_TABLE_NAME, OLD.pull_id;
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$fn$;
DROP TRIGGER IF EXISTS data_pull_guard ON nse.data_pull;
CREATE TRIGGER data_pull_guard BEFORE UPDATE OR DELETE ON nse.data_pull
    FOR EACH ROW EXECUTE FUNCTION nse.guard_pull();

CREATE TABLE IF NOT EXISTS nse.candle_flag (
    flag_id           bigserial PRIMARY KEY,
    pull_id           bigint  NOT NULL REFERENCES nse.data_pull (pull_id),
    instrument_id     bigint  NOT NULL REFERENCES nse.instrument (instrument_id),
    trade_date        date    NOT NULL,
    flag              text    NOT NULL CHECK (flag IN ('zero_volume', 'jump', 'ohlc_inconsistent', 'missing_day', 'duplicate_date', 'non_monotone_date')),
    value             numeric,
    ruling            text CHECK (ruling IN ('genuine', 'unadjusted_event', 'unresolved')),
    ruled_by          text,
    ruled_at          timestamptz,
    note              text,
    UNIQUE (pull_id, instrument_id, trade_date, flag),
    CHECK (ruling IS NULL OR (ruled_by IS NOT NULL AND ruled_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS nse.trading_calendar (
    pull_id           bigint  NOT NULL REFERENCES nse.data_pull (pull_id),
    trade_date        date    NOT NULL,
    n_symbols         integer NOT NULL,
    is_trading_day    boolean NOT NULL,
    PRIMARY KEY (pull_id, trade_date)
);

CREATE OR REPLACE VIEW nse.daily_candle_discovery AS
    SELECT pull_id, instrument_id, trade_date, open, high, low, close, volume FROM nse.daily_candle WHERE trade_date <= DATE '2025-08-31';
CREATE OR REPLACE VIEW nse.daily_candle_holdout AS
    SELECT pull_id, instrument_id, trade_date, open, high, low, close, volume FROM nse.daily_candle WHERE trade_date > DATE '2025-08-31';

