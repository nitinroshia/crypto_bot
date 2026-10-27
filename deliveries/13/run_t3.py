"""
Orchestration script for Task 3 shock_response (Work Order 1.7): the twin of run_s1.py / run_s2.py. For one pair it loads the 5m file,
truncates it at the cutoff, derives the 15m bars, builds the 48 cells (Holm and Bonferroni over 48), classifies the two PRIMARY cells,
runs the dose-response check, the event stability statistic, by-year / leave-one-year-out and the robustness columns, and writes
exactly TWO registry records (family Task3-<PAIR>): `discovery` and `stability`. There is no economic-gate record: M is the
economic criterion of event cells. Labeled variants are returned for the report and NEVER recorded.

DELIBERATELY STOPS AFTER CLASSIFICATION AND STABILITY: freeze_manifest.py, holdout_lock.py and forward_test.py are never imported.

REGISTRY HYGIENE: the default is a SCRATCH registry (temp/scratch-registry.jsonl) or --registry-path (any non-live file); the live
registry is written only with --commit-to-registry. PRE-TAX.

  python3 run_t3.py --pair ETH_USDT --origin-facts          # read-only facts and counts (item 8): writes nothing
  python3 run_t3.py --pair ETH_USDT --registry-path ../../temp/dry.jsonl      # dry run on a scratch registry
  python3 run_t3.py --pair ETH_USDT --commit-to-registry    # LIVE (explicit flag; only after the owner's go-ahead)
  python3 run_t3.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import formula_t3 as f3
import registry
from cutoff import CUTOFF, truncate_at_cutoff
from databundle import _read_feather, default_raw_dir, load_bundle

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "user_data" / "data" / "binance"
PRIMARY_IDS = {"down": "5m_k6_down", "up": "5m_k6_up"}
COST_BASE, COST_STRESS = 0.0024, 0.0030


def family_name(pair: str) -> str:
    return f"Task3-{pair.replace('_', '')}"


def _sha(path: Path | None) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path is not None and path.exists() else "n/a"


def _iso(ts) -> str:
    return pd.Timestamp(ts).isoformat()


def _find(pair: str, tf: str, data_dir: Path, raw_dir: Path | None) -> Path | None:
    raw = Path(raw_dir) if raw_dir is not None else default_raw_dir(data_dir)
    return next((p for p in (Path(data_dir) / f"{pair}-{tf}.feather", raw / f"{pair}-{tf}.feather") if p.exists()), None)


# ----------------------------------------------------------------------------- loading
def load_pair(pair: str, data_dir: Path, raw_dir: Path | None = None, df5: pd.DataFrame | None = None, native15: pd.DataFrame | None = None, mask_zero_volume: bool = False) -> dict:
    """5m file -> truncated at the cutoff -> grid frame; 15m derived from 5m; the native 15m file (if any) compared on every complete bar."""
    if df5 is None:
        df5 = load_bundle(data_dir, pair, ["5m"], raw_dir=raw_dir)["5m"]
    n_before = len(df5)
    df5 = truncate_at_cutoff(df5, CUTOFF)
    fr5, facts5 = f3.frame_from_df(df5, 300, mask_zero_volume=mask_zero_volume)
    fr15 = f3.derive_15m(fr5)
    post = int((df5.index > CUTOFF).sum())
    p15 = None
    if native15 is None:
        p15 = _find(pair, "15m", data_dir, raw_dir)
        native15 = _read_feather(p15) if p15 is not None else None
    cmp15 = None
    if native15 is not None:
        n15, _ = f3.frame_from_df(truncate_at_cutoff(native15, CUTOFF), 900)
        lo, hi = max(fr15.sec[0], n15.sec[0]), min(fr15.sec[-1], n15.sec[-1])
        a0, b0 = int((lo - fr15.sec[0]) // 900), int((lo - n15.sec[0]) // 900)
        m = int((hi - lo) // 900) + 1
        d_o, d_c, d_p = fr15.O[a0:a0 + m], fr15.C[a0:a0 + m], fr15.present[a0:a0 + m]
        n_o, n_c, n_p = n15.O[b0:b0 + m], n15.C[b0:b0 + m], n15.present[b0:b0 + m]
        both = d_p & n_p
        cmp15 = {"compared_bars": int(both.sum()), "open_mismatches": int((~np.isclose(d_o[both], n_o[both], rtol=1e-12, atol=0)).sum()),
                 "close_mismatches": int((~np.isclose(d_c[both], n_c[both], rtol=1e-12, atol=0)).sum()),
                 "present_derived_missing_native": int((d_p & ~n_p).sum()), "present_native_missing_derived": int((~d_p & n_p).sum()),
                 "native_rows": int(len(native15)), "native_first": n15.label(0), "native_last": n15.label(n15.n - 1)}
    p5 = _find(pair, "5m", data_dir, raw_dir)
    return {"fr5": fr5, "fr15": fr15, "facts5": facts5, "rows_before_cutoff_truncation": n_before, "post_cutoff_rows": post, "cmp15": cmp15,
            "files": {"5m": (p5.name if p5 else "5m file", _sha(p5)), "15m": (p15.name if p15 else None, _sha(p15))}}


def prepare_pair(L: dict) -> dict:
    return {"5m": f3.prepare(L["fr5"], f3.W5), "15m": f3.prepare(L["fr15"], f3.W15)}


# ----------------------------------------------------------------------------- facts (item 8)
def counts_for(fr: f3.Frame, prep: dict, thr: float) -> dict:
    """Event counts before and after de-clustering for one timeframe and threshold; no returns are used."""
    z = prep["z"]
    cand = prep["eligible"] & (np.abs(np.where(np.isfinite(z), z, 0.0)) >= thr)
    kept, side = f3.event_clock(prep, thr)
    ok = prep["tgt_ok"][kept]
    gap_drop = (~ok) & (kept + f3.KMAX < fr.n)
    cut_drop = (~ok) & (kept + f3.KMAX >= fr.n)
    return {
        "event_bars_down": int((cand & (z <= -thr)).sum()), "event_bars_up": int((cand & (z >= thr)).sum()),
        "kept_down": int((side == -1).sum()), "kept_up": int((side == 1).sum()),
        "dropped_gap": int(gap_drop.sum()), "dropped_cutoff": int(cut_drop.sum()),
        "used_down": int(((side == -1) & ok).sum()), "used_up": int(((side == 1) & ok).sum()),
    }


def origin_facts_for(pair: str, data_dir: Path, raw_dir: Path | None = None, loaded: dict | None = None) -> dict:
    L = loaded if loaded is not None else load_pair(pair, data_dir, raw_dir)
    P = prepare_pair(L)
    out = {"pair": pair, "facts5": L["facts5"], "files": L["files"], "cmp15": L["cmp15"], "post_cutoff_rows": L["post_cutoff_rows"], "rows_before_cutoff_truncation": L["rows_before_cutoff_truncation"], "tf": {}}
    for tf, fr in (("5m", L["fr5"]), ("15m", L["fr15"])):
        prep = P[tf]
        origin = prep["origin_idx"]
        out["tf"][tf] = {"reasons": prep["reasons"], "first_origin": fr.label(origin[0]), "last_origin": fr.label(origin[-1]),
                         "first_entry": fr.label(origin[0] + 1), "last_entry": fr.label(origin[-1] + 1),
                         "z3": counts_for(fr, prep, f3.THR), "z4": counts_for(fr, prep, f3.THR_DOSE), "first_bar": fr.label(0), "last_bar": fr.label(fr.n - 1)}
        ft = out["tf"][tf]["z3"]
        flags = []
        for nm in ("down", "up"):
            u = ft[f"used_{nm}"]
            if tf == "5m" and (u < 500 or u > 20000):
                flags.append(f"{nm} kept count {u} outside 500..20,000")
        lo, hi = min(ft["used_down"], ft["used_up"]), max(ft["used_down"], ft["used_up"])
        if lo > 0 and hi / lo > 1.5:
            flags.append(f"asymmetry {hi / lo:.2f} > 1.5")
        out["tf"][tf]["flags"] = flags
    t0, last = L["fr5"].sec[P["5m"]["origin_idx"][0] + 1], L["fr5"].sec[P["5m"]["origin_idx"][-1] + 1] + 300
    out["stability_blocks"] = {"t0": pd.Timestamp(int(t0), unit="s", tz="UTC"), "full_90d_blocks": int((last - t0) // (90 * 86400)), "partial_days": ((last - t0) % (90 * 86400)) / 86400}
    return out


def print_origin_facts_report(f: dict) -> None:
    f5 = f["facts5"]
    print(f"\n=== Task 3 origin facts: {f['pair']} ===")
    print(f"5m file {f['files']['5m'][0]} sha256 {f['files']['5m'][1]}")
    print(f"5m rows before the cutoff truncation: {f['rows_before_cutoff_truncation']}; in the discovery frame: {f5['rows']}; grid {f5['grid']} bars {f5['first']} .. {f5['last']}; "
          f"missing bars in the grid: {f5['missing']} (rows without full OHLC: {f5['rows_without_full_ohlc']}); zero-volume rows (treated as present): {f5['zero_volume_rows']}; rows after the cutoff: {f['post_cutoff_rows']} (must be 0)")
    print("expected for a gap-free frame starting 2017-08-17 04:00: 845,808 5m bars, first eligible origin 2017-08-18 04:05 (15m 04:15), last 22:55 on 2025-08-31 (15m 20:45)")
    c = f["cmp15"]
    if c is None:
        print("native 15m file: none (the 15m bars are derived from 5m for both pairs)")
    else:
        print(f"native 15m file {f['files']['15m'][0]} sha256 {f['files']['15m'][1]}: {c['native_rows']} rows in the whole file (before the cutoff truncation), discovery frame {c['native_first']} .. {c['native_last']}; compared with the derived series on {c['compared_bars']} complete bars: "
              f"open mismatches {c['open_mismatches']}, close mismatches {c['close_mismatches']}; present in the derived series but missing natively {c['present_derived_missing_native']}; "
              f"present natively but missing in the derived series {c['present_native_missing_derived']} (the order expects 0)")
    for tf in ("5m", "15m"):
        t = f["tf"][tf]
        r = t["reasons"]
        print(f"[{tf}] bars in grid {r['bars_in_grid']}, present {r['bars_present']}, missing {r['bars_missing']}; first/last bar {t['first_bar']} / {t['last_bar']}; eligible origins {r['eligible_origins']} "
              f"(first {t['first_origin']}, last {t['last_origin']}; first/last entry {t['first_entry']} / {t['last_entry']})")
        print(f"      not an origin: z window {r['not_origin_z_window']}, target window (gap inside the frame) {r['not_origin_target_window_gap']}, cutoff (bar j+12 beyond the frame) {r['not_origin_cutoff']}")
        for key, lab in (("z3", "|z| >= 3"), ("z4", "|z| >= 4")):
            k = t[key]
            print(f"      {lab}: event bars before de-clustering down {k['event_bars_down']} up {k['event_bars_up']}; kept after the shared clock down {k['kept_down']} up {k['kept_up']}; "
                  f"dropped for an incomplete window (gap {k['dropped_gap']}, cutoff {k['dropped_cutoff']}); used in the statistics down {k['used_down']} up {k['used_up']}")
        print(f"      flags: {t['flags'] if t['flags'] else 'none (kept counts within 500..20,000 per side at 5m, asymmetry <= 1.5)'}")
    sb = f["stability_blocks"]
    print(f"stability tiling: t0 = {sb['t0']}; full 90-day blocks {sb['full_90d_blocks']} (expect 32), partial block {sb['partial_days']:.1f} days (expect about 55)")
    print("(no returns, p-values or cell statistics are computed here; nothing is written)")


# ----------------------------------------------------------------------------- labeled variant: zero-volume bars masked
def variant_zero_volume(pair: str, data_dir: Path, raw_dir: Path | None = None, base: dict | None = None, masked_loaded: dict | None = None, base_loaded: dict | None = None) -> dict:
    """READ-ONLY, never recorded (Work Order 1.7 question 2): the primary cells and the 48-cell Holm with zero-volume 5m bars treated as MISSING, next to the primary
    (literal) reading in which they count as present."""
    out = {}
    for name, loaded in (("present (primary)", base_loaded), ("masked (variant)", masked_loaded)):
        L = loaded if loaded is not None else load_pair(pair, data_dir, raw_dir, mask_zero_volume=(name.startswith("masked")))
        P = prepare_pair(L)
        cells = f3.family_cells([f3.cell_table(L["fr5"], P["5m"], "5m"), f3.cell_table(L["fr15"], P["15m"], "15m")])
        rows = {}
        for nm in ("down", "up"):
            r = cells[(cells["timeframe"] == "5m") & (cells["k"] == f3.PRIMARY_K) & (cells["side"] == nm)].iloc[0]
            cls = f3.classify({"mean": r["mean_excess"], "upper95": r["upper95"], "mde": r["mde"]}, float(r["p_holm"]))
            rows[nm] = {"n": int(r["n"]), "mean_excess": float(r["mean_excess"]), "se": float(r["se"]), "t": float(r["t"]), "p_one": float(r["p_one"]), "p_holm": float(r["p_holm"]), "mde": float(r["mde"]), "classification": cls}
        out[name] = {"bars_present": int(L["fr5"].present.sum()), "masked_zero_volume": L["facts5"].get("masked_zero_volume", 0), "eligible_origins": P["5m"]["reasons"]["eligible_origins"], "cells": rows,
                     "mde_above_M": int((cells["mde"] > f3.M).sum())}
    return out


def print_variant_zero_volume(pair: str, v: dict) -> None:
    print(f"\n=== Task 3 labeled variant, zero-volume 5m bars masked (never recorded): {pair} ===")
    for name, d in v.items():
        print(f"[{name}] 5m bars present {d['bars_present']} (zero-volume bars masked: {d['masked_zero_volume']}); eligible 5m origins {d['eligible_origins']}; cells with MDE above M: {d['mde_above_M']}")
        for nm, r in d["cells"].items():
            print(f"    5m k=6 {nm:<4}: n={r['n']} mean excess={r['mean_excess']:.6g} SE={r['se']:.6g} t={r['t']:.4f} one-sided p={r['p_one']:.6g} Holm(48)={r['p_holm']:.6g} MDE={r['mde']:.6g} -> {r['classification'].upper()}")


# ----------------------------------------------------------------------------- by-year
def by_year_events(fr: f3.Frame, origin_idx: np.ndarray, idx: np.ndarray, excess: np.ndarray, min_days: int = 120) -> dict:
    """Per calendar year: n, mean excess, day-clustered SE, t; leave-one-year-out pooled mean; year-driven flag (dropping the year cuts the pooled
    estimate by more than half or flips its sign; a NaN leave-one-out, which happens only with a single year, is never year-driven). `days covered` counts the calendar days
    with an eligible origin in that year (an event-day count would undercount sparse events); years under `min_days` days are shown, not judged."""
    ent = fr.sec[idx + 1]
    years = pd.to_datetime(ent, unit="s", utc=True).year.to_numpy()
    oyears = pd.to_datetime(fr.sec[origin_idx + 1], unit="s", utc=True)
    days_by_year = pd.Series(oyears.normalize()).groupby(oyears.year.to_numpy()).nunique() if False else pd.Series(oyears.normalize()).groupby(np.asarray(oyears.year)).nunique()
    pooled = float(excess.mean()) if len(excess) else float("nan")
    rows, loo, driven, agree = [], {}, {}, {}
    for y in sorted(set(years.tolist())):
        m = years == y
        st = f3.cell_stats(excess[m], ent[m] // f3.DAY_S)
        days = int(days_by_year.get(y, 0))
        judged = days >= min_days
        rows.append({"year": int(y), "n": int(m.sum()), "days_covered": days, "mean_excess": st["mean"], "se": st["se"], "t": st["t"], "judged": judged})
        if judged:
            rest = excess[~m]
            est = float(rest.mean()) if len(rest) else float("nan")
            loo[y] = est
            if np.isfinite(est):
                halved = abs(est) < abs(pooled) / 2
                flipped = (est > 0) != (pooled > 0) and est != 0 and pooled != 0
                driven[y] = bool(halved or flipped)
            else:
                driven[y] = False
            agree[y] = bool((st["mean"] > 0) == (pooled > 0))
    return {"pooled": pooled, "table": pd.DataFrame(rows), "loo": loo, "year_driven": driven, "any_year_driven": any(driven.values()), "sign_agreement": agree,
            "all_judged_years_agree": all(agree.values()) if agree else True}


# ----------------------------------------------------------------------------- the run
def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


def robustness_for(fr: f3.Frame, prep: dict, side_name: str, mu6: float, kept: np.ndarray, side: np.ndarray) -> dict:
    which = -1 if side_name == "down" else 1
    orig = prep["origin_idx"]
    day_of = lambda idx: fr.sec[idx + 1] // f3.DAY_S
    out = {}
    m = (side == which) & prep["tgt_ok"][kept]
    base = kept[m]
    # (a) one clock per side
    ks, _ = f3.event_clock(prep, f3.THR, side=which)
    ks = ks[prep["tgt_ok"][ks]]
    out["a_one_clock_per_side"] = f3.cell_stats(f3.log_target(fr, ks, 6) - mu6, day_of(ks))
    # (b) mu_6 from the |z| < 3 origins only
    zo = prep["z"][orig]
    mu_b = float(f3.log_target(fr, orig[np.abs(zo) < f3.THR], 6).mean())
    out["b_mu_from_small_z_origins"] = {**f3.cell_stats(f3.log_target(fr, base, 6) - mu_b, day_of(base)), "mu_6_small_z": mu_b}
    # (c) entry one bar late against its own baseline over all origins
    mu_c = float(f3.log_target(fr, orig, 6, shift=2).mean())
    out["c_entry_one_bar_late"] = {**f3.cell_stats(f3.log_target(fr, base, 6, shift=2) - mu_c, day_of(base)), "mu_6_late": mu_c}
    # (d) naive SE and t are columns of the main stats; (f) mean raw return minus round-trip costs
    raw = f3.log_target(fr, base, 6)
    out["f_raw_minus_costs"] = {"mean_raw": float(raw.mean()), "minus_base_cost": float(raw.mean() - COST_BASE), "minus_stress_cost": float(raw.mean() - COST_STRESS)}
    # (g) kept events by UTC hour of the event bar
    out["g_utc_hours"] = f3.utc_hour_counts(fr, kept, side)[side_name]
    return out


def run_t3(pair: str, data_dir: Path, raw_dir: Path | None = None, registry_path: Path = registry.DEFAULT_REGISTRY_PATH, commit_to_registry: bool = False,
           loaded: dict | None = None) -> dict:
    """Task 3 for `pair`: appends exactly two records (discovery, stability) and returns every figure (recorded and labeled variants)."""
    L = loaded if loaded is not None else load_pair(pair, data_dir, raw_dir)
    if L["post_cutoff_rows"]:
        raise ValueError("rows after the cutoff in the discovery frame")
    family, reg_pair = family_name(pair), pair.replace("_", "")
    fr5, fr15 = L["fr5"], L["fr15"]
    P = prepare_pair(L)
    tabs = [f3.cell_table(fr5, P["5m"], "5m"), f3.cell_table(fr15, P["15m"], "15m")]
    cells = f3.family_cells(tabs)
    facts = origin_facts_for(pair, data_dir, raw_dir, loaded=L)
    prim = f3.primary_results(fr5, P["5m"])
    kept, side = f3.event_clock(P["5m"], f3.THR)
    dose = f3.dose_response(fr5, P["5m"])
    primary, entries_d, entries_s, stab_cells, extras = {}, {}, {}, {}, {}
    for nm in ("down", "up"):
        row = cells[(cells["timeframe"] == "5m") & (cells["k"] == f3.PRIMARY_K) & (cells["side"] == nm)].iloc[0]
        st = prim[nm]["stats"]
        if abs(row["mean_excess"] - st["mean"]) > 1e-13 or int(row["n"]) != st["n"] or abs(row["se"] - st["se"]) > 1e-13:
            raise ValueError("cell table and primary_results disagree")
        cls = f3.classify({"mean": row["mean_excess"], "upper95": row["upper95"], "mde": row["mde"]}, float(row["p_holm"]))
        cid = PRIMARY_IDS[nm]
        primary[cid] = {"n": int(row["n"]), "mean_excess": float(row["mean_excess"]), "mean_raw": float(row["mean_raw"]), "se": float(row["se"]), "se_naive": float(row["se_naive"]), "t": float(row["t"]),
                        "p_one": float(row["p_one"]), "p_holm": float(row["p_holm"]), "p_bonferroni": float(row["p_bonferroni"]), "mde": float(row["mde"]), "upper95": float(row["upper95"]), "classification": cls}
        entries_d[cid] = float(row["p_one"])
        blk = prim[nm]["block"]
        stab_cells[cid] = {"T": blk["T"], "p_stab": blk["p"], "B_used": blk["B"], "B_full": blk["B_full"], "partial_days": blk["partial_days"], "blocks": blk["blocks"]}
        entries_s[cid] = blk["p"]
        extras[cid] = {"by_year": by_year_events(fr5, P["5m"]["origin_idx"], prim[nm]["idx"], prim[nm]["excess"]),
                       "robustness": robustness_for(fr5, P["5m"], nm, prim["mu"], kept, side),
                       "trades": f3.trade_rows(pair, cid, fr5, prim[nm]["idx"], prim[nm]["excess"])}
    cells_json = _clean(cells.drop(columns=["p_value"]).assign(p_value=cells["p_value"]).to_dict(orient="records"))
    registry.append_record(
        {"family": family, "pair": reg_pair, "status": "discovery", "timestamp_utc": registry.new_timestamp(),
         "detail": {"entries": entries_d, "primary_cells": primary, "all_cells": cells_json, "family_size": 48, "mu_6_5m": float(prim["mu"]),
                    "dose_response": _clean(dose), "origins": _clean({tf: {"reasons": facts["tf"][tf]["reasons"], "first_origin": facts["tf"][tf]["first_origin"], "last_origin": facts["tf"][tf]["last_origin"],
                                                                      "z3": facts["tf"][tf]["z3"], "z4": facts["tf"][tf]["z4"]} for tf in ("5m", "15m")}),
                    "post_cutoff_rows": L["post_cutoff_rows"], "files": {k: list(v) for k, v in L["files"].items()}, "cmp15": _clean(L["cmp15"]), "zero_volume_rows": L["facts5"]["zero_volume_rows"]}},
        registry_path, commit_to_registry=commit_to_registry)
    registry.append_record(
        {"family": family, "pair": reg_pair, "status": "stability", "timestamp_utc": registry.new_timestamp(),
         "detail": {"entries": entries_s, "cells": _clean(stab_cells), "block_days": f3.BLOCK_DAYS, "min_events_per_block": f3.NMIN_BLOCK,
                    "statistic": "Work Order 1.7 event stability: T = sum t_b / sqrt(B'), p_stab = 1 - Phi(T)"}},
        registry_path, commit_to_registry=commit_to_registry)
    return {"family": family, "pair": reg_pair, "cells": cells, "primary": primary, "primary_raw": prim, "dose": dose, "stability": stab_cells, "extras": extras, "facts": facts,
            "mu_table": cells.drop_duplicates(["timeframe", "k"])[["timeframe", "k", "mu"]]}


def print_report(res: dict) -> None:
    print(f"\n=== Task 3 run: {res['family']} ({res['pair']}) -- PRE-TAX ===")
    c = res["cells"]
    show = c[["timeframe", "k", "side", "n", "mean_raw", "mean_excess", "se", "se_naive", "t", "p_value", "p_holm", "p_bonferroni", "mde", "primary"]]
    print("\n-- 48 cells (p_value = one-sided positive for the two primary cells, two-sided otherwise; Holm and Bonferroni over 48) --")
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.float_format", lambda x: f"{x:.6g}"):
        print(show.to_string(index=False))
    print(f"cells with MDE above M = {f3.M}: {int((c['mde'] > f3.M).sum())} of 48; cells with p exactly 0 or 1: {int(((c['p_value'] == 0) | (c['p_value'] == 1)).sum())}")
    print("\n-- primary cells and classification --")
    for cid, p in res["primary"].items():
        print(f"{cid}: n={p['n']} mean excess={p['mean_excess']:.6g} (raw {p['mean_raw']:.6g}) SE={p['se']:.6g} t={p['t']:.4f} one-sided p={p['p_one']:.6g} Holm(48)={p['p_holm']:.6g} "
              f"Bonferroni={p['p_bonferroni']:.6g} MDE={p['mde']:.6g} upper95={p['upper95']:.6g} -> {p['classification'].upper()}")
    print("\n-- dose-response (5m, k=6) --")
    for nm, d in res["dose"].items():
        print(f"{nm}: |z|>=3 mean {d['z3_mean']:.6g} (n={d['z3_n']}); |z|>=4 mean {d['z4_mean']:.6g} (n={d['z4_n']}) -> {d['verdict']}")
    print("\n-- stability (event statistic, 90-day blocks from the first eligible 5m origin) --")
    for cid, s in res["stability"].items():
        print(f"{cid}: T={s['T']:.4f} p_stab={s['p_stab']:.6g} B'={s['B_used']} of {s['B_full']} full blocks; partial block {s['partial_days']:.1f} days; blocks with < 30 events: {sum(1 for b in s['blocks'] if not b['used'])}")
    for cid, x in res["extras"].items():
        by = x["by_year"]
        print(f"\n-- by-year {cid}: pooled mean excess {by['pooled']:.6g}; any year-driven: {by['any_year_driven']}; all judged years agree in sign: {by['all_judged_years_agree']} --")
        print(by["table"].assign(loo=by["table"]["year"].map(lambda y: by["loo"].get(y, np.nan))).to_string(index=False))
        rb = x["robustness"]
        print(f"-- robustness {cid} (descriptive): one clock per side n={rb['a_one_clock_per_side']['n']} mean={rb['a_one_clock_per_side']['mean']:.6g} t={rb['a_one_clock_per_side']['t']:.3f}; "
              f"mu from |z|<3 origins mean={rb['b_mu_from_small_z_origins']['mean']:.6g} t={rb['b_mu_from_small_z_origins']['t']:.3f}; entry one bar late mean={rb['c_entry_one_bar_late']['mean']:.6g} t={rb['c_entry_one_bar_late']['t']:.3f}; "
              f"raw minus base/stress cost {rb['f_raw_minus_costs']['minus_base_cost']:.6g}/{rb['f_raw_minus_costs']['minus_stress_cost']:.6g}")
        print(f"   kept events by UTC hour of the event bar: {rb['g_utc_hours']}")
        print(f"   trade list: {len(x['trades'])} rows")
    print("\nNOT frozen, NOT forward-tested -- results above are for review before proceeding.\n")


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pair", type=str)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--raw-dir", type=Path, default=None)
    p.add_argument("--registry-path", type=Path, default=None)
    p.add_argument("--origin-facts", action="store_true")
    p.add_argument("--variant-zero-volume", action="store_true", help="read-only labeled variant: zero-volume 5m bars masked")
    p.add_argument("--commit-to-registry", action="store_true")
    p.add_argument("--self-test", action="store_true")
    return p


# ============================================================================= self-test
def _synthetic_5m(ref, seed: int = 5, start: str = "2025-03-01 00:00", ndays: int = 190, drop=(), zero_vol=()) -> pd.DataFrame:
    r = ref.make_returns(ndays * 288, np.random.default_rng(seed), "t4sv")
    C, O = ref.closes_opens(r)
    idx = pd.date_range(start, periods=len(r), freq="5min", tz="UTC")
    df = pd.DataFrame({"open": O * 100, "high": np.maximum(O, C) * 100 * 1.0001, "low": np.minimum(O, C) * 100 * 0.9999, "close": C * 100, "volume": 1.0}, index=idx)
    df.index.name = "date"
    for i in zero_vol:
        df.iloc[i, df.columns.get_loc("volume")] = 0.0
    return df.drop(index=idx[list(drop)]) if len(drop) else df


def _self_test() -> None:
    import tempfile

    ref = f3.load_reference()
    drops = [20000, 20001, 30000]
    df = _synthetic_5m(ref, drop=drops, zero_vol=[10, 11])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_dir = tmp / "binance"
        data_dir.mkdir()
        for pair, seed in (("ETH_USDT", 5), ("BTC_USDT", 6)):
            _synthetic_5m(ref, seed=seed, drop=drops, zero_vol=[10, 11]).reset_index().to_feather(data_dir / f"{pair}-5m.feather")
        reg = tmp / "registry.jsonl"
        res = run_t3("ETH_USDT", data_dir, registry_path=reg)
        recs = registry.load_records(reg)
        assert [(r["family"], r["status"]) for r in recs] == [("Task3-ETHUSDT", "discovery"), ("Task3-ETHUSDT", "stability")], "exactly two records, no economic gate"
        d, s = recs[0]["detail"], recs[1]["detail"]
        assert len(d["all_cells"]) == 48 and d["family_size"] == 48 and set(d["entries"]) == {"5m_k6_down", "5m_k6_up"} and set(s["entries"]) == {"5m_k6_down", "5m_k6_up"}
        assert d["post_cutoff_rows"] == 0 and res["facts"]["post_cutoff_rows"] == 0 and d["zero_volume_rows"] == 2
        assert {p["classification"] for p in d["primary_cells"].values()} <= {"pass", "dead", "inconclusive"}
        for cid in ("5m_k6_down", "5m_k6_up"):
            assert abs(d["entries"][cid] - d["primary_cells"][cid]["p_one"]) < 1e-15 and s["cells"][cid]["B_full"] == 2 and len(s["cells"][cid]["blocks"]) == 2
            assert len(res["extras"][cid]["trades"]) == d["primary_cells"][cid]["n"] and list(res["extras"][cid]["trades"].columns)[:3] == ["pair", "cell", "event_bar_time_utc"]
            rb = res["extras"][cid]["robustness"]
            assert len(rb["g_utc_hours"]) == 24 and sum(rb["g_utc_hours"]) >= d["primary_cells"][cid]["n"] and rb["a_one_clock_per_side"]["n"] >= 0
        assert not any(r["status"] in ("frozen", "holdout_consumed") for r in recs)
        # the across-candidate Holm sees each primary cell as its own entry; records without entries behave as before
        hs = registry.holm_at_step(recs, "ETHUSDT", "stability")
        assert set(hs) == {"Task3-ETHUSDT:5m_k6_down", "Task3-ETHUSDT:5m_k6_up"} and all(0 <= v["p_holm"] <= 1 for v in hs.values())
        # re-runnable, and the truncation really removed the post-cutoff rows
        run_t3("ETH_USDT", data_dir, registry_path=reg)
        assert len(registry.load_records(reg)) == 4
        before = sorted(p.name for p in tmp.rglob("*"))
        facts = origin_facts_for("ETH_USDT", data_dir)
        assert sorted(p.name for p in tmp.rglob("*")) == before, "origin facts write nothing"
        assert facts["facts5"]["last"] == pd.Timestamp("2025-08-31 23:55", tz="UTC") and facts["facts5"]["zero_volume_rows"] == 2 and facts["facts5"]["missing"] == 3
        assert facts["tf"]["5m"]["reasons"]["not_origin_cutoff"] == 12 and facts["tf"]["5m"]["reasons"]["bars_missing"] == 3
        print_origin_facts_report(facts)
        # live registry hygiene
        fake = tmp / "fake_live" / "registry.jsonl"
        fake.parent.mkdir()
        fake.write_text("")
        saved = registry.LIVE_REGISTRY_PATH
        registry.LIVE_REGISTRY_PATH = fake
        try:
            try:
                run_t3("ETH_USDT", data_dir, registry_path=fake)
            except registry.LiveRegistryWriteRefused:
                pass
            else:
                raise AssertionError("a live registry path without the flag must be refused")
            assert fake.read_text() == ""
            run_t3("ETH_USDT", data_dir, registry_path=fake, commit_to_registry=True)
            assert len(registry.load_records(fake)) == 2
        finally:
            registry.LIVE_REGISTRY_PATH = saved
        # derived 15m against a native 15m file: equal on complete bars when the native file is built the same way, one mismatch when it is not
        L = load_pair("ETH_USDT", data_dir)
        fr15 = L["fr15"]
        nat = pd.DataFrame({"open": fr15.O, "high": fr15.O, "low": fr15.O, "close": fr15.C, "volume": 1.0}, index=pd.to_datetime(fr15.sec, unit="s", utc=True)).dropna(subset=["open"])
        nat.index.name = "date"
        L2 = load_pair("ETH_USDT", data_dir, native15=nat)
        assert L2["cmp15"]["open_mismatches"] == 0 and L2["cmp15"]["close_mismatches"] == 0 and L2["cmp15"]["compared_bars"] == int(fr15.present.sum())
        nat2 = nat.copy()
        nat2.iloc[100, nat2.columns.get_loc("close")] *= 1.01
        assert load_pair("ETH_USDT", data_dir, native15=nat2)["cmp15"]["close_mismatches"] == 1
        vz = variant_zero_volume("ETH_USDT", data_dir)
        assert vz["masked (variant)"]["masked_zero_volume"] == 2 and vz["masked (variant)"]["bars_present"] == vz["present (primary)"]["bars_present"] - 2 and vz["present (primary)"]["masked_zero_volume"] == 0
        assert set(vz["masked (variant)"]["cells"]) == {"down", "up"}
        print_variant_zero_volume("ETH_USDT", vz)
        print_report(res)
    # by-year equals the nonstationarity module on dense data (consistency with the project's rule)
    import nonstationarity

    rng = np.random.default_rng(3)
    fr = f3.Frame(f3.EPOCH_2017_08_17 + 300 * np.arange(288 * 900), np.ones(288 * 900), np.ones(288 * 900), 300)
    idx = np.sort(rng.choice(np.arange(10, 288 * 900 - 30), 4000, replace=False))
    ex = rng.normal(0.0004, 0.01, len(idx))
    by = by_year_events(fr, np.arange(10, 288 * 900 - 30), idx, ex)
    ev = pd.DataFrame({"excess": ex}, index=pd.to_datetime(fr.sec[idx + 1], unit="s", utc=True))
    ns = nonstationarity.non_stationarity_report(ev, lambda sub: float(sub["excess"].mean()))
    assert abs(by["pooled"] - ns["pooled_estimate"]) < 1e-15 and by["year_driven"] == ns["year_driven"] and by["any_year_driven"] == ns["any_year_driven"]
    assert {y: round(v, 15) for y, v in by["loo"].items()} == {y: round(v, 15) for y, v in ns["leave_one_out"].items()}
    # backward compatibility of the registry extension: S1 and S2 records give exactly what the old rule gives
    from multitest import bonferroni_adjust, holm_adjust

    real = registry.load_records(registry.LIVE_REGISTRY_PATH) if registry.LIVE_REGISTRY_PATH.exists() else []
    for pair in ("ETHUSDT", "BTCUSDT"):
        for step in ("discovery", "stability", "economic_gate"):
            got = registry.holm_at_step(real, pair, step)
            at = {}
            for r in registry.live_records(real, pair):
                if r["status"] == step and r["family"].split("-")[0] in ("S1", "S2"):
                    at[r["family"]] = r
            if not any(r["family"].startswith("Task3") for r in registry.live_records(real, pair)):
                ps = [float(at[f_].get("detail", {}).get("p_value")) if at[f_].get("detail", {}).get("p_value") is not None else float("nan") for f_ in at]
                want = holm_adjust(ps)
                assert list(got) == list(at) and all(abs(got[f_]["p_holm"] - want[i]) < 1e-15 or (np.isnan(want[i]) and np.isnan(got[f_]["p_holm"])) for i, f_ in enumerate(at)), "registry.holm_at_step changed for S1/S2"
    print(f"Self-test passed: run_t3 loads 5m files, truncates at the cutoff (0 post-cutoff rows), counts masked/zero-volume bars, builds the 48 cells with Holm over 48, classifies the two primary cells, "
          f"runs dose-response, stability, by-year and the robustness columns, writes exactly discovery + stability (each primary cell its own Holm entry), keeps the live registry behind --commit-to-registry, "
          f"writes nothing for the origin facts, compares derived and native 15m bars, and leaves registry.holm_at_step unchanged for S1/S2 records.")


def main() -> None:
    a = build_argparser().parse_args()
    if not a.pair:
        print("error: --pair is required (or --self-test)", file=sys.stderr)
        raise SystemExit(2)
    if a.origin_facts:
        print_origin_facts_report(origin_facts_for(a.pair, a.data_dir, a.raw_dir))
        return
    if a.variant_zero_volume:
        print_variant_zero_volume(a.pair, variant_zero_volume(a.pair, a.data_dir, a.raw_dir))
        return
    path = a.registry_path if a.registry_path is not None else (registry.LIVE_REGISTRY_PATH if a.commit_to_registry else registry.SCRATCH_REGISTRY_PATH)
    live = registry.is_live_registry(path)
    print(f"REGISTRY: {'LIVE' if live else 'scratch (live registry untouched)'} -> {path}", file=sys.stderr)
    if live and not a.commit_to_registry:
        print("error: the live registry needs --commit-to-registry", file=sys.stderr)
        raise SystemExit(2)
    print_report(run_t3(a.pair, a.data_dir, a.raw_dir, registry_path=path, commit_to_registry=a.commit_to_registry))


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        main()
