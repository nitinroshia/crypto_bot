"""
S1 trend_slope (mathematician NOTES.md section 7, family 10) -- the FIRST
real candidate to run through item 2's machinery end to end. This module
supplies the S1-specific functions every item-2 module needs as a generic
hook (an `estimator`, a `count_origins`, a `signal_fn`/rule, a
`block_test`); item 2's own modules (cutoff.py, nonstationarity.py,
stability_check.py, economic_gate.py, rule_evaluator.py, holdout_lock.py,
freeze_manifest.py, forward_test.py) supply everything else and are used
UNCHANGED here -- this module has no pipeline logic of its own.

SPEC, VERBATIM (section 7):
"S1 trend_slope (1d; family 10)
- Predictor at the close of day t: x = ln(C_t / C_{t-L}) / sigma30, sigma30
  = std of the last 30 daily log returns ending at t; L in {10,20,40,80,160}.
- Target: ln(C_{t+h} / C_t), h in {1, 5}; entry is the open of day t+1 (a
  close-of-day-t predictor never trades at t's own close); all daily
  origins; Newey-West HAC (5 lags for h=1, 10 for h=5). Direction positive.
- Primary: L=40, h=5. The other nine cells are exploratory; Holm within the
  10. Pre-registered rule for the economic gate: long from the next open if
  x > 0 at the day's close, otherwise cash.
- Gut-check: x uses closes <= t, y uses closes > t; overlap in x is handled
  by HAC."

10 CELLS = 5 lookbacks (L) x 2 horizons (h). PRIMARY = (L=40, h=5) --
everything from the stability check onward (item 2's own machinery) runs
ONLY on the primary cell; the other 9 are discovery-only and exploratory.
"Holm within the 10" is an OWN-FAMILY Holm computed HERE, locally, via
`multitest.annotate_family` on the 10 cells' own p-values -- a different
axis from `registry.holm_at_step`'s ACROSS-CANDIDATE Holm (e.g. S1-ETHUSDT
vs S1-BTCUSDT vs S2-ETHUSDT all reaching "stability" together), which is
registry.py's job, not this module's.

WARMUP / TAIL, HANDLED BY NaN, NEVER BY SHIFTING THE INDEX: `predictor`
needs `max(L, SIGMA_WINDOW)` days of history before day t -- NOT `L +
SIGMA_WINDOW` (an easy off-by-a-lot mistake, caught in this module's own
self-test): the L-day lookback and the 30-day vol window both start
counting from day t independently, they don't stack. Concretely, `x_L`'s
first valid value sits at index position `max(L, SIGMA_WINDOW)` (0-indexed)
-- for the primary cell (L=40 > 30) this is just 40 days; for a shorter
lookback like L=10 it's 30 days (sigma30's own requirement dominates, not
the shorter L). `predictor`'s first `max(L, SIGMA_WINDOW)` values are NaN
accordingly. `target` needs h days of FUTURE history after day t -- its
last h values are NaN. Both stay on the full date index (never
dropped/reindexed) so callers slicing by date -- item 2's `cutoff.py`
truncation, `blocks.tile_blocks` tiling -- never see a silently shortened
series; `count_origins` and the regression itself drop NaN rows
internally, only at the point of computing a result.

WHY primary_estimator AND primary_block_test ARE FACTORIES, NOT PLAIN
FUNCTIONS -- A REAL BUG CAUGHT BY THIS MODULE'S OWN SELF-TEST: `x_L` needs
L (up to 160) days of history before an origin, and `y_h` needs h days
after it, to be valid. `stability_check.py` (and, if ever wired in,
`nonstationarity.py`'s by-year/leave-one-year-out) hands `block_test` /
`estimator` only a narrow DATE-RANGE SLICE of the price series (a 90-day
tile, or one calendar year) -- recomputing `predictor`/`target` FRESH from
that narrow slice starves the first `max(L, SIGMA_WINDOW)` rows of their
real lookback context (they'd be re-derived from data that doesn't exist
in the slice) and silently drops that many origins from every block, WITH
A CORRUPTED (not just smaller) x for the ones it does keep partially near
the edges. Measured effect during development: a 90-day block recomputed
this way kept only 45-50 of its 90 origins, using effectively-truncated
history for even those -- easily enough to flip an unambiguous, injected
positive edge into apparent block-level NEGATIVE signs.
FIX (same principle as `economic_gate.py`'s "one continuous run, then
slice for reporting"): `make_primary_estimator(full_closes)` and
`make_primary_block_test(full_closes)` are FACTORIES that precompute
`x_40`/`y_5` ONCE over the FULL, properly-historied close series, and
return closures that -- given whatever narrow date-range slice
`stability_check.py` (or `nonstationarity.py`) hands them -- select the
matching ORIGINS from those precomputed series by DATE, never recomputing
`predictor`/`target` on the slice itself. Callers must build the closure
with the FULL discovery-sample close series (or full holdout series, for
`forward_test.py`), not a block's own slice.

WHY THE ESTIMATOR AND THE SIGNAL ARE DELIBERATELY DIFFERENT FUNCTIONS, NOT
ONE: the estimator returns a regression SLOPE (a statistic, used to ask
"is there a real effect"). `primary_signal` returns a TRADING RULE (0/1
per day, used by `rule_evaluator.py`/`economic_gate.py` to ask "would
trading on it have made money"). These answer different questions and must
not be conflated into one function -- section 8's mistake log exists to
catch exactly this kind of shortcut.
"""

