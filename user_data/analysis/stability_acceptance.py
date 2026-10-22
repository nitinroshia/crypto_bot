"""
Acceptance tests of the PRODUCTION stability statistic (Work Order 1.5 section 4).

The synthetic generators (`sim_s1`, `sim_s2`) and the acceptance bands come from the
mathematician's `stability_reference.py` (imported, never edited, never copied); the statistic
under test is the production code: `formula_s1.s1_stability_from_returns` (S1: stationary block
bootstrap null, predictor and target rebuilt from every resampled path) and
`stability_check.stability_s2` (S2: circular time-shift null). A band that cannot be met is
reported to the mathematician; the bands are not moved and no different statistic is improvised.

  python3 stability_acceptance.py                      reduced: 60 paths per test, R = 500 (about a minute)
  python3 stability_acceptance.py --full               the real acceptance run: 200 paths, R = 1000
  python3 stability_acceptance.py --compare-reference  also run the reference's own self_test with the
                                                       same seeds and require IDENTICAL observed rates
                                                       (the production code reproduces the reference path by path)
  python3 stability_acceptance.py --confirm-s2-null    only the two S2 false-pass rows, 1000 fresh paths each, R = 2000
                                                       (the confirmation run of answer-to-message-19 section 3a)
Exit status 0 only if every band is met.

FALSE-PASS RULE (answer-to-message-19 section 3a, replacing the false-pass bands of Work Order 1.5 section 4): a
false-pass row passes if the observed rate is at most 7% at the run's path count, OR at most 7% in a confirmation run
of at least 1,000 paths. The confirmation runs automatically for a false-pass row that misses its band (fresh generator
stream, path seeds 0..999, same R as the run); both observed rates are printed. Power rows are unchanged.

Production vs reference: the acceptance origins are exactly B*n per path (no partial block), the case
where the production definition and the reference coincide; the partial-block case (global centring
over the whole origin set, M1 ruling 1) is covered by the self-tests of `stability_check.py` and
`formula_s1.py`, which check it against the definition applied literally.
"""

from __future__ import annotations

import sys
import time

import numpy as np

import stability_check
import stability_reference as ref
from formula_s1 import s1_stability_from_returns

B1, N1 = 30, 90  # S1: 30 blocks of 90 origins
B2, N2 = 22, 270  # S2: 22 blocks of 270 settlements


def _bounds(B: int, n: int) -> list[tuple[int, int]]:
    return [(b * n, (b + 1) * n) for b in range(B)]


CONFIRM_PATHS = 1000
CONFIRM_SEED = 777  # generator stream of the confirmation runs (independent of the main run's stream)
FALSE_PASS_BAND = 0.07


def confirm_false_pass(kind_s: str, kind: str, R: int, P: int = CONFIRM_PATHS, stream: int = 0) -> float:
    """Confirmation run of one false-pass row: P fresh null paths (generator `CONFIRM_SEED + stream`, per-path seeds
    0..P-1), same production statistic. kind_s is 'S1' or 'S2'; kind is 'gauss' or 't3sv'. Returns the observed rate."""
    rng = np.random.default_rng(CONFIRM_SEED + stream)
    if kind_s == "S1":
        r, idx = ref.sim_s1(rng, P, B1, N1, kind, 0.0)
        bounds = _bounds(B1, N1)
        passes = [s1_stability_from_returns(np.concatenate([[0.0], r[i]]), idx + 1, bounds, R=R, seed=i)["p_stab"] < 0.05 for i in range(P)]
    else:
        x, y = ref.sim_s2(rng, P, B2, N2, kind, 0.0)
        bounds = _bounds(B2, N2)
        passes = [stability_check.stability_s2(x[i], y[i], bounds, -1, R=R, seed=i)["p_stab"] < 0.05 for i in range(P)]
    return float(np.mean(passes))


