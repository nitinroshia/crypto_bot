Adds to Answers 1.5; the queue is unchanged. No open questions remain from me.

Ruled

A2-extended (stability windows for the S1/S2 primaries).
Nothing is fit there, so tile the discovery sample from each family's first origin with the same non-overlapping 90-day blocks as the economic gate.
Orientation is the pre-registered direction (S1 positive, S2 negative).
Stouffer runs over the full blocks with equal weights; the final partial block is excluded.
Task 3 and lag scans use the standard walk-forward: rolling fit of 365 days, stepping by the 90-day validate length. Confirm in walkforward.py that the fit window rolls; if it expands, tell me.
C1. Guard scope. Approved, with two additions:
In discovery mode, no argument may extend the loader past the cutoff. The loader must not return a single post-cutoff row, and predictors are computed once on the truncated series. Only the forward-test command loads the full series, with the pre-cutoff history needed for lookbacks.
Post-cutoff reads are allowed if they compute no returns: counts, spans, gaps, zero-trade shares, volume and trade tables, and funding distribution descriptives such as tie share and interval changes. Anything that computes a return of any series, or relates a predictor to a return, is not allowed outside the forward-test command. The A1 tie share stays on data up to the cutoff; a full-range tie count may be added as a separate descriptive.
C2. Approved: exclude the origin and count it.
C3. Approved; verify freqtrade's end-date behaviour when a backtest is needed.
N1. Position open at the cutoff. The forced exit governs. Exit at the close of the last discovery bar (no holdout price), charge the exit cost, and label it "end-of-sample exit". Mark-to-market is a labeled variant.
Positions carry across the internal 90-day block boundaries with no forced exit.
Every evaluation segment (the discovery sample, the holdout) starts flat and ends with a forced exit.
N2. Task 3 direction.
The two primary cells (k = 6, each side, at 5m) are pre-registered one-sided positive excess, since spot is long-only: buy after a down-shock (reversal) or buy after an up-shock (continuation).
Walk-forward orientation for them is positive. answer-02's fit-window-sign orientation applies only to exploratory lag scans, which cannot pass a gate.
This corrects the line in handoff §6 that listed Task 3 under fit-sign orientation.
N3. Dose-response.
Reading (ii) governs: a fresh 13-bar de-clustering at threshold 4. Reading (i) is a labeled variant.
The check compares the k = 6 point estimates per side. Discard if the ≥4 estimate is smaller than the ≥3 estimate and the ≥4 sample has at least 30 events. With fewer than 30 events, mark it "not evaluable" and flag it for my review; do not discard.
N4. Unconditional mean. Approved as read. Add a labeled robustness variant with μ from non-event origins only.

Also

Record 6,709 and 1,979 bytes and Python 3.12.7 at the next handoff revision. No separate re-issue is needed.
Proceed with the order you stated: the snapshot, then the tools and commands for the owner, then item 1, then item 2.

Next steps for you

Send this block together with the files and outputs the developer requested.
Wait for the developer's report on the full snapshot.
If it raises no new questions, tell me "switch". I'll then issue the final context document for the new mathematician, folding in everything settled since v2.2. Please keep holding mathematician_context_v2_2.md until then.
