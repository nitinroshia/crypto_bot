"""
Item 2, first piece: the `--end-date` guard (work order 1.2 "Sample design";
mathematician NOTES.md section 6, "Cutoff mechanics"). This module is the
hard-truncation mechanism; wiring it into a CLI's `--end-date` flag is
research_cli.py's job (see `load_all_dataframes`).

THE CUTOFF. The ETH/USDT-phase discovery cutoff is 2025-08-31 23:59:59 UTC,
inclusive. Section 6 gives four worked examples of "last usable bar" instead
of a per-timeframe table: 1d labeled 2025-08-31 00:00, 1h labeled 23:00, 15m
labeled 23:45, 5m labeled 23:55. All four are bar LABELS (open time -- bars
are left-labeled, per section 6's Conventions) that are <= CUTOFF, and all
four bars' CLOSE time is exactly 2025-09-01 00:00:00. So the single rule
"keep a bar iff its label <= CUTOFF" reproduces all four examples without a
per-timeframe table -- verified for all four in the self-test below -- and
generalizes to any other timeframe (1w included) the same way.

INTERPRETIVE CHOICE (stated per project convention): "the whole target
window ends at or before the cutoff" (section 6, pipeline step 1) is
evaluated on the window's last required bar LABEL, never its close
timestamp -- consistent with CUTOFF itself being a label-space boundary, and
with the S1 worked example in section 6 ("origin t=2025-08-30, h=1: the
target needs the close of day t+1=2025-08-31, which is <= cutoff"). Passing
a close timestamp instead of a label to `origin_window_side` would reject
every window that legitimately ends on the last usable bar (its close is
2025-09-01 00:00:00, one second past a naive CUTOFF comparison) -- so
callers MUST pass labels, not close times. This is exactly the trap section
6's four examples are worked out to guard against.

HARD TRUNCATION. `truncate_at_cutoff` / `truncate_bundle_at_cutoff` DROP
rows; they do not merely mark or filter downstream. Call once, immediately
after loading, so a formula computed on the result structurally cannot see
a post-cutoff row even if it never heard of this module -- a data-shape
guarantee, not a policy one. This is what section 6 means by "must never
return a single post-cutoff row, not merely filter one out after loading".

HOLDOUT_START (2025-09-01 00:00:00 UTC) is the earliest entry time a holdout
origin may have. There is a deliberate one-second gap between CUTOFF and
HOLDOUT_START; no real bar label falls inside it (bars align to round
boundaries), but `origin_window_side` checks explicitly rather than assuming
so, and reports "straddle" for anything that does.

Only the forward-test command loads the full (untruncated) series -- it
needs pre-cutoff history for lookbacks (section 6). Nothing in this module
enforces that on its own; it only makes truncation trivial to apply
everywhere it's needed. The separate mechanism that locks the holdout region
so only the forward-test command can read it ("holdout lock") is scope for
a later piece of item 2, not this one.
"""

from __future__ import annotations

import pandas as pd

CUTOFF = pd.Timestamp("2025-08-31 23:59:59", tz="UTC")  # inclusive
HOLDOUT_START = pd.Timestamp("2025-09-01 00:00:00", tz="UTC")  # inclusive


def truncate_at_cutoff(df: pd.DataFrame, cutoff: pd.Timestamp = CUTOFF) -> pd.DataFrame:
    """Drop every row whose index (bar label) is after `cutoff`. Never
    mutates `df` in place; always returns a fresh frame, so a caller holding
    a reference to the original still sees the full data (truncation must be
    an explicit, visible step, not something that can leak backward)."""
    return df.loc[df.index <= cutoff].copy()


def truncate_bundle_at_cutoff(bundle, cutoff: pd.Timestamp = CUTOFF):
    """Apply `truncate_at_cutoff` to every series in a DataBundle (or any
    str->DataFrame mapping). Preserves the mapping type: a DataBundle stays
    a DataBundle (bare-timeframe aliasing keeps working on the result), a
    plain dict stays a plain dict."""
    default_pair = getattr(bundle, "default_pair", None)
    out = type(bundle)(default_pair) if default_pair is not None else type(bundle)()
    for k, df in dict(bundle).items():
        out[k] = truncate_at_cutoff(df, cutoff)
    return out


def origin_window_side(
    entry_time: pd.Timestamp,
    window_end_label: pd.Timestamp,
    cutoff: pd.Timestamp = CUTOFF,
    holdout_start: pd.Timestamp = HOLDOUT_START,
) -> str:
    """Classify one candidate origin against the cutoff/holdout boundary.
    Both arguments are bar LABELS (open times), never close timestamps --
    see the module docstring's "INTERPRETIVE CHOICE" note.

    Returns:
      "discovery" -- entry_time <= cutoff AND window_end_label <= cutoff.
                     (Checking the origin's own entry_time >= a family's
                     sample start is the CALLER's job, not this function's:
                     the sample start differs per family -- S1/S2/Task 3
                     each have their own first-usable-origin rule, section
                     6 "Origin sets" -- so there is no single constant to
                     check it against here.)
      "holdout"   -- entry_time >= holdout_start.
      "straddle"  -- neither: entry_time <= cutoff but the window reaches
                     past it, or entry_time falls in the (empty, in
                     practice) one-second gap between cutoff and
                     holdout_start. Belongs to neither sample per section 6.
    """
    if entry_time >= holdout_start:
        return "holdout"
    if entry_time <= cutoff and window_end_label <= cutoff:
        return "discovery"
    return "straddle"


