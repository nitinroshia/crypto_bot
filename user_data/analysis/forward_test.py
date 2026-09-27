"""
Item 2, final piece (part 2): the forward-test command (mathematician
NOTES.md section 6, pipeline step 5). Ties together `holdout_lock.py`
(one-shot, self-logging holdout access), `freeze_manifest.py` (the
committed discovery-side estimate), and `rule_evaluator.py` (step 3's
economic check, reapplied at the holdout per the confirmed
evaluation-segment ruling -- docs/correspondence/answer-03.md -- as ONE
continuous run over the whole holdout window, no internal tiling).

SPEC, VERBATIM (step 5): "exactly the frozen primary cell, one-sided in
the discovered direction, one look, then consumed. Minimum sample at test
time: at least 45 days, at least 100 events or observations, SE no larger
than half the claimed effect; if not met, wait (ask [the mathematician] if
it needs more than 120 further days). SE_holdout = SE_discovery x
sqrt(N_discovery / N_holdout), with N the primary cell's origin count
after the purge. Success: one-sided p < 0.05 and estimate at least as
large as both M (event-type cells) and half the discovery estimate.
Failure = dead, no retuning."

PLUS, SEPARATELY (step 3, restated for the holdout): "the frozen rule must
also be net-positive at stress cost" -- this is its OWN, independently
labeled result. Per this project's standing requirement (developer
NOTES.md), step 5's statistical result and this economic check are NEVER
collapsed into one pass/fail -- `run_forward_test`'s return value keeps
them in two separate sub-dicts, `step5` and `step3_holdout`, with no
top-level merged verdict. Interpreting how the two combine for a given
candidate is a judgment call for the mathematician/owner, not this module.

TWO-PHASE DESIGN, so the minimum-sample check never burns the one-shot
holdout look: Phase 1 (`check_holdout_readiness`) is a DESCRIPTIVE read
(`holdout_lock.log_descriptive_access`) -- counting days/observations
available in the holdout region relates no predictor to any return, so
it's not hypothesis-specific and can be repeated as often as needed while
waiting for more data. Phase 2 (`run_forward_test`) only calls
`holdout_lock.unlock_holdout_for_forward_test` (the one-shot,
self-logging gate) once Phase 1's minimums are met -- a "not ready" result
never touches the one-shot lock, so the same candidate can be re-checked
later without error once more holdout data has accumulated.

TWO-STEP REGISTRY PATTERN (per holdout_lock.py's own docstring):
`unlock_holdout_for_forward_test`'s own record carries no p-value (it only
gates access). `run_forward_test` appends a SECOND `holdout_consumed`
record, once the real verdict is known, with the actual p-value and both
results in `detail` -- `registry.holm_at_step` already reads each family's
most-recent record, so this second record is what a
`holm_at_step(..., step="holdout_consumed")` call would see.

`estimator(df) -> float` and `count_origins(df) -> int` are caller-supplied
and generic, matching every other module in this pipeline -- this module
has no opinion on what "the estimate" or "an origin" means for a given
candidate, only on the readiness gate, the SE-scaling formula (which is
NOT re-estimated independently at the holdout -- it is SCALED from
discovery's own dispersion, per the verbatim formula above), the one-sided
test, and the three-way classification for event-type cells (M given) vs.
the binary pass/dead classification for non-event-type cells (M omitted,
e.g. S1/S2).
"""

from __future__ import annotations

from math import erf, sqrt
from pathlib import Path

import pandas as pd

import registry
from cutoff import HOLDOUT_START
from databundle import load_bundle
from freeze_manifest import get_frozen_manifest
from holdout_lock import log_descriptive_access, unlock_holdout_for_forward_test
from rule_evaluator import evaluate_rule

ALPHA = 0.05
MIN_DAYS = 45
MIN_OBSERVATIONS = 100
ONE_SIDED_95_Z = 1.645


def _norm_sf(z: float) -> float:
    """Upper-tail standard normal survival function -- see leadlag.py's
    `_norm_cdf` / stability_check.py's own copy for the same convention
    (avoid pulling in scipy just for this)."""
    return 0.5 * (1 - erf(z / sqrt(2)))


