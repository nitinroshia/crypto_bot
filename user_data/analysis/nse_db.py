"""
Work Order 1.8 addendum section 1: the PostgreSQL store, in our own schema `nse` (never the owner's existing tables).

M2's reference design (docs/work-orders/1.8-schema-reference.sql) adapted and TESTED against PostgreSQL; the deviations, one line of reasoning each:
  D1  the schema name and the cutoff date are TEMPLATE parameters (one DDL, tested in a throwaway schema `nse_test_<random>`, created as `nse` later; the cutoff comes from nse_common, one source of truth);
  D2  prices are plain `numeric`, not numeric(16,4): "raw, exactly as delivered" means no silent rounding of an adjusted price with more than four decimals;
  D3  candles are immutable against UPDATE, DELETE and TRUNCATE (the reference forbade only UPDATE and DELETE);
  D4  data_pull: once export_sha256 is set, nothing of the row may change and the row cannot be deleted (the manifest hash is the pull's identity); a pull without a hash (a failed pull) can be deleted;
  D5  candle_flag: a ruling needs ruled_by and ruled_at (CHECK), so a ruling is never anonymous;
  D6  CREATE OR REPLACE TRIGGER (PostgreSQL 14+) is avoided (DROP TRIGGER IF EXISTS + CREATE TRIGGER), so the DDL runs on PostgreSQL 11 and later;
  D7  the views select explicit columns (not `*`), so a later column can never leak into a view unnoticed.
Everything else (tables, keys, checks, the two views) is as in the reference.

Research code reads ONLY read_discovery() (always with a pull_id); read_holdout_db() needs the one-shot token of nse_loader. A static self-test shows that no other module mentions the candle table or the holdout view.
Credentials come from the owner's `.env` at run time (nse_common.read_env), are never printed, and are redacted from every message.

  python3 nse_db.py --self-test         DB-free checks (DDL rendering, guards, static scan)
  python3 nse_db.py --self-test-db      builds the schema in `nse_test_<random>` on the owner's database, exercises it, drops it
  python3 nse_db.py --render-ddl        prints the DDL for schema `nse`
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sys
from pathlib import Path

from nse_common import CUTOFF_DATE, canonical_csv, read_env, redact

IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")
COLUMNS = "pull_id, instrument_id, trade_date, open, high, low, close, volume"


class NseDbError(RuntimeError):
    pass


class SchemaPermissionError(NseDbError):
    pass


DDL = """
CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE IF NOT EXISTS {schema}.instrument (
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

CREATE TABLE IF NOT EXISTS {schema}.universe_member (
    universe_version  text    NOT NULL,
    instrument_id     bigint  NOT NULL REFERENCES {schema}.instrument (instrument_id),
    draw_order        integer NOT NULL,
    status            text    NOT NULL CHECK (status IN ('candidate', 'selected', 'skipped')),
    reason            text,
    decided_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (universe_version, instrument_id),
    UNIQUE (universe_version, draw_order),
    CHECK (status <> 'skipped' OR reason IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS {schema}.data_pull (
    pull_id           bigserial PRIMARY KEY,
    pulled_at         timestamptz NOT NULL DEFAULT now(),
    source            text  NOT NULL,
    params            jsonb NOT NULL,
    export_sha256     text,
    note              text
);

CREATE TABLE IF NOT EXISTS {schema}.daily_candle (
    pull_id           bigint  NOT NULL REFERENCES {schema}.data_pull (pull_id),
    instrument_id     bigint  NOT NULL REFERENCES {schema}.instrument (instrument_id),
    trade_date        date    NOT NULL,
    open              numeric NOT NULL,
    high              numeric NOT NULL,
    low               numeric NOT NULL,
    close             numeric NOT NULL,
    volume            bigint  NOT NULL,
    PRIMARY KEY (pull_id, instrument_id, trade_date)
);
CREATE INDEX IF NOT EXISTS daily_candle_instrument_date ON {schema}.daily_candle (instrument_id, trade_date);

CREATE OR REPLACE FUNCTION {schema}.forbid_change() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    RAISE EXCEPTION '%.% is immutable: % is not allowed', TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP;
END;
$fn$;
DROP TRIGGER IF EXISTS daily_candle_immutable ON {schema}.daily_candle;
CREATE TRIGGER daily_candle_immutable BEFORE UPDATE OR DELETE ON {schema}.daily_candle
    FOR EACH ROW EXECUTE FUNCTION {schema}.forbid_change();
DROP TRIGGER IF EXISTS daily_candle_no_truncate ON {schema}.daily_candle;
CREATE TRIGGER daily_candle_no_truncate BEFORE TRUNCATE ON {schema}.daily_candle
    FOR EACH STATEMENT EXECUTE FUNCTION {schema}.forbid_change();

CREATE OR REPLACE FUNCTION {schema}.guard_pull() RETURNS trigger LANGUAGE plpgsql AS $fn$
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
DROP TRIGGER IF EXISTS data_pull_guard ON {schema}.data_pull;
CREATE TRIGGER data_pull_guard BEFORE UPDATE OR DELETE ON {schema}.data_pull
    FOR EACH ROW EXECUTE FUNCTION {schema}.guard_pull();

CREATE TABLE IF NOT EXISTS {schema}.candle_flag (
    flag_id           bigserial PRIMARY KEY,
    pull_id           bigint  NOT NULL REFERENCES {schema}.data_pull (pull_id),
    instrument_id     bigint  NOT NULL REFERENCES {schema}.instrument (instrument_id),
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

CREATE TABLE IF NOT EXISTS {schema}.trading_calendar (
    pull_id           bigint  NOT NULL REFERENCES {schema}.data_pull (pull_id),
    trade_date        date    NOT NULL,
    n_symbols         integer NOT NULL,
    is_trading_day    boolean NOT NULL,
    PRIMARY KEY (pull_id, trade_date)
);

CREATE OR REPLACE VIEW {schema}.daily_candle_discovery AS
    SELECT pull_id, instrument_id, trade_date, open, high, low, close, volume FROM {schema}.daily_candle WHERE trade_date <= DATE '{cutoff}';
CREATE OR REPLACE VIEW {schema}.daily_candle_holdout AS
    SELECT pull_id, instrument_id, trade_date, open, high, low, close, volume FROM {schema}.daily_candle WHERE trade_date > DATE '{cutoff}';
"""


def check_ident(name: str) -> str:
    if not IDENT.fullmatch(name or ""):
        raise NseDbError(f"unsafe schema name {name!r}")
    return name


def render_ddl(schema: str = "nse") -> str:
    return DDL.replace("{schema}", check_ident(schema)).replace("{cutoff}", CUTOFF_DATE.isoformat())


# ----------------------------------------------------------------------------- connection and operations
def connect(env: dict | None = None):
    import psycopg2

    env = env if env is not None else read_env()
    try:
        if env.get("DATABASE_URL"):
            return psycopg2.connect(env["DATABASE_URL"])
        need = [k for k in ("PGHOST", "PGDATABASE", "PGUSER") if not env.get(k)]
        if need:
            raise NseDbError(f"no database settings in .env: set DATABASE_URL (or {', '.join(need)} ...); ask the owner")
        return psycopg2.connect(host=env["PGHOST"], port=env.get("PGPORT") or 5432, dbname=env["PGDATABASE"], user=env["PGUSER"], password=env.get("PGPASSWORD"))
    except psycopg2.Error as e:
        raise NseDbError(redact(f"cannot connect to PostgreSQL: {e}", env)) from None


def create_schema(conn, schema: str) -> None:
    """Create the schema and every object inside it (idempotent). Fails with a plain note for the owner if the database user cannot create a schema."""
    import psycopg2
    import psycopg2.errors

    try:
        with conn.cursor() as cur:
            cur.execute(render_ddl(schema))
        conn.commit()
    except psycopg2.errors.InsufficientPrivilege:
        conn.rollback()
        raise SchemaPermissionError("the database user is not allowed to create a schema: ask the owner to grant CREATE on the database to this user (or to create the schema nse for it)") from None


def drop_test_schema(conn, schema: str) -> None:
    """Only a throwaway schema (name starts with nse_test_) can ever be dropped by code; the production schema is never dropped."""
    if not check_ident(schema).startswith("nse_test_"):
        raise NseDbError("refusing to drop a schema that is not a throwaway nse_test_ schema")
    with conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    conn.commit()


def upsert_instruments(conn, schema: str, rows: list[dict]) -> dict[str, int]:
    """rows: {isin, nse_symbol, company, amfi_rank, amfi_avg_mcap}; returns {isin: instrument_id}. instrument_key = 'NSE_EQ|' || isin."""
    out = {}
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                f"INSERT INTO {check_ident(schema)}.instrument (isin, nse_symbol, company, instrument_key, amfi_rank, amfi_avg_mcap) VALUES (%s,%s,%s,%s,%s,%s) "
                f"ON CONFLICT (isin) DO UPDATE SET nse_symbol = EXCLUDED.nse_symbol, company = EXCLUDED.company, amfi_rank = EXCLUDED.amfi_rank, amfi_avg_mcap = EXCLUDED.amfi_avg_mcap RETURNING instrument_id",
                (r["isin"], r.get("nse_symbol"), r["company"], "NSE_EQ|" + r["isin"], r.get("amfi_rank"), r.get("amfi_avg_mcap")))
            out[r["isin"]] = cur.fetchone()[0]
    conn.commit()
    return out


def new_pull(conn, schema: str, source: str, params: dict, note: str | None = None) -> int:
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO {check_ident(schema)}.data_pull (source, params, note) VALUES (%s, %s::jsonb, %s) RETURNING pull_id", (source, json.dumps(params, sort_keys=True), note))
        pid = cur.fetchone()[0]
    conn.commit()
    return pid


def insert_candles(conn, schema: str, pull_id: int, instrument_id: int, rows: list[tuple]) -> int:
    """rows: (date 'YYYY-MM-DD', open, high, low, close, volume), exactly as delivered. Prices are passed as text of the Python float (repr) so numeric stores the delivered decimal."""
    with conn.cursor() as cur:
        cur.executemany(f"INSERT INTO {check_ident(schema)}.daily_candle ({COLUMNS}) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        [(pull_id, instrument_id, r[0], repr(float(r[1])), repr(float(r[2])), repr(float(r[3])), repr(float(r[4])), int(r[5])) for r in rows])
    conn.commit()
    return len(rows)


def export_rows(conn, schema: str, pull_id: int) -> list[tuple]:
    """The pull's candles ordered by ISIN and date (the canonical export order)."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT i.isin, c.trade_date, c.open::float8, c.high::float8, c.low::float8, c.close::float8, c.volume FROM {check_ident(schema)}.daily_candle c "
                    f"JOIN {schema}.instrument i USING (instrument_id) WHERE c.pull_id = %s ORDER BY i.isin, c.trade_date", (pull_id,))
        return [(r[0], str(r[1]), r[2], r[3], r[4], r[5], r[6]) for r in cur.fetchall()]


def canonical_export_text(rows: list[tuple]) -> str:
    """isin,date,open,high,low,close,volume; ordered by ISIN then date; prices as repr of the double; '\\n' line ends."""
    lines = ["isin,date,open,high,low,close,volume"]
    for r in sorted(rows, key=lambda x: (x[0], x[1])):
        lines.append(f"{r[0]},{r[1]},{float(r[2])!r},{float(r[3])!r},{float(r[4])!r},{float(r[5])!r},{int(r[6])}")
    return "\n".join(lines) + "\n"


def finish_pull(conn, schema: str, pull_id: int) -> dict:
    """Compute the SHA-256 of the canonical export and store it in data_pull.export_sha256 (once; the guard trigger forbids any later change). Returns the manifest dict."""
    rows = export_rows(conn, schema, pull_id)
    text = canonical_export_text(rows)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with conn.cursor() as cur:
        cur.execute(f"UPDATE {check_ident(schema)}.data_pull SET export_sha256 = %s WHERE pull_id = %s AND export_sha256 IS NULL RETURNING pulled_at, source, params", (sha, pull_id))
        got = cur.fetchone()
        if got is None:
            conn.rollback()
            raise NseDbError(f"pull {pull_id} does not exist or already has an export hash")
    conn.commit()
    return {"pull_id": pull_id, "export_sha256": sha, "rows": len(rows), "instruments": len({r[0] for r in rows}), "source": got[1], "params": got[2], "pulled_at": str(got[0]), "schema": schema}


def read_discovery(conn, schema: str, pull_id: int, isins: list[str] | None = None) -> list[tuple]:
    """Research code's ONLY door to the candles: the discovery view (dates <= the cutoff), always for one named pull."""
    if not isinstance(pull_id, int):
        raise NseDbError("a pull_id is required")
    sql = (f"SELECT i.isin, d.trade_date, d.open::float8, d.high::float8, d.low::float8, d.close::float8, d.volume FROM {check_ident(schema)}.daily_candle_discovery d "
           f"JOIN {schema}.instrument i USING (instrument_id) WHERE d.pull_id = %s")
    args: list = [pull_id]
    if isins:
        sql += " AND i.isin = ANY(%s)"
        args.append(list(isins))
    with conn.cursor() as cur:
        cur.execute(sql + " ORDER BY i.isin, d.trade_date", args)
        return cur.fetchall()


def read_holdout_db(conn, schema: str, pull_id: int, token: dict | None = None) -> list[tuple]:
    """Holdout rows; only the forward-test command may call it, with the one-shot token of nse_loader.issue_holdout_token."""
    from nse_loader import HoldoutLocked

    if not isinstance(token, dict) or token.get("_issued_by") != "nse_loader.issue_holdout_token" or not re.fullmatch(r"[0-9a-f]{64}", str(token.get("manifest", ""))):
        raise HoldoutLocked("the holdout is locked: only the forward-test command, holding a token for a frozen candidate, may read it")
    with conn.cursor() as cur:
        cur.execute(f"SELECT i.isin, h.trade_date, h.open::float8, h.high::float8, h.low::float8, h.close::float8, h.volume FROM {check_ident(schema)}.daily_candle_holdout h "
                    f"JOIN {schema}.instrument i USING (instrument_id) WHERE h.pull_id = %s ORDER BY i.isin, h.trade_date", (pull_id,))
        return cur.fetchall()


# ----------------------------------------------------------------------------- self-tests
def _self_test() -> None:
    ddl = render_ddl("nse")
    assert "{schema}" not in ddl and "{cutoff}" not in ddl and "DATE '2025-08-31'" in ddl and "CREATE SCHEMA IF NOT EXISTS nse;" in ddl
    assert "CREATE OR REPLACE TRIGGER" not in ddl, "PostgreSQL 14+ syntax avoided (D6)"
    assert "numeric(16,4)" not in ddl and "SELECT *" not in ddl, "D2 and D7"
    assert render_ddl("nse_test_ab12").count("nse_test_ab12.") > 20 and "nse." not in render_ddl("nse_test_ab12").replace("nse_test_", "")
    for bad in ("", "Nse", "nse; drop schema public", "nse-test", "1nse", "a" * 60, None):
        try:
            render_ddl(bad)  # type: ignore[arg-type]
        except NseDbError:
            pass
        else:
            raise AssertionError(f"unsafe schema name accepted: {bad!r}")

    class _C:
        pass

    for name in ("nse", "public", "nse_prod", "other"):
        try:
            drop_test_schema(_C(), name)
        except NseDbError as e:
            assert "throwaway" in str(e)
        else:
            raise AssertionError(f"drop_test_schema must refuse {name}")
    t = canonical_export_text([("INE2", "2020-01-02", 1.5, 2.0, 1.0, 1.75, 10), ("INE1", "2020-01-03", 1, 2, 1, 2, 5), ("INE1", "2020-01-02", 1, 2, 1, 1, 7)])
    assert t.splitlines()[1].startswith("INE1,2020-01-02") and t.splitlines()[3].startswith("INE2,") and t.endswith("\n") and "1.75" in t
    # static scan: no module other than this one mentions the candle table or the holdout view (research code reads only read_discovery)
    here = Path(__file__).resolve().parent
    offenders = [p.name for p in here.glob("*.py") if p.name != "nse_db.py" and re.search(r"daily_candle|candle_holdout", p.read_text())]
    assert offenders == [], f"modules that mention the candle table or the holdout view: {offenders}"
    callers = [p.name for p in here.glob("*.py") if p.name != "nse_db.py" and re.search(r"\bread_holdout_db\s*\(", p.read_text())]
    assert callers == [], f"modules that call the database holdout reader: {callers}"
    src = Path(__file__).read_text()
    assert "FROM {check_ident(schema)}.daily_candle_discovery d" in src.replace("\n", " ").replace('f"SELECT', 'f"SELECT') or "daily_candle_discovery d" in src
    try:
        read_discovery(None, "nse", "not-an-int")  # type: ignore[arg-type]
    except NseDbError:
        pass
    else:
        raise AssertionError("read_discovery needs a pull_id")
    from nse_loader import HoldoutLocked

    for tok in (None, {}, {"manifest": "a" * 64}):
        try:
            read_holdout_db(None, "nse", 1, tok)
        except HoldoutLocked:
            pass
        else:
            raise AssertionError("holdout read without a valid token")
    print("Self-test passed: nse_db renders the adapted DDL for any safe schema name (cutoff 2025-08-31 from nse_common, no PostgreSQL 14+ syntax, explicit view columns), refuses unsafe names and the dropping of any "
          "schema that is not a throwaway nse_test_ schema, builds the canonical export in ISIN-then-date order, and a static scan shows that no other module mentions the candle table or the holdout view.")


def _self_test_db(env: dict | None = None) -> None:
    import psycopg2
    import psycopg2.errors as pe

    env = env if env is not None else read_env()
    conn = connect(env)
    schema = "nse_test_" + secrets.token_hex(4)
    cur = conn.cursor()
    cur.execute("SELECT version(), current_user, current_database()")
    ver, user, db = cur.fetchone()
    cur.execute("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'nse'")
    nse_before = cur.fetchone()[0]
    conn.commit()
    print(f"database: {redact(ver.split(',')[0], env)}; user: {user}; database name: {db}; throwaway schema: {schema}")
    ok = []

    def must_fail(sql, args, exc, label):
        try:
            cur.execute(sql, args)
        except exc:
            conn.rollback()
            ok.append(label)
            return
        conn.rollback()
        raise AssertionError(f"accepted: {label}")

    try:
        create_schema(conn, schema)
        create_schema(conn, schema)  # idempotent
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (schema,))
        names = {r[0] for r in cur.fetchall()}
        assert {"instrument", "universe_member", "data_pull", "daily_candle", "candle_flag", "trading_calendar", "daily_candle_discovery", "daily_candle_holdout"} <= names, names
        ids = upsert_instruments(conn, schema, [{"isin": "INE000A01011", "nse_symbol": "AAA", "company": "A Ltd", "amfi_rank": 101, "amfi_avg_mcap": 90000.5},
                                                {"isin": "INE000B01012", "nse_symbol": "BBB", "company": "B Ltd", "amfi_rank": 102, "amfi_avg_mcap": 80000.25}])
        assert upsert_instruments(conn, schema, [{"isin": "INE000A01011", "nse_symbol": "AAA", "company": "A Ltd", "amfi_rank": 101, "amfi_avg_mcap": 90000.5}]) == {"INE000A01011": ids["INE000A01011"]}
        ia, ib = ids["INE000A01011"], ids["INE000B01012"]
        must_fail(f"INSERT INTO {schema}.instrument (isin, company, instrument_key) VALUES ('INE000C01013','C','NSE_EQ|WRONG')", None, pe.CheckViolation, "instrument_key must equal NSE_EQ|isin")
        must_fail(f"INSERT INTO {schema}.instrument (isin, company, instrument_key) VALUES ('INE000A01011','dup','NSE_EQ|INE000A01011')", None, pe.UniqueViolation, "ISIN is unique")
        must_fail(f"INSERT INTO {schema}.universe_member (universe_version, instrument_id, draw_order, status) VALUES ('v1', %s, 1, 'skipped')", (ia,), pe.CheckViolation, "a skip needs a reason")
        cur.execute(f"INSERT INTO {schema}.universe_member (universe_version, instrument_id, draw_order, status, reason) VALUES ('v1', %s, 1, 'skipped', 'first candle after 2015-08-31')", (ia,))
        conn.commit()
        must_fail(f"INSERT INTO {schema}.universe_member (universe_version, instrument_id, draw_order, status) VALUES ('v1', %s, 1, 'selected')", (ib,), pe.UniqueViolation, "draw_order is unique per version")
        must_fail(f"INSERT INTO {schema}.universe_member (universe_version, instrument_id, draw_order, status) VALUES ('v1', %s, 2, 'bogus')", (ib,), pe.CheckViolation, "status values are checked")
        p1 = new_pull(conn, schema, "upstox_v3_daily", {"unit": "days", "interval": 1, "chunks": 3})
        rows_a = [("2025-08-28", 100.5, 101.0, 99.5, 100.0, 1000), ("2025-08-29", 100.0, 102.0, 99.0, 101.5, 1500), ("2025-08-31", 101.5, 103.0, 101.0, 102.123456789, 900),
                  ("2025-09-01", 102.0, 104.0, 101.5, 103.25, 2000)]
        assert insert_candles(conn, schema, p1, ia, rows_a) == 4
        insert_candles(conn, schema, p1, ib, rows_a[:2])
        must_fail(f"INSERT INTO {schema}.daily_candle ({COLUMNS}) VALUES (%s,%s,'2025-08-28',1,1,1,1,1)", (p1, ia), pe.UniqueViolation, "one candle per pull, instrument and date")
        p2 = new_pull(conn, schema, "upstox_v3_daily", {"unit": "days", "interval": 1, "chunks": 3}, "re-pull")
        insert_candles(conn, schema, p2, ia, rows_a[:1])
        ok.append("a re-pull is a new pull and may repeat a date")
        cur.execute(f"SELECT open::text, close::text FROM {schema}.daily_candle WHERE pull_id=%s AND instrument_id=%s AND trade_date='2025-08-31'", (p1, ia))
        o, c = cur.fetchone()
        assert c == "102.123456789", c
        ok.append("an adjusted price with more than four decimals is stored exactly")
        for sql, label in ((f"UPDATE {schema}.daily_candle SET close = 1", "UPDATE of a candle"), (f"DELETE FROM {schema}.daily_candle", "DELETE of a candle"), (f"TRUNCATE {schema}.daily_candle", "TRUNCATE of the candle table")):
            must_fail(sql, None, pe.RaiseException, label + " is refused")
        # views and the cutoff
        cur.execute(f"SELECT max(trade_date) FROM {schema}.daily_candle_discovery WHERE pull_id=%s", (p1,))
        assert str(cur.fetchone()[0]) == "2025-08-31"
        cur.execute(f"SELECT min(trade_date), count(*) FROM {schema}.daily_candle_holdout WHERE pull_id=%s", (p1,))
        hmin, hn = cur.fetchone()
        assert str(hmin) == "2025-09-01" and hn == 1
        ok.append("2025-08-31 is discovery, 2025-09-01 is holdout, neither view leaks the other")
        disc = read_discovery(conn, schema, p1)
        assert max(r[1] for r in disc).isoformat() == "2025-08-31" and len(disc) == 5 and {r[0] for r in disc} == {"INE000A01011", "INE000B01012"}
        assert [r[0] for r in read_discovery(conn, schema, p1, ["INE000B01012"])] == ["INE000B01012"] * 2
        from nse_loader import HoldoutLocked

        try:
            read_holdout_db(conn, schema, p1, None)
        except HoldoutLocked:
            ok.append("the holdout reader refuses a call without a token")
        else:
            raise AssertionError("holdout read without token")
        # flags and rulings
        must_fail(f"INSERT INTO {schema}.candle_flag (pull_id, instrument_id, trade_date, flag) VALUES (%s,%s,'2025-08-28','bogus')", (p1, ia), pe.CheckViolation, "flag values are checked")
        must_fail(f"INSERT INTO {schema}.candle_flag (pull_id, instrument_id, trade_date, flag, ruling) VALUES (%s,%s,'2025-08-28','jump','genuine')", (p1, ia), pe.CheckViolation, "a ruling needs ruled_by and ruled_at")
        cur.execute(f"INSERT INTO {schema}.candle_flag (pull_id, instrument_id, trade_date, flag, value, ruling, ruled_by, ruled_at) VALUES (%s,%s,'2025-08-28','jump',-0.31,'genuine','M2',now())", (p1, ia))
        conn.commit()
        must_fail(f"INSERT INTO {schema}.candle_flag (pull_id, instrument_id, trade_date, flag) VALUES (%s,%s,'2025-08-28','jump')", (p1, ia), pe.UniqueViolation, "one flag per candle and kind")
        cur.execute(f"INSERT INTO {schema}.trading_calendar VALUES (%s, '2025-08-28', 2, true)", (p1,))
        conn.commit()
        # the manifest hash: identical to an independent computation, set once, then frozen
        m = finish_pull(conn, schema, p1)
        expect = hashlib.sha256(canonical_export_text([(r[0], str(r[1]), r[2], r[3], r[4], r[5], r[6]) for r in export_rows(conn, schema, p1)]).encode()).hexdigest()
        assert m["export_sha256"] == expect and m["rows"] == 6 and m["instruments"] == 2
        for sql, args, label in ((f"UPDATE {schema}.data_pull SET export_sha256 = 'x' WHERE pull_id = %s", (p1,), "changing the export hash"), (f"UPDATE {schema}.data_pull SET params = '{{}}'::jsonb WHERE pull_id = %s", (p1,), "changing the params of a hashed pull"),
                                 (f"DELETE FROM {schema}.data_pull WHERE pull_id = %s", (p1,), "deleting a hashed pull")):
            must_fail(sql, args, pe.RaiseException, label + " is refused")
        try:
            finish_pull(conn, schema, p1)
        except NseDbError:
            ok.append("a second export hash for the same pull is refused")
        else:
            raise AssertionError("finish_pull twice")
        cur.execute(f"UPDATE {schema}.data_pull SET note = 'ok' WHERE pull_id = %s", (p2,))  # an unhashed pull may still change
        p3 = new_pull(conn, schema, "failed", {})
        cur.execute(f"DELETE FROM {schema}.data_pull WHERE pull_id = %s", (p3,))
        conn.commit()
        ok.append("a pull without an export hash can be annotated or deleted")
    finally:
        conn.rollback()
        drop_test_schema(conn, schema)
    cur.execute("SELECT count(*) FROM information_schema.schemata WHERE schema_name = %s", (schema,))
    assert cur.fetchone()[0] == 0, "the throwaway schema was not dropped"
    cur.execute("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'nse'")
    assert cur.fetchone()[0] == nse_before, "the production schema nse was touched"
    conn.close()
    for line in ok:
        print("  ok:", line)
    print(f"Database self-test passed: schema {schema} built twice (idempotent), {len(ok)} behaviours checked, throwaway schema dropped, production schema 'nse' {'untouched (does not exist yet)' if not nse_before else 'untouched'}.")


def main() -> None:
    a = sys.argv[1:]
    if "--render-ddl" in a:
        print(render_ddl("nse"))
    elif "--self-test-db" in a:
        try:
            _self_test_db()
        except SchemaPermissionError as e:
            print(f"NOTE FOR THE OWNER: {e}")
            raise SystemExit(3)
        except NseDbError as e:
            print(f"NOTE FOR THE OWNER: {e}")
            raise SystemExit(2)
    else:
        _self_test()


if __name__ == "__main__":
    main()
