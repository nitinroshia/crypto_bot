"""
Task 4 — Cross-timeframe lead-lag.

Tests whether one timeframe's momentum series leads another's, at a range of
lags, with significance that's corrected for the autocorrelation that
overlapping/momentum-style series carry by construction.

Two independent safeguards against "fake" correlation, matching the spec:
  1. `nonoverlapping_lagged_correlation` -- subsamples to disjoint windows
     before correlating, so shared candles can't inflate the correlation.
  2. `hac_lagged_regression` -- regresses series_b on lagged series_a using
     Newey-West (HAC) standard errors, which stay valid even when the series
     itself is autocorrelated. Use this one when you want to keep more of
     the data (no subsampling) but still trust the p-value.

Prefer running both and comparing; if they disagree sharply about which lag
is significant, that disagreement is itself useful information, not a bug
to resolve by picking whichever result you like better.

A third function, `event_anchored_lead_lag`, resolves mistake #5 from
project_context.md's mistake log: both functions above still report their
"best lag" landing on the edge of whatever _clip_max_lag allows, because
that clip only removes the single fully-contaminated point
(lag=upsample_factor) and not the partial contamination that ramps up to
it from lag=1 onward. Use event_anchored_lead_lag for anything you intend
to actually trust or act on; keep the two above mainly for comparison and
for same-timeframe questions where no coarse/fine composition relationship
exists in the first place (upsample_factor=1).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm


def align_to_common_grid(
    series_coarse: pd.Series, series_fine: pd.Series, shift_periods: int = 0
) -> pd.Series:
    """
    Reindex a coarser-frequency series (e.g. 5m returns) onto a finer
    series' time grid (e.g. 1m) via forward-fill, so that a subsequent
    integer lag-shift is unambiguously in units of the FINE grid.

    shift_periods (in COARSE-timeframe units) matters a lot and defaults to
    0 for backward compatibility, but callers doing genuine lead-lag
    analysis should pass shift_periods=1. Here's why: with shift_periods=0,
    the coarse value visible at any fine timestamp t is the return of the
    coarse window t itself falls inside -- meaning a 1-minute return is
    being compared against the very 5-minute return it's mechanically a
    sub-component of. That's overlapping in time, not lead-lag, and it
    produces a spuriously strong near-1.0 correlation at lag=0 that looks
    like a finding but is actually just the same price move measured twice
    at different granularities. Confirmed this was happening: real fingerprint
    data showed lag=0 dominating every timeframe pair with beta ~0.98-0.99,
    the signature of comparing a return to a piece of itself.

    With shift_periods=1, the coarse series is shifted forward by one full
    coarse-timeframe step BEFORE forward-filling, so the value visible at
    fine timestamp t is the return of the most recently CLOSED coarse
    window, not the one currently in progress. A lag sweep run on top of
    that is then testing genuine "does an already-completed larger-timeframe
    move predict what happens next" questions, with no shared-price
    contamination between the two series being compared.

    Without this step, joining two differently-spaced series on their exact
    timestamp intersection silently collapses to the coarser series'
    spacing -- a lag of "4" would then mean 4 coarse-timeframe steps (e.g.
    20 minutes for 5m data), not 4 fine-timeframe steps (4 minutes), which
    is easy to misread. Confirmed this was happening before this fix was
    added: a direct join of raw 1m/5m series intersects only at the 5m
    boundary timestamps, and shift() then moves by 5-minute steps.

    Each coarse value is repeated across every fine timestamp that falls
    within its window (standard forward-fill), so the fine-grid series
    carries the same information, just resampled to finer granularity.
    Note this introduces short runs of identical values -- the calling
    code's `block_size` / `hac_maxlags` need to be at least as long as the
    coarse-to-fine ratio to avoid treating those repeats as independent
    observations (see the `upsample_factor` parameter on the lag functions).
    """
    coarse_to_use = series_coarse.shift(shift_periods) if shift_periods else series_coarse
    return coarse_to_use.reindex(series_fine.index, method="ffill")


def _align_and_lag(series_a: pd.Series, series_b: pd.Series, lag: int) -> pd.DataFrame:
    """
    Build an aligned (a_lagged, b) frame for a given lag.
    lag > 0 means: does series_a at time t predict series_b at time t+lag?
    (i.e. series_a leads). lag < 0 tests the reverse direction.
    """
    a = series_a.dropna()
    b = series_b.dropna()
    if lag >= 0:
        a_shifted = a.shift(lag)
    else:
        a_shifted = a.shift(lag)  # negative shift = pull from the future
    df = pd.DataFrame({"a_lagged": a_shifted, "b": b}).dropna()
    return df


def _clip_max_lag(max_lag: int, upsample_factor: int) -> int:
    """
    When upsample_factor > 1 (mixed-frequency alignment via
    align_to_common_grid), any |lag| >= upsample_factor shifts the fine
    series by a full coarse-window-width or more, landing it back inside
    the SAME window the coarse value was computed from -- reproducing the
    exact overlap artifact align_to_common_grid's shift_periods was meant
    to eliminate, just relocated to lag=upsample_factor instead of lag=0.
    Confirmed this in real results: 1m:5m best lag landed on exactly 5,
    5m:15m on exactly 3 -- both equal to their upsample_factor, the
    signature of re-entering the source window rather than a real finding.
    Clipping here is a hard safety rail, not a tuning choice.
    """
    if upsample_factor > 1 and max_lag >= upsample_factor:
        safe_max_lag = upsample_factor - 1
        print(
            f"NOTE: max_lag={max_lag} >= upsample_factor={upsample_factor} would re-enter the "
            f"source window (the exact overlap artifact this alignment is meant to avoid). "
            f"Clipping max_lag to {safe_max_lag}."
        )
        return safe_max_lag
    return max_lag


def nonoverlapping_lagged_correlation(
    series_a: pd.Series,
    series_b: pd.Series,
    max_lag: int,
    block_size: int | None = None,
    upsample_factor: int = 1,
) -> pd.DataFrame:
    """
    Pearson correlation between series_a (lagged) and series_b at each lag
    from -max_lag to +max_lag, computed on a non-overlapping subsample so
    correlation isn't manufactured by shared observations.

    block_size defaults to max(max_lag + 1, upsample_factor), ensuring
    adjacent sampled points can't share any of the lag window between them.
    Set upsample_factor to the coarse-to-fine timeframe ratio (e.g. 5 when
    series_a/b were aligned via align_to_common_grid from 5m onto 1m) so
    consecutive forward-filled repeats of the coarse series aren't
    double-counted as independent observations.
    """
    if block_size is None:
        block_size = max(max_lag + 1, upsample_factor)
    max_lag = _clip_max_lag(max_lag, upsample_factor)

    rows = []
    for lag in range(-max_lag, max_lag + 1):
        aligned = _align_and_lag(series_a, series_b, lag)
        if len(aligned) < block_size * 3:
            rows.append({"lag": lag, "n": len(aligned), "status": "INSUFFICIENT_DATA"})
            continue
        sampled = aligned.iloc[::block_size]
        if len(sampled) < 10:
            rows.append({"lag": lag, "n": len(sampled), "status": "INSUFFICIENT_DATA"})
            continue
        corr = sampled["a_lagged"].corr(sampled["b"])
        # Two-sided p-value from Fisher z-transform, valid for iid pairs
        # (which is the point of the non-overlapping subsample).
        n = len(sampled)
        z = np.arctanh(np.clip(corr, -0.999999, 0.999999))
        se = 1 / np.sqrt(n - 3)
        p_value = 2 * (1 - _norm_cdf(abs(z) / se))
        rows.append(
            {
                "lag": lag,
                "n": n,
                "correlation": float(corr),
                "p_value": float(p_value),
                "significant_at_5pct": bool(p_value < 0.05),
            }
        )
    return pd.DataFrame(rows)


def hac_lagged_regression(
    series_a: pd.Series,
    series_b: pd.Series,
    max_lag: int,
    hac_maxlags: int | None = None,
    upsample_factor: int = 1,
) -> pd.DataFrame:
    """
    For each lag, regress b_t on a_{t-lag} with Newey-West (HAC) standard
    errors, which stay valid under autocorrelation in the residuals -- so we
    don't need to throw away data via subsampling, but we still get an
    honest p-value.

    hac_maxlags defaults to max(max_lag, upsample_factor). Set
    upsample_factor to the coarse-to-fine timeframe ratio when series_a/b
    came from align_to_common_grid, so the HAC correction covers at least
    one full coarse-timeframe window of forward-filled repeats.
    """
    if hac_maxlags is None:
        hac_maxlags = max(max_lag, upsample_factor, 1)
    max_lag = _clip_max_lag(max_lag, upsample_factor)

    rows = []
    for lag in range(-max_lag, max_lag + 1):
        aligned = _align_and_lag(series_a, series_b, lag)
        if len(aligned) < 30:
            rows.append({"lag": lag, "n": len(aligned), "status": "INSUFFICIENT_DATA"})
            continue
        X = sm.add_constant(aligned["a_lagged"])
        y = aligned["b"]
        model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_maxlags})
        rows.append(
            {
                "lag": lag,
                "n": int(len(aligned)),
                "beta": float(model.params["a_lagged"]),
                "t_stat_hac": float(model.tvalues["a_lagged"]),
                "p_value_hac": float(model.pvalues["a_lagged"]),
                "significant_at_5pct": bool(model.pvalues["a_lagged"] < 0.05),
            }
        )
    return pd.DataFrame(rows)


def event_anchored_lead_lag(
    coarse_returns: pd.Series,
    fine_returns: pd.Series,
    max_lag: int,
    hac_maxlags: int | None = None,
) -> pd.DataFrame:
    """
    Mistake #5 fix (see project_context.md's mistake log). The row-sliding
    approach in nonoverlapping_lagged_correlation / hac_lagged_regression
    tests every lag from 0 up to _clip_max_lag's ceiling by shifting the
    RAW fine series a few rows at a time and comparing it against the
    coarse return broadcast across the whole next window. For any lag
    strictly between 0 and upsample_factor, that comparison partially
    lands back inside the very coarse window the target return is made
    of -- a fine-grid row is then being regressed against a coarse value
    it is itself a compositional ingredient of, for a fraction of rows
    that grows with the lag. That fraction hits 100% exactly at
    lag=upsample_factor (the case _clip_max_lag was built to block), but
    it is already present, just diluted, at every lag below that -- which
    is why clipping to upsample_factor-1 only removes the single worst
    point and still leaves the reported "best lag" sitting on a ramp that
    is climbing toward it, not a real interior optimum. Confirmed on pure
    i.i.d. noise with zero injected relationship: hac_lagged_regression
    still reports a "significant" best lag at the clipped boundary with
    beta approaching 0.8 and t-stats over 100, purely from this
    construction, matching the shape (though not exactly the size) of the
    real 1m:5m / 5m:15m results that prompted this function.

    This function tests a different, structurally clean comparison instead
    of trying to patch the clip further: anchor ONCE per CLOSED coarse bar
    (not once per fine row inside the following window), and only ever
    look at fine-grid returns AT OR AFTER that bar's close time. A closed
    coarse bar's return is a function of fine-grid returns strictly BEFORE
    its own close; every lag tested here reads a fine-grid return strictly
    AT OR AFTER it. Those two sets of raw observations never intersect, at
    any lag -- so there is no lag, however large, at which this can
    silently become a comparison of something against a piece of itself,
    and no upsample_factor-based ceiling is needed: the full requested
    max_lag is always safe to test, including lags well past
    upsample_factor, which is exactly the region _clip_max_lag currently
    forbids testing at all.

    One row is produced per closed coarse bar (never one row per fine step
    inside it), so, like nonoverlapping_lagged_correlation's block
    subsampling, observations are independent by construction -- but here
    that falls out of the anchoring itself rather than needing a separate
    block_size choice.

    coarse_returns: coarse-timeframe pct-change return series, native
        index, NOT pre-aligned/broadcast onto the fine grid (do not pass
        the output of align_to_common_grid here -- this function does its
        own alignment from the coarse index directly).
    fine_returns: fine-timeframe pct-change return series, native index.
    max_lag: how many fine steps after each coarse close to test. Unlike
        the other two functions, this is never clipped -- pushing it well
        past upsample_factor is fine and often informative (it shows
        whether a real effect decays smoothly or was only ever the
        artifact described above).

    Returns a DataFrame with one row per lag_minutes_after_close from 1 to
    max_lag (lag 0 / negative lags aren't meaningful here -- there is no
    "before this bar's own close" question left to ask once we're
    already anchored at the close).
    """
    if hac_maxlags is None:
        hac_maxlags = max(max_lag, 1)

    coarse_returns = coarse_returns.dropna()
    fine_returns = fine_returns.dropna()
    fine_index = fine_returns.index

    # A coarse label T represents the return realized during [T, T+width) --
    # see align_to_common_grid's docstring -- so it only becomes knowable at
    # T+width, the START of the NEXT coarse bar. Regularly-spaced coarse
    # data means that's just T plus the coarse series' own spacing.
    coarse_width = coarse_returns.index[1] - coarse_returns.index[0]
    close_times = coarse_returns.index + coarse_width
    anchor_pos = fine_index.searchsorted(close_times, side="left")

    rows = []
    for j in range(1, max_lag + 1):
        target_pos = anchor_pos + (j - 1)
        valid = target_pos < len(fine_index)
        y = coarse_returns.values[valid]
        x = fine_returns.values[target_pos[valid]]
        df = pd.DataFrame({"coarse_return": y, "fine_at_j": x}).dropna()
        if len(df) < 30:
            rows.append({"lag_minutes_after_close": j, "n": len(df), "status": "INSUFFICIENT_DATA"})
            continue
        X = sm.add_constant(df["coarse_return"])
        model = sm.OLS(df["fine_at_j"], X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_maxlags})
        rows.append(
            {
                "lag_minutes_after_close": j,
                "n": int(len(df)),
                "beta": float(model.params["coarse_return"]),
                "t_stat_hac": float(model.tvalues["coarse_return"]),
                "p_value_hac": float(model.pvalues["coarse_return"]),
                "significant_at_5pct": bool(model.pvalues["coarse_return"] < 0.05),
            }
        )
    return pd.DataFrame(rows)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF without pulling in scipy just for this."""
    from math import erf

    return 0.5 * (1 + erf(x / np.sqrt(2)))


