"""
S1 report generator (Work Order 1.5 step 6; the eight required contents of section 5, per pair).

READ-ONLY. It reads the daily data files and the LIVE registry (the three records per pair that
step 5 wrote) and writes ONE markdown report file; it never writes the registry. The numbers
recorded in the registry are the source of truth: everything else is recomputed here from the
discovery data with the SAME production code (`formula_s1`, `stability_check`, `economic_gate`,
`rule_evaluator`, `nonstationarity`) and the report REFUSES to be produced unless every
recomputed figure reproduces the recorded one (discovery cells, stability T/p/s_b, gate pooled
return and pass rate). So the report cannot disagree with the registry.

The report states recorded outcomes; it does not interpret them and makes no recommendation.

  python3 s1_report.py --pair ETH_USDT --pair BTC_USDT --out ../../docs/reports/s1-report-step6.md \
         --void-commit ac63ff2 --run-commit 4487f1e
  python3 s1_report.py --self-test
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
from scipy.stats import norm

import blocks
import economic_gate
import formula_s1
import nonstationarity
import registry
import rule_evaluator
from cutoff import CUTOFF, truncate_at_cutoff
from databundle import load_bundle

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "user_data" / "data" / "binance"
Z_ALPHA = float(norm.ppf(0.95))  # one-sided 5%
Z_POWER = float(norm.ppf(0.80))  # 80% power
MDE_MULTIPLIER = Z_ALPHA + Z_POWER  # about 2.486 (answer-01: "roughly 2.5 x SE")
STEPS = ("discovery", "stability", "economic_gate")


class ReportConsistencyError(RuntimeError):
    """A recomputed figure does not reproduce the registry's recorded figure."""


def _close(a: float, b: float, rtol: float = 1e-9, atol: float = 1e-12) -> bool:
    return bool(np.isclose(a, b, rtol=rtol, atol=atol, equal_nan=True))


def _check(label: str, recomputed, recorded, rtol: float = 1e-9, atol: float = 1e-12) -> None:
    if not _close(float(recomputed), float(recorded), rtol, atol):
        raise ReportConsistencyError(f"{label}: recomputed {recomputed!r} != registry {recorded!r}")


def _f(v, fmt: str = ".6g") -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "NaN"
    return format(v, fmt)


def _md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _find_file(pair: str, data_dir: Path, raw_dir: Path | None, timeframe: str = "1d") -> Path | None:
    cands = [data_dir / f"{pair}-{timeframe}.feather"]
    if raw_dir is not None:
        cands.append(raw_dir / f"{pair}-{timeframe}.feather")
    else:
        cands.append(data_dir.parent / "binance_raw" / f"{pair}-{timeframe}.feather")
    return next((p for p in cands if p.exists()), None)


