"""
Raw Binance kline downloader (work order #1, Task 0) + exchange filters.

Why this exists: freqtrade's download-data keeps only OHLCV. Work order #1
also needs, per bar, the number of trades and the taker-buy volumes
(order-flow / "was anyone actually trading" measures), and it needs
ETH/USDT and FDUSD/USDT alongside ETH/FDUSD. This script pulls the full
12-field kline from Binance's public market-data REST API (no API key) and
stores it as feather files in a SEPARATE raw store
(default user_data/data/binance_raw/), same PAIR-timeframe.feather naming as
freqtrade's files:

    date, open, high, low, close, volume, quote_volume, n_trades,
    taker_buy_base, taker_buy_quote

It is kept apart from user_data/data/binance/ on purpose: freqtrade assigns
its six standard column names when it reads a feather file, so a file with
extra columns would break it if freqtrade found one. databundle.py reads
from both places (see its docstring).

What is stored is exactly what Binance returned: NO gap filling. Binance
does not always emit a kline for a minute with zero trades, so missing rows
are meaningful; task0_report.py counts them and compares against the
freqtrade files.

Default jobs (built from the span of your local ETH_FDUSD files, so nothing
is hard-coded to a date):
    ETHFDUSD  1m   same span as the local ETH_FDUSD-1m file  (adds n_trades / taker_buy_*)
    ETHUSDT   1m   same span as local ETH_FDUSD-1m
    ETHUSDT   5m   same span as local ETH_FDUSD-5m (falls back to the 1m span)
    ETHUSDT   1h   full history from --history-start (default 2017-08-01)
    ETHUSDT   1d   full history from --history-start
    FDUSDUSDT 1m   same span as local ETH_FDUSD-1m
It also writes symbol_filters.json (tick size, lot size, min notional,
whether LIMIT_MAKER is allowed) for ETHFDUSD, ETHUSDT and FDUSDUSDT --
those are exchange facts, never assumed anywhere in the research code.

Usage (from the repo root; run on YOUR machine -- needs internet):
    python3 user_data/analysis/fetch_klines.py --dry-run
    python3 user_data/analysis/fetch_klines.py
    python3 user_data/analysis/fetch_klines.py --exchange-info-only
Interrupted? Just re-run: files are extended (resumed), not re-downloaded.
"""

from __future__ import annotations

import argparse
import email.message
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE_URLS = [
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://data-api.binance.vision",  # market-data-only mirror; no geo/account restrictions
]
INTERVAL_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "1d": 86_400_000, "1w": 604_800_000,
}
QUOTES = ("FDUSD", "USDT", "USDC", "BTC")
STORE_COLUMNS = [
    "date", "open", "high", "low", "close", "volume",
    "quote_volume", "n_trades", "taker_buy_base", "taker_buy_quote",
]


def symbol_to_pair(symbol: str) -> str:
    """ETHFDUSD -> ETH_FDUSD, FDUSDUSDT -> FDUSD_USDT (freqtrade file naming)."""
    for q in QUOTES:
        if symbol.endswith(q) and len(symbol) > len(q):
            return f"{symbol[:-len(q)]}_{q}"
    raise ValueError(f"cannot split symbol {symbol!r} into base/quote; add its quote to QUOTES")


# --------------------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------------------
class BinanceHTTPError(RuntimeError):
    pass


