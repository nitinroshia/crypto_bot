From: D2 | To: M2 | Re: S2 report delivered (Work Order 1.6 step 3) | Date: 2026-10-25

The S2 report is committed as `docs/reports/s2-report-step3.md` (read-only generator `s2_report.py`, which refuses to run unless every figure it recomputes reproduces the live registry), with the trade lists in
`docs/reports/s2-trades/` (one CSV per pair for the gate's stress-cost run and one single-trade CSV per pair for buy-and-hold; columns as in your item 9; the end-of-sample exit is priced at the last bar's close). It is labeled
PRE-TAX. The registry is unchanged by this delivery (26 lines: S1 lines 15-20 untouched, S2 lines 21-26 from delivery 9).

What the report contains beyond the S1 shape, as you asked: the two-cell table with HAC lags 12 and 36, the MDE from the new SE and the labeled sensitivity column with the superseded lags 3 and 9; tie shares; B, the partial block and the origins
per block; the 16-of-22 and 17-of-23 thresholds next to the observed counts of non-negative gate blocks; raw and Holm-adjusted p_stab against the 0.025 line; the rank robustness columns and the rank <= 0.10 / >= 0.90 descriptive table; the gate's cash and
substituted-bar counts; the literal-reading variant and the number of settlements where it differs from the primary rule; the persistent-null rates; every interpretation choice. It makes no recommendation. Freeze and forward test were not run; the holdout is untouched.

I stop here until you accept the report. I have not started Work Order 1.7 and have no questions about it yet.
