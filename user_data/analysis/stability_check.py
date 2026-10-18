"""
Amended S1/S2 stability check (Work Order 1.5 section 3; ruled on in
docs/correspondence/answer-04.md). It REPLACES the retired rule (per-block OLS z-scores,
combined Stouffer z and an opposite-block veto), which was mis-specified: on pure noise it
produced negative block slopes, a combined z near -7.6 and a veto that fired in every path
(Work Order 1.5 section 0, R3). `stability_reference.py` (mathematician) is the unambiguous
definition of the statistic; this module is the production implementation. Where the two differ
it is by the mathematician's rulings (answer-04), not by choice: global centring over the WHOLE
common origin set including the partial final block's origins, and calendar-day blocks held as
per-block index ranges (not a reshape).

DEFINITION (identical for S1 and S2 except the null generator):
  blocks   B full, non-overlapping 90-calendar-day blocks tiled from the first origin of the
           family's COMMON origin set (`formula_s1.block_structure`); the final partial block is
           dropped from the SCORES (its origins still count in the centring).
  score    c_b = d * sum_{t in block b} xt * yt, xt and yt deviations from their means over the
           WHOLE common origin set (global centring, no per-block intercept); y is the forward
           return divided by the trailing 30-day sd of daily log returns at the origin.
           d = +1 for S1 (direction positive), d = -1 for S2 (negative): positive = agrees
           with the pre-registered direction.
  null     R = 2000 replicates from the pipeline's own code path.
           S1: stationary block bootstrap of the discovery series' daily log returns (mean block
           length 20), predictor and target REBUILT from each resampled path at the same origin
           positions (`formula_s1.s1_stability`). A time-shift null is NOT valid for S1.
           S2: circular time-shift of the funding-rank vector against the target vector by a
           random offset of at least 300 settlements from zero, over the whole common origin
           set (`shift_null_scores` here).
  combine  mu_b, sd_b = mean and std of c_b over the replicates; s_b = (c_b - mu_b) / sd_b;
           T = sum_b s_b / sqrt(B); p_stab = (1 + #{replicates with T_r >= T_obs}) / (R + 1),
           T_r built from the same mu_b, sd_b.
  pass     p_stab < 0.05; then Holm across candidates per pair (R1, `registry.holm_at_step`).
  retired  the opposite-block veto (R3): at 90 origins a block has almost no power, so a veto can
           only fire by chance.

BLOCK BOUNDS. A block is the half-open position range [start, stop) over the common origin
array. Because origins are sorted by date and blocks are consecutive calendar windows, every
block is a contiguous range and the full blocks tile [0, stop_of_last_full_block); a block with
fewer than 2 origins, or ranges that are not consecutive, are refused loudly.

INTERPRETATION CHOICES (also listed in the delivery message to the mathematician):
  - `combine` follows the reference exactly (std with ddof=0, ties counted with >=).
  - A zero null standard deviation for any block raises instead of dividing by zero.
  - For S2, when fewer than R distinct allowed shifts exist, all of them are used (the reference
    does the same) and the p-value denominator is the number actually used + 1.
"""

from __future__ import annotations

import sys

import numpy as np

ALPHA = 0.05
DEFAULT_R = 2000
DEFAULT_MEAN_BLOCK = 20
DEFAULT_MIN_SHIFT = 300
BOOTSTRAP_CHUNK = 250


# ----------------------------------------------------------------------------- block bounds
def full_block_bounds(origins, structure: dict) -> list[tuple[int, int]]:
    """[(start, stop), ...] position ranges (over the common origin array `origins`) of the
    FULL blocks of `structure` (from `formula_s1.block_structure`)."""
    bounds = []
    for b in structure["blocks"]:
        if not b["is_full"]:
            continue
        members = b["origins"]
        if len(members) == 0:
            raise ValueError(f"full block {b['block_index']} has no origins")
        start = int(origins.get_loc(members[0]))
        bounds.append((start, start + len(members)))
    return bounds


def _check_bounds(bounds: list[tuple[int, int]], n_total: int) -> None:
    if not bounds:
        raise ValueError("no full blocks: the stability check needs at least one full block")
    if bounds[0][0] != 0:
        raise ValueError("the first block must start at the first origin")
    for i, (s, e) in enumerate(bounds):
        if e - s < 2:
            raise ValueError(f"block {i} has {e - s} origins (needs at least 2)")
        if i and s != bounds[i - 1][1]:
            raise ValueError("blocks must be consecutive position ranges")
    if bounds[-1][1] > n_total:
        raise ValueError("block ranges run past the origin array")


