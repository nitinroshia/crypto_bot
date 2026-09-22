For the developer (forward as is)

Decisions

Sample: post-break is canonical. Skip the full-history run for now, since it adds 66 more looks at the same hypotheses. Keep it as a regime-replication check for any post-break candidate.
Walk-forward: keep 90/30 and extend all three 1m stores back to 2026-01-30 (232 days, 4 splits). The pass rule changes now, before any candidate exists, so it can't be tuned to a result.
Same sign in every validate window at the fit-selected lag.
A combined validate-window statistic (Stouffer) with p < 0.05, Holm-adjusted for candidates carried forward.
No split significantly opposite.
Full pipeline: discovery (own-family Holm p < 0.05), then walk-forward, then a freeze timestamp in the manifest, then one forward test on data arriving after the freeze.
Open-price test: yes, and extend it to high and low. Build coarse bars from traded minutes only:
open = first traded minute
high/low = extremes of traded minutes
close = last traded minute
a bin with no trades carries the previous close
If mismatches go to zero, that becomes the resampling rule everywhere.
Lag units: yes. Rename the old column lag_bars and add lag_minutes. The mistake-log entry is accepted as written.

Also

Holm is the gate (Bonferroni for reference), applied within each task's pre-registered family, with the cumulative count reported.
Report correlation next to beta, because my plausibility bands are in correlation units.
Bump statsmodels>=0.15 and fix the comment in scripts/backtest.sh. No strategy backtest gets read until the scenario-A re-costing tool exists.

Tasks 3 and 4: interpretations confirmed (13 bars between events, hour-of-day, closed daily bars).

Task 1 amendments

Add a primary predictor: gap = ln(ETHFDUSD close) − ln(ETHUSDT close ÷ FDUSDUSDT close), minus its trailing 1-day median.
Target: cumulative ETH/FDUSD return from close t to close t+k, for k = 1 and 5, in flat and traded states.
That is 4 primary tests. The lagged-return version stays as specified (20 tests), so the family is 24.
Tradability check: Task 1 passes only if this passes. Use the Task 5 machinery below with gap terciles.
A real fair-value signal shows buys in the lowest-gap tercile beating the middle tercile (mirror for sells).
A last-trade artifact won't. Flat minutes leave last-trade prices stale while quotes have already moved, so lag-1 effects in flat states can be strong and untradable.

New Task 5: imbalance_filter (the data is already in the store)

Signal: taker-buy share = Σ taker_buy_base ÷ Σ volume over the 5 closed minutes before each origin. Skip zero-volume origins and report the count. Terciles come from the prior 30 days only.
Test: the Task 2 baseline with origins every 15 minutes (SEs clustered by day), split by tercile. Cover buys and sells at d = 0.10% and 0.20%, at +15 and +30 minutes.
Primary: buys, d = 0.10%, +30 minutes, top tercile minus bottom. Family: 8. It is useful if it improves the baseline by at least 0.02%.

Housekeeping: once the 1m is extended, re-run run_fingerprint.py --start-date 2026-01-30 for all timeframes, so flat % and kurtosis are on equal spans.

Send back first: the 1m extension, the open-price test and the post-break fingerprint, which are quick. Then Tasks 1, 3, 4 and 5 as each lands.
