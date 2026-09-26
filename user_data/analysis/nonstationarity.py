"""
Item 2, fourth piece: by-year / leave-one-year-out machinery (the
"non-stationarity rule" -- mathematician NOTES.md section 6, immediately
after the pipeline's numbered steps; handoff v2.2 sections 7.10/103/137/202;
work order 1.2 section 2/1.3 section 5).

WHAT THIS CHECKS. For every primary cell's discovery-sample estimate,
report a by-year table (or by-month for ETH/FDUSD -- pass `period="M"`) and
leave-one-year(-month)-out estimates. RED FLAG ("year-driven", verbatim
from section 6): "if dropping any single year (month) cuts the estimate by
more than half or flips its sign, mark it year-driven; it does not advance
without my review." This module computes and flags that; the actual
"does not advance" gating is the pipeline's job (not yet built), not this
module's -- this is a diagnostic, not an enforcement gate like
holdout_lock.py.

PARTIAL-PERIOD RULE (verbatim, section 6): "Years with fewer than 120 days
of data are shown (with n and days covered) but not judged: they stay in
the pooled estimate and are excluded from leave-one-year-out and
year-by-year sign statements." Concretely, three separate things:
  1. EVERY period appears in `by_year_table`, with n, days covered, and its
     own point estimate -- always shown, regardless of size.
  2. A period below the day threshold is NEVER ITSELF DROPPED in the
     leave-one-out procedure (dropping a 20-day sliver and finding the
     pooled estimate barely moves is not a meaningful robustness check --
     of course it wouldn't move much) -- but its DATA IS NEVER REMOVED from
     any OTHER period's leave-one-out computation either. "Stay in the
     pooled estimate" means exactly that: only the one period actually
     being tested for removal is ever excluded from any given leave-one-out
     estimate; a sub-threshold period's rows remain present in every other
     period's "everything except period Y" computation, and in the overall
     pooled estimate.
  3. A period below the threshold is excluded from the "year-by-year sign
     statement" (`sign_agreement` below) -- it does not count toward
     "does every individual judged year's own estimate agree in sign with
     the pooled estimate".

DAYS COVERED, defined precisely (this exact operational definition is not
spelled out anywhere in the source material, so it's stated here as an
explicit interpretive choice per project convention): the count of DISTINCT
CALENDAR DATES present in the period's data -- not a row count, and not a
period-length constant. A leap year with only 6 months of intraday
5-minute bars covers ~180 days, not 366 and not
(6-months x bars-per-day). `n` (row count) is reported separately for
exactly this reason: days-covered answers a different question ("how much
of the calendar do we actually have data for") than n does, and the
120-day threshold is checking the former.

`estimator(subset_df) -> float` is caller-supplied and deliberately
generic -- "the estimate" means different things for different primary
cells (S1's mean effect, S2's OLS slope, Task 3's coefficient); this module
has no opinion on how it's computed, only on how the input is sliced by
calendar period, recombined, and compared. `subset_df` is always a slice of
the original `df` (same columns), so any estimator written against the full
`df` also works unchanged on every by-year / leave-one-out subset.
"""

from __future__ import annotations

import pandas as pd

DEFAULT_MIN_DAYS = 120


def _period_labels(index: pd.DatetimeIndex, period: str) -> pd.Index:
    """Year (int) or "YYYY-MM" (str) label per row, per `period` ("Y" or
    "M")."""
    if period == "Y":
        return index.year
    if period == "M":
        return index.strftime("%Y-%m")
    raise ValueError(f"period must be 'Y' or 'M', got {period!r}")


def by_year_table(
    df: pd.DataFrame, estimator, period: str = "Y", min_days: int = DEFAULT_MIN_DAYS
) -> pd.DataFrame:
    """One row per calendar period present in `df` (`df.index` must be a
    DatetimeIndex): n (row count), days_covered (distinct calendar dates --
    see module docstring), the period's own point estimate (`estimator`
    applied to just that period's rows), and `judged` (days_covered >=
    min_days). Every period is shown regardless of `judged` -- see rule 1
    in the module docstring."""
    labels = _period_labels(df.index, period)
    rows = []
    for label in pd.unique(labels):
        subset = df[labels == label]
        days_covered = subset.index.normalize().nunique()
        rows.append(
            {
                "period": label,
                "n": len(subset),
                "days_covered": days_covered,
                "estimate": estimator(subset),
                "judged": days_covered >= min_days,
            }
        )
    out = pd.DataFrame(rows).sort_values("period").reset_index(drop=True)
    return out


