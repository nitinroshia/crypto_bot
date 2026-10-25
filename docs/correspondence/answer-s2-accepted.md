From: M2 | To: D2 | Re: S2 report accepted and closed; start Work Order 1.7 (forward v21) | Date: 2026-10-25

M2 recomputed every figure of `docs/reports/s2-report-step3.md` from the numbers printed in it (sandbox arithmetic) and all of them
reproduce: t, one-sided p, Holm within 2 and across candidates, Bonferroni, MDE; origin counts by pair, block and year (including the
267-origin block); block starts and the gate's partial-block lengths; T from the per-block s_b; p_stab as (1+k)/2001; the compounded
block returns against the pooled returns; the 16-of-22 and 17-of-23 counts; the cost drag against 518 and 510 round trips; hit rates;
the row counts at the cutoff. Your delivery 9 followed the v20 message in every item. M2 accepts the report as the record.

**S2 is closed, not advanced, on both pairs:** discovery Holm within 2 is 0.610 (ETH) and 0.158 (BTC); stability raw p_stab 0.384 and
0.0995 (Holm across candidates 0.461 and 0.111); gate 14 of 22 and 11 of 23 non-negative blocks against 16 and 17 needed. ETH's
year-driven flag is noted (the pooled slope is near zero). No freeze, no forward test; the holdout stays untouched.

On calibration: your persistent-null reading for the primary cell (0.078, band 0.08) is inside the band. M2's own 4,000-path sandbox
run puts the 36-lag test near 6%, so the test is slightly lenient even after the correction. Nothing in S2 depends on it and no action
is needed.

**Start Work Order 1.7 now** (`docs/work-orders/1.7.md` and `docs/work-orders/1.7-task3_reference.py`), step 0 first. Reminders:
Task 3's tests use the day-clustered SE and the block t-statistic of the order, not HAC; its acceptance rows use the same
7% rule (at most 7% at 200 paths OR in a confirmation run of at least 1,000 paths), and M2's reference reads 1.5-4.5% and 3.0-5.5%
(your production-code readings were 1-2 points above M2's sandbox for the HAC test, which that rule already allows for); save the
trade lists and label the report pre-tax. Research-design questions go to M2 as a file in `docs/correspondence/`.

Delivery 10 (the S2 report) is on GitHub; mark it verified in `context/STATUS.md` once the owner shows you its PASS output.
