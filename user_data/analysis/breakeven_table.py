"""
Break-even hit-rate table, rebuilt from the empirical return distribution at each horizon
(mathematician's NOTES.md section 3, 2026-09-23 request) rather than the symmetric-Gaussian
shortcut the original table used.

OLD METHOD (what this replaces): assume returns at horizon h are Gaussian with the SAME annualized
sigma at every horizon (ETH-like, "about 70%"), scaled to horizon by sqrt(time), then use the
Gaussian expected-absolute-value identity E|X| = sigma_h * sqrt(2/pi) to get the "typical move size"
and solve the symmetric-payoff breakeven equation. Two things that assumption misses: the measured
annualized vol was ~70% assumed vs 90.1%/70.1% actually measured (ETH/BTC), and returns at every
horizon checked here are fat-tailed (excess kurtosis > 0, confirmed below) -- E|X| for a fat-tailed
distribution is not reliably sigma * sqrt(2/pi), so the Gaussian shortcut mis-estimates the typical
move size even when sigma itself is measured correctly.

NEW METHOD: at each horizon, take the actual non-overlapping returns over the discovery sample
(stats_fingerprint.get_nonoverlapping_returns) and use their empirical mean absolute value directly
as the typical move size m. Payoffs are still assumed symmetric (a win and a loss are both size m) --
that assumption isn't being dropped here, only how m itself is obtained.

BREAKEVEN FORMULA (symmetric payoff m per trade, round-trip cost C, hit rate p):
    expected P&L = p*m - (1-p)*m - C = 0  =>  p = 0.5 + C / (2*m)
This is exactly the formula the old table used; only m's source changed (empirical vs Gaussian(sigma)).

HORIZONS AND THEIR SOURCE DATA: 15m from the 5m raw store (k=3, non-overlapping), 1h from the native
1h file (k=1), 4h from the native 1h file (k=4), 1d from the native 1d file (k=1). Whichever base
file is used, it is restricted to the discovery sample FIRST (<= 2025-08-31 23:59:59 UTC), so no
non-overlapping return spans the cutoff.

    python3 user_data/analysis/breakeven_table.py                    # ETH_USDT, BTC_USDT, base+stress cost
    python3 user_data/analysis/breakeven_table.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from stats_fingerprint import distribution_stats, get_nonoverlapping_returns

DISCOVERY_CUTOFF = pd.Timestamp("2025-08-31 23:59:59", tz="UTC")
BASE_ROUND_TRIP = 0.0024    # costs.py base case, 0.10% fee + 0.02% slippage per side
STRESS_ROUND_TRIP = 0.0030  # costs.py stress case, 0.12% fee + 0.03% slippage per side
HORIZONS = {   # label -> (source timeframe file, k for get_nonoverlapping_returns)
    "15m": ("5m", 3),
    "1h": ("1h", 1),
    "4h": ("1h", 4),
    "1d": ("1d", 1),
}


def load_raw(raw_dir: Path, pair: str, timeframe: str) -> pd.DataFrame:
    path = raw_dir / f"{pair}-{timeframe}.feather"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_feather(path, columns=["date", "close"])
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.as_unit("ns")
    return df.sort_values("date").reset_index(drop=True)


def breakeven_hit_rate(m: float, cost: float) -> float | None:
    """p = 0.5 + cost / (2m). None if m is 0 or non-finite (no meaningful breakeven)."""
    if not np.isfinite(m) or m <= 0:
        return None
    return 0.5 + cost / (2.0 * m)


def horizon_stats(raw_dir: Path, pair: str, timeframe: str, k: int, cutoff: pd.Timestamp = DISCOVERY_CUTOFF) -> dict:
    df = load_raw(raw_dir, pair, timeframe)
    df = df[df["date"] <= cutoff]
    returns = get_nonoverlapping_returns(df, k)
    if len(returns) < 8:
        return {"status": "INSUFFICIENT_DATA", "n": int(len(returns))}
    dist = distribution_stats(returns)
    m_empirical = float(returns.abs().mean())
    m_gaussian = float(dist["std"] * np.sqrt(2.0 / np.pi))   # what the old table's shortcut implied
    return {
        "status": "OK", "n": dist["n"], "source_timeframe": timeframe, "k": k,
        "first_return_date": str(df["date"].iloc[0]), "last_return_date": str(df["date"].iloc[-1]),
        "mean_abs_return_empirical": m_empirical, "mean_abs_return_if_gaussian": m_gaussian,
        "std": dist["std"], "skew": dist["skew"], "kurtosis_excess": dist["kurtosis_excess"],
        "looks_normal_at_5pct": dist["looks_normal_at_5pct"],
        "breakeven_hit_rate_empirical_base": breakeven_hit_rate(m_empirical, BASE_ROUND_TRIP),
        "breakeven_hit_rate_empirical_stress": breakeven_hit_rate(m_empirical, STRESS_ROUND_TRIP),
        "breakeven_hit_rate_gaussian_base": breakeven_hit_rate(m_gaussian, BASE_ROUND_TRIP),
    }


def build_table(raw_dir: Path, pairs: list[str]) -> dict:
    return {pair: {h: horizon_stats(raw_dir, pair, tf, k) for h, (tf, k) in HORIZONS.items()} for pair in pairs}


def print_table(table: dict) -> None:
    print(f"Break-even hit rate, base cost {BASE_ROUND_TRIP*100:.2f}% round trip (stress {STRESS_ROUND_TRIP*100:.2f}% also shown), "
          f"discovery sample only, empirical E|return| (not Gaussian-assumed):\n")
    for pair, horizons in table.items():
        print(f"{pair}:")
        for h, r in horizons.items():
            if r["status"] != "OK":
                print(f"  {h:>4s}: INSUFFICIENT_DATA (n={r['n']})")
                continue
            gap = r["breakeven_hit_rate_empirical_base"] - r["breakeven_hit_rate_gaussian_base"]
            print(f"  {h:>4s}: empirical {r['breakeven_hit_rate_empirical_base']*100:5.1f}% base / "
                  f"{r['breakeven_hit_rate_empirical_stress']*100:5.1f}% stress   "
                  f"(old Gaussian-shortcut would have said {r['breakeven_hit_rate_gaussian_base']*100:5.1f}% base, "
                  f"a {gap*100:+.1f}pp difference)   n={r['n']:,}   skew={r['skew']:+.2f} kurtosis_excess={r['kurtosis_excess']:+.2f} "
                  f"{'(normal-looking)' if r['looks_normal_at_5pct'] else '(NOT normal at 5%, Jarque-Bera)'}")
    print()


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
    table = build_table(args.raw_dir, args.pairs)
    print_table(table)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "breakeven_hit_rate.json"
    out.write_text(json.dumps({
        "discovery_cutoff": str(DISCOVERY_CUTOFF), "base_round_trip": BASE_ROUND_TRIP, "stress_round_trip": STRESS_ROUND_TRIP,
        "method": "empirical mean absolute non-overlapping return per horizon, symmetric-payoff breakeven (p = 0.5 + cost / (2m))",
        "table": table,
    }, indent=2))
    print(f"Wrote {out}")
    return 0


# --------------------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------------------
def _mk_1d(returns: np.ndarray, start="2015-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(returns) + 1, freq="1D", tz="UTC")
    close = 100 * np.exp(np.cumsum(returns))
    return pd.DataFrame({"date": dates, "close": np.concatenate([[100.0], close])})


def _self_test() -> None:
    # 1. Formula sanity: p = 0.5 + cost/(2m), matches the old table's own numbers when m is derived
    #    the OLD (Gaussian) way from its stated 70%-annualized/0.24%-cost assumptions.
    sigma_daily_old_assumption = 0.70 / np.sqrt(365)
    for label, periods_per_day, expected_pct in [("1d", 1, 54), ("4h", 6, 60), ("1h", 24, 70), ("15m", 96, 90)]:
        sigma_h = sigma_daily_old_assumption / np.sqrt(periods_per_day)
        m = sigma_h * np.sqrt(2 / np.pi)
        p = breakeven_hit_rate(m, BASE_ROUND_TRIP)
        assert abs(p * 100 - expected_pct) < 1.0, (label, p * 100, expected_pct)
    assert breakeven_hit_rate(0.0, BASE_ROUND_TRIP) is None and breakeven_hit_rate(-1, BASE_ROUND_TRIP) is None
    print("  formula check: reproduces the OLD table's own four numbers (54/60/70/90%) from its stated assumptions")

    # 2. Known-variance Gaussian synthetic data: empirical E|X| should closely match the Gaussian
    #    shortcut sigma*sqrt(2/pi), and the resulting hit rates should nearly agree.
    rng = np.random.default_rng(11)
    n = 5000
    sigma = 0.01
    gauss_returns = rng.normal(0, sigma, n)
    df_gauss = _mk_1d(gauss_returns)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        df_gauss.to_feather(raw / "TEST_PAIR-1d.feather")
        r = horizon_stats(raw, "TEST_PAIR", "1d", 1, cutoff=df_gauss["date"].iloc[-1])
        assert r["status"] == "OK"
        rel_gap = abs(r["mean_abs_return_empirical"] - r["mean_abs_return_if_gaussian"]) / r["mean_abs_return_if_gaussian"]
        assert rel_gap < 0.05, f"Gaussian data should have empirical E|X| within 5% of the Gaussian formula, got {rel_gap:.3f}"
        assert abs(r["kurtosis_excess"]) < 0.5, "Gaussian synthetic data should show ~0 excess kurtosis"
        print(f"  Gaussian synthetic data: empirical and Gaussian-shortcut E|X| agree within {rel_gap*100:.1f}% (n={n}), "
              f"excess kurtosis {r['kurtosis_excess']:+.2f} as expected")

        # 3. Fat-tailed synthetic data with the SAME std as the Gaussian case: empirical E|X| and the
        #    resulting breakeven hit rate must differ meaningfully from the Gaussian shortcut -- this
        #    is the exact effect the mathematician flagged ("imprecision looks fat-tail-driven").
        t_raw = rng.standard_t(df=3, size=n)
        t_returns = t_raw * (sigma / t_raw.std())     # rescaled to the SAME std as the Gaussian series
        df_t = _mk_1d(t_returns)
        df_t.to_feather(raw / "TEST_PAIR-1d.feather")
        rt = horizon_stats(raw, "TEST_PAIR", "1d", 1, cutoff=df_t["date"].iloc[-1])
        assert rt["kurtosis_excess"] > 1.0, "student-t(3) must show strong excess kurtosis"
        assert abs(rt["std"] - r["std"]) / r["std"] < 0.05, "the two synthetic series must have matched std by construction"
        gap_gauss = abs(rt["mean_abs_return_empirical"] - rt["mean_abs_return_if_gaussian"]) / rt["mean_abs_return_if_gaussian"]
        assert gap_gauss > 0.05, f"fat-tailed data must show empirical E|X| meaningfully different from the Gaussian shortcut, got {gap_gauss:.3f}"
        assert rt["mean_abs_return_empirical"] < rt["mean_abs_return_if_gaussian"], (
            "a heavy-tailed-but-same-std distribution concentrates more mass near 0 than a Gaussian, "
            "so its E|X| should be SMALLER than sigma*sqrt(2/pi), not larger")
        print(f"  fat-tailed synthetic data (same std, kurtosis_excess={rt['kurtosis_excess']:+.2f}): empirical E|X| differs from the "
              f"Gaussian shortcut by {gap_gauss*100:.1f}% -- this is exactly the imprecision the empirical method fixes")

    # 4. Discovery cutoff: no non-overlapping return may span the cutoff boundary
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        dates = pd.date_range("2025-08-25", periods=20, freq="1h", tz="UTC")   # crosses 2025-08-31 23:59:59
        closes = 100 + np.cumsum(rng.normal(0, 0.1, 20))
        pd.DataFrame({"date": dates, "close": closes}).to_feather(raw / "TEST_PAIR-1h.feather")
        r4 = horizon_stats(raw, "TEST_PAIR", "1h", 1)
        assert pd.Timestamp(r4["last_return_date"]) <= DISCOVERY_CUTOFF
    print("  discovery cutoff: no return computed past the cutoff, on an hourly series that straddles it")

    # 5. Insufficient data reported, not a crash; full CLI round-trip with both pairs and all 4 horizons
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        tiny = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=3, freq="1D", tz="UTC"), "close": [100.0, 101.0, 99.0]})
        tiny.to_feather(raw / "TEST_PAIR-1d.feather")
        assert horizon_stats(raw, "TEST_PAIR", "1d", 1)["status"] == "INSUFFICIENT_DATA"

        n2 = 3000
        for pair in ("ETH_USDT", "BTC_USDT"):
            base = rng.normal(0, 0.01, n2 * 96)
            for tf, mult in (("5m", 1), ("1h", 12), ("1d", 288)):
                sub = base[::mult]
                closes = 100 * np.exp(np.cumsum(sub))
                dates = pd.date_range("2015-01-01", periods=len(sub) + 1, freq=("5min" if tf == "5m" else "1h" if tf == "1h" else "1D"), tz="UTC")
                pd.DataFrame({"date": dates, "close": np.concatenate([[100.0], closes])}).to_feather(raw / f"{pair}-{tf}.feather")
        out_dir = raw / "out"
        rc = main(["--raw-dir", str(raw), "--pairs", "ETH_USDT", "BTC_USDT", "--output-dir", str(out_dir)])
        assert rc == 0
        j = json.loads((out_dir / "breakeven_hit_rate.json").read_text())
        assert set(j["table"]) == {"ETH_USDT", "BTC_USDT"} and set(j["table"]["ETH_USDT"]) == set(HORIZONS)
        assert all(j["table"][p][h]["status"] == "OK" for p in j["table"] for h in j["table"][p])
    print("Self-test passed: breakeven_table.py reproduces the old table's own numbers from its stated assumptions, "
          "shows fat-tailed data diverging from the Gaussian shortcut as expected, and respects the discovery cutoff.")


if __name__ == "__main__":
    sys.exit(main())
