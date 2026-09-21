"""
Task 0 report (work order #1): what data do we actually have?

Read-only. Writes results/task0_report.json and prints a summary that
answers the Task 0 questions with numbers, not impressions:

  1. History per timeframe: first/last bar, rows, days spanned, literal
     missing bars vs a regular grid, flat (zero-volume) rows.
  2. The planning cost model (from costs.py) and exchange filters (from fetch_klines.py's
     symbol_filters.json, if it has been run).
  3. Structural break (2026-01-29): how many bars of each file are before
     the break, ON the break day, and after it. Reported as three counts --
     the report does not decide where "post-break" starts; the caller does.
  4. 1d bars resampled from 1m vs the native 1d file, restricted to days the
     1m file covers completely; every mismatch is classified as "day contains
     a missing 1m bar / flat row" (explained) or not (unexplained = a bug).
  5. Raw-kline store vs freqtrade file for ETH_FDUSD 1m (if fetch_klines has
     been run): are they the same bars? Which rows exist in only one?
  6. How many walk-forward splits each candidate window setting yields on
     each file (and on its post-break portion).

Usage:
    python3 task0_report.py --data-dir ../data/binance --raw-dir ../data/binance_raw
(from user_data/analysis; or pass paths from the repo root)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import costs
from resample import resample_ohlcv
from walkforward import generate_walk_forward_splits

TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "1d", "1w")
STEP = {
    "1m": pd.Timedelta(minutes=1), "5m": pd.Timedelta(minutes=5), "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30), "1h": pd.Timedelta(hours=1), "1d": pd.Timedelta(days=1),
    "1w": pd.Timedelta(days=7),
}
# Work order #1: treat 2026-01-29 (the day taker fees returned for everyone) as a structural break.
BREAK_DAY = pd.Timestamp("2026-01-29", tz="UTC")
AFTER_BREAK_DAY = BREAK_DAY + pd.Timedelta(days=1)
WINDOW_SETTINGS = {"fit90_validate30": (90, 30), "fit270_validate90": (270, 90)}


def load(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df.set_index("date").sort_index()


def flat_mask(df: pd.DataFrame) -> pd.Series:
    """Project definition (stats_fingerprint.flat_candle_fraction): O==H==L==C and volume==0."""
    return (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"]) & (df["volume"] == 0)


def describe_series(df: pd.DataFrame, tf: str) -> dict:
    step = STEP[tf]
    first, last = df.index.min(), df.index.max()
    expected = int((last - first) / step) + 1
    flat = flat_mask(df)
    out = {
        "rows": int(len(df)),
        "first": str(first), "last": str(last),
        "days_spanned": round((last - first).total_seconds() / 86400, 2),
        "expected_rows_regular_grid": expected,
        "missing_bars_literal_gaps": expected - int(len(df.index.unique())),
        "duplicate_timestamps": int(df.index.duplicated().sum()),
        "sorted": bool(df.index.is_monotonic_increasing),
        "flat_zero_volume_rows": int(flat.sum()),
        "flat_fraction": round(float(flat.mean()), 5),
        "rows_before_break_day": int((df.index < BREAK_DAY).sum()),
        "rows_on_break_day": int(((df.index >= BREAK_DAY) & (df.index < AFTER_BREAK_DAY)).sum()),
        "rows_after_break_day": int((df.index >= AFTER_BREAK_DAY).sum()),
        "entirely_after_break": bool(first >= AFTER_BREAK_DAY),
        "columns": list(df.columns),
    }
    if tf in ("1d", "1w"):
        out["all_bars_open_at_00_00_utc"] = bool(((df.index.hour == 0) & (df.index.minute == 0)).all())
    if tf == "1w":
        out["all_weekly_bars_open_on_monday"] = bool((df.index.dayofweek == 0).all())
    if "n_trades" in df.columns:
        out["bars_with_zero_trades"] = int((df["n_trades"] == 0).sum())
    return out


def walkforward_capacity(first: pd.Timestamp, last: pd.Timestamp) -> dict:
    out = {}
    for name, (fit, val) in WINDOW_SETTINGS.items():
        out[name] = len(generate_walk_forward_splits(first, last, pd.Timedelta(days=fit), pd.Timedelta(days=val)))
    return out


def daily_from_1m_check(df_1m: pd.DataFrame, native_1d: pd.DataFrame, tol: float = 1e-6, vol_tol: float = 1e-3) -> dict:
    """Resample 1m -> 1d and diff against the native 1d file, only for days the
    1m file covers from 00:00 to 23:59 (a partial first/last day can't match)."""
    first_full = df_1m.index.min().ceil("D")
    last_full = (df_1m.index.max() + pd.Timedelta(minutes=1)).floor("D") - pd.Timedelta(days=1)
    if last_full < first_full:
        return {"status": "NO_COMPLETE_DAY_IN_1M"}
    resampled = resample_ohlcv(df_1m, "1d").loc[first_full:last_full]
    native = native_1d.loc[first_full:last_full]
    common = resampled.index.intersection(native.index)
    grid = pd.date_range(first_full, last_full, freq="1D", tz="UTC")
    missing_1m = pd.date_range(df_1m.index.min(), df_1m.index.max(), freq="1min", tz="UTC").difference(df_1m.index)
    gap_days = pd.Series(missing_1m.floor("D")).value_counts()
    # A flat placeholder row can only distort a daily bar at its EDGES (a leading
    # flat row makes the resampled open/high/low the previous close instead of the
    # first real trade; a trailing one does the same to the close). Flat rows in
    # the interior of a day change nothing, and with ~12% flat minutes nearly
    # every day has some, so "day contains a flat row" would explain everything.
    fm = flat_mask(df_1m)
    by_day = fm.groupby(df_1m.index.floor("D"))
    edge_flat_days = (by_day.first() | by_day.last())
    flat_days = by_day.sum()

    bad = {}
    for col, t in (("open", tol), ("high", tol), ("low", tol), ("close", tol), ("volume", vol_tol)):
        diff = (resampled.loc[common, col] - native.loc[common, col]).abs()
        rel = diff / native.loc[common, col].replace(0, pd.NA)
        for day in diff[(diff > t) & (rel.fillna(1) > t)].index:
            bad.setdefault(day, []).append(col)
    explained = {d: c for d, c in bad.items() if gap_days.get(d, 0) > 0 or bool(edge_flat_days.get(d, False))}
    unexplained = {d: c for d, c in bad.items() if d not in explained}
    def show(dct):
        return [{"day": str(d.date()), "columns": cols, "missing_1m_minutes": int(gap_days.get(d, 0)),
                 "first_or_last_1m_row_flat": bool(edge_flat_days.get(d, False)),
                 "flat_1m_rows_in_day": int(flat_days.get(d, 0))} for d, cols in list(dct.items())[:15]]
    return {
        "status": "MATCH" if not bad else "MISMATCH",
        "complete_days_checked": int(len(common)),
        "complete_days_in_1m_range": int(len(grid)),
        "days_missing_from_native_1d": int(len(grid.difference(native.index))),
        "days_missing_from_resampled_1d": int(len(grid.difference(resampled.index))),
        "mismatched_days": int(len(bad)),
        "mismatched_days_with_missing_1m_minutes_or_flat_edge_row": int(len(explained)),
        "mismatched_days_UNEXPLAINED": int(len(unexplained)),
        "examples_explained": show(explained),
        "examples_unexplained": show(unexplained),
    }


def raw_vs_freqtrade(ft: pd.DataFrame, raw: pd.DataFrame) -> dict:
    lo, hi = max(ft.index.min(), raw.index.min()), min(ft.index.max(), raw.index.max())
    ft_r, raw_r = ft.loc[lo:hi], raw.loc[lo:hi]
    common = ft_r.index.intersection(raw_r.index)
    only_ft = ft_r.index.difference(raw_r.index)
    only_raw = raw_r.index.difference(ft_r.index)
    mism = {}
    for col in ("open", "high", "low", "close", "volume"):
        d = (ft_r.loc[common, col] - raw_r.loc[common, col]).abs()
        n = int((d > 1e-9).sum())
        if n:
            mism[col] = {"rows": n, "max_abs_diff": float(d.max()), "first_ts": str(d[d > 1e-9].index[0])}
    only_ft_flat = int(flat_mask(ft_r.loc[only_ft]).sum()) if len(only_ft) else 0
    result = {
        "compared_range": [str(lo), str(hi)],
        "common_rows": int(len(common)),
        "rows_only_in_freqtrade_file": int(len(only_ft)),
        "of_which_flat_zero_volume": only_ft_flat,
        "rows_only_in_raw_store": int(len(only_raw)),
        "ohlcv_mismatches_on_common_rows": mism,
        "identical_on_common_rows": not mism,
    }
    if "n_trades" in raw_r.columns and len(common):
        zero_trade_common = int((raw_r.loc[common, "n_trades"] == 0).sum())
        result["raw_bars_with_zero_trades_on_common_rows"] = zero_trade_common
    return result


SEAM = pd.Timestamp("2026-03-19", tz="UTC")   # where the original 1m download began; the 2026-01-30 extension is joined here


def seam_check(df: pd.DataFrame, seam: pd.Timestamp = SEAM, window_days: int = 1) -> dict:
    """Work order 1.1 seam check: bars on both sides of the join, exactly one minute apart, no
    duplicate and no missing bar in a window around it."""
    lo, hi = seam - pd.Timedelta(days=window_days), seam + pd.Timedelta(days=window_days)
    win = df.loc[(df.index >= lo) & (df.index < hi)]
    grid = pd.date_range(lo, hi - pd.Timedelta(minutes=1), freq="1min", tz="UTC")
    before, after = df.index[df.index < seam], df.index[df.index >= seam]
    ok_pair = bool(len(before) and len(after) and after[0] == seam and before[-1] == seam - pd.Timedelta(minutes=1))
    return {
        "seam": str(seam),
        "bar_before_seam_present": bool(len(before) and before[-1] == seam - pd.Timedelta(minutes=1)),
        "bar_at_seam_present": bool(len(after) and after[0] == seam),
        "consecutive_across_seam": ok_pair,
        "duplicates_in_window": int(win.index.duplicated().sum()),
        "missing_bars_in_window": int(len(grid.difference(win.index))),
        "window": [str(lo), str(hi)],
        "rows_before_seam": int(len(before)), "rows_from_seam": int(len(after)),
    }


def overlap_with_previous(previous: pd.DataFrame, current: pd.DataFrame) -> dict:
    """The extended file must contain every bar of the previous file, identical in OHLCV."""
    common = previous.index.intersection(current.index)
    lost = int(len(previous.index.difference(current.index)))
    mism = {}
    for col in ("open", "high", "low", "close", "volume"):
        d = (previous.loc[common, col] - current.loc[common, col]).abs()
        if (d > 1e-9).any():
            mism[col] = int((d > 1e-9).sum())
    return {"previous_rows": int(len(previous)), "current_rows": int(len(current)),
            "previous_rows_missing_from_current": lost, "ohlcv_mismatches_on_overlap": mism,
            "new_rows_before_previous_start": int((current.index < previous.index.min()).sum()),
            "identical_on_overlap": bool(lost == 0 and not mism)}


def monthly_flat(df: pd.DataFrame) -> dict:
    """Share of flat (zero-trade) minutes per calendar month -- a regime check. Overall flat %
    can hide a level shift inside the sample (ETH/FDUSD 1m: about 1% before 2026-03-19, about
    12% after)."""
    fm = flat_mask(df)
    g = fm.groupby(df.index.strftime("%Y-%m"))
    return {m: {"rows": int(len(x)), "flat": int(x.sum()), "flat_fraction": round(float(x.mean()), 5)} for m, x in g}


def build_report(data_dir: Path, raw_dir: Path, pair: str, previous_1m: Path | None = None) -> dict:
    report: dict = {"pair": pair, "break_day": str(BREAK_DAY.date()),
                    "cost_model": costs.describe(),
                    "freqtrade_files": {}, "raw_store_files": {}, "warnings": []}
    frames: dict[str, pd.DataFrame] = {}
    for tf in TIMEFRAMES:
        df = load(data_dir / f"{pair}-{tf}.feather")
        if df is None:
            report["freqtrade_files"][tf] = {"status": "FILE_NOT_FOUND"}
            continue
        frames[tf] = df
        d = describe_series(df, tf)
        d["walkforward_splits_full_history"] = walkforward_capacity(df.index.min(), df.index.max())
        post = df.loc[df.index >= AFTER_BREAK_DAY]
        d["walkforward_splits_after_break"] = (
            walkforward_capacity(post.index.min(), post.index.max()) if len(post) else {k: 0 for k in WINDOW_SETTINGS})
        report["freqtrade_files"][tf] = d

    if raw_dir.exists():
        for f in sorted(raw_dir.glob("*.feather")):
            tf = f.stem.rsplit("-", 1)[-1]
            df = load(f)
            if df is not None and tf in STEP:
                report["raw_store_files"][f.stem] = describe_series(df, tf)
        filt = raw_dir / "symbol_filters.json"
        if filt.exists():
            report["exchange_filters"] = {
                s: {k: v[k] for k in ("tickSize", "stepSize", "minNotional", "limit_maker_supported", "status")}
                for s, v in json.loads(filt.read_text())["symbols"].items()}
        raw_1m = load(raw_dir / f"{pair}-1m.feather")
        if raw_1m is not None and "1m" in frames:
            report["raw_vs_freqtrade_1m"] = raw_vs_freqtrade(frames["1m"], raw_1m)

    if "1m" in frames and "1d" in frames:
        report["daily_from_1m_vs_native_1d"] = daily_from_1m_check(frames["1m"], frames["1d"])
    if "1m" in frames:
        report["monthly_flat_fraction"] = {f"{pair}_1m": monthly_flat(frames["1m"])}
        fd = load(raw_dir / "FDUSD_USDT-1m.feather")
        if fd is not None:
            report["monthly_flat_fraction"]["FDUSD_USDT_1m"] = monthly_flat(fd)

    # Seam check (work order 1.1): only meaningful once a 1m file reaches back before the seam.
    seams = {}
    for name, df in [("freqtrade_ETH_FDUSD_1m", frames.get("1m"))] + [
            (f"raw_{k}", load(raw_dir / f"{k}.feather")) for k in ("ETH_FDUSD-1m", "ETH_USDT-1m", "FDUSD_USDT-1m")]:
        if df is not None and df.index.min() < SEAM:
            seams[name] = seam_check(df)
    if seams:
        report["seam_check"] = seams
    if previous_1m is not None and "1m" in frames:
        prev = load(previous_1m)
        if prev is not None:
            report["extension_vs_previous_file"] = {"previous_file": str(previous_1m), **overlap_with_previous(prev, frames["1m"])}

    # ---- warnings: things a reader must not miss --------------------------------------------
    w = report["warnings"]
    if "1m" in frames:
        d1 = report["freqtrade_files"]["1m"]
        for tf, d in report["freqtrade_files"].items():
            if tf == "1m" or "rows" not in d:
                continue
            if pd.Timestamp(d["first"]) < pd.Timestamp(d1["first"]) - pd.Timedelta(days=7):
                w.append(f"{tf} history starts {d['first'][:10]} but 1m starts {d1['first'][:10]}: every result "
                         f"pairing {tf} with 1m is only as long as the 1m file.")
        if d1["missing_bars_literal_gaps"] > 0:
            w.append(f"1m file has {d1['missing_bars_literal_gaps']} literal missing minutes "
                     f"({d1['flat_zero_volume_rows']} flat rows are present as placeholders).")
    for tf, d in report["freqtrade_files"].items():
        if "rows" in d and not d["entirely_after_break"]:
            w.append(f"{tf}: {d['rows_before_break_day']} rows before {report['break_day']}, {d['rows_on_break_day']} on the "
                     f"break day, {d['rows_after_break_day']} after -- NOT entirely post-break.")
    dd = report.get("daily_from_1m_vs_native_1d", {})
    if dd.get("mismatched_days_UNEXPLAINED"):
        w.append(f"{dd['mismatched_days_UNEXPLAINED']} day(s) mismatch between 1m-resampled and native 1d with NO missing 1m "
                 f"minute or flat edge row to explain it -- investigate before trusting daily bars.")
    for name, sc in report.get("seam_check", {}).items():
        if not (sc["consecutive_across_seam"] and sc["duplicates_in_window"] == 0 and sc["missing_bars_in_window"] == 0):
            w.append(f"SEAM PROBLEM in {name}: {sc}")
    ev = report.get("extension_vs_previous_file")
    if ev and not ev["identical_on_overlap"]:
        w.append(f"the extended 1m file does NOT reproduce the previous file exactly: {ev}")
    rv = report.get("raw_vs_freqtrade_1m")
    if rv and not rv["identical_on_common_rows"]:
        w.append("raw-kline store and freqtrade 1m file disagree on common rows -- see raw_vs_freqtrade_1m.")
    return report


def print_summary(rep: dict) -> None:
    print(f"=== Task 0 report: {rep['pair']} ===\n")
    cm = rep["cost_model"]
    print(f"Cost model (planning, {cm['execution']}): base {cm['cases']['base']['round_trip']:.2%} round trip "
          f"(fee {cm['cases']['base']['fee_per_side']:.2%} + slippage {cm['cases']['base']['slippage_per_side']:.2%} per side), "
          f"stress {cm['cases']['stress']['round_trip']:.2%}.\n  {cm['note']}")
    if "exchange_filters" in rep:
        for s, f in rep["exchange_filters"].items():
            print(f"Filters {s}: tick={f['tickSize']} step={f['stepSize']} minNotional={f['minNotional']} "
                  f"LIMIT_MAKER={'yes' if f['limit_maker_supported'] else 'NO'}")
    print(f"\nHistory (freqtrade files). Break day = {rep['break_day']}; splits shown for fit/validate = 90/30 and 270/90 days")
    print(f"{'tf':4s} {'first':12s} {'last':12s} {'rows':>9s} {'days':>7s} {'missing':>8s} {'flat%':>6s} "
          f"{'pre':>8s} {'break':>6s} {'post':>8s}  splits(full) splits(post-break)")
    for tf, d in rep["freqtrade_files"].items():
        if "rows" not in d:
            print(f"{tf:4s} {d['status']}")
            continue
        wf, wp = d["walkforward_splits_full_history"], d["walkforward_splits_after_break"]
        print(f"{tf:4s} {d['first'][:10]:12s} {d['last'][:10]:12s} {d['rows']:9d} {d['days_spanned']:7.1f} "
              f"{d['missing_bars_literal_gaps']:8d} {100 * d['flat_fraction']:6.2f} {d['rows_before_break_day']:8d} "
              f"{d['rows_on_break_day']:6d} {d['rows_after_break_day']:8d}  "
              f"{wf['fit90_validate30']:>3d}/{wf['fit270_validate90']:<3d}        {wp['fit90_validate30']:>3d}/{wp['fit270_validate90']:<3d}")
    if rep["raw_store_files"]:
        print("\nRaw-kline store:")
        for name, d in rep["raw_store_files"].items():
            print(f"  {name:18s} {d['first'][:10]} .. {d['last'][:10]}  rows={d['rows']:>9d}  missing={d['missing_bars_literal_gaps']:>7d}"
                  + (f"  zero-trade bars={d['bars_with_zero_trades']}" if "bars_with_zero_trades" in d else ""))
    if "raw_vs_freqtrade_1m" in rep:
        r = rep["raw_vs_freqtrade_1m"]
        print(f"\nRaw vs freqtrade ETH_FDUSD 1m over {r['compared_range'][0][:16]} .. {r['compared_range'][1][:16]}: "
              f"common={r['common_rows']}, only-in-freqtrade={r['rows_only_in_freqtrade_file']} "
              f"(of which flat placeholders: {r['of_which_flat_zero_volume']}), only-in-raw={r['rows_only_in_raw_store']}, "
              f"OHLCV identical on common rows: {r['identical_on_common_rows']}")
    if "daily_from_1m_vs_native_1d" in rep:
        d = rep["daily_from_1m_vs_native_1d"]
        print(f"\n1d built from 1m vs native 1d: {d['status']} -- {d.get('complete_days_checked')} complete days checked, "
              f"{d.get('mismatched_days')} mismatched ({d.get('mismatched_days_with_missing_1m_minutes_or_flat_edge_row')} explained by "
              f"missing 1m minutes or a flat first/last row, {d.get('mismatched_days_UNEXPLAINED')} unexplained)")
    for name, months in rep.get("monthly_flat_fraction", {}).items():
        print(f"\nFlat (zero-trade) minute share by month, {name}: " + "  ".join(f"{m}:{v['flat_fraction']:.1%}" for m, v in months.items()))
    for name, sc in rep.get("seam_check", {}).items():
        print(f"\nSeam {name}: consecutive across {sc['seam'][:10]}: {sc['consecutive_across_seam']}, duplicates={sc['duplicates_in_window']}, "
              f"missing in +-1 day window={sc['missing_bars_in_window']}, rows before/after seam={sc['rows_before_seam']}/{sc['rows_from_seam']}")
    if "extension_vs_previous_file" in rep:
        e = rep["extension_vs_previous_file"]
        print(f"Extension vs previous file: identical on overlap={e['identical_on_overlap']}, previous rows lost={e['previous_rows_missing_from_current']}, "
              f"new rows before old start={e['new_rows_before_previous_start']}")
    print("\nWARNINGS:" if rep["warnings"] else "\nNo warnings.")
    for x in rep["warnings"]:
        print(f"  - {x}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("user_data/data/binance"))
    ap.add_argument("--raw-dir", type=Path, default=None)
    ap.add_argument("--pair", default="ETH_FDUSD")
    ap.add_argument("--output-dir", type=Path, default=Path("user_data/analysis/results"))
    ap.add_argument("--previous-1m", type=Path, default=None,
                    help="the pre-extension 1m file (e.g. the .bak that fetch_klines --export-freqtrade leaves) to prove the "
                         "extended file reproduces it exactly on the overlap")
    args = ap.parse_args()
    raw_dir = args.raw_dir or args.data_dir.parent / "binance_raw"
    rep = build_report(args.data_dir, raw_dir, args.pair, previous_1m=args.previous_1m)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "task0_report.json").write_text(json.dumps(rep, indent=2, default=str))
    print_summary(rep)
    print(f"\nWritten: {args.output_dir / 'task0_report.json'}")


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        import tempfile
        import numpy as np

        rng = np.random.default_rng(5)
        n = 45 * 1440
        idx = pd.date_range("2026-03-01", periods=n, freq="1min", tz="UTC")   # 1m starts 2026-03-01 (after the break)
        close = 3000 * np.cumprod(1 + rng.normal(0, 0.0005, n))
        open_ = np.r_[3000.0, close[:-1]]
        full = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + 0.05, "low": np.minimum(open_, close) - 0.05,
                             "close": close, "volume": rng.gamma(2, 5, n)}, index=idx)
        flat_rows = rng.choice(n, 4000, replace=False)
        for c in ("open", "high", "low", "close"):
            full.iloc[flat_rows, full.columns.get_loc(c)] = np.r_[3000.0, close[:-1]][flat_rows]
        full.iloc[flat_rows, full.columns.get_loc("volume")] = 0.0

        gap_a = idx[3 * 1440 + 100: 3 * 1440 + 130]      # 30 missing minutes on day index 3
        one_min = idx[10 * 1440 + 500]                    # 1 missing minute on day index 10
        one_min_bar = full.loc[[one_min]]
        one_min_bar.iloc[0, one_min_bar.columns.get_loc("volume")] = 1.0
        f1m = full.drop(gap_a).drop(one_min)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); dd, rd = tmp / "binance", tmp / "binance_raw"; dd.mkdir(); rd.mkdir()
            f1m.reset_index(names="date").to_feather(dd / "ETH_FDUSD-1m.feather")
            for tf in ("5m", "15m", "30m", "1h", "1d", "1w"):
                nat = resample_ohlcv(full, tf)      # natives are built from the GAP-FREE path
                if tf == "1d":
                    nat.iloc[20, nat.columns.get_loc("close")] *= 1.01     # corrupt one day with no gap -> unexplained
                nat.reset_index(names="date").to_feather(dd / f"ETH_FDUSD-{tf}.feather")
            # raw store: same bars + 3 extra rows the freqtrade file lacks; 5 freqtrade-only flat rows; 1 price mismatch
            raw = full.copy()
            raw["quote_volume"] = 1.0; raw["n_trades"] = 5; raw["taker_buy_base"] = 0.5; raw["taker_buy_quote"] = 1.0
            raw = raw.drop(idx[flat_rows[:5]])                        # freqtrade has flat placeholders raw does not
            raw = raw.drop(gap_a); raw.iloc[100, raw.columns.get_loc("close")] += 0.5
            raw.reset_index(names="date").to_feather(rd / "ETH_FDUSD-1m.feather")

            rep = build_report(dd, rd, "ETH_FDUSD")
            d1 = rep["freqtrade_files"]["1m"]
            assert d1["rows"] == n - 31 and d1["missing_bars_literal_gaps"] == 31, d1
            assert d1["entirely_after_break"] and d1["rows_before_break_day"] == 0
            assert 0.055 < d1["flat_fraction"] < 0.068, d1["flat_fraction"]
            assert rep["freqtrade_files"]["1w"]["all_weekly_bars_open_on_monday"]
            assert rep["freqtrade_files"]["1d"]["all_bars_open_at_00_00_utc"]
            dq = rep["daily_from_1m_vs_native_1d"]
            assert dq["mismatched_days_with_missing_1m_minutes_or_flat_edge_row"] >= 1, dq   # the 30-minute-gap day is explained
            assert dq["mismatched_days_UNEXPLAINED"] == 1 and dq["examples_unexplained"][0]["columns"] == ["close"], dq
            rv = rep["raw_vs_freqtrade_1m"]
            assert rv["rows_only_in_freqtrade_file"] == 5 and rv["of_which_flat_zero_volume"] == 5, rv
            assert rv["rows_only_in_raw_store"] == 1 and list(rv["ohlcv_mismatches_on_common_rows"]) == ["close"], rv
            assert any("raw-kline store and freqtrade" in x for x in rep["warnings"])
            # a file that starts before the break must be flagged
            pre = full.copy(); pre.index = pre.index - pd.Timedelta(days=60)   # starts 2026-01-01
            pre.reset_index(names="date").to_feather(dd / "ETH_FDUSD-5m.feather")
            rep2 = build_report(dd, rd, "ETH_FDUSD")
            f5 = rep2["freqtrade_files"]["5m"]
            assert not f5["entirely_after_break"] and f5["rows_before_break_day"] > 0 and f5["rows_after_break_day"] > 0
            assert any("5m" in x and "NOT entirely post-break" in x for x in rep2["warnings"])
            print_summary(rep2)
        mf = rep["monthly_flat_fraction"]["ETH_FDUSD_1m"]
        assert set(mf) == {"2026-03", "2026-04"} and abs(sum(v["flat"] for v in mf.values()) - rep["freqtrade_files"]["1m"]["flat_zero_volume_rows"]) == 0
        # seam check: the synthetic 1m file starts 2026-03-01, so it straddles 2026-03-19 and must pass...
        sc = seam_check(full)
        assert sc["consecutive_across_seam"] and sc["missing_bars_in_window"] == 0 and sc["duplicates_in_window"] == 0, sc
        # ...and fail when a bar is missing right at the seam, or a duplicate is present
        broken = full.drop(pd.Timestamp("2026-03-19 00:00", tz="UTC"))
        assert not seam_check(broken)["consecutive_across_seam"] and seam_check(broken)["missing_bars_in_window"] == 1
        dup = pd.concat([full, full.loc[[pd.Timestamp("2026-03-19 00:05", tz="UTC")]]]).sort_index()
        assert seam_check(dup)["duplicates_in_window"] == 1
        # extension vs previous file: previous = the later part; current = full -> identical on overlap
        prev = full.loc[full.index >= pd.Timestamp("2026-03-19", tz="UTC")]
        ov = overlap_with_previous(prev, full)
        assert ov["identical_on_overlap"] and ov["new_rows_before_previous_start"] == len(full) - len(prev)
        tampered = full.copy(); tampered.iloc[-5, tampered.columns.get_loc("close")] += 0.01
        assert not overlap_with_previous(prev, tampered)["identical_on_overlap"]
        assert not overlap_with_previous(full, prev)["identical_on_overlap"]   # rows would be lost
        print("  seam check: consecutive across the join, flags a missing bar or duplicate; extension-vs-previous detects change or loss")
        print("\nSelf-test passed: task0_report counts gaps/flats/break split, classifies 1d mismatches, and diffs raw vs freqtrade.")
    else:
        main()
