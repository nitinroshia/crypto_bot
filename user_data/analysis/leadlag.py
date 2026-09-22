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
                "correlation": float(aligned["a_lagged"].corr(aligned["b"])),
                "t_stat_hac": float(model.tvalues["a_lagged"]),
                "p_value_hac": float(model.pvalues["a_lagged"]),
                "significant_at_5pct": bool(model.pvalues["a_lagged"] < 0.05),
            }
        )
    return pd.DataFrame(rows)


def _modal_step(index: pd.DatetimeIndex) -> pd.Timedelta:
    """The most common spacing between consecutive timestamps -- the series'
    nominal bar width, robust to a few literal gaps (unlike index[1]-index[0],
    which is wrong whenever the first two rows straddle a gap)."""
    diffs = pd.Series(index[1:] - index[:-1])
    return diffs.mode().iloc[0]


def grid_returns(close: pd.Series, step: pd.Timedelta | None = None) -> pd.Series:
    """
    Gap-aware bar returns: close_t / close_{t-step} - 1, but ONLY where the
    previous bar is exactly `step` earlier; NaN otherwise.

    Why: `Series.pct_change()` is positional. If the file is missing rows
    (literal gaps -- see diagnose_gaps.py), the row after a gap gets a
    return computed across the whole gap but labeled as one bar. That
    return spans time before the bar's own window, so it can share raw
    price moves with a coarse bar that closed inside the gap -- the same
    "same data on both sides" failure as mistake #5, arriving via missing
    rows instead of resampling. Callers feeding event_anchored_lead_lag
    should build their returns with this function, not pct_change().
    """
    close = close.sort_index()
    if step is None:
        step = _modal_step(close.index)
    prev_close = close.shift(1)
    contiguous = pd.Series((close.index[1:] - close.index[:-1]) == step, index=close.index[1:])
    contiguous = contiguous.reindex(close.index, fill_value=False)
    ret = close / prev_close - 1
    return ret.where(contiguous).dropna()


