"""
Item 2, sixth piece (part 1): the rule evaluator's core mechanics
(mathematician NOTES.md section 6, "Rule evaluator" -- built now because
"step 3 needs it immediately afterward"). This module is the position ->
cost -> return engine; `economic_gate.py` (built on top of this) applies it
to section 6 step 3's specific pass/fail rule, and the eventual
forward-test command will apply it to step 5's holdout evaluation.

WHAT THIS MODULE DOES NOT YET DO: the full "Outputs" list in section 6's
"Rule evaluator" paragraph is broader than what's built here -- by-year
table, growth-per-week, max drawdown, and buy-and-hold/cash benchmarks are
NOT part of this piece. This module covers the mechanics precisely enough
for `economic_gate.py` to use correctly (gross/net compounded return,
per-bar attribution for later slicing into blocks, trade log, hit rate);
the rest of the reporting surface is later work, not silently skipped --
flagged here so it isn't mistaken for done.

MECHANICS, PER SECTION 6:
- "vectorized long/flat rule on closed bars, entry/exit at the next bar's
  open": `signal[k]` (0 or 1) is decided using information available at
  bar k's CLOSE, and is EXECUTED at bar (k+1)'s open -- so the position
  actually HELD during the interval [open[k], open[k+1]) is `signal[k-1]`,
  i.e. `held_position = signal.shift(1)`. The segment "starts flat"
  (section 6, step 3 and step 5's end-of-segment note), so
  `held_position[0] = 0` -- there is no bar before the segment to have
  supplied a signal, and `.shift(1).fillna(0)` gives exactly this for free
  without special-casing the first bar.
- "costs charged only when the position changes": a trade (and its cost)
  occurs at open[k] iff `held_position[k] != held_position[k-1]`
  (comparing against 0 for k=0, per "starts flat"). This is what makes "a
  position may carry across a block boundary at no cost" (step 3) true:
  nothing here ties a cost to any particular DATE or block edge, only to
  an actual change in the position.
- End-of-segment handling: "every evaluation segment [...] starts flat and
  is forced to exit at its last close [...] labeled 'end-of-sample exit'."
  The very last bar (index n-1) never gets a normal entry/exit via the
  open[k]->open[k+1] mechanism above (there is no open[n] within the
  segment) -- whatever position was held going into bar n-1 is force-closed
  at bar n-1's OWN close, as one extra "closing leg" (open[n-1] to
  close[n-1]) layered on top of that bar's already-attributed interval
  return, charged the same per-side cost if a position was actually open.

INTERPRETIVE NOTE ON BLOCK BOUNDARIES, CONFIRMED BY THE MATHEMATICIAN
(docs/correspondence/answer-03.md, 2026-09-26) -- this was flagged rather
than assumed, and is now settled, not an open question: section 6 step 3
says both "every evaluation segment [...] a discovery block, the whole
discovery sample, the holdout -- starts flat" AND, two sentences earlier,
"a position may carry across a block boundary at no cost." These do not
actually conflict: "evaluation segment" and "block" are not the same thing
-- block boundaries sit INSIDE an evaluation segment, and only the
segment's own start and end force a flat position. The economic gate's
90-day tiles are reporting slices of ONE pre-registered rule run
continuously across the whole discovery sample; they are not themselves
separate evaluation segments. "A discovery block" in step 5's general list
refers to a genuinely different kind of block used elsewhere in the
pipeline -- Task 3's walk-forward validate windows, where each split tests
a freshly-fit model on unseen data and there is no reason for a position to
carry from one split into another (consecutive splits' windows aren't even
guaranteed to be adjacent).

GENERAL PRINCIPLE (stated by the mathematician, for reuse without
re-deriving it): an evaluation segment is whatever spans ONE CONTINUOUS,
UNCHANGING RULE. This is the test to apply anywhere else "segment" or
"block" shows up in the pipeline:
  - The economic gate's 90-day tiles: NOT separate segments (one rule, one
    continuous run, tiles are just reporting slices -- this module's design).
  - Task 3's walk-forward validate windows: ARE separate segments (a new
    fit each time -- genuinely a different rule instance per split).
  - THE HOLDOUT (step 5, not yet built): confirmed to follow the SAME logic
    as the discovery sample -- one continuous flat-start/forced-exit run
    over the WHOLE holdout window, no internal tiling. Simpler than
    discovery: no 70%-of-blocks statistic at the holdout, just a single
    pooled pass/fail. When the forward-test command is built, call
    `evaluate_rule` ONCE over the full holdout range exactly as
    `economic_gate.py` does for the discovery sample -- do not tile it.
  - Step 2 (stability) is UNAFFECTED by any of this: it reuses the same
    90-day date ranges as step 3 for convenience, but it's a regression-sign
    check with no simulated position at all, so "boundary cost" doesn't
    apply there.
"""

