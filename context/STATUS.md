# Project status

Last updated: 2026-09-22, by the developer (Claude).

## Where things stand
- Item 1 (selection-rule change: min-p, no significance pre-filter) is built and self-tested.
- Data-batch tools are built and verified: funding fetcher (REST + data.binance.vision fallback),
  gap locator, liquidity table.
- ETH/USDT 5m and BTC/USDT 1h/1d klines extended; funding data fetched for both symbols;
  128 missing ETH/USDT hours confirmed to coincide with 128 missing BTC/USDT hours
  (exchange-wide outage, not ETH-specific).
- The resample "filled vs traded" bug (WO1.1) is fixed and shipped; historical pre-fix
  snapshots are preserved under docs/history/.
- This repo structure (docs/, context/, .gitignore) replaces the five legacy repos
  (dump-sept, dump-sept-01, dump-sept-02, handover-2026-09-20, sample-bot), which the
  owner is removing from GitHub. See docs/architecture/idea-01-proposal.md and
  idea-02-ratification.md for why.

## Next
- Item 2: --end-date guard, holdout lock, registry, by-year/leave-one-year-out checks,
  freeze manifest, forward-test command (work order 1.2/1.3, clarifications 1.4/1.5).
- Open: git/LFS policy for the two large *_orders.csv files in
  user_data/analysis/results/runs/ (currently untracked, see .gitignore).

## Open questions awaiting the mathematician
See docs/correspondence/ for the full A1-A5/B1-B5/N1-N4 history. Nothing is currently
blocking item 2.
