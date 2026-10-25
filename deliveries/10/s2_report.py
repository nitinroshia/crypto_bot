"""
S2 report generator (Work Order 1.6 step 3, with M2's rulings of 2026-10-23). The S2 twin of s1_report.py. PRE-TAX.

READ-ONLY. It reads the 1h, 1d and funding data files and the LIVE registry (the three records per pair that the S2 live
run wrote) and writes ONE markdown report plus the trade-list CSVs (the economic gate's stress-cost run and the buy-and-hold
comparator, per pair); it never writes the registry. The numbers recorded in the registry are the source of truth: everything
else is recomputed here from the discovery data with the SAME production code (`formula_s2`, `run_s2.build_pair`,
`stability_check`, `economic_gate`, `rule_evaluator`, `nonstationarity`) and the report REFUSES to be produced unless every
recomputed figure reproduces the recorded one (origin facts, the two discovery cells, stability T / p_stab / s_b, gate pooled
return and pass rate, trade count). So the report cannot disagree with the registry.

The report states recorded outcomes; it does not interpret them and makes no recommendation. No freeze, no forward test,
the holdout is untouched.

  python3 s2_report.py --pair ETH_USDT --pair BTC_USDT --out ../../docs/reports/s2-report-step3.md \\
         --trades-dir ../../docs/reports/s2-trades --run-commit <live run commit> --code-commit <commit>
  python3 s2_report.py --self-test
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import blocks
import formula_s1
import formula_s2
import nonstationarity
import registry
import rule_evaluator
import run_s2
from cutoff import CUTOFF
from s1_report import MDE_MULTIPLIER, STEPS, ReportConsistencyError, _check, _f, _find_file, _md_table

DEFAULT_DATA_DIR = run_s2.DEFAULT_DATA_DIR
GATE_BLOCK_SHARE = 0.70
TRADE_COLUMNS = ["pair", "entry_time_utc", "exit_time_utc", "entry_price", "exit_price", "gross_log_return", "net_return_stress", "exit_reason"]


def _sha(path: Path | None) -> str:
    if path is None or not path.exists():
        return "n/a"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iso(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def trades_frame(pair: str, df1h: pd.DataFrame, evaluation: dict) -> pd.DataFrame:
    """One row per round trip (M2's item 9): entry at the open of the entry bar, exit at the open of the exit bar, or at the
    CLOSE of the last discovery bar for the end-of-sample exit. gross_log_return = ln(exit/entry) before costs;
    net_return_stress = the evaluator's own net return of that round trip (both sides charged at the stress cost)."""
    rows = []
    for t in evaluation["trades"]:
        entry = float(df1h.loc[t["entry_time"], "open"])
        exit_ = float(df1h.loc[t["exit_time"], "close" if t["forced"] else "open"])
        rows.append(
            {
                "pair": pair, "entry_time_utc": _iso(t["entry_time"]), "exit_time_utc": _iso(t["exit_time"]),
                "entry_price": entry, "exit_price": exit_, "gross_log_return": math.log(exit_ / entry),
                "net_return_stress": float(t["net_return"]), "exit_reason": "end-of-sample" if t["forced"] else "signal",
            }
        )
    return pd.DataFrame(rows, columns=TRADE_COLUMNS)


def _pair_section(pair: str, data_dir: Path, raw_dir: Path | None, records: list[dict], trades_dir: Path | None, null: dict | None) -> tuple[str, dict, dict]:
    family = formula_s2.family_name(pair)
    reg_pair = pair.replace("_", "")
    idxs = [i for i in registry._live_indices(records, reg_pair) if records[i]["family"] == family]
    live = {records[i]["status"]: (i + 1, records[i]) for i in idxs}
    if sorted(live) != sorted(STEPS) or len(idxs) != len(STEPS):
        raise ReportConsistencyError(f"{family}: expected exactly one live record at each of {STEPS}; found {[records[i]['status'] for i in idxs]}")
    rec_disc, rec_stab, rec_gate = (live[s][1]["detail"] for s in STEPS)

    b = run_s2.build_pair(pair, data_dir, raw_dir)
    inp, obs, oset, rep = b["inputs"], b["obs"], b["oset"], b["origin_report"]
    df1h, df1d = inp["df1h"], inp["df1d"]
    origins = oset["origins"]
    first_origin = origins[0]
    ffacts = run_s2._funding_facts(inp["native"], obs)
    if any(inp["post_cutoff_rows"].values()):
        raise ReportConsistencyError(f"rows after the cutoff in the discovery frames: {inp['post_cutoff_rows']}")

    # ---- 1. origin facts ---------------------------------------------------------
    ro = rec_disc["origins"]
    _check("n origins", rep["n_origins"], rec_disc["n"])
    for key, val in (("first_origin", rep["first_origin"]), ("last_origin", rep["last_origin"])):
        if pd.Timestamp(val).isoformat() != ro[key]:
            raise ReportConsistencyError(f"{key} differs from the registry's discovery record")
    for key in ("n_nominal", "n_excluded", "n_full_blocks", "partial_block_origins"):
        _check(f"origin fact {key}", rep[key], ro[key])
    for k, v in rep["excluded_by_reason"].items():
        _check(f"excluded by reason {k}", v, ro["excluded_by_reason"][k])
    xy = formula_s2.s2_xy(oset, df1h, df1d)
    excl_rows = [[reason, len(idx), ", ".join(_iso(t) for t in idx[:10]) or "-"] for reason, idx in oset["excluded"].items()]
    excl_table = _md_table(["reason (first reason wins)", "origins", "settlement times (UTC)"], excl_rows)
    files = {tf: _find_file(pair, data_dir, raw_dir, tf) for tf in ("1h", "1d")}
    fund_path = inp.get("funding_path")
    hours = pd.date_range(df1h.index[0], df1h.index[-1], freq="1h")
    days = pd.date_range(df1d.index[0], df1d.index[-1], freq="1D")
    gate_tiles = blocks.tile_blocks(df1h, first_origin)
    gate_full = [t for t in gate_tiles if not t["is_final_partial"]]
    struct_full = [bl for bl in rep["structure"]["blocks"] if bl["is_full"]]
    gate_same = len(gate_full) == len(struct_full) and all(g["start"] == m["start"] and g["end"] == m["end"] for g, m in zip(gate_full, struct_full))

    # ---- 2. discovery -------------------------------------------------------------
    interval_h = min(float(k) for k in (ffacts["interval_hours_counts"] or {"8.0": 1}))
    cells = formula_s2.discovery_cells(xy, interval_h)
    rec_cells = pd.DataFrame(rec_disc["all_cells"]).set_index("H")
    for _, c in cells.iterrows():
        H = int(c["H"])
        for col in ("slope", "se", "t_stat", "p_value", "p_holm", "p_bonferroni", "mde", "corr"):
            _check(f"discovery cell {H}h {col}", c[col], rec_cells.loc[H, col])
        if int(rec_cells.loc[H, "hac_lags"]) != int(c["hac_lags"]):
            raise ReportConsistencyError(f"cell {H}h: HAC lags differ from the registry")
    prim = cells[cells["H"] == formula_s2.PRIMARY_H].iloc[0]
    _check("primary slope vs record", prim["slope"], rec_disc["slope"])
    _check("primary p vs record", prim["p_value"], rec_disc["p_value"])
    sens = formula_s2.sensitivity_superseded_lags(xy).set_index("H")
    disc_rows = [
        [int(c["H"]), int(c["hac_lags"]), "primary" if int(c["H"]) == formula_s2.PRIMARY_H else "secondary", _f(c["slope"]), _f(c["se"]), _f(c["corr"], ".4f"),
         _f(c["t_stat"], ".3f"), _f(c["p_value"], ".4g"), _f(c["p_holm"], ".4g"), _f(c["p_bonferroni"], ".4g"), _f(c["mde"]), int(c["n"]),
         f"{sens.loc[int(c['H']), 'hac_lags']} lags: t {_f(sens.loc[int(c['H']), 't_stat'], '.3f')}, p {_f(sens.loc[int(c['H']), 'p_value'], '.4g')}"]
        for _, c in cells.iterrows()
    ]
    disc_table = _md_table(["H (h)", "HAC lags", "tag", "slope", "HAC SE", "corr(x,y)", "HAC t", "one-sided p", "Holm (within 2)", "Bonferroni", f"MDE ({MDE_MULTIPLIER:.3f} x SE)", "n",
                            "sensitivity: superseded lags (not used)"], disc_rows)
    rank_var = formula_s2.rank_variants_primary(xy)
    rank_table = _md_table(["rank variant (primary cell)", "slope", "HAC SE", "corr", "HAC t", "one-sided p"],
                           [[r["variant"], _f(r["slope"]), _f(r["se"]), _f(r["corr"], ".4f"), _f(r["t_stat"], ".3f"), _f(r["p_value"], ".4g")] for _, r in rank_var.iterrows()])
    ext = formula_s2.extremes_table(xy)
    ext_table = _md_table(["H (h)", "group", "n", "mean forward return", "unconditional mean", "excess"],
                          [[int(r["H"]), r["group"], int(r["n"]), _f(r["mean_fwd_return"]), _f(r["unconditional_mean"]), _f(r["excess"])] for _, r in ext.iterrows()])

    # ---- 3. stability -------------------------------------------------------------
    stab = formula_s2.s2_stability(xy, origins, R=int(rec_stab["R"]), seed=int(rec_stab["seed"]), min_shift=int(rec_stab["min_shift"]))
    _check("stability p_stab", stab["p_stab"], rec_stab["p_value"])
    _check("stability T", stab["T"], rec_stab["T"])
    _check("stability B", stab["B"], rec_stab["B"])
    if not np.allclose(stab["s_b"], rec_stab["s_b"], rtol=1e-9, atol=1e-12):
        raise ReportConsistencyError("per-block s_b differ from the registry's stability record")
    stab_table = _md_table(
        ["block", "start", "origins", "s_b", "c_b (block score)"],
        [[i, s, c, _f(sb, ".3f"), _f(cb, ".6g")] for i, (s, c, sb, cb) in enumerate(zip(stab["block_starts"], stab["block_origin_counts"], stab["s_b"], stab["c_b"]))],
    )
    st24 = formula_s2.s2_stability(xy, origins, R=int(rec_stab["R"]), seed=int(rec_stab["seed"]), min_shift=int(rec_stab["min_shift"]), horizon=24)

    # ---- 4. by-year / leave-one-year-out ---------------------------------------------
    ns = nonstationarity.non_stationarity_report(xy, formula_s2.make_primary_estimator(xy))
    _check("by-year pooled estimate vs record slope", ns["pooled_estimate"], rec_disc["slope"])
    ns_rows = []
    for _, r in ns["by_year"].iterrows():
        yr = int(r["period"])
        judged = bool(r["judged"])
        loo = ns["leave_one_out"].get(yr)
        ns_rows.append([yr, int(r["n"]), int(r["days_covered"]), _f(r["estimate"]), "yes" if judged else "no (< 120 days)", _f(loo) if loo is not None else "-",
                        ("YEAR-DRIVEN" if ns["year_driven"].get(yr) else "no") if judged else "-",
                        ("same sign" if ns["sign_agreement"].get(yr) else "opposite sign") if judged else "-"])
    ns_table = _md_table(["year", "origins", "days covered", "slope (that year)", "judged", "slope without that year", "year-driven?", "year's sign vs pooled"], ns_rows)

    # ---- 5. economic gate ----------------------------------------------------------------
    stress = rule_evaluator.STRESS_COST_PER_SIDE
    sig, info = formula_s2.s2_signal(oset, df1h, "primary")
    g = formula_s2.run_gate(df1h, first_origin, sig, stress)
    gate, strat, bh_gate, bh = g["gate"], g["strategy"], g["buy_and_hold_gate"], g["buy_and_hold"]
    _check("gate pooled net return", gate["pooled_net_return"], rec_gate["pooled_net_return"])
    _check("gate pass rate", gate["pass_rate"], rec_gate["pass_rate"])
    _check("gate n trades", strat["n_trades"], rec_gate["n_trades"])
    _check("gate late executions", info["late_executions"], rec_gate["late_executions"])
    _check("gate signal changes", info["signal_changes"], rec_gate["signal_changes"])
    _check("gate cash settlements (invalid rank)", info["cash_masked_rank_settlements"], rec_gate["cash_masked_rank_settlements"])
    if bool(gate["passes"]) != bool(rec_gate["passes"]):
        raise ReportConsistencyError("gate verdict differs from the registry")
    sigL, infoL = formula_s2.s2_signal(oset, df1h, "literal")
    gL = formula_s2.run_gate(df1h, first_origin, sigL, stress)
    full_nonneg = sum(1 for v in gate["full_block_returns"].values() if v >= 0)
    n_full_gate = len(gate["full_block_returns"])
    need = int(math.ceil(GATE_BLOCK_SHARE * n_full_gate - 1e-12))
    bh_nonneg = sum(1 for v in bh_gate["full_block_returns"].values() if v >= 0)
    block_rows = []
    for t in gate_tiles:
        bi = t["block_index"]
        block_rows.append([bi, t["start"].date(), "partial" if t["is_final_partial"] else "full", _f(gate["block_returns"][bi], ".4f"), _f(bh_gate["block_returns"][bi], ".4f")])
    block_table = _md_table(["block", "start", "kind", "strategy net", "buy-and-hold net"], block_rows)
    forced = g["forced_exit"]
    gate_lines = [
        f"- Strategy (primary rule, M2's ruling of 2026-10-23: long from the open of the 1h bar labeled s+1h while the latest valid rank <= {formula_s2.RANK_THRESHOLD}, otherwise cash; "
        f"cash exactly when rank_s is invalid), stress cost {stress:.4%} per side: pooled net return **{_f(gate['pooled_net_return'])}** (gross {_f(strat['gross_return'])}); "
        f"non-negative full blocks **{_f(gate['pass_rate'], '.1%')}** (**{full_nonneg} of {n_full_gate}**; the 70% rule needs at least **{need}**); recorded verdict: "
        f"passes_pooled={gate['passes_pooled']}, passes_block_rate={gate['passes_block_rate']}, passes={gate['passes']}.",
        f"- Trades: {strat['n_trades']} position-change events (entries and exits, including the forced final exit); {len(strat['trades'])} complete round trips; hit rate (round trips with net return > 0): "
        f"{_f(strat['hit_rate'], '.1%')}; long on {_f(g['exposure'], '.1%')} of the 1h bars in the segment.",
        f"- Settlements in the segment: {info['n_settlements_in_segment']} (from the first origin to the last discovery bar, including those after the last origin); long decisions {info['n_long_decisions']}; "
        f"**settlements held in cash because rank_s is invalid: {info['cash_masked_rank_settlements']}**; signal changes {info['signal_changes']}; **trades executed on a substituted bar: {info['late_executions']}**.",
        "- End-of-sample exit: the segment starts flat at the first origin and is forced to exit at the last discovery bar's close, charged as an exit cost "
        + (f"(labeled end-of-sample exit; this run's: entered {forced[0]['entry_time']}, net {_f(forced[0]['net_return'], '.4f')}). " if forced else "(this run was flat at the end, so no forced exit occurred). ")
        + f"The segment runs from the first origin {first_origin} to the last discovery bar {df1h.index[-1]}; no holdout bar is touched.",
        f"- Buy-and-hold comparator (R4), same evaluator, same segment, same blocks, same stress cost (one entry and one forced exit): pooled net return **{_f(bh_gate['pooled_net_return'])}** "
        f"(price-only, before costs: {_f(bh['gross_return'])}); non-negative full blocks **{_f(bh_gate['pass_rate'], '.1%')}** ({bh_nonneg} of {len(bh_gate['full_block_returns'])}).",
        f"- Labeled variant, the order's literal reading (a missing entry or exit bar also forces cash; never recorded): pooled net return {_f(gL['gate']['pooled_net_return'])}, non-negative full blocks "
        f"{_f(gL['gate']['pass_rate'], '.1%')}, passes={gL['gate']['passes']}, trades {gL['strategy']['n_trades']}; settlements where the two readings differ: "
        f"{int((formula_s2.gate_decisions(oset, df1h, 'primary')[1] != formula_s2.gate_decisions(oset, df1h, 'literal')[1]).sum())}.",
    ]
    strat_trades = trades_frame(pair, df1h, strat)
    bh_trades = trades_frame(pair, df1h, bh)
    if len(strat_trades) != len(strat["trades"]) or len(bh_trades) != 1:
        raise ReportConsistencyError("trade lists do not match the evaluator's trades")
    if trades_dir is not None:
        trades_dir.mkdir(parents=True, exist_ok=True)
        strat_trades.to_csv(trades_dir / f"s2-trades-{pair}-strategy-stress.csv", index=False)
        bh_trades.to_csv(trades_dir / f"s2-trades-{pair}-buy-and-hold-stress.csv", index=False)

    # ---- 6. registry -----------------------------------------------------------------------
    holm = {s: registry.holm_at_step(records, reg_pair, s) for s in STEPS}
    reg_table = _md_table(["record (line in registry.jsonl)", "status", "timestamp (UTC)"], [[live[s][0], s, live[s][1]["timestamp_utc"]] for s in STEPS])
    holm_rows = []
    for s in STEPS:
        h = holm[s].get(family)
        holm_rows.append([s, len(holm[s]), ", ".join(sorted(holm[s])), _f(h["p_raw"], ".6g") if h else "-", _f(h["p_holm"], ".6g") if h else "-"])
    holm_table = _md_table(["step", "families at this step", "which", f"{family} p (raw)", f"{family} Holm across candidates"], holm_rows)
    s1_family = f"S1-{reg_pair}"
    s1_rows = [[s, _f(holm[s][s1_family]["p_raw"], ".6g") if s1_family in holm[s] else "-", _f(holm[s][s1_family]["p_holm"], ".6g") if s1_family in holm[s] else "-"] for s in STEPS]
    s1_table = _md_table(["step", f"{s1_family} p (raw)", f"{s1_family} Holm across candidates"], s1_rows)
    stab_holm = holm["stability"].get(family)
    after = int((df1h.index > CUTOFF).sum()) + int((df1d.index > CUTOFF).sum()) + int((inp["native"]["date"] > CUTOFF).sum())
    if after != 0:
        raise ReportConsistencyError(f"{after} rows after the cutoff in the discovery frames")
    cutoff_line = (
        f"The discovery frames (each file truncated at the cutoff {CUTOFF} before any computation) hold **{inp['post_cutoff_rows']['1h']}** 1h rows, **{inp['post_cutoff_rows']['1d']}** daily rows and "
        f"**{inp['post_cutoff_rows']['funding']}** funding settlements after the cutoff (rows dropped by the truncation: 1h {inp['dropped_rows']['1h']}, 1d {inp['dropped_rows']['1d']}, funding {inp['dropped_rows']['funding']}). "
        f"Last funding settlement {ffacts['last_settlement']}; last 1h bar {df1h.index[-1]}; last daily bar {df1d.index[-1]}."
    )

    text = f"""## {pair}  ({family})  -- pre-tax

Data files: `{files['1h'].name if files['1h'] else '1h file'}` sha256 `{_sha(files['1h'])}`; `{files['1d'].name if files['1d'] else '1d file'}` sha256 `{_sha(files['1d'])}`; `{Path(fund_path).name if fund_path else 'funding file'}` sha256 `{_sha(Path(fund_path)) if fund_path else 'n/a'}`.

### 1. Origin facts
- First funding settlement **{ffacts['first_settlement']}**, last {ffacts['last_settlement']}; {ffacts['native_rows']} native rows to the cutoff, settlement interval hours {ffacts['interval_hours_counts']}, interval changes {len(ffacts['interval_changes'] or [])}; 8h observations {ffacts['observations']} (complete {ffacts['complete']}, masked {ffacts['masked']}; the first settlement is masked by construction).
- **Tie share** at the modal value {ffacts['tie_modal_value']} up to the cutoff: **{_f(ffacts['tie_share'], '.4f')}** of {ffacts['tie_n']} observations (the order expected about 0.396 for ETH and 0.401 for BTC).
- First origin **{_iso(rep['first_origin'])}** (= first settlement + 271 x 8h), last origin **{_iso(rep['last_origin'])}** (last settlement with s+1h+72h <= the last 1h bar {_iso(oset['last_bar'])}); **{rep['n_origins']} origins** (nominal {rep['n_nominal']}, excluded **{rep['n_excluded']}**).
- **B = {rep['n_full_blocks']} full {formula_s2.BLOCK_DAYS}-day blocks** (origins per full block min/median/max {rep['block_origins_min']}/{rep['block_origins_median']}/{rep['block_origins_max']}); **partial block: {rep['partial_block_origins']} origins**; span {rep['span_days']} days. Stricter cross-check of the block count: {rep['n_full_blocks_strict_check']}.
- Economic-gate tiling over the 1h discovery rows from the same first origin has the same full blocks: {gate_same} (its partial block runs {(df1h.index[-1] + pd.Timedelta(hours=1) - gate_tiles[-1]['start']).days if gate_tiles[-1]['is_final_partial'] else 0} days).
- 1h file (discovery frame): {len(df1h)} rows, {df1h.index[0]} .. {df1h.index[-1]}, missing hours inside: **{len(hours) - len(df1h)}**; daily file: {len(df1d)} rows, missing days inside: **{len(days) - len(df1d)}**. Rows after the cutoff: see section 7.

{excl_table}

### 2. Discovery table (2 cells, one common origin set, one-sided p in the NEGATIVE direction, Holm within the 2)
Primary cell H = 72h; the 24h cell is secondary. slope = OLS of the forward log return from the open of bar s+1h to the open of bar s+1h+H on the mid-rank; HAC = Newey-West (Bartlett) with 4 x H/8h lags (M2's ruling, replacing the order's 3 and 9); corr = Pearson correlation at the common origins; MDE = {MDE_MULTIPLIER:.3f} x HAC SE in slope units. The last column is a labeled sensitivity with the superseded lags and is not used for any decision.

{disc_table}

Robustness columns on the primary cell only (labeled, never the primary statistic):

{rank_table}

Descriptive, exploratory only: mean forward return and its excess over the unconditional mean at the same horizon:

{ext_table}

### 3. Stability (amended statistic, Work Order 1.5 section 3, S2 time-shift variant; primary 72h cell only)
**T = {_f(stab['T'], '.4f')}, p_stab = {_f(stab['p_stab'], '.6g')}** (B = {stab['B']} full blocks, R = {stab['R']} circular time-shifts, minimum shift {stab['min_shift']} settlements, seed {stab['seed']}); share of blocks with s_b > 0: **{_f(stab['share_blocks_positive'], '.1%')}**; recorded `passes` (p_stab < 0.05, before any across-candidate Holm): **{rec_stab['passes']}**. Origins in blocks {stab['n_origins_in_blocks']} of {stab['n_origins']}; partial block origins {stab['partial_block_origins']} (never scored, counted in the centring).
- **Across-candidate Holm (R1, S1 and S2 are both candidates for this pair):** raw p_stab {_f(stab_holm['p_raw'], '.6g') if stab_holm else '-'}, Holm-adjusted **{_f(stab_holm['p_holm'], '.6g') if stab_holm else '-'}**; S2's raw p_stab must be below 0.025 to survive the two-candidate Holm: **{'yes' if (stab_holm and stab_holm['p_raw'] < 0.025) else 'no'}**.
- Labeled variant, stability on the 24h target (not recorded): T = {_f(st24['T'], '.4f')}, p_stab = {_f(st24['p_stab'], '.6g')}.

{stab_table}

### 4. By-year and leave-one-year-out (primary cell's slope; years with fewer than 120 days are shown, not judged)
Pooled slope {_f(ns['pooled_estimate'])}. Year-driven flag (dropping one judged year cuts the slope by more than half or flips its sign): **any year-driven = {ns['any_year_driven']}**; every judged year's own sign agrees with the pooled sign: {ns['all_judged_years_agree'] if 'all_judged_years_agree' in ns else 'see table'}.

{ns_table}

### 5. Economic gate at stress cost, with buy-and-hold comparators (R4), pre-tax
{chr(10).join(gate_lines)}

Per-block returns (strategy and buy-and-hold over the same blocks; the partial block is included in the pooled figures, not in the block count):

{block_table}

Trade lists (one row per round trip, pre-tax): `s2-trades-{pair}-strategy-stress.csv` ({len(strat_trades)} rows) and `s2-trades-{pair}-buy-and-hold-stress.csv` (1 row), columns {', '.join(TRADE_COLUMNS)}.

### 6. Registry
Records written by the S2 live run (live registry):

{reg_table}

`cumulative_count` for {reg_pair}: **{registry.cumulative_count(records, reg_pair)}**; `cumulative_cells`: **{registry.cumulative_cells(records, reg_pair)}**. `holm_at_step` (across candidates; the economic gate is a pass/fail rule with no p-value, so its Holm is undefined). This pair's S2 family and, below, the S1 family whose adjusted values changed by design once S2 existed:

{holm_table}

{s1_table}

### 7. Cutoff
{cutoff_line}
"""
    summary = {
        "pair": pair, "n_origins": rep["n_origins"], "B": rep["n_full_blocks"], "slope": float(prim["slope"]), "p72": float(prim["p_value"]), "p72_holm": float(prim["p_holm"]),
        "p24": float(cells[cells["H"] == 24].iloc[0]["p_value"]), "stab_p": float(stab["p_stab"]), "stab_p_holm": float(stab_holm["p_holm"]) if stab_holm else float("nan"),
        "stab_pass": bool(rec_stab["passes"]), "gate_pooled": float(gate["pooled_net_return"]), "gate_nonneg": f"{full_nonneg} of {n_full_gate} (needs {need})", "gate_pass": bool(gate["passes"]),
        "bh_pooled": float(bh_gate["pooled_net_return"]), "bh_nonneg": f"{bh_nonneg} of {len(bh_gate['full_block_returns'])}", "any_year_driven": bool(ns["any_year_driven"]),
    }
    return text, summary, {"strategy": strat_trades, "buy_and_hold": bh_trades}


CHOICES = [
    "Label: this report is PRE-TAX. The trade lists (CSV) exist so that a later after-tax layer can be computed from dated trades (M2's item 9).",
    "Origins (Work Order 1.6 section 1, message-20): one common origin set per pair on the 8h settlement grid; first usable origin = first settlement + 271 x 8h (slot 272 counting the masked first settlement as slot 1); last origin = last settlement with s+1h+72h <= the last 1h bar of the discovery frame; an origin whose rank is invalid (R2), entry bar or either exit bar is missing is excluded and counted by reason (first reason in that order), never imputed. The first settlements are at 08:00 UTC (the order's example assumed 00:00), so the first origins are at 16:00 UTC.",
    "Predictor: mid-rank over the 270 previous slots (R2: all 270 previous slots and the current observation valid); ties are exact after rounding to 12 decimals; strict-below and at-or-below ranks are labeled robustness columns on the primary cell only.",
    "Target: ln(open[s+1h+H] / open[s+1h]) on the 1h file, H = 24h and 72h in clock time; the bar labeled s itself never enters.",
    "HAC lags (M2, 2026-10-23, replacing the order's 3 and 9): Newey-West (Bartlett) with 4 x H/8h = 12 (24h) and 36 (72h); lags count observations, not hours, so the few excluded origins shift the lag spacing very slightly. The superseded lags appear only as a labeled sensitivity column. MDE = {MDEM} x HAC SE (z 0.95 + z 0.80).",
    "P-values are one-sided in the negative direction (pre-registered); Holm within the 2 cells is the family adjustment; across candidates (R1) S1 and S2 form the family per pair at the discovery and stability steps, using each family's raw primary-cell p as recorded in the registry; the economic gate has no p-value.",
    "Stability: once per pair on the 72h cell only; blocks are 90 calendar days tiled from the first origin, the partial block is never scored but counted in the centring; y = 72h forward return / sigma30, sigma30 = sd (ddof 1) of the last 30 daily log returns using only daily closes at or before the origin (all three settlements of day D use the close of day D-1); d = -1; circular time-shift null, minimum shift 300, R = 2000, seed 12345 stored. The 24h version is a labeled variant, not recorded.",
    "Economic gate (M2's ruling, replacing the order's gap-excluded clause): the position at settlement s is cash exactly when rank_s is not valid (R2), otherwise long if rank_s <= 0.5; whether the entry or exit bars of the targets exist decides only origin-set membership. A decision is placed on the last 1h row with label <= s, so it executes at the open of s+1h, or at the next available bar's open (counted); the segment starts flat at the first origin, acts on every settlement up to the last discovery bar (the nine after the last origin included) and is forced out at the last discovery bar's close (end-of-sample exit). The order's literal reading is the labeled variant above.",
    "Buy-and-hold comparator (R4): the same evaluator, segment, blocks and stress cost with the signal fixed at 1 (it enters at the open after the first origin bar and pays one entry and one forced exit). 'Price-only' is the same trade before costs.",
    "By-year: calendar years of the origin dates; the estimator is the primary cell's HAC regression slope on that year's origins, via the production hooks; the year-driven rule and the 120-day rule are as in Work Order 1.5.",
    "Cutoff: the loader truncates the funding, 1h and 1d files at the cutoff before any computation (the item-2 pattern), so no post-cutoff row enters any figure; section 7 counts rows after the cutoff in the discovery frames.",
    "Persistent-null calibration (M2's ruling): the self-test's 1,000-path persistent null (AR(1) phi 0.98 per settlement, 40% ties at the low end, production mid-rank, overlapping iid hourly shocks, fixed seed) gives the rejection rates reported above; they are a property of the test, not of the data.",
    "Nothing in this report is a recommendation. Freeze and forward-test were not run and the holdout was not touched; the stability and economic-gate outcomes are as recorded (`passes`).",
]


def build_report(pairs: list[str], data_dir: Path, raw_dir: Path | None, registry_path: Path, trades_dir: Path | None, run_commit: str, code_commit: str = "unknown",
                 null: dict | None = None) -> str:
    """Return the markdown report (writes the trade CSVs into trades_dir when given). Raises ReportConsistencyError if anything
    recomputed differs from the registry, FileNotFoundError if a data file is missing."""
    records = registry.load_records(registry_path)
    sections, summaries = [], []
    for pair in pairs:
        text, summ, _ = _pair_section(pair, data_dir, raw_dir, records, trades_dir, null)
        sections.append(text)
        summaries.append(summ)
    top = _md_table(
        ["pair", "origins", "B", "primary slope (72h)", "72h one-sided p", "72h Holm within 2", "24h one-sided p", "stability p_stab", "p_stab Holm across candidates", "stability passes",
         "gate pooled net", "gate non-negative full blocks", "gate passes", "buy-and-hold pooled", "buy-and-hold non-negative blocks", "any year-driven"],
        [[s["pair"], s["n_origins"], s["B"], _f(s["slope"]), _f(s["p72"], ".4g"), _f(s["p72_holm"], ".4g"), _f(s["p24"], ".4g"), _f(s["stab_p"], ".4g"), _f(s["stab_p_holm"], ".4g"),
          s["stab_pass"], f"{s['gate_pooled']:.4g}", s["gate_nonneg"], s["gate_pass"], f"{s['bh_pooled']:.4g}", s["bh_nonneg"], s["any_year_driven"]] for s in summaries],
    )
    if null is None:
        null_text = "The persistent null was not run in this build of the report (self-test run)."
    else:
        null_text = (f"{null['paths']} paths; one-sided p < 0.05 in **{null['rate72']:.3f}** of paths for the primary 72h cell with {formula_s2.hac_lags(72)} lags (band <= 0.08; binomial se {null['se72']:.3f}) and "
                     f"**{null['rate24']:.3f}** for the 24h cell with {formula_s2.hac_lags(24)} lags (no band); with the superseded lags 3 and 9 the rates read {null['rate24_old']:.3f} and {null['rate72_old']:.3f} (information only).")
    choices = "\n".join(f"{i}. " + c.replace("{MDEM}", f"{MDE_MULTIPLIER:.3f}") for i, c in enumerate(CHOICES, 1))
    return f"""# S2 report: ETH_USDT and BTC_USDT (Work Order 1.6 step 3) -- PRE-TAX

Generated {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')} by `s2_report.py` (read-only) at repo commit {code_commit}. Registry records are from the S2 live run, commit {run_commit}, written once per pair. Every figure below was recomputed from the discovery data and reproduces the registry's recorded figure (the generator refuses to run otherwise). Freeze and forward-test were not run; the holdout is untouched. This report states recorded outcomes and makes no recommendation. M2's rulings of 2026-10-23 (`docs/correspondence/answer-s2-rulings.md`) override Work Order 1.6 where they differ.

### Summary of recorded outcomes
{top}

### Persistent-null calibration (M2's ruling of 2026-10-23, item 1)
{null_text}

{chr(10).join(sections)}

## 8. Interpretation choices (all of them)
{choices}
"""


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Write the S2 report (read-only; reads data and the live registry).")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--pair", action="append", choices=["ETH_USDT", "BTC_USDT"])
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--raw-dir", type=Path, default=None)
    p.add_argument("--registry-path", type=Path, default=registry.LIVE_REGISTRY_PATH)
    p.add_argument("--out", type=Path, help="report file to write")
    p.add_argument("--trades-dir", type=Path, help="directory for the trade-list CSVs")
    p.add_argument("--run-commit", default="unknown")
    p.add_argument("--code-commit", default="unknown")
    p.add_argument("--skip-null", action="store_true", help="do not run the 1000-path persistent null (about a minute)")
    return p


