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


def resample_ohlcv(df_1m: pd.DataFrame, target_timeframe: str, rule: str = "traded") -> pd.DataFrame:
    """
    Resample 1-minute OHLCV data up to `target_timeframe`.

    rule="traded" (DEFAULT since work order 1.1): the exchange's own convention -- see
        `resample_ohlcv_traded`. Adopted after resample_rule_test.py showed ZERO mismatches
        against every native file (5m, 15m, 30m, 1h, 1d, 1w) on the real ETH/FDUSD data,
        1m 2026-01-30 .. 2026-09-19 (67,104 5m bins compared).
    rule="filled" (the original behaviour, kept only for comparison): every 1m row counts,
        including the flat zero-trade placeholder rows Binance emits. On the same real data
        it mismatched native `open` on 7.6% of 5m bins and `high`/`low` on ~2%.

    df_1m must have a DatetimeIndex (or a 'date' column, which will be set as
    the index) and columns: open, high, low, close, volume.

    Aggregation: open=first, high=max, low=min, close=last, volume=sum.
    Bins are left-closed / left-labeled, i.e. a candle's timestamp is its
    OPEN time — matching freqtrade/Binance convention. Verify this against
    Task 2's native-file comparison before relying on it elsewhere.
    """
    if rule == "traded":
        return resample_ohlcv_traded(df_1m, target_timeframe)
    if rule != "filled":
        raise ValueError(f"rule must be 'filled' or 'traded', got {rule!r}")
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


