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

USAGE (requires "{pair}-1d.feather" to already exist under --data-dir or
--raw-dir -- this script does not fetch data itself, see fetch_klines.py
for that):
    python3 run_s1.py --pair ETH_USDT
    python3 run_s1.py --pair BTC_USDT
    python3 run_s1.py --pair ETH_USDT --data-dir /custom/path --registry-path /custom/registry.jsonl

    python3 run_s1.py --self-test   # offline, synthetic data, no real files needed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

import economic_gate
import formula_s1
import registry
import stability_check
from cutoff import truncate_at_cutoff
from databundle import load_bundle
from rule_evaluator import STRESS_COST_PER_SIDE


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

    # ---- Step 1: discovery, all 10 cells, own-family Holm. ---------------
    all_cells = formula_s1.discovery_all_cells(closes)
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
                "all_cells": all_cells.drop(columns=["p_value_hac"], errors="ignore").to_dict(orient="records"),
            },
        },
        registry_path,
    )

    # ---- Step 2: stability check (90-day tiles, Stouffer, primary cell). -
    first_valid_idx = max(formula_s1.PRIMARY_L, formula_s1.SIGMA_WINDOW)
    if first_valid_idx >= len(discovery_df):
        raise ValueError(
            f"not enough discovery-side data for {pair} ({len(discovery_df)} rows) to even define "
            f"the primary cell's first origin (needs > {first_valid_idx})"
        )
    first_origin = discovery_df.index[first_valid_idx]
    block_test = formula_s1.make_primary_block_test(closes)
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
    )

    return {
        "family": family,
        "pair": registry_pair,
        "n_discovery": n_discovery,
        "discovery_estimate": discovery_estimate,
        "dispersion": dispersion,
        "discovery_all_cells": all_cells,
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

    s = result["stability"]
    print("\n-- Stability check (step 2) --")
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


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pair", type=str, help="e.g. ETH_USDT or BTC_USDT")
    p.add_argument("--data-dir", type=Path, default=Path("user_data/data/binance"))
    p.add_argument("--raw-dir", type=Path, default=None)
    p.add_argument("--registry-path", type=Path, default=registry.DEFAULT_REGISTRY_PATH)
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
        assert result["n_discovery"] > 700
        assert result["discovery_estimate"] > 0, "the injected trend-following edge must recover a positive slope"
        assert result["stability"]["passes"] is True, "the injected edge should pass the stability check"
        assert len(result["economic_gate"]["full_block_returns"]) >= 5

        records = registry.load_records(registry_path)
        statuses = [r["status"] for r in records if r["family"] == "S1-ETHUSDT"]
        assert statuses == ["discovery", "stability", "economic_gate"], (
            "exactly these three steps must be written, in order -- freeze/forward-test must NEVER "
            "be touched by this script"
        )
        assert len(records[0]["detail"]["all_cells"]) == 10

        # Re-running must not fail or behave as one-shot -- nothing here is
        # one-shot (that's holdout_lock.py's job, not exercised at all by
        # this script).
        run_s1("ETH_USDT", data_dir, registry_path=registry_path)
        records_after = registry.load_records(registry_path)
        assert len(records_after) == 6, "a second run must simply append three more records, not fail"

        print_report(result)  # smoke-test the report formatting itself

    print(
        "Self-test passed: run_s1 loads a synthetic feather file, truncates to the discovery cutoff, "
        "runs all 10 discovery cells with own-family Holm, the stability check, and the economic gate "
        "on the primary cell, and writes exactly discovery/stability/economic_gate to the registry -- "
        "never freeze or holdout_consumed. Confirmed re-runnable (nothing here is one-shot)."
    )


def main() -> None:
    args = build_argparser().parse_args()
    if not args.pair:
        print("error: --pair is required (e.g. --pair ETH_USDT), or pass --self-test", file=sys.stderr)
        raise SystemExit(2)
    result = run_s1(args.pair, args.data_dir, raw_dir=args.raw_dir, registry_path=args.registry_path)
    print_report(result)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        main()
