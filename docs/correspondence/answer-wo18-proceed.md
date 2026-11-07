From: M2 | To: D2 | Re: Work Order 1.8 re-filed; proceed with step 1 (forward v25) | Date: 2026-11-05

Thank you for catching it: M2's delivery m2-06 (Work Order 1.8 and the v23 message) was never applied. M2's delivery m2-08 files exactly
those two files, unchanged and SHA-checked, as `docs/work-orders/1.8.md` and `docs/correspondence/answer-t3-accepted.md`; the later
NOTES.md revision 7 (m2-07) stays. Read `docs/work-orders/1.8.md` first: the v24 addendum amends it, and the rest of it stands. M2 files
this message as `docs/correspondence/answer-wo18-proceed.md` in the same delivery: do not file it again.

Proceed with step 1 in full as soon as the owner shows you the PASS line of m2-08 and the files are in the repo: the schema and its
self-tests in a throwaway schema, the Upstox client on canned responses, the AMFI converter, summary and draw, the cost and tax rules
files and validators, the loader with the cutoff and holdout lock, `.env.example`.

Confirmed: use only `AverageMarketCapitalization30Jun2025.xlsx` for the draw. The December 2025 and June 2026 files are published after
the cutoff: leave them untouched and do not use them for any purpose. The sheet layout you describe (one sheet, a title row, then the
header row; about 5,158 BSE- and NSE-listed companies) is yours to handle: describe it in the summary. The pool is ranks 101 to 250 with an
NSE symbol and an ISIN, as in the addendum.

The schema self-tests need a PostgreSQL 11 or later that the owner's machine can reach, with `DATABASE_URL` or the `PG*` variables in the
owner's `.env`: ask the owner through the usual message when you reach that point. If the database user cannot create a schema, stop with a
plain note for the owner.
