"""
S2 funding_extreme (Work Order 1.6): the funding-rate twin of formula_s1.py. This module supplies
the S2-specific hooks; everything else is item 2's own code, used UNCHANGED: cutoff.py,
formula_s1.block_structure (90-calendar-day blocks), stability_check.stability_s2 (time-shift null),
nonstationarity.py, multitest.py, rule_evaluator.py, economic_gate.py, registry.py.

SPEC (Work Order 1.6 section 1 and 2), in one place
  observations  8h-aligned settlements (00:00, 08:00, 16:00 UTC) from funding.funding_observations;
                a window with a missing native settlement is masked (NaN), the first settlement is masked.
  predictor     rank_s = (# of the 270 previous slots strictly below the current value
                          + 0.5 x # exactly tied) / 270, current value excluded (mid-rank).
                R2: the 270 previous slots must ALL be valid, else the origin is excluded and counted.
                Ties are exact after rounding to 12 decimals (the same rounding funding.tie_share uses).
                Strict-below and at-or-below ranks are computed too, as labeled robustness columns only.
  target        ln(open[s+1h+H] / open[s+1h]) on the 1h file, H in {24h, 72h} in clock time.
  cells         two: H=24h (HAC 3 lags) and H=72h (HAC 9 lags, PRIMARY). OLS slope with intercept,
                Newey-West HAC, direction NEGATIVE, one-sided p in the negative direction, Holm within the 2.
  origins       one COMMON set per pair: settlements from slot 272 (first settlement + 271 x 8h) to the
                last settlement s with s + 1h + 72h <= the last 1h bar of the discovery frame; an origin
                whose rank is invalid (R2), entry bar (s+1h) or either exit bar is missing from the 1h file
                is EXCLUDED and counted by reason (first reason in that order), never imputed.
  stability     Work Order 1.5 section 3, S2 variant (stability_check.stability_s2): 90-calendar-day blocks
                tiled from the first origin, partial block unscored but counted in the centring, d = -1,
                circular time-shift null (>= 300 settlements, R = 2000, seed stored), y = 72h forward return
                divided by sigma30 = sd (ddof 1) of the last 30 daily log returns using only daily closes
                at or before the origin time (all three settlements of day D use the close of day D-1).
  gate          long from the open of the 1h bar labeled s+1h while the latest valid rank <= 0.5, else cash,
                re-evaluated at each settlement (see `gate_decisions` for the interpretation).

INTERPRETATION CHOICES (every one is listed in the S2 report)
  1. Stability horizon: the work order does not say which horizon y uses; the PRIMARY cell (72h) is used.
  2. Gate validity, literal reading (mode "A", the one recorded): a settlement has a valid rank for the gate when
     its rank is valid (R2) AND its entry bar exists AND, for settlements that are nominal origins, the origin is
     not gap-excluded (so a missing EXIT bar up to 73h later forces cash). Mode "B" (labeled variant, never
     recorded): only an invalid rank forces cash; a missing entry bar just delays execution to the next bar.
  3. Gate segment: it starts flat at the first origin and acts on every settlement up to the last discovery bar
     (the rule needs no forward window), as S1's gate did; it is forced out at the last discovery bar's close.
  4. A decision made at settlement s is placed on the last 1h row with label <= s, so it executes at the next
     available bar's open, which is the open of s+1h when that bar exists. A position change whose execution bar
     is not s+1h is counted and reported (`late_executions`).
  5. HAC lags count observations, not hours, so a few excluded origins shift the lag spacing very slightly.

WARMUP / TAIL. Every vector stays on the full settlement grid with NaN where undefined; exclusions are counted,
never imputed, never shifted.
"""

from __future__ import annotations

from math import erf, sqrt

import numpy as np
import pandas as pd
import statsmodels.api as sm
from numpy.lib.stride_tricks import sliding_window_view

import economic_gate
import formula_s1
import funding
import rule_evaluator
import stability_check
from cutoff import CUTOFF, truncate_at_cutoff
from multitest import annotate_family

RANK_WINDOW = 270
SETTLEMENT_HOURS = 8
ENTRY_LAG_HOURS = 1
HORIZONS_H = [24, 72]
PRIMARY_H = 72
HAC_LAGS = {24: 3, 72: 9}
DIRECTION = -1  # negative: higher funding, lower forward return
BLOCK_DAYS = 90
SIGMA_WINDOW = formula_s1.SIGMA_WINDOW  # 30
RANK_THRESHOLD = 0.5
STABILITY_R = 2000
STABILITY_SEED = 12345
MIN_SHIFT = 300
TIE_DECIMALS = 12
EXPECTED_LAST_USABLE_BAR = pd.Timestamp("2025-08-31 23:00", tz="UTC")
REASONS = ("rank_invalid", "entry_bar_missing", "exit24_bar_missing", "exit72_bar_missing")


def _norm_sf(z: float) -> float:
    return 0.5 * (1 - erf(z / sqrt(2)))


def family_name(pair: str) -> str:
    """S2-ETHUSDT / S2-BTCUSDT (Work Order 1.4 pair-qualified naming)."""
    return f"S2-{pair.replace('_', '')}"


# ----------------------------------------------------------------------------- predictor
def ranks(rates, window: int = RANK_WINDOW) -> dict:
    """Mid-rank (primary), strict-below and at-or-below ranks of each value among its `window` PREVIOUS
    slots, current excluded. `rates` is the observation vector with NaN for masked slots. A slot's rank is NaN
    unless the current value and ALL `window` previous slots are finite (R2). Uses only slots <= i for slot i,
    so nothing after i can change rank_i. Returns {"mid","strict","atmost"} float arrays of len(rates)."""
    v = np.round(np.asarray(rates, dtype=float), TIE_DECIMALS)
    n = len(v)
    out = {k: np.full(n, np.nan) for k in ("mid", "strict", "atmost")}
    if n <= window:
        return out
    finite = np.isfinite(v)
    cs = np.concatenate([[0], np.cumsum(finite)])
    i = np.arange(window, n)
    valid = ((cs[i] - cs[i - window]) == window) & finite[i]
    filled = np.where(finite, v, 0.0)
    prev = sliding_window_view(filled, window)[: n - window]  # row j = filled[j : j + window]; slot i = j + window
    cur = filled[window:][:, None]
    below = (prev < cur).sum(axis=1)
    tied = (prev == cur).sum(axis=1)
    for key, val in (("mid", (below + 0.5 * tied) / window), ("strict", below / window), ("atmost", (below + tied) / window)):
        out[key][window:] = np.where(valid, val, np.nan)
    return out


