**Developer: item 1 complete, data batch verified, starting item 2**

### 1. Item 1 — selection-rule change (built and self-tested)

`leadlag.summarize_best_lag` now defaults to **min-p**: smallest p-value, no "significant" pre-filter, and not the largest |beta| or |correlation|. A best lag is reported whenever any lag was testable at all; its own `significant_at_5pct` still says whether it clears 5%. Ties (a p that underflows to exactly 0.0, which happens often in the HAC tables) are broken by the larger |HAC t| — or, for the non-overlapping table, the larger |Fisher z| — then by the smaller lag.

The pre-1.2 rule (largest |beta| or |correlation| among lags significant at 5%) is kept, named `select="legacy_max_abs_effect_among_significant"`, only so a frozen ETH/FDUSD result can be recomputed exactly as reported. No caller invokes it implicitly.

**One transitional gap, flagged rather than hidden:** `research_cli.evaluate_fixed_lag` (the live walk-forward verdict) still checks whether the fit window found a best lag at all; under the old rule that check filtered out non-significant fits, but under min-p a best lag now exists almost whenever anything was testable, so a non-significant fit lag now reaches validation instead of being screened out first. This function is exactly what item 2 replaces (my last report flagged it as a replacement, not a patch), so I did not patch it in the meantime. **No stored result is affected** — nothing has run through this path outside self-tests, which use hand-built fit/validate tables and don't exercise the live selector.

Also updated: `research_cli.py`'s formula-contract docstring notes the new default; `project_context.md`'s note that the old rule "is being changed" now says it was changed, and that the old `leadlag_summary.json` numbers are frozen under the legacy rule.

### 2. Data batch (owner's run; all descriptive, no returns computed)

- **Funding.** REST worked directly from the owner's machine (no fallback needed). Both symbols show a constant 8h interval since their first settlement, no interval changes, in both cases one masked observation (the very first, whose preceding span is unknown by construction). Tie share up to the cutoff: 39.6% (ETH), 40.1% (BTC) — funding sits at the 0.01%/8h baseline more often than not, as expected. Rank convention (A1) is still needed to interpret this at the tails.
- **Klines.** ETH/USDT 5m now runs 2017-08-17 04:00 to 2026-09-21 06:00 (955,046 rows); BTC/USDT 1h and 1d added, same start. Every pre-existing ETH/USDT 5m row is byte-identical to before.
- **Missing hours.** All 128 missing ETH/USDT hours coincide exactly with 128 missing BTC/USDT hours — this looks like exchange-wide outages, not an ETH-specific issue. 1,715 5m bars are missing in total: 1,536 fall inside those 128 hours (12 bars each, as expected) and 179 are scattered elsewhere.
- **Liquidity, 2026.** ETH/FDUSD trades per day ran 2.0–4.5% of ETH/USDT's in every month except January (11.1% by trade count, 40.5% by quote volume) — January's ETH/FDUSD file starts 2026-01-30, so that month has only 2 covered days and is not comparable to the rest.

### 3. Next
Starting item 2: the `--end-date` guard, holdout lock, registry, by-year/leave-one-year-out machinery, and the freeze/forward-test command. No question attached to this message.
- leadlag.py
- multitest.py
- research_cli.py
- project_context.md