def _pair_section(pair: str, data_dir: Path, raw_dir: Path | None, records: list[dict]) -> tuple[str, dict]:
    """The report section of one pair, and a summary dict for the top table."""
    reg_pair = pair.replace("_", "")
    family = f"S1-{reg_pair}"
    idxs = [i for i in registry._live_indices(records, reg_pair) if records[i]["family"] == family]
    live = {records[i]["status"]: (i + 1, records[i]) for i in idxs}
    if sorted(live) != sorted(STEPS) or len(idxs) != 3:
        raise ReportConsistencyError(
            f"{family}: expected exactly one live record at each of {STEPS}; found {[records[i]['status'] for i in idxs]}"
        )
    rec_disc, rec_stab, rec_gate = (live[s][1]["detail"] for s in STEPS)

    path = _find_file(pair, data_dir, raw_dir)
    if path is None:
        raise FileNotFoundError(f"no {pair} 1d feather file under {data_dir}")
    file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    bundle = load_bundle(data_dir, pair, ["1d"], raw_dir=raw_dir)
    full_df = bundle["1d"]
    df = truncate_at_cutoff(full_df)
    closes = df["close"]

    # ---- 1. origin facts -------------------------------------------------------
    info = formula_s1.origin_report(df)
    origins = info["oset"]["origins"]
    struct = info["structure"]
    first_origin = origins[0]
    _check("n origins", info["n_origins"], rec_disc["n"])
    if info["first_origin"].isoformat() != rec_disc["origins"]["first_origin"] or info["last_origin"].isoformat() != rec_disc["origins"]["last_origin"]:
        raise ReportConsistencyError("origin dates differ from the registry's discovery record")

    # ---- 2. discovery table ----------------------------------------------------
    cells = formula_s1.discovery_all_cells(closes, origins)
    rec_cells = pd.DataFrame(rec_disc["all_cells"]).set_index(["L", "h"])
    cal = formula_s1._calendar(df)["close"]
    rows = []
    for _, c in cells.iterrows():
        key = (int(c["L"]), int(c["h"]))
        for col in ("slope", "se", "t_stat", "p_value", "p_holm", "p_bonferroni"):
            _check(f"discovery cell {key} {col}", c[col], rec_cells.loc[key, col])
        x = formula_s1.predictor(cal, key[0]).reindex(origins)
        y = formula_s1.target(cal, key[1]).reindex(origins)
        corr = float(np.corrcoef(x.to_numpy(), y.to_numpy())[0, 1])
        primary = key == (formula_s1.PRIMARY_L, formula_s1.PRIMARY_H)
        rows.append(
            [key[0], key[1], "primary" if primary else "exploratory", _f(c["slope"]), _f(c["se"]), _f(corr, ".4f"),
             _f(c["t_stat"], ".3f"), _f(c["p_value"], ".4g"), _f(c["p_holm"], ".4g"), _f(c["p_bonferroni"], ".4g"),
             _f(MDE_MULTIPLIER * c["se"]), int(c["n"])]
        )
    disc_table = _md_table(
        ["L", "h", "tag", "slope", "HAC SE", "corr(x,y)", "HAC t", "one-sided p", "Holm (within 10)", "Bonferroni", "MDE (80% power)", "n"], rows
    )
    prim = cells[(cells["L"] == formula_s1.PRIMARY_L) & (cells["h"] == formula_s1.PRIMARY_H)].iloc[0]
    _check("primary slope vs record", prim["slope"], rec_disc["slope"])
    _check("primary p vs record", prim["p_value"], rec_disc["p_value"])

    # ---- 3. stability ----------------------------------------------------------
    stab = formula_s1.s1_stability(df, origins, R=int(rec_stab["R"]), seed=int(rec_stab["seed"]), mean_block=float(rec_stab["mean_block_length"]))
    _check("stability p_stab", stab["p_stab"], rec_stab["p_value"])
    _check("stability T", stab["T"], rec_stab["T"])
    if not np.allclose(stab["s_b"], rec_stab["s_b"], rtol=1e-9, atol=1e-12):
        raise ReportConsistencyError("per-block s_b differ from the registry's stability record")
    stab_rows = [
        [i, start, cnt, _f(sb, ".3f"), _f(cb, ".6g")]
        for i, (start, cnt, sb, cb) in enumerate(zip(stab["block_starts"], stab["block_origin_counts"], stab["s_b"], stab["c_b"]))
    ]
    stab_table = _md_table(["block", "start", "origins", "s_b", "c_b (block score)"], stab_rows)

    # ---- 4. by-year / leave-one-year-out (primary cell) -------------------------
    est = formula_s1.make_primary_estimator(closes, origins)
    ns = nonstationarity.non_stationarity_report(df.loc[origins], est)
    _check("by-year pooled estimate vs record slope", ns["pooled_estimate"], rec_disc["slope"])
    by_year = ns["by_year"]
    ns_rows = []
    for _, r in by_year.iterrows():
        yr = int(r["period"])
        judged = bool(r["judged"])
        loo = ns["leave_one_out"].get(yr)
        ns_rows.append(
            [yr, int(r["n"]), int(r["days_covered"]), _f(r["estimate"]), "yes" if judged else "no (< 120 days)",
             _f(loo) if loo is not None else "-",
             ("YEAR-DRIVEN" if ns["year_driven"].get(yr) else "no") if judged else "-",
             ("same sign" if ns["sign_agreement"].get(yr) else "opposite sign") if judged else "-"]
        )
    ns_table = _md_table(
        ["year", "origins", "days covered", "slope (that year)", "judged", "slope without that year", "year-driven?", "year's sign vs pooled"], ns_rows
    )

    # ---- 5. economic gate at stress cost + buy-and-hold comparators ---------------
    stress = rule_evaluator.STRESS_COST_PER_SIDE
    signal = formula_s1.primary_signal(df)
    gate = economic_gate.economic_gate(df, first_origin, signal, stress)
    _check("gate pooled net return", gate["pooled_net_return"], rec_gate["pooled_net_return"])
    _check("gate pass rate", gate["pass_rate"], rec_gate["pass_rate"])
    data = df[df.index >= first_origin]
    strat = rule_evaluator.evaluate_rule(data, signal.loc[data.index], stress)
    _check("evaluate_rule net return == gate pooled", strat["net_return"], gate["pooled_net_return"])
    ones = pd.Series(1, index=df.index)
    bh_gate = economic_gate.economic_gate(df, first_origin, ones, stress)
    bh = rule_evaluator.evaluate_rule(data, ones.loc[data.index], stress)
    held = rule_evaluator.held_positions(signal.loc[data.index])
    forced = [t for t in strat["trades"] if t["forced"]]
    tiles = blocks.tile_blocks(df, first_origin)
    block_rows = []
    for t in tiles:
        b = t["block_index"]
        sr, br = gate["block_returns"][b], bh_gate["block_returns"][b]
        block_rows.append([b, t["start"].date(), "partial" if t["is_final_partial"] else "full", _f(sr, ".4f"), _f(br, ".4f")])
    block_table = _md_table(["block", "start", "kind", "strategy net", "buy-and-hold net"], block_rows)
    bh_pass = bh_gate["pass_rate"]
    gate_lines = [
        f"- Strategy (pre-registered rule: long from the next open if x > 0 at the close, else cash), stress cost {stress:.4%} per side: "
        f"pooled net return **{_f(gate['pooled_net_return'])}** (gross {_f(strat['gross_return'])}); non-negative full blocks "
        f"**{_f(gate['pass_rate'], '.1%')}** ({sum(1 for v in gate['full_block_returns'].values() if v >= 0)} of {len(gate['full_block_returns'])}); "
        f"recorded verdict: passes_pooled={gate['passes_pooled']}, passes_block_rate={gate['passes_block_rate']}, passes={gate['passes']}.",
        f"- Trades: {strat['n_trades']} position-change events (entries and exits, including the forced final exit); "
        f"{len(strat['trades'])} complete round trips; hit rate (round trips with net return > 0): {_f(strat['hit_rate'], '.1%')}; "
        f"long on {_f(float(held.mean()), '.1%')} of the days.",
        "- End-of-sample exit: every evaluation segment starts flat and is forced to exit at its last close, charged as an exit cost "
        + (f"(labeled forced exit; this run's forced exit: entered {forced[0]['entry_time'].date()}, net {_f(forced[0]['net_return'], '.4f')}). " if forced else "(this run was flat at the end, so no forced exit occurred). ")
        + f"The segment runs from the first origin {first_origin.date()} to the last discovery bar {df.index[-1].date()}; no holdout bar is touched.",
        f"- Buy-and-hold comparator (R4), same evaluator, same segment, same blocks, same stress cost (one entry and one forced exit): "
        f"pooled net return **{_f(bh_gate['pooled_net_return'])}** (price-only, before costs: {_f(bh['gross_return'])}); non-negative full blocks "
        f"**{_f(bh_pass, '.1%')}** ({sum(1 for v in bh_gate['full_block_returns'].values() if v >= 0)} of {len(bh_gate['full_block_returns'])}).",
    ]

    # ---- 6. registry ------------------------------------------------------------
    holm = {s: registry.holm_at_step(records, reg_pair, s) for s in STEPS}
    reg_rows = [[live[s][0], s, live[s][1]["timestamp_utc"]] for s in STEPS]
    reg_table = _md_table(["record (line in registry.jsonl)", "status", "timestamp (UTC)"], reg_rows)
    holm_rows = []
    for s in STEPS:
        h = holm[s].get(family)
        holm_rows.append([s, len(holm[s]), _f(h["p_raw"], ".6g") if h else "-", _f(h["p_holm"], ".6g") if h else "-"])
    holm_table = _md_table(["step", "families at this step", "p (raw)", "Holm across candidates"], holm_rows)

    # ---- 7. cutoff ---------------------------------------------------------------
    after = int((df.index > CUTOFF).sum())
    cutoff_line = (
        f"The discovery frame (the file truncated at the cutoff {CUTOFF} before any computation) ends at {df.index[-1].date()} and holds "
        f"**{after}** rows after the cutoff (file: {len(full_df)} rows, {full_df.index[0].date()} to {full_df.index[-1].date()}; "
        f"{len(df)} discovery rows)."
    )
    if after != 0:
        raise ReportConsistencyError(f"{after} rows after the cutoff in the discovery frame")

    gate_full_same = len([t for t in tiles if not t["is_final_partial"]]) == info["n_full_blocks"]
    text = f"""## {pair}  ({family})

Data file `{path.name}`: {path.stat().st_size} bytes, sha256 `{file_sha}`.

### 1. Origin facts
- First origin {info['first_origin'].date()}, last origin {info['last_origin'].date()}; **{info['n_origins']} origins** (nominal {info['n_nominal']}, excluded for gaps **{info['n_excluded_gap']}**, missing calendar days {info['n_missing_days']}).
- **{info['n_full_blocks']} full {formula_s1.BLOCK_DAYS}-day blocks** (origins per full block min/median/max {info['block_origins_min']}/{info['block_origins_median']}/{info['block_origins_max']}); partial block: **{info['partial_block_origins']} origins** (centred on, never scored).
- Economic-gate tiling over the discovery rows from the same first origin has the same full blocks: {gate_full_same}.

### 2. Discovery table (10 cells, one common origin set, one-sided p, Holm within the 10)
Primary cell L=40, h=5; the other nine are exploratory. slope = OLS of the forward log return on x (x in trailing-30-day-sigma units); HAC = Newey-West (5 lags h=1, 10 lags h=5); corr = Pearson correlation of x and y at the common origins; MDE = {MDE_MULTIPLIER:.3f} x HAC SE (one-sided 5% test, 80% power; computed from the SE, never post-hoc power).

{disc_table}

### 3. Stability (amended statistic, Work Order 1.5 section 3)
**T = {_f(stab['T'], '.4f')}, p_stab = {_f(stab['p_stab'], '.6g')}** (B = {stab['B']} full blocks, R = {stab['R']} bootstrap replicates, mean block length {stab['mean_block_length']:g} days, seed {stab['seed']}); share of blocks with s_b > 0: **{_f(stab['share_blocks_positive'], '.1%')}**; recorded `passes` (p_stab < 0.05, before any across-candidate Holm): **{rec_stab['passes']}**.

{stab_table}

### 4. By-year and leave-one-year-out (primary cell's slope; years with fewer than 120 days are shown, not judged)
Pooled slope {_f(ns['pooled_estimate'])}. Year-driven flag (dropping one judged year cuts the slope by more than half or flips its sign): **any year-driven = {ns['any_year_driven']}**; every judged year's own sign agrees with the pooled sign: {ns['all_judged_years_agree']}.

{ns_table}

### 5. Economic gate at stress cost, with buy-and-hold comparators (R4)
{chr(10).join(gate_lines)}

Per-block returns (strategy and buy-and-hold over the same blocks; the partial block is included in the pooled figures, not in the block count):

{block_table}

### 6. Registry
Records written by step 5 (live, after the void markers of commit {{VOID}}):

{reg_table}

`cumulative_count` for {reg_pair}: **{registry.cumulative_count(records, reg_pair)}**; `cumulative_cells`: **{registry.cumulative_cells(records, reg_pair)}**. `holm_at_step` (across candidates; a family of one is unadjusted; the economic gate is a pass/fail rule with no p-value, so its Holm is undefined):

{holm_table}

### 7. Cutoff
{cutoff_line}
"""
    summary = {
        "pair": pair,
        "n_origins": info["n_origins"],
        "primary_p": float(prim["p_value"]),
        "primary_p_holm": float(prim["p_holm"]),
        "primary_slope": float(prim["slope"]),
        "stab_p": float(stab["p_stab"]),
        "stab_pass": bool(rec_stab["passes"]),
        "gate_pooled": float(gate["pooled_net_return"]),
        "gate_rate": float(gate["pass_rate"]),
        "gate_pass": bool(gate["passes"]),
        "bh_pooled": float(bh_gate["pooled_net_return"]),
        "bh_rate": float(bh_gate["pass_rate"]),
        "any_year_driven": bool(ns["any_year_driven"]),
    }
    return text, summary


