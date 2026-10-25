# Project status

Last updated: 2026-10-23, by D2 (developer), Work Order 1.6 step 2 (delivery 9: M2's rulings, dry run, live run). Refreshed in full
(M2's item 10): the stale 2026-09-25 text is gone; what was still true is kept in "Settled facts". Where this file and `docs/`
disagree, `docs/` wins. Read `docs/PROTOCOL.md` first, then `docs/work-orders/1.6.md`, then `docs/correspondence/answer-s2-rulings.md`
(M2's rulings of 2026-10-23, which override Work Order 1.6 where they differ), then `context/developer/NOTES.md`.

## Current state (D2, 2026-10-23)
- Agents: M2 (mathematician, separate chat, owns research design), D2 (developer, this role; D1 ended with message-19), the owner (runs
  every command, pushes to GitHub). Agents talk only through files in the repo; the developer cannot touch the owner's machine.
  Task: `docs/work-orders/1.6.md` (S2 `funding_extreme` for both pairs, through the economic gate; stop after the S2 report is
  committed). Work Order 1.5 (R1-R4, A1-A6), `answer-04.md` and `answer-to-message-19.md` stay in force. Work Order 1.7 (Task 3,
  shock_response) is filed but NOT started: it starts only after M2 accepts the S2 report and the owner says so; research-design
  questions about it go to M2 as files in `docs/correspondence/`.
- S1 is closed without advancing on either pair (`docs/reports/s1-report-step6.md`). Recorded S1 outcomes (live registry lines 15-20,
  run in commit `4487f1e`): ETH primary slope 0.000715415, n 2772, one-sided p 0.128192, stability T 0.7082, p_stab 0.230385, gate
  pooled net 4.92255 with 40.0% non-negative full blocks (not passed); BTC slope 0.0010087, p 0.0145107, T 1.6966, p_stab 0.0554723,
  gate pooled net 34.5543 with 50.0% (not passed). Nothing is frozen, nothing is forward-tested, and the holdout unlock (one-shot) has
  never been used; S2 must not change that.
- Verified by output from the owner's machine: deliveries 0-8 (commits `cd0a0a1`, `ac63ff2`, `bd0c8cb`, `756f56a`, `f5a883a`,
  `4487f1e`, delivery 6 = S1 report, `11a5fbb` = delivery 7, `901ef7f` = delivery 8). Delivery 7: `formula_s2.py` with self-tests; the false-pass rule
  of answer-to-message-19 3a and its confirmation run (S2 Gaussian null 56/1000, t3 + volatility cluster 53/1000, R 2000, both within 7%;
  `docs/history/2026-10-21_s2-null-confirmation.txt`); S1 regression passed. Delivery 8: `run_s2.py`, read-only origin facts and a scratch dry run
  of both pairs (`docs/reports/s2-origin-facts-step2.txt`, `s2-dry-run-step2.txt`, `s2-dry-run-records-step2.jsonl`); the live registry stayed at 20 lines.
- S2 facts verified on the owner's machine (delivery 8, read-only): first funding settlements at 08:00 UTC (BTC 2019-09-10, ETH 2019-11-27), so the first
  origins are BTC 2019-12-09 16:00 and ETH 2020-02-25 16:00; last origin 2025-08-28 16:00 for both; nominal origins 6,268 (BTC) and 6,034 (ETH); 3 gap-excluded
  per pair (one entry bar, one 24h exit bar, one 72h exit bar) leaving 6,265 and 6,031; full 90-day blocks 23 (BTC) and 22 (ETH), partial blocks of 58 and 94
  origins, one block with 267 origins; tie shares 0.4005 (BTC) and 0.3963 (ETH); 128 missing 1h bars in the discovery frame; no missing daily bars;
  0 post-cutoff rows in every frame; all funding intervals 8h.
- M2's rulings of 2026-10-23 (`docs/correspondence/answer-s2-rulings.md`), applied in delivery 9: (1) HAC lags 12 (24h cell) and 36 (72h cell), 4 x H/8h;
  a persistent-null self-test (AR(1) phi 0.98, 40% ties, 1000 paths, 72h rate band <= 8%); the superseded lags 3/9 stay as a labeled sensitivity column;
  (2) the gate is cash exactly when rank_s is invalid (primary rule); the literal reading (missing entry/exit bars also force cash) is a labeled variant;
  (3) stability once per pair on the 72h cell only; (5) report checks: B, partial block, origins per block, at least 16 of 22 (ETH) / 17 of 23 (BTC) non-negative
  blocks for the 70% rule, raw p_stab < 0.025 to survive the two-candidate Holm; (6) S1 regression before and after the live S2 records; (7) every apply.sh
  refuses to push if `temp/secret_keys.txt` is tracked or in any commit and warns if it is not git-ignored; (9) the S2 report saves each gate's trade list and the
  buy-and-hold trade as CSV and is labeled "pre-tax".
- Delivery 9 (`deliveries/9/`): the updated code and self-tests, a new scratch dry run of both pairs with the ruled settings, an automatic equality check against
  delivery 8's dry-run records on every figure the lags cannot change, then the live run (once per pair, three records each) ONLY when the script is started with
  `--go-live-s2`, with the live records equal to the new dry-run records apart from timestamps and the first 20 registry lines byte-identical; the S1
  regression is run before and after the live write. NOT VERIFIED until the owner's PASS output comes back. The live registry has 20 lines before and 26 after the live run.
- NEXT: delivery 10 = the S2 report (read-only generator `s2_report.py`, refuses unless every recomputed figure reproduces the registry; labeled "pre-tax";
  trade-list CSVs), then stop and wait for M2's acceptance. The owner forwards the report to M2.

## Settled facts
- Pairs: ETH/USDT and BTC/USDT are the two live pairs for research and execution (Work Order 1.4, 2026-09-23); ETH/FDUSD is retired as an execution candidate and its
  results are historical reference only.
- Repo: `https://github.com/nitinroshia/crypto_bot` (public); the five earlier repos are gone. Layout: `docs/work-orders/`, `docs/handoffs/` (M-authored; the developer never
  adds to it), `docs/correspondence/` (developer messages `message-NN`; M answers `answer-*`), `docs/reports/`, `docs/history/`, `deliveries/<n>/` (each delivery's
  files plus its `apply.sh`), `context/mathematician/NOTES.md` (M2's own file, never edited by the developer), `context/STATUS.md`, `context/developer/NOTES.md`.
- Owner's hard limits (`docs/PROTOCOL.md`): nothing that costs money (write `BLOCKED: <what>` and stop); the loop is whole files plus one runner script, owner runs and
  pushes, the developer reads what was pushed; agents talk only through files. Nothing is verified until output from the owner's machine says so. Nothing is ever
  written outside the project root; scratch and backups go in `<repo>/temp/` (gitignored); `temp/secret_keys.txt` is never opened, copied or backed up.
- Discovery cutoff: 2025-08-31 23:59:59 UTC everywhere; data are truncated at the cutoff before any computation; the holdout is untouched. Costs: base 0.24% and stress
  0.30% round trip (0.15% per side stress for the gate).
- Registry (`user_data/analysis/results/registry.jsonl`, append-only): the live file is written only with an explicit `commit_to_registry` flag; the default of every tool is
  scratch (`temp/scratch-registry.jsonl`); a void marker voids earlier records of that (family, pair); `holm_at_step` keys by (family, step) per R1 and reads each live family's
  most recent record; `freeze_manifest`, `holdout_lock` and `forward_test` exist and are one-shot but have never been called for a candidate.
- The 15-minute break-even thread (2026-09-24) is closed: at 15m the typical |return| is below the round-trip cost for a symmetric trade-every-bar model; it does not touch S1,
  S2 or Task 3 (`docs/correspondence/message-07.md`).

## Where things are (`user_data/analysis/`, 38 self-tests in `selftest_all.sh`)
- Shared: `cutoff.py`, `databundle.py`, `funding.py`, `blocks.py`, `nonstationarity.py`, `multitest.py`, `costs.py`, `rule_evaluator.py`, `economic_gate.py`, `registry.py`,
  `stability_check.py` (generic stability statistic, S1 bootstrap and S2 time-shift variants), `stability_acceptance.py` (M1's generators and bands through production code).
- S1: `formula_s1.py`, `run_s1.py`, `s1_report.py` (read-only, cross-checked against the registry). S2: `formula_s2.py`, `run_s2.py`; the S2 report generator comes in delivery 10.
- Data (owner's machine, not in git): `user_data/data/binance*/` feather files for both pairs (1h, 1d, funding used by S2).
