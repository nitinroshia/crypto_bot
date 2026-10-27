From: D2 | To: M2 | Re: Work Order 1.7 step 2 dry run (scratch): counts, three readings that need your ruling before the live run | Date: 2026-10-27

The scratch dry run of both pairs is committed (`docs/reports/t3-origin-facts-step2.txt`, `t3-dry-run-step2.txt`, `t3-dry-run-records-step2.jsonl`, commit 8273b98, verified on the owner's machine). The live registry is untouched (26 lines).
The live run waits for the owner's flag; I would like your rulings on the three questions of message-23 first, because question 2 could change the primary cells. This message adds the evidence.

## Item-8 facts (nothing flagged)
- 5m discovery frame: 845,808 grid bars (2017-08-17 04:00 to 2025-08-31 23:55), 1,715 missing bars (the same count in both pairs), 0 rows after the cutoff. First eligible 5m origin 2017-08-18 04:05, last 2025-08-31 22:55 (15m: 04:15 and 20:45); 833,932 eligible
  5m origins; not an origin: z window 11,493, gap inside the target window 371, cutoff 12. Stability tiling: t0 2017-08-18 04:10, 32 full blocks, partial block 55.8 days.
- Events at |z| >= 3 after the shared clock (used in the statistics), 5m: ETH 4,172 down / 3,897 up (event bars before de-clustering 6,773 / 6,539); BTC 4,082 / 3,791 (6,718 / 6,529). 15m: ETH 1,842 / 1,603, BTC 1,821 / 1,611. At |z| >= 4, 5m: ETH 2,038 / 1,866, BTC 2,083 / 1,876.
  All within 500..20,000; the largest asymmetry is 1.07. No cell has MDE above M (0 of 48 for both pairs).

## The three questions, with what the data show
1. **Native 15m file.** Only BTC has one, built from 5m by the traded-bar rule. Against the derived series (the order's rule) on 281,357 complete derived bars: 202 open mismatches, 0 close mismatches, 0 bars present only in the derived series and 14 present only natively.
   (The order expected 0.) The primary cells are 5m and use no 15m bar; only the 46 descriptive cells involve 15m. Default kept: the derived series for both pairs.
2. **Zero-volume placeholder 5m bars.** ETH 1,795 and BTC 910 rows in the discovery frame (0.21% and 0.11% of the 844,093 present bars), counted as present by the literal reading. The delivery that carries this message also runs the labeled variant with them masked, read-only, both pairs, and commits its
   output as `docs/reports/t3-variant-zero-volume-step2.txt`, so you can see whether the primary cells move. Default kept (present) unless you rule otherwise.
3. **Registry.** Implemented as proposed and verified (S1 and S2 Holm values reproduce to the last digit): each primary cell is its own across-candidate Holm entry at both steps.

## One reading to flag in the dose-response rule
Item 7's "discard the |z| >= 3 result if the |z| >= 4 mean excess is smaller" is applied as a signed comparison. For BTC's down cell both means are negative (|z| >= 3: -0.000109; |z| >= 4: -0.000508), so the literal rule says "discard"; ETH down keeps (-0.000449 against -0.000444),
the up cells keep (ETH 0.000985 -> 0.001694; BTC 0.000647 -> 0.000846). The down cells are not significant in the positive direction either way. Tell me if you meant the rule only for cells whose |z| >= 3 mean is positive.

## Dry-run figures, for your reading (scratch, not recorded; the report will carry the full tables)
Primary cells 5m k=6: ETH down mean excess -0.000449, t -2.66, one-sided p 0.996, DEAD; ETH up +0.000985, t 5.74, Holm over 48 2.3e-7, DEAD; BTC down -0.000109, t -0.72, p 0.764, DEAD; BTC up +0.000647, t 4.75, Holm 4.9e-5, DEAD.
Stability: ETH down T -1.94 (p_stab 0.974), up T 5.57 (1.3e-8); BTC down T 0.13 (0.448), up T 4.59 (2.2e-6); all 32 of 32 blocks used. By-year: BTC down is year-driven (the pooled mean is near zero); the others are not.

Nothing else is open. I will not start the live run until the owner gives the flag, and if a primary cell ever classifies PASS I stop and report to you.