def _urlopen_json(url: str, timeout: float = 30.0):
    req = urllib.request.Request(url, headers={"User-Agent": "eth-fdusd-research/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class BinanceClient:
    """GET-only client with retry/backoff, 429/418 handling and base-URL fallback
    (geo-blocked hosts answer 451/403 -> try the next base)."""

    def __init__(self, base_urls=None, min_interval_s: float = 0.12, max_retries: int = 6,
                 opener=_urlopen_json, sleep=time.sleep):
        self.base_urls = list(base_urls or BASE_URLS)
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self._opener = opener
        self._sleep = sleep
        self._active = 0
        self._last_call = 0.0
        self.n_requests = 0

    def _throttle(self) -> None:
        wait = self.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            self._sleep(wait)
        self._last_call = time.monotonic()

    def get(self, path: str, params: dict | None = None):
        qs = "?" + urllib.parse.urlencode(params) if params else ""
        order = self.base_urls[self._active:] + self.base_urls[: self._active]
        last_err: Exception | None = None
        for base in order:
            for attempt in range(self.max_retries):
                self._throttle()
                self.n_requests += 1
                try:
                    data = self._opener(base + path + qs)
                    self._active = self.base_urls.index(base)
                    return data
                except urllib.error.HTTPError as e:
                    last_err = e
                    if e.code in (429, 418):
                        retry_after = e.headers.get("Retry-After") if e.headers else None
                        self._sleep(float(retry_after) if retry_after else min(60.0, 2.0 ** attempt))
                        continue
                    if e.code in (451, 403):
                        break  # geo/WAF block on this host -> next base URL
                    if e.code >= 500:
                        self._sleep(min(30.0, 2.0 ** attempt))
                        continue
                    raise BinanceHTTPError(f"HTTP {e.code} for {base}{path}{qs}") from e
                except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                    last_err = e
                    self._sleep(min(30.0, 2.0 ** attempt))
                    continue
        raise BinanceHTTPError(f"all base URLs failed for {path}{qs}: {last_err!r}")


# --------------------------------------------------------------------------------------
# Klines
# --------------------------------------------------------------------------------------
def klines_to_frame(rows: list) -> pd.DataFrame:
    """Binance kline arrays -> DataFrame. Also carries `close_ms` (used only to
    drop still-open bars; removed before saving). Handles millisecond AND
    microsecond timestamps (data.binance.vision spot files moved to microseconds
    in 2025; the REST API is milliseconds by default, but be safe)."""
    if not rows:
        return pd.DataFrame(columns=STORE_COLUMNS + ["close_ms"])
    raw = pd.DataFrame(rows).iloc[:, :11]
    open_t = pd.to_numeric(raw[0]).astype("int64")
    close_t = pd.to_numeric(raw[6]).astype("int64")
    if int(open_t.max()) > 10**14:  # microseconds
        open_t, close_t = open_t // 1000, close_t // 1000
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(open_t, unit="ms", utc=True).dt.as_unit("ns"),
            "open": pd.to_numeric(raw[1]).astype(float),
            "high": pd.to_numeric(raw[2]).astype(float),
            "low": pd.to_numeric(raw[3]).astype(float),
            "close": pd.to_numeric(raw[4]).astype(float),
            "volume": pd.to_numeric(raw[5]).astype(float),
            "quote_volume": pd.to_numeric(raw[7]).astype(float),
            "n_trades": pd.to_numeric(raw[8]).astype("int64"),
            "taker_buy_base": pd.to_numeric(raw[9]).astype(float),
            "taker_buy_quote": pd.to_numeric(raw[10]).astype(float),
            "close_ms": close_t,
        }
    )
    return out


