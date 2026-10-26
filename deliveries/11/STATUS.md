# Project status

Last updated: 2026-10-26, by D2 (developer), Work Order 1.7 step 1 (delivery 11: formula_t3.py). Refreshed in full
(M2's item 10): the stale 2026-09-25 text is gone; what was still true is kept in "Settled facts". Where this file and `docs/`
disagree, `docs/` wins. Read `docs/PROTOCOL.md` first, then `docs/work-orders/1.6.md`, then `docs/correspondence/answer-s2-rulings.md`
(M2's rulings of 2026-10-23, which override Work Order 1.6 where they differ), then `context/developer/NOTES.md`.

## Current state (D2, 2026-10-23)
- Agents: M2 (mathematician, separate chat, owns research design), D2 (developer, this role; D1 ended with message-19), the owner (runs
  every command, pushes to GitHub). Agents talk only through files in the repo; the developer cannot touch the owner's machine.
  Task: `docs/work-orders/1.7.md` (Task 3 shock_response, both pairs; stop after the Task 3 report is committed; S2, Work Order 1.6, is closed). Work Order 1.5 (R1-R4, A1-A6), `answer-04.md` and `answer-to-message-19.md` stay in force. Work Order 1.7 (Task 3,
  shock_response) is filed but NOT started: it starts only after M2 accepts the S2 report and the owner says so; research-design
  questions about it go to M2 as files in `docs/correspondence/`.
- S1 is closed without advancing on either pair (`docs/reports/s1-report-step6.md`). Recorded S1 outcomes (live registry lines 15-20,
  run in commit `4487f1e`): ETH primary slope 0.000715415, n 2772, one-sided p 0.128192, stability T 0.7082, p_stab 0.230385, gate
  pooled net 4.92255 with 40.0% non-negative full blocks (not passed); BTC slope 0.0010087, p 0.0145107, T 1.6966, p_stab 0.0554723,
  gate pooled net 34.5543 with 50.0% (not passed). Nothing is frozen, nothing is forward-tested, and the holdout unlock (one-shot) has
  never been used; S2 must not change that.
- Verified by output from the owner's machine: deliveries 0-9 (commits `cd0a0a1`, `ac63ff2`, `bd0c8cb`, `756f56a`, `f5a883a`, `4487f1e`, delivery 6 = S1 report, `11a5fbb` = delivery 7,
  `901ef7f` = delivery 8, `294afb8` = delivery 9). Delivery 7: `formula_s2.py` with self-tests; the false-pass rule of answer-to-message-19 3a and its confirmation run (S2 Gaussian null
  56/1000, t3 + volatility cluster 53/1000, R 2000; `docs/history/2026-10-21_s2-null-confirmation.txt`). Delivery 8: `run_s2.py`, read-only origin facts and a scratch dry run
  (`docs/reports/s2-origin-facts-step2.txt`, `s2-dry-run-step2.txt`). Delivery 9 (2026-10-25): M2's rulings applied (HAC lags 12 and 36, primary gate rule), 38 self-tests passed (the persistent
  null read 0.078 for the 72h cell, 0.067 for the 24h cell), S1 regression before and after identical on the summary table (only the across-candidate Holm rows and cumulative counts changed, by design),
  the ruled dry run equal to delivery 8's on every lag-invariant figure, and the LIVE S2 run once per pair: registry 20 -> 26 lines, first 20 byte-identical, records 21-26 equal the dry run.
- S2 facts verified on the owner's machine: first funding settlements at 08:00 UTC (BTC 2019-09-10, ETH 2019-11-27), first origins BTC 2019-12-09 16:00 and ETH 2020-02-25 16:00, last origin 2025-08-28 16:00
  for both; nominal origins 6,268 (BTC) and 6,034 (ETH); 3 gap-excluded per pair (one entry bar, one 24h exit bar, one 72h exit bar) leaving 6,265 and 6,031; full 90-day blocks 23 (BTC) and 22 (ETH),
  partial blocks of 58 and 94 origins, one block with 267 origins; tie shares 0.4005 (BTC) and 0.3963 (ETH); 128 missing 1h bars in the discovery frame; no missing daily bars; 0 post-cutoff rows; all intervals 8h.
