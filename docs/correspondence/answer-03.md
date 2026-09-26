# Answer 03: evaluation-segment vs. block boundary -- ruling

2026-09-26. In response to `docs/correspondence/message-10.md`.

Confirmed -- and there are two independent pieces of text that settle it, not just the self-test
requirement the developer cited.

Step 3's own sentence already draws the distinction it needs: "starts flat at the beginning of
each evaluation segment... so a position may carry across a block boundary at no cost." Evaluation
segment and block aren't the same thing there -- block boundaries sit inside an evaluation segment,
and only the segment's own start and end force a flat position. The self-test requirement ("charged
once, not twice") is a second, independent confirmation of the same reading. Two different parts of
the spec agreeing is about as settled as this gets.

## The general principle (so it doesn't need re-deriving next time)

An evaluation segment is whatever spans one continuous, unchanging rule. The economic gate's 90-day
tiles are reporting slices of a single pre-registered rule run continuously across the whole
discovery sample -- not that. Task 3's walk-forward validate windows are that: each one tests a
freshly-fit model on data the fit never saw, with no reason for a position to carry from one
split's window into a different split's, especially since consecutive splits' windows aren't even
guaranteed to be adjacent. The developer's reassignment of "a discovery block" (in step 5's general
end-of-segment list) to that case is right.

## The holdout, settled now rather than at the same question again later

The holdout's own net-positive-at-stress-cost check should follow identical logic: one continuous
flat-start/forced-exit run over the whole holdout window, no internal tiling. Simpler than
discovery, since there's no 70%-of-blocks statistic on the holdout, just a single pooled pass/fail
-- but "the holdout" in step 5's list is its own single evaluation segment, same as "the whole
discovery sample," not something with internal boundary costs either.

## One closeout

Step 2 (stability) isn't implicated by any of this. It reuses the same 90-day date ranges for
convenience, but it's a regression-sign check with no simulated position, so "boundary cost"
doesn't apply there at all.
