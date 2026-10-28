"""
Task 3 shock_response (Work Order 1.7): the event clock, targets, cell statistics, classification, event-stability
statistic and the acceptance machinery. Families `Task3-ETHUSDT` and `Task3-BTCUSDT`, same code, 48 cells per pair.
PRE-TAX. The production twin of `docs/work-orders/1.7-task3_reference.py`: on a gap-free series it must reproduce the
reference exactly (self-test 1); on real data it adds gap masking, the cutoff and the derived 15m bars.

SPEC (Work Order 1.7 section 1 and 2), in one place
  bars          5m and 15m, left-labelled; 15m derived from 5m: a 15m bar with any of its three 5m bars missing is missing.
                A bar is present iff open, high, low and close exist; missing bars are masked, never filled.
  returns       r_j = ln(C_j / C_(j-1)) only if bars j and j-1 are both present (consecutive on the regular grid), else masked.
  z, eligible   z_j = r_j / sd_j, sd_j = sample sd (ddof 1) of r_(j-W)..r_(j-1), W = 288 (5m) / 96 (15m); bar j is eligible iff r_j
                and all W earlier returns are unmasked and sd_j > 0. Event: |z_j| >= 3 (down z <= -3, up z >= +3). Decision at
                the close of bar j, entry at the open of bar j+1.
  clock         ONE shared clock per timeframe and pair: scan eligible event bars in time order, keep the first, ignore every event
                bar before j+13, keep the first at or after j+13. A kept event whose target window later proves incomplete stays on
                the clock and is dropped from the statistics (counted). Variant: one clock per side.
  targets       R_k = ln(C_(j+k) / O_(j+1)), k = 1..12. An event with any of the bars j+1..j+12 missing (or beyond the cutoff-truncated
                frame) is excluded from all k (one common event set). mu_k = mean of R_k over ALL origins (eligible bar, bars j+1..j+12
                present), event bars included; a constant. Excess e = R_k - mu_k. Variant: mu_k from the |z| < 3 origins only.
  cells         {5m, 15m} x k 1..12 x {down, up} = 48 per pair; n, mean raw, mean excess, day-clustered SE (clusters = UTC calendar days
                of the entry bar, SE = sqrt(sum_c (sum_i (e_i - mean))^2) / n), naive SE, t, MDE = 2.486 x SE. Normal p-values.
                PRIMARY cells (5m, k = 6, down) and (5m, k = 6, up): one-sided POSITIVE p = 1 - Phi(t); the other 46: two-sided,
                descriptive. Holm and Bonferroni over the 48 (primary one-sided and other two-sided p in the same Holm).
  classify      M = 0.0035 on the excess: PASS = Holm one-sided p < 0.05 and mean excess >= M; DEAD = mean + 1.645 SE < M and
                MDE <= M; otherwise INCONCLUSIVE.
  dose          the same with |z| >= 4 and its own fresh shared clock; for a cell whose |z| >= 3 mean excess is POSITIVE (M2's ruling of 2026-10-27),
                |z| >= 3 is discarded if the |z| >= 4 mean excess is smaller and the |z| >= 4 sample has at least 30 events; fewer than 30:
                "not evaluable", flagged for M2; a cell with a non-positive |z| >= 3 mean prints "n/a: no positive effect".
  stability     per primary cell: 90-calendar-day blocks tiled from t0 = entry time of the first eligible 5m origin; a block is scored
                only if its whole window lies inside [t0, entry time of the last eligible 5m origin + 5 minutes]; blocks with < 30
                events are listed and excluded; t_b = mean(e) / (sd(e) / sqrt(n_b)); T = sum t_b / sqrt(B'); p_stab = 1 - Phi(T).

INTERPRETATION CHOICES (all listed in the report)
  1. A bar is present iff open, high, low and close exist AND, in the PRIMARY (M2's ruling of 2026-10-27), its volume is not zero: a zero-volume
     placeholder bar is treated exactly like a missing bar everywhere (no return for it or the next bar, every z window containing it invalid, a target window
     containing it incomplete, a 15m bin containing it missing, excluded from mu_k). The literal reading (placeholders present) is the labeled sensitivity.
  2. Day clusters use the UTC calendar day of the entry bar's label (bar j+1).
  3. Normal p-values use the survival function (accurate in the tail) instead of 1 - cdf; the difference is below 1e-15.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from multitest import annotate_family

W5, W15 = 288, 96
KMAX = 12
GAP = 13
THR = 3.0
THR_DOSE = 4.0
M = 0.0035
NMIN_BLOCK = 30
BLOCK_DAYS = 90
PRIMARY_K = 6
MDE_MULTIPLIER = 2.486
TIMEFRAMES = {"5m": (300, W5), "15m": (900, W15)}
DAY_S = 86400
EPOCH_2017_08_17 = int(pd.Timestamp("2017-08-17", tz="UTC").timestamp())


# ----------------------------------------------------------------------------- bars and frames
class Frame:
    """A regular left-labelled grid: label seconds `sec`, open `O` and close `C` (NaN where the bar is missing)."""

    def __init__(self, sec: np.ndarray, O: np.ndarray, C: np.ndarray, width_s: int):
        self.sec, self.O, self.C, self.width = np.asarray(sec, dtype=np.int64), np.asarray(O, float), np.asarray(C, float), int(width_s)
        self.n = len(self.sec)
        self.present = np.isfinite(self.O) & np.isfinite(self.C)

    def label(self, j) -> pd.Timestamp:
        return pd.Timestamp(int(self.sec[j]), unit="s", tz="UTC")


def frame_from_df(df: pd.DataFrame, width_s: int, mask_zero_volume: bool = False) -> tuple[Frame, dict]:
    """Regular grid from the first to the last label; a bar is present only if open, high, low and close are all finite.
    Returns (Frame, facts): rows, grid length, missing bars, rows without full OHLC, zero-volume bars."""
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError("bar index must be unique and increasing")
    unit_div = {"ns": 10 ** 9, "us": 10 ** 6, "ms": 10 ** 3, "s": 1}[df.index.unit]
    sec = df.index.asi8 // unit_div
    if (np.diff(sec) % width_s).any() or sec[0] % width_s:
        raise ValueError("bars are not aligned to the timeframe grid")
    n = int((sec[-1] - sec[0]) // width_s) + 1
    pos = ((sec - sec[0]) // width_s).astype(np.int64)
    ohlc_ok = df[["open", "high", "low", "close"]].notna().all(axis=1).to_numpy()
    masked_zero = 0
    if mask_zero_volume and "volume" in df.columns:  # labeled VARIANT (Work Order 1.7 question 2): zero-trade placeholder bars treated as missing
        zv = (df["volume"].to_numpy() == 0) & ohlc_ok
        masked_zero = int(zv.sum())
        ohlc_ok = ohlc_ok & ~zv
    O = np.full(n, np.nan)
    C = np.full(n, np.nan)
    O[pos[ohlc_ok]] = df["open"].to_numpy(float)[ohlc_ok]
    C[pos[ohlc_ok]] = df["close"].to_numpy(float)[ohlc_ok]
    zero_vol = int((df["volume"] == 0).sum()) if "volume" in df.columns else None
    facts = {"rows": int(len(df)), "grid": n, "missing": int(n - ohlc_ok.sum()), "rows_without_full_ohlc": int(len(df) - df[["open", "high", "low", "close"]].notna().all(axis=1).sum()), "masked_zero_volume": masked_zero, "zero_volume_rows": zero_vol,
             "first": pd.Timestamp(int(sec[0]), unit="s", tz="UTC"), "last": pd.Timestamp(int(sec[-1]), unit="s", tz="UTC")}
    return Frame(sec[0] + width_s * np.arange(n), O, C, width_s), facts


def derive_15m(fr5: Frame) -> Frame:
    """15m bars from the 5m grid (the order's rule): bin = three consecutive 5m labels on a :00/:15/:30/:45 boundary; the 15m bar is
    present only if all three 5m bars are present; open = first 5m open, close = last 5m close."""
    if fr5.width != 300:
        raise ValueError("derive_15m needs a 5m frame")
    start_bin = fr5.sec[0] // 900
    end_bin = fr5.sec[-1] // 900
    nb = int(end_bin - start_bin) + 1
    off = int((fr5.sec[0] - start_bin * 900) // 300)
    O = np.full(nb * 3, np.nan)
    C = np.full(nb * 3, np.nan)
    pres = np.zeros(nb * 3, bool)
    O[off:off + fr5.n] = fr5.O
    C[off:off + fr5.n] = fr5.C
    pres[off:off + fr5.n] = fr5.present
    O3, C3, p3 = O.reshape(nb, 3), C.reshape(nb, 3), pres.reshape(nb, 3)
    ok = p3.all(axis=1)
    O15 = np.where(ok, O3[:, 0], np.nan)
    C15 = np.where(ok, C3[:, 2], np.nan)
    return Frame((start_bin + np.arange(nb)) * 900, O15, C15, 900)


# ----------------------------------------------------------------------------- z, eligibility, origins
def prepare(fr: Frame, w: int, kmax: int = KMAX) -> dict:
    """Returns r (NaN = masked), z (NaN = not eligible), `eligible`, target-window flags and the origin set; plus the counts of the
    reasons a bar is not an origin (z window, target window inside the frame, cutoff = beyond the truncated frame)."""
    n = fr.n
    r = np.full(n, np.nan)
    both = fr.present[1:] & fr.present[:-1]
    r[1:] = np.where(both, np.log(np.where(both, fr.C[1:], 1.0) / np.where(both, fr.C[:-1], 1.0)), np.nan)
    fin = np.isfinite(r)
    r0 = np.where(fin, r, 0.0)
    cs1 = np.concatenate([[0.0], np.cumsum(r0)])
    cs2 = np.concatenate([[0.0], np.cumsum(r0 * r0)])
    cf = np.concatenate([[0], np.cumsum(fin.astype(np.int64))])
    z = np.full(n, np.nan)
    eligible = np.zeros(n, dtype=bool)
    if n > w + 1:
        j = np.arange(w + 1, n)
        full = (cf[j] - cf[j - w]) == w  # returns r[j-w .. j-1] all unmasked
        S1 = cs1[j] - cs1[j - w]
        S2 = cs2[j] - cs2[j - w]
        var = np.maximum((S2 - S1 * S1 / w) / (w - 1), 0.0)
        sd = np.sqrt(var)
        ok = full & fin[j] & (sd > 0)
        z[j] = np.where(ok, r[j] / np.where(sd > 0, sd, 1.0), np.nan)
        eligible[j] = ok
    pc = np.concatenate([[0], np.cumsum(fr.present.astype(np.int64))])
    tgt_ok = np.zeros(n, dtype=bool)
    if n > kmax + 1:
        j = np.arange(0, n - kmax)
        tgt_ok[j] = (pc[j + kmax + 1] - pc[j + 1]) == kmax  # bars j+1 .. j+kmax present
    origin = eligible & tgt_ok
    reasons = {
        "bars_in_grid": int(n), "bars_present": int(fr.present.sum()), "bars_missing": int(n - fr.present.sum()),
        "eligible_origins": int(origin.sum()),
        "not_origin_z_window": int((~eligible).sum()),
        "not_origin_target_window_gap": int((eligible & ~tgt_ok & (np.arange(n) + kmax < n)).sum()),
        "not_origin_cutoff": int((eligible & ~tgt_ok & (np.arange(n) + kmax >= n)).sum()),
    }
    return {"w": w, "r": r, "z": z, "eligible": eligible, "tgt_ok": tgt_ok, "origin": origin, "origin_idx": np.flatnonzero(origin), "reasons": reasons}


def log_target(fr: Frame, j: np.ndarray, k: int, shift: int = 1) -> np.ndarray:
    """ln(C_(j+shift-1+k) / O_(j+shift)); shift 1 is the order's target (open of bar j+1 to close of bar j+k), shift 2 the one-bar-late variant."""
    return np.log(fr.C[j + shift - 1 + k]) - np.log(fr.O[j + shift])


def event_clock(prep: dict, thr: float = THR, gap: int = GAP, side: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Shared clock over the eligible event bars (|z| >= thr); `side` = -1 or +1 restricts the scan to that side (the per-side variant).
    Uses only information available at the event bar: it never looks at whether later bars exist."""
    z = prep["z"]
    cand = np.flatnonzero(prep["eligible"] & (np.abs(np.where(np.isfinite(z), z, 0.0)) >= thr))
    if side is not None:
        cand = cand[(z[cand] > 0) == (side == 1)]
    kept, sides, last = [], [], -10 ** 12
    for c in cand.tolist():
        if c >= last + gap:
            kept.append(c)
            sides.append(1 if z[c] > 0 else -1)
            last = c
    return np.array(kept, dtype=np.int64), np.array(sides, dtype=np.int64)


# ----------------------------------------------------------------------------- statistics
def cell_stats(e: np.ndarray, day: np.ndarray, raw: np.ndarray | None = None) -> dict:
    """Mean, day-clustered SE, naive SE, t, normal p-values, MDE, one-sided 95% upper bound. `day` = UTC day id of each entry bar."""
    n = len(e)
    if n < 2:
        nan = float("nan")
        return {"n": n, "mean": nan, "sd": nan, "se": nan, "se_naive": nan, "t": nan, "t_naive": nan, "p_one": nan, "p_two": nan, "mde": nan, "upper95": nan, "mean_raw": nan}
    mean = float(e.mean())
    sd = float(e.std(ddof=1))
    _, inv = np.unique(day, return_inverse=True)
    cl = np.bincount(inv, weights=e - mean)
    se = float(np.sqrt((cl ** 2).sum()) / n)
    se_naive = sd / np.sqrt(n)
    t = mean / se
    return {"n": n, "mean": mean, "sd": sd, "se": se, "se_naive": se_naive, "t": t, "t_naive": mean / se_naive if se_naive > 0 else float("nan"),
            "p_one": float(norm.sf(t)), "p_two": float(2 * norm.sf(abs(t))), "mde": MDE_MULTIPLIER * se, "upper95": mean + 1.645 * se,
            "mean_raw": float(raw.mean()) if raw is not None else float("nan")}


def classify(st: dict, holm_p: float, m: float = M) -> str:
    if holm_p < 0.05 and st["mean"] >= m:
        return "pass"
    if st["upper95"] < m and st["mde"] <= m:
        return "dead"
    return "inconclusive"


def holm_over(ps: np.ndarray) -> np.ndarray:
    """Plain Holm step-down adjustment (used for the reference's two-cell stand-in)."""
    ps = np.asarray(ps, float)
    m = len(ps)
    order = np.argsort(ps)
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * ps[i]))
        adj[i] = run
    return adj


def block_stability(e: np.ndarray, entry_sec: np.ndarray, t0_sec: int, end_sec: int, width_s: int = 300) -> dict:
    """The event stability statistic. Blocks of 90 calendar days from t0; block b scored only if t0 + 90(b+1) days <= end_sec, where
    end_sec = entry time of the last eligible origin + one bar. Blocks with fewer than 30 events are listed and excluded."""
    blk_s = BLOCK_DAYS * DAY_S
    n_full = int((end_sec - t0_sec) // blk_s)
    blk = ((entry_sec - t0_sec) // blk_s).astype(np.int64)
    rows, ts = [], []
    for b in range(n_full):
        eb = e[blk == b]
        nb = len(eb)
        tb = float(eb.mean() / (eb.std(ddof=1) / np.sqrt(nb))) if nb >= NMIN_BLOCK else float("nan")
        rows.append({"block": b, "start_sec": int(t0_sec + b * blk_s), "n": int(nb), "t_b": tb, "used": bool(nb >= NMIN_BLOCK)})
        if nb >= NMIN_BLOCK:
            ts.append(tb)
    partial_days = (end_sec - (t0_sec + n_full * blk_s)) / DAY_S
    if not ts:
        return {"T": float("nan"), "p": float("nan"), "B": 0, "B_full": n_full, "ts": ts, "blocks": rows, "partial_days": partial_days}
    T = float(np.sum(ts) / np.sqrt(len(ts)))
    return {"T": T, "p": float(norm.sf(T)), "B": len(ts), "B_full": n_full, "ts": ts, "blocks": rows, "partial_days": partial_days}


def primary_results(fr: Frame, prep: dict | None = None, thr: float = THR, k: int = PRIMARY_K, kept: np.ndarray | None = None, side: np.ndarray | None = None,
                    holm: str = "two") -> dict:
    """Both primary cells (down, up) on a frame: stats, classification, block statistic. `holm="two"` is the REFERENCE's stand-in (Holm over the
    two primary cells only); the production run uses the Holm over all 48 cells (`cell_table`). Mirrors the reference's `primary_results`."""
    w = W5 if fr.width == 300 else W15
    prep = prep if prep is not None else prepare(fr, w)
    if kept is None:
        kept, side = event_clock(prep, thr)
    orig = prep["origin_idx"]
    mu = float(log_target(fr, orig, k).mean())
    ok = prep["tgt_ok"][kept]
    kept2, side2 = kept[ok], side[ok]
    e_all = log_target(fr, kept2, k) - mu
    day = fr.sec[kept2 + 1] // DAY_S
    t0 = int(fr.sec[orig[0] + 1])
    end = int(fr.sec[orig[-1] + 1] + fr.width)
    out = {}
    for nm, which in (("down", -1), ("up", 1)):
        m = side2 == which
        st = cell_stats(e_all[m], day[m])
        out[nm] = {"stats": st, "block": block_stability(e_all[m], fr.sec[kept2[m] + 1], t0, end, fr.width), "idx": kept2[m], "excess": e_all[m]}
    adj = holm_over(np.array([out["down"]["stats"]["p_one"], out["up"]["stats"]["p_one"]]))
    for i, nm in enumerate(("down", "up")):
        out[nm]["holm"] = float(adj[i])
        out[nm]["class"] = classify(out[nm]["stats"], adj[i])
    out["mu"] = mu
    out["n_events"] = {"down": int((side2 == -1).sum()), "up": int((side2 == 1).sum())}
    out["n_kept_all"] = {"down": int((side == -1).sum()), "up": int((side == 1).sum())}
    return out


def dose_response(fr: Frame, prep: dict | None = None, k: int = PRIMARY_K) -> dict:
    """Item 7: repeat with |z| >= 4 and a FRESH shared clock; verdict per side: discard the |z| >= 3 result iff the |z| >= 4 mean excess is
    smaller AND the |z| >= 4 sample has at least 30 events; fewer than 30 events: "not evaluable" (flag for M2)."""
    w = W5 if fr.width == 300 else W15
    prep = prep if prep is not None else prepare(fr, w)
    r3 = primary_results(fr, prep, THR, k)
    r4 = primary_results(fr, prep, THR_DOSE, k)
    out = {}
    for nm in ("down", "up"):
        s3, s4 = r3[nm]["stats"], r4[nm]["stats"]
        if s3["mean"] <= 0:  # M2's ruling 4 (2026-10-27): the discard rule applies only to a cell with a POSITIVE |z| >= 3 mean excess
            verdict = "n/a: no positive effect"
        elif s4["n"] < NMIN_BLOCK:
            verdict = "not evaluable (fewer than 30 events at |z| >= 4): flag for M2"
        elif s4["mean"] < s3["mean"]:
            verdict = "discard the |z| >= 3 result"
        else:
            verdict = "keep"
        out[nm] = {"z3_mean": s3["mean"], "z3_n": s3["n"], "z4_mean": s4["mean"], "z4_n": s4["n"], "verdict": verdict}
    return out


def cell_table(fr: Frame, prep: dict, tf: str, thr: float = THR, mu_mask: np.ndarray | None = None) -> pd.DataFrame:
    """The 24 cells of one timeframe (k 1..12 x side), one common kept-event set. Columns: timeframe, k, side, n, mean_raw, mean_excess, se, se_naive, t,
    t_naive, mde, p_one, p_two, primary (bool). The family p used by Holm is p_value (one-sided for the primary cells, two-sided otherwise)."""
    kept, side = event_clock(prep, thr)
    ok = prep["tgt_ok"][kept]
    kept, side = kept[ok], side[ok]
    orig = prep["origin_idx"] if mu_mask is None else prep["origin_idx"][mu_mask]
    day = fr.sec[kept + 1] // DAY_S
    rows = []
    for k in range(1, KMAX + 1):
        mu = float(log_target(fr, orig, k).mean())
        R = log_target(fr, kept, k)
        for nm, which in (("down", -1), ("up", 1)):
            m = side == which
            st = cell_stats(R[m] - mu, day[m], raw=R[m])
            primary = tf == "5m" and k == PRIMARY_K
            rows.append({"timeframe": tf, "k": k, "side": nm, "n": st["n"], "mean_raw": st["mean_raw"], "mean_excess": st["mean"], "se": st["se"], "se_naive": st["se_naive"],
                         "t": st["t"], "t_naive": st["t_naive"], "mde": st["mde"], "p_one": st["p_one"], "p_two": st["p_two"], "primary": primary, "mu": mu,
                         "upper95": st["upper95"], "p_value": st["p_one"] if primary else st["p_two"]})
    return pd.DataFrame(rows)


def family_cells(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate the 5m and 15m tables (48 cells) and add Holm / Bonferroni over all 48 (multitest.annotate_family)."""
    frame = pd.concat(tables, ignore_index=True)
    if len(frame) != 48:
        raise ValueError(f"expected 48 cells, got {len(frame)}")
    frame = annotate_family(frame.copy())
    return frame


def utc_hour_counts(fr: Frame, kept: np.ndarray, side: np.ndarray) -> dict:
    hours = (fr.sec[kept] % DAY_S) // 3600
    return {nm: np.bincount(hours[side == which], minlength=24).tolist() for nm, which in (("down", -1), ("up", 1))}


def trade_rows(pair: str, cell: str, fr: Frame, idx: np.ndarray, excess: np.ndarray, k: int = PRIMARY_K) -> pd.DataFrame:
    """Trade list of one primary cell (after-tax layer later): the kept events with complete windows."""
    iso = lambda s: pd.Timestamp(int(s), unit="s", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    ent = fr.O[idx + 1]
    ext = fr.C[idx + k]
    return pd.DataFrame({
        "pair": pair, "cell": cell, "event_bar_time_utc": [iso(s) for s in fr.sec[idx]], "entry_time_utc": [iso(s) for s in fr.sec[idx + 1]],
        "exit_time_utc": [iso(s + fr.width) for s in fr.sec[idx + k]], "entry_price": ent, "exit_price": ext, "gross_log_return": np.log(ext / ent), "excess": excess})


# ----------------------------------------------------------------------------- acceptance
def load_reference():
    path = Path(__file__).resolve().parents[2] / "docs" / "work-orders" / "1.7-task3_reference.py"
    spec = importlib.util.spec_from_file_location("task3_reference", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def frame_from_returns(ref, r: np.ndarray) -> Frame:
    C, O = ref.closes_opens(r)
    return Frame(EPOCH_2017_08_17 + 300 * np.arange(len(r)), O, C, 300)


def acceptance(ref, npaths_null: int, npaths_edge: int, seed: int = 1707, null_kinds=("gauss", "t4sv", "t3sv"), edge_deltas=(0.0010, 0.0035, 0.0050)) -> dict:
    """The acceptance rows of Work Order 1.7 section 4 through PRODUCTION code (reference generators and injection only). Returns the rates."""
    rng = np.random.default_rng(seed)
    n = ref.NDAYS * ref.BAR_DAY
    out = {"null": {}, "edge": {}}
    for kind in null_kinds if npaths_null else ():
        c = {"down": [0, 0, 0], "up": [0, 0, 0]}
        for _ in range(npaths_null):
            res = primary_results(frame_from_returns(ref, ref.make_returns(n, rng, kind)))
            for nm in ("down", "up"):
                c[nm][0] += res[nm]["stats"]["p_one"] < 0.05
                c[nm][1] += res[nm]["block"]["p"] < 0.05
                c[nm][2] += res[nm]["class"] == "dead"
        out["null"][kind] = {nm: {"false_pass": c[nm][0] / npaths_null, "stab": c[nm][1] / npaths_null, "dead": c[nm][2] / npaths_null} for nm in c}
    for delta in edge_deltas if npaths_edge else ():
        cnt = {"sig": 0, "stab": 0, "pass": 0, "dead": 0, "inconclusive": 0}
        for _ in range(npaths_edge):
            r = ref.make_returns(n, rng, "t4sv")
            kept, side = event_clock(prepare(frame_from_returns(ref, r), W5))
            res = primary_results(frame_from_returns(ref, ref.inject(r, kept, side, -1, delta)))["down"]
            cnt["sig"] += res["stats"]["p_one"] < 0.05
            cnt["stab"] += res["block"]["p"] < 0.05
            cnt[res["class"]] += 1
        out["edge"][delta] = {k_: v / npaths_edge for k_, v in cnt.items()}
    return out


# ============================================================================= self-test
def _gapfree(ref, seed=7, ndays=120, kind="t4sv") -> tuple[np.ndarray, Frame]:
    r = ref.make_returns(ndays * 288, np.random.default_rng(seed), kind)
    return r, frame_from_returns(ref, r)


def _self_test(reduced: bool = True) -> None:
    ref = load_reference()
    t_start = time.time()
    # ---- 1. exact reproduction of the reference on make_returns(2935*288, default_rng(2026), "t4sv")
    r = ref.make_returns(ref.NDAYS * 288, np.random.default_rng(2026), "t4sv")
    fr = frame_from_returns(ref, r)
    prep = prepare(fr, W5)
    kept, side = event_clock(prep, THR)
    rk, rs = ref.event_clock(r)
    assert np.array_equal(kept, rk) and np.array_equal(side, rs), "kept events differ from the reference"
    res = primary_results(fr, prep)
    rr = ref.primary_results(r)
    diffs = {}
    for nm in ("down", "up"):
        a, b = res[nm]["stats"], rr[nm]["stats"]
        assert a["n"] == b["n"] and res["n_events"][nm] == rr["n_events"][nm]
        for key, (x, y) in {"mean": (a["mean"], b["mean"]), "se": (a["se"], b["se"]), "t": (a["t"], b["t"]), "T": (res[nm]["block"]["T"], rr[nm]["block"]["T"]),
                            "p_one": (a["p_one"], b["p_one"]), "p_stab": (res[nm]["block"]["p"], rr[nm]["block"]["p"])}.items():
            rel = abs(x - y) / max(abs(y), 1e-300)
            diffs[f"{nm}.{key}"] = rel
            assert rel < 1e-8, f"{nm}.{key}: production {x!r} vs reference {y!r} (relative {rel:.2e})"
        assert res[nm]["class"] == rr[nm]["class"] and res[nm]["block"]["B"] == rr[nm]["block"]["B"] and len(res[nm]["block"]["ts"]) == len(rr[nm]["block"]["ts"])
    assert abs(res["mu"] - rr["mu"]) < 1e-10
    assert (res["n_events"]["down"], res["n_events"]["up"]) == (5244, 5506), "the order quotes kept events (down, up): 5244 5506"
    assert abs(res["mu"] - (-0.0000018532)) < 5e-11 and abs(res["down"]["stats"]["mean"] - (-0.0001271005)) < 5e-11 and abs(res["up"]["stats"]["t"] - 0.654523) < 5e-7
    dr = dose_response(fr, prep)
    drr = ref.dose_response(r)
    for nm in ("down", "up"):
        assert dr[nm]["z3_n"] == drr[3.0][nm]["stats"]["n"] and dr[nm]["z4_n"] == drr[4.0][nm]["stats"]["n"]
        assert abs(dr[nm]["z4_mean"] - drr[4.0][nm]["stats"]["mean"]) < 1e-12 and abs(dr[nm]["z3_mean"] - drr[3.0][nm]["stats"]["mean"]) < 1e-12
    assert (dr["down"]["z4_n"], dr["up"]["z4_n"]) == (2427, 2624)
    worst = max(diffs, key=diffs.get)
    print(f"  exact reproduction (seed 2026, t4sv, {len(r)} bars): kept events identical (down {res['n_events']['down']}, up {res['n_events']['up']}), mu_6 {res['mu']:.10f}; "
          f"largest relative difference {diffs[worst]:.1e} ({worst}); every difference < 1e-8; dose-response n at |z|>=4: {dr['down']['z4_n']} / {dr['up']['z4_n']}")
    # brute-force clock
    r2, fr2 = _gapfree(ref, 5, 105, "t4sv")
    a = event_clock(prepare(fr2, W5))
    b = ref.event_clock_bruteforce(r2)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]) and np.diff(a[0]).min() >= GAP
    print(f"  vectorised eligibility and clock equal the reference's brute-force loop ({len(a[0])} kept events, minimum spacing {np.diff(a[0]).min()} >= 13)")

    # ---- 2. gaps: masks never filled
    r3, fr3 = _gapfree(ref, 11, 40, "gauss")
    base = prepare(fr3, W5)
    j_miss = 700
    O = fr3.O.copy(); C = fr3.C.copy()
    O[j_miss] = np.nan; C[j_miss] = np.nan
    frg = Frame(fr3.sec, O, C, 300)
    pg = prepare(frg, W5)
    assert np.isnan(pg["r"][j_miss]) and np.isnan(pg["r"][j_miss + 1]) and np.isfinite(pg["r"][j_miss + 2]), "the return after a missing bar is masked as well"
    assert not pg["eligible"][j_miss] and not pg["eligible"][j_miss + 1], "the event bar itself / the bar after a gap cannot be eligible"
    assert not pg["eligible"][j_miss:j_miss + 2 + W5].any(), "no bar whose z window contains a masked return is eligible (bars j_miss .. j_miss+289)"
    assert pg["eligible"][j_miss + 2 + W5], "eligibility returns right after the masked returns leave the window"
    assert not pg["tgt_ok"][j_miss - 12:j_miss].any() and pg["tgt_ok"][j_miss - 13] and not pg["origin"][j_miss - 12:j_miss].any(), "origins whose target window j+1..j+12 contains the gap are excluded"
    assert pg["reasons"]["not_origin_target_window_gap"] >= 12 and pg["reasons"]["bars_missing"] == 1
    # an event at a bar before a gap stays on the clock but is dropped from the statistics
    z = pg["z"]
    k_b, s_b = event_clock(pg)
    inc = [j for j in k_b if not pg["tgt_ok"][j]]
    r_big = r3.copy()
    r_big[650] = 0.2  # a huge up-move at bar 650 (eligible), target window 651..662 intact
    r_big[690] = 0.2  # event at 690: target window 691..702 contains the missing bar 700
    frb = frame_from_returns(ref, r_big)
    O = frb.O.copy(); C = frb.C.copy(); O[700] = np.nan; C[700] = np.nan
    pb = prepare(Frame(frb.sec, O, C, 300), W5)
    kb, sb = event_clock(pb)
    assert 650 in kb and 690 in kb and pb["tgt_ok"][650] and not pb["tgt_ok"][690], "an event with a gap in its window is still a kept clock event"
    kept_stats = primary_results(Frame(frb.sec, O, C, 300), pb)
    assert kept_stats["n_kept_all"]["up"] == int((sb == 1).sum()) and kept_stats["n_events"]["up"] == int((sb == 1).sum()) - 1, "dropped from the statistics and counted"
    # 15m derivation: a 15m bin with a missing 5m bar is missing; a missing 5m bar elsewhere does not touch other bins
    f15 = derive_15m(Frame(frb.sec, O, C, 300))
    b700 = (frb.sec[700] // 900 - f15.sec[0] // 900)
    assert not f15.present[b700] and f15.present.sum() == f15.n - 1 and f15.n == len(frb.sec) // 3
    f15c = derive_15m(frb)
    assert abs(f15c.O[5] - frb.O[15]) == 0 and abs(f15c.C[5] - frb.C[17]) == 0 and f15c.sec[0] % 900 == 0, "15m open is the first 5m open, close the last 5m close"
    print("  gaps: the return after a missing bar is masked; z windows with a masked return are not eligible (288 bars after the gap); origins whose j+1..j+12 contains the gap are excluded; "
          "a kept event with an incomplete window stays on the clock and is counted as dropped; a 15m bin with a missing 5m bar is missing")

    # ---- 2b. M2's ruling 2: a zero-volume bar behaves EXACTLY like a missing bar (masked primary)
    ndz = 1500
    rz = ref.make_returns(ndz, np.random.default_rng(9), "t4sv")
    Cz, Oz = ref.closes_opens(rz)
    idxz = pd.date_range("2025-03-01", periods=ndz, freq="5min", tz="UTC")
    dfz = pd.DataFrame({"open": Oz * 100, "high": np.maximum(Oz, Cz) * 100.01, "low": np.minimum(Oz, Cz) * 99.99, "close": Cz * 100, "volume": 1.0}, index=idxz)
    zbar = 700
    dfz_zero = dfz.copy()
    dfz_zero.iloc[zbar, dfz_zero.columns.get_loc("volume")] = 0.0
    fa, fact_a = frame_from_df(dfz_zero, 300, mask_zero_volume=True)
    fb, _ = frame_from_df(dfz.drop(index=idxz[zbar]), 300)
    fc, fact_c = frame_from_df(dfz_zero, 300)
    assert np.array_equal(fa.present, fb.present) and np.array_equal(np.nan_to_num(fa.O, nan=-1), np.nan_to_num(fb.O, nan=-1)) and np.array_equal(np.nan_to_num(fa.C, nan=-1), np.nan_to_num(fb.C, nan=-1))
    pa, pb = prepare(fa, W5), prepare(fb, W5)
    for key in ("r", "z"):
        assert np.array_equal(pa[key], pb[key], equal_nan=True), key
    for key in ("eligible", "tgt_ok", "origin"):
        assert np.array_equal(pa[key], pb[key]), key
    assert np.isnan(pa["r"][zbar]) and np.isnan(pa["r"][zbar + 1]) and np.isfinite(pa["r"][zbar + 2]), "its own return and the next bar's return are masked"
    assert not pa["eligible"][zbar:zbar + 2 + W5].any() and pa["eligible"][zbar + 2 + W5], "every z window containing it is invalid (the 288 following bars)"
    assert not pa["tgt_ok"][zbar - 12:zbar].any() and not pa["origin"][zbar - 12:zbar].any(), "a target window containing it makes the origin or event incomplete"
    a15, b15 = derive_15m(fa), derive_15m(fb)
    assert np.array_equal(a15.present, b15.present) and not a15.present[(fa.sec[zbar] - a15.sec[0]) // 900], "a 15m bin containing it is missing"
    assert fc.present[zbar] and fact_a["masked_zero_volume"] == 1 and fact_c["masked_zero_volume"] == 0, "the literal reading (control) keeps it present"
    print("  zero-volume bar (primary, masked): identical to a missing bar in the grid, returns, z windows (288 bars), target windows and the 15m bin; the literal reading keeps it present")

    # ---- 3. cutoff: truncated frame, sanity bars and last origins
    n_total = 2937 * 288 + 4 * 288
    sec = EPOCH_2017_08_17 + 4 * 3600 + 300 * np.arange(2937 * 288 - 48)
    frc = Frame(sec, np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.003, len(sec)))), np.exp(np.cumsum(np.random.default_rng(4).normal(0, 0.003, len(sec)))), 300)
    assert frc.n == 845808, "gap-free 5m discovery frame from 2017-08-17 04:00 to 2025-08-31 23:55 has 845,808 bars"
    pc = prepare(frc, W5)
    assert frc.label(pc["origin_idx"][0]) == pd.Timestamp("2017-08-18 04:05", tz="UTC") and frc.label(pc["origin_idx"][-1]) == pd.Timestamp("2025-08-31 22:55", tz="UTC")
    assert pc["reasons"]["not_origin_cutoff"] == 12 and pc["reasons"]["not_origin_z_window"] == 289 and frc.label(frc.n - 1) == pd.Timestamp("2025-08-31 23:55", tz="UTC")
    f15 = derive_15m(frc)
    p15 = prepare(f15, W15)
    assert f15.label(p15["origin_idx"][0]) == pd.Timestamp("2017-08-18 04:15", tz="UTC") and f15.label(p15["origin_idx"][-1]) == pd.Timestamp("2025-08-31 20:45", tz="UTC")
    assert f15.label(f15.n - 1) == pd.Timestamp("2025-08-31 23:45", tz="UTC")
    kk, ss = event_clock(pc)
    assert prep is not None and (frc.sec[kk] <= frc.sec[-1]).all()
    ok = pc["tgt_ok"][kk]
    assert (kk[ok] + KMAX < frc.n).all() and ((~ok).sum() == 0 or (kk[~ok] + KMAX >= frc.n).all()), "events near the end are dropped for the cutoff only"
    # truncation helper: no post-cutoff row can enter
    from cutoff import CUTOFF, truncate_at_cutoff

    idx = pd.date_range("2025-08-31 22:00", "2025-09-01 01:00", freq="5min", tz="UTC")
    df_ = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    tr = truncate_at_cutoff(df_, CUTOFF)
    fr_tr, facts = frame_from_df(tr, 300)
    assert tr.index.max() == pd.Timestamp("2025-08-31 23:55", tz="UTC") and (tr.index > CUTOFF).sum() == 0 and facts["last"] == tr.index.max()
    print(f"  cutoff: gap-free discovery frame has {frc.n} 5m bars; first eligible 5m origin {frc.label(pc['origin_idx'][0])} (15m {f15.label(p15['origin_idx'][0])}), "
          f"last 5m origin {frc.label(pc['origin_idx'][-1])} (15m {f15.label(p15['origin_idx'][-1])}); 289 bars fail the z window, 12 fail the cutoff; truncation leaves 0 post-cutoff rows")

    # ---- 4. the clock
    rc, frk = _gapfree(ref, 21, 150, "t3sv")
    pk = prepare(frk, W5)
    k3, s3 = event_clock(pk, 3.0)
    k4, s4 = event_clock(pk, 4.0)
    assert np.diff(k3).min() >= GAP and np.diff(k4).min() >= GAP and len(k3) > 20
    assert len(set(k4.tolist()) - set(k3.tolist())) > 0, "the |z| >= 4 clock is a fresh scan, not a subset of the |z| >= 3 kept events"
    kd, sd_ = event_clock(pk, 3.0, side=-1)
    ku, su = event_clock(pk, 3.0, side=1)
    assert (sd_ == -1).all() and (su == 1).all() and len(kd) + len(ku) >= len(k3), "one clock per side (labelled variant) keeps at least as many events"
    # shared clock: a down event suppresses an up event within 12 bars
    rs_ = ref.make_returns(30 * 288, np.random.default_rng(1), "gauss")
    rs_[3000] = -0.05
    rs_[3005] = 0.05
    rs_[3013] = 0.05
    kk2, ss2 = event_clock(prepare(frame_from_returns(ref, rs_), W5))
    assert 3000 in kk2 and 3005 not in kk2 and 3013 in kk2, "both sides share the clock: spacing is 13 bars"
    print(f"  clock: shared by both sides, spacing >= 13 bars (minimum {np.diff(k3).min()}), the |z| >= 4 clock is a fresh scan ({len(set(k4.tolist()) - set(k3.tolist()))} events not in the |z| >= 3 set), "
          "the per-side clock keeps more events; a down event at j suppresses an up event at j+5 and not one at j+13")

    # ---- 5. cell table, Holm over 48, classification and block statistic
    rt, frt = _gapfree(ref, 31, 300, "t4sv")
    f15t = derive_15m(frt)
    tabs = [cell_table(frt, prepare(frt, W5), "5m"), cell_table(f15t, prepare(f15t, W15), "15m")]
    fam = family_cells(tabs)
    assert len(fam) == 48 and fam["primary"].sum() == 2 and set(fam.loc[fam["primary"], "k"]) == {6} and (fam["family_size"] == 48).all()
    pr = fam[fam["primary"]]
    assert np.allclose(pr["p_value"], pr["p_one"]) and np.allclose(fam.loc[~fam["primary"], "p_value"], fam.loc[~fam["primary"], "p_two"])
    assert (fam["p_holm"] >= fam["p_value"] - 1e-15).all() and (fam["p_bonferroni"] >= fam["p_holm"] - 1e-12).all()
    prim = primary_results(frt)
    cell = fam[(fam["timeframe"] == "5m") & (fam["k"] == 6) & (fam["side"] == "down")].iloc[0]
    assert abs(cell["mean_excess"] - prim["down"]["stats"]["mean"]) < 1e-14 and cell["n"] == prim["down"]["stats"]["n"] and abs(cell["se"] - prim["down"]["stats"]["se"]) < 1e-14
    assert classify({"mean": 0.004, "upper95": 0.01, "mde": 0.01}, 0.01) == "pass" and classify({"mean": 0.0001, "upper95": 0.002, "mde": 0.003}, 0.5) == "dead"
    assert classify({"mean": 0.004, "upper95": 0.01, "mde": 0.01}, 0.2) == "inconclusive" and classify({"mean": 0.0001, "upper95": 0.002, "mde": 0.004}, 0.5) == "inconclusive"
    blk = block_stability(np.ones(100) * 0.001, EPOCH_2017_08_17 + np.arange(100) * 3600, EPOCH_2017_08_17, EPOCH_2017_08_17 + 100 * 3600)
    assert blk["B_full"] == 0 and np.isnan(blk["T"])
    print(f"  cells: 48 per pair (2 primary, one-sided; 46 two-sided), Holm and Bonferroni over 48, the 5m k=6 cell equals primary_results; classification rules and the empty-block case behave as ordered")

    # ---- 6. acceptance rows (reduced here; --full runs 200 / 100 paths with the 7% rule of answer-to-message-19 section 3a)
    n_null, n_edge = (60, 30) if reduced else (200, 100)
    t0 = time.time()
    acc = acceptance(ref, n_null, n_edge)
    rows = []
    for kind, d in acc["null"].items():
        for nm in ("down", "up"):
            band = 0.10 if reduced else 0.07
            assert d[nm]["false_pass"] <= band and d[nm]["stab"] <= band + (0.0 if not reduced else 0.0), f"null {kind} {nm}: false-pass {d[nm]['false_pass']:.3f} stability {d[nm]['stab']:.3f} above {band}"
            assert d[nm]["dead"] >= 0.99, f"null {kind} {nm}: not every null path classifies dead ({d[nm]['dead']:.3f})"
        rows.append(f"{kind}: p<.05 {d['down']['false_pass']:.1%}/{d['up']['false_pass']:.1%}, p_stab<.05 {d['down']['stab']:.1%}/{d['up']['stab']:.1%}")
    e50, e10, e35 = acc["edge"][0.0050], acc["edge"][0.0010], acc["edge"][0.0035]
    need = 0.90 if reduced else 0.95
    assert e50["pass"] >= need and e50["stab"] >= need, f"+0.50% edge: pass {e50['pass']:.2f} stability {e50['stab']:.2f}"
    assert e10["sig"] >= need and e10["dead"] >= need, f"+0.10% edge: significant {e10['sig']:.2f} dead {e10['dead']:.2f}"
    print(f"  acceptance ({n_null} null / {n_edge} edge paths per row, {time.time() - t0:.0f}s; down/up): " + "; ".join(rows) + f"; edge +0.50%: pass {e50['pass']:.0%}, stability {e50['stab']:.0%}; "
          f"+0.10%: significant {e10['sig']:.0%}, dead {e10['dead']:.0%}; +0.35% (information): pass {e35['pass']:.0%}, dead {e35['dead']:.0%}, inconclusive {e35['inconclusive']:.0%}")
    print(f"Self-test passed in {time.time() - t_start:.0f}s: formula_t3.py reproduces the Work Order 1.7 reference exactly and implements masking, the clock, the cells, the classification and the event stability as ordered.")


def _confirm(npaths: int = 1000, seed: int = 99) -> bool:
    """Confirmation run of the null rows (answer-to-message-19 section 3a): `npaths` fresh null paths per kind; PASS iff every rate of one-sided p < 0.05 and of
    p_stab < 0.05 is at most 7% for both primary cells."""
    ref = load_reference()
    ok = True
    for kind, s in zip(("gauss", "t4sv", "t3sv"), (seed, seed + 1, seed + 2)):
        t0 = time.time()
        d = acceptance(ref, npaths, 0, seed=s, null_kinds=(kind,))["null"][kind]
        worst = max(max(d[nm]["false_pass"], d[nm]["stab"]) for nm in d)
        good = worst <= 0.07
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  confirm {kind:<5} {npaths} paths: false-pass down {d['down']['false_pass']:.3f} up {d['up']['false_pass']:.3f}; p_stab down {d['down']['stab']:.3f} up {d['up']['stab']:.3f} "
              f"(band <= 0.07)   ({time.time() - t0:.0f}s)", flush=True)
    print("TASK 3 NULL CONFIRMATION PASSED" if ok else "TASK 3 NULL CONFIRMATION FAILED")
    return ok


def _full() -> bool:
    """The real acceptance run: 200 null paths per kind and 100 edge paths per delta, bands of Work Order 1.7 section 4 with the 7% rule
    (a null row passes at <= 7% at 200 paths OR <= 7% in a confirmation of >= 1000 paths, run automatically for a failing row)."""
    ref = load_reference()
    t0 = time.time()
    acc = acceptance(ref, 200, 100)
    ok = True
    print("Task 3 acceptance (FULL): 200 null paths per kind, 100 edge paths per delta")
    for kind, d in acc["null"].items():
        worst = max(max(d[nm]["false_pass"], d[nm]["stab"]) for nm in d)
        note = ""
        good = worst <= 0.07
        if not good:
            c = acceptance(ref, 1000, 0, seed=99, null_kinds=(kind,))["null"][kind]
            wc = max(max(c[nm]["false_pass"], c[nm]["stab"]) for nm in c)
            good = wc <= 0.07
            note = f"   [200-path worst rate {worst:.3f} above the band; 1000-path confirmation worst rate {wc:.3f} -> {'accepted' if good else 'REJECTED'}]"
        ok &= good
        dead = min(d[nm]["dead"] for nm in d)
        ok &= dead >= 0.99
        print(f"  {'PASS' if good and dead >= 0.99 else 'FAIL'}  null {kind:<5} false-pass down {d['down']['false_pass']:.3f} up {d['up']['false_pass']:.3f}; p_stab down {d['down']['stab']:.3f} up {d['up']['stab']:.3f}; "
              f"classified dead {dead:.3f}{note}", flush=True)
    e = acc["edge"]
    for delta, need_keys in ((0.0050, ("pass", "stab")), (0.0010, ("sig", "dead"))):
        good = all(e[delta][k_] >= 0.95 for k_ in need_keys)
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  edge +{delta * 100:.2f}% (t4sv): significant {e[delta]['sig']:.2f} stability {e[delta]['stab']:.2f} pass {e[delta]['pass']:.2f} dead {e[delta]['dead']:.2f} inconclusive {e[delta]['inconclusive']:.2f}")
    d35 = e[0.0035]
    print(f"  info  edge +0.35% (t4sv): pass {d35['pass']:.2f} dead {d35['dead']:.2f} inconclusive {d35['inconclusive']:.2f} (reference: 0.10 / 0.35 / 0.55)")
    print(f"total {time.time() - t0:.0f}s")
    print("ALL TASK 3 ACCEPTANCE TESTS PASSED" if ok else "SOME TASK 3 ACCEPTANCE TESTS FAILED")
    return ok


if __name__ == "__main__":
    if "--confirm" in sys.argv:
        sys.exit(0 if _confirm() else 1)
    if "--full" in sys.argv:
        sys.exit(0 if _full() else 1)
    _self_test(reduced=True)
