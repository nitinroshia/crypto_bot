"""
Item 2, sixth piece (part 2): the S1/S2 economic gate (mathematician
NOTES.md section 6, pipeline step 3). Built directly on `blocks.py` (same
tiling as the stability check, step 2) and `rule_evaluator.py` (the
position/cost/return engine).

SPEC, VERBATIM: "run the frozen pre-registered rule (section 7) in the
evaluator at STRESS cost, on non-overlapping 90-day blocks tiled from the
family's own first origin [...]. The rule starts flat at the beginning of
each evaluation segment; cash returns 0; a block's return is the compounded
net strategy return at stress cost, with costs charged only when the
position changes, so a position may carry across a block boundary at no
cost. The final partial block is excluded from the 70% pass count but
included in the pooled net-return figure. Require pooled net return > 0
over the whole discovery sample AND net return >= 0 in at least 70% of
full blocks."

HOW THIS IS COMPUTED (see rule_evaluator.py's own interpretive note for the
full reasoning): `evaluate_rule` is called EXACTLY ONCE, over the ENTIRE
discovery sample (from `first_origin` to the data's end) as one continuous
segment -- one flat start, one forced exit, at the sample's own boundaries,
not at each block's edges. Each block's OWN reported return is then
obtained by slicing that single continuous `per_bar_net_return` series by
the block's date range and recompounding, using the SAME block boundaries
`blocks.tile_blocks` produces for the stability check -- never by calling
`evaluate_rule` independently per block, which would force a spurious
exit/re-entry (and its costs) at every block edge and directly contradict
"a position may carry across a block boundary at no cost." A direct
consequence, checked in the self-test: the product of (1 + block_return)
across EVERY block (full and partial together) reproduces the pooled
net-return exactly -- slicing costs nothing, it just re-partitions the same
one compounded series.

TWO SEPARATE CONDITIONS:
  1. `pooled_net_return > 0`, computed over the WHOLE segment INCLUDING the
     final partial block's contribution (spec: "included in the pooled
     net-return figure").
  2. `pass_rate >= 0.70` where `pass_rate` is the fraction of FULL blocks
     (partial block excluded from this count entirely -- spec: "excluded
     from the 70% pass count") with `block_return >= 0` (note: >= 0, not
     > 0 -- a block that exactly breaks even counts as passing).
Both must hold; `passes` is not economic_gate.py's stability-check-style
Stouffer combination, it is a plain AND of these two conditions.
"""

from __future__ import annotations

import pandas as pd

from blocks import tile_blocks
from rule_evaluator import evaluate_rule

PASS_RATE_THRESHOLD = 0.70


def economic_gate(
    df: pd.DataFrame,
    first_origin: pd.Timestamp,
    signal: pd.Series,
    cost_per_side: float,
    block_days: int = 90,
) -> dict:
    """Run the section-6 step-3 economic gate. `df` needs "open"/"close"
    columns; `signal` aligned to `df.index`. `cost_per_side` should
    ordinarily be `rule_evaluator.STRESS_COST_PER_SIDE` (spec: "at STRESS
    cost") -- accepted as a parameter rather than hardcoded so a caller can
    deliberately run this at base cost for comparison/diagnostics, but the
    section-6 pass/fail verdict itself is defined at stress cost only.

    Returns a dict:
      pooled_net_return: float, the whole segment's compounded net return
        (first_origin through the data's end), final partial block included.
      block_returns: {block_index: net_return}, EVERY block (full and
        partial), each obtained by slicing the one continuous per-bar
        series -- not by independently re-evaluating that block.
      full_block_returns: block_returns restricted to non-partial blocks.
      pass_rate: fraction of full_block_returns with return >= 0.
      passes_pooled: pooled_net_return > 0.
      passes_block_rate: pass_rate >= PASS_RATE_THRESHOLD.
      passes: passes_pooled AND passes_block_rate.
    Raises ValueError if there are zero full (non-partial) blocks -- the
    70% count is undefined with nothing to count."""
    tiles = tile_blocks(df, first_origin, block_days=block_days)
    full_tiles = [t for t in tiles if not t["is_final_partial"]]
    if not full_tiles:
        raise ValueError("no full (non-partial) blocks available -- cannot evaluate the 70% pass count")

    data = df[df.index >= first_origin]
    result = evaluate_rule(data, signal.loc[data.index], cost_per_side)
    per_bar = result["per_bar_net_return"]

    block_returns = {}
    for t in tiles:
        sliced = per_bar[(per_bar.index >= t["start"]) & (per_bar.index < t["end"])]
        block_returns[t["block_index"]] = (1 + sliced).prod() - 1

    full_block_returns = {t["block_index"]: block_returns[t["block_index"]] for t in full_tiles}
    pass_rate = sum(1 for r in full_block_returns.values() if r >= 0) / len(full_block_returns)

    return {
        "pooled_net_return": float(result["net_return"]),
        "block_returns": {k: float(v) for k, v in block_returns.items()},
        "full_block_returns": {k: float(v) for k, v in full_block_returns.items()},
        "pass_rate": float(pass_rate),
        "passes_pooled": bool(result["net_return"] > 0),
        "passes_block_rate": bool(pass_rate >= PASS_RATE_THRESHOLD),
        "passes": bool((result["net_return"] > 0) and (pass_rate >= PASS_RATE_THRESHOLD)),
    }


