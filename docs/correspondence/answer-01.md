## For the developer

**Status:** noted. Add a seam check at 2026-03-19: the extension must match the old file exactly where they overlap, with no duplicate or missing bars.

**1. Stouffer rule.**
- Your default is approved for lag-scan formulas:
  - Each split uses its own fit-selected lag.
  - z = sign(fit) × validate HAC t.
  - Weights are equal, with a one-sided combined p.
  - "Significantly opposite" means two-sided p < 0.05 with the opposite sign.
- For tasks with a pre-registered primary cell (Task 1 gap, Task 3 k = 6, Task 4, Task 5), the cell is fixed and no lag is selected.
- Report the selected lag per split. Jumping lags are a warning even when the combined z passes.

**2. Discovery sample.**
- Intended. Discovery uses the full post-break sample, because we can't afford to discard 90 days.
- Walk-forward is therefore a stability check, meaning the effect shows up in every stretch of time. It is not independent evidence. The forward test is the only independent evidence.
- Pre-registered cells involve no selection, so their full-sample p-value stands on its own. Exploratory cells only nominate candidates.
- Tag every reported cell `pre-registered` or `exploratory` in the manifest.

**3. Forward test** (pre-registered now, applied per candidate at freeze).
- **Statistic:** exactly the frozen primary cell, one-sided in the discovered direction. One look, then marked consumed.
- **Minimum sample:** all of the following:
  - at least 45 days
  - at least 100 events or trades
  - a standard error no larger than half the claimed effect, computed at freeze from the discovery dispersion
  If that needs more than 120 days, come back to me and I'll decide between extending and dropping the candidate.
- **Success:** one-sided p < 0.05, and a point estimate at least as large as both:
  - the economic hurdle for its execution scenario (0.05% maker, 0.20% taker)
  - half the discovery estimate, which guards against winner's curse
- **Failure:** the candidate is dead, with no retuning.
- The forward window doubles as the dry-run window, and candidates run in parallel.

**4. Scenario-A mapping.** Classify by execution mechanism, not by label.
- **Profit, maker 0%:** `roi`, but only if the bar's high exceeded the ROI price by at least one tick. Touch-only ROI exits are counted separately and charged as time.
- **Stop, taker 0.10%:** `stop_loss`, `trailing_stop_loss`.
- **Time, taker 0.10%:** `exit_signal`, `custom_exit`, and any exit that had to cross the spread.
- **`force_exit`:** report separately, since these are end-of-data artifacts. Exclude them from expectancy.
- **Entries:** maker 0%, counted only if traded through by at least one tick and never in the placement bar.
- **Stress:** taker at 0.12%.
- Write the assumed category per trade to the output so I can audit it.
- In dry-run, verify the bot really prices `roi` exits on the passive side of the book, not crossing. If freqtrade can't rest a maker exit, tell me, because scenario A would then apply to entries only.

**5. Task 1 tradability.**
- Keep it separate from the 24, as a fixed-sequence gate. It is tested only if Task 1 passes Holm within the 24, so it needs no adjustment against them.
- The gate is one test: buys, d = 0.10%, at +15 minutes, lowest versus middle gap tercile, one-sided day-clustered p < 0.05.
  - I moved it from +30 to +15 because a mispricing signal is short-lived, so the shorter horizon has less noise.
- Sells (highest versus middle tercile) are a mirror check. The same sign is required, and they aren't tested separately.
- Terciles come from the prior 30 days only.

**Defaults approved.**
- The gap median uses the prior 1,440 minutes with the current minute excluded.
- Task 5 uses A_14bars with origins at :00/:15/:30/:45.

**Task 5 power.**
- Proceed, and change the threshold rather than the design. "Material" means at least 0.04%, which is about what the design can resolve. The minimum detectable effect at 80% power is roughly 2.5 × SE, or about 0.03–0.05%.
- Report the minimum detectable effect computed from the standard error, not post-hoc power computed from the observed effect.
- Classify each result three ways:
  - **Pass:** one-sided p < 0.05 and point estimate ≥ 0.04%.
  - **Dead:** one-sided 95% upper bound below 0.04%.
  - **Inconclusive:** everything else. It keeps accruing forward data rather than being killed.
- The same three-way rule applies to the Task 1 gate.
