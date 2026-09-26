"""
Shared tiling mechanics for step 2 (stability check) and step 3 (economic
gate) -- mathematician NOTES.md section 6: both steps use "the SAME
non-overlapping 90-day blocks [...], tiled from the family's own first
origin." Built as its own module (not embedded in stability_check.py) so
step 3, when it's built, reuses this exactly rather than a second,
possibly-drifted implementation of the same tiling rule.

TILED FROM THE FAMILY'S OWN FIRST ORIGIN, NOT CALENDAR-ALIGNED: block 0 is
[first_origin, first_origin + block_days), block 1 is the next block_days
window, and so on -- blocks are NOT aligned to calendar quarters or any
fixed calendar grid. Two different candidates with different first origins
get differently-phased blocks, by design (section 6 does not say to align
across candidates).

FINAL PARTIAL BLOCK: tiling stops once a block's nominal start would exceed
the data's own last available timestamp. The last block generated is
marked `is_final_partial=True` if its NOMINAL window (start to start +
block_days) extends past the data's actual CALENDAR COVERAGE -- which is
one inferred bar-width PAST the last row's own label, not the label itself
(bars are left-labeled, per this project's convention -- see cutoff.py; a
row labeled "day 269" of daily data still covers all of day 269, so
coverage extends through the start of day 270). Bar width is inferred from
the data's own median spacing rather than assumed, since this module is
timeframe-agnostic. Without this adjustment, an exact multiple of
block_days (e.g. exactly 270 daily rows into three 90-day blocks) would be
wrongly flagged partial on its last block -- see the self-test.
Section 6 says this final partial block is "excluded from this check" for
stability (and separately, for the economic gate, "excluded from the 70%
pass count but included in the pooled net-return figure" -- a DIFFERENT
exclusion rule per step, which is why `tile_blocks` itself only marks the
flag and leaves what to do with it to each step's own code, rather than
dropping it here).
"""

from __future__ import annotations

import pandas as pd


def tile_blocks(df: pd.DataFrame, first_origin: pd.Timestamp, block_days: int = 90) -> list[dict]:
    """Non-overlapping `block_days`-day blocks tiled forward from
    `first_origin`, covering `df`'s index range. Rows before `first_origin`
    are not part of any block (excluded entirely, not folded into block 0).

    Returns a list of dicts, one per block, in order:
      {"block_index": int, "start": Timestamp, "end": Timestamp (exclusive),
       "data": the df slice (rows with start <= index < end),
       "is_final_partial": bool}
    Only the LAST dict in the list can have is_final_partial=True (see
    module docstring); every earlier block is guaranteed full-length by
    construction (tiling only advances past a block once the next block's
    nominal start is still within the data's range)."""
    if df.empty:
        return []
    data = df[df.index >= first_origin]
    if data.empty:
        return []
    data_end = data.index.max()
    step = pd.Timedelta(days=block_days)

    # The data's rows are LABELS (typically open times, per this project's
    # left-labeled bar convention -- see cutoff.py), so the actual calendar
    # coverage extends one bar-width PAST the last label, not up to it. This
    # is the same class of trap cutoff.py documents for label-vs-close-time:
    # without it, e.g. 270 daily rows tiled into three exact 90-day blocks
    # would wrongly mark the third block "partial", since the last row's own
    # LABEL (day 269) falls short of the nominal 270-day span even though
    # the data fully covers it. Inferred from the data itself (median
    # spacing) rather than assumed, since this module is timeframe-agnostic.
    diffs = data.index.to_series().diff().dropna()
    bar_width = diffs.median() if len(diffs) else pd.Timedelta(0)
    coverage_end = data_end + bar_width

    blocks = []
    start = first_origin
    i = 0
    while start <= data_end:
        end = start + step
        subset = data[(data.index >= start) & (data.index < end)]
        is_final_partial = end > coverage_end
        blocks.append(
            {"block_index": i, "start": start, "end": end, "data": subset, "is_final_partial": is_final_partial}
        )
        start = end
        i += 1
    return blocks


