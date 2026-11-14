"""
Work Order 1.8 (phase E1): the per-market loader with the cutoff and the holdout lock, zero-volume masking, the validation flags, the trading calendar and the data rule.

  * load_symbol(): reads `<pull>/<SYMBOL>.csv` (dates <= CUTOFF_DATE, the discovery file). The loader truncates at the cutoff BEFORE any computation and refuses a
    discovery file that holds a later date. It never opens the holdout folder.
  * The holdout (`<pull>/holdout/<SYMBOL>.csv`, dates after the cutoff) is readable only through read_holdout(), which needs a token from issue_holdout_token():
    one token per frozen candidate manifest (SHA-256), recorded in a ledger, never issued twice (one-shot). Research code never imports read_holdout (static self-test).
  * mask_zero_volume(): a zero-volume bar is a placeholder, not an observation: masked exactly like a missing bar (mistake 21).
  * validate_symbol(): first/last date, rows, missing trading days, duplicate or non-monotone dates, OHLC consistency, zero-volume days, JUMPS (|close/previous close - 1| > 25%).
    Descriptive only; M2 rules each jump (genuine / unadjusted_event / unresolved); a genuine crash is never masked.
  * data_rule(): first candle on or before 2015-08-31, at least 95% of trading days present from the first candle to the cutoff, no unresolved jump flag.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from nse_common import CUTOFF_DATE, sha256_file

JUMP_THRESHOLD = 0.25
FIRST_CANDLE_LIMIT = date(2015, 8, 31)
MIN_PRESENT_SHARE = 0.95
RULINGS = ("genuine", "unadjusted_event", "unresolved")


class HoldoutLocked(PermissionError):
    pass


# ----------------------------------------------------------------------------- discovery loader
def read_raw(path: Path) -> pd.DataFrame:
    """The CSV exactly as stored (no dedupe, no sorting), date as text."""
    df = pd.read_csv(path, dtype={"date": str})
    if list(df.columns) != ["date", "open", "high", "low", "close", "volume"]:
        raise ValueError(f"{path}: unexpected columns {list(df.columns)}")
    return df


def load_symbol(pull_dir: Path, symbol: str) -> pd.DataFrame:
    """Discovery rows of one symbol, indexed by date (datetime64), ascending. Truncates at the cutoff before returning anything; a file that holds a later date is refused."""
    path = Path(pull_dir) / f"{symbol}.csv"
    raw = read_raw(path)
    if (raw["date"] > CUTOFF_DATE.isoformat()).any():
        raise ValueError(f"{path} holds dates after the cutoff {CUTOFF_DATE}: discovery files must be truncated at write time")
    df = raw.copy()
    df.index = pd.to_datetime(df["date"])
    df = df.drop(columns=["date"]).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df[df.index <= pd.Timestamp(CUTOFF_DATE)]


def mask_zero_volume(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Zero-volume bars become missing bars (open/high/low/close NaN); returns the masked frame (with a boolean `present`) and the number masked."""
    out = df.copy()
    zero = out["volume"].fillna(0) == 0
    out.loc[zero, ["open", "high", "low", "close"]] = np.nan
    out["present"] = out[["open", "high", "low", "close"]].notna().all(axis=1)
    return out, int(zero.sum())


# ----------------------------------------------------------------------------- holdout lock
def issue_holdout_token(frozen_manifest_sha256: str, ledger: Path) -> dict:
    """One-shot: the token for the holdout of ONE frozen candidate manifest. A second request for the same manifest is refused."""
    if not re.fullmatch(r"[0-9a-f]{64}", frozen_manifest_sha256 or ""):
        raise HoldoutLocked("a frozen candidate manifest SHA-256 is required")
    ledger = Path(ledger)
    used = [json.loads(ln)["manifest"] for ln in ledger.read_text().splitlines() if ln.strip()] if ledger.exists() else []
    if frozen_manifest_sha256 in used:
        raise HoldoutLocked("the holdout for this frozen candidate was already unlocked (one-shot)")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a") as fh:
        fh.write(json.dumps({"manifest": frozen_manifest_sha256}) + "\n")
    return {"manifest": frozen_manifest_sha256, "_issued_by": "nse_loader.issue_holdout_token"}


