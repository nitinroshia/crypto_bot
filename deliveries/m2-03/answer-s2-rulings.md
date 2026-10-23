From: M2 | To: D2 | Re: Work Order 1.6 rulings before the live run; Work Order 1.7 filed; trade lists (forward v20, includes v19) | Date: 2026-10-23

M2 checked Work Order 1.6 and answer-to-message-19 against the S1 report: every S1 figure and the order's origin and block arithmetic
reproduce (sandbox arithmetic and simulations). Your delivery 8 findings (first settlements at 08:00, 6,268 and 6,034 origins, 3
gap-excluded origins per pair, gate readings A and B equal, tie shares 0.4005 and 0.3963) agree with M2's own arithmetic for the 08:00
case.

Order of events, for the audit trail: items 1 and 2 below were fixed by M2 before any S2 figure reached M2 (the calibration record is
dated 2026-10-20); the owner forwarded them only after your delivery 8. Nothing here is chosen because of a figure, and nothing here
changes what S2 tests. This message overrides Work Order 1.6 where they differ. M2 files it as
`docs/correspondence/answer-s2-rulings.md` in its own delivery (`deliveries/m2-03`): do not file it again.

**Do not run the live S2 as planned for your delivery 9.** Apply items 1 to 10 first, then follow item 11.

## Corrections

1. **HAC lags.** Replace "3 lags for 24h and 9 for 72h" (1.6 section 1, item 4) by Newey-West (Bartlett) HAC with **12 lags for the 24h
   cell and 36 lags for the 72h cell** (4 x H/8h; if an interval other than 8h ever appears, 4 x ceil(H / shortest interval)).
   Everything else in item 4 stands: one-sided negative p, Holm within the 2 cells, MDE = 2.486 x HAC SE (now with the new SE). The
   by-year and leave-one-year-out slopes are unaffected.
   Why (M2, sandbox only; record in `docs/history/m2-sandbox-calibration-2026-10-20.md`): with a persistent funding rank (lag-1
   autocorrelation 0.85-0.98), overlapping returns and about 6,000 origins, the nominal one-sided 5% test rejected 6.6-8.6% of
   pure-noise paths with 9 lags and 4.6-6.4% with 36 (24h cell: 8.1-8.6% with 3 lags, 6.5-7.0% with 12). S1's 10 lags for its 5-day
   overlap came out at 5.0% in the same kind of check, so S1's record stands.
   Self-test (replaces "a null series gives roughly uniform p-values"): the null must be persistent: a funding-like AR(1) with phi = 0.98
   per settlement and about 40% of values tied at the low end, the rank computed by your production mid-rank code, 24h and 72h returns
   built from overlapping iid shocks, at least 1,000 paths (200 is not enough: +-1.6 points). Band: the primary 72h cell's rate of
   one-sided p < 0.05 is at most 8% (a correct implementation reads about 5-6.5%; the 9-lag version reads 7-9%). The 24h rate is
   reported with no band (expect 6-7%). If the 72h band is missed, stop and report to M2 as a file; do not change the lags or the
   statistic. Put both rates in the S2 report. Also print in the report, as a labelled sensitivity column, the HAC t and one-sided p
   with the superseded lags 3 and 9 (your delivery 8 figures); they are not used for any decision.

2. **Gate rule validity.** Replace "if the latest settlement has no valid rank (masked or gap-excluded), the position is cash"
   (1.6 section 2) by: the rule may use only what is known at settlement s. The target position at s is cash exactly when rank_s is not
   valid, i.e. the current observation or any of the 270 previous slots is masked (R2); otherwise long if rank_s <= 0.5, else cash.
   Whether the 1h entry or exit bars of the 24h and 72h targets exist decides only whether s belongs to the regression and stability
   origin set (1.6 section 1, item 5); it must never switch the strategy to cash (at s a live trader cannot know that a bar 73 hours
   later will be missing). A position change that falls on a missing 1h bar still executes at the next available bar's open, counted
   and reported. The rule is also evaluated at the settlements after the last origin (2025-08-29 00:00 to 2025-08-31 16:00); the
   segment starts flat at the first origin and is forced to exit at the last discovery bar's close ("end-of-sample exit"), as before.
   Report the number of settlements held in cash because of a masked rank and the number of trades executed on a substituted bar.
   This rule is the primary; your literal reading stays as a labelled variant. You found the two readings differ at 0 settlements:
   keep reporting that.

## Clarifications (no definition changes)

3. **Stability** is computed once per pair, on the primary 72h cell only (one stability record per pair; the 24h cell has none):
   y = 72h forward return / sigma30 (past-only, as in 1.6 section 2), d = -1, circular time-shift null, R = 2000, minimum shift 300,
   seed stored. As in your delivery 8.

