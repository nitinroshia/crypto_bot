"""
Annualized realized volatility from daily closes, restricted to the discovery sample.

Work order 1.4, section 4.3: check whether section 3's break-even hit-rate table needs a
pair-specific version. This is a descriptive statistic computed ONLY over discovery data
(<= 2025-08-31 23:59:59 UTC) -- restricting to discovery is not a holdout violation, it's the
opposite: computing it on the full series (holdout included) WOULD be one.

METHOD (stated plainly, since the annualization convention is a real choice, not a fact)
  1. Load daily closes, keep only rows with date <= the discovery cutoff.
  2. Daily log return r_t = ln(C_t / C_{t-1}), computed AFTER the cutoff filter, so no return
     spans the cutoff boundary (a return using a post-cutoff close never enters this calculation).
  3. sigma_daily = sample std of r_t (ddof=1).
  4. Annualize two ways, both reported, since crypto has no single settled convention:
       sigma_365 = sigma_daily * sqrt(365)   -- DEFAULT/headline: these markets trade every
                                                 calendar day, so 365 is the number of return
                                                 observations actually contributing to a year.
       sigma_252 = sigma_daily * sqrt(252)   -- labeled alternate: matches the trad-fi
                                                 convention some crypto research still uses for
                                                 cross-asset comparability.
  Mean daily return, sample size and the exact date range used are reported alongside so the
  discovery-only restriction is checkable, not just asserted.

    python3 user_data/analysis/volatility_report.py                       # ETH_USDT, BTC_USDT
    python3 user_data/analysis/volatility_report.py --pairs ETH_USDT BTC_USDT --self-test
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
TRADING_DAYS = {"365": 365, "252": 252}


def load_daily_closes(raw_dir: Path, pair: str) -> pd.DataFrame:
    path = raw_dir / f"{pair}-1d.feather"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_feather(path, columns=["date", "close"])
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.as_unit("ns")
    return df.sort_values("date").reset_index(drop=True)


def discovery_log_returns(daily: pd.DataFrame, cutoff: pd.Timestamp = DISCOVERY_CUTOFF) -> pd.Series:
    """Log returns computed strictly within the discovery sample: the close series is cut to
    <= cutoff FIRST, so the return spanning into the cutoff boundary from outside never appears."""
    d = daily[daily["date"] <= cutoff].sort_values("date")
    if len(d) < 2:
        return pd.Series(dtype=float)
    r = np.log(d["close"].to_numpy()[1:] / d["close"].to_numpy()[:-1])
    return pd.Series(r, index=d["date"].iloc[1:].to_numpy())


def volatility_stats(returns: pd.Series) -> dict:
    if len(returns) < 2:
        return {"n": int(len(returns)), "status": "INSUFFICIENT_DATA"}
    sigma_daily = float(returns.std(ddof=1))
    return {
        "n": int(len(returns)), "status": "OK",
        "first_return_date": str(returns.index.min()), "last_return_date": str(returns.index.max()),
        "mean_daily_log_return": float(returns.mean()), "sigma_daily": sigma_daily,
        "annualized_365": sigma_daily * np.sqrt(TRADING_DAYS["365"]),
        "annualized_252": sigma_daily * np.sqrt(TRADING_DAYS["252"]),
    }


def report_pair(raw_dir: Path, pair: str, cutoff: pd.Timestamp = DISCOVERY_CUTOFF) -> dict:
    daily = load_daily_closes(raw_dir, pair)
    returns = discovery_log_returns(daily, cutoff)
    stats = volatility_stats(returns)
    return {"pair": pair, "discovery_cutoff": str(cutoff), "daily_closes_available": int(len(daily)), **stats}


def print_report(r: dict) -> None:
    if r["status"] != "OK":
        print(f"{r['pair']}: {r['status']} (only {r['n']} discovery-sample daily returns available)")
        return
    print(f"{r['pair']}: {r['n']} discovery-sample daily returns, {r['first_return_date'][:10]} .. {r['last_return_date'][:10]}")
    print(f"  daily sigma {r['sigma_daily']:.6f}   mean daily log return {r['mean_daily_log_return']:.6f}")
    print(f"  annualized (x sqrt(365), DEFAULT): {r['annualized_365']:.4f}")
    print(f"  annualized (x sqrt(252), labeled alternate): {r['annualized_252']:.4f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", type=Path, default=Path("user_data/data/binance_raw"))
    ap.add_argument("--pairs", nargs="+", default=["ETH_USDT", "BTC_USDT"])
    ap.add_argument("--output-dir", type=Path, default=Path("user_data/analysis/results"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        _self_test()
        return 0
    reports = []
    for pair in args.pairs:
        r = report_pair(args.raw_dir, pair)
        print_report(r)
        reports.append(r)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "volatility_discovery_sample.json"
    out.write_text(json.dumps({"pairs": reports}, indent=2))
    print(f"\nWrote {out}")
    return 0


# --------------------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------------------
def _self_test() -> None:
    # 1. Known-variance synthetic data: daily log returns ~ N(0, sigma^2), verify the estimator
    #    recovers sigma (and both annualizations) within sampling error, and that ddof=1 is used
    #    (matters at this sample size).
    rng = np.random.default_rng(7)
    true_sigma_daily = 0.02
    n = 2000
    log_rets = rng.normal(0, true_sigma_daily, n)
    closes = 100 * np.exp(np.cumsum(log_rets))
    dates = pd.date_range("2019-01-01", periods=n + 1, freq="1D", tz="UTC")
    daily = pd.DataFrame({"date": dates, "close": np.concatenate([[100.0], closes])})
    cutoff = dates[-1] + pd.Timedelta(days=1)   # include every row
    r = volatility_stats(discovery_log_returns(daily, cutoff))
    assert r["n"] == n
    assert abs(r["sigma_daily"] - true_sigma_daily) < 0.001, f"estimated sigma {r['sigma_daily']} vs true {true_sigma_daily}"
    assert abs(r["annualized_365"] - r["sigma_daily"] * np.sqrt(365)) < 1e-9, "annualized_365 must equal sigma_daily * sqrt(365) exactly"
    assert abs(r["annualized_252"] - r["sigma_daily"] * np.sqrt(252)) < 1e-9, "annualized_252 must equal sigma_daily * sqrt(252) exactly"
    manual_sigma = float(pd.Series(np.log(daily["close"].to_numpy()[1:] / daily["close"].to_numpy()[:-1])).std(ddof=1))
    assert abs(r["sigma_daily"] - manual_sigma) < 1e-12, "must match ddof=1 (sample) std exactly"
    print(f"  known-variance recovery: true sigma_daily={true_sigma_daily}, estimated={r['sigma_daily']:.6f} (n={n})")

    # 2. Cutoff restriction: a return spanning the cutoff boundary must NEVER appear, whether the
    #    cutoff falls exactly on a bar or between bars.
    cut = dates[500]                                   # cutoff exactly on a daily close
    r2 = discovery_log_returns(daily, cut)
    assert r2.index.max() == dates[500], "the last return must end exactly at the cutoff bar, using no later close"
    assert len(r2) == 500
    cut_between = dates[500] + pd.Timedelta(hours=12)  # cutoff between two daily bars
    r2b = discovery_log_returns(daily, cut_between)
    assert r2b.index.max() == dates[500], "a between-bar cutoff must not admit the next bar's return"
    print("  cutoff restriction: no return uses a close later than the cutoff, on-bar or between-bar")

    # 3. Insufficient data (0 or 1 closes in the discovery window) is reported, not divided-by-zero
    tiny = daily.iloc[:1]
    assert volatility_stats(discovery_log_returns(tiny, cutoff))["status"] == "INSUFFICIENT_DATA"
    empty = daily.iloc[:0]
    assert volatility_stats(discovery_log_returns(empty, cutoff))["status"] == "INSUFFICIENT_DATA"
    print("  fewer than 2 discovery-sample closes reports INSUFFICIENT_DATA rather than crashing")

    # 4. Full CLI round-trip, two pairs, in the system temp dir (project temp/ is discontinued)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        daily.to_feather(raw / "ETH_USDT-1d.feather")
        daily.assign(close=daily["close"] * 1.5).to_feather(raw / "BTC_USDT-1d.feather")
        out_dir = raw / "out"
        rc = main(["--raw-dir", str(raw), "--pairs", "ETH_USDT", "BTC_USDT", "--output-dir", str(out_dir)])
        assert rc == 0
        j = json.loads((out_dir / "volatility_discovery_sample.json").read_text())
        assert len(j["pairs"]) == 2 and all(p["status"] == "OK" for p in j["pairs"])
        eth, btc = j["pairs"]
        assert abs(eth["sigma_daily"] - btc["sigma_daily"]) < 1e-9, "a constant price scaling must not change volatility"
    print("Self-test passed: volatility_report.py restricts correctly to the discovery sample and annualizes both ways.")


if __name__ == "__main__":
    sys.exit(main())
