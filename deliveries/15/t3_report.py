"""
Task 3 report generator (Work Order 1.7 section 5, with M2's rulings of 2026-10-27). The twin of s1_report.py / s2_report.py. PRE-TAX.

READ-ONLY. It reads the 5m (and native 15m) data files and the LIVE registry (the two records per pair that the Task 3 live run wrote) and writes ONE
markdown report plus the trade-list CSVs of the two primary cells per pair; it never writes the registry. Everything in the report is RECOMPUTED here
with the production code (`run_t3.run_t3` into a throwaway scratch registry) and the report REFUSES to be produced unless the recomputed records equal
the live ones field by field (timestamps aside), so the report cannot disagree with the registry.

The report states recorded outcomes and descriptive statistics; it makes no recommendation (M2 interprets). No freeze, no forward test, the holdout is untouched.

  python3 t3_report.py --pair ETH_USDT --pair BTC_USDT --out ../../docs/reports/t3-report-step3.md --trades-dir ../../docs/reports/t3-trades \\
         --run-commit <live run commit> --code-commit <commit>
  python3 t3_report.py --self-test
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import formula_t3 as f3
import registry
import run_t3
from cutoff import CUTOFF
from s1_report import ReportConsistencyError, _f, _md_table

DEFAULT_DATA_DIR = run_t3.DEFAULT_DATA_DIR
PRIMARY = ("5m_k6_down", "5m_k6_up")


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _same(a, b, path: str, bad: list) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            bad.append(f"{path}: keys differ {sorted(set(a) ^ set(b))[:5]}")
            return
        for k in a:
            _same(a[k], b[k], f"{path}.{k}", bad)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            bad.append(f"{path}: lengths {len(a)} != {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{path}[{i}]", bad)
    elif isinstance(a, float) or isinstance(b, float):
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and (a == b or math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15) or (a != a and b != b))):
            bad.append(f"{path}: {a!r} != {b!r}")
    elif a != b:
        bad.append(f"{path}: {a!r} != {b!r}")


def exact_reproduction() -> dict:
    """Production code against the reference on make_returns(2935*288, default_rng(2026), 't4sv') (Work Order 1.7 section 4, row 1)."""
    ref = f3.load_reference()
    r = ref.make_returns(ref.NDAYS * 288, np.random.default_rng(2026), "t4sv")
    fr = f3.frame_from_returns(ref, r)
    prep = f3.prepare(fr, f3.W5)
    kept, side = f3.event_clock(prep, f3.THR)
    rk, rs = ref.event_clock(r)
    res, rr = f3.primary_results(fr, prep), ref.primary_results(r)
    diffs = {}
    for nm in ("down", "up"):
        a, b = res[nm]["stats"], rr[nm]["stats"]
        for key, (x, y) in {"mean": (a["mean"], b["mean"]), "se": (a["se"], b["se"]), "t": (a["t"], b["t"]), "T": (res[nm]["block"]["T"], rr[nm]["block"]["T"])}.items():
            diffs[f"{nm}.{key}"] = abs(x - y) / max(abs(y), 1e-300)
    return {"bars": len(r), "kept_identical": bool(np.array_equal(kept, rk) and np.array_equal(side, rs)), "kept_down": int((side == -1).sum()), "kept_up": int((side == 1).sum()),
            "n_down": res["down"]["stats"]["n"], "n_up": res["up"]["stats"]["n"], "mu6": res["mu"], "diffs": diffs, "max_diff": max(diffs.values())}


def _pair_section(pair: str, data_dir: Path, raw_dir: Path | None, live_records: list, trades_dir: Path | None, scratch: Path, loaded: dict | None = None,
                  loaded_present: dict | None = None) -> tuple[str, dict, dict]:
    family, reg_pair = run_t3.family_name(pair), pair.replace("_", "")
    idxs = [i for i in registry._live_indices(live_records, reg_pair) if live_records[i]["family"] == family]
    live = {live_records[i]["status"]: (i + 1, live_records[i]) for i in idxs}
    if sorted(live) != ["discovery", "stability"] or len(idxs) != 2:
        raise ReportConsistencyError(f"{family}: expected exactly one live discovery and one live stability record; found {[live_records[i]['status'] for i in idxs]}")

    L = loaded if loaded is not None else run_t3.load_pair(pair, data_dir, raw_dir)
    Lp = loaded_present if loaded_present is not None else run_t3.load_pair(pair, data_dir, raw_dir, mask_zero_volume=False)
    res = run_t3.run_t3(pair, data_dir, raw_dir, registry_path=scratch, loaded=L)  # throwaway scratch registry: never the live file
    re_recs = [r for r in registry.load_records(scratch) if r["family"] == family][-2:]
    bad: list = []
    for new, (_, old) in zip(re_recs, (live["discovery"], live["stability"])):
        _same({k: v for k, v in new.items() if k != "timestamp_utc"}, {k: v for k, v in old.items() if k != "timestamp_utc"}, f"{family}/{new['status']}", bad)
    if bad:
        raise ReportConsistencyError(f"the recomputed {family} records differ from the live registry: {bad[:6]}")

    cells, fac = res["cells"], res["facts"]
    f5, c15 = fac["facts5"], fac["cmp15"]
    var = run_t3.variant_zero_volume(pair, data_dir, raw_dir, masked_loaded=L, base_loaded=Lp)
    vm, vp = var["masked (primary)"], var["present (literal reading, sensitivity)"]
    c15_lit = Lp["cmp15"]

    # ---- 1. provenance
    prov = [
        f"- 5m file `{L['files']['5m'][0]}` sha256 `{L['files']['5m'][1]}`; native 15m file {('`' + str(L['files']['15m'][0]) + '` sha256 `' + L['files']['15m'][1] + '`') if L['files']['15m'][0] else 'none (the 15m bars are derived from 5m for both pairs)'}.",
        f"- 5m rows in the file before the cutoff truncation {L['rows_before_cutoff_truncation']}; rows in the discovery frame {f5['rows']}; regular grid {f5['grid']} bars from {f5['first']} to {f5['last']}; **rows after the cutoff in the discovery frame: {L['post_cutoff_rows']}**.",
        f"- Missing bars in the grid (primary reading, zero-volume bars masked): **{f5['missing'] }**, of which {f5['grid'] - f5['rows']} are absent from the file and **{f5['masked_zero_volume']}** are zero-volume placeholder rows masked as missing (M2's ruling 2 of 2026-10-27). Under the literal reading (placeholders present) {Lp['facts5']['missing']} bars are missing.",
    ]
    if c15 is not None:
        prov.append(f"- Derived 15m against the native 15m file (compared on every complete derived bar): primary reading {c15['compared_bars']} bars compared, open mismatches {c15['open_mismatches']}, close mismatches {c15['close_mismatches']}, present in the derived series only {c15['present_derived_missing_native']}, "
                    f"present natively only {c15['present_native_missing_derived']}; literal reading {c15_lit['compared_bars']} bars, open mismatches {c15_lit['open_mismatches']}, close mismatches {c15_lit['close_mismatches']}, derived only {c15_lit['present_derived_missing_native']}, native only {c15_lit['present_native_missing_derived']}. "
                    f"(M2's ruling 1: the native file is only a comparison; it was built with the traded-bar rule, which explains the differences.)")
    else:
        prov.append("- No native 15m file exists for this pair; nothing to compare.")

    # ---- 2. item-8 counts
    rows = []
    for tf in ("5m", "15m"):
        t = fac["tf"][tf]
        r = t["reasons"]
        for key, lab in (("z3", "|z| >= 3"), ("z4", "|z| >= 4")):
            k = t[key]
            rows.append([tf, lab, r["bars_in_grid"], r["bars_present"], r["bars_missing"], r["eligible_origins"], t["first_origin"].isoformat()[:16], t["last_origin"].isoformat()[:16],
                         f"{k['event_bars_down']} / {k['event_bars_up']}", f"{k['kept_down']} / {k['kept_up']}", f"{k['dropped_gap']} gap, {k['dropped_cutoff']} cutoff", f"{k['used_down']} / {k['used_up']}"])
    counts_table = _md_table(["timeframe", "threshold", "grid bars", "present", "missing", "eligible origins", "first origin", "last origin", "event bars before de-clustering (down / up)",
                              "kept after the shared clock (down / up)", "dropped for an incomplete window", "used in the statistics (down / up)"], rows)
    reasons_lines = "\n".join(f"- [{tf}] not an origin: z window {fac['tf'][tf]['reasons']['not_origin_z_window']}, target window (gap inside the frame) {fac['tf'][tf]['reasons']['not_origin_target_window_gap']}, "
                              f"cutoff (bar j+12 beyond the frame) {fac['tf'][tf]['reasons']['not_origin_cutoff']}; flags: {fac['tf'][tf]['flags'] or 'none'}" for tf in ("5m", "15m"))
    sb = fac["stability_blocks"]

    # ---- 3. mu table and 48 cells
    mu = res["mu_table"].pivot(index="k", columns="timeframe", values="mu")
    mu_table = _md_table(["k", "mu_k 5m (mean R_k over all eligible 5m origins)", "mu_k 15m"], [[int(k), _f(mu.loc[k, "5m"], ".6g"), _f(mu.loc[k, "15m"], ".6g")] for k in mu.index])
    cell_rows = []
    for _, c in cells.iterrows():
        flag = ("PRIMARY " if c["primary"] else "") + ("MDE > M" if c["mde"] > f3.M else "")
        cell_rows.append([c["timeframe"], int(c["k"]), c["side"], int(c["n"]), _f(c["mean_raw"], ".4g"), _f(c["mean_excess"], ".4g"), _f(c["se"], ".4g"), _f(c["se_naive"], ".4g"), _f(c["t"], ".3f"),
                          _f(c["p_value"], ".4g"), _f(c["p_holm"], ".4g"), _f(c["p_bonferroni"], ".4g"), _f(c["mde"], ".4g"), flag.strip()])
    cell_table = _md_table(["tf", "k", "side", "n", "mean raw R_k", "mean excess", "clustered SE", "naive SE", "t", "p (one-sided positive for the primary, two-sided otherwise)", "Holm (48)",
                            "Bonferroni (48)", "MDE (2.486 x SE)", "flag"], cell_rows)

    # ---- 4. classification with the literal-reading sensitivity
    cls_rows = []
    for cid in PRIMARY:
        p = res["primary"][cid]
        nm = "down" if cid.endswith("down") else "up"
        lit = vp["cells"][nm]
        cls_rows.append([cid, p["n"], _f(p["mean_excess"], ".6g"), _f(p["se"], ".6g"), _f(p["t"], ".3f"), _f(p["p_one"], ".4g"), _f(p["p_holm"], ".4g"), _f(p["mde"], ".4g"), _f(p["upper95"], ".4g"), p["classification"].upper(),
                         f"n {lit['n']}, mean {_f(lit['mean_excess'], '.6g')}, t {_f(lit['t'], '.3f')}, Holm {_f(lit['p_holm'], '.4g')}, {lit['classification'].upper()}"])
    cls_table = _md_table(["primary cell", "n", "mean excess", "clustered SE", "t", "one-sided p", "Holm (48)", "MDE", "mean + 1.645 SE", "classification (M = 0.0035)", "sensitivity: zero-volume bars present (literal reading)"], cls_rows)
    mask_lines = (f"- What masking removes: 5m bars present {vm['bars_present']} against {vp['bars_present']} ({vp['bars_present'] - vm['bars_present']} bars); eligible 5m origins {vm['eligible_origins']} against {vp['eligible_origins']} "
                  f"(**{vp['eligible_origins'] - vm['eligible_origins']}** fewer); events per primary cell: " + "; ".join(f"{('down' if cid.endswith('down') else 'up')} {res['primary'][cid]['n']} against {vp['cells']['down' if cid.endswith('down') else 'up']['n']} "
                  f"(**{vp['cells']['down' if cid.endswith('down') else 'up']['n'] - res['primary'][cid]['n']}** fewer)" for cid in PRIMARY) + ".")

    # ---- 5. dose-response
    dose_table = _md_table(["side", "|z| >= 3 mean excess (n)", "|z| >= 4 mean excess (n)", "verdict (M2's ruling 4: the discard rule only for a positive |z| >= 3 mean)"],
                           [[nm, f"{_f(d['z3_mean'], '.6g')} ({d['z3_n']})", f"{_f(d['z4_mean'], '.6g')} ({d['z4_n']})", d["verdict"]] for nm, d in res["dose"].items()])

    # ---- 6. stability
    holm_st = registry.holm_at_step(live_records, reg_pair, "stability")
    holm_di = registry.holm_at_step(live_records, reg_pair, "discovery")
    stab_blocks = ""
    for cid in PRIMARY:
        s = res["stability"][cid]
        stab_blocks += f"\n**{cid}**: T = {_f(s['T'], '.4f')}, p_stab = {_f(s['p_stab'], '.6g')}, B' = {s['B_used']} of {s['B_full']} full blocks, partial block {s['partial_days']:.1f} days.\n\n"
        stab_blocks += _md_table(["block", "start", "events", "t_b", "used (>= 30 events)"], [[b["block"], pd.Timestamp(b["start_sec"], unit="s", tz="UTC").date(), b["n"], _f(b["t_b"], ".3f"), b["used"]] for b in s["blocks"]]) + "\n"
    holm_rows = []
    for step, h in (("discovery", holm_di), ("stability", holm_st)):
        for name in sorted(h):
            holm_rows.append([step, name, _f(h[name]["p_raw"], ".6g"), _f(h[name]["p_holm"], ".6g")])
    holm_table = _md_table(["step", "candidate (family or family:cell)", "raw p", "Holm across candidates"], holm_rows)

    # ---- 7. by-year, robustness
    by_text = ""
    for cid in PRIMARY:
        by = res["extras"][cid]["by_year"]
        t = by["table"].copy()
        t["loo"] = t["year"].map(lambda y: by["loo"].get(y, np.nan))
        by_text += (f"\n**{cid}**: pooled mean excess {_f(by['pooled'], '.6g')}; any year-driven: **{by['any_year_driven']}** (year-driven flags: {by['year_driven']}); every judged year's own sign agrees with the pooled sign: {by['all_judged_years_agree']}.\n\n"
                    + _md_table(["year", "events", "days covered (calendar days with an eligible origin)", "mean excess", "clustered SE", "t", "judged (>= 120 days)", "pooled mean without that year"],
                                [[int(r["year"]), int(r["n"]), int(r["days_covered"]), _f(r["mean_excess"], ".6g"), _f(r["se"], ".4g"), _f(r["t"], ".3f"), bool(r["judged"]), _f(r["loo"], ".6g")] for _, r in t.iterrows()]) + "\n")
    rob_rows = []
    for cid in PRIMARY:
        rb = res["extras"][cid]["robustness"]
        a, b_, c_, fcost = rb["a_one_clock_per_side"], rb["b_mu_from_small_z_origins"], rb["c_entry_one_bar_late"], rb["f_raw_minus_costs"]
        p = res["primary"][cid]
        rob_rows.append([cid, f"{_f(p['mean_excess'], '.6g')} (t {_f(p['t'], '.2f')})", f"n {a['n']}: {_f(a['mean'], '.6g')} (t {_f(a['t'], '.2f')})", f"{_f(b_['mean'], '.6g')} (t {_f(b_['t'], '.2f')})",
                         f"{_f(c_['mean'], '.6g')} (t {_f(c_['t'], '.2f')})", f"{_f(p['se'], '.4g')} / {_f(p['se_naive'], '.4g')}", f"{_f(fcost['mean_raw'], '.6g')}; minus 0.24%: {_f(fcost['minus_base_cost'], '.6g')}; minus 0.30%: {_f(fcost['minus_stress_cost'], '.6g')}"])
    rob_table = _md_table(["primary cell", "(primary) mean excess", "(a) one clock per side", "(b) mu_6 from |z| < 3 origins", "(c) entry one bar late", "(d) clustered / naive SE", "(f) mean raw return, and minus round-trip costs (information)"], rob_rows)
    hours_lines = "\n".join(f"- {cid}: {res['extras'][cid]['robustness']['g_utc_hours']}" for cid in PRIMARY)

    # ---- 8. trade lists and gut checks
    trade_lines, files = [], {}
    for cid in PRIMARY:
        tr = res["extras"][cid]["trades"]
        if len(tr) != res["primary"][cid]["n"]:
            raise ReportConsistencyError(f"{cid}: trade list has {len(tr)} rows, the cell has n = {res['primary'][cid]['n']}")
        name = f"t3-trades-{pair}-{cid}.csv"
        csv = tr.to_csv(index=False)
        if trades_dir is not None:
            trades_dir.mkdir(parents=True, exist_ok=True)
            (trades_dir / name).write_text(csv)
        trade_lines.append(f"- `{name}`: {len(tr)} rows, sha256 `{_sha_bytes(csv.encode())}`")
        files[cid] = tr
    c5 = cells[cells["timeframe"] == "5m"]
    ratio = max(res["primary"][c]["n"] for c in PRIMARY) / max(1, min(res["primary"][c]["n"] for c in PRIMARY))
    gut = [
        f"- No look-ahead: z uses returns r_(j-W)..r_(j-1) only (the event bar's own return is excluded), the decision is at the close of bar j and the entry at the open of bar j+1, the clock never looks at later bars (self-tests, exact reproduction of the reference).",
        f"- Bug signals: kept events (used) down {res['primary'][PRIMARY[0]]['n']} / up {res['primary'][PRIMARY[1]]['n']} (none missing); sides differ by a factor {ratio:.2f} (signal above 1.5: {'YES' if ratio > 1.5 else 'no'}); "
        f"largest |mean excess| among the 5m cells at k = 12 (60 minutes) {_f(c5[c5['k'] == 12]['mean_excess'].abs().max(), '.4g')} (signal above 0.01: {'YES' if c5[c5['k'] == 12]['mean_excess'].abs().max() > 0.01 else 'no'}); cells with MDE above M: "
        f"{int((cells['mde'] > f3.M).sum())} of 48; cells with a p-value of exactly 0 or 1: {int(((cells['p_value'] == 0) | (cells['p_value'] == 1)).sum())}.",
        f"- Microstructure (robustness column c, entry one bar late): " + "; ".join(f"{cid} {_f(res['extras'][cid]['robustness']['c_entry_one_bar_late']['mean'], '.6g')} (t {_f(res['extras'][cid]['robustness']['c_entry_one_bar_late']['t'], '.2f')}) against {_f(res['primary'][cid]['mean_excess'], '.6g')} on the primary entry" for cid in PRIMARY) + ".",
        "- Shared latent state: the excess is measured against one global constant mu_k per timeframe, the SE is clustered by UTC day of the entry bar; no raw mean is quoted as an effect.",
    ]

    text = f"""## {pair}  ({family})  -- pre-tax

