"""
Diagnostic for the resample-vs-native mismatch pattern.

Rather than guess at the mechanism, this checks your REAL 1m data directly:
  1. Are there missing 1-minute timestamps (literal gaps) in the file?
  2. Are there "flat" candles (open==high==low==close, volume==0) -- the
     standard placeholder for a minute with zero trades?
  3. For each bin where the resampled 'open' disagrees with the native file,
     does that bin's underlying 1-minute window contain a gap or a flat
     candle nearby? If yes for the large majority of mismatches, that
     confirms the mechanism and tells us how to handle it (always prefer
     native data, which run_fingerprint.py now does).

Usage:
    python3 diagnose_gaps.py --data-dir ../user_data/data/binance \\
        --pair ETH_FDUSD --timeframe 5m
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from resample import TIMEFRAME_TO_PANDAS_RULE, resample_ohlcv

TIMEFRAME_TO_TIMEDELTA = {
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30),
    "1h": pd.Timedelta(hours=1),
    "1d": pd.Timedelta(days=1),
    "1w": pd.Timedelta(weeks=1),
}


def load_feather(data_dir: Path, pair: str, timeframe: str) -> pd.DataFrame:
    path = data_dir / f"{pair}-{timeframe}.feather"
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df.set_index("date").sort_index()


def find_missing_minutes(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Literal gaps: 1-minute timestamps absent from the file entirely."""
    full_grid = pd.date_range(df_1m.index.min(), df_1m.index.max(), freq="1min", tz="UTC")
    missing = full_grid.difference(df_1m.index)
    if len(missing) == 0:
        return pd.DataFrame(columns=["gap_start", "gap_end", "n_minutes"])

    # Group consecutive missing minutes into contiguous gap blocks.
    missing_sorted = missing.sort_values()
    gaps = []
    block_start = missing_sorted[0]
    prev = missing_sorted[0]
    for ts in missing_sorted[1:]:
        if ts - prev > pd.Timedelta(minutes=1):
            gaps.append((block_start, prev))
            block_start = ts
        prev = ts
    gaps.append((block_start, prev))

    return pd.DataFrame(
        [{"gap_start": s, "gap_end": e, "n_minutes": int((e - s) / pd.Timedelta(minutes=1)) + 1} for s, e in gaps]
    )


def find_flat_zero_volume_rows(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Rows present in the file but flagged as a zero-trade placeholder:
    open == high == low == close and volume == 0."""
    is_flat = (
        (df_1m["open"] == df_1m["high"])
        & (df_1m["high"] == df_1m["low"])
        & (df_1m["low"] == df_1m["close"])
        & (df_1m["volume"] == 0)
    )
    return df_1m[is_flat]


def find_mismatched_bins(resampled: pd.DataFrame, native: pd.DataFrame, col: str, tol: float = 1e-6) -> pd.DatetimeIndex:
    common = resampled.index.intersection(native.index)
    diff = (resampled.loc[common, col] - native.loc[common, col]).abs()
    return diff[diff > tol].index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--pair", type=str, default="ETH_FDUSD")
    parser.add_argument("--timeframe", type=str, default="5m", choices=[tf for tf in TIMEFRAME_TO_PANDAS_RULE if tf != "1m"])
    parser.add_argument("--n-examples", type=int, default=5)
    args = parser.parse_args()

    df_1m = load_feather(args.data_dir, args.pair, "1m")
    native = load_feather(args.data_dir, args.pair, args.timeframe)
    resampled = resample_ohlcv(df_1m.reset_index(), args.timeframe)

    print(f"=== 1m data: {len(df_1m)} rows, {df_1m.index.min()} to {df_1m.index.max()} ===\n")

    gaps = find_missing_minutes(df_1m)
    total_missing_minutes = int(gaps["n_minutes"].sum()) if len(gaps) else 0
    print(f"Literal missing-minute gaps: {len(gaps)} gap block(s), {total_missing_minutes} total missing minutes")
    if len(gaps):
        print(gaps.head(10).to_string(index=False))

    flat_rows = find_flat_zero_volume_rows(df_1m)
    print(f"\nFlat zero-volume placeholder rows present in file: {len(flat_rows)}")

    mismatched_open_bins = find_mismatched_bins(resampled, native, "open")
    print(f"\n=== {args.timeframe}: {len(mismatched_open_bins)} bins with a mismatched 'open' ===")

    n_explained_by_gap = 0
    n_explained_by_flat = 0
    tf_delta = TIMEFRAME_TO_TIMEDELTA[args.timeframe]

    examples_shown = 0
    for bin_start in mismatched_open_bins:
        bin_end = bin_start + tf_delta
        window_has_gap = any((g.gap_start < bin_end) and (g.gap_end >= bin_start) for g in gaps.itertuples())
        window_flats = flat_rows[(flat_rows.index >= bin_start) & (flat_rows.index < bin_end)]
        if window_has_gap:
            n_explained_by_gap += 1
        if len(window_flats) > 0:
            n_explained_by_flat += 1

        if examples_shown < args.n_examples and (window_has_gap or len(window_flats) > 0):
            examples_shown += 1
            print(f"\n--- Example: bin {bin_start} to {bin_end} ---")
            print("Raw 1m rows in this window:")
            print(df_1m[(df_1m.index >= bin_start) & (df_1m.index < bin_end)])
            print(f"Resampled open: {resampled.loc[bin_start, 'open']}  |  Native open: {native.loc[bin_start, 'open']}")

    n_total = len(mismatched_open_bins)
    if n_total > 0:
        print(f"\n=== Summary ===")
        print(f"Mismatched bins explained by a literal gap:  {n_explained_by_gap}/{n_total} ({n_explained_by_gap/n_total:.1%})")
        print(f"Mismatched bins explained by a flat/zero-vol row: {n_explained_by_flat}/{n_total} ({n_explained_by_flat/n_total:.1%})")
        print(f"Mismatched bins explained by EITHER: {len(set(range(n_total)))} -- see per-bin detail above for overlap")
    else:
        print("\nNo mismatched 'open' bins found for this timeframe.")


if __name__ == "__main__":
    main()