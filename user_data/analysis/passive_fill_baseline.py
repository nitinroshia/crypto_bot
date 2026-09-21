"""
HISTORY -- delivered in work order 1.0 (Task 2) and kept as a record. Its follow-ups and the whole
maker-fill line of work were retired in work order 1.2 (the cost model is now taker execution at the
next bar's open; see costs.py). The code still runs and its self-test still passes; it no longer
depends on costs.py. Results: results/runs/*_passive_fill_baseline.*

Task 2 (work order #1): passive-fill negative control.

Purpose: before any strategy is allowed to rest limit orders, measure what a
completely SIGNAL-FREE resting order earns under our fill rule. If a
no-information baseline "earns" money here, the fill simulator is too
generous and every later result that uses it is suspect. An honest baseline
is ~zero or negative (adverse selection: you get filled mostly when price is
moving through your level, against you).

THE BASELINE
    Every 60 minutes on the hour (UTC), rest a BUY at
    last_close * (1 - d), rounded DOWN to the tick (so it is never a more
    aggressive price than intended), for 15 minutes. d in {0.05%, 0.10%, 0.20%}.
    Mirror for SELLS: last_close * (1 + d), rounded UP.
    Then record what happens: fill rate, and the mean forward return from the
    LIMIT PRICE at +15 / +30 / +60 minutes after the fill, BEFORE fees.

EVERY TIMING CONVENTION (nothing is left to interpretation; each choice that
could move the answer is either taken literally from the work order or run
BOTH ways and labeled)
    * Bars are left-labeled (label = open time) and usable only after they
      close. The order is decided at time T (top of the hour) using
      last_close = close of the bar labeled T-1min (closed exactly at T).
      If that bar is missing from the file the origin is SKIPPED and counted.
    * The order starts resting at T, i.e. during bar T. "It never fills in the
      bar it was placed": bar T is NEVER eligible. Eligible bars are T+1 ...
      T+L.
    * L is the one ambiguity in "for 15 minutes" (an order live [T, T+15min)
      touches bars T..T+14, i.e. 14 eligible bars after excluding T; "15 minutes
      after the placement bar" gives 15). BOTH are run and labeled:
          A_14bars = the strict reading, headline
          B_15bars = sensitivity
    * Fill rule (conservative): a resting buy fills only if an eligible bar's
      LOW is at least one tick BELOW the limit (low <= limit - tick); a sell
      only if a bar's HIGH >= limit + tick. Touching the limit exactly is not a
      fill. The fill price is the limit price (no price improvement). A bar that is
      missing from the file (no trades) cannot fill anything.
    * Fill time = the CLOSE of the fill bar (that is when we could first know).
      "+h minutes after the fill" therefore uses the close of the bar labeled
      (fill_bar + h minutes). If that bar is missing the fill is dropped from
      that horizon (counted).
    * Forward "price change" = close_{fill+h} / limit - 1 (both sides). The
      headline number is pnl_for_side: +price_change for buys,
      -price_change for sells (a seller profits when price falls).
    * TICK SIZE is never assumed: it comes from --tick-size or from
      symbol_filters.json (written by fetch_klines.py from Binance's exchangeInfo)
      and is cross-checked against the price grid actually present in the data;
      a mismatch aborts the run.
    * Post-break only: origins before --start (default 2026-01-30 00:00 UTC, the
      first full day after the 2026-01-29 structural break) are excluded.

STATISTICS
    Mean pnl_for_side with a Newey-West (HAC, 2 lags -- adjacent hourly
    origins have overlapping forward windows) t-stat and 95% CI. Family =
    3 d-values x 2 sides x 3 horizons = 18 per variant; Bonferroni AND Holm
    adjusted p are both reported. Verdict labels are mechanical, from the
    Holm p: "consistent with zero", "significantly > 0 (simulator may be too
    generous)", "significantly < 0 (adverse selection)". Hurdles from the work
    order (0.05% maker candidate, 0.20% taker viable) are printed for scale.

Usage (from the repo root):
    python3 user_data/analysis/fetch_klines.py --exchange-info-only   # once, writes tick size
    python3 user_data/analysis/passive_fill_baseline.py
    python3 user_data/analysis/passive_fill_baseline.py --self-test   # offline checks
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from numpy.lib.stride_tricks import sliding_window_view

# Historical thresholds and fees of work orders 1.0/1.1, kept local so this record does not depend on the
# retired cost model (costs.py now carries only the work order 1.2 taker model).
_HIST_HURDLE_MAKER_CANDIDATE = 0.0005
_HIST_HURDLE_VIABLE_AS_TAKER = 0.0020
_HIST_FEES = {"maker": 0.0, "taker": 0.001,
              "source": "account fee page 2026-09-19 (the maker 0% is a promotion and is ignored for planning, work order 1.2)"}
from multitest import bonferroni_adjust, holm_adjust

DEFAULT_D = (0.0005, 0.0010, 0.0020)
HORIZONS = (15, 30, 60)
VARIANTS = {"A_14bars": 14, "B_15bars": 15}
ORIGIN_EVERY_MIN = 60
DEFAULT_START = "2026-01-30"


# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------
def load_1m(path: Path) -> pd.DataFrame:
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df.set_index("date").sort_index()


def build_grid(df: pd.DataFrame) -> dict:
    """Reindex onto the full 1-minute grid. Missing rows become NaN -- they are
    never forward-filled (a missing minute has no trades and cannot fill anything)."""
    idx = pd.date_range(df.index.min().ceil("1min"), df.index.max(), freq="1min", tz="UTC")
    g = df.reindex(idx)
    return {"index": idx, **{c: g[c].to_numpy(dtype=float) for c in ("open", "high", "low", "close", "volume")}}


def infer_tick(prices: np.ndarray, candidates=(1.0, 0.1, 0.01, 0.001, 0.0001, 0.00001)) -> float | None:
    """Largest candidate step such that every observed price is a multiple of it."""
    p = prices[np.isfinite(prices)]
    if len(p) > 200_000:
        p = p[:: len(p) // 200_000]
    for c in candidates:
        q = p / c
        if np.all(np.abs(q - np.round(q)) < 1e-6):
            return c
    return None


def resolve_tick(explicit: float | None, filters_path: Path | None, symbol: str, grid: dict) -> tuple[float, str]:
    source = None
    tick = explicit
    if tick is not None:
        source = "--tick-size"
    elif filters_path is not None and filters_path.exists():
        info = json.loads(filters_path.read_text())["symbols"].get(symbol)
        if info and info.get("tickSize"):
            tick, source = float(info["tickSize"]), f"{filters_path} ({symbol} PRICE_FILTER.tickSize)"
    if tick is None:
        raise SystemExit(
            "Tick size is not known and is deliberately NOT assumed. Run\n"
            "    python3 user_data/analysis/fetch_klines.py --exchange-info-only\n"
            f"(writes symbol_filters.json), or pass --tick-size. Looked for: {filters_path}"
        )
    seen = np.concatenate([grid["close"], grid["low"], grid["high"]])
    inferred = infer_tick(seen)
    if inferred is None or not math.isclose(inferred, tick, rel_tol=1e-9):
        raise SystemExit(
            f"Tick size mismatch: exchange/CLI says {tick} (from {source}) but the price grid in the data "
            f"implies {inferred}. Refusing to simulate fills on the wrong tick."
        )
    return tick, source


# --------------------------------------------------------------------------------------
# Simulator
# --------------------------------------------------------------------------------------
def simulate(grid: dict, *, side: str, d: float, tick: float, last_eligible_offset: int,
             start: pd.Timestamp | None = None, horizons=HORIZONS) -> tuple[pd.DataFrame, dict]:
    """One row per origin. See the module docstring for every convention."""
    assert side in ("buy", "sell")
    idx, n = grid["index"], len(grid["index"])
    close, low, high = grid["close"], grid["low"], grid["high"]
    L = last_eligible_offset

    minute_of_day = idx.hour.to_numpy() * 60 + idx.minute.to_numpy()
    cand = np.flatnonzero(minute_of_day % ORIGIN_EVERY_MIN == 0)
    counts = {"origins_on_grid": int(len(cand))}
    if start is not None:
        keep = idx[cand] >= start
        counts["origins_before_start_excluded"] = int((~keep).sum())
        cand = cand[keep]
    ok_pos = (cand >= 1) & (cand + L < n)  # need bar T-1 and the whole eligible window inside the data
    counts["origins_without_full_window_or_prev_bar"] = int((~ok_pos).sum())
    cand = cand[ok_pos]
    ref = close[cand - 1]
    have_ref = np.isfinite(ref)
    counts["origins_skipped_missing_reference_bar"] = int((~have_ref).sum())
    cand, ref = cand[have_ref], ref[have_ref]

    if side == "buy":
        limit_ticks = np.floor(ref * (1 - d) / tick + 1e-9)   # round DOWN: never more aggressive than intended
    else:
        limit_ticks = np.ceil(ref * (1 + d) / tick - 1e-9)    # round UP
    limit_price = limit_ticks * tick

    if side == "buy":
        series = np.round(low / tick)
        windows = sliding_window_view(series, L)[cand + 1]                   # bars T+1 .. T+L
        hit = windows <= (limit_ticks - 1)[:, None]                          # >= 1 tick through the limit
    else:
        series = np.round(high / tick)
        windows = sliding_window_view(series, L)[cand + 1]
        hit = windows >= (limit_ticks + 1)[:, None]
    hit &= np.isfinite(windows)                                              # missing bars never fill
    filled = hit.any(axis=1)
    first = hit.argmax(axis=1)
    fill_pos = cand + 1 + first

    out = pd.DataFrame(
        {
            "origin_time": idx[cand], "side": side, "d": d, "ref_close": ref, "limit_price": limit_price,
            "filled": filled, "bars_after_placement_to_fill": np.where(filled, first + 1, -1),
            "fill_bar_time": np.where(filled, idx[np.minimum(fill_pos, n - 1)], pd.NaT),
        }
    )
    sign = 1.0 if side == "buy" else -1.0
    for h in horizons:
        tgt = fill_pos + h
        ok = filled & (tgt < n)
        px = np.full(len(cand), np.nan)
        px[ok] = close[tgt[ok]]
        change = px / limit_price - 1
        out[f"price_change_{h}m"] = change
        out[f"pnl_for_side_{h}m"] = sign * change
    counts["origins_simulated"] = int(len(out))
    return out, counts


def mean_stats(y: np.ndarray) -> dict:
    y = np.asarray(y, dtype=float)
    y = y[np.isfinite(y)]
    n = len(y)
    if n < 30:
        return {"n_used": n, "status": "INSUFFICIENT_DATA"}
    fit = sm.OLS(y, np.ones(n)).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
    mean, se = float(fit.params[0]), float(fit.bse[0])
    return {"n_used": n, "mean": mean, "median": float(np.median(y)), "std": float(y.std(ddof=1)),
            "t_hac": float(fit.tvalues[0]), "p_raw": float(fit.pvalues[0]),
            "ci95_low": mean - 1.96 * se, "ci95_high": mean + 1.96 * se}


def run_grid(grid: dict, tick: float, d_values, start: pd.Timestamp | None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rows, orders, counts_by = [], [], {}
    for variant, L in VARIANTS.items():
        for side in ("buy", "sell"):
            for d in d_values:
                o, counts = simulate(grid, side=side, d=d, tick=tick, last_eligible_offset=L, start=start)
                o.insert(0, "variant", variant)
                orders.append(o)
                counts_by[f"{variant}/{side}/d={d}"] = counts
                n_or, n_fill = len(o), int(o["filled"].sum())
                for h in HORIZONS:
                    st = mean_stats(o.loc[o["filled"], f"pnl_for_side_{h}m"].to_numpy())
                    pc = o.loc[o["filled"], f"price_change_{h}m"]
                    rows.append({
                        "variant": variant, "side": side, "d": d, "horizon_min": h,
                        "origins": n_or, "fills": n_fill, "fill_rate": n_fill / n_or if n_or else np.nan,
                        "median_bars_to_fill": float(o.loc[o["filled"], "bars_after_placement_to_fill"].median()) if n_fill else np.nan,
                        "fills_dropped_no_forward_bar": int(o["filled"].sum() - pc.notna().sum()),
                        "mean_price_change": float(pc.mean()) if pc.notna().any() else np.nan,
                        **st,
                    })
    table = pd.DataFrame(rows)
    table["family_size"] = np.nan
    table["p_bonferroni"] = np.nan
    table["p_holm"] = np.nan
    for variant, sub in table.groupby("variant"):
        p = sub["p_raw"].to_numpy(dtype=float) if "p_raw" in sub else np.array([])
        table.loc[sub.index, "family_size"] = int(np.isfinite(p).sum())
        table.loc[sub.index, "p_bonferroni"] = bonferroni_adjust(p)
        table.loc[sub.index, "p_holm"] = holm_adjust(p)

    def verdict(r):
        if not np.isfinite(r.get("p_holm", np.nan)):
            return "insufficient data"
        if r["p_holm"] < 0.05:
            return "significantly > 0 (simulator may be too generous)" if r["mean"] > 0 else "significantly < 0 (adverse selection)"
        return "consistent with zero"

    table["verdict_holm"] = table.apply(verdict, axis=1)
    return table, pd.concat(orders, ignore_index=True), counts_by


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def print_table(table: pd.DataFrame) -> None:
    pct = lambda x: "   n/a    " if not np.isfinite(x) else f"{100 * x:+8.4f}%"
    for variant in VARIANTS:
        print(f"\n=== {variant}: mean pnl_for_side BEFORE fees (family = {int(table[table.variant == variant]['family_size'].iloc[0])} tests) ===")
        print(f"hurdles for scale: maker candidate {_HIST_HURDLE_MAKER_CANDIDATE:.2%}, taker viable {_HIST_HURDLE_VIABLE_AS_TAKER:.2%}")
        print(f"{'side':5s} {'d':>6s} {'fill%':>6s} {'h':>4s} {'n':>6s} {'mean':>10s} {'95% CI':>22s} {'t_hac':>7s} {'p_raw':>8s} {'p_holm':>8s}  verdict")
        for r in table[table.variant == variant].itertuples():
            if not np.isfinite(r.mean):
                print(f"{r.side:5s} {r.d:6.2%} {100 * r.fill_rate:6.1f} {r.horizon_min:4d} {int(r.n_used):6d}  INSUFFICIENT DATA (<30 fills)")
                continue
            print(f"{r.side:5s} {r.d:6.2%} {100 * r.fill_rate:6.1f} {r.horizon_min:4d} {r.n_used:6d} {pct(r.mean)} "
                  f"[{pct(r.ci95_low)},{pct(r.ci95_high)}] {r.t_hac:7.2f} {r.p_raw:8.3g} {r.p_holm:8.3g}  {r.verdict_holm}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("user_data/data/binance"))
    ap.add_argument("--pair", default="ETH_FDUSD")
    ap.add_argument("--filters-file", type=Path, default=None, help="default: <data-dir>/../binance_raw/symbol_filters.json")
    ap.add_argument("--tick-size", type=float, default=None)
    ap.add_argument("--d", type=float, nargs="+", default=list(DEFAULT_D))
    ap.add_argument("--start", default=DEFAULT_START, help="exclude origins before this UTC date (post-break)")
    ap.add_argument("--output-dir", type=Path, default=Path("user_data/analysis/results"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        _self_test()
        return

    df = load_1m(args.data_dir / f"{args.pair}-1m.feather")
    grid = build_grid(df)
    filters = args.filters_file or args.data_dir.parent / "binance_raw" / "symbol_filters.json"
    tick, tick_src = resolve_tick(args.tick_size, filters, args.pair.replace("_", ""), grid)
    start = pd.Timestamp(args.start, tz="UTC") if args.start else None
    print(f"data: {args.pair} 1m, {grid['index'][0]} .. {grid['index'][-1]} ({len(grid['index'])} grid minutes, "
          f"{int(np.isnan(grid['close']).sum())} missing)\ntick size: {tick} (from {tick_src}; matches the data's price grid)\n"
          f"origins from: {start}")

    table, orders, counts = run_grid(grid, tick, args.d, start)
    print_table(table)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs = args.output_dir / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    table.to_csv(runs / f"{ts}_passive_fill_baseline.csv", index=False)
    orders.to_csv(runs / f"{ts}_passive_fill_baseline_orders.csv", index=False)
    manifest = {
        "run_id": f"{ts}_passive_fill_baseline", "git_commit": git_commit(), "task": "work order #1, Task 2",
        "pair": args.pair, "tick_size": tick, "tick_source": tick_src, "d_values": args.d, "horizons_min": list(HORIZONS),
        "variants_last_eligible_bar_offset": VARIANTS, "origin_every_min": ORIGIN_EVERY_MIN, "origins_from": str(start),
        "data_range": [str(grid["index"][0]), str(grid["index"][-1])], "counts": counts,
        "fees_for_context": _HIST_FEES,
        "family_size_per_variant": 18, "adjustments": "Bonferroni and Holm both reported",
        "result_csv": str(runs / f"{ts}_passive_fill_baseline.csv"),
        "definitions": "see the module docstring of passive_fill_baseline.py",
    }
    (runs / f"{ts}_passive_fill_baseline.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nWrote {runs}/{ts}_passive_fill_baseline.{{csv,json}} and *_orders.csv")


# --------------------------------------------------------------------------------------
# Self-test: crafted mechanics + an independent brute-force reference
# --------------------------------------------------------------------------------------
def _crafted_grid(start="2026-03-02 10:00", n=200, px=3000.00, tick=0.01) -> tuple[dict, pd.DatetimeIndex]:
    idx = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    a = np.full(n, px)
    return {"index": idx, "open": a.copy(), "high": a + 0.5, "low": a - 0.5, "close": a.copy(), "volume": np.ones(n)}, idx


def _one(grid, side="buy", d=0.001, L=14, start=None, tick=0.01):
    o, c = simulate(grid, side=side, d=d, tick=tick, last_eligible_offset=L, start=start)
    return o, c


def _self_test() -> None:
    T = pd.Timestamp("2026-03-02 11:00", tz="UTC")     # a top-of-hour origin
    # 1. placement bar excluded; exact-touch is not a fill; one tick through IS a fill
    g, idx = _crafted_grid()
    pos = lambda t: int((t - idx[0]) / pd.Timedelta(minutes=1))
    g["low"][pos(T)] = 2990.00                          # dips far below the limit INSIDE the placement bar
    o, _ = _one(g); r = o[o.origin_time == T].iloc[0]
    assert not r.filled and r.limit_price == 2997.00, r
    g["low"][pos(T) + 3] = 2997.00                      # exactly at the limit: no fill
    o, _ = _one(g); assert not o[o.origin_time == T].iloc[0].filled
    g["low"][pos(T) + 3] = 2996.99                      # one tick through: fill, in bar T+3
    o, _ = _one(g); r = o[o.origin_time == T].iloc[0]
    assert r.filled and r.bars_after_placement_to_fill == 3 and r.fill_bar_time == T + pd.Timedelta(minutes=3), r
    print("  placement bar excluded; touching the limit is not a fill; one tick through is a fill")

    # 2. eligible-window length: 14 bars (A) vs 15 bars (B)
    g, idx = _crafted_grid()
    g["low"][pos(T) + 14] = 2990.0
    assert _one(g, L=14)[0].query("origin_time == @T").iloc[0].filled
    g, idx = _crafted_grid(); g["low"][pos(T) + 15] = 2990.0
    assert not _one(g, L=14)[0].query("origin_time == @T").iloc[0].filled
    assert _one(g, L=15)[0].query("origin_time == @T").iloc[0].filled
    g, idx = _crafted_grid(); g["low"][pos(T) + 16] = 2990.0
    assert not _one(g, L=15)[0].query("origin_time == @T").iloc[0].filled
    print("  variant A covers bars T+1..T+14, variant B T+1..T+15, nothing later")

    # 3. forward return arithmetic, and the +h bar is (fill bar + h minutes)
    g, idx = _crafted_grid(n=300)
    g["low"][pos(T) + 3] = 2996.00
    for h, v in ((15, 3001.0), (30, 3003.0), (60, 2994.0)):
        g["close"][pos(T) + 3 + h] = v
    r = _one(g)[0].query("origin_time == @T").iloc[0]
    assert abs(r["price_change_15m"] - (3001.0 / 2997.0 - 1)) < 1e-12
    assert abs(r["price_change_60m"] - (2994.0 / 2997.0 - 1)) < 1e-12 and abs(r["pnl_for_side_60m"] - r["price_change_60m"]) < 1e-15
    g["close"][pos(T) + 3 + 30] = np.nan               # missing forward bar -> dropped for that horizon only
    r = _one(g)[0].query("origin_time == @T").iloc[0]
    assert np.isnan(r["price_change_30m"]) and np.isfinite(r["price_change_15m"])
    print("  forward return = close(fill bar + h) / limit - 1; missing forward bar drops only that horizon")

    # 4. sell mirror, sign of pnl
    g, idx = _crafted_grid(n=300)
    g["high"][pos(T) + 2] = 3003.00
    assert not _one(g, side="sell")[0].query("origin_time == @T").iloc[0].filled            # touch only
    g["high"][pos(T) + 2] = 3003.01
    g["close"][pos(T) + 2 + 15] = 3000.0
    r = _one(g, side="sell")[0].query("origin_time == @T").iloc[0]
    assert r.filled and r.limit_price == 3003.00
    assert abs(r["price_change_15m"] - (3000.0 / 3003.0 - 1)) < 1e-12 and r["pnl_for_side_15m"] > 0   # price fell: the seller gained
    print("  sell side mirrors: fills on high >= limit + tick, pnl sign flipped")

    # 5. tick rounding never makes an order more aggressive
    g, idx = _crafted_grid(px=3000.05)
    g["close"][:] = 3000.05; g["low"][:] = 3000.0; g["high"][:] = 3000.1
    assert abs(_one(g, side="buy")[0].limit_price.iloc[0] - 2997.04) < 1e-9     # 2997.0495 -> floor
    assert abs(_one(g, side="sell")[0].limit_price.iloc[0] - 3003.06) < 1e-9    # 3003.0505 -> ceil
    print("  buy limit rounds down, sell limit rounds up")

    # 6. missing reference bar -> origin skipped and counted; start filter
    g, idx = _crafted_grid()
    g["close"][pos(T) - 1] = np.nan
    o, c = _one(g)
    assert T not in set(o.origin_time) and c["origins_skipped_missing_reference_bar"] == 1, c
    g, idx = _crafted_grid(n=400)
    o, c = _one(g, start=pd.Timestamp("2026-03-02 12:00", tz="UTC"))
    assert o.origin_time.min() >= pd.Timestamp("2026-03-02 12:00", tz="UTC") and c["origins_before_start_excluded"] >= 1
    print("  missing reference bar -> origin skipped and counted; --start excludes earlier origins")

    # 7. tick inference
    assert infer_tick(np.array([3000.01, 2999.5, 3001.37])) == 0.01
    assert infer_tick(np.array([3000.1, 2999.5, 3001.3])) == 0.1
    print("  tick inference from the price grid")

    # 8. vectorised simulator == independent per-origin brute force, on gappy random data
    rng = np.random.default_rng(8)
    n = 12 * 1440
    idx = pd.date_range("2026-03-02", periods=n, freq="1min", tz="UTC")
    c_ = np.round(3000 + np.cumsum(rng.normal(0, 0.4, n)), 2)
    lo = np.round(c_ - np.abs(rng.normal(0, 0.5, n)), 2)
    hi = np.round(c_ + np.abs(rng.normal(0, 0.5, n)), 2)
    frame = pd.DataFrame({"open": c_, "high": hi, "low": lo, "close": c_, "volume": 1.0}, index=idx)
    frame = frame.drop(idx[rng.choice(n, 400, replace=False)])
    grid = build_grid(frame)
    bars = {t: (r.low, r.high, r.close) for t, r in zip(frame.index, frame.itertuples())}
    tick = 0.01
    for side in ("buy", "sell"):
        for d in (0.0005, 0.001, 0.002):
            for L in (14, 15):
                o, _ = simulate(grid, side=side, d=d, tick=tick, last_eligible_offset=L)
                ref_rows = []
                for T0 in pd.date_range(idx[0].ceil("h"), idx[-1], freq="60min", tz="UTC"):
                    prev = bars.get(T0 - pd.Timedelta(minutes=1))
                    if prev is None or T0 - pd.Timedelta(minutes=1) < idx[0] or T0 + pd.Timedelta(minutes=L) > idx[-1]:
                        continue
                    ref = prev[2]
                    lim = (math.floor(ref * (1 - d) / tick + 1e-9) if side == "buy" else math.ceil(ref * (1 + d) / tick - 1e-9))
                    fb = None
                    for k in range(1, L + 1):
                        b = bars.get(T0 + pd.Timedelta(minutes=k))
                        if b is None:
                            continue
                        if (side == "buy" and round(b[0] / tick) <= lim - 1) or (side == "sell" and round(b[1] / tick) >= lim + 1):
                            fb = k
                            break
                    fwd = {}
                    for h in HORIZONS:
                        b = bars.get(T0 + pd.Timedelta(minutes=(fb or 0) + h)) if fb else None
                        fwd[h] = (b[2] / (lim * tick) - 1) if b else np.nan
                    ref_rows.append((T0, fb is not None, fb or -1, fwd))
                assert len(ref_rows) == len(o), (side, d, L, len(ref_rows), len(o))
                for (T0, f, k, fwd), row in zip(ref_rows, o.itertuples()):
                    assert row.origin_time == T0 and bool(row.filled) == f and row.bars_after_placement_to_fill == k, (T0, row)
                    for h in HORIZONS:
                        a, b = fwd[h], getattr(row, f"price_change_{h}m")
                        assert (np.isnan(a) and np.isnan(b)) or abs(a - b) < 1e-12, (T0, h, a, b)
    print("  vectorised simulator matches an independent per-origin brute force (both sides, 3 d, both variants, 400 missing bars)")

    # 9. statistics + adjusted p plumbing on the same data
    table, orders, _ = run_grid(grid, 0.01, DEFAULT_D, None)
    assert len(table) == 2 * 2 * 3 * 3                     # variants x sides x d x horizons
    tested = table.groupby("variant")["p_raw"].apply(lambda s_: int(s_.notna().sum()))
    assert (table.groupby("variant")["family_size"].first() == tested).all()   # family = tests actually run
    m = table["p_raw"].notna()
    assert (table.loc[m, "p_holm"] >= table.loc[m, "p_raw"] - 1e-12).all()
    assert (table.loc[m, "p_bonferroni"] >= table.loc[m, "p_holm"] - 1e-12).all()
    y = np.random.default_rng(1).normal(0.0002, 0.001, 4000)
    st = mean_stats(y)
    assert abs(st["mean"] - y.mean()) < 1e-15 and abs(st["t_hac"] - y.mean() / (y.std(ddof=1) / 4000 ** 0.5)) < 0.3
    print("  stats: HAC mean/t match the naive iid values on iid data; Holm >= raw, Bonferroni >= Holm; family = tests run (18 when every cell has >=30 fills)")
    print("Self-test passed: passive_fill_baseline implements every stated timing convention.")


if __name__ == "__main__":
    main()
