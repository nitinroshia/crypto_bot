"""
Funding-rate handling for the S2 `funding_extreme` study and data-batch item 2
(work orders 1.2 and 1.5, answer A3). Pure functions, no network: the network side
is fetch_funding.py.

TWO SERIES
  native        one row per settlement exactly as the exchange published it: `date` (UTC,
                settlement time rounded to the nearest SECOND), `funding_time_ms_raw` (as
                published), `rate`, `interval_hours_reported` (only the monthly files carry
                it; NaN from the REST endpoint) and `interval_hours` (DERIVED: hours since
                the previous settlement; NaN for the first row).
  observations  the series S2 uses (answer A3): ONLY the 8h-aligned settlements (00:00, 08:00,
                16:00 UTC). An observation's rate is the SUM of the native rates settled in
                (s - 8h, s], which equals the native rate while the interval is 8h. The rank
                window therefore stays 270 observations and the HAC lags stay 3 and 9.

WHEN AN OBSERVATION IS MASKED (never dropped: it stays on the grid with a NaN rate)
  A native settlement at time t with rate r covers (previous settlement, t]. An observation
  is COMPLETE only if the native settlements inside (s - 8h, s] chain exactly from s - 8h to
  s (a settlement at s - 8h before the window, a settlement at s, none missing in between, so
  no native period straddles a window boundary). Otherwise its rate is NaN and it is counted
  as masked. A complete observation built from more than one native settlement is counted as
  "touched by an interval change". An observation is ALSO masked when any native settlement
  inside its window has a reported interval (monthly files only) that disagrees with the
  derived spacing: that is how a missing native row is caught. Limitation, stated rather than
  hidden: from the REST endpoint (no reported interval) a missing 12:00 row inside a 4h regime
  looks like one 8h period and cannot be detected.

TIE SHARE (answer A1): the fraction of observations equal to the modal funding value. The
share used for the S2 report is computed on observations up to the discovery cutoff only; a
full-range count is a separate, purely descriptive number.

    python3 funding.py          # runs the self-test
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

DISCOVERY_CUTOFF = pd.Timestamp("2025-08-31 23:59:59", tz="UTC")  # work order 1.2, section 2
OBS_HOURS = 8
NATIVE_COLUMNS = ["date", "funding_time_ms_raw", "rate", "interval_hours_reported", "interval_hours", "source"]

_TIME_COLS = ("calc_time", "fundingtime", "funding_time")
_RATE_COLS = ("last_funding_rate", "fundingrate", "funding_rate")
_INTERVAL_COLS = ("funding_interval_hours",)


# --------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------
def _to_ms(values) -> np.ndarray:
    """Timestamps -> integer milliseconds (microsecond inputs are normalised, as in fetch_klines)."""
    ms = pd.to_numeric(pd.Series(values)).astype("int64").to_numpy()
    if len(ms) and int(ms.max()) > 10**14:
        ms = ms // 1000
    return ms


def parse_rest(rows: list[dict]) -> pd.DataFrame:
    """GET /fapi/v1/fundingRate rows -> raw frame (funding_time_ms_raw, rate, interval_hours_reported)."""
    if not rows:
        return pd.DataFrame({"funding_time_ms_raw": pd.Series(dtype="int64"), "rate": pd.Series(dtype=float),
                             "interval_hours_reported": pd.Series(dtype=float)})
    df = pd.DataFrame(rows)
    missing = {"fundingTime", "fundingRate"} - set(df.columns)
    if missing:
        raise ValueError(f"REST funding rows lack {sorted(missing)}; got columns {list(df.columns)}")
    return pd.DataFrame({
        "funding_time_ms_raw": _to_ms(df["fundingTime"]),
        "rate": pd.to_numeric(df["fundingRate"]).astype(float).to_numpy(),
        "interval_hours_reported": np.nan,
    })


def parse_vision_csv(text: str | bytes) -> pd.DataFrame:
    """One data.binance.vision monthly funding-rate CSV -> raw frame. The layout is READ from the
    header, never assumed: an unrecognised header raises with the first lines shown."""
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    first_lines = text.strip().splitlines()[:3]
    df = pd.read_csv(io.StringIO(text))
    cols = {c.strip().lower(): c for c in df.columns}
    tcol = next((cols[c] for c in _TIME_COLS if c in cols), None)
    rcol = next((cols[c] for c in _RATE_COLS if c in cols), None)
    icol = next((cols[c] for c in _INTERVAL_COLS if c in cols), None)
    if tcol is None or rcol is None:
        raise ValueError(f"unrecognised funding CSV header {list(df.columns)}; first lines: {first_lines}")
    return pd.DataFrame({
        "funding_time_ms_raw": _to_ms(df[tcol]),
        "rate": pd.to_numeric(df[rcol]).astype(float).to_numpy(),
        "interval_hours_reported": pd.to_numeric(df[icol]).astype(float).to_numpy() if icol else np.nan,
    })


# --------------------------------------------------------------------------------------
# Native series
# --------------------------------------------------------------------------------------
def _finish(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    df["interval_hours"] = df["date"].diff().dt.total_seconds() / 3600.0
    return df[NATIVE_COLUMNS]


def build_native(raw: pd.DataFrame, source: str) -> pd.DataFrame:
    """Raw frame -> native series: times rounded to the nearest second, duplicates removed (last
    wins), sorted, derived interval added."""
    df = raw.copy()
    ms = df["funding_time_ms_raw"].astype("int64")
    df["date"] = pd.to_datetime(((ms + 500) // 1000) * 1000, unit="ms", utc=True).dt.as_unit("ns")
    df["source"] = source
    return _finish(df)


def merge_native(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """Extend a stored native series; on the same settlement the new row wins; the derived interval
    is recomputed over the merged series."""
    if old is None or not len(old):
        return _finish(new.copy())
    return _finish(pd.concat([old, new], ignore_index=True))


def _ns(ts: pd.Series) -> np.ndarray:
    return ts.dt.tz_convert(None).dt.as_unit("ns").to_numpy().astype("int64")


def interval_segments(native: pd.DataFrame) -> list[dict]:
    """Runs of consecutive settlements with the same derived interval (the first row has none)."""
    iv = native["interval_hours"].round(4)
    out: list[dict] = []
    for i in range(1, len(native)):
        v = float(iv.iloc[i])
        if out and out[-1]["interval_hours"] == v:
            out[-1]["end"] = str(native["date"].iloc[i])
            out[-1]["n"] += 1
        else:
            out.append({"interval_hours": v, "start": str(native["date"].iloc[i]),
                        "end": str(native["date"].iloc[i]), "n": 1})
    return out


def describe_native(native: pd.DataFrame) -> dict:
    if not len(native):
        return {"rows": 0}
    seg = interval_segments(native)
    iv = native["interval_hours"].iloc[1:]
    counts = {str(k): int(v) for k, v in iv.round(4).value_counts().sort_index().items()}
    rep = native["interval_hours_reported"]
    both = rep.notna() & native["interval_hours"].notna()
    mism = int(((rep[both] - native["interval_hours"][both]).abs() > 1e-6).sum())
    return {
        "rows": int(len(native)), "first_settlement": str(native["date"].iloc[0]),
        "last_settlement": str(native["date"].iloc[-1]),
        "interval_hours_counts": counts,
        "interval_segments": seg,
        "interval_changes": [{"date": s["start"], "to_hours": s["interval_hours"]} for k, s in enumerate(seg) if k > 0],
        "irregular_spacing_rows": int(((iv <= 0) | ((iv - iv.round()).abs() > 1e-6)).sum()),
        "reported_vs_derived_interval_mismatches": mism,
        "reported_interval_available": bool(rep.notna().any()),
    }


# --------------------------------------------------------------------------------------
# 8h-aligned observations (answer A3)
# --------------------------------------------------------------------------------------
def funding_observations(native: pd.DataFrame) -> pd.DataFrame:
    """Observations on the 00:00 / 08:00 / 16:00 UTC grid. Columns: rate (NaN if masked),
    n_native, complete, touched_by_interval_change. See the module docstring."""
    cols = ["rate", "n_native", "complete", "touched_by_interval_change"]
    if len(native) < 2:
        return pd.DataFrame(columns=cols, index=pd.DatetimeIndex([], tz="UTC", name="obs_time"))
    t = _ns(native["date"])
    r = native["rate"].to_numpy(float)
    if not np.isfinite(r).all():
        raise ValueError("native funding series contains a non-finite rate")
    H = OBS_HOURS * 3600 * 10**9
    grid = pd.date_range(native["date"].iloc[0].ceil("8h"), native["date"].iloc[-1].floor("8h"), freq="8h", tz="UTC")
    s = grid.tz_convert(None).as_unit("ns").to_numpy().astype("int64")
    lo = np.searchsorted(t, s - H, side="right")
    hi = np.searchsorted(t, s, side="right")
    n_nat = hi - lo
    ok = (n_nat >= 1) & (lo >= 1)
    ok[ok] = (t[lo[ok] - 1] == s[ok] - H) & (t[hi[ok] - 1] == s[ok])
    rep, der = native["interval_hours_reported"].to_numpy(float), native["interval_hours"].to_numpy(float)
    both = np.isfinite(rep) & np.isfinite(der)
    mism = np.zeros(len(t), dtype=int)
    mism[both] = (np.abs(rep[both] - der[both]) > 1e-6).astype(int)
    cm = np.concatenate([[0], np.cumsum(mism)])
    ok &= (cm[hi] - cm[lo]) == 0                     # a settlement whose reported interval disagrees with the spacing masks its window
    cs = np.concatenate([[0.0], np.cumsum(r)])
    rate = np.where(ok, cs[hi] - cs[lo], np.nan)
    out = pd.DataFrame({"rate": rate, "n_native": n_nat.astype(int), "complete": ok,
                        "touched_by_interval_change": ok & (n_nat != 1)}, index=grid)
    out.index.name = "obs_time"
    return out


def tie_share(rates) -> dict:
    """Fraction of observations equal to the modal value (answer A1)."""
    v = pd.Series(np.asarray(rates, dtype=float))
    v = v[np.isfinite(v)].round(12)
    if not len(v):
        return {"n": 0, "modal_value": None, "modal_count": 0, "tie_share": None}
    vc = v.value_counts()
    return {"n": int(len(v)), "modal_value": float(vc.index[0]), "modal_count": int(vc.iloc[0]),
            "tie_share": float(vc.iloc[0] / len(v))}


def describe_observations(obs: pd.DataFrame, cutoff: pd.Timestamp = DISCOVERY_CUTOFF) -> dict:
    """Counts and tie shares. The A1 tie share is computed on observations up to the cutoff; the
    full-range share is a separate descriptive (no return of any series is computed here)."""
    if not len(obs):
        return {"observations": 0}
    upto = obs[obs.index <= cutoff]
    return {
        "observations": int(len(obs)), "first_observation": str(obs.index[0]), "last_observation": str(obs.index[-1]),
        "complete": int(obs["complete"].sum()), "masked": int((~obs["complete"]).sum()),
        "touched_by_interval_change": int(obs["touched_by_interval_change"].sum()),
        "observations_up_to_cutoff": int(len(upto)),
        "tie_share_up_to_cutoff": tie_share(upto["rate"]),
        "tie_share_full_range_descriptive": tie_share(obs["rate"]),
    }


# --------------------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------------------
def _selftest_tmp() -> Path:
    root = Path(__file__).resolve().parents[2]          # <root>/user_data/analysis/<this file>
    d = root / "temp" / "selftest"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _mk_native(times, rates, reported=None, source="test") -> pd.DataFrame:
    ms = (pd.DatetimeIndex(times).tz_convert("UTC").as_unit("ms").asi8).astype("int64")
    raw = pd.DataFrame({"funding_time_ms_raw": ms, "rate": np.asarray(rates, float),
                        "interval_hours_reported": np.nan if reported is None else np.asarray(reported, float)})
    return build_native(raw, source)


def _self_test() -> None:
    # 1. plain 8h regime with millisecond jitter -> rounding to the second, every observation complete
    t8 = pd.date_range("2024-01-01 00:00", periods=30, freq="8h", tz="UTC")
    jitter = (pd.Series(np.arange(30) % 4 * 3 + 2) * 1).to_numpy()            # 2..11 ms after the settlement
    ms = t8.as_unit("ms").asi8 + jitter
    rates = np.round(np.linspace(-0.0002, 0.0005, 30), 8)
    nat = build_native(pd.DataFrame({"funding_time_ms_raw": ms, "rate": rates, "interval_hours_reported": np.nan}), "rest")
    assert (nat["date"] == t8.as_unit("ns")).all(), "millisecond jitter must round onto the settlement second"
    assert nat["interval_hours"].iloc[1:].eq(8.0).all() and pd.isna(nat["interval_hours"].iloc[0])
    obs = funding_observations(nat)
    assert len(obs) == 30 and obs["n_native"].eq(1).all()
    assert obs["complete"].iloc[1:].all() and not obs["complete"].iloc[0], "first settlement has no known span -> masked"
    assert np.allclose(obs["rate"].iloc[1:], rates[1:]) and not obs["touched_by_interval_change"].any()
    print("  8h regime: jitter rounds onto the second; every observation after the first equals its native rate")

    # 2. interval change 8h -> 4h -> 8h: observations sum the native rates inside (s-8h, s]
    a = pd.date_range("2024-01-01 00:00", "2024-01-02 00:00", freq="8h", tz="UTC")            # 8h regime, ends 01-02 00:00
    b = pd.date_range("2024-01-02 04:00", "2024-01-03 16:00", freq="4h", tz="UTC")            # 4h regime
    c = pd.date_range("2024-01-03 00:00", periods=0, freq="8h", tz="UTC")
    times = a.append(b)
    rr = np.arange(1, len(times) + 1) * 1e-5
    nat2 = _mk_native(times, rr)
    obs2 = funding_observations(nat2)
    seg = interval_segments(nat2)
    assert [s["interval_hours"] for s in seg] == [8.0, 4.0] and describe_native(nat2)["interval_changes"][0]["to_hours"] == 4.0
    # the window (01-02 00:00, 01-02 08:00] holds the 04:00 and 08:00 settlements: complete only if the settlement at 00:00
    # (window start) exists -> it does, so the observation is the sum of two native rates and is 'touched'
    s0 = pd.Timestamp("2024-01-02 08:00", tz="UTC")
    i04, i08 = list(times).index(pd.Timestamp("2024-01-02 04:00", tz="UTC")), list(times).index(s0)
    assert obs2.loc[s0, "complete"] and obs2.loc[s0, "touched_by_interval_change"] and obs2.loc[s0, "n_native"] == 2
    assert abs(obs2.loc[s0, "rate"] - (rr[i04] + rr[i08])) < 1e-15
    # an observation before the change is a plain single native rate
    s1 = pd.Timestamp("2024-01-02 00:00", tz="UTC")
    assert obs2.loc[s1, "n_native"] == 1 and not obs2.loc[s1, "touched_by_interval_change"]
    d = describe_observations(obs2)
    assert d["touched_by_interval_change"] >= 3 and d["masked"] >= 1
    print(f"  interval change 8h->4h: observations sum the native rates in (s-8h, s]; touched={d['touched_by_interval_change']}, masked={d['masked']}")

    # 3. a missing native settlement, visible because the monthly file reports the interval: the window is masked, not dropped
    t4 = pd.date_range("2024-02-01 00:00", periods=12, freq="4h", tz="UTC")
    keep = [k for k in range(12) if k != 5]                                                  # drop the 20:00 settlement
    nat3 = _mk_native(t4[keep], np.full(len(keep), 1e-4), reported=np.full(len(keep), 4.0))
    assert describe_native(nat3)["reported_vs_derived_interval_mismatches"] == 1
    o3 = funding_observations(nat3)
    assert len(o3) == 6, "masked observations stay on the grid (never dropped)"
    ts = lambda x: pd.Timestamp(x, tz="UTC")
    assert o3.loc[ts("2024-02-01 16:00"), "complete"] and o3.loc[ts("2024-02-01 16:00"), "n_native"] == 2
    assert not o3.loc[ts("2024-02-02 00:00"), "complete"] and np.isnan(o3.loc[ts("2024-02-02 00:00"), "rate"]), "window with the hole is masked"
    assert o3["complete"].sum() == 4 and o3.loc[ts("2024-02-02 08:00"), "complete"]
    # without a reported interval the same hole is indistinguishable from an 8h period (the documented limitation)
    nat3b = _mk_native(t4[keep], np.full(len(keep), 1e-4))
    assert funding_observations(nat3b).loc[ts("2024-02-02 00:00"), "complete"]
    print("  missing native settlement: caught through the reported interval (window masked, stays on the grid); documented blind spot without it")

    # 4. merge: new wins, interval recomputed, duplicates removed
    m = merge_native(nat.iloc[:20].copy(), nat.iloc[15:].assign(rate=0.5).copy())
    assert len(m) == 30 and (m["rate"].iloc[15:] == 0.5).all() and (m["rate"].iloc[:15] != 0.5).all() and m["date"].is_unique
    print("  merge_native: overlap resolved in favour of the new rows, no duplicates")

    # 5. parsing: REST rows and monthly CSV variants; an unknown header is an error, never a guess
    p = parse_rest([{"symbol": "ETHUSDT", "fundingTime": 1704067200005, "fundingRate": "0.00010000", "markPrice": "2300.1"},
                    {"symbol": "ETHUSDT", "fundingTime": 1704096000002, "fundingRate": "-0.00002500", "markPrice": "2310.0"}])
    assert p["funding_time_ms_raw"].tolist() == [1704067200005, 1704096000002] and p["rate"].tolist() == [0.0001, -2.5e-05]
    csv3 = "calc_time,funding_interval_hours,last_funding_rate\n1704067200000,8,0.00010000\n1704096000000,8,-0.00002500\n"
    v = parse_vision_csv(csv3)
    assert v["interval_hours_reported"].tolist() == [8.0, 8.0] and v["rate"].tolist() == [0.0001, -2.5e-05]
    csv_us = "calc_time,last_funding_rate\n1704067200000000,0.0001\n"
    assert parse_vision_csv(csv_us)["funding_time_ms_raw"].tolist() == [1704067200000] and parse_vision_csv(csv_us)["interval_hours_reported"].isna().all()
    try:
        parse_vision_csv("a,b,c\n1,2,3\n")
    except ValueError as e:
        assert "unrecognised funding CSV header" in str(e)
    else:
        raise AssertionError("an unknown header must raise")
    print("  parsing: REST rows, monthly CSV with and without the interval column, microsecond times; unknown header raises")

    # 6. tie share (answer A1) on data up to the cutoff, full range separate
    idx = pd.date_range("2025-08-30 00:00", periods=12, freq="8h", tz="UTC")               # crosses the cutoff (08-31 23:59:59)
    rates6 = [1e-4] * 6 + [2e-4, 3e-4] + [1e-4] * 4
    nat6 = _mk_native(idx, rates6)
    o6 = funding_observations(nat6)
    d6 = describe_observations(o6)
    up = o6[o6.index <= DISCOVERY_CUTOFF]["rate"].dropna()
    assert d6["tie_share_up_to_cutoff"]["n"] == len(up) and abs(d6["tie_share_up_to_cutoff"]["tie_share"] - (up.round(12) == 1e-4).mean()) < 1e-12
    assert d6["tie_share_full_range_descriptive"]["n"] == int(o6["rate"].notna().sum())
    assert tie_share([])["tie_share"] is None
    print("  tie share: modal-value fraction, cutoff-limited and full-range reported separately")

    # 7. the whole native -> observations path round-trips through a feather file in the project temp dir
    with tempfile.TemporaryDirectory(dir=_selftest_tmp()) as tmp:
        f = Path(tmp) / "x.feather"
        nat.to_feather(f)
        back = pd.read_feather(f)
        assert list(back.columns) == NATIVE_COLUMNS and (back["date"] == nat["date"]).all()
    print("Self-test passed: funding.py parses, rounds, chains and masks funding settlements as answer A3 specifies.")


if __name__ == "__main__":
    _self_test()
