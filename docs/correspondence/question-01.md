Message to forward to the mathematician

Re: WO 1.1. Everything is implementable as written. Five items need your answer before I build them.

Status. The 1m extension to 2026-01-30 is in progress. It needed a tooling fix because freqtrade's downloader did not backfill. All files now end at 2026-09-19 23:59. The open-price test, the lag_bars/lag_minutes rename, correlation next to beta, the statsmodels bump and the backtest.sh comment follow in the next batch. The post-break fingerprint re-run comes after that, so it uses the new columns.

Decisions needed (my default in brackets; without your answer I use it):

Stouffer rule. [Each split uses its own fit-selected lag. z = sign(fit) × HAC t at that lag. Equal weights, one-sided p on the combined Z. "Significantly opposite" means validate two-sided p < 0.05 with the opposite sign.] Or do you want one lag fixed once?
Discovery sample. If discovery scans the full post-break sample and walk-forward then uses the same days, the lag screen has already seen the validate windows. Only the cumulative test count guards against that. Is that intended, or should discovery use only the first fit window?
Forward test. I will record the freeze in the manifest and mark the test consumed after one use. I need a minimum sample or duration and the success criterion. This is only needed once a candidate exists.
Scenario-A re-costing. I need the mapping from freqtrade exit reasons (roi, exit_signal, trailing_stop_loss, stop_loss, force_exit) to profit, stop or time. I will not assume it, because it sets the fee scenario.
Task 1 tradability. Please pre-register the cell. [Buys at d = 0.10% and +30 minutes, lowest versus middle gap tercile. Sells mirrored (highest versus middle). Pass means a positive difference with a one-sided day-clustered p < 0.05.] Should these two tests count inside the 24-test family or separately?

Defaults I will use unless told otherwise. The gap's trailing 1-day median uses the prior 1,440 minutes with the current minute excluded, matching Task 3. Task 5 uses the strict 14-bar window (A_14bars) and origins on :00/:15/:30/:45.

Power note for Task 5. From Task 2's dispersion (30-minute pnl standard deviation about 0.45% at d = 0.10%), the standard error on top-minus-bottom is roughly 0.011% before clustering and about 0.013–0.019% after. That is my rough estimate, not a measurement. The 0.02% "useful" threshold is therefore only about 1–2 standard errors, so power to detect an effect that size is roughly 30–55% even if it is real. I will compute it exactly from the data once it is in. Should the threshold or the sample design change, or shall I proceed and report the achieved power?
