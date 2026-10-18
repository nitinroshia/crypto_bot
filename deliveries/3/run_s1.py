"""
Orchestration script: runs S1 (`formula_s1.py`) through item 2's pipeline
-- discovery (all 10 cells, own-family Holm) -> stability check (primary
cell) -> economic gate (primary cell) -- for a given asset pair, writing
each step's result to the registry.

DELIBERATELY STOPS AFTER THE ECONOMIC GATE: `freeze_manifest.py` and
`forward_test.py` are NOT called here. Per the owner/mathematician's
explicit instruction (2026-09-26): `holdout_lock.unlock_holdout_for_forward_test`
is one-shot, and this would be its first real use for ANY candidate -- the
discovery/stability/economic-gate results are meant to be reviewed BEFORE
freezing and forward-testing proceed. Nothing in this script is one-shot,
so it is safe to re-run as many times as needed while under review (each
run appends fresh discovery/stability/economic_gate records; it never
freezes or touches the holdout).

REGISTRY HYGIENE (Work Order 1.5 step 2): by default this script writes to a
SCRATCH registry (temp/scratch-registry.jsonl) and touches nothing live. It writes
to the LIVE registry only with `--commit-to-registry`.

ORIGIN SET (Work Order 1.5 step 3): all ten cells run on ONE COMMON ORIGIN SET (see
`formula_s1.s1_origin_set`), and the stability/economic-gate tiling starts at that set's
first origin (the 161st daily close when there are no gaps), not at the primary cell's
own 41st close. `--origin-facts` prints the origin facts (first/last origin, count, gap
exclusions, full blocks, per-block counts) and the cutoff check, and writes NOTHING.
THE STABILITY STEP IS STILL THE LEGACY RULE, RETIRED BY WORK ORDER 1.5 (section 3, R3):
its numbers are not results and `--commit-to-registry` is refused until step 4 replaces it
(`STABILITY_REPLACED` below).

USAGE (requires "{pair}-1d.feather" to already exist under --data-dir or
--raw-dir -- this script does not fetch data itself, see fetch_klines.py
for that):
    python3 run_s1.py --pair ETH_USDT                          # scratch registry, live untouched
    python3 run_s1.py --pair BTC_USDT
    python3 run_s1.py --pair ETH_USDT --data-dir /custom/path --registry-path /custom/registry.jsonl
    python3 run_s1.py --pair ETH_USDT --commit-to-registry     # LIVE registry (explicit flag)
    python3 run_s1.py --pair ETH_USDT --origin-facts           # read-only origin facts, no registry

    python3 run_s1.py --self-test   # offline, synthetic data, no real files needed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

import blocks
import economic_gate
import formula_s1
import registry
import stability_check
from cutoff import CUTOFF, truncate_at_cutoff
from databundle import load_bundle
from rule_evaluator import STRESS_COST_PER_SIDE


# The old stability rule (combined Stouffer z + opposite-block veto) is retired by Work Order 1.5.
# Until step 4 replaces it, a LIVE write is refused by the CLI. Step 4 sets this True.
STABILITY_REPLACED = False

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "user_data" / "data" / "binance"


def family_name(pair: str) -> str:
    """S1-ETHUSDT / S1-BTCUSDT -- Work Order 1.4's pair-qualified naming,
    same convention registry.py itself enforces."""
    return f"S1-{pair.replace('_', '')}"


def run_s1(
    pair: str,
    data_dir: Path,
    raw_dir: Path | None = None,
    registry_path: Path = registry.DEFAULT_REGISTRY_PATH,
    timeframe: str = "1d",
    commit_to_registry: bool = False,
) -> dict:
    """Run S1's discovery, stability check, and economic gate for `pair`
    (e.g. "ETH_USDT" or "BTC_USDT"), appending each step's result to the
    registry. Returns a dict with all three steps' results for review --
    does NOT freeze or forward-test (see module docstring)."""
    family = family_name(pair)
    registry_pair = pair.replace("_", "")

    bundle = load_bundle(data_dir, pair, [timeframe], raw_dir=raw_dir)
    full_df = bundle[timeframe]
    discovery_df = truncate_at_cutoff(full_df)
    closes = discovery_df["close"]

    # ---- Origin set: ONE common set for all 10 cells (Work Order 1.5 step 3). ----
    origin_info = formula_s1.origin_report(discovery_df)
    origins = origin_info["oset"]["origins"]
    if len(origins) == 0:
        raise ValueError(
            f"not enough discovery-side data for {pair} ({len(discovery_df)} rows) to define a common "
            f"origin set (needs more than {formula_s1.PRIMARY_L * 4 + formula_s1.SIGMA_WINDOW} daily bars)"
        )
    first_origin = origins[0]
    origin_detail = {
        "first_origin": origin_info["first_origin"].isoformat(),
        "last_origin": origin_info["last_origin"].isoformat(),
        "n_origins": origin_info["n_origins"],
        "n_excluded_gap": origin_info["n_excluded_gap"],
        "n_full_blocks": origin_info["n_full_blocks"],
        "partial_block_origins": origin_info["partial_block_origins"],
    }

    # ---- Step 1: discovery, all 10 cells, own-family Holm, one common origin set. ----
    all_cells = formula_s1.discovery_all_cells(closes, origins)
    primary_row = all_cells[
        (all_cells["L"] == formula_s1.PRIMARY_L) & (all_cells["h"] == formula_s1.PRIMARY_H)
    ].iloc[0]
    n_discovery = int(primary_row["n"])
    discovery_estimate = float(primary_row["slope"])
    dispersion = float(primary_row["se"])

    registry.append_record(
        {
            "family": family,
            "pair": registry_pair,
            "status": "discovery",
            "timestamp_utc": registry.new_timestamp(),
            "detail": {
                "p_value": float(primary_row["p_value"]),
                "family_p_holm": float(primary_row["p_holm"]),
                "family_p_bonferroni": float(primary_row["p_bonferroni"]),
                "slope": discovery_estimate,
                "dispersion": dispersion,
                "n": n_discovery,
                "origins": origin_detail,
                "all_cells": all_cells.drop(columns=["p_value_hac"], errors="ignore").to_dict(orient="records"),
            },
        },
        registry_path,
        commit_to_registry=commit_to_registry,
    )

    # ---- Step 2: stability check. LEGACY RULE, RETIRED (Work Order 1.5 section 3, R3);
    # replaced in step 4. Tiled from the common origin set's first origin. -----------
    block_test = formula_s1.make_primary_block_test(closes, origins)
    stability_result = stability_check.stability_check(
        discovery_df, first_origin, pre_registered_direction=formula_s1.DIRECTION, block_test=block_test,
    )
    registry.append_record(
        {
            "family": family,
            "pair": registry_pair,
            "status": "stability",
            "timestamp_utc": registry.new_timestamp(),
            "detail": {
                "p_value": float(stability_result["p_value"]),
                "combined_z": float(stability_result["combined_z"]),
                "n_blocks_judged": stability_result["n_blocks_judged"],
                "any_significant_opposite": bool(stability_result["any_significant_opposite"]),
                "passes": bool(stability_result["passes"]),
            },
        },
        registry_path,
        commit_to_registry=commit_to_registry,
    )

    # ---- Step 3: economic gate (STRESS cost, same tiling). ----------------
    signal = formula_s1.primary_signal(discovery_df)
    econ_result = economic_gate.economic_gate(discovery_df, first_origin, signal, STRESS_COST_PER_SIDE)
    registry.append_record(
        {
            "family": family,
            "pair": registry_pair,
            "status": "economic_gate",
            "timestamp_utc": registry.new_timestamp(),
            "detail": {
                "pooled_net_return": econ_result["pooled_net_return"],
                "pass_rate": econ_result["pass_rate"],
                "passes_pooled": econ_result["passes_pooled"],
                "passes_block_rate": econ_result["passes_block_rate"],
                "passes": econ_result["passes"],
            },
        },
        registry_path,
        commit_to_registry=commit_to_registry,
    )

    return {
        "family": family,
        "pair": registry_pair,
        "n_discovery": n_discovery,
        "discovery_estimate": discovery_estimate,
        "dispersion": dispersion,
        "discovery_all_cells": all_cells,
        "origins": origin_info,
        "stability": stability_result,
        "economic_gate": econ_result,
    }


def print_report(result: dict) -> None:
    print(f"\n=== S1 report: {result['family']} ({result['pair']}) ===")
    print("\n-- Discovery (10 cells, own-family Holm) --")
    cols = ["L", "h", "slope", "se", "t_stat", "p_value", "p_holm", "p_bonferroni", "n"]
    print(result["discovery_all_cells"][cols].to_string(index=False))
    print(
        f"\nPrimary cell (L={formula_s1.PRIMARY_L}, h={formula_s1.PRIMARY_H}): "
        f"slope={result['discovery_estimate']:.6g}  SE={result['dispersion']:.6g}  n={result['n_discovery']}"
    )

    print_origin_facts(result["origins"])

    s = result["stability"]
    print("\n-- Stability check: LEGACY RULE, RETIRED by Work Order 1.5 (replaced in step 4); NOT a result --")
    print(
        f"n_blocks_judged={s['n_blocks_judged']}  combined_z={s['combined_z']:.4f}  "
        f"p_value={s['p_value']:.6g}  any_significant_opposite={s['any_significant_opposite']}  "
        f"passes={s['passes']}"
    )

    e = result["economic_gate"]
    print("\n-- Economic gate (step 3, stress cost) --")
    print(
        f"pooled_net_return={e['pooled_net_return']:.6g}  pass_rate={e['pass_rate']:.2%}  "
        f"passes_pooled={e['passes_pooled']}  passes_block_rate={e['passes_block_rate']}  "
        f"passes={e['passes']}"
    )
    print("\nNOT frozen, NOT forward-tested -- results above are for review before proceeding.\n")


def print_origin_facts(info: dict) -> None:
    """Print the origin facts of `formula_s1.origin_report` (Work Order 1.5 step 3 /
    report item 1)."""
    print("\n-- Origin set (one common set for all 10 cells) --")
    print(f"first origin: {info['first_origin'].date()}   last origin: {info['last_origin'].date()}   "
          f"span: {info['span_days']} days")
    print(f"origins used: {info['n_origins']}   nominal origins (calendar positions {info['oset']['first_position']}"
          f"..{info['oset']['last_position']}): {info['n_nominal']}   excluded for gaps: {info['n_excluded_gap']}"
          f"   missing calendar days in the sample: {info['n_missing_days']}")
    if info["excluded_gap_dates"]:
        print(f"first excluded-for-gap origins: {', '.join(info['excluded_gap_dates'])}")
    print(f"full {formula_s1.BLOCK_DAYS}-day blocks: {info['n_full_blocks']}   partial block origins: "
          f"{info['partial_block_origins']}   origins per full block (min/median/max): "
          f"{info['block_origins_min']}/{info['block_origins_median']}/{info['block_origins_max']}")


def origin_facts_for(pair: str, data_dir: Path, raw_dir: Path | None = None, timeframe: str = "1d") -> dict:
    """READ-ONLY origin facts for `pair` (Work Order 1.5 step 3). Loads the daily file,
    truncates at the cutoff, builds the common origin set and checks: the discovery frame
    holds no row after the cutoff; all 10 cells report the same n; the economic gate's
    own tiling (`blocks.tile_blocks` over the discovery rows, from the same first origin)
    has the same FULL blocks as the origin-based tiling. Writes nothing (no registry, no
    files); computes no p-values or returns."""
    bundle = load_bundle(data_dir, pair, [timeframe], raw_dir=raw_dir)
    full_df = bundle[timeframe]
    discovery_df = truncate_at_cutoff(full_df)
    info = formula_s1.origin_report(discovery_df)
    origins = info["oset"]["origins"]
    if len(origins) == 0:
        raise ValueError(f"no common origins for {pair}: {len(discovery_df)} discovery rows")
    cells_n = sorted(
        {int(v) for v in formula_s1.discovery_all_cells(discovery_df["close"], origins)["n"]}
    )
    gate_tiles = blocks.tile_blocks(discovery_df, info["first_origin"])
    gate_full = [b for b in gate_tiles if not b["is_final_partial"]]
    gate_same = len(gate_full) == info["n_full_blocks"] and all(
        g["start"] == m["start"] and g["end"] == m["end"]
        for g, m in zip(gate_full, [b for b in info["structure"]["blocks"] if b["is_full"]])
    )
    return {
        "pair": pair,
        "file_first_label": full_df.index[0],
        "file_last_label": full_df.index[-1],
        "file_rows": len(full_df),
        "discovery_rows": len(discovery_df),
        "discovery_last_label": discovery_df.index[-1],
        "rows_after_cutoff_in_discovery": int((discovery_df.index > CUTOFF).sum()),
        "cutoff": CUTOFF,
        "origins": info,
        "cell_n_values": cells_n,
        "gate_full_blocks": len(gate_full),
        "gate_blocks_same_as_origin_blocks": bool(gate_same),
        "gate_partial_days": (
            (discovery_df.index[-1] + pd.Timedelta(days=1) - gate_tiles[-1]["start"]).days if gate_tiles and gate_tiles[-1]["is_final_partial"] else 0
        ),
    }


def print_origin_facts_report(f: dict) -> None:
    print(f"\n=== S1 origin facts: {f['pair']} ===")
    print(f"daily file: {f['file_rows']} rows, {f['file_first_label'].date()} .. {f['file_last_label'].date()}")
    print(f"discovery rows (cut at {f['cutoff']}): {f['discovery_rows']}, last label {f['discovery_last_label'].date()}; "
          f"rows after the cutoff in the discovery frame: {f['rows_after_cutoff_in_discovery']}")
    print_origin_facts(f["origins"])
    print(f"cells' n values (must be one value): {f['cell_n_values']}")
    print(f"economic gate tiling (blocks.tile_blocks over the discovery rows from the same first origin): "
          f"full blocks {f['gate_full_blocks']}, same full blocks as the origin-based tiling: "
          f"{f['gate_blocks_same_as_origin_blocks']}; its partial block runs to the last discovery bar "
          f"({f['gate_partial_days']} days) while the origin-based partial block ends at the last origin "
          f"({f['origins']['partial_block_origins']} origins)")
    print("expected by Work Order 1.5 (about): 2,770 origins, 30 full blocks plus a partial block, "
          "first origin about 2018-01-24 if the file starts 2017-08-17")
    print("(no p-values or returns are computed here; nothing is written)")


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pair", type=str, help="e.g. ETH_USDT or BTC_USDT")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--raw-dir", type=Path, default=None)
    p.add_argument(
        "--registry-path", type=Path, default=None,
        help="registry file to write (default: scratch registry temp/scratch-registry.jsonl; "
        "with --commit-to-registry: the LIVE registry)",
    )
    p.add_argument(
        "--origin-facts", action="store_true",
        help="read-only: print the common origin set's facts and the cutoff check, write nothing",
    )
    p.add_argument(
        "--commit-to-registry", action="store_true",
        help="write to the LIVE registry (required for any live write; default is the scratch registry)",
    )
    p.add_argument("--self-test", action="store_true", help="run the offline self-test (no real data needed) and exit")
    return p


def _self_test() -> None:
    import tempfile

    import numpy as np

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_dir = tmp / "binance"
        registry_path = tmp / "registry.jsonl"
        data_dir.mkdir(parents=True)

        # A synthetic price series with a directly-injected, non-circular
        # trend-following edge, exactly as formula_s1.py's own self-test
        # constructs one -- long enough (900 days) for a real multi-block
        # stability check and economic gate, entirely before the discovery
        # cutoff so truncate_at_cutoff doesn't remove anything here.
        rng = np.random.default_rng(42)
        n = 900
        idx = pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC")
        base_returns = rng.normal(0, 0.01, n)
        base_closes = pd.Series(100 * np.exp(np.cumsum(base_returns)), index=idx)
        x40_base = formula_s1.predictor(base_closes, formula_s1.PRIMARY_L)
        injected = (0.003 * x40_base).fillna(0.0).to_numpy()
        adj_arr = np.zeros(n)
        for t in range(n):
            if injected[t] == 0.0:
                continue
            for s in range(t + 1, min(t + 6, n)):
                adj_arr[s] += injected[t] / 5.0
        closes = pd.Series(100 * np.exp(np.cumsum(base_returns + adj_arr)), index=idx)
        opens = closes.shift(-1).bfill()
        df = pd.DataFrame(
            {"open": opens, "high": closes, "low": closes, "close": closes, "volume": 1.0}, index=idx
        )
        df.reset_index(names="date").to_feather(data_dir / "ETH_USDT-1d.feather")

        result = run_s1("ETH_USDT", data_dir, registry_path=registry_path)

        assert result["family"] == "S1-ETHUSDT"
        assert result["n_discovery"] == n - 165, "n is the common origin set: positions 160 .. N-1-5"
        assert (result["discovery_all_cells"]["n"] == n - 165).all(), "all ten cells on one common origin set"
        assert result["origins"]["first_origin"] == idx[160] and result["origins"]["last_origin"] == idx[n - 6]
        assert result["origins"]["n_full_blocks"] == (n - 165) // 90
        assert result["discovery_estimate"] > 0, "the injected trend-following edge must recover a positive slope"
        # (The legacy stability verdict is retired by Work Order 1.5 and is not asserted; step 4 replaces it.)
        assert result["stability"]["n_blocks_judged"] >= 5
        assert len(result["economic_gate"]["full_block_returns"]) >= 5

        records = registry.load_records(registry_path)
        statuses = [r["status"] for r in records if r["family"] == "S1-ETHUSDT"]
        assert statuses == ["discovery", "stability", "economic_gate"], (
            "exactly these three steps must be written, in order -- freeze/forward-test must NEVER "
            "be touched by this script"
        )
        assert len(records[0]["detail"]["all_cells"]) == 10
        assert records[0]["detail"]["origins"]["n_origins"] == n - 165 and records[0]["detail"]["n"] == n - 165

        # ---- Read-only origin facts: same numbers, no registry, no files written. ----
        before_files = sorted(p.name for p in tmp.rglob("*"))
        facts = origin_facts_for("ETH_USDT", data_dir)
        assert sorted(p.name for p in tmp.rglob("*")) == before_files, "origin facts must write nothing"
        assert facts["origins"]["n_origins"] == n - 165 and facts["cell_n_values"] == [n - 165]
        assert facts["rows_after_cutoff_in_discovery"] == 0 and facts["discovery_last_label"] <= CUTOFF
        assert facts["gate_blocks_same_as_origin_blocks"] is True and facts["gate_full_blocks"] == (n - 165) // 90
        print_origin_facts_report(facts)

        # Re-running must not fail or behave as one-shot -- nothing here is
        # one-shot (that's holdout_lock.py's job, not exercised at all by
        # this script).
        run_s1("ETH_USDT", data_dir, registry_path=registry_path)
        records_after = registry.load_records(registry_path)
        assert len(records_after) == 6, "a second run must simply append three more records, not fail"

        # Registry hygiene (Work Order 1.5 step 2). "Live" is faked as a temp file, so a broken
        # guard could not touch the real registry. Defaults must be scratch, never live.
        import inspect

        assert (
            inspect.signature(run_s1).parameters["registry_path"].default == registry.SCRATCH_REGISTRY_PATH
            and not registry.is_live_registry(registry.DEFAULT_REGISTRY_PATH)
        ), "run_s1's default registry must be scratch"
        fake_live = tmp / "fake_live" / "registry.jsonl"
        fake_live.parent.mkdir(parents=True)
        fake_live.write_text("")
        saved_live = registry.LIVE_REGISTRY_PATH
        registry.LIVE_REGISTRY_PATH = fake_live
        try:
            try:
                run_s1("ETH_USDT", data_dir, registry_path=fake_live)
            except registry.LiveRegistryWriteRefused:
                pass
            else:
                raise AssertionError("run_s1 without the flag must refuse a live registry path")
            assert fake_live.read_text() == "", "the refused run must leave the live file untouched"
            run_s1("ETH_USDT", data_dir, registry_path=fake_live, commit_to_registry=True)
            assert len(registry.load_records(fake_live)) == 3, "with the flag, exactly the three steps are written"
        finally:
            registry.LIVE_REGISTRY_PATH = saved_live

        print_report(result)  # smoke-test the report formatting itself

    print(
        "Self-test passed: run_s1 loads a synthetic feather file, truncates to the discovery cutoff, "
        "builds ONE common origin set (positions 160..N-1-5) used by all 10 discovery cells with own-family Holm, "
        "reports the origin facts read-only, runs the (legacy, verdict not asserted) stability step, and the economic gate "
        "on the primary cell, and writes exactly discovery/stability/economic_gate to the registry -- "
        "never freeze or holdout_consumed. Confirmed re-runnable (nothing here is one-shot). "
        "A live-registry path without the commit flag is refused and the default registry is scratch."
    )


def main() -> None:
    args = build_argparser().parse_args()
    if not args.pair:
        print("error: --pair is required (e.g. --pair ETH_USDT), or pass --self-test", file=sys.stderr)
        raise SystemExit(2)
    if args.origin_facts:
        print_origin_facts_report(origin_facts_for(args.pair, args.data_dir, raw_dir=args.raw_dir))
        return
    if args.commit_to_registry and not STABILITY_REPLACED:
        print(
            "error: --commit-to-registry is refused: the stability step is still the retired legacy rule "
            "(Work Order 1.5 step 4 replaces it).", file=sys.stderr,
        )
        raise SystemExit(2)
    if args.registry_path is not None:
        registry_path = args.registry_path
    elif args.commit_to_registry:
        registry_path = registry.LIVE_REGISTRY_PATH
    else:
        registry_path = registry.SCRATCH_REGISTRY_PATH
    live = registry.is_live_registry(registry_path)
    print(
        f"REGISTRY: {'LIVE' if live else 'scratch (live registry untouched)'} -> {registry_path}"
        + ("" if (live or not args.commit_to_registry) else "   [--commit-to-registry given, but this is not the live file]"),
        file=sys.stderr,
    )
    if live and not args.commit_to_registry:
        print("error: the live registry needs --commit-to-registry", file=sys.stderr)
        raise SystemExit(2)
    result = run_s1(
        args.pair, args.data_dir, raw_dir=args.raw_dir, registry_path=registry_path,
        commit_to_registry=args.commit_to_registry,
    )
    print_report(result)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        main()