def leave_one_out(
    df: pd.DataFrame, estimator, period: str = "Y", min_days: int = DEFAULT_MIN_DAYS
) -> dict:
    """{period_label: estimate computed on df with ONLY that period's rows
    removed}, for every JUDGED period only (rule 2 in the module docstring
    -- a sub-threshold period is never itself dropped, though its data
    remains present in every other period's leave-one-out subset since only
    the one period under test is ever excluded)."""
    labels = _period_labels(df.index, period)
    table = by_year_table(df, estimator, period=period, min_days=min_days)
    judged_periods = table.loc[table["judged"], "period"]
    return {label: estimator(df[labels != label]) for label in judged_periods}


def non_stationarity_report(
    df: pd.DataFrame,
    estimator,
    period: str = "Y",
    min_days: int = DEFAULT_MIN_DAYS,
) -> dict:
    """Bundles the pooled estimate, the by-year/by-month table, leave-one-out
    estimates, the section-6 "year-driven" red flag per judged period
    (dropping it more than halves the pooled estimate's magnitude, OR flips
    its sign -- either alone is enough, verbatim "more than half OR flips
    its sign"), and the year-by-year sign agreement statement (judged
    periods only, rule 3).

    Returns a dict:
      pooled_estimate: float, estimator(df) -- the full, unrestricted estimate.
      by_year: the by_year_table DataFrame.
      leave_one_out: {period: estimate-excluding-that-period}.
      year_driven: {period: bool}, judged periods only.
      any_year_driven: bool -- True if ANY judged period is year_driven; this
        is the section-6 red flag ("it does not advance without my review").
      sign_agreement: {period: bool}, judged periods only -- does that
        period's OWN estimate (from by_year, not leave_one_out) share the
        pooled estimate's sign.
      all_judged_years_agree: bool -- True iff every judged period's own
        sign matches the pooled estimate's sign.
    """
    pooled = estimator(df)
    table = by_year_table(df, estimator, period=period, min_days=min_days)
    loo = leave_one_out(df, estimator, period=period, min_days=min_days)

    def _is_year_driven(loo_estimate: float) -> bool:
        magnitude_halved = abs(loo_estimate) < abs(pooled) / 2
        sign_flipped = (loo_estimate > 0) != (pooled > 0) and loo_estimate != 0 and pooled != 0
        return bool(magnitude_halved or sign_flipped)

    year_driven = {label: _is_year_driven(est) for label, est in loo.items()}

    judged = table.loc[table["judged"]]
    sign_agreement = {
        row["period"]: (row["estimate"] > 0) == (pooled > 0)
        for _, row in judged.iterrows()
    }

    return {
        "pooled_estimate": pooled,
        "by_year": table,
        "leave_one_out": loo,
        "year_driven": year_driven,
        "any_year_driven": any(year_driven.values()),
        "sign_agreement": sign_agreement,
        "all_judged_years_agree": all(sign_agreement.values()) if sign_agreement else True,
    }


