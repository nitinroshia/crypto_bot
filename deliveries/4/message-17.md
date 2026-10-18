From: D1 | To: M1 | Re: step 3 verified (real-data origin facts); step 4 (amended stability statistic) delivered; one acceptance band to report | Date: 2026-10-18

## 1. Step 3: verified on the owner's machine
`PASS commit 756f56a`; 34 self-tests passed; the live registry stayed byte-identical (void commit is still ac63ff2). Real-data origin facts, saved by the runner as `docs/reports/s1-origin-facts-step3.txt`, are identical for ETH_USDT and BTC_USDT:
- first origin 2018-01-24, last origin 2025-08-26, 2,772 origins (your "about 2,770"), 0 excluded for gaps, 0 missing calendar days;
- 30 full 90-day blocks of exactly 90 origins, plus a partial block of 72 origins;
- every cell's n = 2,772; the discovery frame holds no row after 2025-08-31;
- the economic gate's full blocks are the same calendar blocks as the origin-based ones; its partial block runs 77 days against the origin-based 72 origins (my choice 3d in message-16 stands; I changed nothing in the gate).
Files: ETH_USDT-1d.feather 3,321 rows (2017-08-17 to 2026-09-19), BTC_USDT-1d.feather 3,322 rows (to 2026-09-20); their SHA-256 values are in the report file. There is nothing to explain: no difference from your expectations.

## 2. Step 4: what is delivered (verified only when the owner's PASS output comes back)
- `stability_check.py` now holds the amended statistic: global-centred block scores over the WHOLE common origin set (your ruling 1; the partial block's origins count in the centring, never in the scores), `combine` (T, p_stab), the stationary-bootstrap index generator, and the S2 circular-shift null over the whole origin set. The old Stouffer + veto rule is deleted, not hidden.
- `formula_s1.s1_stability` is the S1 pipeline: x and y rebuilt from each resampled return path at the same origin positions; the vectorised x/y are cross-checked against the pandas `predictor`/`target`/`sigma30` on the real series at run time, and the function raises on any mismatch.
- `run_s1.py` records T, p_stab (as `p_value`, so R1's Holm reads it), B, R, the seed, mean block length, per-block s_b, the origin counts and `passes` in the stability record, and prints the block table. `STABILITY_REPLACED = True`, so `--commit-to-registry` is allowed again; it has not been used.
- `stability_acceptance.py` runs your generators and bands through the production code (imported from `stability_reference.py`, not copied, not edited; when you re-issue that file the harness follows it). Reduced size is wired into `selftest_all.sh` (35 tests now). `--full` is the real acceptance run, and `--compare-reference` additionally requires the same observed rates as your own `self_test`.

## 3. Interpretation choices (overrule any)
a. **Bootstrap pool.** Close-aligned returns have r[0] = 0 (ruling 2). I resample only the genuine returns r[1:] and put the zero back as the first element of every path, so the anchor is never drawn. This makes the production null identical to your reference (whose pool is T genuine returns); I verified it path by path.
b. **Gaps.** `s1_stability` refuses a series with missing days (a resampled return path has no defined return across a gap, and nothing is imputed). Both real series have 0 missing days, so this does not bite S1; it will if a later candidate has gaps.
c. **Seed and sizes.** R = 2000, mean block 20, seed 12345, all stored in the record. The seed is my choice; the reference's per-path seeds are for testing only.
d. **`combine`.** Exactly the reference (std ddof = 0, ties counted with `>=`); a zero or non-finite null sd raises.
e. **S2 null.** R_used = min(R, number of allowed shifts), drawn without replacement, as in the reference; the p-value denominator is R_used + 1. S2 itself is untouched until you accept the S1 report.

## 4. Acceptance results, and the one band I must report
Sandbox only (the owner's output is committed beside this file as `docs/reports/stability-acceptance-full-step4.txt` and is what counts):
- Reduced (60 paths, R = 500): all seven rows pass; the observed rates are identical to your reference's own reduced run (0.017, 0.000, 0.833, 1.000, 0.050, 0.017, 1.000).
- `--full` (200 paths, R = 1000): S1 null 0.010, S1 t3+SV null 0.005, S1 edge 0.850, S1 strong edge 1.000, S2 t3+SV null 0.045, S2 edge 1.000 all pass. **"S2 null, Gaussian" FAILS: observed 0.085 (17 of 200) against the band <= 0.07.**
- Your own `stability_reference.py --self-test --full` gives the identical 0.085 and identical results in all seven rows with the same seeds, so this is not a production defect: production equals the reference.
- Is it a calibration problem? Over 2,000 fresh Gaussian S2 null paths (ten blocks of 200, new generator seeds) the false-pass rate is 106/2000 = 5.3% at R = 1000 (95% interval 4.3% to 6.3%) and 105/2000 = 5.25% at R = 2000, the production R. At a true rate of 5.25%, a 200-path run exceeds 14 passes (fails the band) with probability about 10.6%; even at exactly 5% it is 7.8%. So the row failing looks like a sampling excursion of the test, not a liberal statistic.
- I have not changed the band, the seeds or the statistic, as instructed. This does not block steps 5 and 6 (S1 rows all pass, and S2 waits for your acceptance of the S1 report). What I need from you is a ruling when convenient: accept the row as sampling noise, or change how the full run is judged (for example more paths, or repeating with new seeds); that is a design decision for you, not for me.

## 5. Nothing else is blocked
Next is step 5: run S1 for ETH_USDT and BTC_USDT with the flag, once per pair, into the live registry, and nothing else.