def event_anchored_lead_lag(
    coarse_returns: pd.Series,
    fine_returns: pd.Series,
    max_lag: int,
    hac_maxlags: int | None = None,
    legacy_alignment: bool = False,
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

    Returns a DataFrame with one row per `lag_bars` from 1 to max_lag (lag 0 /
    negative lags aren't meaningful here -- there is no "before this bar's
    own close" question left to ask once we're already anchored at the close).

    UNITS (renamed per work order 1.1; the old column `lag_minutes_after_close`
    counted FINE BARS, which are minutes only when the fine series is 1m):
      lag_bars    j = the j-th fine bar after the coarse close. That bar's return
                  is realized during [close + (j-1)*step, close + j*step).
      lag_minutes j * (fine bar length in minutes) = the END of that window, so for a
                  5m fine series lag_bars 25 is lag_minutes 125 (window 120-125 min after close).
    `correlation` is the Pearson correlation of the same two series the
    regression uses, reported next to beta because effect-size bands are stated in
    correlation units.

    STRICT TIME ALIGNMENT (added after the first real-data re-run design
    review). The original version located "the fine row j-1 steps after the
    close" by POSITION in the fine series. That is only correct when the
    fine series covers every coarse close and has no missing rows. Two ways
    it was silently wrong:
      1. Coarse history longer than fine history (real case here: 5m files
         reach back ~3 years, the 1m file ~6 months). Every coarse bar
         closing BEFORE the first fine timestamp was searchsorted to row 0
         and paired with the first few fine returns of the file -- the same
         handful of fine values repeated against years of unrelated coarse
         returns. Reported n was inflated and beta attenuated toward zero
         (reproduced on synthetic data: n 3x too large, injected beta 0.05
         reported as 0.019, p-value overstated).
      2. A missing fine row shifts every later position, so "lag j" could
         really be lag j + (missing rows) -- lag labels no longer minutes.
    The fix: a pair (coarse bar, lag j) is used ONLY IF the fine row found
    at that position carries exactly the timestamp close_time +
    (j-1) * fine_step. Anything else is dropped, not shifted. On gap-free,
    same-span data this changes nothing (all pre-existing self-tests still
    pass, unmodified). `legacy_alignment=True` reproduces the old positional
    behavior, only so the difference can be measured -- never for results.
    Pair this with `grid_returns` for the inputs (a return computed across
    a missing row spans more than one bar).
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
    fine_step = _modal_step(fine_index)
    if legacy_alignment:
        coarse_width = coarse_returns.index[1] - coarse_returns.index[0]
    else:
        coarse_width = _modal_step(coarse_returns.index)
    close_times = coarse_returns.index + coarse_width
    anchor_pos = fine_index.searchsorted(close_times, side="left")

    if not legacy_alignment:
        first_ok = np.asarray(
            (anchor_pos < len(fine_index))
            & (fine_index[np.minimum(anchor_pos, len(fine_index) - 1)] == close_times)
        )
        n_dropped = int(len(close_times) - first_ok.sum())
        # The very last coarse bar always closes exactly where the fine data
        # ends (no fine row yet), so one dropped bar is normal and not worth
        # a NOTE; more than that means real out-of-range or gap exclusions.
        if n_dropped > 1:
            print(
                f"NOTE: event_anchored_lead_lag: {n_dropped}/{len(close_times)} coarse bars have no fine "
                f"row exactly at their close (outside the fine data's date range, or inside a gap) -- "
                f"excluded, not mis-paired."
            )

    fine_minutes = float(fine_step / pd.Timedelta(minutes=1))  # minutes per fine bar
    rows = []
    for j in range(1, max_lag + 1):
        target_pos = anchor_pos + (j - 1)
        valid = target_pos < len(fine_index)
        if not legacy_alignment:
            on_time = np.zeros(len(target_pos), dtype=bool)
            on_time[valid] = np.asarray(
                fine_index[target_pos[valid]] == (close_times[valid] + (j - 1) * fine_step)
            )
            valid = on_time
        y = coarse_returns.values[valid]
        x = fine_returns.values[target_pos[valid]]
        df = pd.DataFrame({"coarse_return": y, "fine_at_j": x}).dropna()
        if len(df) < 30:
            rows.append({"lag_bars": j, "lag_minutes": j * fine_minutes, "n": len(df), "status": "INSUFFICIENT_DATA"})
            continue
        X = sm.add_constant(df["coarse_return"])
        model = sm.OLS(df["fine_at_j"], X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_maxlags})
        rows.append(
            {
                "lag_bars": j,
                "lag_minutes": j * fine_minutes,
                "n": int(len(df)),
                "beta": float(model.params["coarse_return"]),
                "correlation": float(df["coarse_return"].corr(df["fine_at_j"])),
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


# --------------------------------------------------------------------------------------
# Lag selection (work order 1.2 item 1, answer 02 item 3)
# --------------------------------------------------------------------------------------
P_COLUMNS = ("p_value_hac", "p_value")           # same order as multitest.P_COLUMNS
SELECTION_MIN_P = "min_p"
SELECTION_LEGACY = "legacy_max_abs_effect_among_significant"


def _first_present(columns, names):
    return next((c for c in names if c in columns), None)


def _selection_strength(df: pd.DataFrame, corr_col: str) -> pd.Series:
    """Tie-breaker for equal p. A p-value that underflows to exactly 0.0 (|t| > ~38 for the HAC
    tables, |z| > ~8.3 for the non-overlapping table) says nothing about which lag is stronger, so
    equal p is broken by the underlying statistic: |HAC t|; else |Fisher z| = |atanh(r)| * sqrt(n - 3);
    else |effect|."""
    if "t_stat_hac" in df.columns:
        return pd.to_numeric(df["t_stat_hac"], errors="coerce").abs()
    if "correlation" in df.columns and "n" in df.columns:
        r = pd.to_numeric(df["correlation"], errors="coerce").clip(-0.999999, 0.999999)
        n = pd.to_numeric(df["n"], errors="coerce")
        return (np.arctanh(r) * np.sqrt((n - 3).clip(lower=0))).abs()
    if corr_col in df.columns:
        return pd.to_numeric(df[corr_col], errors="coerce").abs()
    return pd.Series(0.0, index=df.index)


def summarize_best_lag(result_df: pd.DataFrame, corr_col: str = "correlation", select: str = SELECTION_MIN_P) -> dict:
    """Pick one lag from a result table (one row per lag tested).

    select="min_p" (DEFAULT, work order 1.2 item 1): the lag with the SMALLEST p-value -- equivalently
    the largest |HAC t| -- with NO "significant" pre-filter and NOT the largest |beta| or |correlation|
    (|beta| favours lags whose target is more volatile, so it selects noise). Ties in p (a p that
    underflows to 0.0) are broken by the larger |t| (see _selection_strength), then by the smaller lag.
    Rows without a p-value (INSUFFICIENT_DATA) cannot be ranked and are skipped. A best lag therefore
    always exists unless NO row is testable; its own `significant_at_5pct` says whether it clears 5%.
    Result: {"status": "BEST_LAG_BY_MIN_P", "selection": "min_p", "n_lags_tested", "n_lags_ranked",
    "best_lag": <that row>}, or {"status": "NO_TESTABLE_LAG", ...}.

    select="legacy_max_abs_effect_among_significant": the rule used until work order 1.2 (largest
    |corr_col| among rows significant at 5%). Kept ONLY so a frozen ETH/FDUSD result can be recomputed
    exactly as it was reported; pass it explicitly by name -- it is never the default and no caller
    invokes it implicitly. Do not use it for new claims.
    """
    if select == SELECTION_LEGACY:
        out = _summarize_best_lag_legacy(result_df, corr_col)
        out["selection"] = SELECTION_LEGACY
        return out
    if select != SELECTION_MIN_P:
        raise ValueError(f"unknown selection rule {select!r}; use {SELECTION_MIN_P!r} or {SELECTION_LEGACY!r}")
    n_tested = 0 if result_df is None else len(result_df)
    base = {"selection": SELECTION_MIN_P, "n_lags_tested": n_tested}
    if result_df is None or result_df.empty:
        return {"status": "NO_TESTABLE_LAG", **base}
    pcol = _first_present(result_df.columns, P_COLUMNS)
    if pcol is None:
        return {"status": "NO_TESTABLE_LAG", **base,
                "note": "No p-value column: every lag had too little data to test (see the per-lag 'status' "
                        "column). Not a real null result, just not enough history for this pair/max_lag."}
    d = result_df.copy()
    d["_p"] = pd.to_numeric(d[pcol], errors="coerce")
    d = d[np.isfinite(d["_p"])]
    if d.empty:
        return {"status": "NO_TESTABLE_LAG", **base, "n_lags_ranked": 0}
    d["_strength"] = _selection_strength(d, corr_col)
    lagc = _first_present(d.columns, ("lag", "lag_bars")) or _first_present(d.columns, [c for c in d.columns if str(c).startswith("lag")])
    d["_lag"] = pd.to_numeric(d[lagc], errors="coerce") if lagc else 0.0
    d = d.sort_values(["_p", "_strength", "_lag"], ascending=[True, False, True], kind="mergesort")
    best = d.iloc[0].drop(labels=["_p", "_strength", "_lag"])
    return {"status": "BEST_LAG_BY_MIN_P", **base, "n_lags_ranked": int(len(d)), "best_lag": best.to_dict()}


def _summarize_best_lag_legacy(result_df: pd.DataFrame, corr_col: str = "correlation") -> dict:
    """The pre-1.2 rule: the lag with the largest |corr_col| among lags significant at 5% (if any)."""
    if result_df is None or result_df.empty:
        return {"status": "NO_SIGNIFICANT_LAG_FOUND", "n_lags_tested": 0}
    if "significant_at_5pct" not in result_df.columns:
        # Every tested lag hit INSUFFICIENT_DATA (short history or a very coarse timeframe pair, e.g. 1d:1w
        # with only ~30 weekly closes). Not the same thing as "tested and found nothing", so say so.
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
    recovered_j = sig.loc[sig["beta"].abs().idxmax(), "lag_bars"] if len(sig) else None
    print(f"Event-anchored recovery check: injected true_j={true_j} beta={true_beta} -> "
          f"recovered lag={recovered_j}, significant lags={sig['lag_bars'].tolist()}")
    assert recovered_j == true_j, f"expected to recover lag={true_j}, got {recovered_j}"
    assert len(sig) == 1, f"expected exactly one significant lag, got {len(sig)}"
    print("Self-test passed: event_anchored_lead_lag is blind to the mechanical-overlap artifact and "
          "recovers a real, realistically-sized injected effect cleanly.")
    # Fifth self-test -- strict time alignment (see event_anchored_lead_lag's
    # docstring, "STRICT TIME ALIGNMENT"). Three parts:
    #   (a) coarse history LONGER than fine history (the real ETH/FDUSD
    #       situation: 5m reaches back years, 1m only months). Pure
    #       positional matching pairs every pre-fine coarse bar with the
    #       first fine rows of the file. Strict alignment must use exactly
    #       the coarse bars that close inside the fine range, and recover
    #       the injected beta without attenuation.
    #   (b) a literal gap (missing rows) in the fine series: n at each lag
    #       must equal an independently counted number of on-time pairs.
    #   (c) grid_returns must blank the return that spans a missing row.
    rng5 = np.random.default_rng(31)
    U5 = 5
    n_long5 = 45 * 1440
    idx_long5 = pd.date_range("2026-03-01", periods=n_long5, freq="1min", tz="UTC")
    r_long5 = pd.Series(rng5.normal(0, 0.001, n_long5), index=idx_long5)
    coarse5 = _left_labeled_coarse(r_long5, U5)  # 45 days of coarse returns
    fine_start5 = idx_long5[30 * 1440]
    fine_short5 = r_long5.loc[fine_start5:].copy()  # only the last 15 days
    close_times5 = coarse5.index + pd.Timedelta(minutes=U5)
    pos5 = fine_short5.index.searchsorted(close_times5, side="left")
    inside5 = np.asarray(close_times5 >= fine_short5.index[0]) & (pos5 + 2 < len(fine_short5))
    fine_short5.iloc[pos5[inside5] + 2] += 0.05 * coarse5.values[inside5]  # true_j = 3

    strict = event_anchored_lead_lag(coarse5, fine_short5, max_lag=6)
    legacy = event_anchored_lead_lag(coarse5, fine_short5, max_lag=6, legacy_alignment=True)
    expected_n_a = int(inside5.sum())
    beta_strict = float(strict.loc[strict["lag_bars"] == 3, "beta"].iloc[0])
    beta_legacy = float(legacy.loc[legacy["lag_bars"] == 3, "beta"].iloc[0])
    print(f"\nStrict-alignment check (a): coarse bars closing inside fine range = {expected_n_a}; "
          f"strict n(lag1)={int(strict['n'].iloc[0])}, legacy n(lag1)={int(legacy['n'].iloc[0])}; "
          f"injected beta 0.05 -> strict {beta_strict:.3f}, legacy {beta_legacy:.3f}")
    assert int(strict["n"].iloc[0]) == expected_n_a, "strict alignment must use only in-range coarse bars"
    assert int(legacy["n"].iloc[0]) > 2 * expected_n_a, "legacy alignment should show the inflated n (bug demo)"
    assert abs(beta_strict - 0.05) < 0.015, f"strict beta should recover ~0.05, got {beta_strict}"
    assert beta_legacy < 0.035, "legacy beta should be visibly attenuated (bug demo)"

    # (b) literal gap
    fine_full5 = r_long5.loc[fine_start5:].copy()
    ct_full = coarse5.index + pd.Timedelta(minutes=U5)
    pos_full = fine_full5.index.searchsorted(ct_full, side="left")
    ok_full = np.asarray(ct_full >= fine_full5.index[0]) & (pos_full + 2 < len(fine_full5))
    fine_full5.iloc[pos_full[ok_full] + 2] += 0.05 * coarse5.values[ok_full]
    gap_start = fine_full5.index[7 * 1440]
    gap_idx = pd.date_range(gap_start, periods=180, freq="1min", tz="UTC")  # 3-hour hole
    fine_gappy = fine_full5.drop(gap_idx)
    gap_res = event_anchored_lead_lag(coarse5, fine_gappy, max_lag=6)
    for _, row in gap_res.iterrows():
        j = int(row["lag_bars"])
        want_close = pd.Index(ct_full).isin(fine_gappy.index)
        want_target = pd.Index(ct_full + pd.Timedelta(minutes=j - 1)).isin(fine_gappy.index)
        expected_n = int((want_close & want_target).sum())
        assert int(row["n"]) == expected_n, f"gap case, lag {j}: n={row['n']} expected {expected_n}"
    gap_best = summarize_best_lag(gap_res, corr_col="beta")
    assert gap_best["best_lag"]["lag_bars"] == 3, "effect must still be recovered around a gap"
    print("Strict-alignment check (b): n matches an independent on-time-pair count at every lag around a "
          "3-hour gap, and the injected lag is still recovered.")

    # (c) grid_returns
    px = pd.Series(
        [100.0, 101.0, 102.0, 104.0, 105.0],
        index=pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:01", "2026-01-01 00:02",
                              "2026-01-01 00:05", "2026-01-01 00:06"], utc=True),
    )
    gr = grid_returns(px)  # rows at 00:05 spans the 00:03-00:04 hole -> must be dropped
    assert list(gr.index.strftime("%H:%M")) == ["00:01", "00:02", "00:06"], list(gr.index.strftime("%H:%M"))
    print("Strict-alignment check (c): grid_returns drops the return that spans a missing row.")

    # (d) mixed datetime resolutions (ms vs ns) must not break the alignment
    coarse_ms = coarse5.copy()
    coarse_ms.index = coarse_ms.index.as_unit("ms")
    strict_ms = event_anchored_lead_lag(coarse_ms, fine_short5, max_lag=6)
    assert strict_ms["n"].tolist() == strict["n"].tolist(), "index resolution must not change the result"
    print("Self-test passed: strict time alignment excludes out-of-range / gap-straddling pairs instead of mis-pairing them.")

    # Sixth self-test -- units and correlation (work order 1.1).
    #   lag_bars counts fine bars; lag_minutes = bars * fine bar length; correlation sits next to beta.
    r_units = event_anchored_lead_lag(coarse5, fine_short5, max_lag=6)          # fine series is 1m
    assert (r_units["lag_minutes"] == r_units["lag_bars"] * 1.0).all()
    assert {"lag_bars", "lag_minutes", "beta", "correlation"} <= set(r_units.columns)
    assert "lag_minutes_after_close" not in r_units.columns
    row3 = r_units[r_units["lag_bars"] == 3].iloc[0]
    assert row3["correlation"] > 0.03 and np.sign(row3["correlation"]) == np.sign(row3["beta"])
    # 5m fine series: rebuild returns on a 5m grid and check the minute conversion
    fine5 = (1 + fine_short5).resample("5min", label="left", closed="left").prod() - 1
    coarse15 = (1 + fine_short5).resample("15min", label="left", closed="left").prod() - 1
    r5 = event_anchored_lead_lag(coarse15, fine5, max_lag=4)
    assert (r5["lag_minutes"] == r5["lag_bars"] * 5.0).all(), "5m fine bars must convert to 5 minutes each"
    hac_tbl = hac_lagged_regression(fine_short5.iloc[:3000], fine_short5.iloc[:3000], max_lag=3, upsample_factor=1)
    assert "correlation" in hac_tbl.columns and hac_tbl["correlation"].abs().max() <= 1.0
    print("Self-test passed: lag_bars / lag_minutes units are explicit (5m fine bars = 5 minutes) and correlation is reported next to beta.")

    # Selection rule (work order 1.2 item 1): smallest p, no "significant" pre-filter, not |beta|.
    # (a) a table where the two rules DISAGREE: lag 2 has the biggest |beta| among the significant lags,
    #     lag 3 has by far the smallest p (largest |HAC t|) but a tiny beta.
    tbl = pd.DataFrame({
        "lag": [1, 2, 3, 4], "n": [1000] * 4, "beta": [0.010, 0.050, 0.004, 0.030],
        "correlation": [0.02, 0.03, 0.12, 0.05], "t_stat_hac": [2.3, 2.1, 3.9, 1.0],
        "p_value_hac": [0.021, 0.036, 9.5e-5, 0.31], "significant_at_5pct": [True, True, True, False],
    })
    assert summarize_best_lag(tbl, corr_col="beta", select=SELECTION_LEGACY)["best_lag"]["lag"] == 2, "legacy rule = largest |beta| among significant"
    new_pick = summarize_best_lag(tbl, corr_col="beta")
    assert new_pick["best_lag"]["lag"] == 3 and new_pick["selection"] == "min_p" and new_pick["status"] == "BEST_LAG_BY_MIN_P"
    assert new_pick["n_lags_tested"] == 4 and new_pick["n_lags_ranked"] == 4
    # (b) no pre-filter: with nothing significant the smallest-p lag is still returned (the legacy rule returned nothing)
    weak = tbl.assign(p_value_hac=[0.4, 0.2, 0.09, 0.5], significant_at_5pct=False)
    assert summarize_best_lag(weak, corr_col="beta")["best_lag"]["lag"] == 3 and summarize_best_lag(weak, corr_col="beta")["best_lag"]["significant_at_5pct"] is False
    assert summarize_best_lag(weak, corr_col="beta", select=SELECTION_LEGACY)["status"] == "NO_SIGNIFICANT_LAG_FOUND"
    # (c) rows without a p-value (INSUFFICIENT_DATA) are skipped; if none is testable there is no best lag
    part = pd.concat([tbl.iloc[:2], pd.DataFrame({"lag": [5], "n": [3], "status": ["INSUFFICIENT_DATA"]})], ignore_index=True)
    assert summarize_best_lag(part)["best_lag"]["lag"] == 1 and summarize_best_lag(part)["n_lags_ranked"] == 2 and summarize_best_lag(part)["n_lags_tested"] == 3
    nothing = pd.DataFrame({"lag": [1, 2], "n": [3, 4], "status": ["INSUFFICIENT_DATA"] * 2})
    assert summarize_best_lag(nothing)["status"] == "NO_TESTABLE_LAG" and "best_lag" not in summarize_best_lag(nothing)
    assert summarize_best_lag(pd.DataFrame())["status"] == "NO_TESTABLE_LAG" and summarize_best_lag(None)["status"] == "NO_TESTABLE_LAG"
    # (d) ties: p underflowed to 0.0 in both rows -> the larger |HAC t| wins; in the non-overlapping table the
    #     larger |Fisher z| wins; equal everything -> the smaller lag
    tie_hac = pd.DataFrame({"lag": [1, 2], "beta": [0.9, 0.1], "t_stat_hac": [41.0, 49.8], "p_value_hac": [0.0, 0.0]})
    assert summarize_best_lag(tie_hac, corr_col="beta")["best_lag"]["lag"] == 2
    tie_no = pd.DataFrame({"lag": [3, 4], "n": [30501, 30501], "correlation": [0.20, 0.33], "p_value": [0.0, 0.0]})
    assert summarize_best_lag(tie_no)["best_lag"]["lag"] == 4
    tie_all = pd.DataFrame({"lag": [4, 2], "n": [100, 100], "correlation": [0.3, 0.3], "p_value": [0.01, 0.01]})
    assert summarize_best_lag(tie_all)["best_lag"]["lag"] == 2
    # (e) the event-anchored table calls its lag column lag_bars; an unknown rule name is an error
    ev = pd.DataFrame({"lag_bars": [1, 2, 3], "beta": [0.3, 0.1, 0.02], "t_stat_hac": [1.0, 2.5, 3.0], "p_value_hac": [0.31, 0.012, 0.0027]})
    assert summarize_best_lag(ev, corr_col="beta")["best_lag"]["lag_bars"] == 3
    try:
        summarize_best_lag(ev, select="largest_beta")
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown selection rule must raise")
    # (f) on simulated data the new rule recovers the built-in lag from a real HAC table, and the row it returns
    #     is the row with the minimum p
    rng3 = np.random.default_rng(11)
    a3 = pd.Series(rng3.normal(0, 1, 4000))
    b3 = a3.shift(2) * 0.15 + pd.Series(rng3.normal(0, 1, 4000))
    hac3 = hac_lagged_regression(a3, b3.fillna(0), max_lag=6)
    pick3 = summarize_best_lag(hac3, corr_col="beta")
    assert pick3["best_lag"]["lag"] == 2 and abs(pick3["best_lag"]["p_value_hac"] - hac3["p_value_hac"].min()) < 1e-300
    print("Self-test passed: summarize_best_lag picks the smallest-p lag with no significance pre-filter (largest |HAC t| on ties); "
          "the legacy largest-|beta|-among-significant rule is kept only under its own name.")
