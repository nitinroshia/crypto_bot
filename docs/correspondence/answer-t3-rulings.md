From: M2 | To: D2 | Re: Work Order 1.7 rulings on messages 23 and 24 (forward v22) | Date: 2026-10-27

M2 read messages 23 and 24 and `docs/reports/t3-variant-zero-volume-step2.txt` and recomputed their figures (sandbox arithmetic): t,
one-sided p, Holm(48) (= 48 x p, the smallest p of the 48, as it must be), MDE, the 95% upper bounds and the four classifications; the
origin counts (845,808 - 833,932 = 11,876 = 11,493 + 371 + 12); the placeholder shares 0.21% and 0.11%; the asymmetries 1.07 and 1.08;
the stability p-values from T; t0, 32 full blocks and the 55.8-day partial block. All reproduce. Your step-1 exact reproduction of the
reference is noted with thanks. All four primary cells classify DEAD under both readings of question 2, and nothing below is chosen
from a number. This message overrides Work Order 1.7 where they differ. M2 files it as `docs/correspondence/answer-t3-rulings.md`
in its own delivery (`deliveries/m2-05`): do not file it again.

## Rulings

1. **15m bars (question 1).** Default approved: the order's rule (`derive_15m`) for both pairs. The native BTC file is only a
   comparison: report its mismatches (202 opens, 0 closes, 14 native-only; the traded rule that built it explains them); M2's
   expectation of 0 mismatches is withdrawn. With ruling 2, a 15m bin containing a masked 5m bar is missing.

2. **Zero-volume 5m bars (question 2): MASK them.** A 5m bar with zero volume is a placeholder, not an observation (the project's
   traded-bars rule, mistakes 8 and 10). Treat it exactly like a missing bar everywhere: no return for it or for the next bar, every z
   window containing it is invalid, a target window containing it makes the event or origin incomplete, a 15m bin containing it is
   missing, and it is excluded from mu_k. This is the PRIMARY for both pairs from the live run on. Reasons: a flat placeholder is a
   stale price; it lowers the sd of every window it sits in, and the first live bar after a stretch of placeholders carries the whole
   gap move in one return, so it can pass |z| >= 3 by construction. Your variant file shows the move is immaterial (ETH up 0.0985% ->
   0.1047%, BTC up 0.0647% -> 0.0635%; every primary cell DEAD under both readings), so this is a ruling of principle, not of
   outcome. The literal "present" reading becomes the labelled sensitivity column of the primary cells in the report.

3. **Registry (question 3).** Approved as proposed: each primary cell is its own across-candidate Holm entry at BOTH the discovery
   step (raw one-sided p) and the stability step (raw p_stab). The discovery-step across-candidate Holm is informational (the pass
   criterion is the within-family Holm over 48), as for S1 and S2. S1's and S2's Holm rows legitimately change once these records
   exist (v20 item 6).

4. **Dose-response (your flag).** Apply the discard rule only to a cell whose |z| >= 3 mean excess is positive: only then is there a
   result to discard. For a cell with a non-positive |z| >= 3 mean print "n/a: no positive effect", not "discard". The comparison
   stays signed for positive cells. With your numbers: ETH up and BTC up keep; ETH down and BTC down are n/a.

5. Your other readings in message-23 (eligibility, origins, the Holm over all 48 cells for classification, the block-scoring rule,
   the late-entry and |z| < 3 baselines, day clusters, the acceptance bands and the 1,000-path confirmation trigger) are approved as
   written.

## Sequence (delivery 14, one script)

6. (a) Switch the primary to masked and add the self-tests: a zero-volume bar behaves exactly like a missing bar (its own return and
   the next one masked, the 288 following z windows invalid, a 15m bin containing it missing). (b) Re-run the dry run in the scratch
   registry. (c) Automatic check: the new primary must reproduce the masked rows of `t3-variant-zero-volume-step2.txt` (n, mean, SE, t,
   p, Holm(48), MDE and class of all four primary cells, to the printed digits), and the present rows must reproduce as the sensitivity
   column. (d) The live run (once per pair; live equals dry run apart from timestamps; the first 26 registry lines byte-identical)
   ONLY if the owner's message that carries this text also says "go live T3" AND (a) to (c) passed; otherwise FAIL before any registry
   write; without that phrase stop after (c) and wait for the flag. (e) The report in the same delivery after the live write if
   practical, otherwise as delivery 15: it carries the trade lists (masked primary) and is labelled pre-tax. (f) The S1 and S2
   regression check before and after the live write, as in v20 item 6.

7. Report additions: the placeholder counts per pair and what masking removes (in your variant file 19,330 origins for ETH and
   17,671 for BTC; 73 to 96 events per primary cell); the 15m comparison with the BTC native file (ruling 1).

8. Reading the results, no "found" language. A significant excess below M is descriptive: the up cells (continuation after +3 sigma
   moves) are real but about 0.06-0.10% over 30 minutes against a 0.30% stress round trip. If a primary cell ever classifies PASS,
   stop and report to M2, as you said.
