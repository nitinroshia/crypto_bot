For the developer

1. Hurdle vs. Task 5 threshold. That was an inconsistency in my rules, and it is fixed. The forward-test hurdle is the candidate's own materiality threshold, set at registration and identical in discovery and forward:

Raw signal effects measured at a taker-like entry (Task 3): 0.05% (maker candidate) or 0.20% (taker viable).
Filter differences (Task 5, and the Task 1 gate): 0.04%. A filter's difference is never compared with 0.05%, because a filter isn't a strategy return.
Forward success: one-sided p < 0.05 and an estimate at least as large as both that threshold and half the discovery estimate.
Net strategy economics (scenario A/B, adverse selection, stops) are judged later, on the strategy's backtest and dry-run against the scoreboard.

Expect marginal discovery passes (0.04–0.05%) to fail forward fairly often. That is winner's curse being filtered out, so it is the design working.

2. Entries failing the tick-through rule. Confirmed: exclude and count, with no taker re-charge, because the policy is skip-if-unfilled.

Report the implied entry fill rate and the results under both fill rules: touch (freqtrade's default, the optimistic bound) and through (the pessimistic bound, and the gate).
In dry-run, the realized fill rate should fall between the two simulated rates. If it falls outside, the fill model is wrong.
Exclusion shifts slot occupancy for later trades. That is second-order; ignore it, but note it.
Exits are different. The position is already open, so a touch-only exit stays charged as time, as specified.

3. Lag selection. Use neither |beta| nor |correlation|. Select the smallest p (largest |HAC t|) in the fit window, which is the same rule discovery uses.

Drop the "significant" pre-filter. 90-day fit windows are underpowered, and the validate window carries the inference.
|beta| favors lags whose target is more volatile, so it selects noise.
Report correlation beside beta for reading effect size.

Defaults

Reference sign: not the full-sample sign. That sign includes the validate windows, so it would flatter the combined z. Orient by the pre-registered direction where one exists:
Task 1 gap: slope negative.
Task 1 gate: lowest-gap tercile better than middle.
Task 4: volume coefficient positive.
Task 5: top minus bottom positive.
For two-sided cells (Task 3, lag scans), orient by each split's fit-window sign.
Stress: approved, with 0.12% on taker legs in both scenarios. Also add a maker stress of 0.05% on maker legs, reported as a third line ("A-stress"), because the zero-maker promotion can be withdrawn. Nothing goes to real money unless it survives A-stress.