if __name__ == "__main__":
    import numpy as np

    def mean_estimator(subset: pd.DataFrame) -> float:
        return float(subset["value"].mean())

    # ---- Dataset 1: a magnitude-halving "year-driven" year (2024), plus a
    # sub-120-day partial year (2020) that must be shown but never itself
    # droppable, while still counting toward the pooled estimate AND toward
    # every other year's leave-one-out subset. -----------------------------
    def make_year(year: int, n_days: int, value: float) -> pd.DataFrame:
        idx = pd.date_range(f"{year}-01-01", periods=n_days, freq="1D", tz="UTC")
        return pd.DataFrame({"value": value}, index=idx)

    df1 = pd.concat(
        [
            make_year(2020, 30, 5.0),  # partial: 30 days < 120, NOT judged
            make_year(2021, 200, 2.0),
            make_year(2022, 200, 2.0),
            make_year(2023, 200, 2.0),
            make_year(2024, 200, 20.0),  # the "driven" year
        ]
    )

    table1 = by_year_table(df1, mean_estimator)
    assert list(table1["period"]) == [2020, 2021, 2022, 2023, 2024]
    assert list(table1["n"]) == [30, 200, 200, 200, 200]
    assert list(table1["days_covered"]) == [30, 200, 200, 200, 200]
    assert list(table1["judged"]) == [False, True, True, True, True]
    assert abs(table1.loc[table1["period"] == 2020, "estimate"].iloc[0] - 5.0) < 1e-9

    report1 = non_stationarity_report(df1, mean_estimator)
    pooled1 = (30 * 5.0 + 200 * 2.0 + 200 * 2.0 + 200 * 2.0 + 200 * 20.0) / (30 + 200 * 4)
    assert abs(report1["pooled_estimate"] - pooled1) < 1e-9

    # 2020 must never appear in leave_one_out or year_driven (not judged).
    assert 2020 not in report1["leave_one_out"]
    assert 2020 not in report1["year_driven"]
    assert 2020 not in report1["sign_agreement"]

    # Excluding 2024 (the driven year) removes 200 rows of value=20, but
    # 2020's 30 rows of value=5 MUST still be present in the remaining pool
    # (rule 2) -- verify the arithmetic reflects that, not their removal.
    loo_2024 = (30 * 5.0 + 200 * 2.0 + 200 * 2.0 + 200 * 2.0) / (30 + 600)
    assert abs(report1["leave_one_out"][2024] - loo_2024) < 1e-9
    assert report1["year_driven"][2024] is True, "dropping 2024 must more-than-halve the pooled estimate"

    # Excluding any of the three "normal" years (2021/2022/2023) must NOT
    # trigger year_driven -- confirms the flag isn't just noise-triggered.
    for y in (2021, 2022, 2023):
        assert report1["year_driven"][y] is False, f"{y} should not be flagged year-driven"

    assert report1["any_year_driven"] is True
    # All judged years are positive, pooled is positive -> full agreement.
    assert report1["all_judged_years_agree"] is True

    # ---- Dataset 2: a sign-flip "year-driven" year (Year A), isolating the
    # sign-flip branch of the red flag from the magnitude-halving branch. --
    idxA = pd.date_range("2021-01-01", periods=200, freq="1D", tz="UTC")
    idxB = pd.date_range("2022-01-01", periods=200, freq="1D", tz="UTC")
    idxC = pd.date_range("2023-01-01", periods=200, freq="1D", tz="UTC")
    df2 = pd.concat(
        [
            pd.DataFrame({"value": -3.0}, index=idxA),
            pd.DataFrame({"value": 1.0}, index=idxB),
            pd.DataFrame({"value": 1.0}, index=idxC),
        ]
    )
    report2 = non_stationarity_report(df2, mean_estimator)
    pooled2 = (200 * -3.0 + 200 * 1.0 + 200 * 1.0) / 600
    assert abs(report2["pooled_estimate"] - pooled2) < 1e-9
    assert pooled2 < 0

    loo_A = (200 * 1.0 + 200 * 1.0) / 400  # = 1.0, opposite sign to pooled
    assert abs(report2["leave_one_out"][2021] - loo_A) < 1e-9
    assert report2["year_driven"][2021] is True, "dropping year A must flip the sign -> year-driven"
    assert report2["year_driven"][2022] is False
    assert report2["year_driven"][2023] is False
    assert report2["any_year_driven"] is True

    # Sign-agreement statement: pooled is negative; year A's own estimate is
    # negative (agrees), years B and C are positive (disagree) -> not all
    # judged years agree.
    assert report2["sign_agreement"][2021] is True
    assert report2["sign_agreement"][2022] is False
    assert report2["sign_agreement"][2023] is False
    assert report2["all_judged_years_agree"] is False

    # ---- Stationary dataset: no year should ever be flagged. -------------
    rng = np.random.default_rng(0)
    idx_stat = pd.date_range("2021-01-01", periods=1200, freq="1D", tz="UTC")
    df3 = pd.DataFrame({"value": 2.0 + rng.normal(0, 0.05, size=len(idx_stat))}, index=idx_stat)
    report3 = non_stationarity_report(df3, mean_estimator)
    assert report3["any_year_driven"] is False, "a stationary series must not trigger the red flag"
    assert report3["all_judged_years_agree"] is True

    # ---- by-month grouping (ETH/FDUSD convention) works the same way. ----
    idx_m = pd.date_range("2024-01-01", periods=400, freq="1D", tz="UTC")
    df4 = pd.DataFrame({"value": 1.0}, index=idx_m)
    table_m = by_year_table(df4, mean_estimator, period="M", min_days=20)
    assert table_m["period"].iloc[0].startswith("2024-")
    assert len(table_m) == pd.unique(idx_m.strftime("%Y-%m")).size

    print(
        "Self-test passed: by_year_table shows every period (including a sub-120-day partial one) "
        "with correct n/days_covered/judged; leave_one_out never drops a sub-threshold period but "
        "keeps its data in every other period's subset and in the pooled estimate; the year-driven "
        "red flag fires correctly for both a magnitude-halving year and a sign-flipping year, and "
        "not for ordinary years or a stationary series; sign_agreement matches by hand; by-month "
        "grouping works identically."
    )
