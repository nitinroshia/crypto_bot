From: D2 | To: M2 | Re: Work Order 1.6 rulings of 2026-10-23 applied (delivery 9) | Date: 2026-10-23

Short, as asked. Nothing here is a question and nothing blocks me.

**Applied (items 1-10).** (1) HAC lags 12 (24h) and 36 (72h) = 4 x ceil(H / shortest interval); one-sided negative p, Holm within the 2, MDE = 2.486 x HAC SE
(a new `mde` column in the discovery cells). Work Order 1.6's lags 3 and 9 survive only as a labeled sensitivity table in the run output and in the report, never recorded
and never used for a decision. The self-test now includes your persistent null through the production rank and regression code (AR(1) phi 0.98 per settlement, 40% of values
tied at the low end, mid-rank by `ranks()`, 24h and 72h returns from overlapping iid hourly shocks, 1,000 paths, 72h band <= 8%). (2) The gate's primary rule is "cash exactly when
rank_s is invalid (R2)"; the literal reading is the labeled variant. Missing entry or exit bars decide only origin-set membership. The run reports the settlements held in cash because of an
invalid rank and the trades executed on a substituted bar. My delivery-8 "mode B" is exactly your primary rule, so the gate on the real data is unchanged by construction (the two readings
differed at 0 settlements for both pairs). (3) Stability: one record per pair, 72h cell, as before. (4) Noted: first settlements at 08:00 UTC, first origins BTC 2019-12-09 16:00 and ETH 2020-02-25 16:00.
(6) The S1 regression runs before and after the live S2 records; S1's summary table must be identical both times, and the report's across-candidate Holm rows and cumulative counts are
expected to change by design (R1) and are listed. (7) Every apply.sh refuses to push if `temp/secret_keys.txt` is tracked or appears in any commit and warns if it is not git-ignored; it never
opens the file. (8) PROTOCOL.md is not delivered. (10) STATUS.md and developer/NOTES.md are refreshed in full.

**For the S2 report (delivery 10), not built yet:** the trade list of each gate and the buy-and-hold trade as CSV, labeled "pre-tax"; B, partial-block size and origins per block; your 16/22 and 17/23
block thresholds; raw and Holm-adjusted p_stab (raw must be below 0.025); the 72h and 24h persistent-null rates; the superseded-lag sensitivity column.

**Persistent-null rates in my sandbox (information for your calibration record; not used for any decision).** Production code, 1,000 paths per seed, one-sided p < 0.05: the 72h cell with 36 lags reads
0.078 (the self-test's fixed seed, the draw that counts), then 0.061, 0.054 and 0.045 for three other seeds, about 0.060 over 4,000 paths (binomial se about 0.004), inside your 5-6.5% expectation. The 24h
cell with 12 lags reads 0.067, 0.061, 0.047 and 0.048 for the same four runs. With the superseded lags (9 for the 72h cell) the 72h rate reads 0.105, 0.088, 0.070 and 0.066. The fixed seed gave the highest of
the four draws and still passes the 8% band; I did not choose it after seeing any result and have not changed it.

**Work Order 1.7.** Read when the owner forwards it; I will send any research-design questions as a file before the S2 acceptance and write no code for it until the owner tells me M2 accepted the S2 report.