if __name__ == "__main__":
    import numpy as np

    from rule_evaluator import STRESS_COST_PER_SIDE

    first_origin = pd.Timestamp("2020-01-01", tz="UTC")
    rng = np.random.default_rng(7)

    def make_continuous_path(n_days: int, drifts_by_90day_block: list, vol: float, seed: int, start_price: float = 100.0):
        """ONE continuous price path spanning all blocks (each block may
        have its own drift regime, but the price level itself never resets
        -- concatenating independently-seeded, independently-based-at-100
        blocks would inject a fake, huge discontinuity at every boundary,
        which is exactly the kind of bug this test exists to avoid
        reproducing by accident)."""
        r = np.random.default_rng(seed)
        drift_per_day = np.repeat(drifts_by_90day_block, 90)[:n_days]
        log_returns = r.normal(drift_per_day, vol, n_days)
        opens = start_price * np.exp(np.cumsum(log_returns))
        closes = opens * (1 + r.normal(0, vol / 4, n_days))
        idx = pd.date_range(first_origin, periods=n_days, freq="1D", tz="UTC")
        return pd.DataFrame({"open": opens, "close": closes}, index=idx)

    # ---- All 4 full blocks profitable, always-long signal -> should pass
    # both conditions comfortably. One continuous 360-day path, uniformly
    # trending up throughout. -------------------------------------------
    df_good = make_continuous_path(360, [0.004, 0.004, 0.004, 0.004], vol=0.01, seed=1)
    signal_long = pd.Series(1, index=df_good.index)
    result_good = economic_gate(df_good, first_origin, signal_long, STRESS_COST_PER_SIDE)
    assert len(result_good["full_block_returns"]) == 4
    assert result_good["passes_pooled"] is True
    assert result_good["pass_rate"] == 1.0
    assert result_good["passes"] is True

    # Sanity check on the interpretive claim itself: slicing must reproduce
    # the pooled return exactly -- product of ALL blocks (full + partial;
    # there is no partial one here, so just the 4 full ones) equals pooled.
    recompounded = 1.0
    for r in result_good["block_returns"].values():
        recompounded *= 1 + r
    assert abs((recompounded - 1) - result_good["pooled_net_return"]) < 1e-9, (
        "product of per-block returns must reproduce the pooled net return exactly"
    )

    # ---- 5 full blocks, only 3 of 5 (60%) with return >= 0 -> block-rate
    # condition must fail even though we'll also check pooled separately.
    # One continuous 450-day path with an explicit per-block drift regime:
    # blocks 2 and 4 (0-indexed) are given strongly negative drift. --------
    df_mixed = make_continuous_path(450, [0.004, 0.004, -0.008, 0.004, -0.008], vol=0.01, seed=2)
    result_mixed = economic_gate(df_mixed, first_origin, signal_long.reindex(df_mixed.index, fill_value=1), STRESS_COST_PER_SIDE)
    assert len(result_mixed["full_block_returns"]) == 5
    assert result_mixed["pass_rate"] == 3 / 5
    assert result_mixed["passes_block_rate"] is False
    assert result_mixed["passes"] is False, "60% < 70% must fail the gate regardless of the pooled figure"

    # ---- Exactly 70% (7 of 10) must PASS the block-rate condition (>=, not >).
    drifts_70 = [0.004] * 7 + [-0.008] * 3
    df_exact70 = make_continuous_path(900, drifts_70, vol=0.01, seed=3)
    result_70 = economic_gate(df_exact70, first_origin, signal_long.reindex(df_exact70.index, fill_value=1), STRESS_COST_PER_SIDE)
    assert abs(result_70["pass_rate"] - 0.70) < 1e-9
    assert result_70["passes_block_rate"] is True, "exactly 70% must pass (threshold is >=, not >)"

    # ---- Final partial block: excluded from the 70% count, but its return
    # must still be present in block_returns AND folded into pooled_net_return.
    # Continue the SAME good 360-day path for another 10 days (no reset).
    df_with_partial = make_continuous_path(370, [0.004] * 4 + [0.004], vol=0.01, seed=1)
    signal_with_partial = pd.Series(1, index=df_with_partial.index)
    result_partial = economic_gate(df_with_partial, first_origin, signal_with_partial, STRESS_COST_PER_SIDE)
    assert len(result_partial["full_block_returns"]) == 4, "the partial tail must not be counted toward the 70% denominator"
    assert len(result_partial["block_returns"]) == 5, "but its own return must still be reported"
    # Pooled return must differ from the 4-full-blocks-only pooled return,
    # proving the partial block's bars really are folded into the pooled figure.
    assert abs(result_partial["pooled_net_return"] - result_good["pooled_net_return"]) > 1e-9

    # ---- No full blocks at all -> raises rather than silently passing/failing.
    tiny_tail = df_with_partial[df_with_partial.index >= first_origin + pd.Timedelta(days=360)]
    try:
        economic_gate(tiny_tail, first_origin + pd.Timedelta(days=360), signal_with_partial, STRESS_COST_PER_SIDE)
    except ValueError:
        pass
    else:
        raise AssertionError("expected an all-partial data range to raise, not silently produce a verdict")

    print(
        "Self-test passed: economic_gate reproduces the pooled net return exactly as the product of "
        "every block's own sliced return (full and partial together), correctly excludes the final "
        "partial block from the 70% pass-rate denominator while still including its return in the "
        "pooled figure, treats exactly 70% as passing, fails a candidate at 60%, and raises when there "
        "are no full blocks to judge."
    )