def check_holdout_readiness(
    data_dir: Path,
    asset_pair: str,
    timeframe: str,
    pair: str,
    count_origins,
    n_discovery: int,
    se_discovery: float,
    discovery_estimate: float,
    raw_dir: Path | None = None,
    min_days: int = MIN_DAYS,
    min_observations: int = MIN_OBSERVATIONS,
    registry_path: Path = registry.DEFAULT_REGISTRY_PATH,
) -> dict:
    """Phase 1: a DESCRIPTIVE check of how much holdout data is available
    -- logs via `log_descriptive_access` (not the one-shot gate) and never
    touches `unlock_holdout_for_forward_test`, so this can be called
    repeatedly while waiting for more holdout data to accumulate.

    Returns {"ready": bool, "days_covered", "n_holdout", "se_holdout",
    "reasons": [...]} -- `reasons` lists which specific minimums are not
    yet met (empty when ready)."""
    bundle = load_bundle(data_dir, asset_pair, [timeframe], raw_dir=raw_dir)
    log_descriptive_access("forward_test_readiness_check", pair, registry_path=registry_path)

    df = bundle[timeframe]
    holdout_df = df[df.index >= HOLDOUT_START]
    days_covered = holdout_df.index.normalize().nunique()
    n_holdout = count_origins(holdout_df) if len(holdout_df) else 0
    se_holdout = (se_discovery * sqrt(n_discovery / n_holdout)) if n_holdout > 0 else float("inf")

    reasons = []
    if days_covered < min_days:
        reasons.append(f"only {days_covered} of {min_days} required days covered")
    if n_holdout < min_observations:
        reasons.append(f"only {n_holdout} of {min_observations} required observations")
    if se_holdout > abs(discovery_estimate) / 2:
        reasons.append(f"SE_holdout {se_holdout:.6g} exceeds half the claimed effect {abs(discovery_estimate) / 2:.6g}")

    return {
        "ready": not reasons,
        "days_covered": int(days_covered),
        "n_holdout": int(n_holdout),
        "se_holdout": float(se_holdout),
        "reasons": reasons,
    }


