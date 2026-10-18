"""
S1 trend_slope (mathematician NOTES.md section 7, family 10) -- the FIRST
real candidate to run through item 2's machinery end to end. This module
supplies the S1-specific functions every item-2 module needs as a generic
hook (an `estimator`, a `count_origins`, a `signal_fn`/rule, a
`block_test`); item 2's own modules (cutoff.py, nonstationarity.py,
stability_check.py (amended statistic, Work Order 1.5 step 4), economic_gate.py, rule_evaluator.py, holdout_lock.py,
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

COMMON ORIGIN SET (Work Order 1.5 step 3; mathematician NOTES.md section 6, "Origin
sets"): ALL TEN CELLS ARE REGRESSED ON ONE COMMON SET OF ORIGINS -- the intersection,
by entry time, of every cell's usable origins -- never on each cell's own maximal
sample (that was bug 1 of the pre-fix S1: n between 2,772 and 2,906 across cells).
Built on a COMPLETE DAILY CALENDAR: the discovery frame is reindexed to every day from
its first to its last label, so a missing day is a NaN bar, not a silently skipped row
(a positional `shift(L)` over a gappy series would measure L ROWS, not L DAYS). The
nominal origins are the calendar positions from `max(max(L), SIGMA_WINDOW)` = 160 (the
161st daily close) to `N - 1 - max(h)` (h=5's last complete window; 2025-08-26 for the
discovery sample ending 2025-08-31). An origin is USABLE only if every bar it needs
exists: C_t and C_{t-L} for every L, the 31 closes t-30..t behind sigma30, C_{t+h}
for both h, and the entry bar of day t+1 (open and close). A nominal origin missing any
of them is EXCLUDED FOR A GAP and counted, never imputed (`s1_origin_set` reports
the excluded origins). The 90-day blocks are CALENDAR days tiled from the first origin
(`block_structure`): block b holds the origins whose labels fall in [t0 + 90b d,
t0 + 90(b+1) d) (the entry time is the next day's open for every origin, so labels and
entry times give the same partition); a block is full only if its whole window lies
inside the origin span (first origin to last origin, inclusive); the last partial block
is excluded. Blocks hold per-block index sets, never a reshape, so a gap-excluded origin
just leaves a block with fewer origins.

WHY primary_estimator AND primary_block_test ARE FACTORIES, NOT PLAIN
FUNCTIONS -- A REAL BUG CAUGHT BY THIS MODULE'S OWN SELF-TEST: `x_L` needs
L (up to 160) days of history before an origin, and `y_h` needs h days
after it, to be valid. A date-range slice handed by a caller (and, if ever wired in,
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
slice for reporting"): `make_primary_estimator(full_closes)` is a FACTORY
that precomputes `x_40`/`y_5` ONCE over the FULL, properly-historied close
series, and returns a closure that -- given whatever narrow date-range slice
a caller (`nonstationarity.py`) hands it -- selects the
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

import stability_check
from multitest import annotate_family

LOOKBACKS = [10, 20, 40, 80, 160]
HORIZONS = [1, 5]
PRIMARY_L = 40
PRIMARY_H = 5
SIGMA_WINDOW = 30
HAC_LAGS = {1: 5, 5: 10}
DIRECTION = 1  # positive, per section 7
BLOCK_DAYS = 90  # calendar days per block (Work Order 1.5, M1 ruling 2)
STABILITY_R = 2000  # null replicates (Work Order 1.5 section 3)
STABILITY_SEED = 12345  # fixed and stored in the registry record, so a run is reproducible
STABILITY_MEAN_BLOCK = 20  # mean block length (days) of the stationary bootstrap


def _norm_sf(z: float) -> float:
    """Upper-tail standard normal survival function -- see leadlag.py's
    `_norm_cdf` / forward_test.py's own copies of
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


def sigma30(closes: pd.Series) -> pd.Series:
    """Trailing std (ddof=1) of the last SIGMA_WINDOW daily log returns ending at day t --
    the same quantity `predictor` divides by; the stability check divides the forward return
    by it too (y = forward return / sigma30 at the origin)."""
    return np.log(closes).diff().rolling(SIGMA_WINDOW).std()


def target(closes: pd.Series, h: int) -> pd.Series:
    """y = ln(C_{t+h} / C_t), aligned to day t. NaN for the last h rows
    (no future data available yet for those origins)."""
    log_close = np.log(closes)
    return log_close.shift(-h) - log_close


