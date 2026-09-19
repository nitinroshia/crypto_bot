"""
Task 2 — Canonical resampling + self-check.

One function resamples 1m OHLCV up to any target timeframe. A second function
diffs that resampled output against an independently-downloaded native file
for the same timeframe, so we have two independent paths to any timeframe and
can catch alignment/timezone bugs before building anything on top of them.
"""

from __future__ import annotations

import pandas as pd

# Pandas offset aliases for each freqtrade timeframe we care about.
# ("min" instead of the deprecated "T"; "W" defaults to week-ending-Sunday,
# which is fine here as long as we're consistent between resampled and
# native comparisons.)
TIMEFRAME_TO_PANDAS_RULE = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    # Binance daily candles are UTC midnight-to-midnight, which is exactly
    # pandas' default "D" bin boundary -- no special anchor needed here,
    # unlike the weekly case below.
    "1d": "1D",
    # W-MON anchors weekly bins to Monday 00:00 (matching Binance's weekly
    # candle labeling). The unqualified "W" rule anchors to Sunday instead,
    # which silently produces labels one day off from every native weekly
    # candle -- confirmed against synthetic data before this fix.
    "1w": "W-MON",
}


def resample_ohlcv(df_1m: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
    """
    Resample 1-minute OHLCV data up to `target_timeframe`.

    df_1m must have a DatetimeIndex (or a 'date' column, which will be set as
    the index) and columns: open, high, low, close, volume.

    Aggregation: open=first, high=max, low=min, close=last, volume=sum.
    Bins are left-closed / left-labeled, i.e. a candle's timestamp is its
    OPEN time — matching freqtrade/Binance convention. Verify this against
    Task 2's native-file comparison before relying on it elsewhere.
    """
    if target_timeframe not in TIMEFRAME_TO_PANDAS_RULE:
        raise ValueError(
            f"Unsupported timeframe '{target_timeframe}'. "
            f"Supported: {sorted(TIMEFRAME_TO_PANDAS_RULE)}"
        )

    df = df_1m.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "date" not in df.columns:
            raise ValueError("df_1m needs a DatetimeIndex or a 'date' column")
        df = df.set_index(pd.to_datetime(df["date"], utc=True))

    df = df.sort_index()

    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df_1m is missing required columns: {missing}")

    rule = TIMEFRAME_TO_PANDAS_RULE[target_timeframe]

    resampled = df.resample(rule, label="left", closed="left").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )

    # Drop bins with no trades at all (e.g. exchange downtime), rather than
    # silently forward-filling — forward-filling a gap manufactures fake
    # zero-volatility candles that would distort every stat downstream.
    resampled = resampled.dropna(subset=["open", "high", "low", "close"])

    return resampled


def compare_resampled_vs_native(
    resampled: pd.DataFrame,
    native: pd.DataFrame,
    price_tol: float = 1e-6,
    volume_tol: float = 1e-3,
) -> dict:
    """
    Diff a resampled dataframe against an independently-downloaded native
    file for the same timeframe, over their overlapping period.

    Returns a summary dict. Does NOT silently correct anything — if there's
    a mismatch, that's flagged for a human to look at, since it usually means
    an alignment or timezone bug worth understanding, not a formula bug to
    patch over.
    """
    native = native.copy()
    if not isinstance(native.index, pd.DatetimeIndex):
        if "date" not in native.columns:
            raise ValueError("native df needs a DatetimeIndex or a 'date' column")
        native = native.set_index(pd.to_datetime(native["date"], utc=True))
    native = native.sort_index()

    common_index = resampled.index.intersection(native.index)
    if len(common_index) == 0:
        return {
            "overlap_rows": 0,
            "status": "NO_OVERLAP",
            "note": "No shared timestamps between resampled and native data. "
            "Check timezone handling and bin labeling before anything else.",
        }

    r = resampled.loc[common_index]
    n = native.loc[common_index]

    mismatches = {}
    for col, tol in (
        ("open", price_tol),
        ("high", price_tol),
        ("low", price_tol),
        ("close", price_tol),
        ("volume", volume_tol),
    ):
        diff = (r[col] - n[col]).abs()
        rel_diff = diff / n[col].replace(0, pd.NA)
        bad = diff[(diff > tol) & (rel_diff.fillna(1) > tol)]
        if len(bad) > 0:
            mismatches[col] = {
                "n_mismatched_rows": int(len(bad)),
                "max_abs_diff": float(diff.max()),
                "first_mismatch_ts": str(bad.index[0]),
            }

    return {
        "overlap_rows": int(len(common_index)),
        "status": "MATCH" if not mismatches else "MISMATCH",
        "mismatches": mismatches,
    }


if __name__ == "__main__":
    # Self-test on synthetic data: build fake 1m candles, resample to 5m,
    # and confirm it matches a hand-resampled reference.
    import numpy as np

    rng = pd.date_range("2026-01-01", periods=60, freq="1min", tz="UTC")
    prices = 2500 + np.cumsum(np.random.default_rng(0).normal(0, 1, len(rng)))
    df_1m = pd.DataFrame(
        {
            "date": rng,
            "open": prices,
            "high": prices + 0.5,
            "low": prices - 0.5,
            "close": prices + np.random.default_rng(1).normal(0, 0.1, len(rng)),
            "volume": np.random.default_rng(2).uniform(1, 10, len(rng)),
        }
    ).set_index(rng)

    df_5m = resample_ohlcv(df_1m, "5m")
    print(f"1m rows: {len(df_1m)}  ->  5m rows: {len(df_5m)}")
    assert len(df_5m) == 12, "expected 60 one-minute candles to fold into 12 five-minute candles"

    # Compare against itself as a trivial sanity check of the diff function.
    result = compare_resampled_vs_native(df_5m, df_5m)
    assert result["status"] == "MATCH"
    print("Self-test passed: resample_ohlcv + compare_resampled_vs_native both work.")