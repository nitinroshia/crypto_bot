"""
Task 6 — Walk-forward harness (structure only).

Just the splitting mechanism for now: rolling fit/validate windows over a
date range. No fitting or validation logic goes here yet -- that gets wired
in once Phase 1's findings tell us what's actually worth validating.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class WalkForwardSplit:
    fit_start: pd.Timestamp
    fit_end: pd.Timestamp
    validate_start: pd.Timestamp
    validate_end: pd.Timestamp


def generate_walk_forward_splits(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    fit_period: pd.Timedelta,
    validate_period: pd.Timedelta,
    step: pd.Timedelta | None = None,
) -> list[WalkForwardSplit]:
    """
    Roll a fit window of length `fit_period` followed immediately by a
    validate window of length `validate_period`, advancing by `step` each
    time (defaults to validate_period, i.e. non-overlapping validate blocks).

    Example: fit 9 months, validate the next 3, then roll forward 3 months
    and repeat -- pass fit_period=pd.Timedelta(days=270),
    validate_period=pd.Timedelta(days=90).
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    if step is None:
        step = validate_period

    if fit_period <= pd.Timedelta(0) or validate_period <= pd.Timedelta(0) or step <= pd.Timedelta(0):
        raise ValueError("fit_period, validate_period, and step must all be positive")

    splits = []
    fit_start = start
    while True:
        fit_end = fit_start + fit_period
        validate_start = fit_end
        validate_end = validate_start + validate_period
        if validate_end > end:
            break
        splits.append(
            WalkForwardSplit(
                fit_start=fit_start,
                fit_end=fit_end,
                validate_start=validate_start,
                validate_end=validate_end,
            )
        )
        fit_start = fit_start + step

    return splits


def apply_splits(df: pd.DataFrame, splits: list[WalkForwardSplit]) -> list[dict]:
    """Slice a DatetimeIndex-ed dataframe into fit/validate pieces for each
    split. Still just plumbing -- what you DO with each piece is Phase 2."""
    out = []
    for s in splits:
        out.append(
            {
                "split": s,
                "fit_df": df.loc[s.fit_start : s.fit_end],
                "validate_df": df.loc[s.validate_start : s.validate_end],
            }
        )
    return out


if __name__ == "__main__":
    # Self-test against dummy data: 18 months of daily dummy rows, 9-month
    # fit / 3-month validate / 3-month step -> should produce multiple
    # non-overlapping validate windows that together don't exceed the range.
    idx = pd.date_range("2025-01-01", "2026-07-01", freq="D", tz="UTC")
    dummy = pd.DataFrame({"value": range(len(idx))}, index=idx)

    splits = generate_walk_forward_splits(
        start=idx[0],
        end=idx[-1],
        fit_period=pd.Timedelta(days=270),
        validate_period=pd.Timedelta(days=90),
    )
    assert len(splits) >= 1, "expected at least one split from 18 months of dummy data"

    pieces = apply_splits(dummy, splits)
    for i, p in enumerate(pieces):
        s = p["split"]
        print(
            f"Split {i}: fit [{s.fit_start.date()} -> {s.fit_end.date()}] "
            f"({len(p['fit_df'])} rows), "
            f"validate [{s.validate_start.date()} -> {s.validate_end.date()}] "
            f"({len(p['validate_df'])} rows)"
        )
        assert p["fit_df"].index.max() <= p["validate_df"].index.min(), (
            "fit window must not overlap validate window"
        )

    print(f"Self-test passed: {len(splits)} walk-forward split(s) generated with no fit/validate overlap.")
