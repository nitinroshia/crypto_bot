# Work order 1.2 -- install and verify

## Install (copy over your tree; patches in patches/ are for review only)
- `user_data/analysis/`: `costs.py`, `task0_report.py`, `passive_fill_baseline.py`, `selftest_all.sh`
- new folder `user_data/analysis/retired/` with `costs_scenarios_AB.py` and `README_retired.md`
- repo root: `README.md`, `project_context.md` (these replace the versions in the earlier `docs_update/` package, which is now superseded)
- `HANDOFF_developer.md` (v2): keep it wherever you keep project documents; the repo root is fine
- delete `user_data/analysis/project_context_additions.md` (superseded by project_context.md)

The patches apply cleanly to the current live files (README.md 12,073 bytes and project_context.md 20,712 bytes on your machine).

## Verify (from the repo root; copy exactly)

    cd user_data/analysis && bash selftest_all.sh 2>&1 | tail -5 && cd ../..
    python3 user_data/analysis/research_cli.py --list-formulas
    grep statsmodels user_data/analysis/requirements.txt
    python3 user_data/analysis/costs.py

Send back the printed output of all four commands. Expected: `ALL SELF-TESTS PASSED`; four formula lines; the line
`statsmodels>=0.15`; and the costs self-test message.

Also needed to finish item 1 of the work order: the current `scripts/backtest.sh` (only its comment is to be fixed; FEE=0.001 stays).