from __future__ import annotations

from math import erf, sqrt

import numpy as np
import pandas as pd
import statsmodels.api as sm

from multitest import annotate_family

LOOKBACKS = [10, 20, 40, 80, 160]
HORIZONS = [1, 5]
PRIMARY_L = 40
PRIMARY_H = 5
SIGMA_WINDOW = 30
HAC_LAGS = {1: 5, 5: 10}
DIRECTION = 1  # positive, per section 7


def _norm_sf(z: float) -> float:
    """Upper-tail standard normal survival function -- see leadlag.py's
    `_norm_cdf` / stability_check.py's / forward_test.py's own copies of
    the same convention (avoid pulling in scipy just for this)."""
    return 0.5 * (1 - erf(z / sqrt(2)))


def predictor(closes: pd.Series, L: int) -> pd.Series:
    """x = ln(C_t / C_{t-L}) / sigma30, aligned to day t (index label = t,
    i.e. the day the predictor is KNOWN as of that day's close). NaN for
    the first `max(L, SIGMA_WINDOW)` rows (whichever requirement -- the
    L-day window or the 30-day vol estimate -- needs more history; these
    do NOT stack, see the module docstring's WARMUP note)."""
    log_close = np.log(closes)
    daily_log_returns = log_close.diff()
    sigma30 = daily_log_returns.rolling(SIGMA_WINDOW).std()
    return (log_close - log_close.shift(L)) / sigma30


def target(closes: pd.Series, h: int) -> pd.Series:
    """y = ln(C_{t+h} / C_t), aligned to day t. NaN for the last h rows
    (no future data available yet for those origins)."""
    log_close = np.log(closes)
    return log_close.shift(-h) - log_close