def _self_test() -> None:
    import tempfile

    worlds = {"ETH_USDT": formula_s2._make_world(1800, 41, c=0.002, start="2021-01-01 00:00"), "BTC_USDT": formula_s2._make_world(1800, 42, c=0.0, start="2021-01-01 00:00", drop_bars=[pd.Timestamp("2021-06-01 01:00", tz="UTC")])}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        reg = tmp / "registry.jsonl"
        data_dir = tmp / "binance"
        for pair, w in worlds.items():
            run_s2._write_world(tmp, w, pair)
            run_s2.run_s2(pair, data_dir, registry_path=reg, stability_R=200)
        out_dir = tmp / "trades"
        text = build_report(["ETH_USDT", "BTC_USDT"], data_dir, None, reg, out_dir, "abc1234", "def5678", null=None)
        assert "PRE-TAX" in text and "S2-ETHUSDT" in text and "S2-BTCUSDT" in text and "Summary of recorded outcomes" in text and "makes no recommendation" in text
        assert "settlements held in cash because rank_s is invalid" in text and "trades executed on a substituted bar" in text and "sensitivity: superseded lags" in text
        for pair in worlds:
            st = pd.read_csv(out_dir / f"s2-trades-{pair}-strategy-stress.csv")
            bh = pd.read_csv(out_dir / f"s2-trades-{pair}-buy-and-hold-stress.csv")
            assert list(st.columns) == TRADE_COLUMNS and list(bh.columns) == TRADE_COLUMNS and len(bh) == 1 and bh["exit_reason"].iloc[0] == "end-of-sample"
            assert set(st["exit_reason"]) <= {"signal", "end-of-sample"} and (st["exit_reason"] == "end-of-sample").sum() <= 1 and len(st) > 5
            assert (st["entry_price"] > 0).all() and (st["exit_price"] > 0).all() and np.allclose(st["gross_log_return"], np.log(st["exit_price"] / st["entry_price"]))
            assert (pd.to_datetime(st["exit_time_utc"]) > pd.to_datetime(st["entry_time_utc"])).all() and (st["net_return_stress"] < np.expm1(st["gross_log_return"])).all()
        # buy-and-hold net return equals the evaluator's closed form (one entry, one forced exit)
        b = pd.read_csv(out_dir / "s2-trades-ETH_USDT-buy-and-hold-stress.csv").iloc[0]
        cost = rule_evaluator.STRESS_COST_PER_SIDE
        assert abs(b["net_return_stress"] - ((1 - cost) ** 2 * b["exit_price"] / b["entry_price"] - 1)) < 1e-12
        # it refuses a registry whose recorded figures were tampered with, and a missing record
        import json

        lines = reg.read_text().splitlines()
        rec = json.loads(lines[0])
        rec["detail"]["slope"] = rec["detail"]["slope"] * 1.01
        bad = tmp / "tampered.jsonl"
        bad.write_text("\n".join([json.dumps(rec)] + lines[1:]) + "\n")
        try:
            build_report(["ETH_USDT"], data_dir, None, bad, None, "x")
        except ReportConsistencyError:
            pass
        else:
            raise AssertionError("a tampered discovery record must be refused")
        short = tmp / "short.jsonl"
        short.write_text("\n".join(lines[:2]) + "\n")
        try:
            build_report(["ETH_USDT"], data_dir, None, short, None, "x")
        except ReportConsistencyError:
            pass
        else:
            raise AssertionError("an incomplete family must be refused")
        try:
            build_report(["ETH_USDT"], tmp / "nowhere", None, reg, None, "x")
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("a missing data file must be refused")
    print("Self-test passed: s2_report builds the PRE-TAX two-pair S2 report from synthetic data and a registry written by run_s2, reproduces every recorded figure, "
          "writes one trade-list CSV per pair (columns per M2's item 9) plus the single buy-and-hold trade, and refuses a tampered record, an incomplete family and a missing data file.")


def main() -> None:
    a = build_argparser().parse_args()
    if a.self_test:
        _self_test()
        return
    if not a.pair or a.out is None:
        build_argparser().error("--pair and --out are required")
    null = None if a.skip_null else formula_s2._persistent_null()
    text = build_report(a.pair, a.data_dir, a.raw_dir, a.registry_path, a.trades_dir, a.run_commit, a.code_commit, null=null)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(f"wrote {a.out} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
