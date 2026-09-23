"""
Derive a coarser raw-store timeframe from a finer one already on disk, using the traded-minutes
resample rule (work order 1.1), and persist it as a new raw-store file.

Work order 1.4, section 4.1: BTC/USDT needs a 15m raw-store file for Task 3, and nothing else in
the queue needs BTC/USDT 1m, so 15m is built from the newly-fetched native 5m rather than from 1m.
`resample.resample_ohlcv_traded` turns out to already generalize to any source granularity finer
than the target -- its logic (open = first TRADED source bar, high/low/close from traded bars only,
a bar with zero traded source rows carries the previous close) never assumed "1 minute" anywhere
except its parameter name and docstring. Verified on synthetic 5m-source data before relying on it
here (see the self-test), and the source/target pairing is always logged so this is checked again on
every real run, not just once.

    python3 user_data/analysis/build_derived_raw.py --pair BTC_USDT --source-timeframe 5m --target-timeframe 15m
    python3 user_data/analysis/build_derived_raw.py --self-test

STORAGE: <raw-dir>/<PAIR>-<target>.feather, columns date, open, high, low, close, volume,
quote_volume, n_trades, taker_buy_base, taker_buy_quote. The non-OHLCV columns are summed like
volume (quote_volume, n_trades) or carried as NaN (taker_buy_base/quote have no clean "traded only"
aggregation rule yet, so they are left NaN rather than guessed -- flagged in the report). A target
bar whose SOURCE window has literally no rows at all (a full outage) is correctly absent from the
output, not filled; the standard gap locator on the derived file will find it as a gap the same way
it would on any independently-fetched file.

DESCRIPTIVE-DERIVATION ONLY: this tool re-expresses existing raw-store data at a coarser grain. It
computes no return and applies no cutoff, so it may run over the whole raw store regardless of the
discovery cutoff -- the cutoff is applied later, by whatever reads this file for a hypothesis test.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from resample import TIMEFRAME_TO_PANDAS_RULE, resample_ohlcv_traded

RAW_COLUMNS = ["date", "open", "high", "low", "close", "volume", "quote_volume", "n_trades", "taker_buy_base", "taker_buy_quote"]
SUMMED_EXTRA = ("quote_volume", "n_trades")
UNAGGREGATED_EXTRA = ("taker_buy_base", "taker_buy_quote")


def load_raw(raw_dir: Path, pair: str, timeframe: str) -> pd.DataFrame:
    path = raw_dir / f"{pair}-{timeframe}.feather"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.as_unit("ns")
    return df.sort_values("date").reset_index(drop=True)


def derive(df: pd.DataFrame, target_timeframe: str) -> tuple[pd.DataFrame, dict]:
    """Traded-minutes OHLCV via resample_ohlcv_traded, plus the extra raw-store columns (summed
    where that's a well-defined operation, NaN where it isn't -- see the module docstring)."""
    if target_timeframe not in TIMEFRAME_TO_PANDAS_RULE:
        raise ValueError(f"unsupported target timeframe {target_timeframe!r}")
    ohlcv = resample_ohlcv_traded(df.set_index("date"), target_timeframe)
    rule = TIMEFRAME_TO_PANDAS_RULE[target_timeframe]
    have_summed = [c for c in SUMMED_EXTRA if c in df.columns]
    extra = df.set_index("date")[have_summed].resample(rule, label="left", closed="left").sum() if have_summed else None
    out = ohlcv.reset_index(names="date")
    for c in SUMMED_EXTRA:
        out[c] = extra.reindex(ohlcv.index)[c].to_numpy() if extra is not None and c in have_summed else np.nan
    for c in UNAGGREGATED_EXTRA:
        out[c] = np.nan
    return out[RAW_COLUMNS], {
        "unaggregated_columns": [c for c in UNAGGREGATED_EXTRA],
        "summed_columns": have_summed,
        "missing_source_columns": [c for c in RAW_COLUMNS[1:] if c not in df.columns],
    }


def save(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".feather.tmp")
    df.to_feather(tmp)
    tmp.replace(path)


def report(pair: str, source_tf: str, target_tf: str, src: pd.DataFrame, out: pd.DataFrame, extra_info: dict, path: Path) -> dict:
    step = TIMEFRAME_TO_PANDAS_RULE[target_tf]
    expected = int((out["date"].max() - out["date"].min()) / pd.Timedelta(step)) + 1 if len(out) else 0
    return {
        "pair": pair, "source_timeframe": source_tf, "target_timeframe": target_tf, "file": str(path),
        "source_rows": int(len(src)), "target_rows": int(len(out)),
        "target_first": str(out["date"].min()) if len(out) else None, "target_last": str(out["date"].max()) if len(out) else None,
        "target_missing_vs_grid": expected - len(out) if len(out) else None,
        **extra_info,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", type=Path, default=Path("user_data/data/binance_raw"))
    ap.add_argument("--pair", required=False)
    ap.add_argument("--source-timeframe", required=False)
    ap.add_argument("--target-timeframe", required=False)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        _self_test()
        return 0
    if not (args.pair and args.source_timeframe and args.target_timeframe):
        ap.error("--pair, --source-timeframe and --target-timeframe are required unless --self-test")
    src = load_raw(args.raw_dir, args.pair, args.source_timeframe)
    out, extra_info = derive(src, args.target_timeframe)
    path = args.raw_dir / f"{args.pair}-{args.target_timeframe}.feather"
    save(path, out)
    r = report(args.pair, args.source_timeframe, args.target_timeframe, src, out, extra_info, path)
    print(f"{r['pair']}: {r['source_timeframe']} ({r['source_rows']} rows) -> {r['target_timeframe']} ({r['target_rows']} rows)")
    print(f"  span {r['target_first']} .. {r['target_last']}   missing vs regular {args.target_timeframe} grid: {r['target_missing_vs_grid']}")
    print(f"  summed columns: {r['summed_columns']}   left NaN (no clean traded-only rule yet): {r['unaggregated_columns']}")
    if r["missing_source_columns"]:
        print(f"  NOTE: source file lacks {r['missing_source_columns']}; those columns are NaN throughout the output")
    print(f"  wrote {path}")
    return 0


# --------------------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------------------
def _mk_5m(n=36, zero_at=(6,)) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01 00:00", periods=n, freq="5min", tz="UTC")
    rng = np.random.default_rng(3)
    close = 100 + np.cumsum(rng.normal(0, 0.1, n))
    df = pd.DataFrame({
        "date": idx, "open": close, "high": close + 0.05, "low": close - 0.05, "close": close,
        "volume": rng.uniform(1, 5, n), "quote_volume": rng.uniform(100, 500, n),
        "n_trades": rng.integers(5, 50, n).astype("int64"),
        "taker_buy_base": rng.uniform(0, 2, n), "taker_buy_quote": rng.uniform(0, 200, n),
    })
    for i in zero_at:
        prev_close = df["close"].iloc[i - 1]
        for c in ("open", "high", "low", "close"):
            df.loc[i, c] = prev_close
        df.loc[i, ["volume", "quote_volume", "n_trades", "taker_buy_base", "taker_buy_quote"]] = 0
    return df


def _self_test() -> None:
    # 1. 5m -> 15m: open comes from the first TRADED 5m bar, matching the standalone check already
    #    run against resample_ohlcv_traded directly -- this proves derive() wires it correctly, with
    #    the extra raw-store columns handled sanely, not that resample_ohlcv_traded itself is correct.
    df = _mk_5m()
    out, info = derive(df, "15m")
    assert len(out) == 12, "3 hours of 5m bars -> 12 15m bins"
    bin_start = pd.Timestamp("2024-01-01 00:30", tz="UTC")
    row = out[out["date"] == bin_start].iloc[0]
    real_first_traded_open = df.loc[7, "open"]   # bar 6 (index) is the injected zero-trade placeholder in this bin
    assert abs(row["open"] - real_first_traded_open) < 1e-9, "derive() must skip the zero-trade placeholder's open, same as resample_ohlcv_traded alone"
    assert info["summed_columns"] == ["quote_volume", "n_trades"] and info["unaggregated_columns"] == ["taker_buy_base", "taker_buy_quote"]
    expected_qv = df.loc[6:8, "quote_volume"].sum()
    assert abs(row["quote_volume"] - expected_qv) < 1e-6, "quote_volume must sum across all 3 source bars, placeholder included (it's 0)"
    assert row[["taker_buy_base", "taker_buy_quote"]].isna().all(), "unaggregated columns are NaN, never guessed"
    assert list(out.columns) == RAW_COLUMNS
    print("  5m->15m: open skips the zero-trade placeholder; quote_volume/n_trades summed; taker_buy_* left NaN, not guessed")

    # 2. A source window with literally NO rows at all is correctly absent from the output, not filled
    df2 = pd.concat([df.iloc[:6], df.iloc[9:]], ignore_index=True)   # entire 00:30 bin's 3 source rows missing
    out2, _ = derive(df2, "15m")
    assert len(out2) == 11 and pd.Timestamp("2024-01-01 00:30", tz="UTC") not in set(out2["date"])
    print("  a fully-missing source window is absent from the output (a gap, not a fabricated bar)")

    # 3. A source file lacking quote_volume/n_trades entirely is handled without crashing, and reported
    df3 = df.drop(columns=["quote_volume", "n_trades"])
    out3, info3 = derive(df3, "15m")
    assert out3["quote_volume"].isna().all() and out3["n_trades"].isna().all()
    assert set(info3["missing_source_columns"]) == {"quote_volume", "n_trades"}
    print("  a source file missing optional columns derives cleanly and reports exactly what's missing")

    # 4. Full CLI round-trip through feather files in the system temp dir (project temp/ is discontinued)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        df.to_feather(raw / "BTC_USDT-5m.feather")
        rc = main(["--raw-dir", str(raw), "--pair", "BTC_USDT", "--source-timeframe", "5m", "--target-timeframe", "15m"])
        assert rc == 0 and (raw / "BTC_USDT-15m.feather").exists()
        back = pd.read_feather(raw / "BTC_USDT-15m.feather")
        assert list(back.columns) == RAW_COLUMNS and len(back) == 12
    print("Self-test passed: build_derived_raw.py derives a coarser raw-store timeframe correctly and persists it.")


if __name__ == "__main__":
    sys.exit(main())
