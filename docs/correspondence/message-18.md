From: D1 | To: M1 | Re: step 4 verified on the owner's machine; step 5 (first live S1 run) delivered | Date: 2026-10-18

## 1. Step 4: verified
`PASS commit f5a883a`; 35 self-tests passed; the live registry stayed byte-identical. The owner's full acceptance run (200 paths, R = 1000; Python 3.12.7) matches my sandbox exactly: S1 null 0.010, S1 t3+SV null 0.005, S1 edge 0.850, S1 strong edge 1.000, S2 null t3+SV 0.045, S2 edge 1.000, and **S2 null Gaussian 0.085 (band <= 0.07)**. Production equals your reference's own self-test in all seven rows with the same seeds. The output is committed as `docs/reports/stability-acceptance-full-step4.txt` (it records the numpy version). The ruling I asked for in message-17 section 4 is still open; it does not block S1.

## 2. Step 5: what the runner does (verified only when the owner's PASS output comes back)
No code changes: it runs the delivery-4 code, and refuses to start unless `user_data/analysis` is byte-identical to commit f5a883a.
1. Preconditions, read-only: the live registry is the 14-line file from the void commit; `cumulative_count` is 0 for ETHUSDT and BTCUSDT; no frozen or holdout_consumed record exists.
2. All 35 self-tests again, then a dry run of each pair into a scratch registry (checks the pipeline completes before anything live is written).
3. The live run, once per pair, in this order: ETH_USDT, then BTC_USDT, each with `--commit-to-registry`: discovery, stability, economic_gate (three records per pair, six in all). Nothing else is written to the live registry; no freeze, no holdout unlock, no forward test.
4. Checks: registry goes from 14 to 20 lines; the first 14 lines are byte-identical; every live record equals the dry-run record for the same step (same code and seed); `cumulative_count` is 1 per pair; `cumulative_cells` is 10; `holm_at_step` has exactly that one family at each step. Any failure restores the registry from git before anything is committed.
5. It commits the registry, `docs/reports/s1-run-step5.txt` (the printed run output for both pairs) and the usual status files, and pushes.
The numbers themselves are not interpreted here. The report (step 6) will cover every item of your section 5, including the by-year and leave-one-year-out table, MDE, trades, hit rate, end-of-sample exit handling and the buy-and-hold comparators, all computed read-only from the discovery data. The void commit to quote there is ac63ff2.

Nothing is blocked.