### 1. Provenance
{chr(10).join(prov)}

### 2. Counts (item 8)
{counts_table}

{reasons_lines}
- Stability tiling: t0 = {sb['t0']} (entry time of the first eligible 5m origin); {sb['full_90d_blocks']} full 90-day blocks; partial block {sb['partial_days']:.1f} days.

### 3. mu_k table
{mu_table}

### 4. The 48 cells (family size 48; Holm and Bonferroni over all 48; primary cells one-sided positive, the other 46 two-sided and descriptive)
{cell_table}

### 5. Classification of the two primary cells (5m, k = 6)
{cls_table}

{mask_lines}

### 6. Dose-response (5m, k = 6, |z| >= 4 with its own fresh clock)
{dose_table}

### 7. Stability (event statistic; 90-day calendar blocks from the first eligible 5m origin)
{stab_blocks}
Across-candidate Holm (R1; S1, S2 and each Task 3 primary cell are candidates for this pair; the discovery-step Holm is informational, the pass criterion is the Holm over 48):

{holm_table}

### 8. By-year and leave-one-year-out (primary cells; years under 120 days are shown, not judged)
{by_text}
### 9. Robustness columns (descriptive; none is the primary statistic)
{rob_table}

Kept events by UTC hour of the event bar (24 counts, hour 0 first):
{hours_lines}