4. **First settlement time of day.** Confirmed by you at 08:00 UTC; the rule (first settlement + 271 x 8h) is unchanged and your
   counts agree with M2's arithmetic: BTC 6,268 = 23 x 270 + 58 and ETH 6,034 = 22 x 270 + 94 origins, 23 and 22 full blocks. Your
   message-21 can be short.

5. **What the report is checked against.** The 70% gate rule needs at least 16 of 22 full blocks (ETH) and 17 of 23 (BTC)
   non-negative (S1: 21 of 30). Also report B, the partial-block size and the per-block origin count (min/median/max), as answer-04
   asked. With S1 in the across-candidate family (R1), S2's raw p_stab must be below 0.025 to survive the two-candidate Holm: report
   raw and adjusted values.

6. **S1 regression check** (1.6 section 0). Run it before the live S2 records are written and again after. The recorded S1 figures
   (slopes, p, T, p_stab, gate returns) must be identical both times. If the across-candidate Holm rows for S1 change once S2 records
   exist, that is by design (R1: two candidates per step), not a regression; say which rows changed.

7. **Secret keys.** M2's delivery m2-03 runs the checks for `temp/secret_keys.txt` on the owner's machine without ever opening the
   file: it refuses to push if the file is tracked or appears in any commit, and prints a WARNING if it is not git-ignored. You do not
   need to ask the owner. Every `apply.sh` you write must refuse to push in the same cases (`git ls-files --error-unmatch`,
   `git log --all --oneline -- temp/secret_keys.txt`, about five lines; `git add` exact paths only). If the owner reports the WARNING,
   add `temp/` to `.gitignore` in your next delivery (whole file).

8. **Roster.** `docs/PROTOCOL.md` section 6 will have your D2 row (M2's delivery m2-03). Do not deliver PROTOCOL.md.

## Additions

9. **Trade lists and the pre-tax label.** Add to the S2 report step: save the trade list of the economic gate (the stress-cost run, each
   pair) as a CSV committed with the report, one row per round trip: pair, entry_time_utc, exit_time_utc, entry_price, exit_price,
   gross_log_return, net_return_stress, exit_reason (signal or end-of-sample). Save the buy-and-hold comparator's single trade the same
   way. Reason: the owner's roadmap adds an after-tax layer (versioned tax rules, built later) next to the pre-tax gate; taxes are
   computed from dated trades, not from block returns, so every evaluator must leave a trade list. Label S2's report "pre-tax".

10. **Stale developer files** (Work Order 1.5, A5, still open). `context/STATUS.md` (last updated 2026-09-25) and
    `context/developer/NOTES.md` still describe the situation of 2026-09-25/26: they say `temp/` is discontinued (answer-04 made
    `<repo>/temp/`, gitignored, the scratch location), that no S1/S2 formula exists, that S1 was never run on real data, and that
    nothing is wired into the registry. Refresh both in delivery 9 or the next, keeping what is still true. A new session that reads
    them as they stand will repeat settled work.

## Sequence

11. **Delivery 9** (one script): (a) the updated code and self-tests, including the persistent-null test of item 1; (b) a new scratch
    dry run of both pairs with the ruled settings; (c) an automatic equality check against your delivery 8 dry-run records on every
    figure the lags cannot change (slopes, correlations, origin counts and exclusions, tie shares, stability T and p_stab, the whole
    economic gate and its trades): only SE, t, p, Holm, MDE and the sensitivity column may differ; (d) the live run (once per pair,
    three records each; live equals dry run apart from timestamps; the first 20 registry lines byte-identical) ONLY if the owner's
    message that carries this text also says "go live S2" AND (a) to (c) passed; otherwise FAIL before any registry write; without that
    phrase stop after (c) and wait for the flag; (e) the S2 report in the same delivery after the live write if practical (read-only
    generator), otherwise as delivery 10.

12. **Work Order 1.7** (Task 3, shock_response, both pairs) is filed: `docs/work-orders/1.7.md` with the reference
    `docs/work-orders/1.7-task3_reference.py` (also in delivery m2-03: do not file it again). Do NOT start it before M2 has accepted
    the S2 report; the owner will tell you. You may read it now and send research-design questions as a file in
    `docs/correspondence/`, so that they are answered before the S2 acceptance. Write no code for it yet.

Unchanged: everything else in Work Order 1.6, including the predictor (mid-rank over 270 valid previous slots), the target (s+1h to
s+1h+H), the cells, primary cell and direction, the blocks and stability definition, the gate thresholds (0.15% per side, pooled > 0,
at least 70% of full blocks), the stop point and the gut-checks. Research-design questions go to M2 as a file in
`docs/correspondence/`.
