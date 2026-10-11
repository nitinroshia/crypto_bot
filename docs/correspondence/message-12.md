# C. ANSWER TO THE MATHEMATICIAN (reply to v11)

**Status first.** `message-12` was never forwarded or committed, so you have not seen the details below. No valid S1 results exist yet. The fix is not in the repo.

**1. The bugs.** There are three, not two.
- *Warmup (`formula_s1.py`, `predictor`).* I assumed it needed `L + 30` days. It needs `max(L, 30)`, because the two windows don't stack. This was my own assumption, in my first draft. A self-test with L=5 caught it. Found before any real run; no real data and no registry writes. You asked which file and line “the NOTES.md one” refers to. I could not tie that to any of the three bugs above, and I will not guess. Please tell me which claim you mean and I will quote the exact lines. so please grep your copy for `L+30`.
- *Block test lookback (`make_primary_block_test` / `make_primary_estimator`).* The functions recomputed x and y from each 90-day slice, starving the first `max(L, 30)` rows and dropping about half of each block's origins. A self-test caught it, because an injected positive edge showed negative per-block signs. Fixed with factories that precompute x and y on the full series and select by date. No real data and no registry writes.
- *Origin sets (§6) not implemented.* This is the one that touched real data. Both families wrote `discovery`, `stability` and `economic_gate` records on the wrong origin set. Both **must be marked `void_pre_fix`**, and that has **not yet been done**. They are still live records in the repo's `registry.jsonl`. The fix is described in the handoff above and is not yet in the repo.

**2. Re-runs and the registry.** In the code currently on `main`, `cumulative_count` counts distinct family names and `holm_at_step` reads each family's single latest record. Re-running a family therefore cannot inflate either. Voiding, however, is not possible in the current code (see the handoff). One interpretive question for you: I read "candidates that reach a step" as "currently at that step". A family that has since moved on, as `run_s1` does in one pass, drops out of the earlier step's Holm. If you meant "every candidate that has ever reached the step, each on its own record", `holm_at_step` must change.

**3. S2 first usable origin.** Positional counting is my recommendation: the masked first slot occupies position 0, as `funding.py` already counts it, so the 271st settlement is the first origin.
- BTC/USDT: **2019-12-09 00:00 UTC**.
- ETH/USDT: **2020-02-25 00:00 UTC**.
The alternative reading (masked slot not counted) lands on the same calendar date at 08:00 UTC. This is arithmetic from the recorded first-settlement dates (BTC 2019-09-10, ETH 2019-11-27) and the 8h grid. It **assumes the first native settlement is 8h-aligned**, which I have not checked against the raw files. `funding.describe_native()['first_settlement']` would settle it.

**4. S1 results, pre-fix and therefore void.** For transparency only:
- ETH primary: slope 0.00085, one-sided p 0.089 (own-family Holm 0.536). Stability: combined z = −3.94, opposite-block veto fired, fail. Economic gate: pooled net return 13.73, 59.4% of full blocks non-negative (below 70%), fail.
- BTC primary: slope 0.00114, p 0.0097 (Holm 0.097). Stability: combined z = −3.33, veto fired, fail. Economic gate: pooled net return 98.3, 65.6% of blocks non-negative, fail.
- A pooled net return above 0 is easy for a long-biased rule on assets that rose this much, so the 70%-of-blocks condition is the informative one.

**5. A stability-check calibration concern (my own simulations, not preserved).**
- *Cause:* OLS on an overlapping-window predictor (`x_40` reuses 39 of 40 days) has a negative small-sample t bias. On pure noise, mean t was about −2.17 at n=90, shrinking to about −0.25 at n=2000.
- *Null case:* on pure random-walk series with ~30 blocks, mean combined Stouffer z was about −7.7. The opposite-block veto fired in 100% of null paths.
- *Edge case:* with an injected strong edge (pooled t about +15), the veto still fired in about 67–70% of paths. Removing the per-block intercept helped but did not fix it.
- *Meaning:* the real-data stability failures above may not be evidence of a negative effect. That reading is yours to make.
- *Caveat:* the simulation scripts were lost. Please treat these as leads to reproduce, not as established figures.

**6. S1 stops at the economic gate.** Freeze and forward-test have not been run and will not be until you have reviewed post-fix results. Also note the `forward_test.py` hooks issue under "Known open issue" in the handoff.