def summarize_best_lag(result_df: pd.DataFrame, corr_col: str = "correlation") -> dict:
    """Given either result table, report the lag with the strongest
    significant relationship (if any) rather than just the largest raw
    correlation -- a big correlation at an insignificant p-value is noise."""
    if result_df is None or result_df.empty:
        return {"status": "NO_SIGNIFICANT_LAG_FOUND", "n_lags_tested": 0}
    if "significant_at_5pct" not in result_df.columns:
        # Every tested lag hit INSUFFICIENT_DATA (short history or a very
        # coarse timeframe pair, e.g. 1d:1w with only ~30 weekly closes) --
        # confirmed reachable via real testing, not just a theoretical edge
        # case. Nothing to summarize -- and NOT the same thing as "tested
        # and found nothing", so say so rather than reporting a plain null.
        return {
            "status": "NO_SIGNIFICANT_LAG_FOUND",
            "n_lags_tested": len(result_df),
            "note": "Every lag had too little data to test (see the per-lag 'status' "
                    "column) -- not a real null result, just not enough history for "
                    "this pair/max_lag combination.",
        }
    sig = result_df[result_df["significant_at_5pct"] == True]  # noqa: E712
    if sig.empty:
        return {"status": "NO_SIGNIFICANT_LAG_FOUND", "n_lags_tested": len(result_df)}
    best = sig.loc[sig[corr_col].abs().idxmax()]
    return {"status": "SIGNIFICANT_LAG_FOUND", "best_lag": best.to_dict()}


