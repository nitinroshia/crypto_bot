"""
Orchestration script: runs S2 (`formula_s2.py`) through item 2's pipeline -- discovery (2 cells, Holm within the 2) ->
stability check (primary cell, time-shift null) -> economic gate (stress cost) -- for one pair, writing each step's
result to the registry. The S2 twin of run_s1.py; Work Order 1.6.

DELIBERATELY STOPS AFTER THE ECONOMIC GATE: freeze_manifest.py, holdout_lock.py and forward_test.py are never imported
here. The holdout unlock is one-shot and has never been used.

REGISTRY HYGIENE (Work Order 1.5 step 2): by default this script writes to a SCRATCH registry (temp/scratch-registry.jsonl)
or to the file given with --registry-path (any non-live file). It writes the LIVE registry only with --commit-to-registry.
Exactly three records per run: S2-<PAIR> at discovery, stability, economic_gate. Labeled variants (gate literal reading, the 24h
stability, rank robustness, extremes, by-year) are computed and returned for the report but NEVER recorded.

USAGE (needs {pair}-1h, {pair}-1d and {pair}-funding feather files under --data-dir or --raw-dir):
    python3 run_s2.py --pair ETH_USDT --origin-facts                  # read-only facts: no registry, no p-values, no returns
    python3 run_s2.py --pair ETH_USDT --registry-path ../../temp/dry.jsonl   # dry run, non-live registry
    python3 run_s2.py --pair ETH_USDT --commit-to-registry            # LIVE registry (explicit flag; step 2 live run only)
    python3 run_s2.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import blocks
import formula_s1
import formula_s2
import funding
import nonstationarity
import registry
from cutoff import CUTOFF
from formula_s2 import family_name  # noqa: F401  (re-exported: S2-ETHUSDT / S2-BTCUSDT)
from rule_evaluator import STRESS_COST_PER_SIDE

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "user_data" / "data" / "binance"


def _iso(ts) -> str | None:
    return None if ts is None else pd.Timestamp(ts).isoformat()


def _cells_records(cells: pd.DataFrame) -> list[dict]:
    out = []
    for rec in cells.to_dict(orient="records"):
        out.append({k: (int(v) if isinstance(v, (np.integer,)) else float(v) if isinstance(v, (np.floating,)) else v) for k, v in rec.items()})
    return out


def _funding_facts(native: pd.DataFrame, obs: pd.DataFrame) -> dict:
    nat = funding.describe_native(native)
    d = funding.describe_observations(obs)
    ts = d.get("tie_share_up_to_cutoff", {})
    return {
        "first_settlement": nat.get("first_settlement"), "last_settlement": nat.get("last_settlement"),
        "native_rows": nat.get("rows"), "interval_hours_counts": nat.get("interval_hours_counts"),
        "interval_changes": nat.get("interval_changes"),
        "observations": d.get("observations"), "complete": d.get("complete"), "masked": d.get("masked"),
        "touched_by_interval_change": d.get("touched_by_interval_change"),
        "tie_share": ts.get("tie_share"), "tie_modal_value": ts.get("modal_value"), "tie_n": ts.get("n"),
    }


def _origin_detail(rep: dict) -> dict:
    return {
        "first_origin": _iso(rep["first_origin"]), "last_origin": _iso(rep["last_origin"]),
        "n_origins": int(rep["n_origins"]), "n_nominal": int(rep["n_nominal"]), "n_excluded": int(rep["n_excluded"]),
        "excluded_by_reason": {k: int(v) for k, v in rep["excluded_by_reason"].items()},
        "n_full_blocks": int(rep["n_full_blocks"]), "partial_block_origins": int(rep["partial_block_origins"]),
    }


def build_pair(pair: str, data_dir: Path, raw_dir: Path | None = None, inputs: dict | None = None) -> dict:
    """Everything computed from the (truncated) data, no registry: used by the run, the origin facts and the report."""
    inp = inputs if inputs is not None else formula_s2.load_discovery_inputs(data_dir, pair, raw_dir)
    if any(inp["post_cutoff_rows"].values()):
        raise ValueError(f"post-cutoff rows in the discovery frames: {inp['post_cutoff_rows']}")
    obs = funding.funding_observations(inp["native"])
    oset = formula_s2.s2_origin_set(obs, inp["df1h"])
    if len(oset["origins"]) == 0:
        raise ValueError(f"no common origins for {pair}")
    return {"inputs": inp, "obs": obs, "oset": oset, "origin_report": formula_s2.origin_report(oset)}


def run_s2(
    pair: str,
    data_dir: Path,
    raw_dir: Path | None = None,
    registry_path: Path = registry.DEFAULT_REGISTRY_PATH,
    commit_to_registry: bool = False,
    stability_R: int = formula_s2.STABILITY_R,
    stability_seed: int = formula_s2.STABILITY_SEED,
    inputs: dict | None = None,
) -> dict:
    """Run S2's discovery, stability check and economic gate for `pair`, appending exactly three records. Returns all
    figures (recorded and labeled variants) for review. Does NOT freeze or forward-test."""
    family = family_name(pair)
    registry_pair = pair.replace("_", "")
    b = build_pair(pair, data_dir, raw_dir, inputs)
    inp, obs, oset, rep = b["inputs"], b["obs"], b["oset"], b["origin_report"]
    df1h, df1d = inp["df1h"], inp["df1d"]
    origins = oset["origins"]
    first_origin = origins[0]
    xy = formula_s2.s2_xy(oset, df1h, df1d)
    ffacts = _funding_facts(inp["native"], obs)

    # ---- Step 1: discovery, both cells on one common origin set, HAC lags 4 x H/8h, Holm within the 2. ----
    interval_h = min(float(k) for k in (ffacts["interval_hours_counts"] or {"8.0": 1}))
    cells = formula_s2.discovery_cells(xy, interval_h)
    sensitivity = formula_s2.sensitivity_superseded_lags(xy)  # labeled, never recorded, never used for a decision
    primary = cells[cells["H"] == formula_s2.PRIMARY_H].iloc[0]
    registry.append_record(
        {
            "family": family, "pair": registry_pair, "status": "discovery", "timestamp_utc": registry.new_timestamp(),
            "detail": {
                "p_value": float(primary["p_value"]), "family_p_holm": float(primary["p_holm"]),
                "family_p_bonferroni": float(primary["p_bonferroni"]),
                "slope": float(primary["slope"]), "dispersion": float(primary["se"]), "n": int(primary["n"]),
                "origins": _origin_detail(rep), "funding": ffacts, "post_cutoff_rows": inp["post_cutoff_rows"],
                "all_cells": _cells_records(cells),
            },
        },
        registry_path, commit_to_registry=commit_to_registry,
    )

    # ---- Step 2: stability (primary cell, circular time-shift null). ----
    st = formula_s2.s2_stability(xy, origins, R=stability_R, seed=stability_seed)
    registry.append_record(
        {
            "family": family, "pair": registry_pair, "status": "stability", "timestamp_utc": registry.new_timestamp(),
            "detail": {
                "p_value": float(st["p_stab"]), "T": float(st["T"]), "B": int(st["B"]), "R": int(st["R"]), "seed": int(st["seed"]),
                "min_shift": int(st["min_shift"]), "horizon_h": int(st["horizon_h"]),
                "n_origins": int(st["n_origins"]), "n_origins_in_blocks": int(st["n_origins_in_blocks"]),
                "partial_block_origins": int(st["partial_block_origins"]),
                "share_blocks_positive": float(st["share_blocks_positive"]), "s_b": [float(v) for v in st["s_b"]],
                "passes": bool(st["passes"]), "statistic": "amended stability check, Work Order 1.5 section 3, S2 time-shift variant",
            },
        },
        registry_path, commit_to_registry=commit_to_registry,
    )

    # ---- Step 3: economic gate at stress cost, PRIMARY rule (M2's ruling of 2026-10-23: cash only for an invalid rank);
    # the order's literal reading is a labeled variant, never recorded. ----
    sigA, infoA = formula_s2.s2_signal(oset, df1h, "primary")
    gA = formula_s2.run_gate(df1h, first_origin, sigA, STRESS_COST_PER_SIDE)
    econ = gA["gate"]
    registry.append_record(
        {
            "family": family, "pair": registry_pair, "status": "economic_gate", "timestamp_utc": registry.new_timestamp(),
            "detail": {
                "pooled_net_return": econ["pooled_net_return"], "pass_rate": econ["pass_rate"],
                "passes_pooled": econ["passes_pooled"], "passes_block_rate": econ["passes_block_rate"], "passes": econ["passes"],
                "rule_mode": "primary", "late_executions": int(infoA["late_executions"]), "signal_changes": int(infoA["signal_changes"]),
                "n_trades": int(gA["strategy"]["n_trades"]), "cash_masked_rank_settlements": int(infoA["cash_masked_rank_settlements"]),
            },
        },
        registry_path, commit_to_registry=commit_to_registry,
    )

    # ---- Labeled variants: computed for the report, never recorded. ----
    sigB, infoB = formula_s2.s2_signal(oset, df1h, "literal")
    gB = formula_s2.run_gate(df1h, first_origin, sigB, STRESS_COST_PER_SIDE)
    st24 = formula_s2.s2_stability(xy, origins, R=stability_R, seed=stability_seed, horizon=24)
    ns = nonstationarity.non_stationarity_report(xy, formula_s2.make_primary_estimator(xy))
    return {
        "family": family, "pair": registry_pair, "n_discovery": int(primary["n"]),
        "discovery_estimate": float(primary["slope"]), "dispersion": float(primary["se"]),
        "cells": cells, "sensitivity": sensitivity, "origins": rep, "funding": ffacts, "stability": st, "economic_gate": econ, "gate_detail": gA, "gate_info": infoA,
        "variants": {"gate_literal": gB, "gate_info_literal": infoB, "stability_24h": st24},
        "rank_variants": formula_s2.rank_variants_primary(xy), "extremes": formula_s2.extremes_table(xy), "by_year": ns,
        "post_cutoff_rows": inp["post_cutoff_rows"],
    }


# ----------------------------------------------------------------------------- read-only origin facts
def origin_facts_for(pair: str, data_dir: Path, raw_dir: Path | None = None, inputs: dict | None = None) -> dict:
    """READ-ONLY facts for `pair` (Work Order 1.6 step 1/5/6): funding file facts, tie share, the common origin set,
    exclusions by reason, blocks, the cutoff check, 1h/1d gaps and the gate segment. Computes no p-values and no returns
    (the origin set needs only which bars exist); writes nothing."""
    b = build_pair(pair, data_dir, raw_dir, inputs)
    inp, obs, oset, rep = b["inputs"], b["obs"], b["oset"], b["origin_report"]
    df1h, df1d = inp["df1h"], inp["df1d"]
    origins = oset["origins"]
    grid = oset["grid"]
    first_pos = oset["first_position"]
    hours = pd.date_range(df1h.index[0], df1h.index[-1], freq="1h")
    days = pd.date_range(df1d.index[0], df1d.index[-1], freq="1D")
    tA, vA = formula_s2.gate_decisions(oset, df1h, "primary")
    tB, vB = formula_s2.gate_decisions(oset, df1h, "literal")
    gate_tiles = blocks.tile_blocks(df1h, origins[0])
    gate_full = [t for t in gate_tiles if not t["is_final_partial"]]
    struct_full = [bl for bl in rep["structure"]["blocks"] if bl["is_full"]]
    gate_same = len(gate_full) == len(struct_full) and all(g["start"] == m["start"] and g["end"] == m["end"] for g, m in zip(gate_full, struct_full))
    return {
        "pair": pair, "funding": _funding_facts(inp["native"], obs), "dropped_rows": inp["dropped_rows"], "post_cutoff_rows": inp["post_cutoff_rows"],
        "grid_first": grid[0], "grid_last": grid[-1], "grid_n": int(len(grid)), "slot_272": grid[first_pos],
        "first_origin_is_first_settlement_plus_271x8h": bool(origins[0] == grid[0] + 271 * pd.Timedelta(hours=8)),
        "last_bar_1h": oset["last_bar"], "last_origin_limit": oset["limit"],
        "file_1h": {"rows": int(len(df1h)), "first": df1h.index[0], "last": df1h.index[-1], "missing_hours": int(len(hours) - len(df1h))},
        "file_1d": {"rows": int(len(df1d)), "first": df1d.index[0], "last": df1d.index[-1], "missing_days": int(len(days) - len(df1d))},
        "origins": rep, "gate_decisions": {"settlements_in_segment": int(len(tA)), "long_primary": int(vA.sum()), "long_literal": int(vB.sum()), "differ_primary_vs_literal": int((vA != vB).sum()),
                           "cash_masked_rank": int((~np.isfinite(oset["rank_mid"][np.asarray(oset["grid"] >= origins[0])])).sum())},
        "gate_full_blocks": len(gate_full), "gate_blocks_same_as_origin_blocks": bool(gate_same),
        "gate_partial_days": int((df1h.index[-1] + pd.Timedelta(hours=1) - gate_tiles[-1]["start"]).days) if gate_tiles and gate_tiles[-1]["is_final_partial"] else 0,
    }


def print_origin_facts_report(f: dict) -> None:
    r, ff = f["origins"], f["funding"]
    print(f"\n=== S2 origin facts: {f['pair']} ===")
    print(f"funding native file: {ff['native_rows']} rows up to the cutoff, first settlement {ff['first_settlement']}, last {ff['last_settlement']}; "
          f"interval hours (counts): {ff['interval_hours_counts']}; interval changes: {len(ff['interval_changes'] or [])}")
    print(f"8h observations: {ff['observations']} (complete {ff['complete']}, masked {ff['masked']}, touched by an interval change {ff['touched_by_interval_change']}); "
          f"tie share at the modal value {ff['tie_modal_value']}: {ff['tie_share']:.4f} of {ff['tie_n']} (expect about 0.396 ETH, 0.401 BTC)")
    print(f"rows dropped by the cutoff (funding / 1h / 1d): {f['dropped_rows']['funding']} / {f['dropped_rows']['1h']} / {f['dropped_rows']['1d']}; "
          f"rows after the cutoff left in the discovery frames: {f['post_cutoff_rows']} (must all be 0)")
    print(f"settlement grid: {f['grid_n']} slots, {f['grid_first']} .. {f['grid_last']}; slot 272 = {f['slot_272']}")
    print(f"1h file (discovery): {f['file_1h']['rows']} rows {f['file_1h']['first']} .. {f['file_1h']['last']}, missing hours inside: {f['file_1h']['missing_hours']}")
    print(f"1d file (discovery): {f['file_1d']['rows']} rows {f['file_1d']['first']} .. {f['file_1d']['last']}, missing days inside: {f['file_1d']['missing_days']}")
    print(f"first origin: {r['first_origin']}   (= first settlement + 271 x 8h: {f['first_origin_is_first_settlement_plus_271x8h']})")
    print(f"last origin: {r['last_origin']}   (last settlement with s+1h+72h <= last 1h bar {f['last_bar_1h']}, i.e. s <= {f['last_origin_limit']}; expected 2025-08-28 16:00)")
    print(f"nominal origins: {r['n_nominal']}   usable: {r['n_origins']}   excluded: {r['n_excluded']}   by reason: {r['excluded_by_reason']}")
    print(f"span {r['span_days']} days; full {formula_s2.BLOCK_DAYS}-day blocks: {r['n_full_blocks']} (stricter cross-check: {r['n_full_blocks_strict_check']}); "
          f"partial block origins: {r['partial_block_origins']}; origins per full block (min/median/max): "
          f"{r['block_origins_min']}/{r['block_origins_median']}/{r['block_origins_max']}")
    print("expected by Work Order 1.6 before gap exclusions: about 6,269 origins and 23 full blocks (BTC), about 6,035 and 22 (ETH); 270 per full block")
    g = f["gate_decisions"]
    print(f"gate segment: {g['settlements_in_segment']} settlements from the first origin; long decisions primary {g['long_primary']}, literal {g['long_literal']}; settlements where they differ: {g['differ_primary_vs_literal']}; "
          f"settlements held in cash because rank_s is invalid: {g['cash_masked_rank']}")
    print(f"economic gate tiling (blocks.tile_blocks over the 1h discovery rows from the first origin): full blocks {f['gate_full_blocks']}, "
          f"same full blocks as the origin-based tiling: {f['gate_blocks_same_as_origin_blocks']}; its partial block runs {f['gate_partial_days']} days")
    print("(no p-values or returns are computed here; nothing is written)")


# ----------------------------------------------------------------------------- report printing
def print_report(res: dict) -> None:
    print(f"\n=== S2 run: {res['family']} ({res['pair']}) ===")
    print("\n-- Discovery (2 cells, one common origin set, HAC lags 4 x H/8h = 12 and 36, Holm within the 2; one-sided p in the NEGATIVE direction) --")
    cols = ["H", "hac_lags", "slope", "se", "corr", "t_stat", "p_value", "p_holm", "p_bonferroni", "mde", "n"]
    print(res["cells"][cols].to_string(index=False))
    print("labeled sensitivity, superseded lags 3 and 9 (delivery 8's figures; not used for any decision):")
    print(res["sensitivity"].to_string(index=False))
    print(f"Primary cell (H = {formula_s2.PRIMARY_H}h): slope={res['discovery_estimate']:.6g}  HAC SE={res['dispersion']:.6g}  n={res['n_discovery']}")
    print("\n-- Rank robustness, primary cell (labeled, never recorded) --")
    print(res["rank_variants"][["variant", "slope", "se", "corr", "t_stat", "p_value"]].to_string(index=False))
    print("\n-- Descriptive extremes (exploratory only) --")
    print(res["extremes"].to_string(index=False))
    r = res["origins"]
    print(f"\n-- Origins -- first {r['first_origin']}  last {r['last_origin']}  n {r['n_origins']} (nominal {r['n_nominal']}, excluded {r['n_excluded']} {r['excluded_by_reason']})  "
          f"full blocks {r['n_full_blocks']}  partial block origins {r['partial_block_origins']}")
    s = res["stability"]
    print("\n-- Stability (amended statistic, S2 time-shift variant, primary cell) --")
    print(f"T={s['T']:.4f}  p_stab={s['p_stab']:.6g}  B={s['B']}  R={s['R']}  seed={s['seed']}  min_shift={s['min_shift']}  "
          f"share of blocks with s_b>0: {s['share_blocks_positive']:.1%}  passes (p_stab<0.05, before Holm across candidates)={s['passes']}")
    print("block  start       origins   s_b")
    for i, (start, cnt, sb) in enumerate(zip(s["block_starts"], s["block_origin_counts"], s["s_b"])):
        print(f"{i:>5}  {start}  {cnt:>7}  {sb:>8.3f}")
    v = res["variants"]["stability_24h"]
    print(f"labeled variant, stability on the 24h target (not recorded): T={v['T']:.4f} p_stab={v['p_stab']:.6g}")
    e, gi = res["economic_gate"], res["gate_info"]
    print("\n-- Economic gate (stress cost, PRIMARY rule: cash only when rank_s is invalid; recorded) --")
    print(f"pooled_net_return={e['pooled_net_return']:.6g}  pass_rate={e['pass_rate']:.2%}  passes_pooled={e['passes_pooled']}  passes_block_rate={e['passes_block_rate']}  passes={e['passes']}")
    gd = res["gate_detail"]
    print(f"trades {gd['strategy']['n_trades']}  hit rate {gd['strategy']['hit_rate']:.3f}  exposure {gd['exposure']:.3f}  late executions {gi['late_executions']}  "
          f"buy-and-hold pooled {gd['buy_and_hold_gate']['pooled_net_return']:.6g} (non-negative blocks {gd['buy_and_hold_gate']['pass_rate']:.1%})")
    print(f"settlements held in cash because rank_s is invalid: {gi['cash_masked_rank_settlements']}; trades executed on a substituted bar: {gi['late_executions']}")
    eb = res["variants"]["gate_literal"]["gate"]
    print(f"labeled variant, gate literal reading (not recorded): pooled {eb['pooled_net_return']:.6g}  pass_rate {eb['pass_rate']:.2%}  passes={eb['passes']}")
    print("\nNOT frozen, NOT forward-tested -- results above are for review before proceeding.\n")


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pair", type=str, help="e.g. ETH_USDT or BTC_USDT")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--raw-dir", type=Path, default=None)
    p.add_argument("--registry-path", type=Path, default=None,
                   help="registry file to write (default: scratch temp/scratch-registry.jsonl; with --commit-to-registry: the LIVE registry)")
    p.add_argument("--origin-facts", action="store_true", help="read-only: print the facts and the cutoff check, write nothing")
    p.add_argument("--commit-to-registry", action="store_true", help="write to the LIVE registry (required for any live write)")
    p.add_argument("--self-test", action="store_true", help="run the offline self-test (no real data needed) and exit")
    return p


def _write_world(tmp: Path, world: dict, pair: str = "ETH_USDT") -> Path:
    data_dir = tmp / "binance"
    data_dir.mkdir(parents=True, exist_ok=True)
    world["df1h"].reset_index(names="date").to_feather(data_dir / f"{pair}-1h.feather")
    world["df1d"].reset_index(names="date").to_feather(data_dir / f"{pair}-1d.feather")
    world["native"].to_feather(data_dir / f"{pair}-funding.feather")
    return data_dir


def _self_test() -> None:
    import inspect
    import tempfile

    world = formula_s2._make_world(1800, 11, c=0.006, start="2021-01-01 00:00")  # runs past the cutoff on purpose
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_dir = _write_world(tmp, world)
        reg = tmp / "registry.jsonl"
        res = run_s2("ETH_USDT", data_dir, registry_path=reg, stability_R=200)
        assert res["family"] == "S2-ETHUSDT" and res["post_cutoff_rows"] == {"funding": 0, "1h": 0, "1d": 0}
        assert res["origins"]["last_origin"] == pd.Timestamp("2025-08-28 16:00", tz="UTC"), "last origin on a 00:00-aligned synthetic grid"
        assert res["origins"]["first_origin"] == pd.Timestamp("2021-01-01", tz="UTC") + 271 * pd.Timedelta(hours=8)
        assert (res["cells"]["n"] == res["n_discovery"]).all() and res["n_discovery"] == res["origins"]["n_origins"]
        assert res["discovery_estimate"] < 0, "the injected negative relation must recover a negative slope"
        st = res["stability"]
        assert st["R"] == 200 and st["B"] == res["origins"]["n_full_blocks"] and st["passes"] is True
        assert res["economic_gate"]["pass_rate"] >= 0 and "gate_literal" in res["variants"] and list(res["sensitivity"]["hac_lags"]) == [3, 9] and list(res["cells"]["hac_lags"]) == [12, 36]
        records = registry.load_records(reg)
        assert [r["status"] for r in records if r["family"] == "S2-ETHUSDT"] == ["discovery", "stability", "economic_gate"], "exactly three steps, in order"
        d = records[0]["detail"]
        assert len(d["all_cells"]) == 2 and d["n"] == res["n_discovery"] and abs(d["p_value"] - float(res["cells"].query("H == 72")["p_value"].iloc[0])) < 1e-15
        assert d["post_cutoff_rows"] == {"funding": 0, "1h": 0, "1d": 0} and d["origins"]["n_origins"] == res["n_discovery"]
        s_rec = records[1]["detail"]
        assert s_rec["p_value"] == st["p_stab"] and s_rec["B"] == st["B"] and s_rec["horizon_h"] == 72 and s_rec["min_shift"] == 300
        g_rec = records[2]["detail"]
        assert g_rec["rule_mode"] == "primary" and "cash_masked_rank_settlements" in g_rec and {"pooled_net_return", "pass_rate", "passes_pooled", "passes_block_rate", "passes"} <= set(g_rec)
        assert not any(r["status"] in ("frozen", "holdout_consumed") for r in records), "never freeze or touch the holdout"
        # the S1-style across-candidate Holm reads the raw primary p from the discovery record
        hs = registry.holm_at_step(records, "ETHUSDT", "discovery")
        assert abs(hs["S2-ETHUSDT"]["p_raw"] - d["p_value"]) < 1e-15

        before = sorted(p.name for p in tmp.rglob("*"))
        facts = origin_facts_for("ETH_USDT", data_dir)
        assert sorted(p.name for p in tmp.rglob("*")) == before, "origin facts must write nothing"
        assert facts["origins"]["n_origins"] == res["n_discovery"] and facts["post_cutoff_rows"] == {"funding": 0, "1h": 0, "1d": 0}
        assert facts["first_origin_is_first_settlement_plus_271x8h"] and facts["gate_blocks_same_as_origin_blocks"] and facts["gate_full_blocks"] == facts["origins"]["n_full_blocks"]
        assert facts["file_1h"]["missing_hours"] == 0 and facts["file_1d"]["missing_days"] == 0
        print_origin_facts_report(facts)

        run_s2("ETH_USDT", data_dir, registry_path=reg, stability_R=200)
        assert len(registry.load_records(reg)) == 6, "a second run simply appends three more records"

        assert inspect.signature(run_s2).parameters["registry_path"].default == registry.SCRATCH_REGISTRY_PATH and not registry.is_live_registry(registry.DEFAULT_REGISTRY_PATH)
        fake_live = tmp / "fake_live" / "registry.jsonl"
        fake_live.parent.mkdir(parents=True)
        fake_live.write_text("")
        saved = registry.LIVE_REGISTRY_PATH
        registry.LIVE_REGISTRY_PATH = fake_live
        try:
            try:
                run_s2("ETH_USDT", data_dir, registry_path=fake_live, stability_R=200)
            except registry.LiveRegistryWriteRefused:
                pass
            else:
                raise AssertionError("run_s2 without the flag must refuse a live registry path")
            assert fake_live.read_text() == "", "the refused run must leave the live file untouched"
            run_s2("ETH_USDT", data_dir, registry_path=fake_live, commit_to_registry=True, stability_R=200)
            assert len(registry.load_records(fake_live)) == 3
        finally:
            registry.LIVE_REGISTRY_PATH = saved
        print_report(res)

        # a masked funding stretch and missing bars flow through to counted exclusions, never imputed
        wg = formula_s2._make_world(1800, 11, c=0.006, start="2021-01-01 00:00", drop_native=[700], drop_bars=[world["t8"][1500] + pd.Timedelta(hours=1)])
        gdir = _write_world(tmp / "gappy", wg)
        gf = origin_facts_for("ETH_USDT", gdir)
        assert gf["origins"]["excluded_by_reason"]["rank_invalid"] == 272 and gf["origins"]["n_excluded"] == 275 and gf["file_1h"]["missing_hours"] == 1

    print("Self-test passed: run_s2 loads synthetic 1h/1d/funding feather files, truncates at the cutoff (0 post-cutoff rows), builds ONE common origin set, "
          "runs discovery (2 cells, Holm within 2), the S2 stability check and the economic gate, writes exactly discovery/stability/economic_gate (raw primary p in the "
          "discovery record), never freeze or holdout_consumed, is re-runnable, refuses a live-registry path without --commit-to-registry, "
          "reports the origin facts read-only, and counts masked and gap exclusions.")


def main() -> None:
    args = build_argparser().parse_args()
    if not args.pair:
        print("error: --pair is required (e.g. --pair ETH_USDT), or pass --self-test", file=sys.stderr)
        raise SystemExit(2)
    if args.origin_facts:
        print_origin_facts_report(origin_facts_for(args.pair, args.data_dir, raw_dir=args.raw_dir))
        return
    if args.registry_path is not None:
        registry_path = args.registry_path
    elif args.commit_to_registry:
        registry_path = registry.LIVE_REGISTRY_PATH
    else:
        registry_path = registry.SCRATCH_REGISTRY_PATH
    live = registry.is_live_registry(registry_path)
    print(f"REGISTRY: {'LIVE' if live else 'scratch (live registry untouched)'} -> {registry_path}"
          + ("" if (live or not args.commit_to_registry) else "   [--commit-to-registry given, but this is not the live file]"), file=sys.stderr)
    if live and not args.commit_to_registry:
        print("error: the live registry needs --commit-to-registry", file=sys.stderr)
        raise SystemExit(2)
    print_report(run_s2(args.pair, args.data_dir, raw_dir=args.raw_dir, registry_path=registry_path, commit_to_registry=args.commit_to_registry))


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        main()