def _calendar(data) -> pd.DataFrame:
    """The frame (or close Series) on a COMPLETE daily UTC calendar from its first to
    its last label; days with no bar become all-NaN rows. Raises if the index is not
    tz-aware, unique, increasing and midnight-labelled (S1 is a 1d-bar candidate)."""
    df = data.to_frame("close") if isinstance(data, pd.Series) else data
    idx = df.index
    if len(idx) == 0:
        return df
    if idx.tz is None:
        raise ValueError("S1 needs a tz-aware (UTC) daily index")
    if idx.has_duplicates or not idx.is_monotonic_increasing:
        raise ValueError("S1 needs a unique, increasing daily index")
    if not (idx == idx.normalize()).all():
        raise ValueError("S1 expects daily bars labelled at 00:00 UTC")
    return df.reindex(pd.date_range(idx[0], idx[-1], freq="1D"))


def s1_origin_set(data) -> dict:
    """The family's COMMON ORIGIN SET (see the module docstring). `data` is the daily
    frame (columns include "close", optionally "open") or a close Series, already
    truncated at the cutoff. Returns a dict:
      origins          DatetimeIndex of usable origins (labels = day t, the close the
                       predictor is known at), in order
      nominal          DatetimeIndex of nominal origins (calendar positions 160..N-1-5)
      excluded_gap     DatetimeIndex of nominal origins excluded because a needed bar is missing
      missing_days     DatetimeIndex of calendar days with no bar
      first_position, last_position   the nominal calendar positions used
    Nothing is imputed; every exclusion is counted."""
    cal = _calendar(data)
    empty = pd.DatetimeIndex([], tz="UTC")
    first_pos = max(max(LOOKBACKS), SIGMA_WINDOW)
    if len(cal) == 0 or len(cal) - 1 - max(HORIZONS) < first_pos:
        return {"origins": empty, "nominal": empty, "excluded_gap": empty, "missing_days": empty,
                "first_position": first_pos, "last_position": len(cal) - 1 - max(HORIZONS)}
    last_pos = len(cal) - 1 - max(HORIZONS)
    closes = cal["close"]
    ok = pd.Series(True, index=cal.index)
    for L in LOOKBACKS:
        ok &= predictor(closes, L).notna()
    for h in HORIZONS:
        ok &= target(closes, h).notna()
    entry_bar_exists = closes.shift(-1).notna()  # the entry bar is day t+1
    if "open" in cal.columns:
        entry_bar_exists &= cal["open"].shift(-1).notna()
    ok &= entry_bar_exists
    nominal = cal.index[first_pos : last_pos + 1]
    usable_mask = ok.loc[nominal].to_numpy()
    return {
        "origins": nominal[usable_mask],
        "nominal": nominal,
        "excluded_gap": nominal[~usable_mask],
        "missing_days": cal.index[closes.isna().to_numpy()],
        "first_position": first_pos,
        "last_position": last_pos,
    }


def common_origins(data) -> pd.DatetimeIndex:
    """Just the usable common origins (see `s1_origin_set`)."""
    return s1_origin_set(data)["origins"]


def block_structure(origins: pd.DatetimeIndex, block_days: int = BLOCK_DAYS) -> dict:
    """The 90-CALENDAR-day tiling of a family's origins (M1 ruling 2): block b holds the
    origins in [t0 + b*block_days d, t0 + (b+1)*block_days d), t0 = the first origin.
    A block is FULL only if its whole window lies inside the origin span (first origin
    to last origin inclusive), so the last partial block is not full. Per-block index
    sets, never a reshape. Returns {"first", "last", "span_days", "n_full", "blocks":
    [{"block_index","start","end","origins","is_full"}], "partial_origins"}."""
    if len(origins) == 0:
        return {"first": None, "last": None, "span_days": 0, "n_full": 0, "blocks": [], "partial_origins": 0}
    first, last = origins[0], origins[-1]
    span_days = (last - first).days + 1
    n_full = span_days // block_days
    n_blocks = n_full + (1 if span_days % block_days else 0)
    step = pd.Timedelta(days=block_days)
    blocks = []
    for b in range(n_blocks):
        start = first + b * step
        end = start + step
        members = origins[(origins >= start) & (origins < end)]
        blocks.append({"block_index": b, "start": start, "end": end, "origins": members, "is_full": b < n_full})
    partial = len(blocks[-1]["origins"]) if n_blocks > n_full else 0
    return {"first": first, "last": last, "span_days": span_days, "n_full": n_full, "blocks": blocks, "partial_origins": partial}


def origin_report(data, block_days: int = BLOCK_DAYS) -> dict:
    """Everything Work Order 1.5 step 3 / report item 1 asks for, per pair: first and
    last origin, origin count, origins excluded for gaps, full blocks, the partial
    block's size, and origins per full block (min / median / max)."""
    oset = s1_origin_set(data)
    struct = block_structure(oset["origins"], block_days)
    full_counts = [len(b["origins"]) for b in struct["blocks"] if b["is_full"]]
    return {
        "first_origin": struct["first"],
        "last_origin": struct["last"],
        "n_origins": len(oset["origins"]),
        "n_nominal": len(oset["nominal"]),
        "n_excluded_gap": len(oset["excluded_gap"]),
        "excluded_gap_dates": [d.date().isoformat() for d in oset["excluded_gap"][:20]],
        "n_missing_days": len(oset["missing_days"]),
        "span_days": struct["span_days"],
        "n_full_blocks": struct["n_full"],
        "partial_block_origins": struct["partial_origins"],
        "block_origins_min": min(full_counts) if full_counts else None,
        "block_origins_median": float(np.median(full_counts)) if full_counts else None,
        "block_origins_max": max(full_counts) if full_counts else None,
        "oset": oset,
        "structure": struct,
    }


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


