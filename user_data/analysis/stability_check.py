"""
Item 2, fifth piece: the section-6 stability check for S1/S2-style
candidates (mathematician NOTES.md section 6, pipeline step 2). This is
what replaces the current WRONG `research_cli.evaluate_fixed_lag` verdict
(see context/developer/NOTES.md's transitional note) -- it is NOT
independent evidence (section 6 says so explicitly), it's a robustness
check gating whether a candidate is even allowed to proceed to the economic
gate (step 3).

SPEC, VERBATIM (section 6, step 2, S1/S2 bullet): "use the SAME
non-overlapping 90-day blocks as the economic gate (step 3), tiled from the
family's own first origin [-- see blocks.py, shared with step 3 for exactly
this reason]. Each block's sign is compared against the pre-registered
direction; combined Stouffer z (equal weights) needs one-sided p < 0.05
(Holm across candidates carried forward); no block may be significantly
opposite (two-sided p < 0.05, opposite sign); the final partial block is
excluded from this check."

THREE SEPARATE CONDITIONS, ALL FROM ONE SENTENCE -- don't collapse them:
  1. Combined evidence: Stouffer-combine every JUDGED block's own z-score
     (oriented so the pre-registered direction is positive), and require a
     ONE-SIDED p < 0.05 on the combined z. This is `p_value` /
     `combined_significant` below -- the number that eventually feeds
     `registry.holm_at_step(..., step="stability")` ("Holm across
     candidates carried forward" -- that Holm step itself is registry.py's
     job, already built; this module only produces the raw p-value it
     needs).
  2. Veto: even if condition 1 passes, ANY judged block whose OWN two-sided
     test is significant (p < 0.05) AND opposite in sign to the
     pre-registered direction fails the candidate outright. This is
     deliberately independent of the combined result -- a candidate can
     have a strong combined z and still fail here if even one block
     contradicts it loudly enough. `any_significant_opposite` /
     `veto_triggered` below.
  3. The final partial block (blocks.tile_blocks's `is_final_partial=True`)
     is excluded from BOTH 1 and 2 entirely -- it contributes to neither
     the Stouffer sum nor the veto check, however extreme its own number
     looks. (Contrast with the economic gate, step 3, which excludes it
     from a different count but still includes it in a pooled figure --
     see blocks.py's docstring. This module does not reuse that logic;
     step 3 is separate, not-yet-built work.)

ORIENTATION: `pre_registered_direction` is +1 or -1 (S1 is positive, S2 is
negative -- section 6, step 2's last bullet). Every block's raw z from
`block_test` is compared against this directly for the veto (raw sign vs
raw direction), and separately ORIENTED (multiplied by
`pre_registered_direction`) before Stouffer-summing, so that "the combined
z supports the pre-registered direction" always corresponds to a POSITIVE
oriented sum, regardless of whether the candidate's own registered
direction is + or -. This lets `p_value` always be read the same way
(smaller = stronger support for whatever direction was pre-registered) for
both S1 (positive) and S2 (negative) without the caller needing to
special-case S2's sign anywhere in this module.

`block_test(subset_df) -> (z, p_two_sided)` is caller-supplied and
deliberately generic, exactly like `nonstationarity.py`'s `estimator` --
S1 and S2 compute their own z-score differently (different underlying
statistic entirely), and this module has no opinion on how it's computed,
only on how blocks are combined and vetoed. `z` MUST be a genuine
standard-normal test statistic (not an arbitrary signed magnitude) for the
Stouffer combination to be statistically valid -- this module does not
and cannot verify that property of the caller's function.
"""

from __future__ import annotations

from math import erf, sqrt

import pandas as pd

from blocks import tile_blocks

ALPHA = 0.05


def _norm_sf(z: float) -> float:
    """Upper-tail standard normal survival function, 1 - CDF(z), without
    pulling in scipy just for this (matches leadlag.py's own convention --
    see its `_norm_cdf`)."""
    return 0.5 * (1 - erf(z / sqrt(2)))


