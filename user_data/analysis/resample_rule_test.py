"""
Open-price test (work order 1.1): does building coarse bars from TRADED minutes only
reproduce the exchange's native bars?

For every timeframe (5m, 15m, 30m, 1h, 1d, 1w) it rebuilds the bars from the 1m file
twice -- the original rule ("filled": every 1m row counts, including flat zero-trade
placeholders) and the new rule ("traded": open = first traded minute, high/low = extremes of
traded minutes, close = last traded minute, empty bin carries the previous close) -- and
counts mismatches against the native file in open, high, low, close and volume. Only
COMPLETE bins are compared (a bin the 1m file covers only partly can never match).

Decision rule from the mathematician: if the traded rule shows zero mismatches, it becomes
the resampling rule everywhere (a one-line default flip in resample.py). Any residual
mismatch is listed with the facts needed to explain it.

    python3 user_data/analysis/resample_rule_test.py
    python3 user_data/analysis/resample_rule_test.py --self-test
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from resample import compare_resampled_vs_native, resample_ohlcv

TFS = ("5m", "15m", "30m", "1h", "1d", "1w")
STEP = {"5m": pd.Timedelta(minutes=5), "15m": pd.Timedelta(minutes=15), "30m": pd.Timedelta(minutes=30),
        "1h": pd.Timedelta(hours=1), "1d": pd.Timedelta(days=1), "1w": pd.Timedelta(days=7)}


def _load(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df.set_index("date").sort_index()


def complete_bins(index: pd.DatetimeIndex, tf: str, first: pd.Timestamp, last: pd.Timestamp) -> pd.DatetimeIndex:
    """Bins whose whole window lies inside the 1m file's coverage."""
    return index[(index >= first) & (index + STEP[tf] <= last + pd.Timedelta(minutes=1))]


def mismatch_examples(df_1m: pd.DataFrame, rebuilt: pd.DataFrame, native: pd.DataFrame, tf: str, limit: int = 8) -> list[dict]:
    out = []
    for col in ("open", "high", "low", "close", "volume"):
        tol = 1e-3 if col == "volume" else 1e-6
        idx = rebuilt.index.intersection(native.index)
        bad = idx[((rebuilt.loc[idx, col] - native.loc[idx, col]).abs() > tol).to_numpy()]
        for ts in bad[:limit]:
            window = df_1m.loc[ts: ts + STEP[tf] - pd.Timedelta(minutes=1)]
            out.append({
                "bin": str(ts), "column": col, "rebuilt": float(rebuilt.loc[ts, col]), "native": float(native.loc[ts, col]),
                "minutes_in_bin": int(len(window)), "traded_minutes_in_bin": int((window["volume"] > 0).sum()),
                "first_minute_flat": bool(window["volume"].iloc[0] == 0) if len(window) else None,
            })
    return out[:limit * 2]


def run_test(data_dir: Path, raw_dir: Path | None, pair: str) -> dict:
    df_1m = _load(data_dir / f"{pair}-1m.feather")
    if df_1m is None:
        raise FileNotFoundError(f"{data_dir / (pair + '-1m.feather')} not found")
    first, last = df_1m.index.min(), df_1m.index.max()
    report: dict = {"pair": pair, "one_minute_range": [str(first), str(last)], "timeframes": {}}

    # 'traded' is defined as volume > 0; confirm that is the same set as n_trades > 0 on the raw store.
    if raw_dir is not None:
        raw = _load(raw_dir / f"{pair}-1m.feather")
        if raw is not None and "n_trades" in raw.columns:
            common = raw.index.intersection(df_1m.index)
            same = bool(((raw.loc[common, "volume"] > 0) == (raw.loc[common, "n_trades"] > 0)).all())
            report["volume_gt0_equals_n_trades_gt0"] = same

    all_zero, untested = True, []
    for tf in TFS:
        native = _load(data_dir / f"{pair}-{tf}.feather")
        if native is None:
            report["timeframes"][tf] = {"status": "NATIVE_FILE_NOT_FOUND"}
            untested.append(tf)
            continue
        entry = {}
        for rule in ("filled", "traded"):
            rebuilt = resample_ohlcv(df_1m, tf, rule=rule)
            keep = complete_bins(rebuilt.index, tf, first, last)
            r_, n_ = rebuilt.loc[keep], native.loc[native.index.intersection(keep)]
            cmp_ = compare_resampled_vs_native(r_, n_)
            entry[rule] = {
                "bins_compared": cmp_["overlap_rows"], "status": cmp_["status"],
                "mismatched_rows": {c: m["n_mismatched_rows"] for c, m in cmp_.get("mismatches", {}).items()},
            }
            if rule == "traded":
                entry["missing_bins_in_rebuilt"] = int(len(native.index.intersection(keep).difference(r_.index)))
                if cmp_["status"] != "MATCH":
                    entry["examples_traded_rule"] = mismatch_examples(df_1m, r_, n_.loc[n_.index.intersection(r_.index)], tf)
        all_zero &= entry["traded"]["status"] == "MATCH"
        report["timeframes"][tf] = entry
    note = f" (NOT TESTED, no native file: {', '.join(untested)})" if untested else ""
    report["verdict"] = (f"ZERO MISMATCHES with the traded rule on every tested timeframe{note} -> adopt it as the default resampling rule"
                         if all_zero and len(untested) < len(TFS) else
                         "Residual mismatches remain under the traded rule -- see examples; do NOT flip the default yet")
    return report