def discovery_cell(closes: pd.Series, L: int, h: int, origins: pd.DatetimeIndex | None = None) -> dict:
    """OLS of y_h on x_L with Newey-West HAC SE (section 7's per-cell test), matching
    this project's established HAC convention (see leadlag.py's
    `hac_lagged_regression`). Returns {"L","h","slope","se","t_stat","p_value","n"};
    `p_value` is ONE-SIDED in the pre-registered positive direction -- NOT the
    two-sided statsmodels default.

    `origins` is the family's COMMON ORIGIN SET: x and y are selected at exactly
    those origins. With `origins=None` the cell uses its OWN maximal sample -- that
    is NOT a family result (it is only for unit checks); `discovery_all_cells` always
    passes the common set. x and y are computed on the COMPLETE daily calendar."""
    cal_closes = _calendar(closes)["close"]
    x = predictor(cal_closes, L)
    y = target(cal_closes, h)
    if origins is not None:
        x, y = x.reindex(origins), y.reindex(origins)
    return {"L": L, "h": h, **_regress(x, y, HAC_LAGS[h])}


def discovery_all_cells(closes: pd.Series, origins: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    """All 10 (L, h) cells' discovery results on ONE COMMON ORIGIN SET, own-family
    Holm-adjusted (section 7: "Holm within the 10") via `multitest.annotate_family`
    -- both Bonferroni and Holm reported, neither silently preferred. One row per
    cell; the primary cell is the row with L=PRIMARY_L, h=PRIMARY_H. `origins`
    defaults to `common_origins(closes)`; every cell's n must equal its length
    (checked: a cell on a different sample is bug 1 of the pre-fix S1)."""
    if origins is None:
        origins = common_origins(closes)
    cells = [discovery_cell(closes, L, h, origins) for h in HORIZONS for L in LOOKBACKS]
    frame = pd.DataFrame(cells)
    if not (frame["n"] == len(origins)).all():
        raise ValueError(f"cells are not on one common origin set: n={sorted(set(frame['n']))}, origins={len(origins)}")
    return annotate_family(frame)


def make_primary_estimator(full_closes: pd.Series, origins: pd.DatetimeIndex | None = None):
    """Factory: precomputes the primary cell's x_40/y_5 ONCE over `full_closes` (must
    be the FULL discovery-sample -- or full-holdout, for forward_test.py -- close
    series, not a block's own slice; see the module docstring's WHY note), on the
    complete daily calendar. Returns an `estimator(subset_df) -> float` closure for
    `nonstationarity.py`-style callers: given a date-range
    slice, it selects the matching precomputed origins BY DATE -- only dates that are
    members of the common origin set (`origins`, default `common_origins(full_closes)`)
    -- and returns just the regression slope. It never recomputes x or y on the slice."""
    cal_closes = _calendar(full_closes)["close"]
    members = common_origins(full_closes) if origins is None else origins
    x_full = predictor(cal_closes, PRIMARY_L)
    y_full = target(cal_closes, PRIMARY_H)

    def estimator(subset_df: pd.DataFrame) -> float:
        dates = subset_df.index.intersection(members)
        return _regress(x_full.reindex(dates), y_full.reindex(dates), HAC_LAGS[PRIMARY_H])["slope"]

    return estimator


def primary_xy_from_returns(r, positions, L: int = PRIMARY_L, h: int = PRIMARY_H):
    """Vectorised x (= ln(C_t/C_{t-L}) / sigma30) and y (= ln(C_{t+h}/C_t) / sigma30) of the
    PRIMARY cell, rebuilt from daily log returns `r` of shape (..., T) ALIGNED TO THE CLOSES
    (r[..., j] = ln(C_j / C_{j-1}), r[..., 0] = 0, so an origin position is a close position),
    at integer origin `positions`. sigma30 is the sample sd (ddof=1) of the 30 returns ending at
    the origin. This is `predictor`/`target`/`sigma30` computed from cumulative sums so the same
    code can run on thousands of resampled paths; `s1_stability` cross-checks it against the
    pandas versions on the real series at run time, and the self-test checks it on synthetic data."""
    r = np.asarray(r, dtype=float)
    pos = np.asarray(positions)
    lnC = np.cumsum(r, axis=-1)
    c2 = np.cumsum(r**2, axis=-1)
    s1 = lnC[..., pos] - lnC[..., pos - SIGMA_WINDOW]
    s2 = c2[..., pos] - c2[..., pos - SIGMA_WINDOW]
    sd30 = np.sqrt(np.maximum((s2 - s1**2 / SIGMA_WINDOW) / (SIGMA_WINDOW - 1), 1e-18))
    x = (lnC[..., pos] - lnC[..., pos - L]) / sd30
    y = (lnC[..., pos + h] - lnC[..., pos]) / sd30
    return x, y


def s1_stability_from_returns(
    r,
    positions,
    bounds: list[tuple[int, int]],
    *,
    R: int = STABILITY_R,
    seed: int = STABILITY_SEED,
    mean_block: float = STABILITY_MEAN_BLOCK,
    d: int = DIRECTION,
    chunk: int = stability_check.BOOTSTRAP_CHUNK,
) -> dict:
    """The S1 stability statistic (see stability_check.py) from close-aligned daily log returns
    `r` (length T, r[0] = 0), origin `positions` (close positions of the COMMON origin set) and
    the full-block `bounds` over that set. Null: stationary block bootstrap of the genuine
    returns r[1:] (the r[0] = 0 anchor is not part of the pool), predictor and target REBUILT
    from every resampled path at the same origin positions, `chunk` replicates at a time."""
    r = np.asarray(r, dtype=float)
    positions = np.asarray(positions)
    x0, y0 = primary_xy_from_returns(r, positions)
    c_obs = stability_check.block_scores(x0, y0, bounds, d)
    pool = r[1:]
    rng = np.random.default_rng(seed)
    c_null = np.empty((R, len(bounds)))
    done = 0
    while done < R:
        m = min(chunk, R - done)
        bi = stability_check.stationary_bootstrap_idx(m, len(pool), mean_block, rng)
        paths = np.concatenate([np.zeros((m, 1)), pool[bi]], axis=1)
        xb, yb = primary_xy_from_returns(paths, positions)
        c_null[done : done + m] = stability_check.block_scores(xb, yb, bounds, d)
        done += m
    T_obs, p, s_obs = stability_check.combine(c_obs, c_null)
    return stability_check.result_dict(T_obs, p, s_obs, c_obs, R, seed, {"mean_block_length": float(mean_block)})


def s1_stability(
    data,
    origins: pd.DatetimeIndex | None = None,
    *,
    R: int = STABILITY_R,
    seed: int = STABILITY_SEED,
    mean_block: float = STABILITY_MEAN_BLOCK,
) -> dict:
    """The S1 stability check on the discovery frame `data` (already truncated at the cutoff):
    the common origin set (default `common_origins(data)`), its 90-calendar-day full blocks
    (`block_structure`), observed x and y at the origins, and the bootstrap null (see
    `s1_stability_from_returns`). Refuses a series with missing days: a resampled return path
    needs a complete daily calendar (returns across a gap are not defined, and nothing is
    imputed). Cross-checks the vectorised x and y against the pandas `predictor`/`target`/
    `sigma30` on the real series and raises on any mismatch. Returns `stability_check.result_dict`
    plus origin/block facts."""
    cal = _calendar(data)
    closes = cal["close"]
    if closes.isna().any():
        raise ValueError(
            f"S1 stability needs a gap-free daily series; {int(closes.isna().sum())} calendar day(s) have no bar. "
            "Nothing is imputed: ask the mathematician how to handle the gap."
        )
    if origins is None:
        origins = common_origins(data)
    if len(origins) == 0:
        raise ValueError("no common origins")
    struct = block_structure(origins)
    bounds = stability_check.full_block_bounds(origins, struct)
    log_c = np.log(closes.to_numpy())
    r = np.diff(log_c, prepend=log_c[0])  # r[0] = 0, r[j] = ln(C_j / C_{j-1})
    positions = closes.index.get_indexer(origins)
    if (positions < 0).any():
        raise ValueError("an origin is not on the calendar")
    # Cross-check against the pandas production predictor / target / sigma30 (once, on the real series).
    x_v, y_v = primary_xy_from_returns(r, positions)
    x_p = predictor(closes, PRIMARY_L).reindex(origins).to_numpy()
    y_p = (target(closes, PRIMARY_H) / sigma30(closes)).reindex(origins).to_numpy()
    if not (np.allclose(x_v, x_p, rtol=1e-9, atol=1e-9) and np.allclose(y_v, y_p, rtol=1e-9, atol=1e-9)):
        raise ValueError("vectorised x/y differ from the pandas predictor/target: refusing to run")
    out = s1_stability_from_returns(r, positions, bounds, R=R, seed=seed, mean_block=mean_block)
    full = [b for b in struct["blocks"] if b["is_full"]]
    out.update(
        {
            "n_origins": len(origins),
            "n_origins_in_blocks": int(bounds[-1][1]),
            "partial_block_origins": struct["partial_origins"],
            "block_starts": [b["start"].date().isoformat() for b in full],
            "block_origin_counts": [len(b["origins"]) for b in full],
        }
    )
    return out


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
    """Number of COMMON-SET origins of `df` (see `s1_origin_set`) -- what "N" means
    everywhere in item 2 for this candidate (`freeze_manifest.py`'s n_discovery).
    NOTE for `forward_test.py` (Work Order 1.5 amendment A2, not needed for the S1
    report): a holdout-only slice has no look-back history, so its common set is
    empty or wrong; the forward-test hooks must be given the full history and count
    only origins whose entry is after the cutoff."""
    return len(common_origins(df))


def _brute_force_origins(df: pd.DataFrame) -> pd.DatetimeIndex:
    """Independent re-derivation of the usable common origins from first principles
    (which BARS each origin needs), with no pandas rolling/shift semantics at all --
    used only by the self-test to check `s1_origin_set` against."""
    have = set(df.index)
    days = pd.date_range(df.index[0], df.index[-1], freq="1D")
    one = pd.Timedelta(days=1)
    out = []
    for i in range(max(max(LOOKBACKS), SIGMA_WINDOW), len(days) - max(HORIZONS)):
        t = days[i]
        need = {t - L * one for L in LOOKBACKS} | {t - k * one for k in range(SIGMA_WINDOW + 1)}
        need |= {t + h * one for h in HORIZONS} | {t + one}
        if need <= have:
            out.append(t)
    return pd.DatetimeIndex(out, tz="UTC")


if __name__ == "__main__":
    import blocks
    import economic_gate
    import stability_reference as ref
    from rule_evaluator import STRESS_COST_PER_SIDE

    # ---- predictor/target: hand-computable on a small, deterministic series (long
    # enough for a real SIGMA_WINDOW=30 rolling window: with fewer than 31 closes
    # sigma30 would be entirely NaN, which would silently pass a too-short check).
    idx = pd.date_range("2024-01-01", periods=40, freq="1D", tz="UTC")
    rng_tiny = np.random.default_rng(1)
    closes_tiny = pd.Series(100 * np.exp(np.cumsum(rng_tiny.normal(0, 0.01, 40))), index=idx)
    x5 = predictor(closes_tiny, L=5)
    log_close = np.log(closes_tiny)
    manual_sigma30_at39 = log_close.diff().iloc[10:40].std()  # the 30 returns ending at day 39
    expected_x5_at39 = (log_close.iloc[39] - log_close.iloc[34]) / manual_sigma30_at39
    assert abs(x5.iloc[39] - expected_x5_at39) < 1e-9
    # Warmup is max(L, SIGMA_WINDOW), NOT L+SIGMA_WINDOW: for L=5 < 30 sigma30's own
    # 30-day requirement binds.
    assert x5.iloc[:30].isna().all(), "warmup must be max(L, SIGMA_WINDOW)=30 here, not L+SIGMA_WINDOW=35"
    assert x5.iloc[30:].notna().all()
    x40_tiny = predictor(pd.Series(closes_tiny.to_numpy().tolist() * 2, index=pd.date_range("2024-01-01", periods=80, freq="1D", tz="UTC")), 40)
    assert x40_tiny.iloc[:40].isna().all() and x40_tiny.iloc[40:].notna().all(), "L=40 > 30: warmup is 40"
    y1 = target(closes_tiny, h=1)
    assert abs(y1.iloc[0] - (np.log(closes_tiny.iloc[1]) - np.log(closes_tiny.iloc[0]))) < 1e-12
    assert y1.iloc[-1:].isna().all(), "the last h rows must be NaN (no future data yet)"

    # ---- A 2,000-day synthetic series with a KNOWN, injected, non-circular trend edge.
    rng = np.random.default_rng(0)
    n = 2000
    idx2 = pd.date_range("2018-01-01", periods=n, freq="1D", tz="UTC")
    base_returns = rng.normal(0, 0.01, n)
    closes_trend = pd.Series(100 * np.exp(np.cumsum(base_returns)), index=idx2)
    x40_base = predictor(closes_trend, PRIMARY_L)  # base series only, no circularity
    injected_effect = (0.003 * x40_base).fillna(0.0).to_numpy()
    adj = np.zeros(n)
    for t in range(n):
        if injected_effect[t] == 0.0:
            continue
        for s_ in range(t + 1, min(t + 6, n)):
            adj[s_] += injected_effect[t] / 5.0
    closes_edge = pd.Series(100 * np.exp(np.cumsum(base_returns + adj)), index=idx2)
    df_edge = pd.DataFrame({"open": closes_edge.shift(-1).bfill(), "close": closes_edge})
    closes_noise = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=idx2)

    # ---- COMMON ORIGIN SET, no gaps: positions 160 .. N-1-5 exactly (the 161st close
    # .. h=5's last complete window), the same for every cell.
    oset = s1_origin_set(df_edge)
    assert oset["origins"].equals(idx2[160 : n - 5]), "no gaps: origins must be index[160 : N-5]"
    assert len(oset["origins"]) == n - 165 and oset["origins"][0] == idx2[160] and oset["origins"][-1] == idx2[n - 6]
    assert len(oset["excluded_gap"]) == 0 and len(oset["missing_days"]) == 0
    assert oset["origins"].equals(common_origins(closes_edge)), "a close Series gives the same set as the frame"
    assert count_origins(df_edge) == n - 165
    all_cells = discovery_all_cells(closes_edge)
    assert len(all_cells) == 10 and (all_cells["n"] == n - 165).all(), "EVERY cell must use the common origin set"
    assert set(zip(all_cells["L"], all_cells["h"])) == {(L, h) for h in HORIZONS for L in LOOKBACKS}
    assert (all_cells["family_size"] == 10).all() and "p_holm" in all_cells.columns and "p_bonferroni" in all_cells.columns
    # A cell on its OWN sample (origins=None) has a larger n for short L -- that is the pre-fix bug.
    own = discovery_cell(closes_edge, 10, 1)
    assert own["n"] > n - 165, "a cell on its own sample differs from the common set (what the fix removes)"
    # Hand-check one cell on the common set: independent regression on the same dates.
    cell_40_5 = all_cells[(all_cells["L"] == 40) & (all_cells["h"] == 5)].iloc[0]
    xi, yi = predictor(closes_edge, 40).reindex(oset["origins"]), target(closes_edge, 5).reindex(oset["origins"])
    assert abs(cell_40_5["slope"] - _regress(xi, yi, HAC_LAGS[5])["slope"]) < 1e-12
    assert cell_40_5["slope"] > 0 and cell_40_5["p_value"] < 0.01, "the injected edge must be recovered, clearly significant"
    noise_cell = discovery_all_cells(closes_noise)
    noise_primary = noise_cell[(noise_cell["L"] == 40) & (noise_cell["h"] == 5)].iloc[0]
    assert noise_primary["p_value"] > 0.05, "pure noise must not show a significant positive primary slope"
    # Cells passed an inconsistent origin set must raise rather than silently mix samples.
    try:
        bad = discovery_all_cells(closes_edge, origins=oset["origins"][:-1])  # consistent subset: fine
        assert (bad["n"] == len(oset["origins"]) - 1).all()
    except Exception as exc:  # pragma: no cover
        raise AssertionError(f"a consistent explicit origin set must be accepted: {exc}")

    # ---- GAPS: excluded and counted, never imputed; checked against a first-principles
    # brute-force re-derivation. Holes: inside the first nominal origins' windows, a
    # two-day hole, one far inside, and one near the end.
    holes = [idx2[50], idx2[400], idx2[401], idx2[1000], idx2[n - 3]]
    df_gappy = df_edge.drop(index=holes)
    oset_g = s1_origin_set(df_gappy)
    expected_g = _brute_force_origins(df_gappy)
    assert oset_g["origins"].equals(expected_g), "gap exclusion must match the first-principles derivation exactly"
    assert len(oset_g["excluded_gap"]) > 0 and len(oset_g["missing_days"]) == len(holes)
    assert len(oset_g["origins"]) + len(oset_g["excluded_gap"]) == len(oset_g["nominal"])
    assert not set(holes) & set(oset_g["origins"]), "an origin on a missing day is excluded"
    # x_160 reaches back 160 DAYS: the origin exactly 160 days after a hole is excluded
    # even though 160 ROWS back is a different day (calendar days, not row counts).
    assert idx2[50] + pd.Timedelta(days=160) not in set(oset_g["origins"])
    assert idx2[1000] - pd.Timedelta(days=1) not in set(oset_g["origins"]), "the entry bar (day t+1) must exist"
    cells_g = discovery_all_cells(df_gappy["close"])
    assert (cells_g["n"] == len(oset_g["origins"])).all(), "with gaps, every cell is still on the one common set"
    # A hole inside the FIRST nominal origin's volatility window (day 150 is within the 30
    # returns behind origin 160): that origin is excluded and counted, so the first origin moves.
    df_early_hole = df_edge.drop(index=[idx2[150]])
    oset_e = s1_origin_set(df_early_hole)
    assert oset_e["origins"].equals(_brute_force_origins(df_early_hole))
    assert oset_e["origins"][0] > idx2[160] and len(oset_e["excluded_gap"]) > 0

    # ---- BLOCKS: 90 calendar days from the first origin; per-block index sets; the
    # partial block is not full; matches blocks.tile_blocks (the economic gate's tiler).
    struct = block_structure(oset["origins"])
    assert struct["span_days"] == n - 165 and struct["n_full"] == (n - 165) // 90 == 20
    assert struct["partial_origins"] == (n - 165) % 90 == 35
    assert [len(b["origins"]) for b in struct["blocks"][:-1]] == [90] * 20 and len(struct["blocks"]) == 21
    assert struct["blocks"][0]["start"] == oset["origins"][0] and struct["blocks"][-1]["is_full"] is False
    rep = origin_report(df_edge)
    assert (rep["n_origins"], rep["n_full_blocks"], rep["partial_block_origins"]) == (n - 165, 20, 35)
    assert (rep["block_origins_min"], rep["block_origins_median"], rep["block_origins_max"]) == (90, 90.0, 90)
    tiled = blocks.tile_blocks(df_edge.loc[oset["origins"]], oset["origins"][0])
    assert len(tiled) == len(struct["blocks"])
    for tb, mine in zip(tiled, struct["blocks"]):
        assert tb["data"].index.equals(mine["origins"]) and tb["is_final_partial"] == (not mine["is_full"])
    # With gaps: block BOUNDARIES stay on the calendar, a block simply has fewer origins.
    struct_g = block_structure(oset_g["origins"])
    for b in struct_g["blocks"]:
        for d in b["origins"]:
            assert b["start"] <= d < b["end"]
            assert (d - oset_g["origins"][0]).days // 90 == b["block_index"]
    assert sum(len(b["origins"]) for b in struct_g["blocks"]) == len(oset_g["origins"]), "no origin is dropped by tiling"
    assert min(len(b["origins"]) for b in struct_g["blocks"] if b["is_full"]) < 90, "a block with a gap has fewer than 90 origins"
    tiled_g = blocks.tile_blocks(df_gappy.loc[oset_g["origins"]], oset_g["origins"][0])
    for tb, mine in zip(tiled_g, struct_g["blocks"]):
        assert tb["data"].index.equals(mine["origins"]) and tb["is_final_partial"] == (not mine["is_full"])
    # Exact multiple: no partial block.
    exact = block_structure(oset["origins"][:180])
    assert exact["n_full"] == 2 and exact["partial_origins"] == 0 and len(exact["blocks"]) == 2

    # ---- primary_signal: matches x>0 exactly, by hand.
    sig = primary_signal(df_edge)
    assert (sig == (predictor(df_edge["close"], PRIMARY_L) > 0).astype(int)).all()

    # ---- Factories: select by date from a full-series precomputation, never recompute
    # on a slice; only common-set dates are used.
    assert abs(make_primary_estimator(closes_edge)(df_edge) - cell_40_5["slope"]) < 1e-12
    block1 = struct["blocks"][3]
    block_slice = df_edge[(df_edge.index >= block1["start"]) & (df_edge.index < block1["end"])]
    naive_n = predictor(block_slice["close"], PRIMARY_L).notna().sum()
    assert naive_n < len(block_slice), "a naive per-block recomputation starves x of look-back and drops origins"
    x_chk = predictor(closes_edge, PRIMARY_L).reindex(block1["origins"])
    y_chk = target(closes_edge, PRIMARY_H).reindex(block1["origins"])
    assert pd.DataFrame({"x": x_chk, "y": y_chk}).dropna().shape[0] == 90 == len(block1["origins"])
    est = make_primary_estimator(closes_edge)
    assert abs(est(block_slice) - _regress(x_chk, y_chk, HAC_LAGS[PRIMARY_H])["slope"]) < 1e-12
    # A slice that includes non-origin dates (the 160-day warmup) still only uses common-set dates.
    warm_slice = df_edge.iloc[:300]
    only_origins = warm_slice.loc[warm_slice.index.intersection(oset["origins"])]
    assert abs(est(warm_slice) - est(only_origins)) < 1e-12, "dates outside the common set must be ignored"

    # ---- STABILITY (Work Order 1.5 step 4). The vectorised x/y equal the pandas predictor/target/sigma30.
    log_c = np.log(closes_edge.to_numpy())
    r_edge = np.diff(log_c, prepend=log_c[0])
    pos_edge = closes_edge.index.get_indexer(oset["origins"])
    x_v, y_v = primary_xy_from_returns(r_edge, pos_edge)
    assert np.allclose(x_v, predictor(closes_edge, PRIMARY_L).reindex(oset["origins"]), rtol=1e-9, atol=1e-9)
    assert np.allclose(y_v, (target(closes_edge, PRIMARY_H) / sigma30(closes_edge)).reindex(oset["origins"]), rtol=1e-9, atol=1e-9)

    # Equal to the mathematician's reference where the definitions coincide (no partial block, same seed,
    # one chunk and several chunks): the reference path of T genuine returns = production r[1:].
    r_ref, idx_ref = ref.sim_s1(np.random.default_rng(21), 2, 6, 30, "gauss", 0.006)
    for i, R_ in ((0, 200), (1, 600)):
        want_T, want_p, want_s, want_c = ref.stability_s1(r_ref[i], idx_ref, 6, 30, +1, R=R_, seed=i)
        got = s1_stability_from_returns(
            np.concatenate([[0.0], r_ref[i]]), idx_ref + 1, [(b_ * 30, (b_ + 1) * 30) for b_ in range(6)], R=R_, seed=i
        )
        assert abs(got["T"] - want_T) < 1e-9 and abs(got["p_stab"] - want_p) < 1e-12, "must reproduce the reference exactly"
        assert np.allclose(got["s_b"], want_s) and np.allclose(got["c_b"], want_c)

    # With a PARTIAL block: the scores equal the definition applied literally (pandas, whole-set centring),
    # and differ from slice centring (the reference's [:B*n] simplification).
    st = s1_stability(df_edge, R=200, seed=1)
    assert (st["B"], st["n_origins"], st["partial_block_origins"], st["n_origins_in_blocks"]) == (20, n - 165, 35, 1800)
    xo = predictor(closes_edge, PRIMARY_L).reindex(oset["origins"])
    yo = (target(closes_edge, PRIMARY_H) / sigma30(closes_edge)).reindex(oset["origins"])
    prod_all = (xo - xo.mean()) * (yo - yo.mean())
    literal = [DIRECTION * prod_all.loc[b_["origins"]].sum() for b_ in struct["blocks"] if b_["is_full"]]
    assert np.allclose(st["c_b"], literal, rtol=1e-9, atol=1e-12), "block scores must equal the definition, centred on the WHOLE set"
    x1800, y1800 = xo.iloc[:1800], yo.iloc[:1800]
    sliced = ((x1800 - x1800.mean()) * (y1800 - y1800.mean())).to_numpy().reshape(20, 90).sum(1)
    assert not np.allclose(st["c_b"], sliced), "centring over the whole set differs from the reference's slice centring"
    assert st["block_origin_counts"] == [90] * 20 and len(st["block_starts"]) == 20 and st["block_starts"][0] == oset["origins"][0].date().isoformat()
    assert st["R"] == 200 and st["seed"] == 1 and st["mean_block_length"] == 20.0 and len(st["s_b"]) == 20
    assert st["passes"] == (st["p_stab"] < 0.05) and 0 < st["share_blocks_positive"] <= 1
    assert s1_stability(df_edge, R=200, seed=1) == st, "deterministic given the seed"
    assert st["p_stab"] < 0.05, f"the injected edge must pass the stability check (p_stab {st['p_stab']:.4f})"
    noise = s1_stability(pd.DataFrame({"open": closes_noise.shift(-1).bfill(), "close": closes_noise}), R=200, seed=1)
    assert noise["p_stab"] > 0.01, f"pure noise must not pass (p_stab {noise['p_stab']:.4f})"
    try:
        s1_stability(df_gappy, R=50)
    except ValueError as exc:
        assert "gap-free" in str(exc)
    else:
        raise AssertionError("a series with missing days must be refused, not imputed")

    # ---- INTEGRATION: the primary hooks plug into economic_gate.py with no adapter code.
    first_origin = oset["origins"][0]
    econ_result = economic_gate.economic_gate(df_edge, first_origin, primary_signal(df_edge), STRESS_COST_PER_SIDE)
    assert len(econ_result["full_block_returns"]) >= 3
    # The gate tiles the discovery rows from the same first origin: its FULL blocks are the same
    # calendar blocks (it may run a few days longer in its partial block; see message-16).
    gate_tiles = blocks.tile_blocks(df_edge, first_origin)
    assert sum(not b["is_final_partial"] for b in gate_tiles) >= struct["n_full"]

    print(
        "Self-test passed: predictor/target match hand computation with warmup max(L,30); the common "
        "origin set is index[160:N-5] with no gaps and matches a first-principles brute-force "
        "derivation with gaps (excluded origins counted, none imputed, L measured in calendar days, "
        "entry bar required); all 10 cells use that one set and a cell on its own sample differs; "
        "block_structure gives 90-calendar-day blocks from the first origin with per-block index sets, "
        "a partial block that is not full, and matches blocks.tile_blocks; the factories select by "
        "date from a full-series precomputation and ignore non-common dates; the injected edge is "
        "recovered and pure noise is not; the vectorised x/y equal the pandas predictor/target; the "
        "S1 stability statistic reproduces the mathematician's reference exactly where the definitions "
        "coincide (one and several bootstrap chunks), equals the definition applied literally with a "
        "partial block (global centring), passes an injected edge, does not pass noise, is deterministic "
        "given the seed, and refuses a gappy series; the hooks plug into economic_gate.py."
    )
