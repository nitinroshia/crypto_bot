# Developer note: the >100% break-even figures are real, not an artifact

2026-09-24. Follow-up to message-06 and the mathematician's v4 note.

## The finding stands, and it's more solid than it first looked

The 15m break-even hit rate exceeds 100% for BTC/USDT (101.7% base / 114.7% stress) and for
ETH/USDT at stress cost (100.7%). I didn't take that at face value -- I added an outlier-sensitivity
check to `breakeven_table.py` before writing anything: drop the most extreme 0.1% of observations
and see if the headline number was being set by a handful of events.

It wasn't. Dropping the biggest moves makes the required hit rate **worse**, not better (BTC 15m:
101.7% -> 102.8% with the extremes removed; ETH 15m: 90.6% -> 91.3%). That's the opposite of what a
bad-tick artifact would look like. The correct reading: the *bulk* of 15-minute returns on both
pairs are tiny relative to the round-trip cost, and the rare huge moves are actually the only thing
keeping the average move size as large as it is. Remove them and the "typical" move shrinks further.

**Concretely:** BTC/USDT's empirical mean |15m return| is about 0.232% -- smaller than the base
round-trip cost itself (0.24%). ETH/USDT's is about 0.296% -- clears base cost, not stress cost
(0.30%). Under the symmetric-payoff assumption (win and loss both sized at the typical move), no
hit rate, not even 100%, produces a profit when the typical move doesn't cover the cost of entering
and exiting.

## What's actually driving it

Both pairs' three largest 15-minute moves cluster at the same handful of dates -- ETH's two biggest
(-21.50% and +21.34%) are adjacent 15-minute bars (a crash and a near-full recovery within 30
minutes), and BTC shows the same pattern at the same dates. Two independently-fetched series showing
identical extreme timestamps is strong evidence this is genuine, market-wide history (a real flash
crash / liquidation cascade), not a per-pair data error. I found a real bug in my own tool while
digging into this -- the worst-move dates were being reported as raw row positions, not calendar
dates, which is exactly the kind of thing that would have made this unfalsifiable. Fixed, self-tested
(a synthetic injected spike must resolve to its real date, not a row number), and the owner is
rerunning to get the actual dates in the next log rather than my rough estimate.

## What this means for the pipeline, not just this table

This doesn't touch S1 or S2 (daily-close and 8h-funding based) at all. It's specific to a
trade-every-15-minutes, symmetric-payoff model -- which is not what Task 3 is. Task 3's whole premise
is conditioning on |z| >= 3 shocks and measuring the reaction, not assuming every 15-minute bar is a
coin flip with a small consistent edge. If anything, this table is indirect support for that design:
the ordinary-bar economics at 15m are bad enough that a strategy has to be doing something other than
"trade every bar" to have a chance, which is exactly Task 3's structure. Worth stating explicitly so
this finding reads as a constraint on one specific model, not a verdict on 15m/intraday work generally.

## Confirmed: these are three real, documented market events

The mathematician cross-referenced the actual dates from the corrected tool and closed this out:
- **2020-03-12** ("Black Thursday," the COVID crash)
- **2021-05-19** (documented as the largest flash crash since March 2020: ETH -46%, BTC -32% in
  under 12 hours) -- this is almost certainly the adjacent-bar crash-and-recovery pair described above
- **2017-09-04 / 2017-09-15** (China's ICO ban, followed by the exchange-shutdown escalation)

All three are genuine market history, not data artifacts. Recorded here rather than left as
"presumed real."

## Also added: median |return| alongside the mean (mathematician's remaining ask, now closed)

`breakeven_table.py` now reports median |return| next to the empirical mean at every cell, with its
own breakeven hit rate (base and stress). Self-tested: on Gaussian synthetic data the median matches
its own known closed form (sigma * sqrt(2) * erfinv(0.5)) rather than the mean's; on fat-tailed data
with matched variance, the median/mean ratio is confirmed to drop further below the Gaussian case's
(fat tails concentrate more of the distribution's mass near zero, not less) -- proving median and mean
are telling genuinely different, both-worth-reporting parts of the same story, not two estimates of
the same thing.

Everything else in this table -- the formula, the empirical-mean methodology, the outlier-sensitivity
check -- stands as previously reported; the mathematician confirmed it final.