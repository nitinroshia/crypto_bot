"""
Gap locator (work order 1.2 data batch, item 3; answers 1.4/1.5: "mask them, never drop").

For a stored kline file it lists every run of missing bars against the regular grid, reports the
LEADING partial day separately (a series that starts at 04:00 is not "missing" its first four
hours), cross-checks a finer file (the 5m bars inside each missing hour) and can compare the gap
set of two pairs (ETH/USDT vs BTC/USDT: exchange-wide outages should coincide).

    python3 user_data/analysis/locate_gaps.py --pair ETH_USDT --timeframe 1h \\
        --crosscheck-timeframe 5m --compare-pair BTC_USDT
    python3 user_data/analysis/locate_gaps.py --self-test

MASKING: `mask_to_grid` puts the series on its full regular grid; every absent bar becomes a row
of NaN with gap=True, so later code sees the hole instead of silently skipping it (an origin
whose entry or exit bar is masked is excluded and counted, answer C2). Nothing is filled,
interpolated or forward-carried, and nothing is dropped.

DESCRIPTIVE ONLY: this tool reads bar timestamps and counts them. It computes no return of any
series, so it may read the whole file, including data after the discovery cutoff (answer C1).
Output goes to <output-dir>/gaps/ (default user_data/analysis/results/gaps/), inside the project.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

DISCOVERY_CUTOFF = pd.Timestamp("2025-08-31 23:59:59", tz="UTC")
STEP = {"1m": pd.Timedelta(minutes=1), "5m": pd.Timedelta(minutes=5), "15m": pd.Timedelta(minutes=15),
        "30m": pd.Timedelta(minutes=30), "1h": pd.Timedelta(hours=1), "1d": pd.Timedelta(days=1)}


def _ns(ix) -> np.ndarray:
    """Epoch nanoseconds regardless of the index unit (pandas 3 may hold s/ms/us/ns)."""
    return pd.DatetimeIndex(ix).as_unit("ns").asi8


def load_index(raw_dir: Path, pair: str, tf: str) -> pd.DatetimeIndex:
    path = raw_dir / f"{pair}-{tf}.feather"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_feather(path, columns=["date"])
    return pd.DatetimeIndex(pd.to_datetime(df["date"], utc=True)).sort_values()


def find_gaps(index: pd.DatetimeIndex, step: pd.Timedelta) -> tuple[pd.DataFrame, dict]:
    """Runs of missing bars inside the file's own span. Returns (gaps, irregular) where irregular
    counts spacings that are not a whole multiple of the step (should be zero) and duplicates."""
    idx = pd.DatetimeIndex(index).sort_values()
    dup = int(idx.duplicated().sum())
    idx = idx.unique()
    d = idx[1:] - idx[:-1]
    ratio = d / step
    whole = np.isclose(ratio, np.round(ratio))
    irregular = int((~whole).sum() + (ratio < 1 - 1e-9).sum())
    pos = np.flatnonzero(ratio > 1 + 1e-9)
    rows = []
    for i in pos:
        n = int(round(ratio[i])) - 1
        rows.append({"gap_start": idx[i] + step, "gap_end": idx[i + 1] - step, "n_missing": n})
    gaps = pd.DataFrame(rows, columns=["gap_start", "gap_end", "n_missing"])
    return gaps, {"irregular_spacings": irregular, "duplicate_timestamps": dup}


def leading_partial_day(first: pd.Timestamp, step: pd.Timedelta) -> dict:
    """Bars of the first UTC day that precede the first row (the series simply starts later)."""
    day0 = first.normalize()
    n = int(round((first - day0) / step)) if step < pd.Timedelta(days=1) else 0
    return {"first_row": str(first), "first_day_start": str(day0), "leading_bars_before_first_row": n}


def mask_to_grid(df: pd.DataFrame, step: pd.Timedelta) -> pd.DataFrame:
    """Full regular grid over the file's span; missing bars are NaN rows with gap=True."""
    grid = pd.date_range(df.index.min(), df.index.max(), freq=step, tz="UTC")
    out = df.reindex(grid)
    out["gap"] = ~grid.isin(df.index)
    return out