def stability_check(
    df: pd.DataFrame,
    first_origin: pd.Timestamp,
    pre_registered_direction: int,
    block_test,
    block_days: int = 90,
    alpha: float = ALPHA,
) -> dict:
    """Run the section-6 stability check. `pre_registered_direction` must be
    +1 or -1. Returns a dict:
      blocks: per-JUDGED-block results (final partial block excluded
        entirely -- not even listed here), each {"block_index", "start",
        "end", "z", "p_two_sided", "sign", "significant_opposite"}.
      n_blocks_judged: len(blocks) above.
      combined_z: Stouffer-combined z (equal weights) of each judged
        block's ORIENTED z (z * pre_registered_direction), i.e. positive
        means "supports the pre-registered direction".
      p_value: one-sided p-value from combined_z (upper-tail of the
        oriented statistic) -- feed this into
        `registry.holm_at_step(..., step="stability")`'s detail["p_value"].
      combined_significant: p_value < alpha.
      any_significant_opposite: True if ANY judged block is
        significant_opposite (condition 2, the veto).
      passes: combined_significant AND NOT any_significant_opposite -- the
        overall stability-check verdict BEFORE any cross-candidate Holm
        adjustment (which is registry.py's job, not this function's).
    Raises ValueError if `pre_registered_direction` is not +1 or -1, or if
    there are zero judged blocks (nothing to combine -- e.g. all data fell
    in a single final-partial block)."""
    if pre_registered_direction not in (1, -1):
        raise ValueError(f"pre_registered_direction must be +1 or -1, got {pre_registered_direction!r}")

    tiles = tile_blocks(df, first_origin, block_days=block_days)
    judged = [t for t in tiles if not t["is_final_partial"]]
    if not judged:
        raise ValueError("no judged (non-final-partial) blocks available -- cannot run a stability check")

    block_results = []
    for t in judged:
        z, p_two_sided = block_test(t["data"])
        sign = 1 if z > 0 else (-1 if z < 0 else 0)
        significant_opposite = (p_two_sided < alpha) and (sign != 0) and (sign != pre_registered_direction)
        block_results.append(
            {
                "block_index": t["block_index"],
                "start": t["start"],
                "end": t["end"],
                "z": z,
                "p_two_sided": p_two_sided,
                "sign": sign,
                "significant_opposite": significant_opposite,
            }
        )

    oriented_zs = [r["z"] * pre_registered_direction for r in block_results]
    k = len(oriented_zs)
    combined_z = sum(oriented_zs) / sqrt(k)
    p_value = _norm_sf(combined_z)
    combined_significant = p_value < alpha
    any_significant_opposite = any(r["significant_opposite"] for r in block_results)

    return {
        "blocks": block_results,
        "n_blocks_judged": k,
        "combined_z": combined_z,
        "p_value": p_value,
        "combined_significant": combined_significant,
        "any_significant_opposite": any_significant_opposite,
        "passes": combined_significant and not any_significant_opposite,
    }


