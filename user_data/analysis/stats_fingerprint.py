"""
Task 3 — Statistical fingerprint per timeframe.

Every function here reports raw numbers (test statistics, p-values, sample
sizes) alongside any pass/fail label. "Looks significant" is not an
acceptable output on its own anywhere in this module.

Non-overlapping windows: `get_nonoverlapping_returns` is the building block
every other function should use for its returns series whenever the caller
wants a lookback > 1 candle. Using pandas' rolling/pct_change with overlap
manufactures artificial autocorrelation purely from shared candles -- that's
a known failure mode, not a style choice.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import acf, adfuller


def get_nonoverlapping_returns(df: pd.DataFrame, k: int, price_col: str = "close") -> pd.Series:
    """
    Non-overlapping k-candle returns: take every k-th row, then pct_change.
    E.g. k=3 on 1m data gives returns over disjoint 3-minute blocks, not a
    rolling 3-candle window recomputed every minute.
    """
    if k < 1:
        raise ValueError("k must be >= 1")
    sampled = df[price_col].iloc[::k]
    return sampled.pct_change().dropna()


def stationarity_test(returns: pd.Series, adf_maxlag: int | None = None) -> dict:
    """Augmented Dickey-Fuller test. Null hypothesis: series has a unit root
    (i.e. is non-stationary). Report the raw statistic and p-value, not just
    a verdict -- borderline cases (p around 0.05) need a human look.

    adf_maxlag: if None (default), uses autolag="AIC", which searches for
    the best lag count via repeated regressions -- this is the correct
    choice for a trusted/final run, but is genuinely expensive at large N
    (confirmed: ~16s for 100k rows in testing; your 260k-row 1m series
    picked used_lag=86, meaning the search space was large). Pass a fixed
    integer (e.g. 20) here for fast iteration while developing/debugging
    the pipeline itself -- it skips the search entirely and just uses that
    lag count. Don't use a fixed maxlag for a result you intend to actually
    interpret; re-run with adf_maxlag=None before trusting a p-value.
    """
    returns = returns.dropna()
    if len(returns) < 20:
        return {
            "n": len(returns),
            "status": "INSUFFICIENT_DATA",
            "note": "Fewer than 20 observations; ADF result would be unreliable.",
        }
    capped_from = None
    if adf_maxlag is None:
        adf_stat, p_value, used_lag, n_obs, crit_values, _ = adfuller(
            returns, autolag="AIC", result_object=False
        )
    else:
        # A fixed adf_maxlag can still exceed statsmodels' own validity bound
        # for a small sample (must be < nobs/2 - 1 - ntrend) -- this shows up
        # on coarse timeframes with modest history (1d, 1w especially)
        # combined with a longer lookback's non-overlapping window shrinking
        # n further. Confirmed: a 209-row 1d series at lookback=5 (~41 non-
        # overlapping observations) hits this with the default --fast
        # maxlag=20. Cap rather than crash, but say so in the result instead
        # of silently changing what was asked for.
        safe_maxlag = max(1, len(returns) // 2 - 2)
        if adf_maxlag > safe_maxlag:
            capped_from = adf_maxlag
        effective_maxlag = min(adf_maxlag, safe_maxlag)
        # autolag=None returns a 5-tuple (no icbest) -- different shape than
        # the autolag="AIC" branch above.
        adf_stat, p_value, used_lag, n_obs, crit_values = adfuller(
            returns, maxlag=effective_maxlag, autolag=None, result_object=False
        )
    result = {
        "n": int(n_obs),
        "adf_statistic": float(adf_stat),
        "p_value": float(p_value),
        "used_lag": int(used_lag),
        "critical_values": {k: float(v) for k, v in crit_values.items()},
        "likely_stationary_at_5pct": bool(p_value < 0.05),
    }
    if capped_from is not None:
        result["adf_maxlag_capped_from"] = capped_from
        result["note"] = (
            f"Requested adf_maxlag={capped_from} exceeded what this sample size allows; "
            f"capped to {effective_maxlag}. Small-sample coarse timeframe/lookback -- "
            f"re-run without --fast (adf_maxlag=None) before trusting this p-value."
        )
    return result


def distribution_stats(returns: pd.Series) -> dict:
    """Mean/std/skew/kurtosis of a return series, plus a normality check
    (Jarque-Bera) so we know how much to trust normal-distribution intuitions
    (like '3-sigma event') at this timeframe."""
    returns = returns.dropna()
    if len(returns) < 8:
        return {"n": len(returns), "status": "INSUFFICIENT_DATA"}
    jb_stat, jb_p = sp_stats.jarque_bera(returns)
    return {
        "n": int(len(returns)),
        "mean": float(returns.mean()),
        "std": float(returns.std()),
        "skew": float(sp_stats.skew(returns)),
        "kurtosis_excess": float(sp_stats.kurtosis(returns)),  # 0 = normal-like tails
        "jarque_bera_stat": float(jb_stat),
        "jarque_bera_p_value": float(jb_p),
        "looks_normal_at_5pct": bool(jb_p > 0.05),
    }


def autocorrelation_analysis(returns: pd.Series, n_lags: int = 10) -> dict:
    """ACF of returns out to n_lags, plus a Ljung-Box test for whether any
    autocorrelation found is statistically distinguishable from noise at
    all. A nonzero ACF value with a high Ljung-Box p-value is noise and
    should be reported as such, not treated as a finding."""
    returns = returns.dropna()
    if len(returns) < n_lags * 3:
        return {
            "n": len(returns),
            "status": "INSUFFICIENT_DATA",
            "note": f"Need at least {n_lags * 3} observations for {n_lags} lags; have {len(returns)}.",
        }
    acf_values = acf(returns, nlags=n_lags, fft=True)
    lb_result = acorr_ljungbox(returns, lags=[n_lags], return_df=True)
    return {
        "n": int(len(returns)),
        "acf_by_lag": {i: float(v) for i, v in enumerate(acf_values) if i > 0},
        "ljung_box_stat": float(lb_result["lb_stat"].iloc[0]),
        "ljung_box_p_value": float(lb_result["lb_pvalue"].iloc[0]),
        "autocorrelation_likely_real_at_5pct": bool(lb_result["lb_pvalue"].iloc[0] < 0.05),
    }


def volume_participation(df: pd.DataFrame, return_col_lookback: int = 1, top_quantile: float = 0.1) -> dict:
    """
    Compares volume on the largest-magnitude-return candles vs. the
    smallest, as a first concrete check of "do bigger moves involve more
    participation" rather than assuming it.
    """
    d = df.copy()
    d["ret"] = d["close"].pct_change(periods=return_col_lookback)
    d = d.dropna(subset=["ret", "volume"])
    if len(d) < 20:
        return {"n": len(d), "status": "INSUFFICIENT_DATA"}

    abs_ret = d["ret"].abs()
    hi_cut = abs_ret.quantile(1 - top_quantile)
    lo_cut = abs_ret.quantile(top_quantile)

    big_move_volume = d.loc[abs_ret >= hi_cut, "volume"]
    small_move_volume = d.loc[abs_ret <= lo_cut, "volume"]

    # Mann-Whitney U rather than a t-test since volume is typically
    # right-skewed, not normal.
    u_stat, p_value = sp_stats.mannwhitneyu(big_move_volume, small_move_volume, alternative="greater")

    return {
        "n_total": int(len(d)),
        "n_big_move_candles": int(len(big_move_volume)),
        "n_small_move_candles": int(len(small_move_volume)),
        "median_volume_big_moves": float(big_move_volume.median()),
        "median_volume_small_moves": float(small_move_volume.median()),
        "mann_whitney_u": float(u_stat),
        "p_value_big_moves_have_more_volume": float(p_value),
        "big_moves_have_more_volume_at_5pct": bool(p_value < 0.05),
    }


def flat_candle_fraction(df: pd.DataFrame) -> dict:
    """
    Fraction of candles that are zero-volume/flat placeholders
    (open==high==low==close, volume==0) -- a liquidity characteristic of
    the pair at this timeframe, not noise. Surfaced explicitly here after
    the resample-vs-native mismatch investigation showed these candles
    carry a stale price forward and can distort ADF/ACF results if not
    accounted for (a flat candle's "0% return" is not the same kind of
    observation as a genuine balanced-trading 0% return).
    """
    is_flat = (
        (df["open"] == df["high"])
        & (df["high"] == df["low"])
        & (df["low"] == df["close"])
        & (df["volume"] == 0)
    )
    return {
        "n_total": int(len(df)),
        "n_flat": int(is_flat.sum()),
        "fraction_flat": float(is_flat.mean()),
    }


def run_full_fingerprint(
    df: pd.DataFrame, lookbacks: list[int] = (1, 3, 5), n_lags: int = 10, adf_maxlag: int | None = None
) -> dict:
    """Convenience wrapper: runs the full battery for one timeframe's
    dataframe across a few non-overlapping lookback lengths.

    adf_maxlag: passed through to stationarity_test -- set to a small fixed
    int (e.g. 20) for fast iteration, leave None for a trusted final run.
    """
    report = {
        "volume_participation": volume_participation(df),
        "flat_candle_fraction": flat_candle_fraction(df),
    }
    for k in lookbacks:
        returns = get_nonoverlapping_returns(df, k)
        report[f"lookback_{k}"] = {
            "stationarity": stationarity_test(returns, adf_maxlag=adf_maxlag),
            "distribution": distribution_stats(returns),
            "autocorrelation": autocorrelation_analysis(returns, n_lags=n_lags),
        }
    return report


if __name__ == "__main__":
    # Self-test on synthetic data with a KNOWN property (independent random
    # walk increments -> should show up as stationary returns, no real
    # autocorrelation, and roughly normal-ish distribution).
    rng = np.random.default_rng(42)
    n = 2000
    prices = 2500 + np.cumsum(rng.normal(0, 1, n))
    volume = rng.uniform(1, 10, n)
    df = pd.DataFrame(
        {
            "close": prices,
            "open": prices,
            "high": prices + 0.5,
            "low": prices - 0.5,
            "volume": volume,
        }
    )

    report = run_full_fingerprint(df, lookbacks=[1, 5])
    lb1 = report["lookback_1"]
    assert lb1["stationarity"]["likely_stationary_at_5pct"], "iid-increment returns should be stationary"
    assert not lb1["autocorrelation"]["autocorrelation_likely_real_at_5pct"], (
        "iid increments should NOT show real autocorrelation"
    )
    print("Self-test passed on synthetic random-walk data:")
    print(f"  ADF p-value (lookback=1): {lb1['stationarity']['p_value']:.4f}")
    print(f"  Ljung-Box p-value (lookback=1): {lb1['autocorrelation']['ljung_box_p_value']:.4f}")
    print(f"  Volume participation p-value: {report['volume_participation']['p_value_big_moves_have_more_volume']:.4f}")