def expand_gap_bars(gaps: pd.DataFrame, step: pd.Timedelta) -> pd.DatetimeIndex:
    parts = [pd.date_range(r.gap_start, r.gap_end, freq=step) for r in gaps.itertuples()]
    return parts[0].append(parts[1:]) if parts else pd.DatetimeIndex([], tz="UTC")


def crosscheck(fine_index: pd.DatetimeIndex, gaps: pd.DataFrame, coarse_step: pd.Timedelta, fine_step: pd.Timedelta) -> dict:
    """Do the fine bars agree with the coarse gaps? Counts fine rows still present inside a coarse gap
    (should be 0), and fine bars missing outside every coarse gap."""
    fi = pd.DatetimeIndex(fine_index).sort_values().unique()
    fv = _ns(fi)
    per_gap_present = []
    inside = 0
    for r in gaps.itertuples():
        a, b = pd.Timestamp(r.gap_start).as_unit("ns").value, pd.Timestamp(r.gap_end + coarse_step).as_unit("ns").value              # [start, end of last missing coarse bar)
        present = int(np.searchsorted(fv, b, side="left") - np.searchsorted(fv, a, side="left"))
        per_gap_present.append(present)
        inside += int(round(((r.gap_end + coarse_step) - r.gap_start) / fine_step))
    fine_gaps, _ = find_gaps(fi, fine_step)
    fine_missing_total = int(fine_gaps["n_missing"].sum()) if len(fine_gaps) else 0
    # fine gap bars that fall inside a coarse gap window
    win_a = np.array([pd.Timestamp(r.gap_start).as_unit("ns").value for r in gaps.itertuples()], dtype="int64")
    win_b = np.array([pd.Timestamp(r.gap_end + coarse_step).as_unit("ns").value for r in gaps.itertuples()], dtype="int64")
    missing_bars = _ns(expand_gap_bars(fine_gaps, fine_step)) if len(fine_gaps) else np.array([], dtype="int64")
    if len(missing_bars) and len(win_a):
        k = np.searchsorted(win_a, missing_bars, side="right") - 1
        in_win = (k >= 0) & (missing_bars < win_b[np.clip(k, 0, None)])
    else:
        in_win = np.zeros(len(missing_bars), dtype=bool)
    outside = fine_gaps.copy()
    if len(fine_gaps):
        first_bar = _ns(fine_gaps["gap_start"])
        k = np.searchsorted(win_a, first_bar, side="right") - 1 if len(win_a) else np.full(len(first_bar), -1)
        covered = (k >= 0) & (_ns(fine_gaps["gap_end"]) < win_b[np.clip(k, 0, None)]) if len(win_a) else np.zeros(len(first_bar), bool)
        outside = fine_gaps[~covered]
    return {
        "coarse_gaps": int(len(gaps)),
        "coarse_gap_windows_that_still_contain_fine_rows": int(sum(1 for p in per_gap_present if p > 0)),
        "fine_rows_present_inside_coarse_gaps": int(sum(per_gap_present)),
        "fine_bars_expected_inside_coarse_gaps": int(inside),
        "fine_bars_missing_total": fine_missing_total,
        "fine_bars_missing_inside_coarse_gaps": int(in_win.sum()),
        "fine_bars_missing_outside_coarse_gaps": int(fine_missing_total - in_win.sum()),
        "fine_gap_blocks_outside_coarse_gaps": int(len(outside)),
        "largest_outside_blocks": [{"start": str(r.gap_start), "end": str(r.gap_end), "n_missing": int(r.n_missing)}
                                   for r in outside.sort_values("n_missing", ascending=False).head(10).itertuples()],
    }