if __name__ == "__main__":
    def z_test(subset: pd.DataFrame) -> tuple:
        """Toy block_test for the self-test only: one-sample z-test of
        mean(value) != 0, treating the sample std as the population SE
        (fine for synthetic data with a known, fixed generating std)."""
        x = subset["value"].to_numpy()
        n = len(x)
        mean = x.mean()
        se = x.std(ddof=1) / sqrt(n)
        z = mean / se
        p_two_sided = 2 * _norm_sf(abs(z))
        return z, p_two_sided

    import numpy as np

    first_origin = pd.Timestamp("2020-01-01", tz="UTC")

    def make_block_data(n_blocks: int, days_per_block: int, means: list, std: float, seed: int) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        frames = []
        start = first_origin
        for m in means:
            idx = pd.date_range(start, periods=days_per_block, freq="1D", tz="UTC")
            frames.append(pd.DataFrame({"value": rng.normal(m, std, size=days_per_block)}, index=idx))
            start = start + pd.Timedelta(days=days_per_block)
        return pd.concat(frames)

    # ---- Clearly stable, positive-direction candidate (S1-like): 4 full
    # 90-day blocks, all with a solid positive mean -> combined z should be
    # comfortably significant, no block opposite. -------------------------
    df_stable = make_block_data(4, 90, [0.3, 0.35, 0.28, 0.32], std=1.0, seed=1)
    result_stable = stability_check(df_stable, first_origin, pre_registered_direction=1, block_test=z_test)
    assert result_stable["n_blocks_judged"] == 4
    assert result_stable["combined_significant"] is True
    assert result_stable["any_significant_opposite"] is False
    assert result_stable["passes"] is True

    # ---- Same shape, but pre-registered NEGATIVE (S2-like): flip every
    # mean's sign, register direction=-1 -- must pass identically (tests
    # that orientation, not just "positive z", is what's actually checked).
    df_stable_neg = make_block_data(4, 90, [-0.3, -0.35, -0.28, -0.32], std=1.0, seed=1)
    result_stable_neg = stability_check(df_stable_neg, first_origin, pre_registered_direction=-1, block_test=z_test)
    assert result_stable_neg["passes"] is True
    assert result_stable_neg["combined_z"] > 0, "oriented z must be positive once flipped to match direction=-1"

    # ---- Weak/noisy blocks: combined z should fail to reach significance
    # even though nothing is significantly opposite. -----------------------
    df_weak = make_block_data(4, 90, [0.02, -0.01, 0.03, 0.0], std=1.0, seed=2)
    result_weak = stability_check(df_weak, first_origin, pre_registered_direction=1, block_test=z_test)
    assert result_weak["combined_significant"] is False
    assert result_weak["passes"] is False

    # ---- Veto case: strong combined evidence, but one block is
    # SIGNIFICANTLY opposite -- must fail overall despite passing condition 1.
    df_veto = make_block_data(4, 90, [0.4, 0.4, -0.9, 0.4], std=1.0, seed=3)
    result_veto = stability_check(df_veto, first_origin, pre_registered_direction=1, block_test=z_test)
    opposite_flags = [r["significant_opposite"] for r in result_veto["blocks"]]
    assert any(opposite_flags), "the -0.9-mean block must be flagged significantly opposite"
    assert result_veto["passes"] is False, "veto must fail the candidate even if combined_significant is True"

    # ---- Final partial block: give it an extreme, wildly-opposite value --
    # it must NOT enter the Stouffer sum and must NOT trigger the veto. ----
    df_with_partial = pd.concat(
        [
            make_block_data(3, 90, [0.3, 0.3, 0.3], std=1.0, seed=4),
            pd.DataFrame(
                {"value": [-100.0] * 10},
                index=pd.date_range(first_origin + pd.Timedelta(days=270), periods=10, freq="1D", tz="UTC"),
            ),
        ]
    )
    result_partial = stability_check(df_with_partial, first_origin, pre_registered_direction=1, block_test=z_test)
    assert result_partial["n_blocks_judged"] == 3, "the trailing 10-day sliver must not be counted as a judged block"
    assert result_partial["passes"] is True, "the extreme final-partial block must not affect the verdict at all"

    # ---- Invalid direction is rejected. ------------------------------------
    try:
        stability_check(df_stable, first_origin, pre_registered_direction=0, block_test=z_test)
    except ValueError:
        pass
    else:
        raise AssertionError("expected an invalid pre_registered_direction to be rejected")

    print(
        "Self-test passed: stability_check combines judged blocks via Stouffer z and requires "
        "one-sided p<0.05 in the pre-registered direction (verified for both S1-style positive and "
        "S2-style negative orientation); the opposite-block veto fails a candidate even when the "
        "combined result would otherwise pass; a genuinely partial final block is excluded from both "
        "the combination and the veto no matter how extreme its own value; an invalid direction is "
        "rejected."
    )
