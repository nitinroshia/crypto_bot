# Project status

Last updated: 2026-09-23, by the developer (Claude).

## Current pairs
**ETH/USDT and BTC/USDT are the project's two live pairs, for both research and execution**
(work order 1.4, owner-approved). ETH/FDUSD is retired as an execution-pair candidate on
liquidity grounds; its existing results stay as historical reference, and no further formula
work targets it. See `docs/work-orders/1.4.md` and `project_context.md`'s "Current pairs" section.

## Where things stand
- Item 1 (selection-rule change: min-p, no significance pre-filter) is built and self-tested.
- Data-batch tools built and verified: funding fetcher, gap locator, liquidity table, and (WO1.4)
  a raw-store timeframe deriver (`build_derived_raw.py`) and a discovery-sample volatility report
  (`volatility_report.py`). 20 self-tests total, all passing (`selftest_all.sh`).
- `resample_ohlcv_traded` (the WO1.1 fix) is confirmed to generalize to any source granularity,
  not just 1m -- proven on synthetic data (see `resample.py`'s own self-test) and used by
  `build_derived_raw.py` to build BTC/USDT's 15m from its native 5m, since nothing in the queue
  needs BTC/USDT 1m.
- Self-test scratch no longer touches the project directory at all -- every tool's self-test now
  uses the system temp dir, now that project-local `temp/` is discontinued.
- ETH/USDT 5m and BTC/USDT 1h/1d klines extended; funding data fetched for both symbols; 128
  missing ETH/USDT hours confirmed to coincide with 128 missing BTC/USDT hours (exchange-wide
  outage, not ETH-specific).
- This repo (docs/, context/, .gitignore) replaces the five legacy repos (dump-sept,
  dump-sept-01/02, handover-2026-09-20, sample-bot), removed from GitHub by the owner. See
  `docs/architecture/`.

## In progress (work order 1.4: pair expansion)
- Waiting on one owner data run: BTC/USDT native 5m (back to 2017-08-17 04:00, matching
  ETH/USDT's 5m span), BTC/USDT 15m derived from it, a gap check on both, and the discovery-sample
  annualized-volatility report for both pairs. Commands given directly to the owner.
- Every pre-registered task (S1, S2, Task 3, Task 4-once-relevant) will run as two independent
  families per pair (`<task>-ETHUSDT`, `<task>-BTCUSDT`) once item 2's registry exists --
  pair-qualified naming is being folded into item 2's schema now, not retrofitted later.
- The old "replicate the sign on BTC, report only" language is retired. Replacement: when either
  pair's candidate freezes, the other pair's same-cell point estimate/sign/discovery-p is reported
  as a labeled context column -- informative, not gating.

## Next
- Once the owner's WO1.4 data run lands: review the gap and volatility reports, then continue
  item 2 (`--end-date` guard, holdout lock, registry with pair-qualified naming,
  by-year/leave-one-year-out checks, freeze manifest, forward-test command).

## Open questions awaiting the mathematician
See `docs/correspondence/` for the full A1-A5/B1-B5/N1-N4 history. Nothing is currently blocking
item 2. No open question from work order 1.4 either -- see the developer's reply for the two
interpretive readings stated (365-day vol annualization as the default label; BTC/USDT 15m
derived from 5m rather than fetched natively), neither of which needs an answer to proceed.