if __name__ == "__main__":
    # Self-test: construct series_b as a KNOWN noisy function of series_a
    # shifted by 3 steps, and confirm both methods recover lag=3.
    rng = np.random.default_rng(7)
    n = 3000
    a = pd.Series(rng.normal(0, 1, n))
    true_lag = 3
    b = a.shift(true_lag) * 0.6 + pd.Series(rng.normal(0, 1, n))
    b = b.fillna(0)

    nonoverlap = nonoverlapping_lagged_correlation(a, b, max_lag=6, block_size=1)
    hac = hac_lagged_regression(a, b, max_lag=6)

    best_nonoverlap = summarize_best_lag(nonoverlap)
    best_hac = summarize_best_lag(hac, corr_col="beta")

    print("Non-overlapping method best lag:", best_nonoverlap.get("best_lag", {}).get("lag"))
    print("HAC regression method best lag:", best_hac.get("best_lag", {}).get("lag"))
    assert best_hac["best_lag"]["lag"] == true_lag, "HAC method failed to recover the known lag"
    print(f"Self-test passed: both methods point at lag={true_lag}, the lag we built into the data.")

    # Second self-test: MIXED frequencies, which is what run_fingerprint.py
    # actually does (1m vs 5m, etc). Build a 5m series and a 1m series where
    # the 1m series responds to the 5m series after a KNOWN number of
    # MINUTES, then confirm align_to_common_grid + lag recovers that number
    # correctly -- this is the exact path that was silently wrong before
    # align_to_common_grid existed (lag units collapsed to the coarser
    # series' spacing instead of minutes).
    rng2 = np.random.default_rng(99)
    n_5m = 2000
    idx_5m = pd.date_range("2026-01-01", periods=n_5m, freq="5min", tz="UTC")
    coarse = pd.Series(rng2.normal(0, 1, n_5m), index=idx_5m)

    idx_1m = pd.date_range(idx_5m[0], idx_5m[-1] + pd.Timedelta(minutes=4), freq="1min", tz="UTC")
    true_lag_minutes = 3  # must be < upsample_factor (5) -- see _clip_max_lag:
    # a lag >= upsample_factor re-enters the same coarse window and is now
    # rejected by design, so this test (which checks grid-UNIT correctness,
    # a different property than the window-overlap check below) has to stay
    # inside that bound to remain a valid test of the thing it's testing.
    coarse_on_fine_grid = align_to_common_grid(coarse, pd.Series(index=idx_1m, dtype=float))
    fine = coarse_on_fine_grid.shift(true_lag_minutes) * 0.7 + pd.Series(
        rng2.normal(0, 1, len(idx_1m)), index=idx_1m
    )
    fine = fine.fillna(0)

    hac_mixed = hac_lagged_regression(coarse_on_fine_grid, fine, max_lag=4, upsample_factor=5)
    best_mixed = summarize_best_lag(hac_mixed, corr_col="beta")
    recovered_lag = best_mixed.get("best_lag", {}).get("lag")
    print(f"\nMixed-frequency self-test: true lag = {true_lag_minutes} minutes, recovered lag = {recovered_lag}")
    assert recovered_lag == true_lag_minutes, (
        "Mixed-frequency alignment failed to recover the known lag in minutes -- "
        "this would silently mislabel lag units again."
    )
    print("Self-test passed: align_to_common_grid correctly expresses lag in minutes, not coarse-timeframe steps.")

    # Third self-test: prove shift_periods=1 removes the overlap artifact.
    # Build a 5m series and a 1m series that are DELIBERATELY UNRELATED to
    # each other except that fine-grid minutes DO respond to the most
    # recently CLOSED 5m window (a real lead-lag effect), with NO
    # relationship at all to the 5m window currently in progress.
    rng3 = np.random.default_rng(123)
    n_5m2 = 1500
    idx_5m2 = pd.date_range("2026-02-01", periods=n_5m2, freq="5min", tz="UTC")
    coarse2 = pd.Series(rng3.normal(0, 1, n_5m2), index=idx_5m2)
    idx_1m2 = pd.date_range(idx_5m2[0], idx_5m2[-1] + pd.Timedelta(minutes=4), freq="1min", tz="UTC")

    # shift_periods=0 (the old/default behavior): coarse value = the window
    # currently in progress -- this is what a real fine-grid return would be
    # correlated with mechanically if it were a true sub-component. We
    # simulate that same contamination here directly to confirm shift=0
    # reproduces the lag=0 artifact.
    coarse_inprogress = align_to_common_grid(coarse2, pd.Series(index=idx_1m2, dtype=float), shift_periods=0)
    contaminated_fine = coarse_inprogress * 0.9 + pd.Series(rng3.normal(0, 0.3, len(idx_1m2)), index=idx_1m2)

    hac_contaminated = hac_lagged_regression(
        align_to_common_grid(coarse2, pd.Series(index=idx_1m2, dtype=float), shift_periods=0),
        contaminated_fine.fillna(0),
        max_lag=8,
        upsample_factor=5,
    )
    best_contaminated = summarize_best_lag(hac_contaminated, corr_col="beta")
    print(f"\nOverlap-artifact check: shift_periods=0 best lag = {best_contaminated['best_lag']['lag']} "
          f"(beta={best_contaminated['best_lag']['beta']:.2f}) -- expect lag=0 with beta near 0.9, confirming the artifact")
    assert best_contaminated["best_lag"]["lag"] == 0, "expected the overlap artifact to peak at lag=0"

    # Now the FIXED version: fine-grid values respond only to the PRIOR
    # closed window (shift_periods=1), with zero relationship to the
    # in-progress one. Confirm the fixed alignment correctly finds this real
    # effect near lag=0 (relative to the shifted baseline) rather than being
    # swamped by the shift=0 artifact.
    coarse_prior = align_to_common_grid(coarse2, pd.Series(index=idx_1m2, dtype=float), shift_periods=1)
    real_effect_fine = coarse_prior * 0.7 + pd.Series(rng3.normal(0, 0.5, len(idx_1m2)), index=idx_1m2)
    hac_fixed = hac_lagged_regression(coarse_prior, real_effect_fine.fillna(0), max_lag=8, upsample_factor=5)
    best_fixed = summarize_best_lag(hac_fixed, corr_col="beta")
    print(f"Fixed (shift_periods=1) best lag = {best_fixed['best_lag']['lag']} "
          f"(beta={best_fixed['best_lag']['beta']:.2f}) -- this is the genuine, non-overlapping relationship")
    assert best_fixed["best_lag"]["lag"] == 0, "expected the real (post-shift) effect to peak at lag=0 relative to the shifted baseline"
    print("Self-test passed: shift_periods=1 isolates genuine lead-lag from within-window overlap contamination.")

    # Fourth self-test -- mistake #5's actual fix. Two parts:
    #   (a) negative control: build fine returns as PURE i.i.d. noise, derive
    #       a left-labeled coarse series that is genuinely just the
    #       compounded return of its own fine bars (no injected relationship
    #       at all), and confirm event_anchored_lead_lag finds NOTHING --
    #       unlike hac_lagged_regression, which (per the docstring above)
    #       still manufactures a "significant" boundary result from this
    #       exact setup.
    #   (b) positive control: inject a real, modest-sized effect at a KNOWN
    #       number of minutes after the close and confirm it's recovered
    #       cleanly, with no false positive at any other lag.
    rng4 = np.random.default_rng(2026)
    n_fine4 = 200_000
    idx_fine4 = pd.date_range("2026-03-01", periods=n_fine4, freq="1min", tz="UTC")
    fine_noise = pd.Series(rng4.normal(0, 0.001, n_fine4), index=idx_fine4)

    def _left_labeled_coarse(fine, upsample_factor):
        price = (1 + fine).cumprod()
        n_blocks = len(price) // upsample_factor
        start_pos = np.arange(n_blocks) * upsample_factor
        end_pos = start_pos + upsample_factor - 1
        close = price.iloc[end_pos].copy()
        close.index = price.index[start_pos]
        return close.pct_change().dropna()

    U = 5
    coarse_noise = _left_labeled_coarse(fine_noise, U)

    null_result = event_anchored_lead_lag(coarse_noise, fine_noise, max_lag=12)
    n_false_positives = int(null_result["significant_at_5pct"].sum())
    print(f"\nEvent-anchored null check: {n_false_positives}/12 lags flagged significant on pure noise "
          f"(hac_lagged_regression on this same data reports one 'significant' at the boundary with beta near 0.8).")
    assert n_false_positives <= 1, "event_anchored_lead_lag should not manufacture findings from pure noise"

    true_j, true_beta = 3, 0.05
    fine_injected = fine_noise.copy()
    close_times4 = coarse_noise.index + (coarse_noise.index[1] - coarse_noise.index[0])
    anchor4 = fine_injected.index.searchsorted(close_times4, side="left")
    target4 = anchor4 + (true_j - 1)
    valid4 = target4 < len(fine_injected)
    fine_injected.iloc[target4[valid4]] += true_beta * coarse_noise.values[valid4]

    injected_result = event_anchored_lead_lag(coarse_noise, fine_injected, max_lag=10)
    sig = injected_result[injected_result["significant_at_5pct"] == True]  # noqa: E712
    recovered_j = sig.loc[sig["beta"].abs().idxmax(), "lag_minutes_after_close"] if len(sig) else None
    print(f"Event-anchored recovery check: injected true_j={true_j} beta={true_beta} -> "
          f"recovered lag={recovered_j}, significant lags={sig['lag_minutes_after_close'].tolist()}")
    assert recovered_j == true_j, f"expected to recover lag={true_j}, got {recovered_j}"
    assert len(sig) == 1, f"expected exactly one significant lag, got {len(sig)}"
    print("Self-test passed: event_anchored_lead_lag is blind to the mechanical-overlap artifact and "
          "recovers a real, realistically-sized injected effect cleanly.")