### 10. Trade lists (pre-tax; one row per kept event with a complete window)
{chr(10).join(trade_lines)}
Columns: pair, cell, event_bar_time_utc, entry_time_utc (open of bar j+1), exit_time_utc (close of bar j+6), entry_price (O_(j+1)), exit_price (C_(j+6)), gross_log_return, excess.

### 11. Gut-checks
{chr(10).join(gut)}
"""
    summary = {"pair": pair, "cells": {cid: res["primary"][cid] for cid in PRIMARY}, "stab": res["stability"], "dose": res["dose"], "n_mde_above_M": int((cells["mde"] > f3.M).sum()),
               "origins_masked": vm["eligible_origins"], "origins_present": vp["eligible_origins"], "year_driven": {cid: res["extras"][cid]["by_year"]["any_year_driven"] for cid in PRIMARY}}
    return text, summary, files


CHOICES = [
    "PRE-TAX. The trade lists exist so that a later after-tax layer can be computed from dated trades.",
    "Bars and masking (M2's ruling 2, 2026-10-27, PRIMARY): a 5m bar is present iff open, high, low and close exist and its volume is not zero; a zero-volume placeholder is treated exactly like a missing bar (no return for it or for the next bar, every z window containing it invalid, a target window containing it incomplete, a 15m bin containing it missing, excluded from mu_k). The literal reading (placeholders present) is the labeled sensitivity next to each primary cell.",
    "15m bars (M2's ruling 1): derived from 5m by the order's rule for both pairs (a 15m bin with any of its three 5m bars missing is missing); the native BTC 15m file is only a comparison.",
    "z: sample sd (ddof 1) of the W = 288 (5m) / 96 (15m) previous returns, the event bar's own return excluded; eligible iff r_j and all W previous returns are unmasked and sd > 0; event: |z| >= 3 (down z <= -3, up z >= +3); decision at the close of bar j, entry at the open of bar j+1.",
    "Clock: one shared clock per timeframe and pair, scanned in time order over the eligible event bars (keep the first, ignore every event bar before j+13); a kept event whose target window later proves incomplete stays on the clock and is dropped from the statistics (counted); one clock per side is a labeled variant.",
    "Targets and baseline: R_k = ln(C_(j+k) / O_(j+1)), k = 1..12; an event with any of the bars j+1..j+12 missing is excluded from all k; mu_k = mean of R_k over ALL eligible origins (bars j+1..j+12 present, event bars included), a constant per timeframe; excess e = R_k - mu_k; the |z| < 3 baseline and the one-bar-late entry are labeled variants.",
    "Statistics: day-clustered SE (clusters = UTC calendar days of the entry bar), naive SE reported next to it, normal p-values (survival function), MDE = 2.486 x SE; the two primary cells are one-sided positive, the other 46 two-sided; Holm and Bonferroni over all 48 cells of the pair; classification (M = 0.0035): PASS = Holm(48) one-sided p < 0.05 and mean excess >= M; DEAD = mean + 1.645 SE < M and MDE <= M; otherwise INCONCLUSIVE.",
    "Dose-response (M2's ruling 4): |z| >= 4 with a fresh shared clock; for a cell whose |z| >= 3 mean excess is positive the |z| >= 3 result is discarded if the |z| >= 4 mean excess is smaller and the |z| >= 4 sample has at least 30 events (fewer: not evaluable, flagged); a cell with a non-positive |z| >= 3 mean prints 'n/a: no positive effect'.",
    "Stability: per primary cell, 90-calendar-day blocks tiled from the entry time of the first eligible 5m origin; a block is scored only if its whole window lies inside [t0, entry time of the last eligible 5m origin + 5 minutes]; blocks with fewer than 30 events are listed and excluded; t_b = mean(e) / (sd(e) / sqrt(n_b)); T = sum t_b / sqrt(B'); p_stab = 1 - Phi(T).",
    "Registry (M2's ruling 3): family Task3-<PAIR> with two records (discovery, stability); each primary cell is its own across-candidate Holm entry at both steps (raw one-sided p and raw p_stab); the discovery-step Holm is informational. S1's and S2's across-candidate rows changed by design once these records existed.",
    "By-year: calendar years of the entry bar; 'days covered' counts calendar days with an eligible origin in that year (an event-day count would undercount sparse events); years under 120 days are shown, not judged; year-driven = dropping the year cuts the pooled mean by more than half or flips its sign (a NaN leave-one-out is never year-driven).",
    "Cutoff: every file is truncated at the cutoff before any computation; a bar whose window would extend past the frame's last bar is not an origin (counted separately as 'cutoff').",
    "Nothing in this report is a recommendation, and no result is described as a discovery. Freeze and forward test were not run; the holdout is untouched.",
]


def build_report(pairs: list[str], data_dir: Path, raw_dir: Path | None, registry_path: Path, trades_dir: Path | None, run_commit: str, code_commit: str = "unknown",
                 acceptance_path: Path | None = None, regression_path: Path | None = None, checks_path: Path | None = None, repro: dict | None = None,
                 loaded: dict | None = None, loaded_present: dict | None = None) -> str:
    """The markdown report. Raises ReportConsistencyError if a recomputed record differs from the live registry; FileNotFoundError if a data file is missing."""
    records = registry.load_records(registry_path)
    sections, summaries = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for pair in pairs:
            text, summ, _ = _pair_section(pair, data_dir, raw_dir, records, trades_dir, Path(tmp) / f"scratch-{pair}.jsonl",
                                          loaded=(loaded or {}).get(pair), loaded_present=(loaded_present or {}).get(pair))
            sections.append(text)
            summaries.append(summ)
    srows = []
    for s in summaries:
        for cid in PRIMARY:
            c, st = s["cells"][cid], s["stab"][cid]
            srows.append([s["pair"], cid, c["n"], _f(c["mean_excess"], ".6g"), _f(c["t"], ".3f"), _f(c["p_one"], ".4g"), _f(c["p_holm"], ".4g"), _f(c["mde"], ".4g"), c["classification"].upper(),
                          _f(st["T"], ".3f"), _f(st["p_stab"], ".4g"), f"{st['B_used']} of {st['B_full']}", s["year_driven"][cid], s["n_mde_above_M"]])
    top = _md_table(["pair", "primary cell", "n", "mean excess", "t", "one-sided p", "Holm (48)", "MDE", "classification", "stability T", "p_stab", "B' of full blocks", "any year-driven", "cells with MDE > M (of 48)"], srows)
    acc = ""
    if acceptance_path is not None and acceptance_path.exists():
        lines = [ln for ln in acceptance_path.read_text().splitlines() if ln.strip().startswith(("PASS", "info", "FAIL", "null", "edge", "total")) or ln.startswith(("ALL TASK", "SOME TASK", "Task 3 acceptance"))]
        acc = "\n".join("    " + ln for ln in lines)
    reg = ""
    if regression_path is not None and regression_path.exists():
        reg = "\n".join("    " + ln[:240] for ln in regression_path.read_text().splitlines() if "regression" in ln or "PASSED" in ln or "FAILED" in ln)
    chk = ""
    if checks_path is not None and checks_path.exists():
        chk = "\n".join("    " + ln[:240] for ln in checks_path.read_text().splitlines() if ln.strip())
    rep = ""
    if repro is not None:
        rep = (f"Exact reproduction of the reference (seed 2026, t4sv, {repro['bars']} bars): kept events identical to the reference's: **{repro['kept_identical']}** (down {repro['kept_down']}, up {repro['kept_up']}); n per side {repro['n_down']} / {repro['n_up']}; "
               f"mu_6 {repro['mu6']:.10f}; relative differences of mean excess, SE, t and T (down, up): " + ", ".join(f"{k} {v:.1e}" for k, v in repro["diffs"].items()) + f"; largest {repro['max_diff']:.1e} (the order requires below 1e-8).")
    choices = "\n".join(f"{i}. {c}" for i, c in enumerate(CHOICES, 1))
    return f"""# Task 3 report: ETH_USDT and BTC_USDT (Work Order 1.7 section 5) -- PRE-TAX