def read_holdout(pull_dir: Path, symbol: str, token: dict | None = None) -> pd.DataFrame:
    """Holdout rows (dates after the cutoff) of one symbol. Only the forward-test command may call this, with a token from issue_holdout_token()."""
    if not isinstance(token, dict) or token.get("_issued_by") != "nse_loader.issue_holdout_token" or not re.fullmatch(r"[0-9a-f]{64}", str(token.get("manifest", ""))):
        raise HoldoutLocked("the holdout is locked: only the forward-test command, holding a token for a frozen candidate, may read it")
    df = read_raw(Path(pull_dir) / "holdout" / f"{symbol}.csv")
    if (df["date"] <= CUTOFF_DATE.isoformat()).any():
        raise ValueError("a holdout file holds a date on or before the cutoff")
    df.index = pd.to_datetime(df["date"])
    return df.drop(columns=["date"]).sort_index()


# ----------------------------------------------------------------------------- calendar, validation, data rule
def trading_calendar(frames: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    """The dates on which at least half of the pulled symbols have a candle (a zero-volume candle still counts as a candle: the calendar is about the exchange being open)."""
    counts = pd.concat([pd.Series(1, index=f.index[~f.index.duplicated()]) for f in frames.values()]).groupby(level=0).sum()
    return list(counts[counts >= len(frames) / 2.0].index)


def validate_symbol(raw: pd.DataFrame, calendar: list[pd.Timestamp]) -> dict:
    """Descriptive validation of one symbol from the stored CSV (raw order, raw duplicates). Returns facts and a list of flags {flag, date, detail}."""
    flags: list[dict] = []
    dates = pd.to_datetime(raw["date"])
    dup = raw["date"][raw["date"].duplicated(keep=False)]
    for d in sorted(set(dup)):
        flags.append({"flag": "duplicate_date", "date": d, "detail": f"{int((raw['date'] == d).sum())} rows"})
    nonmono = [str(raw["date"].iloc[i]) for i in range(1, len(raw)) if raw["date"].iloc[i] <= raw["date"].iloc[i - 1] and raw["date"].iloc[i] != raw["date"].iloc[i - 1]]
    for d in nonmono:
        flags.append({"flag": "non_monotone_date", "date": d, "detail": "earlier than the previous row"})
    df = raw.copy()
    df.index = dates
    df = df[~df.index.duplicated(keep="first")].sort_index()
    for ts, r in df.iterrows():
        o, h, l, c = r["open"], r["high"], r["low"], r["close"]
        if not (l > 0 and o > 0 and h > 0 and c > 0 and l <= o <= h and l <= c <= h):
            flags.append({"flag": "ohlc_inconsistent", "date": ts.date().isoformat(), "detail": f"o={o} h={h} l={l} c={c}"})
        if r["volume"] == 0:
            flags.append({"flag": "zero_volume", "date": ts.date().isoformat(), "detail": "placeholder, masked like a missing bar"})
    ret = df["close"].pct_change()
    for ts, v in ret[ret.abs() > JUMP_THRESHOLD].items():
        flags.append({"flag": "jump", "date": ts.date().isoformat(), "detail": f"return {v:+.4f}, volume {int(df.loc[ts, 'volume'])}"})
    cal = [d for d in calendar if df.index[0] <= d <= df.index[-1]] if len(df) else []
    missing = [d for d in cal if d not in df.index]
    for d in missing[:500]:
        flags.append({"flag": "missing_day", "date": d.date().isoformat(), "detail": "trading-calendar date without a candle"})
    return {"rows": int(len(df)), "first_date": df.index[0].date().isoformat() if len(df) else None, "last_date": df.index[-1].date().isoformat() if len(df) else None,
            "missing_trading_days": len(missing), "calendar_days_in_span": len(cal), "flags": flags,
            "counts": {k: sum(1 for f in flags if f["flag"] == k) for k in ("duplicate_date", "non_monotone_date", "ohlc_inconsistent", "zero_volume", "jump", "missing_day")}}


def data_rule(report: dict, calendar: list[pd.Timestamp], rulings: dict[str, str] | None = None) -> tuple[bool, list[str]]:
    """Work Order 1.8: first candle on or before 2015-08-31; at least 95% of the trading days from the first candle to the cutoff present; no unresolved jump flag.
    `rulings` maps a jump date (ISO) to genuine / unadjusted_event / unresolved; a jump without a ruling is unresolved; only 'genuine' keeps the symbol
    (an unadjusted split makes the price series unusable as delivered). Zero-volume days count as NOT present (they are masked)."""
    reasons = []
    rulings = rulings or {}
    if report["first_date"] is None or date.fromisoformat(report["first_date"]) > FIRST_CANDLE_LIMIT:
        reasons.append(f"first candle {report['first_date']} is after {FIRST_CANDLE_LIMIT}")
    span = [d for d in calendar if report["first_date"] and pd.Timestamp(report["first_date"]) <= d <= pd.Timestamp(CUTOFF_DATE)]
    zero_days = {f["date"] for f in report["flags"] if f["flag"] == "zero_volume"}
    missing = {f["date"] for f in report["flags"] if f["flag"] == "missing_day"}
    present = len([d for d in span if d.date().isoformat() not in zero_days and d.date().isoformat() not in missing]) if span else 0
    share = present / len(span) if span else 0.0
    if share < MIN_PRESENT_SHARE:
        reasons.append(f"present share {share:.3f} of {len(span)} trading days is below {MIN_PRESENT_SHARE}")
    for f in report["flags"]:
        if f["flag"] == "jump":
            r = rulings.get(f["date"], "unresolved")
            if r != "genuine":
                reasons.append(f"jump on {f['date']} ({f['detail']}) is {r}")
    return (not reasons), reasons


# ----------------------------------------------------------------------------- self-test
def _synthetic(n_days=900, start="2013-01-01", seed=1, jump_at=None, zero_at=(), missing_at=()):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n_days)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n_days)))
    if jump_at is not None:
        c[jump_at:] *= 0.5
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.002, "low": np.minimum(o, c) * 0.998, "close": c, "volume": rng.integers(1000, 5000, n_days)}, index=idx)
    for i in zero_at:
        df.iloc[i, df.columns.get_loc("volume")] = 0
    return df.drop(index=idx[list(missing_at)]) if len(missing_at) else df


