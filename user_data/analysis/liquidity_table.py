"""
Monthly liquidity table (work order 1.2 data batch, item 4; work order 1.2 section 7.13).

One table from the RAW 1m store: for each month of the chosen year, per pair, the number of
trades per day and the quote volume per day, the share of zero-trade minutes, and the
ETH/FDUSD-to-ETH/USDT ratios. It reads counts and volumes only.

    python3 user_data/analysis/liquidity_table.py                  # 2026, ETH_FDUSD vs ETH_USDT
    python3 user_data/analysis/liquidity_table.py --year 2026
    python3 user_data/analysis/liquidity_table.py --self-test

DEFINITIONS (nothing left to interpretation)
  minutes_covered  rows present in the month; days_covered = minutes_covered / 1440 (a month
                   that is only partly covered, such as the current one, is divided by the days
                   actually covered, never by the calendar length)
  trades_per_day   sum(n_trades) / days_covered
  quote_per_day    sum(quote_volume) / days_covered, in each pair's own quote currency (USDT for
                   ETH/USDT, FDUSD for ETH/FDUSD; both are dollar-pegged, the peg is not adjusted)
  zero_trade_share fraction of present minutes with n_trades == 0
  ratio            ETH_FDUSD value divided by ETH_USDT value, month by month

DESCRIPTIVE ONLY: no return of any series is computed, so reading data after the discovery
cutoff is allowed (answer C1). Output: <output-dir>/liquidity_monthly_<year>.csv and .json,
inside the project (default user_data/analysis/results/).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

NEEDED = ["date", "n_trades", "quote_volume"]


def load(raw_dir: Path, pair: str) -> pd.DataFrame:
    path = raw_dir / f"{pair}-1m.feather"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_feather(path)
    miss = [c for c in NEEDED if c not in df.columns]
    if miss:
        raise ValueError(f"{path} lacks {miss}; this table needs the RAW store (columns: {list(df.columns)})")
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df[NEEDED].set_index("date").sort_index()


def monthly(df: pd.DataFrame, year: int) -> pd.DataFrame:
    d = df[df.index.year == year]
    g = d.groupby(d.index.strftime("%Y-%m"))
    out = pd.DataFrame({
        "minutes_covered": g.size(),
        "n_trades_total": g["n_trades"].sum(),
        "quote_volume_total": g["quote_volume"].sum(),
        "zero_trade_minutes": g["n_trades"].apply(lambda s: int((s == 0).sum())),
    })
    out["days_covered"] = out["minutes_covered"] / 1440.0
    out["trades_per_day"] = out["n_trades_total"] / out["days_covered"]
    out["quote_per_day"] = out["quote_volume_total"] / out["days_covered"]
    out["zero_trade_share"] = out["zero_trade_minutes"] / out["minutes_covered"]
    out.index.name = "month"
    return out


def build_table(a: pd.DataFrame, b: pd.DataFrame, name_a: str, name_b: str, year: int) -> pd.DataFrame:
    ma, mb = monthly(a, year), monthly(b, year)
    keep = ["days_covered", "trades_per_day", "quote_per_day", "zero_trade_share"]
    t = ma[keep].add_suffix(f"__{name_a}").join(mb[keep].add_suffix(f"__{name_b}"), how="outer")
    t[f"ratio_trades_per_day__{name_a}_over_{name_b}"] = t[f"trades_per_day__{name_a}"] / t[f"trades_per_day__{name_b}"]
    t[f"ratio_quote_per_day__{name_a}_over_{name_b}"] = t[f"quote_per_day__{name_a}"] / t[f"quote_per_day__{name_b}"]
    return t


def print_table(t: pd.DataFrame, name_a: str, name_b: str) -> None:
    print(f"\n{'month':8s} {'days':>6s} | {'trades/day ' + name_a:>22s} {'trades/day ' + name_b:>22s} {'ratio':>7s} | "
          f"{'quote/day ' + name_a:>24s} {'quote/day ' + name_b:>24s} {'ratio':>7s} | {'zero-trade ' + name_a:>19s} {'zero-trade ' + name_b:>19s}")
    for m, r in t.iterrows():
        print(f"{m:8s} {r[f'days_covered__{name_a}']:6.1f} | {r[f'trades_per_day__{name_a}']:22,.0f} {r[f'trades_per_day__{name_b}']:22,.0f} "
              f"{r[f'ratio_trades_per_day__{name_a}_over_{name_b}']:7.3f} | {r[f'quote_per_day__{name_a}']:24,.0f} {r[f'quote_per_day__{name_b}']:24,.0f} "
              f"{r[f'ratio_quote_per_day__{name_a}_over_{name_b}']:7.3f} | {r[f'zero_trade_share__{name_a}']:19.4f} {r[f'zero_trade_share__{name_b}']:19.4f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", type=Path, default=Path("user_data/data/binance_raw"))
    ap.add_argument("--pair-a", default="ETH_FDUSD")
    ap.add_argument("--pair-b", default="ETH_USDT")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--output-dir", type=Path, default=Path("user_data/analysis/results"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        _self_test()
        return 0
    a, b = load(args.raw_dir, args.pair_a), load(args.raw_dir, args.pair_b)
    t = build_table(a, b, args.pair_a, args.pair_b, args.year)
    print(f"Monthly liquidity {args.year}: {args.pair_a} vs {args.pair_b} (raw 1m store; counts and volumes only)")
    print(f"  {args.pair_a}: {a.index.min()} .. {a.index.max()}    {args.pair_b}: {b.index.min()} .. {b.index.max()}")
    print_table(t, args.pair_a, args.pair_b)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.output_dir / f"liquidity_monthly_{args.year}"
    t.to_csv(f"{stem}.csv")
    Path(f"{stem}.json").write_text(json.dumps({
        "year": args.year, "pair_a": args.pair_a, "pair_b": args.pair_b, "descriptive_only": "no returns computed",
        "definitions": "days_covered = minutes/1440; per-day = total / days_covered; quote in each pair's own quote currency; ratio = a / b",
        "table": json.loads(t.to_json(orient="index")),
    }, indent=2))
    print(f"\nWrote {stem}.csv and .json")
    return 0


# --------------------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------------------


def _frame(start, end, trades_of, quote_of, missing=()) -> pd.DataFrame:
    idx = pd.date_range(start, end, freq="1min", tz="UTC")
    idx = idx.difference(pd.DatetimeIndex(missing))
    n = np.array([trades_of(t) for t in idx], dtype="int64")
    return pd.DataFrame({"n_trades": n, "quote_volume": np.array([quote_of(t) for t in idx], dtype=float)}, index=idx)


def _self_test() -> None:
    # A: Jan full month, Feb partly covered (10 days), 1 trade every minute except every 10th minute has zero trades
    a = _frame("2026-01-01 00:00", "2026-02-10 23:59",
               lambda t: 0 if t.minute % 10 == 0 else 5, lambda t: 0.0 if t.minute % 10 == 0 else 100.0)
    # B: same span with 2 missing minutes in January, 10 trades per minute, 200 quote per minute
    miss = [pd.Timestamp("2026-01-05 03:00", tz="UTC"), pd.Timestamp("2026-01-05 03:01", tz="UTC")]
    b = _frame("2026-01-01 00:00", "2026-02-10 23:59", lambda t: 10, lambda t: 200.0, missing=miss)
    ma, mb = monthly(a, 2026), monthly(b, 2026)
    # January A: 31*1440 minutes, 10% zero-trade, 5 trades in the other 90%
    assert ma.loc["2026-01", "minutes_covered"] == 31 * 1440 and abs(ma.loc["2026-01", "zero_trade_share"] - 0.1) < 1e-12
    assert abs(ma.loc["2026-01", "trades_per_day"] - 1440 * 0.9 * 5) < 1e-9 and abs(ma.loc["2026-01", "quote_per_day"] - 1440 * 0.9 * 100) < 1e-9
    # partly covered February is divided by the days actually covered (10), not 28
    assert abs(ma.loc["2026-02", "days_covered"] - 10.0) < 1e-12 and abs(ma.loc["2026-02", "trades_per_day"] - 1440 * 0.9 * 5) < 1e-9
    # B January with 2 missing minutes: days_covered reduced, per-day rate still 1440 * 10
    assert abs(mb.loc["2026-01", "days_covered"] - (31 * 1440 - 2) / 1440) < 1e-12 and abs(mb.loc["2026-01", "trades_per_day"] - 14400) < 1e-9
    t = build_table(a, b, "A", "B", 2026)
    assert abs(t.loc["2026-01", "ratio_trades_per_day__A_over_B"] - (1440 * 0.9 * 5) / 14400) < 1e-9
    assert abs(t.loc["2026-01", "ratio_quote_per_day__A_over_B"] - (1440 * 0.9 * 100) / (1440 * 200)) < 1e-9
    # another year is excluded
    assert monthly(a, 2025).empty
    print("  monthly table: per-day rates use days actually covered, zero-trade share and ratios as defined")

    with tempfile.TemporaryDirectory() as tmp:
        raw, outp = Path(tmp) / "raw", Path(tmp) / "out"
        raw.mkdir()
        for name, f in (("ETH_FDUSD", a), ("ETH_USDT", b)):
            f.reset_index(names="date").to_feather(raw / f"{name}-1m.feather")
        main(["--raw-dir", str(raw), "--output-dir", str(outp), "--year", "2026"])
        j = json.loads((outp / "liquidity_monthly_2026.json").read_text())
        assert j["descriptive_only"] == "no returns computed" and "2026-01" in j["table"] and (outp / "liquidity_monthly_2026.csv").exists()
        # a frame without the raw columns is refused with a clear message
        pd.DataFrame({"date": a.index[:5], "open": 1.0}).to_feather(raw / "BAD_USDT-1m.feather")
        try:
            load(raw, "BAD_USDT")
        except ValueError as e:
            assert "RAW store" in str(e)
        else:
            raise AssertionError("missing columns must raise")
    print("Self-test passed: liquidity_table.py computes the monthly trades and quote volume per day as defined.")


if __name__ == "__main__":
    sys.exit(main())
