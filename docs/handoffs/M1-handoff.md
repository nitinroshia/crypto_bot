# Handoff: mathematician M1 -> M2

Written by M1, 2026-10-19. M1's chat ran for weeks and is too long to keep using safely; S1's closure is a clean
seam. The owner starts M2 from this file when the developer's S2 report is on GitHub.

## Kickoff for M2 (the owner pastes this, then the link to the developer's latest report)

```
You are M2, the mathematician on the crypto_bot research project (public GitHub repo: nitinroshia/crypto_bot).
Follow docs/PROTOCOL.md exactly; the owner's three hard limits are not negotiable: (1) never propose, require or
nudge toward anything that costs money; (2) the loop: you give the owner whole files plus a runner script, the
owner runs it and pushes to GitHub, you read what was pushed; (3) agents talk only through files in the repo.
Read in this order, all under https://raw.githubusercontent.com/nitinroshia/crypto_bot/refs/heads/main/ :
docs/PROTOCOL.md, docs/handoffs/M1-handoff.md, context/mathematician/NOTES.md (stale in places: see the
handoff), docs/work-orders/1.5.md, docs/work-orders/1.6.md, docs/correspondence/answer-04.md,
docs/correspondence/answer-to-message-19.md, docs/reports/s1-report-step6.md. Then check the developer's latest
report (link in the owner's next message): recompute its figures before trusting any of it. Reply format: a short
plain-language note to the owner, then "For the developer (forward as is) - v<next number>" if anything needs to
go. Your first deliverable after the check: an updated context/mathematician/NOTES.md.
```

## 1. Where the project stands (2026-10-19)

- **Pipeline: built and verified on the owner's machine** (item 2 plus Work Order 1.5): cutoff guard, holdout
  lock, registry with voiding, by-year/LOYO, amended stability statistic, economic gate, S1 formula, run and
  report generator (`user_data/analysis/s1_report.py`, which refuses to run unless every figure reproduces the
  registry). Delivery loop works: S1 took two days from kickoff to a verified report.
- **S1 (daily trend, both pairs): closed, not advanced.** ETH primary Holm(10) 0.769, p_stab 0.230, 40% of blocks
  non-negative; BTC primary Holm(10) 0.145, p_stab 0.0555, 50% non-negative (gate needs 70%). Pooled returns are
  large (BTC 34.55 vs buy-and-hold 8.51) but come from sitting out drawdowns and are concentrated. Record:
  `docs/reports/s1-report-step6.md` and `docs/correspondence/answer-to-message-19.md`. Three live registry records
  per pair; no freeze, holdout untouched.
- **15m trade-every-bar route: closed by arithmetic.** Empirical break-even hit rate at 15m is above 100% for BTC
  (base 101.7%, stress 114.7%) and for ETH at stress (100.7%); median-based figures are worse (ETH base 117%). The
  extremes are real market history (Black Thursday 2020-03-12, 2021-05-19, China 2017-09), not data errors.
  1h is also very demanding (ETH 70%/75%, BTC 76%/83% base/stress by mean). Annualised vol, discovery sample:
  ETH 90.1%, BTC 70.1% (sqrt(365)).
- **Data (discovery to 2025-08-31, holdout after):** ETH_USDT and BTC_USDT 1d, 1h, 5m (BTC 15m derived from 5m),
  funding (ETH first settlement 2019-11-27, BTC 2019-09-10). Missing 5m bars coincide exactly across the two pairs
  (1,715, exchange-wide).
- **Next:** Work Order 1.6 (S2, both pairs) goes to new developer D2. After the S2 report: M2 writes Work Order 1.7
  (Task 3 shock_response, both pairs; data is ready; section 7 of NOTES has the definition). Task 4 (vol forecast)
  only if a candidate survives. Fallback if all die: volatility-managed exposure.
- **Honest odds (my judgment):** S1 is dead; S2 is slow and weak (likely "not advanced"); Task 3 is the best
  remaining shot but must beat a 0.35% materiality bar after a 0.30% round trip. A clean "no edge found with public
  price and funding data at these horizons" is a legitimate end state and saves capital. Say so plainly to the
  owner; never promise results.

## 2. What is stale in `context/mathematician/NOTES.md` (M2's first deliverable is an updated copy)

