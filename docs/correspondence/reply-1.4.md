# Developer reply to work order 1.4

2026-09-23. Nothing here is a question requiring an answer before proceeding -- both readings
below are stated so they're checkable, not because either is genuinely ambiguous.

## Built and self-tested
- `build_derived_raw.py` -- derives and persists a coarser raw-store timeframe from a finer one
  already on disk, via `resample.resample_ohlcv_traded`.
- `volatility_report.py` -- annualized realized volatility from daily closes, restricted to the
  discovery sample, for any set of pairs.
- `resample.resample_ohlcv_traded` confirmed (new permanent self-test, not just a one-off check)
  to generalize correctly to a non-1m source. Its logic never actually assumed 1-minute bars --
  only its parameter name and docstring did.

## Reading 1: BTC/USDT's 15m is derived from its native 5m, not fetched natively or from 1m
Section 4.1 says "build 15m with the traded-minutes resample rule" without specifying the source
granularity. Fetching BTC/USDT's native 1m (to match how ETH/FDUSD's coarser timeframes were
originally built) would mean downloading a full 1m history nothing else in the queue needs, since
Task 3 -- the only consumer of BTC/USDT 15m -- needs 5m as its finest granularity. `resample_ohlcv_traded`
already generalizes cleanly to a 5m source (see above), so 15m is derived from the freshly-fetched
native 5m via `build_derived_raw.py`. If BTC/USDT 1m turns out to be needed for something else
later, this doesn't block fetching it then.

## Reading 2: annualized volatility uses sqrt(365) as the default, sqrt(252) as a labeled alternate
Crypto trades every calendar day, so 365 return observations make a year, not 252 (the trad-fi
trading-day convention). `volatility_report.py` reports both, labeled, since some crypto research
still uses 252 for cross-asset comparability -- but 365 is what gets called "annualized" in this
project's own reports unless told otherwise.

## Everything else in the work order
Implemented as specified: pair-qualified registry naming folded into item 2's schema (not built
yet, but the naming convention `<task>-ETHUSDT` / `<task>-BTCUSDT` is settled now so nothing needs
retrofitting), same cutoff and walk-forward windows for both pairs, cross-pair "replicate the sign"
gating retired in favor of the labeled context-column report, both pairs' tasks run together rather
than staggered. `project_context.md` and `context/STATUS.md` updated per section 6.

## One thing that changed for everyone's tools, not just this work order
Project-local `temp/` is discontinued (2026-09-22 restructuring). Every self-test that used to
write scratch files under `<project root>/temp/selftest` now uses the system temp directory
instead -- `funding.py`, `fetch_funding.py`, `locate_gaps.py`, and `liquidity_table.py` were
patched accordingly, and `selftest_all.sh` no longer sets `TMPDIR` to a project path. No behavior
change outside of where scratch files land.