def run_forward_test(
    data_dir: Path,
    asset_pair: str,
    timeframe: str,
    family: str,
    pair: str,
    estimator,
    count_origins,
    signal_fn,
    cost_per_side: float,
    m_threshold: float | None = None,
    raw_dir: Path | None = None,
    registry_path: Path = registry.DEFAULT_REGISTRY_PATH,
    min_days: int = MIN_DAYS,
    min_observations: int = MIN_OBSERVATIONS,
    alpha: float = ALPHA,
) -> dict:
    """Phase 2: the actual one-shot forward test, run only if Phase 1 says
    ready. Reads the frozen manifest via `freeze_manifest.get_frozen_manifest`
    for `direction`, `discovery_estimate`, `dispersion` (SE_discovery), and
    `n_discovery` -- this module never accepts those as separate
    parameters, since step 5 must test "exactly the frozen primary cell",
    not a value the caller could pass in fresh.

    Returns one of:
      {"status": "wait", "readiness": {...}} -- Phase 1 not yet satisfied;
        the one-shot lock was NOT touched, safe to retry later.
      {"status": "tested", "step5": {...}, "step3_holdout": {...}} -- the
        one-shot look was consumed; see the module docstring for why these
        two results are never merged into one verdict.
    Propagates `holdout_lock.HoldoutAlreadyConsumedError` unchanged if this
    candidate's one-shot look was already consumed by an earlier call --
    that is the correct behavior (no retuning), not an error to swallow.
    """
    manifest = get_frozen_manifest(family, pair, registry_path=registry_path)
    direction = manifest["detail"]["direction"]
    discovery_estimate = manifest["detail"]["discovery_estimate"]
    se_discovery = manifest["detail"]["dispersion"]
    n_discovery = manifest["detail"]["n_discovery"]

    readiness = check_holdout_readiness(
        data_dir, asset_pair, timeframe, pair, count_origins, n_discovery, se_discovery,
        discovery_estimate, raw_dir=raw_dir, min_days=min_days, min_observations=min_observations,
        registry_path=registry_path,
    )
    if not readiness["ready"]:
        return {"status": "wait", "readiness": readiness}

    # Phase 2: the one-shot, self-logging gate. Raises
    # HoldoutAlreadyConsumedError on a second attempt -- propagated as-is.
    bundle = unlock_holdout_for_forward_test(
        data_dir, asset_pair, [timeframe], family=family, pair=pair, raw_dir=raw_dir, registry_path=registry_path,
    )
    df = bundle[timeframe]
    holdout_df = df[df.index >= HOLDOUT_START]

    n_holdout = count_origins(holdout_df)
    se_holdout = se_discovery * sqrt(n_discovery / n_holdout)
    holdout_estimate = estimator(holdout_df)

    oriented_holdout = holdout_estimate * direction
    oriented_discovery = discovery_estimate * direction
    z = oriented_holdout / se_holdout
    p_value = _norm_sf(z)

    statistical_significant = p_value < alpha
    magnitude_ok = oriented_holdout >= 0.5 * oriented_discovery
    m_ok = True if m_threshold is None else (oriented_holdout >= m_threshold)
    step5_passes = bool(statistical_significant and magnitude_ok and m_ok)

    if m_threshold is None:
        # Non-event-type cells (S1/S2): binary, per "Failure = dead, no
        # retuning" -- no separate "inconclusive" state without an M to
        # test the upper bound against.
        classification = "pass" if step5_passes else "dead"
    else:
        # Event-type cells: three-way, per section 6's "pass = one-sided
        # p<0.05 and excess>=M; dead = one-sided 95% upper bound below M;
        # otherwise inconclusive."
        upper_bound = oriented_holdout + ONE_SIDED_95_Z * se_holdout
        if step5_passes:
            classification = "pass"
        elif upper_bound < m_threshold:
            classification = "dead"
        else:
            classification = "inconclusive"

    # Step 3, restated at the holdout: ONE continuous evaluation segment,
    # no internal tiling (confirmed, docs/correspondence/answer-03.md).
    econ_result = evaluate_rule(holdout_df, signal_fn(holdout_df), cost_per_side)
    step3_holdout_passes = bool(econ_result["net_return"] > 0)

    registry.append_record(
        {
            "family": family,
            "pair": pair,
            "status": "holdout_consumed",
            "timestamp_utc": registry.new_timestamp(),
            "detail": {
                "p_value": float(p_value),
                "step5_passes": step5_passes,
                "classification": classification,
                "step3_holdout_passes": step3_holdout_passes,
                "step3_holdout_net_return": float(econ_result["net_return"]),
                "holdout_estimate": float(holdout_estimate),
                "se_holdout": float(se_holdout),
                "n_holdout": int(n_holdout),
            },
        },
        registry_path,
    )

    return {
        "status": "tested",
        "step5": {
            "p_value": float(p_value),
            "statistical_significant": bool(statistical_significant),
            "magnitude_ok": bool(magnitude_ok),
            "m_ok": bool(m_ok),
            "passes": step5_passes,
            "classification": classification,
            "holdout_estimate": float(holdout_estimate),
            "se_holdout": float(se_holdout),
            "n_holdout": int(n_holdout),
        },
        "step3_holdout": {
            "net_return": float(econ_result["net_return"]),
            "passes": step3_holdout_passes,
        },
    }