The file is the 2026-09-23 snapshot. Replace or fix: the header and status (item 2 and Work Order 1.4 are done);
section 1 (role contract: now the PROTOCOL loop, agent IDs, runner scripts, no money); section 3 (the break-even
table is superseded by the empirical figures above); section 4 (BTC 5m/15m and funding dates are in; the
volatility comparison is done); section 6 step 2 (the old per-block HAC/Stouffer test and the opposite-block veto
are RETIRED: use Work Order 1.5 section 3) and step 3 (unchanged; add R4 reporting); the Holm rule (R1); S2's
first-origin rule (R2); section 7 S2 (use Work Order 1.6) and S1 (closed); section 8 (add mistakes #14 and #15 and
the process lesson below); sections 9 to 11 (rewrite). File naming: work orders continue at 1.7; correspondence
files carry a header line and are free-form `answer-<topic>` names where the numbering is unclear.

## 3. Rulings in force

- Work Order 1.5: R1 (across-candidate Holm: every non-void candidate with a record at a step stays in that step's
  family, per pair; keyed by family and step), R2 (S2 counts valid observations; first usable origin = first
  settlement + 271 x 8h), R3 (opposite-block veto retired), R4 (report buy-and-hold on the same segment); section 8
  A1 to A6 (void design, hooks ruling, delivery, retired self-test, stale files, step 0).
- `answer-04` (answers to D1's first reply): centre over the whole common origin set including the partial block;
  blocks are 90 CALENDAR days with per-block index sets; scratch lives under `<repo>/temp/` and
  `temp/secret_keys.txt` is never touched.
- `answer-to-message-19`: S2 acceptance bands amended (false-pass rows pass at <= 7% at 200 paths OR <= 7% in a
  confirmation run of >= 1,000 paths); B&H and partial-block choices accepted.
- Forward-test hooks (A2): predictor look-back may read pre-cutoff history; holdout origins are decided by section 6.

## 4. Open items

- D1's messages 13 to 18 were never shown to M1. Every interpretation choice is listed in the S1 report section 8
  and was accepted, but skim 13 to 18 once for anything not covered.
- S2 acceptance confirmation run (>= 1,000 paths, expect about 5.3%): in `docs/history/` or to be re-run by D2.
- Task 3: confirm `walkforward.py` rolls (the self-test showed fixed 271-row fit windows sliding 90 days: rolling);
  Work Order 1.7 must be written before D2 finishes S2 if the owner wants no idle time.
- `temp/secret_keys.txt` exists in the owner's folder (gitignored as far as known). Never read, copy or back it up.

## 5. Lessons (add to the mistake log)

14. A per-block OLS-with-intercept significance test on an overlapping, persistent predictor, plus an
    opposite-block veto with no multiplicity control, fails pure noise (85% of null blocks negative; veto 100%).
    Any new gate gets a null-calibration and a power check on synthetic data BEFORE it is pre-registered.
15. An acceptance band tighter than the Monte Carlo error of the test (200 paths gives +/-1.6 points at 5%): a
    correct implementation fails it about one run in nine. Set bands from the standard error, with a confirmation run.
16. (Process) Accepting "item 2 done" without asking how a bad record is withdrawn; the live registry then held void
    records with no way to remove them. Ask for the failure path of every irreversible mechanism.
17. (Process) The cause of the 8 to 10 lost days was the delivery channel (code pasted through chat), not research.
    The PROTOCOL fixes it; never reintroduce patches or inline code.

## 6. The owner

- Not a coder; runs commands on a Mac; time is the scarce resource; highly dissatisfied with past efficiency.
  Wants short, plain-language notes, then one forward-as-is block labeled with a version number. The last
  forward-as-is message was v17 (to D2); the next is v18.
- Hard limits (repeat of PROTOCOL section 1): no money asks until the project has earned money; the file/script
  loop; agents talk only through repo files. Free tools and what the owner already has are fine.

## 7. Agents

| ID | Role | Status |
|---|---|---|
| M0, D0 | earlier sessions | ended |
| M1 | mathematician | ended with this handoff |
| D1 | developer | completed Work Order 1.5 (S1) |
| D2 | developer | starts Work Order 1.6 (S2) |
| M2 | mathematician | starts when the S2 report is on GitHub |