# ----------------------------------------------------------------------------- core statistic
def block_scores(x, y, bounds: list[tuple[int, int]], d: int):
    """x, y: (..., N) arrays over the WHOLE common origin set (partial block included).
    Returns (..., B) scores c_b = d * sum_{t in block b} xt*yt with xt, yt centred on their
    means over all N origins (global centring, no per-block intercept)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    _check_bounds(bounds, x.shape[-1])
    prod = (x - x.mean(-1, keepdims=True)) * (y - y.mean(-1, keepdims=True))
    starts = [s for s, _ in bounds]
    return d * np.add.reduceat(prod[..., : bounds[-1][1]], starts, axis=-1)


def combine(c_obs, c_null):
    """c_obs (B,), c_null (R, B) -> (T_obs, p_stab, s_obs)."""
    c_obs = np.asarray(c_obs, dtype=float)
    c_null = np.asarray(c_null, dtype=float)
    B = len(c_obs)
    mu, sd = c_null.mean(0), c_null.std(0)
    if (sd <= 0).any() or not np.isfinite(sd).all():
        raise ValueError("a block's null standard deviation is zero or not finite")
    s_obs = (c_obs - mu) / sd
    T_obs = s_obs.sum() / np.sqrt(B)
    T_null = ((c_null - mu) / sd).sum(1) / np.sqrt(B)
    p = (1 + (T_null >= T_obs).sum()) / (len(T_null) + 1)
    return float(T_obs), float(p), s_obs


def stationary_bootstrap_idx(R: int, T: int, mean_block: float, rng):
    """(R, T) integer indices into a length-T vector: stationary bootstrap (geometric block
    lengths with the given mean, circular wrap), as in the reference."""
    restart = rng.random((R, T)) < 1.0 / mean_block
    restart[:, 0] = True
    starts = rng.integers(0, T, (R, T))
    tt = np.arange(T)[None, :]
    base = np.maximum.accumulate(np.where(restart, tt, 0), axis=1)
    sv = np.take_along_axis(starts, base, axis=1)
    return (sv + (tt - base)) % T


def result_dict(T_obs: float, p: float, s_obs, c_obs, R: int, seed: int, extra: dict | None = None) -> dict:
    out = {
        "T": float(T_obs),
        "p_stab": float(p),
        "s_b": [float(v) for v in s_obs],
        "c_b": [float(v) for v in np.asarray(c_obs)],
        "B": len(c_obs),
        "R": int(R),
        "seed": int(seed),
        "share_blocks_positive": float(np.mean(np.asarray(s_obs) > 0)),
        "passes": bool(p < ALPHA),
    }
    if extra:
        out.update(extra)
    return out


# ----------------------------------------------------------------------------- S2 (time-shift null)
def shift_null_scores(x, y, bounds: list[tuple[int, int]], d: int, R: int, min_shift: int, seed: int):
    """Circular time-shift null over the WHOLE common origin set. x: the predictor vector (S2:
    funding rank, computed once from the real series), y: the standardised target vector, both
    length N. Returns (c_obs (B,), c_null (R_used, B)); shift k in [min_shift, N - min_shift]
    pairs x_i with y_{(i+k) mod N}; block b's score at shift k sums over the origins of block b
    only. R_used = min(R, number of allowed shifts), drawn without replacement."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    N = len(x)
    _check_bounds(bounds, N)
    xc, yc = x - x.mean(), y - y.mean()
    xb = np.zeros((len(bounds), N))
    for b, (s, e) in enumerate(bounds):
        xb[b, s:e] = xc[s:e]
    # circular cross-correlation: C[b, k] = sum_i xb[b, i] * yc[(i + k) % N]
    C = d * np.fft.irfft(np.conj(np.fft.rfft(xb, axis=1)) * np.fft.rfft(yc)[None, :], n=N, axis=1)
    allowed = np.arange(min_shift, N - min_shift + 1)
    if len(allowed) == 0:
        raise ValueError(f"no allowed shifts: N={N}, min_shift={min_shift}")
    rng = np.random.default_rng(seed)
    ks = rng.choice(allowed, size=min(R, len(allowed)), replace=False)
    return C[:, 0], C[:, ks].T