def _regress(x: pd.Series, y: pd.Series, hac_lags: int) -> dict:
    """OLS of y on x with Newey-West HAC SE -- the shared regression core
    used by both `discovery_cell` (on freshly-computed x/y from raw
    closes) and the `make_primary_*` factories below (on PRE-COMPUTED,
    date-selected x/y) -- so a per-block stability test runs EXACTLY the
    same regression as discovery, just on a different, correctly-sourced
    subset of origins. Returns {"slope","se","t_stat","p_value","n"};
    `p_value` is one-sided in the pre-registered positive direction."""
    aligned = pd.DataFrame({"x": x, "y": y}).dropna()
    n = len(aligned)
    X = sm.add_constant(aligned["x"])
    model = sm.OLS(aligned["y"], X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    t_stat = float(model.tvalues["x"])
    return {
        "slope": float(model.params["x"]),
        "se": float(model.bse["x"]),
        "t_stat": t_stat,
        "p_value": _norm_sf(t_stat * DIRECTION),
        "n": n,
    }


def discovery_cell(closes: pd.Series, L: int, h: int) -> dict:
    """OLS of y_h on x_L with Newey-West HAC SE (section 7's per-cell
    test), matching this project's established HAC convention (see
    leadlag.py's `hac_lagged_regression`). Returns {"L","h","slope","se",
    "t_stat","p_value","n"}; `p_value` is ONE-SIDED in the pre-registered
    positive direction -- NOT the two-sided statsmodels default."""
    x = predictor(closes, L)
    y = target(closes, h)
    return {"L": L, "h": h, **_regress(x, y, HAC_LAGS[h])}


def discovery_all_cells(closes: pd.Series) -> pd.DataFrame:
    """All 10 (L, h) cells' discovery results, own-family Holm-adjusted
    (section 7: "Holm within the 10") via `multitest.annotate_family` --
    both Bonferroni and Holm reported, neither silently preferred, per
    this project's standing convention. One row per cell; the primary
    cell is the row with L=PRIMARY_L, h=PRIMARY_H."""
    cells = [discovery_cell(closes, L, h) for h in HORIZONS for L in LOOKBACKS]
    return annotate_family(pd.DataFrame(cells))


def make_primary_estimator(full_closes: pd.Series):
    """Factory: precomputes the primary cell's x_40/y_5 ONCE over
    `full_closes` (must be the FULL discovery-sample -- or full-holdout,
    for forward_test.py -- close series, not a block's own slice; see the
    module docstring's WHY note). Returns an `estimator(subset_df) ->
    float` closure for `nonstationarity.py` / `stability_check.py`-style
    callers: given a date-range slice, selects the matching precomputed
    origins by date and returns just the regression slope."""
    x_full = predictor(full_closes, PRIMARY_L)
    y_full = target(full_closes, PRIMARY_H)

    def estimator(subset_df: pd.DataFrame) -> float:
        dates = subset_df.index
        return _regress(x_full.reindex(dates), y_full.reindex(dates), HAC_LAGS[PRIMARY_H])["slope"]

    return estimator


def make_primary_block_test(full_closes: pd.Series):
    """Factory: precomputes the primary cell's x_40/y_5 ONCE over
    `full_closes` (see `make_primary_estimator` and the module docstring's
    WHY note) and returns a `block_test(subset_df) -> (z, p_two_sided)`
    closure for `stability_check.py`."""
    x_full = predictor(full_closes, PRIMARY_L)
    y_full = target(full_closes, PRIMARY_H)

    def block_test(subset_df: pd.DataFrame) -> tuple[float, float]:
        dates = subset_df.index
        result = _regress(x_full.reindex(dates), y_full.reindex(dates), HAC_LAGS[PRIMARY_H])
        z = result["t_stat"]
        return z, 2 * _norm_sf(abs(z))

    return block_test


def primary_signal(df: pd.DataFrame) -> pd.Series:
    """The PRE-REGISTERED ECONOMIC RULE (section 7): "long from the next
    open if x > 0 at the day's close, otherwise cash" -- using the primary
    cell's own L=40. Returns the RAW decision made at each day's close
    (1 if x>0 else 0); `rule_evaluator.evaluate_rule`'s own
    `held_positions` already handles "acts at the next bar's open" via
    `signal.shift(1)`, so this function must NOT shift anything itself."""
    x = predictor(df["close"], PRIMARY_L)
    return (x > 0).astype(int)


def count_origins(df: pd.DataFrame) -> int:
    """Valid (non-NaN x_40 AND non-NaN y_5) daily origins for the PRIMARY
    cell -- what "N" means everywhere in item 2 for this candidate
    (`freeze_manifest.py`'s n_discovery, `forward_test.py`'s n_holdout)."""
    x = predictor(df["close"], PRIMARY_L)
    y = target(df["close"], PRIMARY_H)
    return int((x.notna() & y.notna()).sum())


if __name__ == "__main__":
    import blocks
    import economic_gate
    import stability_check
    from rule_evaluator import STRESS_COST_PER_SIDE

    # ---- predictor/target: hand-computable on a small, deterministic
    # series (long enough for a real SIGMA_WINDOW=30 rolling window --
    # a series shorter than L+30 would have sigma30 entirely NaN, which
    # would silently pass a too-short check without testing anything).
    idx = pd.date_range("2024-01-01", periods=40, freq="1D", tz="UTC")
    rng_tiny = np.random.default_rng(1)
    closes_tiny = pd.Series(100 * np.exp(np.cumsum(rng_tiny.normal(0, 0.01, 40))), index=idx)
    x5 = predictor(closes_tiny, L=5)
    # Verify at the LAST index (39): recompute independently via pandas
    # slicing, not by re-deriving the implementation's own formula by hand.
    log_close = np.log(closes_tiny)
    manual_sigma30_at39 = log_close.diff().iloc[10:40].std()  # the 30 returns ending at day 39
    expected_x5_at39 = (log_close.iloc[39] - log_close.iloc[34]) / manual_sigma30_at39
    assert abs(x5.iloc[39] - expected_x5_at39) < 1e-9
    # Warmup is max(L, SIGMA_WINDOW), NOT L+SIGMA_WINDOW -- for L=5 < 30,
    # sigma30's own 30-day requirement is what actually binds (a real
    # off-by-a-lot mistake this exact assertion caught during development).
    assert x5.iloc[:30].isna().all(), "warmup must be max(L, SIGMA_WINDOW)=30 here, not L+SIGMA_WINDOW=35"
    assert x5.iloc[30:].notna().all()

    y1 = target(closes_tiny, h=1)
    assert abs(y1.iloc[0] - (np.log(closes_tiny.iloc[1]) - np.log(closes_tiny.iloc[0]))) < 1e-12
    assert y1.iloc[-1:].isna().all(), "the last h rows must be NaN (no future data yet)"

    # ---- discovery_cell: recovers a KNOWN injected trend-following
    # relationship, and shows no such relationship on pure noise. ----------
    rng = np.random.default_rng(0)
    n = 600  # long enough for L=160+30 warmup plus a meaningful post-warmup sample
    idx2 = pd.date_range("2020-01-01", periods=n, freq="1D", tz="UTC")

    # Trending series: inject a KNOWN, exact linear relationship between
    # x_40 (computed on a BASE random walk, before any injection -- no
    # circular feedback) and the next 5 days' returns, distributed evenly
    # across those 5 days. A sign-based or recursive-feedback injection was
    # tried first and produced wildly inconsistent per-block signs despite
    # a strongly significant pooled result -- this direct, non-circular
    # construction is what a controlled synthetic test actually needs.
    base_returns = rng.normal(0, 0.01, n)
    closes_trend = pd.Series(100 * np.exp(np.cumsum(base_returns)), index=idx2)
    x40_base = predictor(closes_trend, PRIMARY_L)  # base series only, no circularity
    true_slope = 0.003
    injected_effect = (true_slope * x40_base).fillna(0.0).to_numpy()
    adj = np.zeros(n)
    for t in range(n):
        if injected_effect[t] == 0.0:
            continue
        for s in range(t + 1, min(t + 6, n)):
            adj[s] += injected_effect[t] / 5.0
    closes_trend_final = pd.Series(100 * np.exp(np.cumsum(base_returns + adj)), index=idx2)

    primary_result = discovery_cell(closes_trend_final, PRIMARY_L, PRIMARY_H)
    assert primary_result["n"] > 400
    assert primary_result["slope"] > 0, "the injected trend-following edge must recover a positive slope"
    assert primary_result["p_value"] < 0.01, "a real, injected edge over 400+ origins must be clearly significant"

    closes_noise = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=idx2)
    noise_result = discovery_cell(closes_noise, PRIMARY_L, PRIMARY_H)
    assert noise_result["p_value"] > 0.05, "pure noise must not show a significant positive slope"

    # ---- discovery_all_cells: 10 rows, own-family Holm applied. -----------
    all_cells = discovery_all_cells(closes_trend_final)
    assert len(all_cells) == 10
    assert set(zip(all_cells["L"], all_cells["h"])) == {(L, h) for h in HORIZONS for L in LOOKBACKS}
    assert (all_cells["family_size"] == 10).all()
    assert "p_holm" in all_cells.columns and "p_bonferroni" in all_cells.columns
    primary_row = all_cells[(all_cells["L"] == PRIMARY_L) & (all_cells["h"] == PRIMARY_H)].iloc[0]
    assert abs(primary_row["slope"] - primary_result["slope"]) < 1e-12

    # ---- primary_signal: matches x>0 exactly, by hand, on a slice. --------
    df_trend = pd.DataFrame({"open": closes_trend_final.shift(-1).bfill(), "close": closes_trend_final})
    sig = primary_signal(df_trend)
    x_check = predictor(df_trend["close"], PRIMARY_L)
    assert (sig == (x_check > 0).astype(int)).all()

    # ---- count_origins matches discovery_cell's own n for the primary cell.
    assert count_origins(df_trend) == primary_result["n"]

    # ---- make_primary_block_test: built on the FULL series, its z/p for
    # the WHOLE-series date range must match discovery_cell's own numbers
    # exactly (same regression, same data, just reached via the factory).
    full_block_test = make_primary_block_test(closes_trend_final)
    z, p_two_sided = full_block_test(df_trend)
    assert abs(z - primary_result["t_stat"]) < 1e-12
    assert abs(p_two_sided - 2 * primary_result["p_value"]) < 1e-9

    # ---- THE BUG THIS FACTORY FIXES: a NAIVE per-block re-derivation
    # (discovery_cell on just a 90-day slice's own closes) starves x_40 of
    # lookback context and silently drops origins -- verify the factory's
    # date-selection approach recovers the FULL 90 origins a block should
    # have, while the naive approach recovers far fewer. -------------------
    block_start = idx2[max(PRIMARY_L, SIGMA_WINDOW)] + pd.Timedelta(days=270)
    block_end = block_start + pd.Timedelta(days=90)
    block_slice = df_trend[(df_trend.index >= block_start) & (df_trend.index < block_end)]
    naive_n = predictor(block_slice["close"], PRIMARY_L).notna().sum()
    full_estimator = make_primary_estimator(closes_trend_final)
    x_full_check = predictor(closes_trend_final, PRIMARY_L).reindex(block_slice.index)
    y_full_check = target(closes_trend_final, PRIMARY_H).reindex(block_slice.index)
    fixed_n_actual = pd.DataFrame({"x": x_full_check, "y": y_full_check}).dropna().shape[0]
    assert naive_n < fixed_n_actual, "the naive per-block recomputation must recover FEWER valid origins than the fixed, date-selecting approach"
    assert fixed_n_actual == len(block_slice), "the fixed approach must recover EVERY origin in a fully-warmed-up block"
    # make_primary_estimator's slope on this same block must match a direct
    # regression on the same date-selected x/y (cross-checks the factory
    # against an independently-assembled computation, not just its own logic).
    expected_block_slope = _regress(x_full_check, y_full_check, HAC_LAGS[PRIMARY_H])["slope"]
    assert abs(full_estimator(block_slice) - expected_block_slope) < 1e-12

    # ---- INTEGRATION: the factory-built block_test/estimator actually
    # plug into stability_check.py, and primary_signal into
    # economic_gate.py, without any adapter code. ---------------------------
    first_origin = idx2[max(PRIMARY_L, SIGMA_WINDOW)]  # first day x_40 is defined (L=40 > 30, so this is day 40)
    stability_result = stability_check.stability_check(
        df_trend, first_origin, pre_registered_direction=DIRECTION, block_test=make_primary_block_test(closes_trend_final),
    )
    assert stability_result["n_blocks_judged"] >= 3
    assert stability_result["passes"] is True, "the injected trend-following edge should pass the stability check"

    econ_result = economic_gate.economic_gate(
        df_trend, first_origin, primary_signal(df_trend), STRESS_COST_PER_SIDE,
    )
    assert len(econ_result["full_block_returns"]) >= 3
    # Not asserting economic_gate passes -- a real, statistically detectable
    # edge is not guaranteed to clear trading costs; that's exactly the
    # kind of question the economic gate exists to answer independently,
    # not something this self-test should assume either way.

    print(
        "Self-test passed: predictor/target match hand computation exactly, including correct NaN "
        "warmup/tail (max(L, SIGMA_WINDOW), not L+SIGMA_WINDOW); discovery_cell recovers a directly-"
        "injected, non-circular trend-following edge and shows no effect on pure noise; "
        "discovery_all_cells produces the full 10-cell family with own-family Holm applied; "
        "primary_signal/count_origins are internally consistent with discovery_cell's own numbers; "
        "the make_primary_estimator/make_primary_block_test factories are verified against an "
        "independent same-data regression and confirmed to recover every origin in a block (unlike "
        "a naive per-block recomputation, which silently starves early rows of lookback context); "
        "and the primary cell's hooks plug into stability_check.py and economic_gate.py directly, "
        "with no adapter code needed."
    )
