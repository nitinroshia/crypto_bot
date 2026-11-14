"""
Work Order 1.8 addendum section 2: the Upstox V3 historical-candle client (daily candles of NSE equities).

Official documentation (read 2026-11-06): https://upstox.com/developer/api-documentation/v3/get-historical-candle-data
  GET https://api.upstox.com/v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}   (to_date FIRST; both dates inclusive, YYYY-MM-DD)
  instrument_key = NSE_EQ|<ISIN> (the pipe is URL-encoded); daily candles: unit "days", interval 1; ONE DECADE per request at most, daily history from January 2000;
  data.candles rows = [timestamp (ISO, +05:30), open, high, low, close, volume, open interest], possibly newest first.
  Headers: Authorization: Bearer <token>, Accept: application/json.
Rate limits (https://upstox.com/developer/api-documentation/rate-limiting): standard APIs allow 50 requests per second, 500 per minute and 2,000 per 30 minutes per user.
This client stays far below them: ONE request at a time, at least MIN_INTERVAL_S (2 s) between request starts (at most 30 per minute), a hard cap of MAX_PER_30MIN (1,000)
per 30 minutes, exponential backoff on 429 and 5xx (honouring Retry-After), and resume (a finished chunk is never requested again).

Authentication: the read-only ANALYTICS token from the owner's `.env` (UPSTOX_ANALYTICS_TOKEN; UPSTOX_ACCESS_TOKEN only as a fallback). The token is NEVER logged, printed or put in an
error message: every message is passed through nse_common.redact(). Self-tests use canned responses: no network, no token.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import date, datetime, timedelta
from pathlib import Path

from nse_common import redact

BASE_URL = "https://api.upstox.com/v3/historical-candle"
MIN_INTERVAL_S = 2.0
MAX_PER_30MIN = 1000
MAX_RETRIES = 6
BACKOFF_BASE_S = 2.0
BACKOFF_CAP_S = 60.0
HOLE_DAYS = 7  # a calendar gap larger than this between neighbouring rows of two chunks is reported as a possible hole
FIXED_CHUNKS = [(date(2000, 1, 1), date(2009, 12, 31)), (date(2010, 1, 1), date(2019, 12, 31))]


class UpstoxError(RuntimeError):
    pass


def chunks_for(latest_day: date) -> list[tuple[date, date]]:
    """Decade chunks: 2000-01-01..2009-12-31, 2010-01-01..2019-12-31, 2020-01-01..latest day."""
    return FIXED_CHUNKS + [(date(2020, 1, 1), latest_day)]


def token_from_env(env: dict) -> str:
    tok = env.get("UPSTOX_ANALYTICS_TOKEN") or env.get("UPSTOX_ACCESS_TOKEN")
    if not tok:
        raise UpstoxError("no Upstox token in .env (UPSTOX_ANALYTICS_TOKEN): ask the owner to generate the read-only analytics token and save it in .env")
    return tok


class UpstoxClient:
    def __init__(self, env: dict, opener=None, sleep=time.sleep, clock=time.monotonic, state_dir: Path | None = None):
        self._env = dict(env)
        self._token = token_from_env(self._env)
        self._opener = opener if opener is not None else urllib.request.urlopen
        self._sleep, self._clock = sleep, clock
        self._state_dir = Path(state_dir) if state_dir is not None else None
        self._last_start: float | None = None
        self._window: deque = deque()
        self.requests_made = 0

    # ------------------------------------------------------------------ plumbing
    def url(self, isin: str, from_date: date, to_date: date) -> str:
        key = urllib.parse.quote(f"NSE_EQ|{isin}", safe="")
        return f"{BASE_URL}/{key}/days/1/{to_date.isoformat()}/{from_date.isoformat()}"

    def _pace(self) -> None:
        now = self._clock()
        if self._last_start is not None and now - self._last_start < MIN_INTERVAL_S:
            self._sleep(MIN_INTERVAL_S - (now - self._last_start))
        now = self._clock()
        while self._window and now - self._window[0] >= 1800:
            self._window.popleft()
        if len(self._window) >= MAX_PER_30MIN:
            self._sleep(1800 - (now - self._window[0]) + 1)
        self._last_start = self._clock()
        self._window.append(self._last_start)

    def _fail(self, msg: str) -> UpstoxError:
        return UpstoxError(redact(msg, self._env))

    def _request(self, url: str) -> dict:
        import urllib.request as ur

        for attempt in range(MAX_RETRIES + 1):
            self._pace()
            req = ur.Request(url, headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"})
            self.requests_made += 1
            wait = None
            try:
                with self._opener(req, timeout=30) as resp:
                    body = resp.read()
                    try:
                        return json.loads(body)
                    except ValueError as e:
                        raise self._fail(f"response is not JSON ({e})") from None
            except urllib.error.HTTPError as e:
                if e.code == 429 or 500 <= e.code < 600:
                    ra = e.headers.get("Retry-After") if getattr(e, "headers", None) else None
                    wait = min(float(ra), 120.0) if ra and str(ra).replace(".", "", 1).isdigit() else min(BACKOFF_BASE_S * 2 ** attempt, BACKOFF_CAP_S)
                    last = f"HTTP {e.code}"
                else:
                    raise self._fail(f"HTTP {e.code} from Upstox for {url} (not retried): check the token and the instrument key") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                wait = min(BACKOFF_BASE_S * 2 ** attempt, BACKOFF_CAP_S)
                last = f"network error {type(e).__name__}"
            if attempt == MAX_RETRIES:
                raise self._fail(f"{last} for {url}: gave up after {MAX_RETRIES} retries")
            self._sleep(wait)
        raise self._fail("unreachable")

    # ------------------------------------------------------------------ data
    @staticmethod
    def parse_candles(payload: dict, from_date: date, to_date: date) -> tuple[list[tuple], list[str]]:
        """Rows (date, open, high, low, close, volume) ascending, one per date; plus notes (duplicates dropped, rows outside the window, odd timestamps)."""
        if payload.get("status") != "success":
            raise UpstoxError("response status is not 'success'")
        candles = (payload.get("data") or {}).get("candles")
        if candles is None:
            raise UpstoxError("response has no data.candles")
        notes, seen, rows = [], {}, []
        dup = outside = odd = 0
        for c in candles:
            ts = str(c[0])
            d = ts[:10]
            if not (ts[10:].startswith("T00:00:00") and ts.endswith("+05:30")):
                odd += 1
            try:
                dd = date.fromisoformat(d)
            except ValueError:
                raise UpstoxError(f"unreadable candle timestamp {ts!r}") from None
            if not (from_date <= dd <= to_date):
                outside += 1
                continue
            if d in seen:
                dup += 1
                continue
            seen[d] = True
            rows.append((d, float(c[1]), float(c[2]), float(c[3]), float(c[4]), int(c[5])))
        rows.sort(key=lambda r: r[0])
        if dup:
            notes.append(f"{dup} duplicate date(s) dropped (first kept)")
        if outside:
            notes.append(f"{outside} row(s) outside {from_date}..{to_date} dropped")
        if odd:
            notes.append(f"{odd} timestamp(s) not at 00:00:00+05:30")
        return rows, notes

    def fetch_chunk(self, isin: str, from_date: date, to_date: date) -> tuple[list[tuple], list[str]]:
        cache = self._state_dir / f"{isin}_{from_date.isoformat()}_{to_date.isoformat()}.json" if self._state_dir is not None else None
        if cache is not None and cache.exists():
            payload, resumed = json.loads(cache.read_text()), True
        else:
            payload, resumed = self._request(self.url(isin, from_date, to_date)), False
            if cache is not None:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(payload))
        rows, notes = self.parse_candles(payload, from_date, to_date)
        return rows, ([f"chunk {from_date}..{to_date} resumed from the state folder (no request)"] if resumed else []) + [f"chunk {from_date}..{to_date}: {n}" for n in notes]

    def fetch_daily(self, isin: str, latest_day: date) -> tuple[list[tuple], list[str]]:
        """All daily candles of one instrument: decade chunks, merged ascending, duplicates dropped, chunk borders checked for overlaps and holes."""
        merged: dict[str, tuple] = {}
        notes: list[str] = []
        prev_last: str | None = None
        for lo, hi in chunks_for(latest_day):
            rows, n = self.fetch_chunk(isin, lo, hi)
            notes += n
            if rows:
                if prev_last is not None:
                    gap = (date.fromisoformat(rows[0][0]) - date.fromisoformat(prev_last)).days
                    if gap > HOLE_DAYS:
                        notes.append(f"possible hole at the border {prev_last} -> {rows[0][0]} ({gap} calendar days)")
                    if rows[0][0] <= prev_last:
                        notes.append(f"overlap at the border: {rows[0][0]} <= {prev_last}")
                prev_last = rows[-1][0]
            for r in rows:
                merged.setdefault(r[0], r)
        return [merged[d] for d in sorted(merged)], notes


# ----------------------------------------------------------------------------- self-test with canned responses
class _Resp:
    def __init__(self, body: bytes):
        self._b = body

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _candles(start: date, end: date, newest_first=True, dup_first=False) -> dict:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append([f"{d.isoformat()}T00:00:00+05:30", 100.0, 101.0, 99.0, 100.5, 1000, 0])
        d += timedelta(days=1)
    if newest_first:
        out.reverse()
    if dup_first and out:
        out.append(list(out[0]))
    return {"status": "success", "data": {"candles": out}}


def _self_test() -> None:
    import tempfile

    TOKEN = "SECRETTOKEN.abc-123456789"
    env = {"UPSTOX_ANALYTICS_TOKEN": TOKEN, "DATABASE_URL": "postgresql://u:dbpass123@h/db"}

    class Fake:
        def __init__(self, script):
            self.script, self.requests = list(script), []

        def __call__(self, req, timeout=None):
            self.requests.append(req)
            item = self.script.pop(0) if self.script else None
            if callable(item):
                item = item(req)
            if isinstance(item, Exception):
                raise item
            return _Resp(json.dumps(item).encode())

    def http(code, retry_after=None):
        h = {"Retry-After": retry_after} if retry_after else {}
        return urllib.error.HTTPError("https://x", code, "err", h, None)

    class Clock:
        def __init__(self):
            self.t, self.slept = 1000.0, []

        def now(self):
            return self.t

        def sleep(self, s):
            self.slept.append(s)
            self.t += s

    def make(script, state=None):
        clk = Clock()
        fake = Fake(script)
        return UpstoxClient(env, opener=fake, sleep=clk.sleep, clock=clk.now, state_dir=state), fake, clk

    # URL, headers, chunks
    cl, fake, clk = make([_candles(date(2020, 1, 1), date(2020, 3, 31))])
    u = cl.url("INE002A01018", date(2020, 1, 1), date(2026, 11, 5))
    assert u == "https://api.upstox.com/v3/historical-candle/NSE_EQ%7CINE002A01018/days/1/2026-11-05/2020-01-01", u
    assert chunks_for(date(2026, 11, 5)) == [(date(2000, 1, 1), date(2009, 12, 31)), (date(2010, 1, 1), date(2019, 12, 31)), (date(2020, 1, 1), date(2026, 11, 5))]
    rows, notes = cl.fetch_chunk("INE002A01018", date(2020, 1, 1), date(2020, 3, 31))
    req = fake.requests[0]
    assert req.get_header("Authorization") == f"Bearer {TOKEN}" and req.get_header("Accept") == "application/json" and "%7C" in req.full_url
    assert [r[0] for r in rows] == sorted(r[0] for r in rows) and rows[0][0] == "2020-01-01", "newest-first input is sorted ascending"
    # duplicates, rows outside the window, odd timestamps
    pay = _candles(date(2020, 1, 1), date(2020, 1, 31), dup_first=True)
    pay["data"]["candles"].append(["2019-12-31T00:00:00+05:30", 1, 1, 1, 1, 1, 0])
    pay["data"]["candles"].append(["2020-01-02T09:15:00+05:30", 1, 1, 1, 1, 1, 0])
    rows, notes = UpstoxClient.parse_candles(pay, date(2020, 1, 1), date(2020, 1, 31))
    assert len({r[0] for r in rows}) == len(rows) and any("duplicate" in n for n in notes) and any("outside" in n for n in notes) and any("not at 00:00:00+05:30" in n for n in notes)
    for bad in ({"status": "error"}, {"status": "success", "data": {}}, {"status": "success", "data": {"candles": [["garbage", 1, 1, 1, 1, 1, 0]]}}):
        try:
            UpstoxClient.parse_candles(bad, date(2020, 1, 1), date(2020, 1, 31))
        except UpstoxError:
            pass
        else:
            raise AssertionError(f"accepted {bad}")
    # pacing: one request at a time, at least 2 s between starts
    script = [_candles(date(2000, 1, 3), date(2009, 12, 31)), _candles(date(2010, 1, 1), date(2019, 12, 31)), _candles(date(2020, 1, 1), date(2026, 11, 5))]
    cl, fake, clk = make(script)
    rows, notes = cl.fetch_daily("INE002A01018", date(2026, 11, 5))
    assert cl.requests_made == 3 and len(clk.slept) == 2 and all(abs(s - MIN_INTERVAL_S) < 1e-9 for s in clk.slept), clk.slept
    assert [r[0] for r in rows] == sorted({r[0] for r in rows}) and rows[0][0] == "2000-01-03" and rows[-1][0] == "2026-11-05" and not notes, notes
    # backoff: 429 then success; 500 then success; Retry-After honoured; resumed gap
    cl, fake, clk = make([http(429), http(500), _candles(date(2020, 1, 1), date(2020, 1, 31))])
    cl.fetch_chunk("INE002A01018", date(2020, 1, 1), date(2020, 1, 31))
    assert cl.requests_made == 3 and clk.slept[0] == 2.0 and clk.slept[1] > 2.0, clk.slept
    cl, fake, clk = make([http(429, "7"), _candles(date(2020, 1, 1), date(2020, 1, 31))])
    cl.fetch_chunk("INE002A01018", date(2020, 1, 1), date(2020, 1, 31))
    assert clk.slept[0] == 7.0
    # give up after MAX_RETRIES; not retried on 401; token and DB password never appear in an error
    cl, fake, clk = make([http(429)] * (MAX_RETRIES + 1))
    try:
        cl.fetch_chunk("INE002A01018", date(2020, 1, 1), date(2020, 1, 31))
    except UpstoxError as e:
        assert "gave up" in str(e) and cl.requests_made == MAX_RETRIES + 1 and TOKEN not in str(e)
    else:
        raise AssertionError("must give up")
    assert max(clk.slept) <= BACKOFF_CAP_S
    cl, fake, clk = make([http(401), _candles(date(2020, 1, 1), date(2020, 1, 31))])
    try:
        cl.fetch_chunk("INE002A01018", date(2020, 1, 1), date(2020, 1, 31))
    except UpstoxError as e:
        assert cl.requests_made == 1 and TOKEN not in str(e) and "dbpass123" not in str(e) and "401" in str(e)
    else:
        raise AssertionError("401 must not be retried")
    leaky = UpstoxError(redact(f"boom with Authorization: Bearer {TOKEN} and postgresql://u:dbpass123@h/db", env))
    assert TOKEN not in str(leaky) and "dbpass123" not in str(leaky)
    try:
        UpstoxClient({}, opener=Fake([]))
    except UpstoxError as e:
        assert "ask the owner" in str(e)
    else:
        raise AssertionError("a missing token must stop with a plain note")
    assert UpstoxClient({"UPSTOX_ACCESS_TOKEN": "fallback-token-12345"}, opener=Fake([]))._token == "fallback-token-12345"
    # resume: finished chunks are never requested again
    with tempfile.TemporaryDirectory() as tmp:
        script = [_candles(date(2000, 1, 3), date(2009, 12, 31)), _candles(date(2010, 1, 1), date(2019, 12, 31)), http(500), http(500), http(500), http(500), http(500), http(500), http(500)]
        cl, fake, clk = make(script, Path(tmp))
        try:
            cl.fetch_daily("INE002A01018", date(2026, 11, 5))
        except UpstoxError:
            pass
        else:
            raise AssertionError("third chunk should fail")
        assert len(list(Path(tmp).glob("*.json"))) == 2
        cl2, fake2, clk2 = make([_candles(date(2020, 1, 1), date(2026, 11, 5))], Path(tmp))
        rows, notes = cl2.fetch_daily("INE002A01018", date(2026, 11, 5))
        assert cl2.requests_made == 1 and sum("resumed" in n for n in notes) == 2 and rows[0][0] == "2000-01-03"
    # chunk borders: overlap and hole
    over = [_candles(date(2000, 1, 3), date(2010, 1, 5)), _candles(date(2010, 1, 1), date(2019, 12, 31)), _candles(date(2020, 1, 1), date(2026, 11, 5))]
    cl, _, _ = make(over)
    rows, notes = cl.fetch_daily("INE002A01018", date(2026, 11, 5))
    assert any("outside" in n for n in notes), "rows beyond a chunk's window are dropped and noted"
    hole = [_candles(date(2000, 1, 3), date(2009, 12, 31)), _candles(date(2010, 3, 1), date(2019, 12, 31)), _candles(date(2020, 1, 1), date(2026, 11, 5))]
    cl, _, _ = make(hole)
    rows, notes = cl.fetch_daily("INE002A01018", date(2026, 11, 5))
    assert any("possible hole" in n for n in notes)
    print("Self-test passed: nse_upstox builds the V3 URL (to_date first, pipe URL-encoded), sends Bearer and Accept headers, sorts newest-first rows ascending, drops duplicates and rows outside the window, "
          "spaces requests by 2 s, backs off exponentially on 429/5xx (Retry-After honoured, capped, gives up after 6 retries), never retries a 401, never lets the token or the DB password into an error, "
          "stops plainly without a token, resumes without re-requesting finished chunks and reports border holes.")


if __name__ == "__main__":
    _self_test()