from __future__ import annotations

import pandas as pd

BASE_FEE_PER_SIDE = 0.0010
BASE_SLIPPAGE_PER_SIDE = 0.0002
STRESS_FEE_PER_SIDE = 0.0012
STRESS_SLIPPAGE_PER_SIDE = 0.0003
BASE_COST_PER_SIDE = BASE_FEE_PER_SIDE + BASE_SLIPPAGE_PER_SIDE
STRESS_COST_PER_SIDE = STRESS_FEE_PER_SIDE + STRESS_SLIPPAGE_PER_SIDE


def held_positions(signal: pd.Series) -> pd.Series:
    """The position actually HELD per bar (0/1), given `signal` (0/1,
    decided at each bar's own close). Entry/exit at the NEXT bar's open, and
    the segment starts flat -- both are exactly `signal.shift(1).fillna(0)`,
    no special-casing needed for the first bar."""
    return signal.shift(1).fillna(0).astype(int)


def evaluate_rule(df: pd.DataFrame, signal: pd.Series, cost_per_side: float) -> dict:
    """Evaluate one long/flat rule over one evaluation segment (the whole
    `df` given -- see the module docstring's interpretive note on what
    counts as "one segment" for the economic gate). `df` needs "open" and
    "close" columns; `signal` must be aligned to `df.index`, values in
    {0, 1}.

    Returns a dict:
      gross_return, net_return: total compounded return over the WHOLE
        segment (gross = no costs; net = after costs).
      per_bar_net_return: pd.Series aligned to df.index -- bar k holds the
        net return REALIZED by the time bar k concludes (the interval
        ending at open[k], for k>=1; bar 0 is always 0, nothing has been
        realized yet). The LAST bar's entry additionally includes the
        forced end-of-segment exit leg, compounded in. Cumulative product
        of (1 + per_bar_net_return) over any date-range slice gives that
        slice's own compounded net return WITHOUT re-simulating -- this is
        what `economic_gate.py` slices into 90-day blocks.
      per_bar_gross_return: same, without costs.
      n_trades: count of position-change events, INCLUDING the final
        forced exit if a position was open at the end (each counted once,
        whichever side it is -- entry or exit).
      trades: list of {entry_time, exit_time, gross_return, net_return,
        forced} for each complete entry-to-exit run (forced=True only for
        one that ends via the end-of-segment forced exit).
      hit_rate: fraction of `trades` with net_return > 0 (NaN if no trades).
    """
    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()
    n = len(df)
    held = held_positions(signal).to_numpy()

    per_bar_net = [0.0] * n
    per_bar_gross = [0.0] * n
    n_trades = 0
    trades = []
    entry_idx = None

    prev = 0
    for k in range(n - 1):
        cur = held[k]
        net_mult = 1.0
        if cur != prev:
            n_trades += 1
            net_mult *= 1 - cost_per_side
            if prev == 0 and cur == 1:
                entry_idx = k
            elif prev == 1 and cur == 0:
                gross_ret = opens[k] / opens[entry_idx] - 1
                # The trade's own net return also carries the entry AND
                # this exit cost (two sides total for one round trip).
                net_ret = (1 - cost_per_side) * (opens[k] / opens[entry_idx]) * (1 - cost_per_side) - 1
                trades.append(
                    {"entry_time": df.index[entry_idx], "exit_time": df.index[k], "gross_return": gross_ret, "net_return": net_ret, "forced": False}
                )
                entry_idx = None
        raw_ret = opens[k + 1] / opens[k] - 1
        gross_leg = 1 + cur * raw_ret
        net_leg = gross_leg * net_mult
        per_bar_net[k + 1] = net_leg - 1
        per_bar_gross[k + 1] = gross_leg - 1
        prev = cur

    # End-of-segment forced exit: whatever position was held going into the
    # last bar (== `prev` after the loop) is closed at that bar's own close.
    if n >= 1 and prev == 1:
        n_trades += 1
        final_gross_leg = closes[n - 1] / opens[n - 1]
        final_net_leg = final_gross_leg * (1 - cost_per_side)
        # Layer this closing leg on top of whatever was already attributed
        # to the last bar (its own open-to-open interval, if any).
        per_bar_gross[n - 1] = (1 + per_bar_gross[n - 1]) * final_gross_leg - 1
        per_bar_net[n - 1] = (1 + per_bar_net[n - 1]) * final_net_leg - 1
        gross_ret = closes[n - 1] / opens[entry_idx] - 1
        net_ret = (1 - cost_per_side) * (closes[n - 1] / opens[entry_idx]) * (1 - cost_per_side) - 1
        trades.append(
            {"entry_time": df.index[entry_idx], "exit_time": df.index[n - 1], "gross_return": gross_ret, "net_return": net_ret, "forced": True}
        )

    per_bar_net_s = pd.Series(per_bar_net, index=df.index)
    per_bar_gross_s = pd.Series(per_bar_gross, index=df.index)
    net_return = (1 + per_bar_net_s).prod() - 1
    gross_return = (1 + per_bar_gross_s).prod() - 1
    hit_rate = (sum(1 for t in trades if t["net_return"] > 0) / len(trades)) if trades else float("nan")

    return {
        "gross_return": gross_return,
        "net_return": net_return,
        "per_bar_net_return": per_bar_net_s,
        "per_bar_gross_return": per_bar_gross_s,
        "n_trades": n_trades,
        "trades": trades,
        "hit_rate": hit_rate,
    }