Generated {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')} by `t3_report.py` (read-only) at repo commit {code_commit}. Registry records are from the Task 3 live run, commit {run_commit}, written once per pair. Every figure below was recomputed from the discovery data with the production code and the recomputed records equal the live registry's field by field (the generator refuses to run otherwise). Freeze and forward test were not run; the holdout is untouched. This report states recorded outcomes and descriptive statistics; it makes no recommendation. M2's rulings of 2026-10-27 (`docs/correspondence/answer-t3-rulings.md`) override Work Order 1.7 where they differ.

### Summary of the primary cells (masked reading; M = 0.0035 on the excess)
{top}

### Acceptance results (Work Order 1.7 section 4), exact reproduction and checks
{rep or 'Exact reproduction was not recomputed in this build of the report (self-test run).'}

Full acceptance run on the owner's machine (`docs/reports/t3-acceptance-full-step1.txt`):

{acc or '    (file not provided in this build)'}

Checks of the live-run delivery (`docs/reports/t3-checks-step3.txt`):

{chk or '    (file not provided in this build)'}

### S1 / S2 regression result (`docs/reports/t3-regression-after-t3-step3.txt`)
The S1 and S2 reports were regenerated before any Task 3 record existed (S1 equal to the recorded post-S2 state, S2 equal to the committed report) and again after the live write (summary tables identical except the Holm-across-candidates column; only the across-candidate Holm rows and cumulative counts changed, by design):

{reg or '    (file not provided in this build)'}

{chr(10).join(sections)}

## 12. Interpretation choices (all of them)
{choices}
"""


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Write the Task 3 report (read-only; reads data and the live registry).")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--pair", action="append", choices=["ETH_USDT", "BTC_USDT"])
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--raw-dir", type=Path, default=None)
    p.add_argument("--registry-path", type=Path, default=registry.LIVE_REGISTRY_PATH)
    p.add_argument("--out", type=Path)
    p.add_argument("--trades-dir", type=Path)
    p.add_argument("--run-commit", default="unknown")
    p.add_argument("--code-commit", default="unknown")
    p.add_argument("--acceptance", type=Path, default=None)
    p.add_argument("--regression", type=Path, default=None)
    p.add_argument("--checks", type=Path, default=None)
    p.add_argument("--skip-repro", action="store_true", help="do not recompute the exact reproduction (about half a minute)")
    return p


def _self_test() -> None:
    ref = f3.load_reference()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_dir = tmp / "binance"
        data_dir.mkdir()
        for pair, seed in (("ETH_USDT", 5), ("BTC_USDT", 6)):
            run_t3._synthetic_5m(ref, seed=seed, drop=[20000, 20001, 30000], zero_vol=[10, 11, 500]).reset_index().to_feather(data_dir / f"{pair}-5m.feather")
        reg = tmp / "registry.jsonl"
        for pair in ("ETH_USDT", "BTC_USDT"):
            run_t3.run_t3(pair, data_dir, registry_path=reg)
        out_dir = tmp / "trades"
        text = build_report(["ETH_USDT", "BTC_USDT"], data_dir, None, reg, out_dir, "abc1234", "def5678")
        assert "PRE-TAX" in text and "Task3-ETHUSDT" in text and "Task3-BTCUSDT" in text and "makes no recommendation" in text and "Interpretation choices" in text
        assert "found" not in text.lower().replace("not found", ""), "no 'found' language"
        for pair in ("ETH_USDT", "BTC_USDT"):
            for cid in PRIMARY:
                tr = pd.read_csv(out_dir / f"t3-trades-{pair}-{cid}.csv")
                assert list(tr.columns) == ["pair", "cell", "event_bar_time_utc", "entry_time_utc", "exit_time_utc", "entry_price", "exit_price", "gross_log_return", "excess"] and len(tr) > 10
                assert (pd.to_datetime(tr["exit_time_utc"]) > pd.to_datetime(tr["entry_time_utc"])).all() and np.allclose(tr["gross_log_return"], np.log(tr["exit_price"] / tr["entry_price"]))
                assert f"t3-trades-{pair}-{cid}.csv`: {len(tr)} rows" in text
        # refuses a tampered record, an incomplete family and a missing data file
        import json

        lines = reg.read_text().splitlines()
        rec = json.loads(lines[0])
        rec["detail"]["primary_cells"]["5m_k6_up"]["mean_excess"] *= 1.01
        bad = tmp / "tampered.jsonl"
        bad.write_text("\n".join([json.dumps(rec)] + lines[1:]) + "\n")
        try:
            build_report(["ETH_USDT"], data_dir, None, bad, None, "x")
        except ReportConsistencyError:
            pass
        else:
            raise AssertionError("a tampered discovery record must be refused")
        short = tmp / "short.jsonl"
        short.write_text(lines[0] + "\n")
        try:
            build_report(["ETH_USDT"], data_dir, None, short, None, "x")
        except ReportConsistencyError:
            pass
        else:
            raise AssertionError("an incomplete family must be refused")
        try:
            build_report(["ETH_USDT"], tmp / "nowhere", None, reg, None, "x")
        except (FileNotFoundError, KeyError, OSError):
            pass
        else:
            raise AssertionError("a missing data file must be refused")
    print("Self-test passed: t3_report builds the PRE-TAX two-pair Task 3 report from synthetic 5m data and a registry written by run_t3, recomputes every record and requires it to equal the registry, "
          "writes one trade-list CSV per primary cell (columns per the order), contains no 'found' language, and refuses a tampered record, an incomplete family and a missing data file.")


def main() -> None:
    a = build_argparser().parse_args()
    if a.self_test:
        _self_test()
        return
    if not a.pair or a.out is None:
        build_argparser().error("--pair and --out are required")
    repro = None if a.skip_repro else exact_reproduction()
    text = build_report(a.pair, a.data_dir, a.raw_dir, a.registry_path, a.trades_dir, a.run_commit, a.code_commit, a.acceptance, a.regression, a.checks, repro)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(f"wrote {a.out} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