def stability_s2(rank, ystd, bounds, d: int = -1, R: int = DEFAULT_R, min_shift: int = DEFAULT_MIN_SHIFT, seed: int = 0) -> dict:
    """S2 stability check on pre-computed vectors over the whole common origin set (see
    `shift_null_scores`). Returns `result_dict` (T, p_stab, s_b, B, R used, seed, passes, ...)."""
    c_obs, c_null = shift_null_scores(rank, ystd, bounds, d, R, min_shift, seed)
    T_obs, p, s_obs = combine(c_obs, c_null)
    return result_dict(T_obs, p, s_obs, c_obs, len(c_null), seed, {"min_shift": int(min_shift)})


# ----------------------------------------------------------------------------- self-test
def _brute_scores(x, y, bounds, d):
    """The definition applied literally, with plain python loops."""
    N = len(x)
    mx, my = sum(x) / N, sum(y) / N
    return [d * sum((x[i] - mx) * (y[i] - my) for i in range(s, e)) for s, e in bounds]


if __name__ == "__main__":
    import stability_reference as ref

    rng = np.random.default_rng(7)

    # ---- block_scores == the definition by brute force; global centring includes the PARTIAL block
    N = 23
    x, y = rng.standard_normal(N), rng.standard_normal(N)
    bounds = [(0, 5), (5, 10), (10, 15)]  # origins 15..22 are the partial block: no score, but they count in the centring
    for d in (+1, -1):
        assert np.allclose(block_scores(x, y, bounds, d), _brute_scores(list(x), list(y), bounds, d), atol=1e-12)
    assert np.allclose(block_scores(x, y, bounds, -1), -block_scores(x, y, bounds, +1)), "d = -1 flips every score"
    sliced = block_scores(x[:15], y[:15], bounds, +1)  # the reference's [:B*n] centring
    assert not np.allclose(sliced, block_scores(x, y, bounds, +1)), "centring over the whole set must differ from slice centring"
    assert np.allclose(block_scores(x[:15], y[:15], bounds, +1), ref.block_scores(x[:15], y[:15], 3, 5, +1)), "no partial block: matches the reference"
    # batched (R, N) input gives the same rows
    xs, ys = rng.standard_normal((4, N)), rng.standard_normal((4, N))
    batch = block_scores(xs, ys, bounds, +1)
    assert batch.shape == (4, 3) and all(np.allclose(batch[i], block_scores(xs[i], ys[i], bounds, +1)) for i in range(4))
    # uneven blocks (a gap leaves a block with fewer origins) are handled by index ranges, not a reshape
    uneven = [(0, 4), (4, 9), (9, 12)]
    assert np.allclose(block_scores(x, y, uneven, +1), _brute_scores(list(x), list(y), uneven, +1))

    # ---- bounds validation: refuse, never guess
    for bad in ([], [(1, 5)], [(0, 1), (1, 4)], [(0, 5), (6, 10)], [(0, 5), (5, 99)]):
        try:
            block_scores(x, y, bad, +1)
        except ValueError:
            pass
        else:
            raise AssertionError(f"bounds {bad} must be refused")

    # ---- combine: by hand
    c_obs = np.array([2.0, 1.0])
    c_null = np.array([[0.0, 0.0], [1.0, 2.0], [2.0, 4.0], [3.0, 2.0]])
    mu, sd = c_null.mean(0), c_null.std(0)
    s_hand = (c_obs - mu) / sd
    T_hand = s_hand.sum() / np.sqrt(2)
    T_null_hand = [(((row - mu) / sd).sum() / np.sqrt(2)) for row in c_null]
    p_hand = (1 + sum(t >= T_hand for t in T_null_hand)) / (len(c_null) + 1)
    T_obs, p, s_obs = combine(c_obs, c_null)
    assert abs(T_obs - T_hand) < 1e-12 and abs(p - p_hand) < 1e-12 and np.allclose(s_obs, s_hand)
    big = combine(np.array([50.0, 50.0]), c_null)
    assert abs(big[1] - 1 / (len(c_null) + 1)) < 1e-12, "p_stab is bounded below by 1/(R+1)"
    low = combine(np.array([-50.0, -50.0]), c_null)
    assert low[1] == 1.0
    tied = combine(np.array([0.0, 0.0]), np.array([[0.0, 0.0], [0.0, 0.0], [1.0, 1.0], [-1.0, -1.0]]))
    assert abs(tied[1] - (1 + 3) / 5) < 1e-12, "ties count as >= (T_obs = 0 ties with two zero replicates)"
    try:
        combine(np.array([1.0, 1.0]), np.zeros((5, 2)))
    except ValueError:
        pass
    else:
        raise AssertionError("a zero null sd must raise")

    # ---- stationary bootstrap: valid indices, restart at 0, mean block length ~ requested
    bi = stationary_bootstrap_idx(2000, 1000, 20, np.random.default_rng(1))
    assert bi.shape == (2000, 1000) and bi.min() >= 0 and bi.max() < 1000
    continues = (bi[:, 1:] == (bi[:, :-1] + 1) % 1000).mean()
    assert abs((1 - continues) - 1 / 20) < 0.004, f"mean block length off: restart share {1 - continues:.4f} vs 0.05"

    # ---- S2 shift null: brute-force circular cross-correlation, partial block included
    Ns = 40
    xs2, ys2 = rng.standard_normal(Ns), rng.standard_normal(Ns)
    b2 = [(0, 10), (10, 20), (20, 30)]  # 30..39 is the partial block
    c_obs2, c_null2 = shift_null_scores(xs2, ys2, b2, -1, R=1000, min_shift=5, seed=3)
    xc2, yc2 = xs2 - xs2.mean(), ys2 - ys2.mean()
    def brute_shift(k):
        return [-sum(xc2[i] * yc2[(i + k) % Ns] for i in range(s, e)) for s, e in b2]
    assert np.allclose(c_obs2, brute_shift(0), atol=1e-10)
    allowed = np.arange(5, Ns - 5 + 1)
    assert len(c_null2) == len(allowed), "fewer allowed shifts than R: all are used, once each"
    got = sorted(map(tuple, np.round(c_null2, 9)))
    want = sorted(tuple(np.round(brute_shift(k), 9)) for k in allowed)
    assert np.allclose(got, want, atol=1e-8), "every allowed shift must appear exactly once and match brute force"
    assert np.allclose(c_obs2, brute_shift(0)) and len(c_null2) == 31
    try:
        shift_null_scores(xs2, ys2, b2, -1, R=10, min_shift=25, seed=1)
    except ValueError:
        pass
    else:
        raise AssertionError("no allowed shifts must raise")

    # ---- production == the reference where the two definitions coincide (no partial block, same seed)
    # (S1's equivalence with the reference is checked in formula_s1.py, which owns the S1 hooks.)
    xr, yr = ref.sim_s2(np.random.default_rng(5), 2, 6, 270, "gauss", 0.003)
    for i in range(2):
        want_T, want_p, want_s, want_c = ref.stability_s2(xr[i], yr[i], 6, 270, -1, R=200, seed=i)
        got = stability_s2(xr[i], yr[i], [(b * 270, (b + 1) * 270) for b in range(6)], -1, R=200, seed=i)
        assert abs(got["T"] - want_T) < 1e-9 and abs(got["p_stab"] - want_p) < 1e-12
        assert np.allclose(got["s_b"], want_s) and np.allclose(got["c_b"], want_c)
    assert stability_s2(xr[0], yr[0], [(b * 270, (b + 1) * 270) for b in range(6)], -1, R=200, seed=4) == \
        stability_s2(xr[0], yr[0], [(b * 270, (b + 1) * 270) for b in range(6)], -1, R=200, seed=4), "deterministic given the seed"

    print(
        "Self-test passed: block scores equal the definition by brute force (global centring over the whole "
        "origin set including the partial block; d=-1 flips; uneven blocks by index range); bounds that are "
        "empty, short, non-consecutive or out of range are refused; combine matches a by-hand T and p_stab "
        "(+1 in numerator and denominator, bounded below by 1/(R+1)) and refuses a zero null sd; the stationary "
        "bootstrap has the requested mean block length; the S2 time-shift null equals a brute-force circular "
        "cross-correlation over every allowed shift, partial block included; and the S2 production statistic "
        "reproduces the mathematician's reference exactly (same seed) where the definitions coincide."
    )