if __name__ == "__main__":
    first_origin = pd.Timestamp("2020-01-01", tz="UTC")

    # ---- Exactly 3 full 90-day blocks, no partial remainder. --------------
    idx_exact = pd.date_range(first_origin, periods=270, freq="1D", tz="UTC")  # 2020-01-01 .. 2020-09-26
    df_exact = pd.DataFrame({"value": range(270)}, index=idx_exact)
    blocks_exact = tile_blocks(df_exact, first_origin, block_days=90)
    assert len(blocks_exact) == 3
    assert all(not b["is_final_partial"] for b in blocks_exact), "an exact multiple of block_days has no partial block"
    assert blocks_exact[0]["start"] == first_origin
    assert blocks_exact[0]["end"] == first_origin + pd.Timedelta(days=90)
    assert blocks_exact[1]["start"] == blocks_exact[0]["end"], "blocks must be contiguous, non-overlapping"
    assert len(blocks_exact[0]["data"]) == 90 and len(blocks_exact[2]["data"]) == 90

    # ---- 105 days of data: one full block, one genuinely partial block. --
    idx_partial = pd.date_range(first_origin, periods=105, freq="1D", tz="UTC")
    df_partial = pd.DataFrame({"value": range(105)}, index=idx_partial)
    blocks_partial = tile_blocks(df_partial, first_origin, block_days=90)
    assert len(blocks_partial) == 2
    assert blocks_partial[0]["is_final_partial"] is False
    assert blocks_partial[1]["is_final_partial"] is True
    assert len(blocks_partial[0]["data"]) == 90
    assert len(blocks_partial[1]["data"]) == 15, "the partial block only has the 15 remaining days of real data"

    # ---- Rows before first_origin are excluded entirely, not folded into
    # block 0. ---------------------------------------------------------------
    idx_early = pd.date_range(first_origin - pd.Timedelta(days=10), periods=100, freq="1D", tz="UTC")
    df_early = pd.DataFrame({"value": range(100)}, index=idx_early)
    blocks_early = tile_blocks(df_early, first_origin, block_days=90)
    assert blocks_early[0]["data"].index.min() >= first_origin
    assert len(blocks_early[0]["data"]) == 90  # the 10 pre-origin rows are dropped, not counted

    # ---- Empty data -> no blocks, no error. --------------------------------
    assert tile_blocks(pd.DataFrame({"value": []}, index=pd.DatetimeIndex([], tz="UTC")), first_origin) == []
    idx_before = pd.date_range(first_origin - pd.Timedelta(days=30), periods=5, freq="1D", tz="UTC")
    df_before_only = pd.DataFrame({"value": range(5)}, index=idx_before)
    assert tile_blocks(df_before_only, first_origin) == [], "data entirely before first_origin yields no blocks"

    # ---- Hourly data: bar-width inference must use the data's OWN spacing
    # (1 hour), not an assumed 1-day constant -- 90*24 exact hourly rows must
    # show zero partial blocks, matching the exact-multiple daily case above.
    idx_hourly = pd.date_range(first_origin, periods=90 * 24 * 3, freq="1h", tz="UTC")
    df_hourly = pd.DataFrame({"value": range(len(idx_hourly))}, index=idx_hourly)
    blocks_hourly = tile_blocks(df_hourly, first_origin, block_days=90)
    assert len(blocks_hourly) == 3
    assert all(not b["is_final_partial"] for b in blocks_hourly), "exact hourly multiple must show no partial block"
    assert all(len(b["data"]) == 90 * 24 for b in blocks_hourly)

    print(
        "Self-test passed: tile_blocks produces contiguous non-overlapping blocks from first_origin, "
        "correctly flags only a genuinely calendar-short final block as partial (not merely a "
        "sparser one), excludes pre-origin rows entirely, and handles empty/all-early data cleanly."
    )