CHOICES = [
    "Void design (amendment A1, message-14): a void marker is one `void_pre_fix` record; every record of that (family, pair) written BEFORE its latest marker is void; refuses families with a live frozen/holdout_consumed record. Void commit of step 1: {VOID}.",
    "Registry hygiene (message-15): `append_record` refuses the live registry without `commit_to_registry=True`; the default registry is scratch; step 5 used the flag once per pair after a scratch dry run whose records the live records equal.",
    "Origins (message-16): one common origin set on a complete daily calendar; a nominal origin needs every bar it uses (C_t, C_t-L for each L, the 31 closes behind sigma30, C_t+h for both h, the entry bar of day t+1) or it is excluded and counted; blocks are 90 calendar days tiled from the first origin, per-block index sets, partial block never scored. Here no gaps occurred.",
    "Stability (message-17): global centring over the whole origin set including the partial block's origins (M1 ruling 1); bootstrap pool is the genuine returns r[1:] with the r[0]=0 anchor never resampled; R = 2000, mean block 20 days, seed 12345 (my choice, stored); `combine` follows the reference exactly; a series with missing days is refused. The acceptance run's S2-Gaussian row (0.085 against a band of 0.07) is OPEN for the mathematician (message-17); it does not concern S1.",
    "Economic gate: unchanged (R4). It tiles the discovery rows (through the last discovery bar) from the common set's first origin, so its partial block runs to that bar while the origin-based partial block ends at the last origin; the pooled figure includes the partial block.",
    "Buy-and-hold comparator (R4): the same evaluator, segment (first origin to the last discovery bar), blocks and stress cost, with the signal fixed at 1 (it enters at the open after the first origin and pays one entry and one forced exit). 'Price-only' is the same segment before costs. Whether 'over the same origins' should instead end at the last origin is the mathematician's call; I used the gate's own segment.",
    "MDE: {MDEM} x HAC SE (z 0.95 + z 0.80: one-sided 5% test, 80% power), in slope units; computed from the standard error as answer-01 requires. Correlation: Pearson, descriptive, at the common origins (the HAC SE is for the slope only).",
    "By-year: calendar years of the origin dates (the first origin is in January 2018, the last in August 2025); the estimator is the primary cell's HAC regression slope on that year's origins, via the production hooks; the year-driven rule and the 120-day rule are `nonstationarity.py` as built in item 2.",
    "P-values are one-sided in the pre-registered positive direction; Holm within the 10 cells is the family adjustment; across candidates each pair has a family of one at the discovery and stability steps, so the adjusted p equals the raw p there; the economic gate has no p-value.",
    "Cutoff: the loader reads the full daily file and `truncate_at_cutoff` is applied before any computation (the item-2 pattern), so no post-cutoff row enters any figure; the check above counts rows after the cutoff in the discovery frame.",
    "Nothing in this report is a recommendation. Freeze and forward-test were not run and the holdout was not touched; the stability and economic-gate outcomes are as recorded (`passes`).",
]


