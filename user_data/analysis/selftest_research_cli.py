"""
Self-test for research_cli.py's work-order-#1 changes (there is no __main__
block in research_cli.py itself). Builds synthetic feather files with KNOWN
structure in a temp dir and checks:
  1. bare timeframe keys still work and PAIR:tf keys resolve (backward compat);
  2. the four built-in formulas still run through run_once;
  3. walk-forward validates ONLY the fit-selected lag (crafted tables where the
     old "best lag within 1 step" rule and the new rule disagree);
  4. walk-forward end-to-end: an injected real effect replicates in every
     split, pure noise does not, and windows are half-open;
  5. run_once records family size and adjusted p.

    python3 selftest_research_cli.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import research_cli as rc
from resample import resample_ohlcv


def _make_ohlcv(ret: pd.Series, rng) -> pd.DataFrame:
    close = 3000 * (1 + ret).cumprod()
    open_ = close.shift(1).fillna(3000.0)
    spread = np.abs(rng.normal(0, 0.0002, len(ret)))
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * (1 + spread),
            "low": np.minimum(open_, close) * (1 - spread),
            "close": close,
            "volume": rng.gamma(2, 5, len(ret)),
        }
    )


def _write(dirpath: Path, pair: str, tf: str, df: pd.DataFrame) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    df.reset_index(names="date").to_feather(dirpath / f"{pair}-{tf}.feather")


def build_dataset(root: Path, inject: bool, seed: int = 4, days: int = 60) -> tuple[Path, Path]:
    """1m ETH_FDUSD (+5m, 15m natives resampled from it). If inject, the 1m
    return j=3 minutes after every 5m bar's close gets +0.05 * that 5m bar's
    return -- a real, modest lead-lag effect at a known lag."""
    rng = np.random.default_rng(seed)
    n = days * 1440
    idx = pd.date_range("2026-03-01", periods=n, freq="1min", tz="UTC")
    ret = pd.Series(rng.normal(0, 0.0007, n), index=idx)
    if inject:
        price = (1 + ret).cumprod()
        nb = n // 5
        close5 = price.iloc[np.arange(nb) * 5 + 4].to_numpy()
        r5 = np.r_[np.nan, close5[1:] / close5[:-1] - 1]  # 5m bar k covers minutes 5k..5k+4
        tgt = np.arange(nb) * 5 + 5 + 2                    # 3rd minute after the bar's close
        ok = (tgt < n) & np.isfinite(r5)
        ret.iloc[tgt[ok]] += 0.05 * r5[ok]
    df = _make_ohlcv(ret, rng)
    data_dir, raw_dir = root / "binance", root / "binance_raw"
    for tf in ("1m", "5m", "15m"):
        _write(data_dir, "ETH_FDUSD", tf, df if tf == "1m" else resample_ohlcv(df, tf))
    _write(raw_dir, "ETH_USDT", "1m", df)
    return data_dir, raw_dir


def test_fixed_lag_rule() -> None:
    """Old rule: replicated if validate's own best lag is within 1 step and same sign.
    New rule: only the fit-selected lag is tested in validate."""
    fit_best = {"status": "SIGNIFICANT_LAG_FOUND",
                "best_lag": {"lag_bars": 3.0, "n": 900, "beta": 0.05,
                             "t_stat_hac": 4.0, "p_value_hac": 6e-5, "significant_at_5pct": True}}
    fit_df = pd.DataFrame({"lag_bars": [1, 2, 3], "n": 900, "beta": [0.0, 0.01, 0.05],
                           "t_stat_hac": [0.1, 0.5, 4.0], "p_value_hac": [0.9, 0.6, 6e-5],
                           "significant_at_5pct": [False, False, True]})
    # validate: lag 4 is the significant one, lag 3 (the fit lag) is not.
    val_df = pd.DataFrame({"lag_bars": [2, 3, 4], "n": 300, "beta": [0.0, 0.02, 0.06],
                           "t_stat_hac": [0.0, 1.0, 3.5], "p_value_hac": [0.99, 0.30, 4e-4],
                           "significant_at_5pct": [False, False, True]})
    ev = rc.evaluate_fixed_lag(fit_best, fit_df, val_df)
    assert ev["replicated"] is False and ev["reason"] == "NOT_SIGNIFICANT_IN_VALIDATE", ev
    assert ev["fit_family"]["family_size"] == 3

    val_ok = val_df.copy()
    val_ok.loc[val_ok["lag_bars"] == 3, ["beta", "p_value_hac", "significant_at_5pct"]] = [0.04, 0.01, True]
    assert rc.evaluate_fixed_lag(fit_best, fit_df, val_ok)["replicated"] is True

    val_flip = val_ok.copy()
    val_flip.loc[val_flip["lag_bars"] == 3, "beta"] = -0.04
    assert rc.evaluate_fixed_lag(fit_best, fit_df, val_flip)["reason"] == "SIGN_FLIPPED"

    assert rc.evaluate_fixed_lag({"status": "NO_SIGNIFICANT_LAG_FOUND"}, fit_df, val_df)["reason"] == "NO_SIGNIFICANT_LAG_IN_FIT"
    assert rc.evaluate_fixed_lag(fit_best, fit_df, val_df.iloc[0:0])["reason"] == "VALIDATE_TABLE_UNAVAILABLE"
    thin = val_df[val_df["lag_bars"] != 3]
    assert rc.evaluate_fixed_lag(fit_best, fit_df, thin)["reason"] == "VALIDATE_INSUFFICIENT_DATA_AT_FIT_LAG"
    print("  fixed-lag rule: validate tests only the fit-selected lag (a significant neighbour no longer rescues it)")


def main() -> None:
    test_fixed_lag_rule()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # ---- 1/2/5: compat, formulas, family stats (dataset WITH an injected effect) ----------
        data_dir, raw_dir = build_dataset(tmp / "inj", inject=True)
        out_dir = tmp / "out_inj"
        bundle = rc.load_all_dataframes(data_dir, "ETH_FDUSD", ["1m", "5m", "ETH_USDT:1m"])
        assert "1m" in bundle and "ETH_FDUSD:1m" in bundle and "ETH_USDT:1m" in bundle
        assert bundle["1m"].equals(bundle["ETH_FDUSD:1m"])
        print("  bundle: bare keys and PAIR:tf keys both resolve")

        manifest, _ = rc.run_once("event_anchored", data_dir, "ETH_FDUSD", {"pair": "1m:5m"}, 8, out_dir)
        best = manifest["result"]["best_lag"]
        assert int(best["lag_bars"]) == 3, best
        assert manifest["family"]["family_size"] == 8
        assert manifest["family"]["p_bonferroni"] >= manifest["family"]["p_raw"]
        assert manifest["family"]["p_holm"] <= manifest["family"]["p_bonferroni"] + 1e-12
        print(f"  run_once(event_anchored): recovers injected lag 3; family={manifest['family']['family_size']}, "
              f"raw p={manifest['family']['p_raw']:.2g}, Holm p={manifest['family']['p_holm']:.2g}")
        for name, params in (("hac", {"pair": "1m:5m"}), ("nonoverlap", {"pair": "1m:5m"}),
                             ("volume_leads_volatility", {"timeframe": "5m"})):
            m, _ = rc.run_once(name, data_dir, "ETH_FDUSD", params, 6, out_dir)
            assert m["result"] is not None
        print("  hac / nonoverlap / volume_leads_volatility still run")

        # ---- 4: walk-forward end to end -------------------------------------------------------
        wf = rc.run_walkforward("event_anchored", data_dir, "ETH_FDUSD", {"pair": "1m:5m"}, 6,
                                fit_days=30, validate_days=10, step_days=10, output_dir=out_dir)
        assert wf["n_splits"] >= 2
        assert all(sp["replicated"] for sp in wf["splits"]), [sp.get("reason") for sp in wf["splits"]]
        for sp in wf["splits"]:
            assert int(sp["fit_lag"]) == 3 and sp["validate_significant"] and sp["same_sign"]
            assert pd.Timestamp(sp["fit_range"][1]) == pd.Timestamp(sp["validate_range"][0])
        print(f"  walk-forward (injected effect): {wf['n_replicated']}/{wf['n_splits']} splits replicated at fit lag 3")

        noise_dir, _ = build_dataset(tmp / "noise", inject=False, seed=9)
        wf0 = rc.run_walkforward("event_anchored", noise_dir, "ETH_FDUSD", {"pair": "1m:5m"}, 6,
                                 fit_days=30, validate_days=10, step_days=10, output_dir=tmp / "out_noise")
        assert wf0["n_replicated"] < wf0["n_splits"], "pure noise must not replicate in every split"
        print(f"  walk-forward (pure noise): {wf0['n_replicated']}/{wf0['n_splits']} splits replicated (must be < all)")

    print("Self-test passed: research_cli work-order-#1 changes behave as specified.")


if __name__ == "__main__":
    main()