def print_report(rep: dict) -> None:
    print(f"Open-price test, {rep['pair']} 1m {rep['one_minute_range'][0][:16]} .. {rep['one_minute_range'][1][:16]}")
    if "volume_gt0_equals_n_trades_gt0" in rep:
        print(f"'traded' (volume>0) is the same set as n_trades>0 on the raw store: {rep['volume_gt0_equals_n_trades_gt0']}")
    print(f"\n{'tf':4s} {'bins':>7s} | {'filled rule: mismatched rows':38s} | traded rule")
    for tf, e in rep["timeframes"].items():
        if "filled" not in e:
            print(f"{tf:4s} {e['status']}")
            continue
        print(f"{tf:4s} {e['filled']['bins_compared']:7d} | {str(e['filled']['mismatched_rows']):38s} | "
              f"{e['traded']['status']} {e['traded']['mismatched_rows'] or ''}")
        for ex in e.get("examples_traded_rule", [])[:5]:
            print(f"       e.g. {ex}")
    print(f"\nVERDICT: {rep['verdict']}")


def _self_test() -> None:
    rng = np.random.default_rng(7)
    days, n_min = 10, 10 * 1440
    counts = rng.poisson(1.6, n_min)
    mot = np.repeat(np.arange(n_min), counts)
    ts = pd.Timestamp("2026-01-05", tz="UTC").timestamp() + mot * 60 + rng.uniform(0, 60, len(mot))
    trades = pd.DataFrame({"t": pd.to_datetime(np.sort(ts), unit="s", utc=True).as_unit("ns"),
                           "price": np.round(3000 + np.cumsum(rng.normal(0, 0.15, len(mot))), 2), "size": rng.gamma(2, 0.5, len(mot))})

    def bars(freq, n):
        g = trades.set_index("t").resample(freq, label="left", closed="left")
        b = g["price"].agg(open="first", high="max", low="min", close="last"); b["volume"] = g["size"].sum()
        b = b.reindex(pd.date_range("2026-01-05", periods=n, freq=freq, tz="UTC").as_unit("ns"))
        e, prev = b["close"].isna(), b["close"].ffill()
        for c in ("open", "high", "low", "close"):
            b.loc[e, c] = prev[e]
        b.loc[e, "volume"] = 0.0
        return b.dropna(subset=["close"])

    spec = {"1m": ("1min", n_min), "5m": ("5min", n_min // 5), "15m": ("15min", n_min // 15), "30m": ("30min", n_min // 30),
            "1h": ("1h", n_min // 60), "1d": ("1D", days)}
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for tf, (freq, n) in spec.items():
            b = bars(freq, n)
            # start the 1m file a few hours after the native files: partial first bins must be ignored
            if tf == "1m":
                b = b.iloc[7 * 60 + 13:]
            b.reset_index(names="date").to_feather(d / f"ETH_FDUSD-{tf}.feather")
        # weekly native from trades on Monday anchors would need >7 days of Mondays; skip -> reported as not found
        rep = run_test(d, None, "ETH_FDUSD")
        for tf in ("5m", "15m", "30m", "1h", "1d"):
            e = rep["timeframes"][tf]
            assert e["traded"]["status"] == "MATCH", (tf, e)
            assert e["filled"]["status"] == "MISMATCH" or tf == "1d", (tf, e)
            assert e["traded"]["bins_compared"] > 0 and e["missing_bins_in_rebuilt"] == 0
        assert rep["timeframes"]["1w"]["status"] == "NATIVE_FILE_NOT_FOUND"
        assert rep["timeframes"]["1d"]["traded"]["bins_compared"] == days - 1   # partial first day excluded
        print_report(rep)
    print("\nSelf-test passed: the test excludes partial bins, shows the filled-rule mismatches, and the traded rule matches.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("user_data/data/binance"))
    ap.add_argument("--raw-dir", type=Path, default=None)
    ap.add_argument("--pair", default="ETH_FDUSD")
    ap.add_argument("--output-dir", type=Path, default=Path("user_data/analysis/results"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        _self_test()
        return
    raw = args.raw_dir or args.data_dir.parent / "binance_raw"
    rep = run_test(args.data_dir, raw if raw.exists() else None, args.pair)
    print_report(rep)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "resample_rule_test.json").write_text(json.dumps(rep, indent=2, default=str))
    print(f"\nWritten: {args.output_dir / 'resample_rule_test.json'}")


if __name__ == "__main__":
    main()
