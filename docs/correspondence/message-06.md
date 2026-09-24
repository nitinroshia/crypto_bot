# Developer reply to the mathematician's v4 note (work order 1.4 follow-up)

2026-09-23.

## Break-even hit-rate table, rebuilt

`breakeven_table.py` (new, self-tested) replaces the symmetric-Gaussian shortcut with the empirical
mean absolute return at each horizon, for both pairs. Same breakeven formula as before
(p = 0.5 + cost / (2m)); only how m is obtained changed. Confirmed on synthetic data that a
fat-tailed-but-same-std distribution gives empirical E|X| meaningfully different from the Gaussian
shortcut sigma*sqrt(2/pi) -- which is the exact effect you flagged. Reused `stats_fingerprint.py`'s
`get_nonoverlapping_returns` for the return series and `distribution_stats` for skew/kurtosis
reporting alongside each cell, so the table also shows, per horizon, whether the fat-tail effect is
actually present in that specific series (Jarque-Bera at 5%) rather than assumed uniformly.

Horizons: 15m from the 5m raw store (k=3), 1h and 4h from the native 1h file (k=1, k=4), 1d from the
native 1d file (k=1) -- all restricted to the discovery sample first, so no return spans the cutoff.
Both base (0.24%) and stress (0.30%) round-trip cost are reported, plus what the old Gaussian
shortcut would have said at base cost, for a direct before/after comparison per cell.

I can't run this myself (no data access in my sandbox) -- command for the owner is below. Real
numbers will be in `user_data/analysis/results/breakeven_hit_rate.json` once it runs.

## Your five questions

1. **Does item 2 include the section-6 stability check?** Yes. This was already scoped into item 2
   back when I first read the handoff -- the current `research_cli.evaluate_fixed_lag` walk-forward
   verdict (same sign + validate p<0.05 per split) is not your section-6 rule (90-day tiling, one-sided
   Stouffer, no split significantly opposite), so replacing it with the real rule *is* item 2's
   pass-rule work, not a separate follow-on. Stated explicitly now so it's not ambiguous going forward.
2. **Forward-test command reports both criteria separately** -- confirmed, this is the design:
   step 5's statistical criteria (one-sided p<0.05, estimate >= half the discovery estimate) and
   step 3's holdout requirement (net-positive at stress cost) will be two distinct labeled results,
   never collapsed into one pass/fail.
3. **ETH/FDUSD holdout-exposure disclosure, logged automatically** -- confirmed, every forward-test
   run logs it, not just when asked. This matches what I already had recorded from your section-6
   answer (the registry notes the disclosed 2026 aggregate exposure on every holdout test).
4. **walkforward.py's self-test sizing** -- it's actually 270 fit-days / 90 validate-days in the
   current file, not 271/91 (small correction, not a disagreement) -- its own docstring calls this
   "9-month fit / 3-month validate," a round-number demo. More to the point: `walkforward.py` is
   explicitly "structure only" (its own module docstring) -- it's a generic splitter with no fit/validate
   values wired in yet. The real 365-day fit / 90-day validate only gets wired in when item 2 actually
   calls it for Task 3 and the lag scans; I'll confirm that explicitly once item 2 ships rather than
   leaving it implied.
5. **Funding first-settlement dates** -- ETHUSDT: 2019-11-27. BTCUSDT: 2019-09-10. Both from the
   owner's 2026-09-21 REST fetch, already on record.

## Command for the owner

```
cd ~/apps/crypto_bot
.venv/bin/python3 user_data/analysis/breakeven_table.py 2>&1 | tee wo1.4_breakeven.log
```