def build_report(
    pairs: list[str],
    data_dir: Path,
    raw_dir: Path | None,
    registry_path: Path,
    void_commit: str,
    run_commit: str,
    code_commit: str = "unknown",
) -> str:
    """Return the markdown report. Raises ReportConsistencyError if anything recomputed differs
    from the registry, FileNotFoundError if a data file is missing. Writes nothing."""
    records = registry.load_records(registry_path)
    sections, summaries = [], []
    for pair in pairs:
        text, summ = _pair_section(pair, data_dir, raw_dir, records)
        sections.append(text.replace("{VOID}", void_commit))
        summaries.append(summ)
    top_rows = [
        [s["pair"], s["n_origins"], _f(s["primary_slope"]), _f(s["primary_p"], ".4g"), _f(s["primary_p_holm"], ".4g"),
         _f(s["stab_p"], ".4g"), s["stab_pass"], f"{s['gate_pooled']:.4g}", f"{s['gate_rate']:.1%}", s["gate_pass"],
         f"{s['bh_pooled']:.4g}", f"{s['bh_rate']:.1%}", s["any_year_driven"]]
        for s in summaries
    ]
    top = _md_table(
        ["pair", "origins", "primary slope", "primary one-sided p", "Holm within 10", "stability p_stab", "stability passes",
         "gate pooled net", "gate non-negative blocks", "gate passes", "buy-and-hold pooled", "buy-and-hold non-negative blocks", "any year-driven"],
        top_rows,
    )
    choices = "\n".join(f"{i}. " + c.replace("{VOID}", void_commit).replace("{MDEM}", f"{MDE_MULTIPLIER:.3f}") for i, c in enumerate(CHOICES, 1))
    return f"""# S1 report: ETH_USDT and BTC_USDT (Work Order 1.5 step 6)

Generated {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')} by `s1_report.py` (read-only) at repo commit {code_commit}. Registry records are from the step-5 live run, commit {run_commit}; the pre-fix S1 records were voided by commit {void_commit}. Every figure below was recomputed from the discovery data and reproduces the registry's recorded figure (the generator refuses to run otherwise). Freeze and forward-test were not run; the holdout is untouched. This report states recorded outcomes and makes no recommendation.

### Summary of recorded outcomes
{top}

{chr(10).join(sections)}

## 8. Interpretation choices (all of them)
{choices}
"""


