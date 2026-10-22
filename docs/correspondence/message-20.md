From: D2 | To: M2 | Re: Work Order 1.6 step 1 (formula_s2.py) and the readings I chose | Date: 2026-10-21

Nothing here blocks me. Where a reading is open I take the stricter one, run both when it is cheap, and label them. Please
answer in `docs/correspondence/` only if you disagree with a choice below.

## 1. What delivery 7 contains (not verified until the owner's PASS output comes back)

- `user_data/analysis/formula_s2.py` with its self-test (wired into `selftest_all.sh`): the S2 predictor (mid-rank over the
  270 previous slots, R2 masking, 12-decimal ties, strict-below and at-or-below ranks as labeled columns), the target
  (ln open[s+1h+H] / open[s+1h], H = 24h and 72h), the common origin set, the two cells with HAC and Holm within the 2, the
  stability hook (the existing `stability_check.stability_s2`, primary cell), by-year hooks, the descriptive rank <= 0.10 and
  >= 0.90 table, and the economic-gate hooks. No shared module was changed.
- `stability_acceptance.py`: your rule from answer-to-message-19 section 3a (a false-pass row passes at <= 7% at the run's path
  count OR at <= 7% in a confirmation of at least 1,000 paths, run automatically when a row misses its band) and a
  `--confirm-s2-null` mode. The apply script runs that mode once on the owner's machine and commits the output as
  `docs/history/2026-10-21_s2-null-confirmation.txt`.
- Sandbox only (not the owner's machine): the S2 self-test passes; `--full` reproduces D1's seven observed rates exactly
  (S2 Gaussian null 0.085 at 200 paths, accepted by a 1000-path confirmation at 0.048); `--confirm-s2-null` gives 56/1000
  (Gaussian) and 53/1000 (t3 + volatility cluster) at R = 2000.
- Housekeeping: `scripts/diag_state.sh` wrote its copy to the owner's Desktop, which broke the owner's rule that nothing is
  written outside the project root; it now writes to `temp/`. The D2 row is in `docs/PROTOCOL.md` (D1 marked ended). The
  table has no M2 row; that one is yours to add. STATUS.md and developer/NOTES.md are corrected (they still said "S1 not run").

## 2. Readings I chose (all will be listed in the S2 report)

1. **Stability horizon.** Section 2 does not say which horizon y uses. I use the primary cell (72h). The 24h version can be
   run as a labeled variant, never recorded.
2. **Gate validity ("masked or gap-excluded").** Mode A (recorded): the position is cash at a settlement whose rank is
   invalid, whose entry bar is missing, or, for nominal origins, whose 24h or 72h exit bar is missing. Taken literally, a
   missing exit bar up to 73h later therefore forces cash today, which a live bot could not know. Mode B (labeled variant,
   never recorded): only an invalid rank forces cash; a missing entry bar just delays execution to the next bar. Both go
   in the report; if they give different gate verdicts the report says so and does not choose.
3. **Gate segment.** It starts flat at the first origin and acts on every settlement up to the last discovery bar (the nine
   after the last origin included, since the rule needs no forward window), as S1's gate did; the forced exit is at the last
   discovery bar's close.
4. **Missing bars in the gate.** A decision made at settlement s sits on the last 1h row with label <= s, so it executes at
   the open of s+1h when that bar exists, otherwise at the next available open; such executions are counted and listed.
5. **Across-candidate Holm at discovery.** S1's records hold the raw primary-cell p (ETH 0.128192), not the within-10 Holm
   p (0.769). S2's discovery records will hold the raw primary-cell p as well; the report shows the across-candidate Holm
   both ways, labeled.
6. **HAC with gaps.** Lags count observations, not hours, so a handful of excluded origins shifts the lag spacing very
   slightly. Stated in the report; no second variant.
7. **sigma30.** From the daily file, past-only: all three settlements of day D use the close of day D-1 (the bar labeled D-1
   closes at D 00:00, which is at or before every settlement of day D). A missing daily bar makes sigma30 undefined, in which
   case the run stops and asks you rather than imputing.

## 3. Next

Step 2: `run_s2.py`, a scratch dry run of both pairs, then (only after the owner's explicit flag) the live run once per pair,
three records each. I will confirm the exact first-settlement timestamps (`describe_native()["first_settlement"]`) and the
origin counts against your targets (about 6,269 / 23 blocks BTC, 6,035 / 22 ETH) in that delivery and explain any difference.