if __name__ == "__main__":
    import numpy as np

    def make_df(opens, closes, start="2020-01-01"):
        idx = pd.date_range(start, periods=len(opens), freq="1D", tz="UTC")
        return pd.DataFrame({"open": opens, "close": closes}, index=idx)

    def reference_evaluate(opens, closes, sig, cost_per_side):
        """Independent, unoptimized reference implementation -- a direct
        transcription of section 6's mechanics, used to cross-check the
        vectorized-ish implementation above rather than trusting either
        alone."""
        n = len(opens)
        prev = 0
        capital = 1.0
        gross_capital = 1.0
        entry_idx = None
        n_trades = 0
        for k in range(n - 1):
            cur = sig[k - 1] if k >= 1 else 0
            if cur != prev:
                n_trades += 1
                capital *= 1 - cost_per_side
                if prev == 0 and cur == 1:
                    entry_idx = k
                prev = cur
            raw = opens[k + 1] / opens[k] - 1
            capital *= 1 + cur * raw
            gross_capital *= 1 + cur * raw
        if prev == 1:
            n_trades += 1
            capital *= 1 - cost_per_side
            capital *= closes[n - 1] / opens[n - 1]
            gross_capital *= closes[n - 1] / opens[n - 1]
        return capital - 1, gross_capital - 1, n_trades

    # ---- Fuzz cross-check: vectorized-ish implementation vs. an
    # independent, obviously-correct reference loop, on many random
    # scenarios. ------------------------------------------------------------
    rng = np.random.default_rng(0)
    for trial in range(30):
        n = rng.integers(5, 60)
        opens = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
        closes = opens * (1 + rng.normal(0, 0.003, n))
        sig = rng.integers(0, 2, n)
        df = make_df(opens, closes)
        signal = pd.Series(sig, index=df.index)
        cost = 0.0012
        result = evaluate_rule(df, signal, cost)
        ref_net, ref_gross, ref_trades = reference_evaluate(opens, closes, sig, cost)
        assert abs(result["net_return"] - ref_net) < 1e-9, f"trial {trial}: net mismatch"
        assert abs(result["gross_return"] - ref_gross) < 1e-9, f"trial {trial}: gross mismatch"
        assert result["n_trades"] == ref_trades, f"trial {trial}: trade count mismatch"
        # per_bar_net_return must itself compound to the same total.
        recompounded = (1 + result["per_bar_net_return"]).prod() - 1
        assert abs(recompounded - result["net_return"]) < 1e-9

    # ---- Required self-test 1: a random walk must be net-negative after
    # costs (zero true edge + any nonzero trading activity => costs win). --
    n = 500
    rw_opens = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    rw_closes = rw_opens * (1 + rng.normal(0, 0.002, n))
    df_rw = make_df(rw_opens, rw_closes)
    noisy_signal = pd.Series((rng.random(n) > 0.5).astype(int), index=df_rw.index)  # trades often, no edge
    rw_result = evaluate_rule(df_rw, noisy_signal, STRESS_COST_PER_SIDE)
    assert rw_result["n_trades"] > 50, "the test needs meaningfully frequent trading to be a real check"
    assert rw_result["net_return"] < 0, "a zero-edge, frequently-trading rule must be net-negative after costs"

    # A sharper, exact version of the same idea: price never moves at all
    # (zero true edge, deterministically), so net_return must equal EXACTLY
    # the compounded cost drag from trading, with zero slack for luck.
    flat_opens = np.full(50, 100.0)
    flat_closes = np.full(50, 100.0)
    df_flat = make_df(flat_opens, flat_closes)
    alternating = pd.Series([i % 2 for i in range(50)], index=df_flat.index)
    flat_result = evaluate_rule(df_flat, alternating, 0.001)
    assert flat_result["gross_return"] == 0.0, "flat prices must show exactly zero gross return regardless of position"
    assert flat_result["net_return"] < 0, "with flat prices, ANY trading must show a strictly negative net return"
    expected_net = (1 - 0.001) ** flat_result["n_trades"] - 1
    assert abs(flat_result["net_return"] - expected_net) < 1e-9, "cost drag on flat prices must match trade count exactly"

    # ---- Required self-test 2: an injected drift must be recovered. ------
    daily_drift = 0.002
    n = 200
    drift_opens = 100 * (1 + daily_drift) ** np.arange(n)
    drift_closes = drift_opens * 1.0
    df_drift = make_df(drift_opens, drift_closes)
    always_long = pd.Series([1] * n, index=df_drift.index)
    drift_result = evaluate_rule(df_drift, always_long, BASE_COST_PER_SIDE)
    # held_position starts flat (interval 0 always earns 0, per "starts
    # flat" -- there's no bar before the segment to have supplied a signal
    # for interval 0), so only intervals k=1..n-2 actually hold the
    # position: (n-2) contributing intervals, not (n-1).
    expected_gross = (1 + daily_drift) ** (n - 2) - 1
    assert abs(drift_result["gross_return"] - expected_gross) < 1e-6, "the known drift must be recovered in gross_return"
    assert drift_result["n_trades"] == 2, "always-long over one segment: exactly one entry, one forced exit"
    assert drift_result["net_return"] < drift_result["gross_return"], "costs must strictly reduce the drift-driven return"

    # ---- Required self-test 3: a position spanning a "block boundary"
    # must be charged costs once, not twice. Simulate ONE continuous
    # segment, then slice per_bar_net_return at a midpoint (a stand-in for
    # a 90-day tile edge, exactly how economic_gate.py will do it) and
    # confirm no extra cost appears at that seam. --------------------------
    n = 40
    span_opens = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.01, n)))
    span_closes = span_opens * 1.0
    df_span = make_df(span_opens, span_closes)
    # Long for bars [5, 35), flat otherwise -- deliberately spans the
    # midpoint (bar 20) with NO signal change there.
    span_signal = pd.Series([1 if 5 <= i < 35 else 0 for i in range(n)], index=df_span.index)
    span_result = evaluate_rule(df_span, span_signal, BASE_COST_PER_SIDE)
    assert span_result["n_trades"] == 2, "one entry, one exit -- the midpoint must not itself be a trade"
    midpoint = df_span.index[20]
    assert span_result["per_bar_net_return"].loc[midpoint] == span_result["per_bar_gross_return"].loc[midpoint], (
        "no cost may appear at a bar where the position did not change, block-boundary-shaped or not"
    )
    first_half = (1 + span_result["per_bar_net_return"].iloc[:20]).prod() - 1
    second_half = (1 + span_result["per_bar_net_return"].iloc[20:]).prod() - 1
    whole = (1 + first_half) * (1 + second_half) - 1
    assert abs(whole - span_result["net_return"]) < 1e-9, (
        "slicing the per-bar series at the midpoint and recompounding must reproduce the whole-segment "
        "return exactly -- i.e. the entry/exit costs are attributed once each, not duplicated or dropped "
        "at the seam"
    )

    print(
        "Self-test passed: evaluate_rule matches an independent reference implementation across 30 "
        "randomized trials; a frequently-trading zero-edge rule is net-negative after costs (both "
        "statistically on a random walk and exactly on flat prices); a known drift is recovered in "
        "gross_return with costs strictly reducing it; and a position spanning a block-boundary-like "
        "midpoint is charged its entry/exit costs exactly once, with the per-bar series slicing and "
        "recompounding exactly back to the whole-segment total."
    )