if __name__ == "__main__":
    # ---- The four worked examples from section 6, exactly as stated ------
    examples = {
        "1d": (pd.Timestamp("2025-08-31 00:00", tz="UTC"), pd.Timestamp("2025-08-30 00:00", tz="UTC")),
        "1h": (pd.Timestamp("2025-08-31 23:00", tz="UTC"), pd.Timestamp("2025-08-31 22:00", tz="UTC")),
        "15m": (pd.Timestamp("2025-08-31 23:45", tz="UTC"), pd.Timestamp("2025-08-31 23:30", tz="UTC")),
        "5m": (pd.Timestamp("2025-08-31 23:55", tz="UTC"), pd.Timestamp("2025-08-31 23:50", tz="UTC")),
    }
    for tf, (last_label, prev_label) in examples.items():
        step = last_label - prev_label
        idx = pd.date_range(last_label - 4 * step, last_label + 4 * step, freq=step, tz="UTC")
        df = pd.DataFrame({"close": range(len(idx))}, index=idx)
        kept = truncate_at_cutoff(df)
        assert kept.index.max() == last_label, f"{tf}: expected last kept label {last_label}, got {kept.index.max()}"
        assert last_label + step not in kept.index, f"{tf}: the bar just past cutoff must be dropped"
        assert len(kept) == len(df) - 4, f"{tf}: expected exactly the 4 post-cutoff bars dropped"

    # ---- Never mutates the input, always a fresh frame --------------------
    idx = pd.date_range("2025-08-30", periods=6, freq="1D", tz="UTC")
    original = pd.DataFrame({"close": range(6)}, index=idx)
    before = original.copy()
    _ = truncate_at_cutoff(original)
    assert original.equals(before), "truncate_at_cutoff must not mutate its input"

    # ---- Bundle truncation preserves DataBundle behavior -------------------
    from databundle import DataBundle

    b = DataBundle("ETH_FDUSD")
    b["1d"] = original
    b["ETH_USDT:1d"] = original.copy()
    trunc = truncate_bundle_at_cutoff(b)
    assert isinstance(trunc, DataBundle) and trunc.default_pair == "ETH_FDUSD"
    assert "1d" in trunc and "ETH_USDT:1d" in trunc and "ETH_FDUSD:1d" in trunc  # aliasing survives
    assert trunc["1d"].index.max() == pd.Timestamp("2025-08-31", tz="UTC")
    assert len(trunc["1d"]) == 2 and len(b["1d"]) == 6, "original bundle's frame must be untouched"

    # A plain dict stays a plain dict.
    plain = {"x": original}
    trunc_plain = truncate_bundle_at_cutoff(plain)
    assert type(trunc_plain) is dict and trunc_plain["x"].index.max() == pd.Timestamp("2025-08-31", tz="UTC")

    # ---- origin_window_side: discovery / holdout / straddle ---------------
    d1 = pd.Timestamp("2025-08-30", tz="UTC")
    assert origin_window_side(d1, d1) == "discovery"
    assert origin_window_side(d1, pd.Timestamp("2025-08-31", tz="UTC")) == "discovery"  # S1 worked example
    # Entry inside discovery but the window reaches into the holdout: straddle, not discovery.
    assert origin_window_side(d1, pd.Timestamp("2025-09-02", tz="UTC")) == "straddle"
    assert origin_window_side(HOLDOUT_START, HOLDOUT_START) == "holdout"
    assert origin_window_side(pd.Timestamp("2025-09-05", tz="UTC"), pd.Timestamp("2025-09-06", tz="UTC")) == "holdout"
    # The one-second gap itself: entry after cutoff but before holdout_start -> straddle, not either sample.
    gap_entry = CUTOFF + pd.Timedelta(microseconds=500000)
    assert CUTOFF < gap_entry < HOLDOUT_START
    assert origin_window_side(gap_entry, gap_entry) == "straddle"

    print(
        "Self-test passed: truncate_at_cutoff reproduces all four section-6 worked examples "
        "(1d/1h/15m/5m) via one label<=CUTOFF rule, never mutates input, DataBundle aliasing "
        "survives truncation, plain dicts stay plain dicts, and origin_window_side classifies "
        "discovery/holdout/straddle correctly including the boundary gap."
    )