def run(P: int = 60, R: int = 500, full: bool = False, compare_reference: bool = False) -> bool:
    """Run the seven acceptance tests; returns True iff every band is met. The generator RNG
    (seed 12345) and the per-path seeds (the path index) match the reference's own `self_test`,
    so the observed rates are directly comparable (and, with a correct statistic, identical)."""
    if full:
        P, R = 200, 1000
    rng = np.random.default_rng(12345)
    bounds1, bounds2 = _bounds(B1, N1), _bounds(B2, N2)
    observed: list[float] = []

    def s1_rate(kind: str, a: float) -> float:
        r, idx = ref.sim_s1(rng, P, B1, N1, kind, a)
        passes = [
            s1_stability_from_returns(np.concatenate([[0.0], r[i]]), idx + 1, bounds1, R=R, seed=i)["p_stab"] < 0.05
            for i in range(P)
        ]
        return float(np.mean(passes))

    def s2_rate(kind: str, a: float) -> float:
        x, y = ref.sim_s2(rng, P, B2, N2, kind, a)
        passes = [stability_check.stability_s2(x[i], y[i], bounds2, -1, R=R, seed=i)["p_stab"] < 0.05 for i in range(P)]
        return float(np.mean(passes))

    tests = [
        ("S1 null, Gaussian iid            false-pass <= 0.07", lambda: s1_rate("gauss", 0.0), lambda v: v <= 0.07, ("S1", "gauss")),
        ("S1 null, t3 + volatility cluster false-pass <= 0.07", lambda: s1_rate("t3sv", 0.0), lambda v: v <= 0.07, ("S1", "t3sv")),
        ("S1 edge a=0.006 (pooled t ~ 5)   pass >= 0.70", lambda: s1_rate("gauss", 0.006), lambda v: v >= 0.70, None),
        ("S1 edge a=0.012 (pooled t ~ 11)  pass >= 0.95", lambda: s1_rate("gauss", 0.012), lambda v: v >= 0.95, None),
        ("S2 null, Gaussian                false-pass <= 0.07", lambda: s2_rate("gauss", 0.0), lambda v: v <= 0.07, ("S2", "gauss")),
        ("S2 null, t3 + volatility cluster false-pass <= 0.07", lambda: s2_rate("t3sv", 0.0), lambda v: v <= 0.07, ("S2", "t3sv")),
        ("S2 edge a=0.003 (corr ~ -0.16)   pass >= 0.80", lambda: s2_rate("gauss", 0.003), lambda v: v >= 0.80, None),
    ]
    print(f"stability acceptance: {P} paths per test, R = {R} replicates{' (FULL)' if full else ' (reduced)'}", flush=True)
    ok = True
    t_start = time.time()
    for test_no, (name, runner, check, conf) in enumerate(tests):
        t0 = time.time()
        v = runner()
        observed.append(v)
        good = bool(check(v))
        note = ""
        if not good and conf is not None:  # false-pass row missed its band: the confirmation run decides (section 3a)
            vc = confirm_false_pass(conf[0], conf[1], R, stream=test_no)
            good = vc <= FALSE_PASS_BAND
            note = f"   [{P}-path rate above the band; confirmation run {CONFIRM_PATHS} paths, R = {R}: observed {vc:.3f} -> {'accepted' if good else 'REJECTED'}]"
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}   observed {v:.3f}   ({time.time() - t0:.0f}s){note}", flush=True)
    print(f"total {time.time() - t_start:.0f}s")
    if compare_reference:
        print("reference's own self_test, same seeds (expect identical observed rates):", flush=True)
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ref.self_test(P=P, R=R, full=full)
        ref_rates = [float(line.rsplit("observed", 1)[1]) for line in buf.getvalue().splitlines() if "observed" in line]
        print("  reference rates :", ref_rates)
        print("  production rates:", [round(v, 3) for v in observed])
        same = len(ref_rates) == len(observed) and all(abs(a - b) < 5e-4 for a, b in zip(ref_rates, observed))
        print("  IDENTICAL to the reference" if same else "  DIFFERENT from the reference")
        ok &= same
    print("ALL STABILITY ACCEPTANCE TESTS PASSED" if ok else "STABILITY ACCEPTANCE TESTS FAILED")
    return ok


def confirm_s2_null(R: int = 2000) -> bool:
    """The confirmation run asked for in answer-to-message-19 section 3a: both S2 false-pass rows, 1000 fresh paths each,
    at the production R. Exit 0 iff both observed rates are <= 7%."""
    print(f"S2 false-pass confirmation run: {CONFIRM_PATHS} fresh null paths per row, R = {R} (production), "
          f"generator seed {CONFIRM_SEED} + row, path seeds 0..{CONFIRM_PATHS - 1}", flush=True)
    ok = True
    for stream, (label, kind) in enumerate((("S2 null, Gaussian", "gauss"), ("S2 null, t3 + volatility cluster", "t3sv"))):
        t0 = time.time()
        v = confirm_false_pass("S2", kind, R, stream=stream)
        n_pass = int(round(v * CONFIRM_PATHS))
        good = v <= FALSE_PASS_BAND
        ok &= good
        se = (v * (1 - v) / CONFIRM_PATHS) ** 0.5
        print(f"  {'PASS' if good else 'FAIL'}  {label:36s} false-pass {n_pass}/{CONFIRM_PATHS} = {v:.3f} (binomial se {se:.3f}; band <= 0.07)   ({time.time() - t0:.0f}s)", flush=True)
    print("S2 FALSE-PASS CONFIRMATION PASSED" if ok else "S2 FALSE-PASS CONFIRMATION FAILED")
    return ok


if __name__ == "__main__":
    if "--confirm-s2-null" in sys.argv:
        sys.exit(0 if confirm_s2_null() else 1)
    sys.exit(0 if run(full="--full" in sys.argv, compare_reference="--compare-reference" in sys.argv) else 1)
