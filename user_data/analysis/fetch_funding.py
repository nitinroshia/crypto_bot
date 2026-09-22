"""
Funding-rate downloader (work order 1.2 data batch, item 2; answers A3 and 1.4 item 5).

SOURCE ORDER (as ruled): the USD-M futures REST endpoint first; if it is unreachable from this
machine, the data.binance.vision monthly funding-rate files for USD-M futures. The run REPORTS
which source was used, the first settlement date, the settlement intervals seen (and every
interval change), and the descriptive counts of the 8h observations (see funding.py).

    GET https://fapi.binance.com/fapi/v1/fundingRate?symbol=ETHUSDT&startTime=..&limit=1000
    https://data.binance.vision/data/futures/um/monthly/fundingRate/ETHUSDT/ETHUSDT-fundingRate-YYYY-MM.zip

Nothing about the response layout is assumed silently: the REST rows must carry fundingTime and
fundingRate, and the monthly CSV layout is read from its header (unknown header -> error showing
the first lines). The first real run on the owner's machine is therefore also the check of
those two layouts; this sandbox cannot reach Binance and tested everything against fakes only.

    python3 user_data/analysis/fetch_funding.py --dry-run
    python3 user_data/analysis/fetch_funding.py                       # ETHUSDT and BTCUSDT, source auto
    python3 user_data/analysis/fetch_funding.py --source vision       # force the monthly files
    python3 user_data/analysis/fetch_funding.py --self-test           # offline checks

STORAGE (inside the project root only): <out-dir>/ETH_USDT-funding.feather (and BTC_USDT-...),
columns date, funding_time_ms_raw, rate, interval_hours_reported, interval_hours, source, plus
<out-dir>/funding_manifest.json. Re-running extends the REST series from its last settlement;
the monthly files are small and re-read in full. The monthly source publishes whole months only,
so its last settlement is at the end of the last complete month (reported).

DESCRIPTIVE ONLY: this tool reads and counts funding rates (spans, intervals, ties). It computes
no return of any series and relates no predictor to a return.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import funding as fd
from fetch_klines import BinanceClient, BinanceHTTPError, symbol_to_pair

REST_BASE = "https://fapi.binance.com"
REST_PATH = "/fapi/v1/fundingRate"
VISION_BASE = "https://data.binance.vision"
DEFAULT_SYMBOLS = ("ETHUSDT", "BTCUSDT")
DEFAULT_HISTORY_START = "2019-09-01"          # before either USD-M perpetual existed; the first record found is the first settlement
REST_LIMIT = 1000


# --------------------------------------------------------------------------------------
# REST
# --------------------------------------------------------------------------------------
def fetch_rest(client, symbol: str, start_ms: int, end_ms: int, limit: int | None = None, log=print) -> pd.DataFrame:
    """Page forward from start_ms until the endpoint returns a short or empty page."""
    limit = REST_LIMIT if limit is None else limit
    rows: list[dict] = []
    cursor, pages = start_ms, 0
    while cursor <= end_ms:
        page = client.get(REST_PATH, {"symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": limit})
        pages += 1
        if not page:
            break
        rows.extend(page)
        last = max(int(r["fundingTime"]) for r in page)
        if last < cursor:
            break
        cursor = last + 1
        if len(page) < limit:
            break
    log(f"    {symbol} REST: {pages} page(s), {len(rows)} rows")
    return fd.parse_rest(rows)


# --------------------------------------------------------------------------------------
# data.binance.vision monthly files
# --------------------------------------------------------------------------------------
def vision_url(symbol: str, year: int, month: int) -> str:
    return f"{VISION_BASE}/data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{year:04d}-{month:02d}.zip"


def _urlopen_bytes(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "eth-research-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def month_range(start: pd.Timestamp, now: pd.Timestamp) -> list[tuple[int, int]]:
    """Whole months from start's month through the last COMPLETE month before now."""
    cur = pd.Timestamp(year=start.year, month=start.month, day=1, tz="UTC")
    last_complete = pd.Timestamp(year=now.year, month=now.month, day=1, tz="UTC") - pd.DateOffset(months=1)
    out = []
    while cur <= last_complete:
        out.append((cur.year, cur.month))
        cur = cur + pd.DateOffset(months=1)
    return out


