From: M1 | To: D1 (and D2, who continues from the repo) | Re: S1 report accepted; rulings on message-19 | Date: 2026-10-19

## 1. The S1 report is accepted as the record

I re-checked every figure I can check from the report alone. They reconcile: the Holm adjustments within the 10
cells (both pairs); the stability statistic (sum of the 30 block scores s_b divided by sqrt(30): ETH 3.879/5.477 =
0.708, BTC 9.291/5.477 = 1.696, the report's 1.6966 from unrounded scores); the shares of positive blocks (17 of 30 and 15 of 30); the origin count (2,772,
equal to nominal); the block counts (30 full blocks plus a 72-origin partial block); the non-negative block counts
in both per-block tables (12 and 15 for the strategy, 18 and 13 for buy-and-hold); and the cost drag (0.997^74 =
0.80 for ETH, 0.997^77 = 0.79 for BTC, matching net against gross). The generator that refuses to run unless the
figures reproduce the registry is exactly the discipline this project needs.

## 2. S1 outcome: the project record

Under the pre-registered rules S1 is NOT advanced, for either pair:

- discovery: the primary cell's Holm-adjusted p within the 10 cells is 0.769 (ETH) and 0.145 (BTC), both above 0.05;
- stability: p_stab is 0.230 (ETH) and 0.0555 (BTC), both above 0.05;
- economic gate: pooled net return is positive on both (ETH 4.92 against buy-and-hold 3.13; BTC 34.55 against
  8.51), but only 40.0% (ETH) and 50.0% (BTC) of full blocks are non-negative, against the required 70%.

No freeze and no forward test. The holdout is untouched. S1 is closed: its definitions, cells, rule and thresholds
are not changed. Its three records per pair stay live in the registry: a failed candidate stays in every later
across-candidate family (R1).

How to read it, without retuning anything:

- BTC's raw p of 0.0145 does not survive the 10-cell family.
- BTC's large pooled outperformance of buy-and-hold comes mainly from sitting out the 2018, mid-2021 and 2022
  drawdowns. The positive stability evidence is concentrated: blocks 5 and 11 alone supply 7.5 of the 9.3 total.
- The MDE (slope 0.00115 for BTC, 0.00157 for ETH) is above the observed slopes, so S1 is "not shown", not "shown
  absent".
- Any future trend variant is a NEW candidate: pre-registered before anyone looks at its results, with its own
  family name, and counted in every across-candidate family from then on.

## 3. Rulings on your open items

a. **S2 Gaussian acceptance row (0.085 against 0.07): ACCEPTED, no code change.** The band was mine and was too
   tight for 200 paths. With a true false-pass rate of 5.3% the standard error of a 200-path estimate is about 1.6
   points, so a correct implementation reads above 7% roughly one run in nine. New rule, replacing the false-pass
   bands in 1.5 section 4: a false-pass row passes if the observed rate is at most 7% at 200 paths, OR at most 7%
   in a confirmation run of at least 1,000 paths. If the confirmation run's output (your 5.3% estimate) is not
   already under `docs/history/`, the developer who continues re-runs it once, inside its first delivery, and
   commits the output. Power rows are unchanged.
b. **Buy-and-hold comparator: ACCEPTED as you defined it** (the gate's own segment, blocks and stress cost). "Same
   origins" in R4 means "the same evaluation segment as the strategy".
c. **Partial blocks: ACCEPTED as built.** The partial block is not scored for the 70% rule; the pooled figure
   includes it (section 6, step 3).

I have accepted all eleven interpretation choices in report section 8.

## 4. What happens next

- Work Order 1.6 (S2, both pairs, through the economic gate, no freeze) is in `docs/work-orders/1.6.md`. A new
  developer (D2) takes it from the repo. Your work package, Work Order 1.5, is complete.
- I have seen message-19 and the S1 report only. Messages 13 to 18 were not shared with me, so I rely on report
  section 8 for the choices you made in them.
- Thank you. The S1 pipeline went from kickoff to a verified report in two days, and every claim in your report was
  checkable. That is the standard for everyone who follows.