def resample_ohlcv_traded(df_1m: pd.DataFrame, target_timeframe: str, traded: pd.Series | None = None) -> pd.DataFrame:
    """
    Resample 1m -> `target_timeframe` from TRADED minutes only (work order 1.1).

    Why: Binance emits a flat placeholder bar (O=H=L=C=previous close, volume 0) for a
    minute with no trades. Treating those as real prices lets a placeholder become a
    coarse bar's open (previous close instead of the first real trade), or even its
    high/low. The exchange itself builds coarse bars from trades, so:
        open   = open of the first traded minute in the bin
        high   = highest high among traded minutes
        low    = lowest low among traded minutes
        close  = close of the last traded minute
        volume = sum of volume
        a bin with no traded minute carries the previous close (O=H=L=C, volume 0)
    A minute is "traded" if `traded` says so; by default volume > 0 (identical to
    n_trades > 0 -- checked on the real ETH/FDUSD and FDUSD/USDT data, where flat rows
    and zero-trade rows are the same set).

    Bins are decided from ALL rows (so the set of bins is the same as the original rule);
    leading bins with no earlier trade to carry are dropped.
    """
    if target_timeframe not in TIMEFRAME_TO_PANDAS_RULE:
        raise ValueError(f"Unsupported timeframe '{target_timeframe}'. Supported: {sorted(TIMEFRAME_TO_PANDAS_RULE)}")
    df = df_1m.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "date" not in df.columns:
            raise ValueError("df_1m needs a DatetimeIndex or a 'date' column")
        df = df.set_index(pd.to_datetime(df["date"], utc=True))
    df = df.sort_index()
    missing = {"open", "high", "low", "close", "volume"} - set(df.columns)
    if missing:
        raise ValueError(f"df_1m is missing required columns: {missing}")

    rule = TIMEFRAME_TO_PANDAS_RULE[target_timeframe]
    mask = (df["volume"] > 0) if traded is None else traded.reindex(df.index).fillna(False).astype(bool)
    all_bins = df["close"].resample(rule, label="left", closed="left").count()
    all_bins = all_bins[all_bins > 0].index          # bins that have at least one row of any kind

    t = df.loc[mask.to_numpy()]
    agg = t.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).reindex(all_bins)
    empty = agg["close"].isna()
    carried = agg["close"].ffill()                   # last traded close before each bin
    for col in ("open", "high", "low", "close"):
        agg.loc[empty, col] = carried[empty]
    agg.loc[empty, "volume"] = 0.0
    return agg.dropna(subset=["open", "high", "low", "close"])


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

    df_5m = resample_ohlcv(df_1m, "5m", rule="filled")
    assert resample_ohlcv(df_1m, "5m").equals(df_5m), "with every minute traded the two rules must agree"
    print(f"1m rows: {len(df_1m)}  ->  5m rows: {len(df_5m)}")
    assert len(df_5m) == 12, "expected 60 one-minute candles to fold into 12 five-minute candles"

    # Compare against itself as a trivial sanity check of the diff function.
    result = compare_resampled_vs_native(df_5m, df_5m)
    assert result["status"] == "MATCH"
    print("Self-test passed: resample_ohlcv + compare_resampled_vs_native both work.")

    # Second self-test -- the traded-minutes rule against an INDEPENDENT ground truth.
    # Simulate raw TRADES (about 12% of minutes get none), then build (a) 1m bars the way the
    # exchange does, with flat placeholders for empty minutes, and (b) "native" 5m / 1h / 1d bars
    # straight from the trades. The original rule must show the open/high/low mismatches seen on
    # the real data; the traded rule must reproduce the native bars exactly.
    trng = np.random.default_rng(42)
    days = 6
    n_min = days * 1440
    counts = trng.poisson(2.0, n_min)                       # trades per minute; P(0) ~ 13.5%
    minute_of_trade = np.repeat(np.arange(n_min), counts)
    t_sec = pd.Timestamp("2026-01-01", tz="UTC").timestamp() + minute_of_trade * 60 + trng.uniform(0, 60, len(minute_of_trade))
    order = np.argsort(t_sec)
    t_sec, minute_of_trade = t_sec[order], minute_of_trade[order]
    price = np.round(3000 + np.cumsum(trng.normal(0, 0.15, len(t_sec))), 2)
    size = trng.gamma(2, 0.5, len(t_sec))
    trades = pd.DataFrame({"t": pd.to_datetime(t_sec, unit="s", utc=True), "price": price, "size": size})
    trades["t"] = trades["t"].dt.as_unit("ns")

    def bars_from_trades(freq):
        g = trades.set_index("t").resample(freq, label="left", closed="left")
        b = g["price"].agg(open="first", high="max", low="min", close="last")
        b["volume"] = g["size"].sum()
        full = pd.date_range("2026-01-01", periods={"1min": n_min, "5min": n_min // 5, "1h": n_min // 60, "1D": days}[freq],
                             freq=freq, tz="UTC").as_unit("ns")
        b = b.reindex(full)
        empty_ = b["close"].isna()
        prev = b["close"].ffill()
        for c in ("open", "high", "low", "close"):
            b.loc[empty_, c] = prev[empty_]
        b.loc[empty_, "volume"] = 0.0
        return b.dropna(subset=["close"])

    one_min = bars_from_trades("1min")
    assert 0.10 < (one_min["volume"] == 0).mean() < 0.17, "simulation should have ~13% empty minutes"
    for tf, freq in (("5m", "5min"), ("1h", "1h"), ("1d", "1D")):
        native = bars_from_trades(freq)
        old = compare_resampled_vs_native(resample_ohlcv(one_min, tf, rule="filled"), native)
        new = compare_resampled_vs_native(resample_ohlcv(one_min, tf), native)   # default rule is "traded"
        assert new == compare_resampled_vs_native(resample_ohlcv(one_min, tf, rule="traded"), native)
        assert new["status"] == "MATCH", (tf, new)
        if tf != "1d":
            assert old["status"] == "MISMATCH" and "open" in old["mismatches"], (tf, old)
        print(f"  {tf}: filled rule mismatches={ {k: v['n_mismatched_rows'] for k, v in old.get('mismatches', {}).items()} }"
              f" -> traded rule: {new['status']} ({new['overlap_rows']} bins)")
    # a bin with no trades carries the previous close, with zero volume
    gap = one_min.copy()
    gap.loc["2026-01-01 00:10":"2026-01-01 00:19", ["open", "high", "low", "close"]] = gap.loc["2026-01-01 00:09", "close"]
    gap.loc["2026-01-01 00:10":"2026-01-01 00:19", "volume"] = 0.0
    r5 = resample_ohlcv(gap, "5m", rule="traded")
    for ts in ("2026-01-01 00:10", "2026-01-01 00:15"):
        row = r5.loc[pd.Timestamp(ts, tz="UTC")]
        assert row["volume"] == 0 and row["open"] == row["high"] == row["low"] == row["close"] == gap.loc["2026-01-01 00:09", "close"]
    print("Self-test passed: traded-minutes rule reproduces bars built from raw trades exactly; the filled rule does not.")