def main() -> None:
    p = argparse.ArgumentParser(description="Write the S1 report (read-only; reads data and the live registry).")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--pair", action="append", choices=["ETH_USDT", "BTC_USDT"])
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--raw-dir", type=Path, default=None)
    p.add_argument("--registry-path", type=Path, default=registry.LIVE_REGISTRY_PATH)
    p.add_argument("--out", type=Path, help="report file to write (the only file this script writes)")
    p.add_argument("--void-commit", default="ac63ff2")
    p.add_argument("--run-commit", default="unknown")
    p.add_argument("--code-commit", default="unknown")
    a = p.parse_args()
    if a.self_test:
        _self_test()
        return
    if not a.pair or a.out is None:
        p.error("--pair and --out are required")
    text = build_report(a.pair, a.data_dir, a.raw_dir, a.registry_path, a.void_commit, a.run_commit, a.code_commit)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(f"wrote {a.out} ({len(text.splitlines())} lines)")


def _self_test() -> None:
    import json
    import tempfile

    import run_s1

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_dir = tmp / "data"
        data_dir.mkdir()
        rng = np.random.default_rng(5)
        n = 1700
        idx = pd.date_range("2018-01-01", periods=n, freq="1D", tz="UTC")
        base = rng.normal(0, 0.01, n)
        closes = pd.Series(100 * np.exp(np.cumsum(base)), index=idx)
        x40 = formula_s1.predictor(closes, 40)
        shifted = np.zeros(n)
        for t in range(n):
            if not np.isnan(x40.iloc[t]):
                for s_ in range(t + 1, min(t + 6, n)):
                    shifted[s_] += 0.002 * x40.iloc[t] / 5.0
        closes = pd.Series(100 * np.exp(np.cumsum(base + shifted)), index=idx)
        pd.DataFrame(
            {"open": closes.shift(-1).bfill(), "high": closes, "low": closes, "close": closes, "volume": 1.0}, index=idx
        ).reset_index(names="date").to_feather(data_dir / "ETH_USDT-1d.feather")
        reg_path = tmp / "registry.jsonl"
        run_s1.run_s1("ETH_USDT", data_dir, registry_path=reg_path, stability_R=200)
        before = reg_path.read_bytes()

        text = build_report(["ETH_USDT"], data_dir, None, reg_path, "abc1234", "def5678", "0123456")
        assert reg_path.read_bytes() == before, "the report must not write the registry"
        for needle in ("### 1. Origin facts", "### 2. Discovery table", "### 3. Stability", "### 4. By-year", "### 5. Economic gate",
                       "### 6. Registry", "### 7. Cutoff", "## 8. Interpretation choices", "Buy-and-hold comparator", "abc1234", "def5678",
                       "rows after the cutoff", "Summary of recorded outcomes"):
            assert needle in text, f"report lacks {needle!r}"
        assert text.count("| primary |") == 1 and text.count("| exploratory |") == 9, "ten tagged cells, one primary"
        assert "{VOID}" not in text and "{MDEM}" not in text and "{MDE_MULTIPLIER" not in text, "unfilled placeholder"
        assert f"**{1700 - 165} origins**" in text and "**0** rows after the cutoff" in text

        # Tampering with the registry must make the report refuse (it cannot disagree with the registry).
        lines = [json.loads(l) for l in reg_path.read_text().splitlines()]
        for step_idx, key, new in ((1, "p_value", 0.123456), (2, "pooled_net_return", 9.99), (0, "slope", 0.5)):
            tampered = json.loads(json.dumps(lines))
            tampered[step_idx]["detail"][key] = new
            tp = tmp / f"tampered_{step_idx}.jsonl"
            tp.write_text("\n".join(json.dumps(r) for r in tampered) + "\n")
            try:
                build_report(["ETH_USDT"], data_dir, None, tp, "a", "b")
            except ReportConsistencyError:
                pass
            else:
                raise AssertionError(f"a tampered {key} must be refused")
        # A registry with a missing step is refused too.
        short = tmp / "short.jsonl"
        short.write_text("\n".join(json.dumps(r) for r in lines[:2]) + "\n")
        try:
            build_report(["ETH_USDT"], data_dir, None, short, "a", "b")
        except ReportConsistencyError:
            pass
        else:
            raise AssertionError("a registry without the economic_gate record must be refused")
        # Missing data file.
        try:
            build_report(["BTC_USDT"], data_dir, None, reg_path, "a", "b")
        except (FileNotFoundError, ReportConsistencyError):
            pass
        else:
            raise AssertionError("a missing data file must be refused")
    print(
        "Self-test passed: on synthetic data the report has every required section with the ten tagged cells, "
        "reproduces the registry's discovery, stability and economic-gate figures, never writes the registry, and "
        "refuses a registry whose recorded figures were tampered with or whose records are incomplete, and a missing data file."
    )


if __name__ == "__main__":
    main()