# ----------------------------------------------------------------------------- target and volatility
def forward_log_return(opens: pd.Series, s_times: pd.DatetimeIndex, H: int) -> np.ndarray:
    """ln(open[s+1h+H] / open[s+1h]) at each settlement time; NaN if either bar is missing (never imputed)."""
    if opens.index.has_duplicates:
        raise ValueError("1h index has duplicates")
    entry = s_times + pd.Timedelta(hours=ENTRY_LAG_HOURS)
    exit_ = entry + pd.Timedelta(hours=H)
    o_in = opens.reindex(entry).to_numpy(float)
    o_out = opens.reindex(exit_).to_numpy(float)
    return np.log(o_out) - np.log(o_in)


def sigma30_at(df1d: pd.DataFrame, times: pd.DatetimeIndex) -> np.ndarray:
    """sd (ddof 1) of the last 30 daily log returns using only daily closes at or before each time. A daily bar
    labeled D closes at D+1 00:00, so for any time on day D the latest usable close is the bar labeled D-1.
    Computed on the complete daily calendar (a missing day is NaN, never skipped)."""
    cal = formula_s1._calendar(df1d)["close"]
    sig = formula_s1.sigma30(cal)
    day = times.normalize() - pd.Timedelta(days=1)
    return sig.reindex(day).to_numpy(float)


# ----------------------------------------------------------------------------- inputs and cutoff
def read_native(path) -> pd.DataFrame:
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.as_unit("ns")
    return df


def truncate_inputs(native: pd.DataFrame, df1h: pd.DataFrame, df1d: pd.DataFrame, cutoff: pd.Timestamp = CUTOFF) -> dict:
    """HARD truncation at the cutoff before any computation (funding settlements, 1h and 1d bars). Returns the
    truncated frames and the number of rows dropped and of post-cutoff rows left (must be 0)."""
    n2 = native[native["date"] <= cutoff].reset_index(drop=True)
    h2 = truncate_at_cutoff(df1h, cutoff)
    d2 = truncate_at_cutoff(df1d, cutoff)
    return {
        "native": n2, "df1h": h2, "df1d": d2,
        "dropped_rows": {"funding": int(len(native) - len(n2)), "1h": int(len(df1h) - len(h2)), "1d": int(len(df1d) - len(d2))},
        "post_cutoff_rows": {"funding": int((n2["date"] > cutoff).sum()), "1h": int((h2.index > cutoff).sum()), "1d": int((d2.index > cutoff).sum())},
    }


def load_discovery_inputs(data_dir, pair: str, raw_dir=None) -> dict:
    """Load `{pair}-funding.feather`, `{pair}-1h.feather`, `{pair}-1d.feather` and truncate at the cutoff."""
    from pathlib import Path

    from databundle import default_raw_dir, load_bundle

    data_dir = Path(data_dir)
    raw = Path(raw_dir) if raw_dir is not None else default_raw_dir(data_dir)
    fpath = next((f / f"{pair}-funding.feather" for f in (data_dir, raw) if (f / f"{pair}-funding.feather").exists()), None)
    if fpath is None:
        raise FileNotFoundError(f"no {pair}-funding.feather under {data_dir} or {raw}")
    bundle = load_bundle(data_dir, pair, ["1h", "1d"], raw_dir=raw_dir)
    out = truncate_inputs(read_native(fpath), bundle["1h"], bundle["1d"])
    out["funding_path"] = fpath
    return out


# ----------------------------------------------------------------------------- origin set
def s2_origin_set(obs: pd.DataFrame, df1h: pd.DataFrame) -> dict:
    """The family's COMMON ORIGIN SET (see the module docstring). `obs` = funding.funding_observations output
    on truncated native data; `df1h` = the truncated 1h frame. Returns a dict:
      grid, rates                    the full settlement grid and its (masked = NaN) rates
      rank_mid/rank_strict/rank_atmost   rank arrays on the grid (NaN where invalid)
      nominal                        settlements from slot 272 to the last with s+1h+72h <= last 1h bar
      origins                        usable common origins; excluded {reason: DatetimeIndex} (first reason wins)
      nominal_grid, usable_grid      boolean masks on the grid
      last_bar, first_position, limit
    Nothing is imputed; every exclusion is counted."""
    grid = obs.index
    rates = obs["rate"].to_numpy(float)
    rk = ranks(rates)
    labels = df1h.index
    if labels.has_duplicates or not labels.is_monotonic_increasing:
        raise ValueError("the 1h index must be unique and increasing")
    last_bar = labels.max()
    first_pos = RANK_WINDOW + 1  # slot 272 counting the masked first settlement as slot 1
    limit = last_bar - pd.Timedelta(hours=ENTRY_LAG_HOURS + max(HORIZONS_H))
    nominal_grid = np.zeros(len(grid), dtype=bool)
    if len(grid) > first_pos:
        nominal_grid[first_pos:] = True
        nominal_grid &= np.asarray(grid <= limit)
    usable_grid = np.zeros(len(grid), dtype=bool)
    nominal = grid[nominal_grid]
    pos = np.flatnonzero(nominal_grid)
    empty = pd.DatetimeIndex([], tz="UTC")
    excluded = {r: empty for r in REASONS}
    origins = empty
    if len(pos):
        one = pd.Timedelta(hours=ENTRY_LAG_HOURS)
        ok = {
            "rank_invalid": np.isfinite(rk["mid"][pos]),
            "entry_bar_missing": labels.get_indexer(nominal + one) >= 0,
            "exit24_bar_missing": labels.get_indexer(nominal + one + pd.Timedelta(hours=24)) >= 0,
            "exit72_bar_missing": labels.get_indexer(nominal + one + pd.Timedelta(hours=72)) >= 0,
        }
        usable = np.ones(len(pos), dtype=bool)
        alive = np.ones(len(pos), dtype=bool)
        for r in REASONS:
            bad = alive & ~ok[r]
            excluded[r] = nominal[bad]
            alive &= ok[r]
            usable &= ok[r]
        usable_grid[pos[usable]] = True
        origins = nominal[usable]
    return {
        "grid": grid, "rates": rates, "rank_mid": rk["mid"], "rank_strict": rk["strict"], "rank_atmost": rk["atmost"],
        "nominal": nominal, "origins": origins, "excluded": excluded, "nominal_grid": nominal_grid, "usable_grid": usable_grid,
        "last_bar": last_bar, "first_position": first_pos, "limit": limit,
    }