- RECORDED S2 OUTCOMES (live registry lines 21-26, pre-tax; no interpretation here, the report has the full tables). ETHUSDT: 72h primary cell slope -0.000661852, HAC SE 0.00725403 (36 lags), n 6031,
  one-sided p 0.463651, Holm within 2 0.61005; 24h cell p 0.305025; stability T 0.2713, p_stab 0.384308, passes False, 54.5% of 22 blocks s_b>0; gate pooled net 0.431909, 63.64% non-negative full blocks (14 of 22,
  16 needed), passes False; buy-and-hold pooled 16.7209. BTCUSDT: slope -0.00540211, HAC SE 0.00538861, n 6265, p 0.158049, Holm 0.158049; 24h cell p 0.031624 (Holm within 2: 0.063249); stability T 1.1411,
  p_stab 0.0994503, passes False, 60.9% of 23 blocks; gate pooled net 0.262307, 47.83% (11 of 23, 17 needed), passes False; buy-and-hold pooled 13.5584. The two gate readings differ at 0 settlements for both pairs.
- M2's rulings of 2026-10-23 (`docs/correspondence/answer-s2-rulings.md`) are applied: HAC lags 12/36; gate cash only when rank_s is invalid (literal reading a labeled variant); stability once per pair on the 72h cell;
  S1 regression before and after the live write; apply scripts refuse to push if `temp/secret_keys.txt` is tracked or in any commit; the S2 report is PRE-TAX and ships trade-list CSVs.
- Delivery 10 (2026-10-25, commit `2334f30`) VERIFIED by the owner's output: 39 self-tests passed, the live registry stayed byte-identical at 26 lines, `s2_report.py` reproduced every recorded S2 figure and wrote
  `docs/reports/s2-report-step3.md` (PRE-TAX) and four trade-list CSVs (518 ETH and 510 BTC strategy trades, one buy-and-hold trade each). M2 recomputed every figure from the printed numbers and ACCEPTED the report
  (`docs/correspondence/answer-s2-accepted.md`, commit `63edecf`): S2 is closed, not advanced, on both pairs; no freeze, no forward test; the holdout is untouched.
- WORK ORDER 1.7 (Task 3 shock_response, both pairs, 48 cells per pair, through classification and stability) is the current task (`docs/work-orders/1.7.md`, reference `docs/work-orders/1.7-task3_reference.py`). Step 0 done: the owner's
  diag (2026-10-25T22:39:02Z) shows the folder clean at `63edecf` = `origin/main`, registry 26 lines equal to GitHub, Python 3.12.7, `ETH_USDT-5m` and `BTC_USDT-5m` present, `BTC_USDT-15m` present (derived), no ETH 15m file.
- Delivery 11 (`deliveries/11/`, Work Order 1.7 step 1) is prepared: `formula_t3.py` (event clock, masking, targets, 48-cell statistics, classification, event stability, dose-response, acceptance machinery; its self-test reproduces the reference
  exactly, largest relative difference 4.7e-14 in my sandbox, plus gap, cutoff, clock and reduced acceptance tests) wired into `selftest_all.sh` (40 self-tests), the FULL acceptance run (200 null / 100 edge paths, the 7% rule with automatic
  1000-path confirmation) committed as `docs/reports/t3-acceptance-full-step1.txt`, and `message-23.md` to M2 (three research-design questions with defaults, none blocking). NOT VERIFIED until the owner's PASS output comes back.
  No registry write; scratch only.
- NEXT: delivery 12 = `run_t3.py` (read-only origin/event counts of item 8, then the dry run on the real data for both pairs on a scratch registry; one backward-compatible `registry.py` extension so each primary cell is its own entry in the
  across-candidate Holm), then, after the owner's explicit flag, the live run once per pair, then the Task 3 report (`t3_report.py`, trade lists, PRE-TAX). Stop after the report; if a primary cell classifies PASS, stop and report to M2.

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

## Where things are (`user_data/analysis/`, 40 self-tests in `selftest_all.sh`)
- Shared: `cutoff.py`, `databundle.py`, `funding.py`, `blocks.py`, `nonstationarity.py`, `multitest.py`, `costs.py`, `rule_evaluator.py`, `economic_gate.py`, `registry.py`,
  `stability_check.py` (generic stability statistic, S1 bootstrap and S2 time-shift variants), `stability_acceptance.py` (M1's generators and bands through production code).
- S1: `formula_s1.py`, `run_s1.py`, `s1_report.py` (read-only, cross-checked against the registry). S2: `formula_s2.py`, `run_s2.py`; `s2_report.py` (read-only report generator, trade-list CSVs).
- Data (owner's machine, not in git): `user_data/data/binance*/` feather files for both pairs (1h, 1d, funding used by S2).
