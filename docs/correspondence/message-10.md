# Developer question: economic gate (step 3) block-boundary cost mechanics

2026-09-26.

Building `rule_evaluator.py` and `economic_gate.py` (section 6, step 3), I ran into what reads
like a tension in section 6's own text, and want your confirmation on the resolution before this
gate is used on a real S1/S2 candidate -- this is financial-model territory, not something I
wanted to settle silently even though I'm fairly confident in the reading below.

## The tension

Step 3 says: "The rule starts flat at the beginning of each evaluation segment [...] a block's
return is the compounded net strategy return at stress cost, with costs charged only when the
position changes, so a position may carry across a block boundary at no cost."

Step 5's general end-of-segment note says: "every evaluation segment -- a discovery block, the
whole discovery sample, the holdout -- starts flat and is forced to exit at its last close [...]
labeled 'end-of-sample exit'."

Read together naively, these look like they could contradict: if each 90-day tile is independently
an "evaluation segment" that starts flat and force-exits at its own end, a position spanning a tile
boundary would be force-exited at one tile's close and re-entered at the next tile's start -- two
costs, not zero.

## How I resolved it

Section 6's own self-test requirement for this exact module settles it: "a position spanning a
block boundary must be charged costs once, not twice." That's only achievable if the economic
gate's "whole discovery sample" is evaluated as ONE continuous run (one flat start, one forced
exit, at the sample's own start and end), with each 90-day block's own reported return obtained by
SLICING that one continuous per-bar return series by date range -- not by independently
re-evaluating each block as its own flat-start/force-exit segment. Under that reading, "a discovery
block" in step 5's general list refers to a block-shaped unit used elsewhere in the pipeline (e.g.
Task 3's walk-forward fit/validate windows, which genuinely are independent segments), not to step
3's specific 90-day economic-gate tiles.

Built and self-tested accordingly (`user_data/analysis/rule_evaluator.py`,
`user_data/analysis/economic_gate.py`) -- the self-test directly verifies that the product of every
block's own sliced return (full and partial together) reproduces the pooled net return exactly, and
that a position spanning a synthetic block-boundary midpoint is charged its entry/exit costs once.

## The ask

Can you confirm this reading is what was intended, or correct me if "a discovery block" in the
end-of-segment note was meant to apply to step 3's tiles too (in which case the 70%-pass-rate
figure would need to be computed from independently-reset per-block simulations instead, which
would charge more round-trip costs than the continuous-run version and could change which
candidates pass)?
