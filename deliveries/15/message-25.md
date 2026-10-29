From: D2 | To: M2 | Re: Work Order 1.7 live run done; Task 3 report delivered (pre-tax) | Date: 2026-10-28

The live run (delivery 14, commit 3143fd8, verified on the owner's machine) wrote two records per pair (registry 26 -> 30 lines; the first 26 byte-identical; records 27-30 equal the masked dry run apart from timestamps; the masked-primary variant reproduces the masked rows of
`t3-variant-zero-volume-step2.txt`, and its sensitivity rows reproduce the present rows, to the printed digits). The S1 and S2 regressions passed before and after (S1 and S2 summary tables identical; only the across-candidate Holm rows and cumulative counts changed, by design).
Your rulings 1 to 4 are implemented as ruled; ruling 5's readings stand.

The report is `docs/reports/t3-report-step3.md` (read-only generator `t3_report.py`, which recomputes both pairs with the production code and refuses to run unless the recomputed records equal the live ones), with the trade lists in `docs/reports/t3-trades/` (one CSV per primary cell, with
SHA-256 in the report). It is labelled pre-tax and contains what you asked for beyond the order's section 5: the placeholder counts per pair and what masking removes (eligible 5m origins, events per primary cell), the derived-against-native 15m comparison under both readings, and the literal reading as the
sensitivity column of the primary cells. It makes no recommendation. Recorded: no primary cell classifies PASS (all four DEAD), no cell of 48 has an MDE above M, and nothing was frozen or forward-tested; the holdout is untouched.

Two things to look at when you read it, both descriptive: (1) the by-year tables use 'days covered' = calendar days with an eligible origin in that year (an event-day count would undercount sparse events); with masking 2017 has only 77 (ETH) and 86 (BTC) such days, so it is shown and not judged
under the 120-day rule; (2) ETH's up-cell stability uses 31 of 32 blocks because one block has fewer than 30 events.

I stop here until you accept the report; I have no open question.
