# retired/ -- what work order 1.2 retired (2026-09-20)

**Why.** The planning cost model changed (fee 0.10% for makers and takers; the account's current maker 0% is
a promotion and is ignored; execution is taker at the next bar's open), and the research pair moved to
ETH/USDT. The maker / resting-order line of work no longer has a use.

**Retired** (as listed in work order 1.2): Task 1 in all its versions and its tradability gate; Task 5; Task 2
follow-ups; the liquidity monitor; fill-rule reporting (touch vs through); Scenario A and A-stress; the
re-costing tool.

**What existed as code, and where it is now**
| Item | Status |
|---|---|
| Scenario A / B cost model (`costs.py` up to work order 1.1) | Archived here unchanged as `costs_scenarios_AB.py` behind a RETIRED banner. Its self-test still runs (`python3 retired/costs_scenarios_AB.py`, and inside `selftest_all.sh`). Live code must not import it. |
| Task 1, Task 5, liquidity monitor, fill-rule reporting, re-costing tool | Never built: they existed only as specifications in the mathematician's messages and in the earlier `HANDOFF_developer.md`. There is no code to move. |
| Task 2 (`../passive_fill_baseline.py`) | **Left in place** as delivered history (its follow-ups are what was retired, not the task itself). It now carries a HISTORY note and no longer imports `costs.py`; its self-test passes. If it should be moved here too, that is a one-line move. |

**Results kept as history (not deleted, not to be extended):** `results/runs/20260919T125727Z_passive_fill_baseline.*`
(184 days) and `results/runs/20260920T014429Z_passive_fill_baseline.*` (233 days), plus the Task 0 outputs and the
post-break fingerprint / event-anchored results under `results/` and `results/from_2026-01-30/`.

**Rule.** Nothing under `retired/` is imported by live code, and nothing here is developed further.