def origin_report(oset: dict, block_days: int = BLOCK_DAYS) -> dict:
    """Origin facts per pair (Work Order 1.6 section 1.5): first/last origin, counts, exclusions by reason, full
    blocks, partial block size, origins per full block. Also a stricter cross-check of the number of full blocks."""
    origins = oset["origins"]
    struct = formula_s1.block_structure(origins, block_days)
    full = [len(b["origins"]) for b in struct["blocks"] if b["is_full"]]
    strict_full = 0
    if len(origins):
        step = pd.Timedelta(days=block_days)
        end_of_span = origins[-1] + pd.Timedelta(hours=SETTLEMENT_HOURS)  # an origin occupies its 8h slot
        strict_full = int((end_of_span - origins[0]) // step)
    return {
        "first_origin": struct["first"], "last_origin": struct["last"],
        "n_origins": len(origins), "n_nominal": len(oset["nominal"]),
        "n_excluded": int(sum(len(v) for v in oset["excluded"].values())),
        "excluded_by_reason": {k: int(len(v)) for k, v in oset["excluded"].items()},
        "span_days": struct["span_days"], "n_full_blocks": struct["n_full"], "n_full_blocks_strict_check": strict_full,
        "partial_block_origins": struct["partial_origins"],
        "block_origins_min": min(full) if full else None,
        "block_origins_median": float(np.median(full)) if full else None,
        "block_origins_max": max(full) if full else None,
        "structure": struct,
    }


def s2_xy(oset: dict, df1h: pd.DataFrame, df1d: pd.DataFrame) -> pd.DataFrame:
    """The common-set vectors, indexed by origin: rank (mid, PRIMARY), rank_strict, rank_atmost, y24, y72, sigma30.
    Raises if any value is not finite (a gap would have been excluded already; sigma30 can still be missing)."""
    origins = oset["origins"]
    gpos = oset["grid"].get_indexer(origins)
    out = pd.DataFrame(
        {"rank": oset["rank_mid"][gpos], "rank_strict": oset["rank_strict"][gpos], "rank_atmost": oset["rank_atmost"][gpos]},
        index=origins,
    )
    for H in HORIZONS_H:
        out[f"y{H}"] = forward_log_return(df1h["open"], origins, H)
    out["sigma30"] = sigma30_at(df1d, origins)
    bad = out.isna().sum()
    if bad.any():
        raise ValueError(f"non-finite values at the common origins: {bad[bad > 0].to_dict()} -- ask the mathematician; nothing is imputed")
    if (out["sigma30"] <= 0).any():
        raise ValueError("sigma30 <= 0 at an origin")
    return out


# ----------------------------------------------------------------------------- discovery
def _regress(x, y, hac_lags: int) -> dict:
    aligned = pd.DataFrame({"x": np.asarray(x, float), "y": np.asarray(y, float)}).dropna()
    model = sm.OLS(aligned["y"], sm.add_constant(aligned["x"])).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    t_stat = float(model.tvalues["x"])
    return {
        "slope": float(model.params["x"]), "se": float(model.bse["x"]), "t_stat": t_stat,
        "p_value": _norm_sf(t_stat * DIRECTION), "n": int(len(aligned)),
        "corr": float(np.corrcoef(aligned["x"], aligned["y"])[0, 1]),
    }


def discovery_cells(xy: pd.DataFrame) -> pd.DataFrame:
    """Both cells (H = 24h, 72h) on the ONE common set, Holm and Bonferroni within the 2 (annotate_family).
    The primary cell is the row with H == PRIMARY_H. Every cell's n must equal len(xy)."""
    rows = [{"H": H, "hac_lags": HAC_LAGS[H], **_regress(xy["rank"], xy[f"y{H}"], HAC_LAGS[H])} for H in HORIZONS_H]
    frame = pd.DataFrame(rows)
    if not (frame["n"] == len(xy)).all():
        raise ValueError("cells are not on one common origin set")
    return annotate_family(frame)


def rank_variants_primary(xy: pd.DataFrame) -> pd.DataFrame:
    """Robustness columns on the primary cell only: mid-rank (primary), strict-below, at-or-below."""
    rows = []
    for name, col in (("mid-rank (primary)", "rank"), ("strict-below", "rank_strict"), ("at-or-below", "rank_atmost")):
        rows.append({"variant": name, **_regress(xy[col], xy[f"y{PRIMARY_H}"], HAC_LAGS[PRIMARY_H])})
    return pd.DataFrame(rows)


def extremes_table(xy: pd.DataFrame, lo: float = 0.10, hi: float = 0.90) -> pd.DataFrame:
    """Descriptive, exploratory only: mean forward return and its excess over the unconditional mean at the same
    horizon for rank <= lo and rank >= hi, with counts."""
    rows = []
    for H in HORIZONS_H:
        y = xy[f"y{H}"]
        uncond = float(y.mean())
        for name, m in ((f"rank <= {lo:.2f}", xy["rank"] <= lo), (f"rank >= {hi:.2f}", xy["rank"] >= hi)):
            n = int(m.sum())
            mean = float(y[m].mean()) if n else float("nan")
            rows.append({"H": H, "group": name, "n": n, "mean_fwd_return": mean, "unconditional_mean": uncond, "excess": mean - uncond})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- stability and by-year
def s2_stability(xy: pd.DataFrame, origins: pd.DatetimeIndex, R: int = STABILITY_R, seed: int = STABILITY_SEED, min_shift: int = MIN_SHIFT) -> dict:
    """The amended stability check, S2 variant, on the primary cell (72h): blocks from `formula_s1.block_structure`,
    x = mid-rank, y = 72h forward return / sigma30 (past-only), d = -1, circular time-shift null."""
    struct = formula_s1.block_structure(origins, BLOCK_DAYS)
    bounds = stability_check.full_block_bounds(origins, struct)
    x = xy["rank"].to_numpy(float)
    y = (xy[f"y{PRIMARY_H}"] / xy["sigma30"]).to_numpy(float)
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("non-finite stability vectors")
    out = stability_check.stability_s2(x, y, bounds, DIRECTION, R, min_shift, seed)
    full = [b for b in struct["blocks"] if b["is_full"]]
    out.update(
        {
            "n_origins": len(origins), "n_origins_in_blocks": int(bounds[-1][1]),
            "partial_block_origins": struct["partial_origins"],
            "block_starts": [b["start"].date().isoformat() for b in full],
            "block_origin_counts": [len(b["origins"]) for b in full],
            "horizon_h": PRIMARY_H,
        }
    )
    return out


def make_primary_estimator(xy_full: pd.DataFrame):
    """Factory for nonstationarity.py: precomputed vectors, a date-range slice selects origins BY DATE."""

    def estimator(subset_df: pd.DataFrame) -> float:
        dates = subset_df.index.intersection(xy_full.index)
        return _regress(xy_full.loc[dates, "rank"], xy_full.loc[dates, f"y{PRIMARY_H}"], HAC_LAGS[PRIMARY_H])["slope"]

    return estimator


# ----------------------------------------------------------------------------- economic gate hooks
def gate_decisions(oset: dict, df1h: pd.DataFrame, mode: str = "A", threshold: float = RANK_THRESHOLD):
    """(settlement times, 0/1 decisions) for every settlement from the first origin on. 1 = long (valid rank <=
    threshold), 0 = cash. Mode "A" (recorded): valid = rank valid AND entry bar exists AND, for nominal origins,
    the origin is not gap-excluded. Mode "B" (labeled variant): valid = rank valid only."""
    if mode not in ("A", "B"):
        raise ValueError("mode must be 'A' or 'B'")
    first = oset["origins"][0]
    m = np.asarray(oset["grid"] >= first)
    t = oset["grid"][m]
    r = oset["rank_mid"][m]
    valid_rank = np.isfinite(r)
    if mode == "B":
        valid = valid_rank
    else:
        entry_ok = df1h.index.get_indexer(t + pd.Timedelta(hours=ENTRY_LAG_HOURS)) >= 0
        valid = np.where(oset["nominal_grid"][m], oset["usable_grid"][m], valid_rank & entry_ok)
    with np.errstate(invalid="ignore"):
        value = (valid & (r <= threshold)).astype(int)
    return t, value


def signal_from_decisions(index: pd.DatetimeIndex, settle_times: pd.DatetimeIndex, values, start: pd.Timestamp):
    """The 0/1 signal on every 1h row of `index`: flat before `start`; a decision made at settlement s sits on the last
    row with label <= s (so rule_evaluator's shift(1) executes it at the next available bar's open, which is s+1h when
    that bar exists) and is carried forward until the next decision. Returns (signal Series, info) where info counts
    settlement-driven signal changes and those whose execution bar is not s+1h (`late_executions`)."""
    values = np.asarray(values, dtype=int)
    seg = index[index >= start]
    sig = pd.Series(0, index=index, dtype=int)
    info = {"signal_changes": 0, "late_executions": 0, "unexecuted_at_end": 0, "late_examples": []}
    if len(seg) == 0:
        return sig, info
    r = seg.searchsorted(settle_times, side="right") - 1
    arr = np.full(len(seg), np.nan)
    for ri, v in zip(r, values):
        if ri >= 0:
            arr[ri] = v
    sig.loc[seg] = pd.Series(arr).ffill().fillna(0).astype(int).to_numpy()
    prev = 0
    for s, ri, v in zip(settle_times, r, values):
        if ri < 0 or v == prev:
            continue
        prev = v
        info["signal_changes"] += 1
        if ri + 1 >= len(seg):
            info["unexecuted_at_end"] += 1
            continue
        if seg[ri + 1] != s + pd.Timedelta(hours=ENTRY_LAG_HOURS):
            info["late_executions"] += 1
            if len(info["late_examples"]) < 20:
                info["late_examples"].append({"settlement": s.isoformat(), "intended": (s + pd.Timedelta(hours=1)).isoformat(), "executed": seg[ri + 1].isoformat()})
    return sig, info


def s2_signal(oset: dict, df1h: pd.DataFrame, mode: str = "A"):
    t, v = gate_decisions(oset, df1h, mode)
    sig, info = signal_from_decisions(df1h.index, t, v, oset["origins"][0])
    info["mode"] = mode
    info["n_settlements_in_segment"] = int(len(t))
    info["n_long_decisions"] = int(v.sum())
    return sig, info


def run_gate(df1h: pd.DataFrame, first_origin: pd.Timestamp, signal: pd.Series, cost: float = rule_evaluator.STRESS_COST_PER_SIDE) -> dict:
    """The economic gate plus its R4 comparator on the SAME segment, blocks and stress cost: buy-and-hold is the
    always-long signal through the same evaluator (enters at the open after the first origin bar)."""
    gate = economic_gate.economic_gate(df1h, first_origin, signal, cost)
    data = df1h[df1h.index >= first_origin]
    strat = rule_evaluator.evaluate_rule(data, signal.loc[data.index], cost)
    ones = pd.Series(1, index=df1h.index)
    bh_gate = economic_gate.economic_gate(df1h, first_origin, ones, cost)
    bh = rule_evaluator.evaluate_rule(data, ones.loc[data.index], cost)
    held = rule_evaluator.held_positions(signal.loc[data.index])
    if abs(strat["net_return"] - gate["pooled_net_return"]) > 1e-12:
        raise ValueError("evaluate_rule and economic_gate disagree on the pooled return")
    return {
        "gate": gate, "strategy": strat, "buy_and_hold_gate": bh_gate, "buy_and_hold": bh,
        "exposure": float(held.mean()), "n_rows": int(len(data)),
        "forced_exit": [t for t in strat["trades"] if t["forced"]],
    }


# ============================================================================= self-test
def _make_world(n_days: int, seed: int, c: float = 0.0, sigma_h: float = 0.004, tie_share: float = 0.4,
                start: str = "2020-01-01 00:00", drop_bars=(), drop_native=(), unit: str = "ns"):
    """Synthetic world with known truth. Funding: iid, `tie_share` exactly at the modal 0.0001, the rest continuous.
    Hourly log-returns: iid noise sigma_h minus c x (mid-rank - 0.5) of the latest settlement (so rank_s drives the 7 hours
    after s: the true slope of the 72h forward return on rank_s is -7c). Hourly frame covers the whole grid."""
    rng = np.random.default_rng(seed)
    n_settle = n_days * 3
    t8 = pd.date_range(start, periods=n_settle, freq="8h", tz="UTC")
    u = rng.random(n_settle)
    rates = np.where(u < tie_share, 1e-4, np.round(rng.normal(1e-4, 1.5e-4, n_settle), 8))
    native = funding._mk_native(t8, rates)
    if len(drop_native):
        native = native.drop(index=list(drop_native)).reset_index(drop=True)
    rk = ranks(np.concatenate([[np.nan], rates[1:]]))["mid"]
    n_hours = n_settle * 8
    hours = pd.date_range(start, periods=n_hours, freq="1h", tz="UTC")
    drift = -c * (np.nan_to_num(rk[np.arange(n_hours) // 8], nan=0.5) - 0.5)
    ret = rng.normal(0.0, sigma_h, n_hours) + drift
    opens = 100.0 * np.exp(np.concatenate([[0.0], np.cumsum(ret)[:-1]]))
    closes = opens * np.exp(ret)
    df1h = pd.DataFrame({"open": opens, "close": closes}, index=hours.as_unit(unit))
    df1h.index.name = "date"
    d = df1h.groupby(df1h.index.floor("D")).agg(open=("open", "first"), close=("close", "last"))
    d.index.name = "date"
    if len(drop_bars):
        df1h = df1h.drop(index=pd.DatetimeIndex(list(drop_bars)).as_unit(unit))
    return {"native": native, "df1h": df1h, "df1d": d, "rates": rates, "t8": t8}


def _pipeline(world: dict):
    obs = funding.funding_observations(world["native"])
    oset = s2_origin_set(obs, world["df1h"])
    return obs, oset, s2_xy(oset, world["df1h"], world["df1d"])


def _brute_ranks(v, window):
    n = len(v)
    mid, st, am = (np.full(n, np.nan) for _ in range(3))
    r = [None if not np.isfinite(x) else round(float(x), TIE_DECIMALS) for x in v]
    for i in range(window, n):
        prev = r[i - window : i]
        if r[i] is None or any(p is None for p in prev):
            continue
        below = sum(1 for p in prev if p < r[i])
        tied = sum(1 for p in prev if p == r[i])
        mid[i], st[i], am[i] = (below + 0.5 * tied) / window, below / window, (below + tied) / window
    return mid, st, am


def _self_test() -> None:
    import time

    t0 = time.time()
    # ---- 1. mid-rank with heavy ties equals a brute-force reference (and a by-hand case)
    h = ranks([1, 1, 2, 3, 2], window=4)
    assert abs(h["mid"][4] - 0.625) < 1e-12 and abs(h["strict"][4] - 0.5) < 1e-12 and abs(h["atmost"][4] - 0.75) < 1e-12, "by hand: below 2, tied 1 of 4"
    rng = np.random.default_rng(1)
    for window, n in ((20, 400), (270, 900)):
        v = rng.choice([1, 2, 3], size=n, p=[0.5, 0.3, 0.2]) * 1e-4 + np.where(rng.random(n) < 0.15, rng.normal(0, 1e-5, n), 0.0)
        v[rng.random(n) < 0.02] = np.nan
        got, want = ranks(v, window), _brute_ranks(v, window)
        for k, w in zip(("mid", "strict", "atmost"), want):
            assert np.allclose(got[k], w, equal_nan=True, atol=1e-12), f"{k} rank differs from brute force (window {window})"
    ties = np.round(np.array([1e-4 + 1e-14, 1e-4, 1e-4 - 1e-14, 2e-4]), 12)
    assert ranks(np.concatenate([ties[:3], ties[:3], [1e-4]]), window=3)["mid"][6] == 0.5, "values equal after 12-decimal rounding tie exactly"
    print("  mid-rank: equals the brute-force reference with heavy ties and NaNs (windows 20 and 270); by-hand case; 12-decimal ties")

    # ---- 2. no look-ahead: changing values after slot i leaves rank_i unchanged
    v = rng.normal(0, 1, 700)
    base = ranks(v)["mid"]
    for i in (300, 450, 650):
        w = v.copy()
        w[i + 1 :] = rng.normal(0, 5, len(w) - i - 1)
        assert np.allclose(ranks(w)["mid"][: i + 1], base[: i + 1], equal_nan=True), f"rank at or before {i} changed with later values"
    world = _make_world(400, 2, c=0.0, unit="ms")  # millisecond-unit hourly index: alignment must be by value
    obs, oset, xy = _pipeline(world)
    k = len(oset["grid"]) // 2
    nat2 = world["native"].copy()
    later = nat2["date"] > oset["grid"][k]
    nat2.loc[later, "rate"] = nat2.loc[later, "rate"] * 3 + 1e-3
    oset2 = s2_origin_set(funding.funding_observations(nat2), world["df1h"])
    assert np.allclose(oset["rank_mid"][: k + 1], oset2["rank_mid"][: k + 1], equal_nan=True), "changing funding after s changed rank_s"
    # target starts at s+1h and ends at s+1h+H: open[k] = 100 exp(0.001 k) makes y exactly 0.001 H
    hours = world["df1h"].index
    flat = pd.DataFrame({"open": 100 * np.exp(0.001 * np.arange(len(hours))), "close": 1.0}, index=hours)
    yy = {H: forward_log_return(flat["open"], oset["origins"], H) for H in HORIZONS_H}
    assert all(np.allclose(yy[H], 0.001 * H) for H in HORIZONS_H), "target must span exactly [s+1h, s+1h+H]"
    flat2 = flat.copy()
    flat2.loc[oset["origins"][5], "open"] = 1e9  # the bar labeled s itself must not matter
    assert np.allclose(forward_log_return(flat2["open"], oset["origins"], 72), 0.072), "the bar labeled s must not enter the target"
    # sigma30 uses only closes at or before the origin: closes from day D on do not change sigma30 for times on day D
    d = world["df1d"].copy()
    s_t = oset["origins"][400]
    d2 = d.copy()
    d2.loc[d2.index >= s_t.normalize(), "close"] = d2.loc[d2.index >= s_t.normalize(), "close"] * 7.0
    a, b = sigma30_at(d, pd.DatetimeIndex([s_t])), sigma30_at(d2, pd.DatetimeIndex([s_t]))
    assert np.isfinite(a).all() and np.allclose(a, b), "future daily closes changed sigma30"
    d3 = d.copy()
    d3.loc[s_t.normalize() - pd.Timedelta(days=1), "close"] *= 1.5
    assert not np.allclose(sigma30_at(d3, pd.DatetimeIndex([s_t])), a), "the previous day's close must enter sigma30"
    print("  no look-ahead: later funding cannot change rank_s; target spans exactly [s+1h, s+1h+H]; sigma30 past-only (previous day's close enters, day D's does not); ms-unit index aligns by value")

    # ---- 3. R2 and origin counts on a clean synthetic series
    n_days = 500
    w = _make_world(n_days, 3)
    obs, oset, xy = _pipeline(w)
    grid = oset["grid"]
    assert np.isnan(oset["rank_mid"][: RANK_WINDOW + 1]).all(), "no rank before slot 272"
    assert oset["origins"][0] == grid[0] + 271 * pd.Timedelta(hours=8) == pd.Timestamp("2020-01-01", tz="UTC") + 271 * pd.Timedelta(hours=8), "first origin = first settlement + 271 x 8h"
    lim = w["df1h"].index.max() - pd.Timedelta(hours=73)
    want_last = grid[grid <= lim].max()
    assert oset["origins"][-1] == want_last and len(oset["excluded"]["rank_invalid"]) == 0
    assert len(oset["origins"]) == int(((grid >= grid[271]) & (grid <= lim)).sum()) == len(oset["nominal"])
    rep = origin_report(oset)
    assert rep["n_full_blocks"] == rep["n_full_blocks_strict_check"] and rep["block_origins_min"] == rep["block_origins_max"] == 270, "270 origins per full block when nothing is excluded"
    print(f"  R2 / origins: first origin = first settlement + 271 x 8h; last = last s with s+1h+72h <= last bar; {rep['n_origins']} origins, {rep['n_full_blocks']} full blocks of 270")

    # ---- 4. mask and gap exclusion counts, never imputed
    k = 600  # a native settlement is missing: observations k and k+1 are masked
    w2 = _make_world(n_days, 3, drop_native=[k])
    o2 = funding.funding_observations(w2["native"])
    assert int((~o2["complete"]).sum()) == 3, "first settlement + two windows touched by the missing native"
    ostat = s2_origin_set(o2, w2["df1h"])
    exp_bad = ~np.array([np.isfinite(r) for r in _brute_ranks(o2["rate"].to_numpy(), RANK_WINDOW)[0]])
    nom = ostat["nominal_grid"]
    assert len(ostat["excluded"]["rank_invalid"]) == int((exp_bad & nom).sum()) == 272, "masked slot k and k+1 invalidate the origins k .. k+271"
    assert len(ostat["origins"]) == len(oset["origins"]) - 272
    bad_grid = o2.index[exp_bad & nom]
    assert not ostat["origins"].isin(bad_grid).any()
    s_e, s_24, s_72 = grid[300], grid[330], grid[360]  # bars labeled s+1h are entry, exit24, exit72 of three different origins
    drops = [s_e + pd.Timedelta(hours=1), s_24 + pd.Timedelta(hours=25), s_72 + pd.Timedelta(hours=73), grid[400] + pd.Timedelta(hours=3)]
    w3 = _make_world(n_days, 3, drop_bars=drops)
    o3 = s2_origin_set(funding.funding_observations(w3["native"]), w3["df1h"])
    ex = {r: set(o3["excluded"][r]) for r in REASONS}
    assert s_e in ex["entry_bar_missing"] and s_24 in ex["exit24_bar_missing"] and s_72 in ex["exit72_bar_missing"], "each missing bar excludes its origin under the right reason"
    # a bar labeled s+1h is the entry of s, exit24 of s-24h and exit72 of s-72h
    assert {s_e - pd.Timedelta(hours=24), s_e - pd.Timedelta(hours=72)} <= ex["exit24_bar_missing"] | ex["exit72_bar_missing"] | ex["entry_bar_missing"]
    total_ex = sum(len(v) for v in o3["excluded"].values())
    assert total_ex == 9, "three missing bars, each the entry of one origin, exit24 of another and exit72 of a third"
    assert grid[400] in set(o3["origins"]), "a missing bar that no origin needs excludes nothing"
    assert len(o3["origins"]) + total_ex == len(oset["origins"])
    print(f"  masks and gaps: one missing native settlement -> 272 R2 exclusions (by brute force); missing entry/exit24/exit72 bars exclude their origins by reason ({total_ex} in total); nothing imputed")

    # ---- 5. cutoff truncation
    n_days = 1800
    start = "2021-01-01 00:00"
    wc = _make_world(n_days, 4, start=start)
    t = truncate_inputs(wc["native"], wc["df1h"], wc["df1d"])
    assert t["post_cutoff_rows"] == {"funding": 0, "1h": 0, "1d": 0} and t["dropped_rows"]["funding"] > 0 and t["dropped_rows"]["1h"] > 0
    assert t["native"]["date"].max() <= CUTOFF and t["df1h"].index.max() <= CUTOFF and t["df1d"].index.max() <= CUTOFF
    oc = s2_origin_set(funding.funding_observations(t["native"]), t["df1h"])
    assert oc["grid"].max() <= pd.Timestamp("2025-08-31 16:00", tz="UTC") and oc["last_bar"] == EXPECTED_LAST_USABLE_BAR
    assert oc["origins"][-1] == pd.Timestamp("2025-08-28 16:00", tz="UTC"), "last origin on a 00:00-aligned grid"
    wc2 = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in wc.items()}
    wc2["native"].loc[wc2["native"]["date"] > CUTOFF, "rate"] = 9.9
    t2 = truncate_inputs(wc2["native"], wc2["df1h"], wc2["df1d"])
    assert np.allclose(funding.funding_observations(t["native"])["rate"], funding.funding_observations(t2["native"])["rate"], equal_nan=True)
    print("  cutoff: post-cutoff rows after truncation = 0 (funding, 1h, 1d); last settlement <= 2025-08-31 16:00, last bar 2025-08-31 23:00, last origin 2025-08-28 16:00; post-cutoff values cannot matter")

    # ---- 6. injected negative relation is recovered; null p-values roughly uniform
    c = 0.00167  # true slope -7c = -0.0117, true correlation about -0.10
    slopes, corrs, ps = [], [], []
    for s in range(40):
        wi = _make_world(600, 100 + s, c=c)
        _, _, xyi = _pipeline(wi)
        cell = _regress(xyi["rank"], xyi["y72"], HAC_LAGS[72])
        slopes.append(cell["slope"]); corrs.append(cell["corr"]); ps.append(cell["p_value"])
    m, se = float(np.mean(slopes)), float(np.std(slopes, ddof=1) / np.sqrt(len(slopes)))
    assert abs(m - (-7 * c)) < max(4 * se, 0.15 * 7 * c), f"mean slope {m:.5f} vs true {-7 * c:.5f} (se {se:.5f})"
    assert -0.13 < float(np.mean(corrs)) < -0.07, f"mean corr {np.mean(corrs):.3f}"
    assert float(np.mean(np.array(slopes) < 0)) > 0.85 and float(np.mean(np.array(ps) < 0.05)) > 0.2
    pn = np.array([_regress(*(lambda xy_: (xy_["rank"], xy_["y72"]))(_pipeline(_make_world(300, 1000 + s))[2]), HAC_LAGS[72])["p_value"] for s in range(300)])
    frac = [float(np.mean(pn < q)) for q in (0.05, 0.25, 0.5, 0.75)]
    assert 0.02 <= frac[0] <= 0.12 and abs(frac[1] - 0.25) < 0.08 and abs(frac[2] - 0.5) < 0.09 and abs(frac[3] - 0.75) < 0.08, f"null p-values not roughly uniform: {frac}"
    print(f"  injected relation (true slope {-7 * c:.4f}, corr about -0.10): mean slope {m:.4f} (se {se:.4f}), mean corr {np.mean(corrs):.3f}, share of negative slopes {np.mean(np.array(slopes) < 0):.0%}; "
          f"null one-sided p below 0.05/0.25/0.5/0.75 in {frac[0]:.3f}/{frac[1]:.3f}/{frac[2]:.3f}/{frac[3]:.3f} of 300 worlds")

    # ---- 7. stability on a synthetic world (S2 variant wired through production code)
    wi = _make_world(1500, 7, c=0.006)
    _, oi, xyi = _pipeline(wi)
    st = s2_stability(xyi, oi["origins"], R=500, seed=1)
    assert st["B"] == origin_report(oi)["n_full_blocks"] and st["passes"] and st["share_blocks_positive"] > 0.6, f"strong injected edge must pass: p {st['p_stab']}"
    assert s2_stability(xyi, oi["origins"], R=500, seed=1) == st, "deterministic given the seed"
    wn = _make_world(1500, 8, c=0.0)
    _, on, xyn = _pipeline(wn)
    sn = s2_stability(xyn, on["origins"], R=500, seed=1)
    assert sn["p_stab"] > 0.01, "a null world should almost never reach p_stab < 0.01"
    ystd = (xyi["y72"] / xyi["sigma30"]).to_numpy()
    struct = formula_s1.block_structure(oi["origins"], BLOCK_DAYS)
    bnds = stability_check.full_block_bounds(oi["origins"], struct)
    assert np.allclose(st["c_b"], stability_check.block_scores(xyi["rank"].to_numpy(), ystd, bnds, DIRECTION), atol=1e-9), "block scores use x=rank, y=y72/sigma30, global centring"
    print(f"  stability: injected edge passes (p_stab {st['p_stab']:.4f}, {st['B']} blocks), null world p_stab {sn['p_stab']:.3f}, deterministic, block scores equal the definition")

    # ---- 8. by-year / leave-one-year-out plug in (primary cell, 120-day rule)
    import nonstationarity

    ns = nonstationarity.non_stationarity_report(xyi, make_primary_estimator(xyi))
    assert abs(ns["pooled_estimate"] - _regress(xyi["rank"], xyi["y72"], 9)["slope"]) < 1e-12 and len(ns["by_year"]) >= 4
    print(f"  by-year: pooled estimate equals the discovery slope; {len(ns['by_year'])} calendar years, judged only with >= 120 days")

    # ---- 9. the economic rule
    idx = pd.date_range("2020-01-01", periods=24 * 20, freq="1h", tz="UTC")
    sett = pd.date_range("2020-01-01 00:00", periods=60, freq="8h", tz="UTC")
    vals = np.array([0, 1, 1, 0, 0, 1, 0] + [0] * 53)
    sig, info = signal_from_decisions(idx, sett, vals, sett[0])
    held = rule_evaluator.held_positions(sig)
    chg = held.index[held.diff().fillna(held.iloc[0]).ne(0)]
    want = [sett[1] + pd.Timedelta(hours=1), sett[3] + pd.Timedelta(hours=1), sett[5] + pd.Timedelta(hours=1), sett[6] + pd.Timedelta(hours=1)]
    assert list(chg) == want, "positions change only at the open of s+1h of a decision change"
    assert info["signal_changes"] == 4 and info["late_executions"] == 0
    flat = pd.DataFrame({"open": 100.0, "close": 100.0}, index=idx)
    cost = 0.0015
    ev = rule_evaluator.evaluate_rule(flat, sig, cost)
    assert ev["n_trades"] == 4 and abs(ev["net_return"] - ((1 - cost) ** 4 - 1)) < 1e-12, "cost is charged once per position change (2 round trips)"
    # flat when there is no valid rank: a settlement with an invalid rank is cash even if the previous one was long
    o_t = s2_origin_set(funding.funding_observations(_make_world(500, 3, drop_native=[600])["native"]), _make_world(500, 3)["df1h"])
    tA, vA = gate_decisions(o_t, _make_world(500, 3)["df1h"], "A")
    bad = ~np.isfinite(o_t["rank_mid"][np.asarray(o_t["grid"] >= o_t["origins"][0])])
    assert bad.any() and (vA[bad] == 0).all(), "no valid rank means cash"
    # a missing bar: the change executes at the next available open, counted and reported
    idx2 = idx.delete(idx.get_loc(sett[1] + pd.Timedelta(hours=1)))
    sig2, info2 = signal_from_decisions(idx2, sett, vals, sett[0])
    held2 = rule_evaluator.held_positions(sig2)
    first_change = held2.index[held2.diff().fillna(held2.iloc[0]).ne(0)][0]
    assert first_change == sett[1] + pd.Timedelta(hours=2) and info2["late_executions"] == 1, "missing entry bar: executes at the next available open, counted"
    idx3 = idx.delete(idx.get_loc(sett[1]))
    sig3, info3 = signal_from_decisions(idx3, sett, vals, sett[0])
    held3 = rule_evaluator.held_positions(sig3)
    assert held3.index[held3.diff().fillna(held3.iloc[0]).ne(0)][0] == sett[1] + pd.Timedelta(hours=1) and info3["late_executions"] == 0, "missing settlement bar: still the open of s+1h"
    # mode A vs B differ only where a missing exit bar excludes an origin
    wg = _make_world(500, 3, drop_bars=[grid[300] + pd.Timedelta(hours=73)])
    og = s2_origin_set(funding.funding_observations(wg["native"]), wg["df1h"])
    tA, vA = gate_decisions(og, wg["df1h"], "A")
    tB, vB = gate_decisions(og, wg["df1h"], "B")
    diff = tA[vA != vB]
    assert (vB >= vA).all() and set(diff) <= set().union(*[set(v) for v in og["excluded"].values()]), "mode A differs from mode B only at gap-excluded origins"
    print("  economic rule: positions change only at the open of s+1h; cost once per change ((1-c)^n); cash when there is no valid rank; missing bar executes at the next open and is counted; mode A vs B differ only at gap-excluded origins")

    # ---- 10. gate end to end on a synthetic world (buy-and-hold comparator, forced exit)
    wgt = _make_world(1500, 9, c=0.0002)
    _, ogt, _ = _pipeline(wgt)
    sigA, infoA = s2_signal(ogt, wgt["df1h"], "A")
    g = run_gate(wgt["df1h"], ogt["origins"][0], sigA)
    assert g["gate"]["pass_rate"] >= 0 and len(g["forced_exit"]) <= 1 and 0.0 <= g["exposure"] <= 1.0
    assert np.isclose(np.prod([1 + v for v in g["gate"]["block_returns"].values()]), 1 + g["gate"]["pooled_net_return"], rtol=1e-9, atol=0.0)
    print(f"  gate: runs end to end on the synthetic world (pooled {g['gate']['pooled_net_return']:.3f}, buy-and-hold {g['buy_and_hold_gate']['pooled_net_return']:.3f}, exposure {g['exposure']:.2f})")

    print(f"Self-test passed in {time.time() - t0:.0f}s: formula_s2.py implements Work Order 1.6's predictor, target, origins, cells, stability and economic rule as specified.")


if __name__ == "__main__":
    _self_test()