def fetch_klines(client, symbol: str, interval: str, start_ms: int, end_ms: int,
                 now_ms: int | None = None, log=print) -> pd.DataFrame:
    """All CLOSED klines with open time in [start_ms, end_ms]. Paginated by open time."""
    step = INTERVAL_MS[interval]
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    cursor, frames, pages = start_ms, [], 0
    while cursor <= end_ms:
        rows = client.get(
            "/api/v3/klines",
            {"symbol": symbol, "interval": interval, "startTime": cursor, "endTime": end_ms, "limit": 1000},
        )
        pages += 1
        if not rows:
            break
        frame = klines_to_frame(rows)
        last_open_ms = int(frame["date"].iloc[-1].timestamp() * 1000)
        frames.append(frame)
        if last_open_ms < cursor:  # no forward progress -> stop rather than loop forever
            break
        cursor = last_open_ms + step
        if log and pages % 50 == 0:
            log(f"    {symbol} {interval}: {pages} pages, up to {frame['date'].iloc[-1]}")
    if not frames:
        return pd.DataFrame(columns=STORE_COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    df = df[df["close_ms"] < now_ms]  # drop the still-forming bar
    df = df.drop(columns=["close_ms"]).drop_duplicates("date", keep="last").sort_values("date")
    return df.reset_index(drop=True)


def read_store(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.as_unit("ns")
    return df


def save_merged(path: Path, new: pd.DataFrame) -> pd.DataFrame:
    old = read_store(path)
    merged = new if old is None else pd.concat([old, new], ignore_index=True)
    merged = merged.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    merged = merged[STORE_COLUMNS]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".feather.tmp")
    merged.to_feather(tmp)
    tmp.replace(path)
    return merged


# --------------------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------------------
@dataclass
class Job:
    symbol: str
    interval: str
    start_ms: int
    end_ms: int

    @property
    def label(self) -> str:
        return f"{self.symbol} {self.interval}"


def _ms(ts: pd.Timestamp) -> int:
    return int(pd.Timestamp(ts).timestamp() * 1000)


def local_span(path: Path) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    if not path.exists():
        return None
    d = pd.to_datetime(pd.read_feather(path, columns=["date"])["date"], utc=True)
    return d.min(), d.max()


def _floor_ms(ms: int, step: int) -> int:
    return (ms // step) * step


def default_jobs(data_dir: Path, pair: str, history_start: str, start_1m: str | None = None) -> list[Job]:
    """`start_1m` (e.g. "2026-01-30") moves the START of the three 1m jobs earlier than the local
    freqtrade file. The END of every job still comes from the local 1m file, so all files finish
    at the same bar. Use it to extend the raw store backwards when freqtrade's own downloader
    will not (see --start and --export-freqtrade)."""
    span_1m = local_span(data_dir / f"{pair}-1m.feather")
    if span_1m is None:
        raise FileNotFoundError(
            f"{data_dir / (pair + '-1m.feather')} not found -- pass --jobs SYMBOL:INTERVAL:START:END explicitly"
        )
    span_5m = local_span(data_dir / f"{pair}-5m.feather") or span_1m
    first_1m = _ms(pd.Timestamp(start_1m, tz="UTC")) if start_1m else _ms(span_1m[0])
    end_wall = _ms(span_1m[1]) + INTERVAL_MS["1m"]  # end of the last local 1m bar
    hist = _ms(pd.Timestamp(history_start, tz="UTC"))

    def end_for(interval: str) -> int:
        step = INTERVAL_MS[interval]
        return _floor_ms(end_wall, step) - 1  # last COMPLETE bar inside the local 1m span

    base = pair.replace("_", "")
    return [
        Job(base, "1m", first_1m, end_for("1m")),
        Job("ETHUSDT", "1m", first_1m, end_for("1m")),
        Job("ETHUSDT", "5m", _ms(span_5m[0]), end_for("5m")),
        Job("ETHUSDT", "1h", hist, end_for("1h")),
        Job("ETHUSDT", "1d", hist, end_for("1d")),
        Job("FDUSDUSDT", "1m", first_1m, end_for("1m")),
    ]


def parse_job(spec: str, default_end_ms: int) -> Job:
    parts = spec.split(":")
    if len(parts) < 3:
        raise ValueError(f"--jobs entries look like SYMBOL:INTERVAL:START[:END], got {spec!r}")
    symbol, interval, start = parts[0], parts[1], parts[2]
    end_ms = _ms(pd.Timestamp(parts[3], tz="UTC")) if len(parts) > 3 else default_end_ms
    if interval not in INTERVAL_MS:
        raise ValueError(f"unknown interval {interval!r}")
    return Job(symbol, interval, _ms(pd.Timestamp(start, tz="UTC")), end_ms)


def run_job(client, job: Job, out_dir: Path, now_ms: int, resume: bool = True, log=print) -> dict:
    step = INTERVAL_MS[job.interval]
    path = out_dir / f"{symbol_to_pair(job.symbol)}-{job.interval}.feather"
    start_ms = job.start_ms
    old = read_store(path) if resume else None
    if old is not None and len(old) and _ms(old["date"].min()) <= job.start_ms + step - 1:
        start_ms = max(job.start_ms, _ms(old["date"].max()) + step)  # existing file covers the start: extend it
    req_before = client.n_requests
    if start_ms > job.end_ms:
        fetched = pd.DataFrame(columns=STORE_COLUMNS)
    else:
        log(f"  fetching {job.label}: {pd.Timestamp(start_ms, unit='ms', tz='UTC')} -> "
            f"{pd.Timestamp(job.end_ms, unit='ms', tz='UTC')}")
        fetched = fetch_klines(client, job.symbol, job.interval, start_ms, job.end_ms, now_ms=now_ms, log=log)
    merged = save_merged(path, fetched) if len(fetched) or path.exists() else fetched
    if not len(merged):
        return {"file": str(path), "symbol": job.symbol, "interval": job.interval, "status": "NO_DATA_RETURNED"}
    expected = int((merged["date"].max() - merged["date"].min()) / pd.Timedelta(milliseconds=step)) + 1
    return {
        "file": str(path), "symbol": job.symbol, "interval": job.interval,
        "status": "OK" if len(fetched) else "UP_TO_DATE",
        "rows": int(len(merged)), "first": str(merged["date"].min()), "last": str(merged["date"].max()),
        "rows_fetched_this_run": int(len(fetched)), "requests_this_run": client.n_requests - req_before,
        "missing_bars_vs_regular_grid": expected - int(len(merged)),
        "bars_with_zero_trades": int((merged["n_trades"] == 0).sum()),
    }


# --------------------------------------------------------------------------------------
# Raw store -> freqtrade file (only when freqtrade's own downloader will not backfill)
# --------------------------------------------------------------------------------------
FREQTRADE_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def export_to_freqtrade(raw_dir: Path, data_dir: Path, pair: str, interval: str = "1m", now_tag: str | None = None) -> dict:
    """Rewrite <data_dir>/<pair>-<interval>.feather from the raw-kline store, keeping only the six
    columns freqtrade knows. The existing file is backed up first, and the export is REFUSED unless
      (a) it covers every timestamp the existing file has, and
      (b) on all those timestamps the OHLCV values are identical.
    Task 0 already showed the raw store and freqtrade's file agree bar-for-bar, so (b) is the
    guard that this is still true; if it ever fails, nothing is written."""
    raw = read_store(raw_dir / f"{pair}-{interval}.feather")
    if raw is None:
        raise FileNotFoundError(f"{raw_dir / (pair + '-' + interval + '.feather')} not found -- run the download first")
    target = data_dir / f"{pair}-{interval}.feather"
    old = None
    if target.exists():
        old = pd.read_feather(target)
        old["date"] = pd.to_datetime(old["date"], utc=True).dt.as_unit("ns")
        merged = old.merge(raw[FREQTRADE_COLUMNS], on="date", how="left", suffixes=("_old", "_raw"), indicator=True)
        lost = int((merged["_merge"] == "left_only").sum())
        if lost:
            raise SystemExit(f"REFUSED: {lost} existing rows are not in the raw store; nothing written.")
        for col in FREQTRADE_COLUMNS[1:]:
            bad = int(((merged[f"{col}_old"] - merged[f"{col}_raw"]).abs() > 1e-9).sum())
            if bad:
                raise SystemExit(f"REFUSED: {bad} rows differ in '{col}' between the freqtrade file and the raw store; nothing written.")
    out = raw[FREQTRADE_COLUMNS].sort_values("date").reset_index(drop=True)
    backup = None
    if target.exists():
        tag = now_tag or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = target.with_name(f"{target.stem}.backup-{tag}.feather.bak")
        target.replace(backup)
    tmp = target.with_suffix(".feather.tmp")
    out.to_feather(tmp, compression="lz4")
    tmp.replace(target)
    return {"file": str(target), "backup": str(backup) if backup else None, "rows_before": None if old is None else int(len(old)),
            "rows_after": int(len(out)), "first": str(out["date"].min()), "last": str(out["date"].max())}


# --------------------------------------------------------------------------------------
# Exchange filters (tick size etc. -- exchange facts, never assumed)
# --------------------------------------------------------------------------------------
def parse_symbol_filters(info: dict) -> dict:
    sym = info["symbols"][0]
    filters = {f["filterType"]: f for f in sym.get("filters", [])}
    notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
    order_types = sym.get("orderTypes", [])
    return {
        "symbol": sym["symbol"],
        "status": sym.get("status"),
        "orderTypes": order_types,
        "limit_maker_supported": "LIMIT_MAKER" in order_types,
        "tickSize": float(filters["PRICE_FILTER"]["tickSize"]) if "PRICE_FILTER" in filters else None,
        "stepSize": float(filters["LOT_SIZE"]["stepSize"]) if "LOT_SIZE" in filters else None,
        "minQty": float(filters["LOT_SIZE"]["minQty"]) if "LOT_SIZE" in filters else None,
        "minNotional": float(notional["minNotional"]) if "minNotional" in notional else None,
        "raw_filters": sym.get("filters", []),
    }


def fetch_symbol_filters(client, symbols: list[str]) -> dict:
    out = {}
    for s in symbols:
        out[s] = parse_symbol_filters(client.get("/api/v3/exchangeInfo", {"symbol": s}))
    return out


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("user_data/data/binance"),
                    help="freqtrade data dir; its ETH_FDUSD files define the span to download")
    ap.add_argument("--out-dir", type=Path, default=Path("user_data/data/binance_raw"))
    ap.add_argument("--pair", default="ETH_FDUSD")
    ap.add_argument("--history-start", default="2017-08-01", help="start for the full-history ETHUSDT 1h/1d jobs")
    ap.add_argument("--jobs", nargs="+", default=None, metavar="SYMBOL:INTERVAL:START[:END]",
                    help="override the default job list, e.g. ETHUSDT:1m:2026-03-01:2026-09-18")
    ap.add_argument("--base-url", default=None, help="use only this API host")
    ap.add_argument("--no-resume", action="store_true", help="re-download instead of extending existing files")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and request estimate, download nothing")
    ap.add_argument("--exchange-info-only", action="store_true", help="only refresh symbol_filters.json")
    ap.add_argument("--start", default=None, metavar="YYYY-MM-DD",
                    help="start date for the three 1m jobs (default: start of the local freqtrade 1m file). "
                         "Ends still come from the local 1m file.")
    ap.add_argument("--export-freqtrade", action="store_true",
                    help="after downloading, rewrite <data-dir>/<pair>-1m.feather from the raw store (backup + identity checks)")
    ap.add_argument("--export-only", action="store_true", help="only run the export, download nothing")
    ap.add_argument("--self-test", action="store_true", help="run the offline self-test (no network) and exit")
    args = ap.parse_args(argv)

    client = BinanceClient(base_urls=[args.base_url] if args.base_url else None)
    now_ms = int(time.time() * 1000)

    if args.export_only:
        rep = export_to_freqtrade(args.out_dir, args.data_dir, args.pair)
        print(json.dumps(rep, indent=2))
        return 0
    if args.jobs:
        jobs = [parse_job(j, now_ms) for j in args.jobs]
    elif args.exchange_info_only:
        jobs = []
    else:
        jobs = default_jobs(args.data_dir, args.pair, args.history_start, start_1m=args.start)

    if args.dry_run:
        total = 0
        for j in jobs:
            n = math.ceil(((j.end_ms - j.start_ms) / INTERVAL_MS[j.interval] + 1) / 1000)
            total += n
            print(f"{j.label:14s} {pd.Timestamp(j.start_ms, unit='ms', tz='UTC')} -> "
                  f"{pd.Timestamp(j.end_ms, unit='ms', tz='UTC')}   ~{n} requests")
        print(f"total ~{total} requests (~{total * 0.12 / 60:.1f} min at the built-in rate limit)")
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print("Fetching exchange filters ...")
    filters = fetch_symbol_filters(client, sorted({j.symbol for j in jobs} | {"ETHFDUSD", "ETHUSDT", "FDUSDUSDT"}))
    (args.out_dir / "symbol_filters.json").write_text(json.dumps(
        {"fetched_utc": datetime.now(timezone.utc).isoformat(), "symbols": filters}, indent=2))
    for s, f in filters.items():
        print(f"  {s}: tickSize={f['tickSize']} stepSize={f['stepSize']} minNotional={f['minNotional']} "
              f"LIMIT_MAKER={'yes' if f['limit_maker_supported'] else 'NO'} status={f['status']}")

    reports = []
    for j in jobs:
        print(f"[{len(reports) + 1}/{len(jobs)}] {j.label}")
        rep = run_job(client, j, args.out_dir, now_ms, resume=not args.no_resume)
        reports.append(rep)
        print(f"  -> {rep['status']}: {rep.get('rows', 0)} rows, {rep.get('first')} .. {rep.get('last')}, "
              f"missing bars vs regular grid: {rep.get('missing_bars_vs_regular_grid')}, "
              f"zero-trade bars: {rep.get('bars_with_zero_trades')}")
    if reports:
        (args.out_dir / "fetch_manifest.json").write_text(json.dumps(
            {"finished_utc": datetime.now(timezone.utc).isoformat(), "jobs": reports}, indent=2, default=str))
        print(f"\nWrote {args.out_dir}/fetch_manifest.json and symbol_filters.json")
    if args.export_freqtrade:
        rep = export_to_freqtrade(args.out_dir, args.data_dir, args.pair)
        print("\nExported to freqtrade data dir:\n" + json.dumps(rep, indent=2))
    return 0


# --------------------------------------------------------------------------------------
# Self-test: a fake exchange with known structure (no network needed)
# --------------------------------------------------------------------------------------
class _FakeExchange:
    """Generates deterministic klines; omits some minutes (no trades) like the real feed."""

    def __init__(self, first_ms: int, n_bars: int, step_ms: int, missing: set[int], micro: bool = False):
        self.step, self.micro = step_ms, micro
        self.opens = [first_ms + i * step_ms for i in range(n_bars) if i not in missing]
        self.calls = 0

    def kline(self, t):
        i = (t // self.step) % 997
        px = 3000 + i * 0.01
        m = 1000 if self.micro else 1
        return [t * m, f"{px:.2f}", f"{px + 1:.2f}", f"{px - 1:.2f}", f"{px + 0.5:.2f}", "1.5",
                (t + self.step - 1) * m, "4500.0", 3 + i % 5, "0.7", "2100.0", "0"]

    def get(self, path, params):
        self.calls += 1
        if path == "/api/v3/exchangeInfo":
            return {"symbols": [{"symbol": params["symbol"], "status": "TRADING",
                                 "orderTypes": ["LIMIT", "LIMIT_MAKER", "MARKET"],
                                 "filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
                                             {"filterType": "LOT_SIZE", "stepSize": "0.00010000", "minQty": "0.00010000"},
                                             {"filterType": "NOTIONAL", "minNotional": "5.00000000"}]}]}
        lo, hi, lim = params["startTime"], params["endTime"], params["limit"]
        return [self.kline(t) for t in self.opens if lo <= t <= hi][:lim]


def _self_test() -> None:
    import tempfile

    t0 = int(pd.Timestamp("2026-03-01", tz="UTC").timestamp() * 1000)
    n_bars = 3 * 1440 + 17
    missing = {5, 6, 7, 999, 1000, 1001, 2500}
    fake = _FakeExchange(t0, n_bars, 60_000, missing)
    client = BinanceClient(min_interval_s=0.0)
    client.get = fake.get  # bypass HTTP for the pagination logic

    end_ms = t0 + n_bars * 60_000 - 1
    now_ms = end_ms - 30_000  # the last bar is still forming (closes after now) -> must be dropped
    df = fetch_klines(client, "ETHUSDT", "1m", t0, end_ms, now_ms=now_ms, log=None)
    expected = [t for t in fake.opens if t + 60_000 - 1 < now_ms]
    got = [int(x.timestamp() * 1000) for x in df["date"]]
    assert got == expected, (len(got), len(expected))
    assert len(fake.opens) - len(got) == 1, "exactly the still-open bar must be dropped"
    assert fake.calls == math.ceil(len(fake.opens) / 1000), (fake.calls, len(fake.opens))
    assert df["date"].is_monotonic_increasing and df["date"].is_unique
    assert list(df.columns) == STORE_COLUMNS
    assert str(df["date"].dt.tz) == "UTC"
    assert df["n_trades"].dtype == "int64" and float(df["taker_buy_base"].iloc[0]) == 0.7
    print(f"  pagination: {len(df)} bars over {fake.calls} requests, no duplicates, gaps preserved, open bar dropped")

    # microsecond timestamps give the same bars
    fake_us = _FakeExchange(t0, n_bars, 60_000, missing, micro=True)
    client_us = BinanceClient(min_interval_s=0.0)
    client_us.get = fake_us.get
    df_us = fetch_klines(client_us, "ETHUSDT", "1m", t0, end_ms, now_ms=now_ms, log=None)
    assert df_us["date"].tolist() == df["date"].tolist()
    print("  microsecond timestamps are normalised to the same bars")

    # resume: fetch the first half, then the full job -> identical to one-shot, no duplicates
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        client2 = BinanceClient(min_interval_s=0.0)
        client2.get = fake.get
        mid = t0 + 1500 * 60_000
        run_job(client2, Job("ETHUSDT", "1m", t0, mid), out, now_ms)
        rep = run_job(client2, Job("ETHUSDT", "1m", t0, end_ms), out, now_ms)
        full = read_store(out / "ETH_USDT-1m.feather")
        assert full["date"].tolist() == df["date"].tolist() and full["date"].is_unique
        assert rep["missing_bars_vs_regular_grid"] == len(missing), rep
        again = run_job(client2, Job("ETHUSDT", "1m", t0, end_ms), out, now_ms)
        assert again["status"] == "UP_TO_DATE" and again["rows_fetched_this_run"] == 0
        assert (full["n_trades"] >= 3).all() and full.equals(read_store(out / "ETH_USDT-1m.feather"))
        print(f"  resume/extend: two partial runs == one shot; third run is UP_TO_DATE; "
              f"missing bars vs grid reported = {rep['missing_bars_vs_regular_grid']}")

    # retry / fallback behaviour of the real client, with a scripted opener
    hdrs = email.message.Message(); hdrs["Retry-After"] = "0"
    script = [urllib.error.HTTPError("u", 429, "slow down", hdrs, None),
              urllib.error.HTTPError("u", 451, "geo", email.message.Message(), None),
              {"ok": True}]
    seen = []

    def scripted(url):
        seen.append(url)
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    c3 = BinanceClient(base_urls=["https://a.example", "https://b.example"], min_interval_s=0.0,
                       opener=scripted, sleep=lambda s: None)
    assert c3.get("/x", {"q": 1}) == {"ok": True}
    assert seen[0].startswith("https://a.example") and seen[1].startswith("https://a.example") \
        and seen[2].startswith("https://b.example"), seen
    try:
        BinanceClient(base_urls=["https://a.example"], min_interval_s=0.0, sleep=lambda s: None,
                      opener=lambda url: (_ for _ in ()).throw(urllib.error.HTTPError(url, 400, "bad", email.message.Message(), None))
                      ).get("/x")
    except BinanceHTTPError:
        pass
    else:
        raise AssertionError("a 400 must raise, not retry forever")
    print("  http client: 429 -> retry, 451 -> next base URL, 400 -> immediate error")

    # exchange filters + symbol naming + job planning
    f = fetch_symbol_filters(client, ["ETHFDUSD"])["ETHFDUSD"]
    assert f["tickSize"] == 0.01 and f["limit_maker_supported"] and f["minNotional"] == 5.0
    assert symbol_to_pair("ETHFDUSD") == "ETH_FDUSD" and symbol_to_pair("FDUSDUSDT") == "FDUSD_USDT" \
        and symbol_to_pair("ETHUSDT") == "ETH_USDT"
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        idx = pd.date_range("2026-03-01 00:00", "2026-03-04 05:07", freq="1min", tz="UTC")
        pd.DataFrame({"date": idx, "open": 1.0}).to_feather(d / "ETH_FDUSD-1m.feather")
        jobs = default_jobs(d, "ETH_FDUSD", "2017-08-01")
        assert [(j.symbol, j.interval) for j in jobs] == [
            ("ETHFDUSD", "1m"), ("ETHUSDT", "1m"), ("ETHUSDT", "5m"), ("ETHUSDT", "1h"), ("ETHUSDT", "1d"), ("FDUSDUSDT", "1m")]
        last_1m_end = int(idx[-1].timestamp() * 1000) + 60_000
        assert jobs[0].end_ms == last_1m_end - 1
        assert jobs[2].end_ms % 300_000 == 299_999 and jobs[2].end_ms <= last_1m_end - 1   # last COMPLETE 5m bar
        assert jobs[4].end_ms % 86_400_000 == 86_399_999                                     # last complete day
        assert jobs[3].start_ms < jobs[0].start_ms
    print("  exchange filters parsed; default jobs derive from the local ETH_FDUSD span")
    # start override: the three 1m jobs start earlier, everything else (and every END) unchanged
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        idx = pd.date_range("2026-03-19 00:00", "2026-03-22 23:59", freq="1min", tz="UTC")
        pd.DataFrame({"date": idx, "open": 1.0}).to_feather(d / "ETH_FDUSD-1m.feather")
        base_jobs = default_jobs(d, "ETH_FDUSD", "2017-08-01")
        early = default_jobs(d, "ETH_FDUSD", "2017-08-01", start_1m="2026-01-30")
        want = _ms(pd.Timestamp("2026-01-30", tz="UTC"))
        for i, j in enumerate(early):
            if (j.symbol, j.interval) in (("ETHFDUSD", "1m"), ("ETHUSDT", "1m"), ("FDUSDUSDT", "1m")):
                assert j.start_ms == want and j.end_ms == base_jobs[i].end_ms
            else:
                assert j.start_ms == base_jobs[i].start_ms and j.end_ms == base_jobs[i].end_ms
    print("  --start moves only the three 1m job starts; every end still comes from the local 1m file")

    # export to freqtrade: extends backwards, backs up, and REFUSES on any disagreement or lost row
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); raw_dir, data_dir = tmp / "raw", tmp / "ft"; raw_dir.mkdir(); data_dir.mkdir()
        t0_ = int(pd.Timestamp("2026-03-01", tz="UTC").timestamp() * 1000)
        fx = _FakeExchange(t0_, 3 * 1440, 60_000, missing=set())
        cl = BinanceClient(min_interval_s=0.0); cl.get = fx.get
        end_ = t0_ + 3 * 1440 * 60_000 - 1
        run_job(cl, Job("ETHFDUSD", "1m", t0_, end_), raw_dir, end_ + 10**9, log=lambda *a, **k: None)
        raw_df = read_store(raw_dir / "ETH_FDUSD-1m.feather")
        late = raw_df[raw_df["date"] >= raw_df["date"].iloc[1440]][FREQTRADE_COLUMNS]   # freqtrade file = only the later 2 days
        late.reset_index(drop=True).to_feather(data_dir / "ETH_FDUSD-1m.feather")
        rep = export_to_freqtrade(raw_dir, data_dir, "ETH_FDUSD", now_tag="TEST")
        new = pd.read_feather(data_dir / "ETH_FDUSD-1m.feather")
        assert rep["rows_before"] == 2 * 1440 and rep["rows_after"] == 3 * 1440 and len(new) == 3 * 1440
        assert list(new.columns) == FREQTRADE_COLUMNS and Path(rep["backup"]).exists()
        # disagreement -> refused, file untouched
        bad = new.copy(); bad.loc[10, "close"] += 1.0
        bad.to_feather(data_dir / "ETH_FDUSD-1m.feather")
        try:
            export_to_freqtrade(raw_dir, data_dir, "ETH_FDUSD", now_tag="TEST2")
        except SystemExit as e:
            assert "REFUSED" in str(e)
        else:
            raise AssertionError("must refuse when values differ")
        # existing row missing from raw -> refused
        extra = new.copy(); extra.loc[0, "date"] = extra.loc[0, "date"] - pd.Timedelta(days=30)
        extra.to_feather(data_dir / "ETH_FDUSD-1m.feather")
        try:
            export_to_freqtrade(raw_dir, data_dir, "ETH_FDUSD", now_tag="TEST3")
        except SystemExit as e:
            assert "REFUSED" in str(e)
        else:
            raise AssertionError("must refuse when rows would be lost")
    print("  export: extends the freqtrade file backwards, keeps a backup, refuses on any value mismatch or lost row")
    print("Self-test passed: fetch_klines paginates, resumes, retries and plans jobs correctly (offline fake exchange).")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        sys.exit(main())