def _to_raw(df: pd.DataFrame) -> pd.DataFrame:
    r = df.reset_index().rename(columns={"index": "date"})
    r["date"] = r["date"].dt.strftime("%Y-%m-%d")
    return r[["date", "open", "high", "low", "close", "volume"]]


def _self_test() -> None:
    import tempfile

    from nse_common import write_pull

    full = _synthetic(n_days=700, start="2023-06-01", seed=2)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rows = [(str(d.date()), r.open, r.high, r.low, r.close, int(r.volume)) for d, r in full.iterrows()]
        assert max(full.index.date) > CUTOFF_DATE, "the synthetic series must run past the cutoff"
        m = write_pull(tmp / "pull-1", {"AAA": rows}, "2026-11-06T00:00:00Z", "test")
        # discovery loader: truncated, ascending, no holdout dates
        d = load_symbol(tmp / "pull-1", "AAA")
        assert d.index.max() <= pd.Timestamp(CUTOFF_DATE) and d.index.is_monotonic_increasing and len(d) == m["symbols"]["AAA"]["rows"]
        # a discovery file with a later date is refused
        bad = tmp / "pull-bad"
        bad.mkdir()
        (bad / "AAA.csv").write_text("date,open,high,low,close,volume\n2025-08-29,1,1,1,1,5\n2025-09-01,1,1,1,1,5\n")
        try:
            load_symbol(bad, "AAA")
        except ValueError as e:
            assert "after the cutoff" in str(e)
        else:
            raise AssertionError("a discovery file with a post-cutoff date must be refused")
        # holdout lock
        for token in (None, {}, {"manifest": "a" * 64}, {"manifest": "zz", "_issued_by": "nse_loader.issue_holdout_token"}):
            try:
                read_holdout(tmp / "pull-1", "AAA", token)
            except HoldoutLocked:
                pass
            else:
                raise AssertionError(f"holdout read without a valid token: {token}")
        led = tmp / "ledger.jsonl"
        tok = issue_holdout_token("b" * 64, led)
        h = read_holdout(tmp / "pull-1", "AAA", tok)
        assert h.index.min() > pd.Timestamp(CUTOFF_DATE) and len(h) == m["holdout"]["AAA"]["rows"]
        for bad_manifest in ("short", None):
            try:
                issue_holdout_token(bad_manifest, led)
            except HoldoutLocked:
                pass
            else:
                raise AssertionError("a token needs a frozen manifest hash")
        try:
            issue_holdout_token("b" * 64, led)
        except HoldoutLocked as e:
            assert "one-shot" in str(e)
        else:
            raise AssertionError("the holdout token is one-shot per frozen candidate")
        # static scan: no research module (everything except this one) calls read_holdout or opens a holdout file
        here = Path(__file__).resolve().parent
        offenders = [p.name for p in here.glob("*.py") if p.name not in ("nse_loader.py",) and not p.name.startswith("nse_forward_test")
                     and re.search(r"\bread_holdout\s*\(|\bissue_holdout_token\s*\(", p.read_text())]
        assert offenders == [], f"modules that call the NSE holdout reader: {offenders}"
    # masking
    z = _synthetic(n_days=60, seed=3, zero_at=(10, 11, 40))
    mz, nz = mask_zero_volume(z)
    assert nz == 3 and int((~mz["present"]).sum()) == 3 and mz.iloc[10][["open", "high", "low", "close"]].isna().all() and mz["present"].iloc[12]
    # validation flags on a series with a crash, a zero-volume day, a missing day and an inconsistent bar
    calendar = list(pd.bdate_range("2012-01-02", periods=1200))
    s0 = _synthetic(n_days=1200, start="2012-01-02", seed=4, jump_at=300, zero_at=(50,))
    jump_date = str(s0.index[300].date())
    s = s0.drop(index=s0.index[[100]])
    s.iloc[200, s.columns.get_loc("low")] = s.iloc[200]["high"] * 1.1  # low above high
    raw = _to_raw(s)
    rep = validate_symbol(raw, calendar)
    c = rep["counts"]
    assert c["jump"] == 1 and c["zero_volume"] == 1 and c["missing_day"] == 1 and c["ohlc_inconsistent"] == 1 and c["duplicate_date"] == 0 and c["non_monotone_date"] == 0, c
    jump = [f for f in rep["flags"] if f["flag"] == "jump"][0]
    ret = float(re.search(r"return ([+-][0-9.]+)", jump["detail"]).group(1))
    assert jump["date"] == jump_date and -0.56 < ret < -0.44, "a -50% crash is flagged, never masked"
    dup = pd.concat([raw, raw.iloc[[5]]], ignore_index=True)
    assert validate_symbol(dup, calendar)["counts"]["duplicate_date"] == 1
    shuffled = raw.copy()
    shuffled.iloc[[7, 8]] = shuffled.iloc[[8, 7]].values
    assert validate_symbol(shuffled, calendar)["counts"]["non_monotone_date"] >= 1
    # the calendar: dates on which at least half of the symbols have a candle
    fa, fb, fc = _synthetic(60, seed=5), _synthetic(60, seed=6, missing_at=(3,)), _synthetic(60, seed=7)
    cal = trading_calendar({"A": fa, "B": fb, "C": fc})
    assert fa.index[3] in cal, "1 of 3 symbols missing: still at least half"
    cal2 = trading_calendar({"A": fa.drop(index=fa.index[3]), "B": fb, "C": fc})
    assert fa.index[3] not in cal2, "2 of 3 symbols missing: not a trading day"
    # the data rule
    ok_series = _synthetic(n_days=1200, start="2012-01-02", seed=8)
    r_ok = validate_symbol(_to_raw(ok_series[ok_series.index <= pd.Timestamp(CUTOFF_DATE)]), [d for d in calendar if d <= pd.Timestamp(CUTOFF_DATE)])
    assert data_rule(r_ok, calendar)[0]
    late = _synthetic(n_days=900, start="2016-03-01", seed=9)
    cal_late = list(pd.bdate_range("2012-01-02", "2025-08-29"))
    r_late = validate_symbol(_to_raw(late[late.index <= pd.Timestamp(CUTOFF_DATE)]), cal_late)
    ok_l, why_l = data_rule(r_late, cal_late)
    assert not ok_l and any("first candle" in w for w in why_l)
    gappy = _synthetic(n_days=1100, start="2012-01-02", seed=10, missing_at=tuple(range(200, 280)))
    r_g = validate_symbol(_to_raw(gappy), list(pd.bdate_range("2012-01-02", periods=1100)))
    ok_g, why_g = data_rule(r_g, list(pd.bdate_range("2012-01-02", periods=1100)))
    assert not ok_g and any("present share" in w for w in why_g)
    cal_j = list(pd.bdate_range("2012-01-02", periods=1200))
    r_j = validate_symbol(raw, cal_j)
    assert not data_rule(r_j, cal_j)[0]
    ok_ruled, why_ruled = data_rule(r_j, cal_j, {jump["date"]: "genuine"})
    assert all("jump" not in w for w in why_ruled), "a genuine ruling clears the jump flag (other reasons may remain)"
    assert any("unadjusted_event" in w for w in data_rule(r_j, cal_j, {jump["date"]: "unadjusted_event"})[1]) and any("unresolved" in w for w in data_rule(r_j, cal_j, {jump["date"]: "unresolved"})[1])
    print("Self-test passed: nse_loader truncates at 2025-08-31 and refuses a discovery file with a later date, locks the holdout behind a one-shot token tied to a frozen manifest hash (static scan: no research module touches it), "
          "masks zero-volume bars like missing bars, flags jumps (a -50% crash is flagged, never masked), zero volume, missing days, OHLC problems and duplicate or non-monotone dates, builds the half-of-symbols trading calendar and applies the data rule.")


if __name__ == "__main__":
    _self_test()