if __name__ == "__main__":
    import tempfile

    import numpy as np

    from freeze_manifest import freeze_candidate
    from holdout_lock import HoldoutAlreadyConsumedError
    from rule_evaluator import STRESS_COST_PER_SIDE

    def count_origins(df: pd.DataFrame) -> int:
        """Toy origin-counter for the self-test: one origin per row."""
        return len(df)

    def make_series(n_days: int, drift: float, vol: float, seed: int, start_price: float = 100.0) -> pd.DataFrame:
        r = np.random.default_rng(seed)
        idx = pd.date_range(HOLDOUT_START - pd.Timedelta(days=30), periods=n_days, freq="1D", tz="UTC")
        log_returns = r.normal(drift, vol, n_days)
        opens = start_price * np.exp(np.cumsum(log_returns))
        closes = opens * (1 + r.normal(0, vol / 4, n_days))
        return pd.DataFrame({"open": opens, "close": closes}, index=idx)

    def write_feather(raw_dir: Path, asset_pair: str, timeframe: str, df: pd.DataFrame) -> None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        df.reset_index(names="date").to_feather(raw_dir / f"{asset_pair}-{timeframe}.feather")

    def always_long(df: pd.DataFrame) -> pd.Series:
        return pd.Series(1, index=df.index)

    def mean_estimator(df: pd.DataFrame) -> float:
        return float(df["open"].pct_change().dropna().mean())

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # ---- Scenario A: not enough holdout data yet -> "wait", and the
        # one-shot lock must NOT be touched (repeatable later). -----------
        data_dir_a = tmp / "a" / "binance"
        df_a = make_series(40, drift=0.003, vol=0.01, seed=1)  # only 10 days past HOLDOUT_START
        write_feather(data_dir_a, "ETH_USDT", "1d", df_a)
        registry_path_a = tmp / "a" / "registry.jsonl"
        freeze_candidate("S1-ETHUSDT", "ETHUSDT", direction=1, discovery_estimate=0.01, dispersion=0.004, n_discovery=200, registry_path=registry_path_a)
        result_a = run_forward_test(
            data_dir_a, "ETH_USDT", "1d", "S1-ETHUSDT", "ETHUSDT", mean_estimator, count_origins, always_long,
            STRESS_COST_PER_SIDE, registry_path=registry_path_a,
        )
        assert result_a["status"] == "wait"
        assert result_a["readiness"]["ready"] is False
        assert not any(r["status"] == "holdout_consumed" for r in registry.load_records(registry_path_a)), (
            "a 'wait' result must not consume the one-shot holdout look"
        )
        # Repeating the check must not raise -- it's descriptive, not one-shot.
        result_a2 = run_forward_test(
            data_dir_a, "ETH_USDT", "1d", "S1-ETHUSDT", "ETHUSDT", mean_estimator, count_origins, always_long,
            STRESS_COST_PER_SIDE, registry_path=registry_path_a,
        )
        assert result_a2["status"] == "wait"

        # ---- Scenario B: ready, passes BOTH step5 and step3. -------------
        data_dir_b = tmp / "b" / "binance"
        df_b = make_series(150, drift=0.004, vol=0.008, seed=2)  # ~120 days past HOLDOUT_START
        write_feather(data_dir_b, "ETH_USDT", "1d", df_b)
        registry_path_b = tmp / "b" / "registry.jsonl"
        # n_discovery kept BELOW the ~120 available holdout observations:
        # SE_holdout = SE_discovery * sqrt(n_discovery / n_holdout) only
        # SHRINKS when n_holdout > n_discovery -- if n_discovery were larger
        # than what the holdout can offer, the scaling factor exceeds 1 and
        # SE_holdout would come out LARGER than SE_discovery, not smaller.
        freeze_candidate("S1-ETHUSDT", "ETHUSDT", direction=1, discovery_estimate=0.003, dispersion=0.001, n_discovery=100, registry_path=registry_path_b)
        result_b = run_forward_test(
            data_dir_b, "ETH_USDT", "1d", "S1-ETHUSDT", "ETHUSDT", mean_estimator, count_origins, always_long,
            STRESS_COST_PER_SIDE, registry_path=registry_path_b,
        )
        assert result_b["status"] == "tested"
        assert result_b["step5"]["passes"] is True
        assert result_b["step5"]["classification"] == "pass"
        assert result_b["step3_holdout"]["passes"] is True
        holdout_records = [r for r in registry.load_records(registry_path_b) if r["status"] == "holdout_consumed"]
        assert len(holdout_records) == 2, "expected the access-log record AND the verdict record (two-step pattern)"
        assert holdout_records[0]["detail"]["p_value"] is None, "first record is the bare access log"
        assert holdout_records[1]["detail"]["p_value"] is not None, "second record carries the real verdict"

        # ---- Scenario C: a second attempt on the SAME candidate must
        # raise HoldoutAlreadyConsumedError, propagated unchanged. --------
        try:
            run_forward_test(
                data_dir_b, "ETH_USDT", "1d", "S1-ETHUSDT", "ETHUSDT", mean_estimator, count_origins, always_long,
                STRESS_COST_PER_SIDE, registry_path=registry_path_b,
            )
        except HoldoutAlreadyConsumedError:
            pass
        else:
            raise AssertionError("expected a second forward test on the same candidate to be refused")

        # ---- Scenario D: ready, but the effect is far too weak -> "dead"
        # (binary classification, no M given). -----------------------------
        data_dir_d = tmp / "d" / "binance"
        df_d = make_series(150, drift=0.0000, vol=0.01, seed=3)
        write_feather(data_dir_d, "ETH_USDT", "1d", df_d)
        registry_path_d = tmp / "d" / "registry.jsonl"
        freeze_candidate("S2-ETHUSDT", "ETHUSDT", direction=1, discovery_estimate=0.01, dispersion=0.002, n_discovery=200, registry_path=registry_path_d)
        result_d = run_forward_test(
            data_dir_d, "ETH_USDT", "1d", "S2-ETHUSDT", "ETHUSDT", mean_estimator, count_origins, always_long,
            STRESS_COST_PER_SIDE, registry_path=registry_path_d,
        )
        assert result_d["status"] == "tested"
        assert result_d["step5"]["passes"] is False
        assert result_d["step5"]["classification"] == "dead"

        # ---- Scenario E: step5 passes but step3 (economic) fails -- the
        # two results must be independently reported, never conflated.
        # Uses a near-zero-drift series (statistical "significance" here
        # comes from an artificially tight SE_discovery scaling, not from a
        # large true edge -- exactly the case an independent economic check
        # exists to catch) with a churning, no-edge signal that trades on
        # pure noise; STRESS costs alone must push its net return negative.
        data_dir_e = tmp / "e" / "binance"
        df_e = make_series(150, drift=0.0, vol=0.008, seed=4)
        write_feather(data_dir_e, "ETH_USDT", "1d", df_e)
        registry_path_e = tmp / "e" / "registry.jsonl"
        # Tuned so the tiny realized holdout mean (this fixed seed) clears
        # significance/magnitude comfortably, without relying on a large
        # true drift -- see the module's exploratory notes; not derived
        # from any formula, just picked to give a robust margin either way.
        freeze_candidate("S1-ETHUSDT", "ETHUSDT", direction=1, discovery_estimate=0.001, dispersion=0.000155, n_discovery=100, registry_path=registry_path_e)

        def churning_signal(df: pd.DataFrame) -> pd.Series:
            rng = np.random.default_rng(5)
            return pd.Series((rng.random(len(df)) > 0.5).astype(int), index=df.index)

        result_e = run_forward_test(
            data_dir_e, "ETH_USDT", "1d", "S1-ETHUSDT", "ETHUSDT", mean_estimator, count_origins, churning_signal,
            STRESS_COST_PER_SIDE, registry_path=registry_path_e,
        )
        assert result_e["status"] == "tested"
        assert result_e["step5"]["passes"] is True, "step5 judges the series' own (tiny but precisely-measured) mean, independent of the signal used for step3"
        assert result_e["step3_holdout"]["passes"] is False, "a churning, no-edge signal must fail the economic check on costs alone"

        # ---- Scenario F: event-type cell (M given) -- exercise the
        # three-way classification's "dead" branch: the effect clearly
        # clears step5's own significance/magnitude bar (same series as
        # scenario B) but M=0.01 is set deliberately far above what this
        # series can reach, so even the one-sided 95% upper bound stays
        # below M -- a robust, non-noise-sensitive way to reach "dead"
        # specifically (as opposed to the boundary-straddling
        # "inconclusive" case, which isn't worth a seed-dependent test).
        data_dir_f = tmp / "f" / "binance"
        df_f = make_series(150, drift=0.004, vol=0.008, seed=2)
        write_feather(data_dir_f, "ETH_USDT", "1d", df_f)
        registry_path_f = tmp / "f" / "registry.jsonl"
        freeze_candidate("Task3-ETHUSDT", "ETHUSDT", direction=1, discovery_estimate=0.003, dispersion=0.001, n_discovery=100, registry_path=registry_path_f)
        result_f = run_forward_test(
            data_dir_f, "ETH_USDT", "1d", "Task3-ETHUSDT", "ETHUSDT", mean_estimator, count_origins, always_long,
            STRESS_COST_PER_SIDE, m_threshold=0.01, registry_path=registry_path_f,
        )
        assert result_f["status"] == "tested"
        assert result_f["step5"]["m_ok"] is False, "the effect must fall short of M=0.01"
        assert result_f["step5"]["classification"] == "dead", (
            "a comfortably-below-M effect (upper bound still under M) must classify as dead, not inconclusive"
        )

    print(
        "Self-test passed: insufficient holdout data returns 'wait' without touching the one-shot lock "
        "and can be safely retried; a clear positive effect with a profitable signal passes both step5 "
        "and step3 and writes the two-step registry pattern; a second attempt on an already-tested "
        "candidate is refused; a null effect classifies as dead; step5 and step3 are verified "
        "independent (one can pass while the other fails, from the same underlying series); and the "
        "event-type three-way classification correctly avoids 'pass' for a sub-M effect."
    )