def fetch_vision_month(open_bytes, symbol: str, year: int, month: int, retries: int = 3, sleep=time.sleep) -> bytes | None:
    """Zip bytes, or None if the file does not exist (HTTP 404)."""
    url = vision_url(symbol, year, month)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            return open_bytes(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = e
        sleep(min(20.0, 2.0 ** attempt))
    raise BinanceHTTPError(f"could not download {url}: {last!r}")


def fetch_vision(open_bytes, symbol: str, months: list[tuple[int, int]], log=print, sleep=time.sleep) -> tuple[pd.DataFrame, dict]:
    parts, found, missing = [], [], []
    for (y, m) in months:
        blob = fetch_vision_month(open_bytes, symbol, y, m, sleep=sleep)
        if blob is None:
            missing.append(f"{y:04d}-{m:02d}")
            continue
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not names:
                raise ValueError(f"{vision_url(symbol, y, m)} holds no CSV (members: {zf.namelist()})")
            parts.append(fd.parse_vision_csv(zf.read(names[0])))
        found.append(f"{y:04d}-{m:02d}")
    if not found:
        raise BinanceHTTPError(f"{symbol}: no monthly funding file found for {months[0]}..{months[-1]}")
    first_i = months.index((int(found[0][:4]), int(found[0][5:])))
    interior_missing = [x for x in missing if (int(x[:4]), int(x[5:])) > months[first_i]]
    info = {"months_found": len(found), "first_month_found": found[0], "last_month_found": found[-1],
            "months_missing_before_first": len(missing) - len(interior_missing), "months_missing_interior": interior_missing}
    log(f"    {symbol} monthly files: {len(found)} found ({found[0]} .. {found[-1]}), interior gaps: {interior_missing or 'none'}")
    return pd.concat(parts, ignore_index=True), info


# --------------------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------------------
def store_path(out_dir: Path, symbol: str) -> Path:
    return out_dir / f"{symbol_to_pair(symbol)}-funding.feather"


def read_store(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.as_unit("ns")
    return df


def save_store(path: Path, native: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".feather.tmp")
    native.to_feather(tmp)
    tmp.replace(path)


# --------------------------------------------------------------------------------------
# One symbol
# --------------------------------------------------------------------------------------
def run_symbol(symbol: str, *, out_dir: Path, source: str, history_start: pd.Timestamp, now: pd.Timestamp,
               rest_client, open_bytes, resume: bool = True, log=print, sleep=time.sleep) -> dict:
    path = store_path(out_dir, symbol)
    old = read_store(path) if resume else None
    used, rest_error, vision_info = None, None, None
    parts = None
    if source in ("auto", "rest"):
        start_ms = int(old["funding_time_ms_raw"].iloc[-1]) + 1 if old is not None and len(old) else int(history_start.value // 10**6)
        try:
            parts = fetch_rest(rest_client, symbol, start_ms, int(now.value // 10**6), log=log)
            used = "rest"
        except BinanceHTTPError as e:
            rest_error = str(e)
            if source == "rest":
                raise
            log(f"    {symbol}: futures REST unreachable ({rest_error}); falling back to data.binance.vision monthly files")
    if used is None:
        months = month_range(history_start, now)
        parts, vision_info = fetch_vision(open_bytes, symbol, months, log=log, sleep=sleep)
        used = "vision"
    new_rows = len(parts)
    native_new = fd.build_native(parts, used)
    merged = fd.merge_native(old, native_new)
    if not len(merged):
        raise BinanceHTTPError(f"{symbol}: no funding rows obtained from {used}")
    save_store(path, merged)
    obs = fd.funding_observations(merged)
    return {
        "symbol": symbol, "file": str(path), "source_used": used, "rest_error": rest_error, "vision": vision_info,
        "rows_fetched_this_run": int(new_rows), "native": fd.describe_native(merged),
        "observations": fd.describe_observations(obs),
        "fetched_utc": now.isoformat(),
    }


def print_report(res: dict) -> None:
    n, o = res["native"], res["observations"]
    print(f"\n{res['symbol']}: source used = {res['source_used'].upper()}"
          + (f" (REST failed: {res['rest_error']})" if res["rest_error"] else ""))
    print(f"  first settlement {n['first_settlement']}   last settlement {n['last_settlement']}   rows {n['rows']} ({res['rows_fetched_this_run']} fetched this run)")
    print(f"  settlement intervals (hours -> rows): {n['interval_hours_counts']}")
    if n["interval_changes"]:
        print("  INTERVAL CHANGES: " + "; ".join(f"{c['date']} -> {c['to_hours']}h" for c in n["interval_changes"]))
    else:
        print("  interval changes: none")
    print(f"  irregular spacing rows: {n['irregular_spacing_rows']}   reported-vs-derived interval mismatches: {n['reported_vs_derived_interval_mismatches']} "
          f"(reported interval available: {n['reported_interval_available']})")
    print(f"  8h observations: {o['observations']} (first {o['first_observation']}), complete {o['complete']}, masked {o['masked']}, "
          f"touched by an interval change {o['touched_by_interval_change']}")
    t, tf = o["tie_share_up_to_cutoff"], o["tie_share_full_range_descriptive"]
    print(f"  tie share up to the cutoff: {t['tie_share']:.4f} (modal value {t['modal_value']}, {t['modal_count']} of {t['n']})"
          if t.get("n") else "  tie share up to the cutoff: n/a")
    print(f"  tie share, full range (descriptive only): {tf['tie_share']:.4f} (modal value {tf['modal_value']}, {tf['modal_count']} of {tf['n']})"
          if tf.get("n") else "")
    if res.get("vision"):
        print(f"  monthly files: {res['vision']}")


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    ap.add_argument("--out-dir", type=Path, default=Path("user_data/data/binance_raw"))
    ap.add_argument("--source", choices=("auto", "rest", "vision"), default="auto")
    ap.add_argument("--history-start", default=DEFAULT_HISTORY_START)
    ap.add_argument("--base-url", default=REST_BASE, help="futures REST host (default %(default)s)")
    ap.add_argument("--no-resume", action="store_true", help="ignore the stored series and refetch everything")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        _self_test()
        return 0
    now = pd.Timestamp.now(tz="UTC")
    start = pd.Timestamp(args.history_start, tz="UTC")
    if args.dry_run:
        for s in args.symbols:
            print(f"{s}: {args.base_url}{REST_PATH}?symbol={s}&startTime={int(start.value // 10**6)}&limit={REST_LIMIT}  (paged)  "
                  f"[fallback: {len(month_range(start, now))} monthly files, e.g. {vision_url(s, start.year, start.month)}]")
            print(f"    store: {store_path(args.out_dir, s)}")
        return 0
    client = BinanceClient(base_urls=[args.base_url], min_interval_s=0.5, max_retries=3)
    results = []
    for s in args.symbols:
        print(f"\n[{s}]")
        res = run_symbol(s, out_dir=args.out_dir, source=args.source, history_start=start, now=now, rest_client=client,
                         open_bytes=_urlopen_bytes, resume=not args.no_resume)
        print_report(res)
        results.append(res)
    manifest = args.out_dir / "funding_manifest.json"
    manifest.write_text(json.dumps({"written_utc": now.isoformat(), "source_option": args.source, "symbols": results}, indent=2, default=str))
    print(f"\nWrote {manifest}")
    return 0


# --------------------------------------------------------------------------------------
# Self-test (offline: fake REST and fake monthly files)
# --------------------------------------------------------------------------------------
def _selftest_tmp() -> Path:
    root = Path(__file__).resolve().parents[2]
    d = root / "temp" / "selftest"
    d.mkdir(parents=True, exist_ok=True)
    return d


class _FakeREST:
    def __init__(self, times_ms, rates, fail=False):
        self.rows = [{"symbol": "ETHUSDT", "fundingTime": int(t), "fundingRate": f"{r:.8f}", "markPrice": "1.0"} for t, r in zip(times_ms, rates)]
        self.fail, self.calls = fail, []

    def get(self, path, params=None):
        self.calls.append(dict(params))
        if self.fail:
            raise BinanceHTTPError("all base URLs failed (fake)")
        assert path == REST_PATH and params["symbol"] and params["limit"] >= 1
        sel = [r for r in self.rows if params["startTime"] <= r["fundingTime"] <= params["endTime"]]
        return sel[: params["limit"]]


def _fake_zip(csv_text: str, name="x.csv") -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as zf:
        zf.writestr(name, csv_text)
    return b.getvalue()


def _self_test() -> None:
    now = pd.Timestamp("2026-03-15 10:00", tz="UTC")
    start = pd.Timestamp("2025-11-01", tz="UTC")
    t = pd.date_range("2025-11-27 16:00", "2026-03-15 08:00", freq="8h", tz="UTC")
    ms = t.as_unit("ms").asi8 + (np.arange(len(t)) % 5) + 1                      # 1..5 ms of published jitter
    rates = np.round(np.where(np.arange(len(t)) % 3 == 0, 1e-4, np.linspace(-1e-4, 6e-4, len(t))), 8)
    nrows = len(t)

    with tempfile.TemporaryDirectory(dir=_selftest_tmp()) as tmp:
        out = Path(tmp)
        # 1. REST: paging (limit 1000 -> force 2 pages with a small monkeypatched limit), rounding, store, report
        global REST_LIMIT
        keep_limit, REST_LIMIT = REST_LIMIT, 50
        try:
            rest = _FakeREST(ms, rates)
            res = run_symbol("ETHUSDT", out_dir=out, source="auto", history_start=start, now=now, rest_client=rest,
                             open_bytes=lambda u: (_ for _ in ()).throw(AssertionError("vision must not be used when REST works")))
        finally:
            REST_LIMIT = keep_limit
        assert res["source_used"] == "rest" and res["rows_fetched_this_run"] == nrows and len(rest.calls) >= 3
        assert res["native"]["first_settlement"].startswith("2025-11-27 16:00:00")
        assert res["native"]["interval_changes"] == [] and res["native"]["interval_hours_counts"] == {"8.0": nrows - 1}
        stored = read_store(store_path(out, "ETHUSDT"))
        assert (stored["date"] == t.as_unit("ns")).all() and stored["source"].eq("rest").all()
        assert res["observations"]["masked"] == 1 and res["observations"]["touched_by_interval_change"] == 0
        assert res["observations"]["tie_share_up_to_cutoff"]["n"] == 0                # discovery cutoff is 2025-08-31: no such data here
        print(f"  REST path: {len(rest.calls)} pages, jitter rounded, stored, first settlement reported, no interval change")

        # 2. resume: a second run asks only from the last settlement onward and adds nothing
        rest2 = _FakeREST(ms, rates)
        res2 = run_symbol("ETHUSDT", out_dir=out, source="auto", history_start=start, now=now, rest_client=rest2, open_bytes=None)
        assert rest2.calls[0]["startTime"] == int(ms[-1]) + 1 and res2["rows_fetched_this_run"] == 0 and res2["native"]["rows"] == nrows
        print("  resume: second run requests from the last published time + 1 ms and keeps the series unchanged")

    with tempfile.TemporaryDirectory(dir=_selftest_tmp()) as tmp:
        out = Path(tmp)
        # 3. REST unreachable -> monthly files; header read from the CSV; a 4h regime and its interval change are reported
        months = {}
        cur = pd.Timestamp("2025-12-01", tz="UTC")
        while cur < pd.Timestamp("2026-03-01", tz="UTC"):
            nxt = cur + pd.DateOffset(months=1)
            iv = np.where(np.arange(len(t)) >= 0, 8, 8)
            tt = [x for x in pd.date_range(cur, nxt - pd.Timedelta(seconds=1), freq="8h", tz="UTC")]
            if cur >= pd.Timestamp("2026-02-01", tz="UTC"):                                  # switch to 4h from February
                tt = list(pd.date_range(cur, nxt - pd.Timedelta(seconds=1), freq="4h", tz="UTC"))
                ivh = 4
            else:
                ivh = 8
            csv = "calc_time,funding_interval_hours,last_funding_rate\n" + "".join(
                f"{int(x.as_unit('ms').value // 10**6) + 3},{ivh},0.0001\n" for x in tt)
            months[(cur.year, cur.month)] = _fake_zip(csv, f"ETHUSDT-fundingRate-{cur.year}-{cur.month:02d}.csv")
            cur = nxt
        seen = []

        def opener(url):
            seen.append(url)
            key = (int(url[-11:-7]), int(url[-6:-4]))
            if key in months:
                return months[key]
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        res3 = run_symbol("ETHUSDT", out_dir=out, source="auto", history_start=pd.Timestamp("2025-11-01", tz="UTC"), now=now,
                          rest_client=_FakeREST([], [], fail=True), open_bytes=opener, sleep=lambda s: None)
        assert res3["source_used"] == "vision" and "unreachable" not in (res3["rest_error"] or "") and res3["rest_error"]
        assert res3["vision"]["first_month_found"] == "2025-12" and res3["vision"]["last_month_found"] == "2026-02"
        assert res3["vision"]["months_missing_before_first"] == 1 and res3["vision"]["months_missing_interior"] == []
        assert seen[0].endswith("ETHUSDT-fundingRate-2025-11.zip") and "/futures/um/monthly/fundingRate/ETHUSDT/" in seen[0]
        assert not any("2026-03" in u for u in seen), "the current, incomplete month must not be requested"
        n3 = res3["native"]
        assert [c["to_hours"] for c in n3["interval_changes"]] == [4.0] and n3["interval_changes"][0]["date"].startswith("2026-02-01")
        assert n3["reported_interval_available"] and n3["reported_vs_derived_interval_mismatches"] <= 1
        assert res3["observations"]["touched_by_interval_change"] > 0
        print(f"  fallback: REST failure -> monthly files; header-driven parsing; interval change {n3['interval_changes'][0]['date'][:10]} -> 4h and "
              f"{res3['observations']['touched_by_interval_change']} touched observations reported")

        # 4. forced REST failure raises; an interior missing month is flagged; an unknown CSV layout raises
        try:
            run_symbol("ETHUSDT", out_dir=out, source="rest", history_start=start, now=now, rest_client=_FakeREST([], [], fail=True), open_bytes=None)
        except BinanceHTTPError:
            pass
        else:
            raise AssertionError("--source rest must not fall back")
        holes = dict(months)
        del holes[(2026, 1)]
        def opener2(url):
            key = (int(url[-11:-7]), int(url[-6:-4]))
            if key in holes:
                return holes[key]
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        _, info = fetch_vision(opener2, "ETHUSDT", month_range(start, now), log=lambda *a: None, sleep=lambda s: None)
        assert info["months_missing_interior"] == ["2026-01"]
        bad = {(2025, 12): _fake_zip("x,y\n1,2\n")}
        try:
            fetch_vision(lambda u: bad[(int(u[-11:-7]), int(u[-6:-4]))], "ETHUSDT", [(2025, 12)], log=lambda *a: None, sleep=lambda s: None)
        except ValueError as e:
            assert "unrecognised funding CSV header" in str(e)
        else:
            raise AssertionError("unknown layout must raise")
        print("  --source rest never falls back; interior missing month flagged; unknown monthly layout raises")

    # 5. month range: whole months, current month excluded
    mr = month_range(pd.Timestamp("2025-11-15", tz="UTC"), pd.Timestamp("2026-01-02", tz="UTC"))
    assert mr == [(2025, 11), (2025, 12)], mr
    print("Self-test passed: fetch_funding.py falls back correctly, resumes, reports interval changes and never guesses a layout.")


if __name__ == "__main__":
    sys.exit(main())
