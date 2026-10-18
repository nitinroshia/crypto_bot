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
Exit status 0 only if every band is met.

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
        ("S1 null, Gaussian iid            false-pass <= 0.07", lambda: s1_rate("gauss", 0.0), lambda v: v <= 0.07),
        ("S1 null, t3 + volatility cluster false-pass <= 0.07", lambda: s1_rate("t3sv", 0.0), lambda v: v <= 0.07),
        ("S1 edge a=0.006 (pooled t ~ 5)   pass >= 0.70", lambda: s1_rate("gauss", 0.006), lambda v: v >= 0.70),
        ("S1 edge a=0.012 (pooled t ~ 11)  pass >= 0.95", lambda: s1_rate("gauss", 0.012), lambda v: v >= 0.95),
        ("S2 null, Gaussian                false-pass <= 0.07", lambda: s2_rate("gauss", 0.0), lambda v: v <= 0.07),
        ("S2 null, t3 + volatility cluster false-pass <= 0.07", lambda: s2_rate("t3sv", 0.0), lambda v: v <= 0.07),
        ("S2 edge a=0.003 (corr ~ -0.16)   pass >= 0.80", lambda: s2_rate("gauss", 0.003), lambda v: v >= 0.80),
    ]
    print(f"stability acceptance: {P} paths per test, R = {R} replicates{' (FULL)' if full else ' (reduced)'}", flush=True)
    ok = True
    t_start = time.time()
    for name, runner, check in tests:
        t0 = time.time()
        v = runner()
        observed.append(v)
        good = bool(check(v))
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}   observed {v:.3f}   ({time.time() - t0:.0f}s)", flush=True)
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


if __name__ == "__main__":
    sys.exit(0 if run(full="--full" in sys.argv, compare_reference="--compare-reference" in sys.argv) else 1)