def compare_gap_sets(gaps_a: pd.DataFrame, gaps_b: pd.DataFrame, step: pd.Timedelta) -> dict:
    a, b = set(expand_gap_bars(gaps_a, step)), set(expand_gap_bars(gaps_b, step))
    return {"bars_missing_a": len(a), "bars_missing_b": len(b), "in_both": len(a & b), "only_a": len(a - b), "only_b": len(b - a)}


def summarize(index: pd.DatetimeIndex, step: pd.Timedelta) -> dict:
    gaps, odd = find_gaps(index, step)
    idx = pd.DatetimeIndex(index).sort_values().unique()
    before = gaps[gaps["gap_end"] <= DISCOVERY_CUTOFF]
    year = gaps.groupby(gaps["gap_start"].dt.year)["n_missing"].agg(["count", "sum"]) if len(gaps) else pd.DataFrame()
    return {
        "rows": int(len(idx)), "first": str(idx[0]), "last": str(idx[-1]),
        "leading_partial_day": leading_partial_day(idx[0], step),
        "expected_rows_from_first_to_last": int(round((idx[-1] - idx[0]) / step)) + 1,
        "interior_gap_blocks": int(len(gaps)), "interior_bars_missing": int(gaps["n_missing"].sum()) if len(gaps) else 0,
        "interior_bars_missing_up_to_cutoff": int(before["n_missing"].sum()) if len(before) else 0,
        "gap_blocks_up_to_cutoff": int(len(before)),
        "by_year": {int(y): {"blocks": int(r["count"]), "bars": int(r["sum"])} for y, r in year.iterrows()} if len(year) else {},
        "longest_blocks": [{"start": str(r.gap_start), "end": str(r.gap_end), "n_missing": int(r.n_missing)}
                           for r in gaps.sort_values("n_missing", ascending=False).head(10).itertuples()],
        **odd,
    }, gaps


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", type=Path, default=Path("user_data/data/binance_raw"))
    ap.add_argument("--pair", default="ETH_USDT")
    ap.add_argument("--timeframe", default="1h", choices=sorted(STEP))
    ap.add_argument("--crosscheck-timeframe", default=None, choices=sorted(STEP))
    ap.add_argument("--compare-pair", default=None)
    ap.add_argument("--output-dir", type=Path, default=Path("user_data/analysis/results"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        _self_test()
        return 0
    step = STEP[args.timeframe]
    idx = load_index(args.raw_dir, args.pair, args.timeframe)
    summ, gaps = summarize(idx, step)
    report = {"pair": args.pair, "timeframe": args.timeframe, "descriptive_only": "no returns computed", **summ}
    lp = summ["leading_partial_day"]
    print(f"{args.pair} {args.timeframe}: {summ['rows']} rows, {summ['first']} .. {summ['last']}")
    print(f"  leading partial day: series starts {lp['first_row']}, {lp['leading_bars_before_first_row']} bar(s) of that day precede it (not counted as gaps)")
    print(f"  interior gaps: {summ['interior_gap_blocks']} block(s), {summ['interior_bars_missing']} bar(s) missing "
          f"({summ['gap_blocks_up_to_cutoff']} block(s) / {summ['interior_bars_missing_up_to_cutoff']} bar(s) up to the cutoff)")
    print(f"  expected rows first..last: {summ['expected_rows_from_first_to_last']}   irregular spacings: {summ['irregular_spacings']}   duplicates: {summ['duplicate_timestamps']}")
    print(f"  by year: {summ['by_year']}")
    for b in summ["longest_blocks"][:5]:
        print(f"  longest: {b['start']} .. {b['end']}  ({b['n_missing']} bars)")
    if args.crosscheck_timeframe:
        fstep = STEP[args.crosscheck_timeframe]
        fidx = load_index(args.raw_dir, args.pair, args.crosscheck_timeframe)
        report["crosscheck"] = {"fine_timeframe": args.crosscheck_timeframe, **crosscheck(fidx, gaps, step, fstep)}
        c = report["crosscheck"]
        print(f"  {args.crosscheck_timeframe} cross-check: fine rows still present inside coarse gaps = {c['fine_rows_present_inside_coarse_gaps']} "
              f"(windows affected {c['coarse_gap_windows_that_still_contain_fine_rows']}); fine bars missing total {c['fine_bars_missing_total']} = "
              f"{c['fine_bars_missing_inside_coarse_gaps']} inside coarse gaps + {c['fine_bars_missing_outside_coarse_gaps']} outside "
              f"({c['fine_gap_blocks_outside_coarse_gaps']} block(s))")
    if args.compare_pair:
        oidx = load_index(args.raw_dir, args.compare_pair, args.timeframe)
        _, ogaps = summarize(oidx, step)
        report["compare"] = {"other_pair": args.compare_pair, **compare_gap_sets(gaps, ogaps, step)}
        c = report["compare"]
        print(f"  vs {args.compare_pair}: missing bars {c['bars_missing_a']} vs {c['bars_missing_b']}; in both {c['in_both']}; only {args.pair} {c['only_a']}; only {args.compare_pair} {c['only_b']}")
    out = args.output_dir / "gaps"
    out.mkdir(parents=True, exist_ok=True)
    gaps.assign(pair=args.pair, timeframe=args.timeframe).to_csv(out / f"gaps_{args.pair}-{args.timeframe}.csv", index=False)
    (out / f"gaps_{args.pair}-{args.timeframe}.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"\nWrote {out / ('gaps_' + args.pair + '-' + args.timeframe + '.csv')} and .json")
    return 0


# --------------------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------------------


def _self_test() -> None:
    h = pd.Timedelta(hours=1)
    m5 = pd.Timedelta(minutes=5)
    full = pd.date_range("2020-01-01 04:00", "2020-03-01 23:00", freq="1h", tz="UTC")
    holes = [pd.date_range("2020-01-10 05:00", periods=3, freq="1h", tz="UTC"),          # 3-hour outage
             pd.date_range("2020-02-01 12:00", periods=1, freq="1h", tz="UTC"),          # 1 hour
             pd.date_range("2020-02-20 00:00", periods=5, freq="1h", tz="UTC")]
    gone = holes[0].append(holes[1]).append(holes[2])
    idx1h = full.difference(gone)
    gaps, odd = find_gaps(idx1h, h)
    assert len(gaps) == 3 and gaps["n_missing"].tolist() == [3, 1, 5] and int(gaps["n_missing"].sum()) == 9 and odd == {"irregular_spacings": 0, "duplicate_timestamps": 0}
    assert gaps.iloc[0]["gap_start"] == pd.Timestamp("2020-01-10 05:00", tz="UTC") and gaps.iloc[0]["gap_end"] == pd.Timestamp("2020-01-10 07:00", tz="UTC")
    lp = leading_partial_day(idx1h[0], h)
    assert lp["leading_bars_before_first_row"] == 4, "a series starting at 04:00 has 4 leading bars, which are NOT gaps"
    assert summarize(idx1h, h)[0]["expected_rows_from_first_to_last"] - len(idx1h) == 9
    print("  gaps: runs, sizes and positions found; the 4 leading hours are reported separately, not as a gap")

    # 5m file: consistent with the 1h gaps, plus two extra missing 5m bars and one extra block elsewhere
    full5 = pd.date_range("2020-01-01 04:00", "2020-03-01 23:55", freq="5min", tz="UTC")
    gone5 = pd.DatetimeIndex([])
    for hh in gone:
        gone5 = gone5.append(pd.date_range(hh, periods=12, freq="5min", tz="UTC"))
    extra = pd.DatetimeIndex(pd.to_datetime(["2020-01-20 10:15", "2020-01-20 10:20", "2020-02-10 03:35"], utc=True))
    idx5 = full5.difference(gone5).difference(extra)
    c = crosscheck(idx5, gaps, h, m5)
    assert c["fine_rows_present_inside_coarse_gaps"] == 0 and c["fine_bars_expected_inside_coarse_gaps"] == 9 * 12
    assert c["fine_bars_missing_total"] == 9 * 12 + 3 and c["fine_bars_missing_inside_coarse_gaps"] == 9 * 12
    assert c["fine_bars_missing_outside_coarse_gaps"] == 3 and c["fine_gap_blocks_outside_coarse_gaps"] == 2
    # a coarse gap whose window still holds a fine row is reported as an inconsistency
    idx5_bad = idx5.append(pd.DatetimeIndex([pd.Timestamp("2020-01-10 06:30", tz="UTC")])).sort_values()
    assert crosscheck(idx5_bad, gaps, h, m5)["coarse_gap_windows_that_still_contain_fine_rows"] == 1
    print("  cross-check: fine bars inside each coarse gap counted (0 present), extra fine gaps outside them located")

    # comparing two pairs
    other = full.difference(holes[0].append(holes[2]).append(pd.date_range("2020-02-25 00:00", periods=2, freq="1h", tz="UTC")))
    og, _ = find_gaps(other, h)
    cmp_ = compare_gap_sets(gaps, og, h)
    assert cmp_ == {"bars_missing_a": 9, "bars_missing_b": 10, "in_both": 8, "only_a": 1, "only_b": 2}, cmp_
    print("  compare: bars missing in both / only in one pair counted")

    # masking keeps every hole as a NaN row and drops nothing
    df = pd.DataFrame({"open": np.arange(len(idx1h), dtype=float), "volume": 1.0}, index=idx1h)
    mk = mask_to_grid(df, h)
    assert len(mk) == len(idx1h) + 9 and int(mk["gap"].sum()) == 9 and mk.loc[~mk["gap"], "open"].notna().all() and mk.loc[mk["gap"], "open"].isna().all()
    assert (mk.loc[~mk["gap"], "open"].to_numpy() == df["open"].to_numpy()).all()
    print("  mask_to_grid: 9 NaN rows added on the regular grid, every real row kept, nothing filled")

    # irregular spacing and duplicates are reported, never silently repaired
    weird = pd.DatetimeIndex(pd.to_datetime(["2020-01-01 00:00", "2020-01-01 01:00", "2020-01-01 01:30", "2020-01-01 03:00", "2020-01-01 03:00"], utc=True))
    _, odd2 = find_gaps(weird, h)
    assert odd2["irregular_spacings"] >= 1 and odd2["duplicate_timestamps"] == 1
    print("  irregular spacing and duplicate timestamps are reported")

    # end to end through the CLI on feather files in the system temp dir
    with tempfile.TemporaryDirectory() as tmp:
        raw, outp = Path(tmp) / "raw", Path(tmp) / "out"
        raw.mkdir()
        for name, ix in (("ETH_USDT-1h", idx1h), ("ETH_USDT-5m", idx5), ("BTC_USDT-1h", other)):
            pd.DataFrame({"date": ix, "open": 1.0}).to_feather(raw / f"{name}.feather")
        main(["--raw-dir", str(raw), "--pair", "ETH_USDT", "--timeframe", "1h", "--crosscheck-timeframe", "5m",
              "--compare-pair", "BTC_USDT", "--output-dir", str(outp)])
        rep = json.loads((outp / "gaps" / "gaps_ETH_USDT-1h.json").read_text())
        assert rep["interior_bars_missing"] == 9 and rep["crosscheck"]["fine_rows_present_inside_coarse_gaps"] == 0 and rep["compare"]["in_both"] == 8
        assert (outp / "gaps" / "gaps_ETH_USDT-1h.csv").exists() and rep["descriptive_only"] == "no returns computed"
    print("Self-test passed: locate_gaps.py finds, cross-checks, compares and masks gaps without dropping a bar.")


if __name__ == "__main__":
    sys.exit(main())
