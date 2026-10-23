# M2 sandbox calibration record, 2026-10-20

SANDBOX ONLY. Nothing here was run on the owner's machine and nothing here is "verified" in the PROTOCOL sense. It is the evidence
behind two things M2 ruled before any S2 result existed (see `docs/correspondence/answer-s2-rulings.md` and NOTES section 7):
the S2 discovery test uses HAC lags of 12 (24h cell) and 36 (72h cell) instead of 3 and 9, and the S2 stability check's power
statements. It is also the reference for D2's own persistent-null self-test on the production code, which is the real check.

Environment: Python 3.12.3, numpy 2.4.4, scipy 1.17.1; seeds fixed in the scripts, so the logs below reproduce exactly. Files:
`s2_sim.py` (size and power), `extra_sim.py` (24h-cell bandwidth and an S1-like check; imports `s2_sim.py`), `hac_size.py`
(preliminary size grid with the simulated rank autocorrelations). Run: `python3 s2_sim.py size`, `python3 s2_sim.py power`,
`python3 extra_sim.py`, `python3 hac_size.py 1000`.

## What was simulated

- Funding-like latent series z: AR(1) with persistence phi per 8h settlement (0.9, 0.98, 0.995), optionally with about 40% of values
  tied at the low end (as in the real series: tie share 39.6% ETH, 40.1% BTC), rank = rolling mid-rank over the 270 previous values
  (the production definition). Simulated rank autocorrelation: lag 1 between 0.85 and 0.98, lag 9 between 0.3 and 0.87.
- 8h returns: iid Gaussian, or t(4) shocks with persistent log-volatility ("sv"). 24h and 72h forward returns are sums of the next 3
  and 9 returns (overlapping origins every 8h). 6,000 origins per path.
- Null: funding independent of returns (a second variant lets funding innovations load on the contemporaneous return: kappa = 0.5).
- Alternative: the return in the 8h after settlement s-1 loads on (rank_{s-1} - 0.5), scaled to hit a target correlation between the
  rank and the 72h forward return.
- Tests (one-sided negative, nominal 5%): Newey-West Bartlett HAC t with 9, 18, 36 lags ("hac9" ...), the flat-kernel
  Hansen-Hodrick estimator with 8 lags ("hh8"), the circular-shift test of the slope ("shift", 300 draws), and the S2 stability
  statistic of Work Order 1.5 section 3 on the 72h cell, 22 full blocks of 270, R = 300 ("stab").

## Findings

1. Size (500 paths per row; Monte Carlo SE about 1 point). With a persistent rank the 9-lag HAC test over-rejects: 6.6-8.6% at
   nominal 5%; 18 lags 5.0-6.6%; 36 lags 4.6-6.4%; the shift test 4.4-5.8% and the stability check 3.6-5.8% are calibrated.
   Mechanism: the Bartlett taper at a bandwidth close to the overlap length under-estimates the long-run variance when the regressor
   is nearly constant over the overlap window (sd of the t statistic about 1.15-1.2 instead of 1).
2. The 24h cell is harder: 8.1-8.6% with 3 lags, 6.8-7.2% with 6, 6.5-7.0% with 12, 6.2-7.0% with 24. It is exploratory.
3. S1 (daily trend, 10 lags for the 5-day overlap) is fine: 5.0% in an S1-like simulation (random walk with t(4) shocks and
   volatility clustering, 40-day trend predictor, 2,772 origins); 5 lags would have read 6.5%. S1's p-values stand.
4. Power of the S2 stability check (300 paths per row; SE about 3 points near 50%): 18-25% at a realised correlation of -0.03,
   61-79% at -0.07 to -0.09, 99-100% at -0.16. M1's statement "roughly 20% to 70%" holds.
5. The discovery test with 36 lags loses only a few points of power against the 9-lag version (for example 19.7% against 26.0% at
   -0.03, but the 9-lag number includes its excess false positives).

## Logs

### s2_sim.py size
```
SIZE phi=0.9 ties=1 sv=0       rho_target=+0.00 realized=+0.001 | reject@5%: hac9= 8.6% hac18= 6.6% hac36= 6.2% hh8= 5.4% shift= 5.2% stab= 5.4%
SIZE phi=0.98 ties=1 sv=0      rho_target=+0.00 realized=+0.002 | reject@5%: hac9= 8.6% hac18= 6.6% hac36= 6.4% hh8= 5.8% shift= 5.8% stab= 5.8%
SIZE phi=0.995 ties=1 sv=0     rho_target=+0.00 realized=+0.002 | reject@5%: hac9= 6.6% hac18= 5.0% hac36= 4.6% hh8= 3.8% shift= 5.2% stab= 5.4%
SIZE phi=0.98 ties=0 sv=0      rho_target=+0.00 realized=-0.000 | reject@5%: hac9= 7.0% hac18= 5.6% hac36= 5.0% hh8= 3.8% shift= 4.4% stab= 3.6%
SIZE phi=0.98 ties=1 sv=1      rho_target=+0.00 realized=+0.000 | reject@5%: hac9= 8.0% hac18= 6.0% hac36= 5.6% hh8= 5.0% shift= 4.6% stab= 3.6%
SIZE phi=0.995 ties=1 sv=1     rho_target=+0.00 realized=+0.003 | reject@5%: hac9= 7.6% hac18= 6.4% hac36= 5.0% hh8= 3.8% shift= 4.4% stab= 5.0%
elapsed 62.5 s
```

### s2_sim.py power
```
POWER phi=0.98 ties=1 sv=0     rho_target=-0.03 realized=-0.025 | reject@5%: hac9=26.0% hac18=21.3% hac36=19.7% hh8=17.7% shift=17.0% stab=18.0%
POWER phi=0.98 ties=1 sv=0     rho_target=-0.08 realized=-0.094 | reject@5%: hac9=87.7% hac18=87.0% hac36=86.3% hh8=83.7% shift=81.7% stab=78.7%
POWER phi=0.98 ties=1 sv=0     rho_target=-0.16 realized=-0.157 | reject@5%: hac9=99.7% hac18=99.3% hac36=99.3% hh8=99.3% shift=99.3% stab=99.0%
POWER phi=0.98 ties=1 sv=1     rho_target=-0.03 realized=-0.036 | reject@5%: hac9=35.3% hac18=31.0% hac36=28.0% hh8=26.0% shift=24.7% stab=25.0%
POWER phi=0.98 ties=1 sv=1     rho_target=-0.08 realized=-0.072 | reject@5%: hac9=74.0% hac18=71.0% hac36=66.7% hh8=63.3% shift=61.0% stab=61.3%
POWER phi=0.98 ties=1 sv=1     rho_target=-0.16 realized=-0.171 | reject@5%: hac9=100.0% hac18=100.0% hac36=100.0% hh8=100.0% shift=100.0% stab=100.0%
elapsed 32.5 s
```

### extra_sim.py
```
24h cell phi=0.98 ties=1 sv=0: L=3:  8.1% L=6:  6.8% L=12:  6.5% L=24:  6.2%
24h cell phi=0.995 ties=1 sv=0: L=3:  8.2% L=6:  7.2% L=12:  6.8% L=24:  6.4%
24h cell phi=0.98 ties=1 sv=1: L=3:  8.6% L=6:  7.2% L=12:  7.0% L=24:  7.0%
S1-like h=5 (positive one-sided 5%): L=10:  5.0% L=5:  6.5% L=20:  4.4% L=40:  4.2%
S1-like h=1: L=5:  3.4% L=10:  3.3%
elapsed 31.5 s
```

### hac_size.py 1000
```
phi=0.0    kappa=0.0  ties=False rank AC(1)=-0.014 AC(9)=-0.003 | 24h L=3:  3.9% 72h L=9:  4.9% 72h L=18:  5.0% 72h L=40:  5.4% 72h HH L=8:  5.4% | sd(t72,L9)=0.99
phi=0.9    kappa=0.0  ties=False rank AC(1)=0.885 AC(9)=0.346 | 24h L=3:  8.1% 72h L=9:  9.0% 72h L=18:  7.3% 72h L=40:  6.6% 72h HH L=8:  5.7% | sd(t72,L9)=1.13
phi=0.98   kappa=0.0  ties=False rank AC(1)=0.967 AC(9)=0.770 | 24h L=3:  4.9% 72h L=9:  6.3% 72h L=18:  4.4% 72h L=40:  3.9% 72h HH L=8:  3.0% | sd(t72,L9)=1.16
phi=0.995  kappa=0.0  ties=False rank AC(1)=0.982 AC(9)=0.873 | 24h L=3:  6.6% 72h L=9:  7.3% 72h L=18:  5.9% 72h L=40:  5.1% 72h HH L=8:  4.2% | sd(t72,L9)=1.20
phi=0.0    kappa=0.5  ties=False rank AC(1)=0.014 AC(9)=0.002 | 24h L=3:  5.9% 72h L=9:  6.2% 72h L=18:  6.3% 72h L=40:  6.3% 72h HH L=8:  6.4% | sd(t72,L9)=1.02
phi=0.9    kappa=0.5  ties=False rank AC(1)=0.884 AC(9)=0.353 | 24h L=3:  7.1% 72h L=9:  7.6% 72h L=18:  6.0% 72h L=40:  5.2% 72h HH L=8:  4.5% | sd(t72,L9)=1.18
phi=0.98   kappa=0.5  ties=False rank AC(1)=0.965 AC(9)=0.750 | 24h L=3:  6.2% 72h L=9:  7.7% 72h L=18:  5.8% 72h L=40:  5.1% 72h HH L=8:  4.4% | sd(t72,L9)=1.18
phi=0.995  kappa=0.5  ties=False rank AC(1)=0.980 AC(9)=0.849 | 24h L=3:  8.8% 72h L=9:  8.9% 72h L=18:  7.1% 72h L=40:  6.0% 72h HH L=8:  5.5% | sd(t72,L9)=1.22
phi=0.0    kappa=0.0  ties=True  rank AC(1)=0.012 AC(9)=0.006 | 24h L=3:  6.4% 72h L=9:  5.9% 72h L=18:  5.7% 72h L=40:  5.5% 72h HH L=8:  6.0% | sd(t72,L9)=1.02
phi=0.9    kappa=0.0  ties=True  rank AC(1)=0.851 AC(9)=0.343 | 24h L=3:  7.1% 72h L=9:  7.1% 72h L=18:  6.0% 72h L=40:  5.6% 72h HH L=8:  4.9% | sd(t72,L9)=1.17
phi=0.98   kappa=0.0  ties=True  rank AC(1)=0.945 AC(9)=0.705 | 24h L=3:  7.2% 72h L=9:  8.5% 72h L=18:  7.2% 72h L=40:  6.5% 72h HH L=8:  6.0% | sd(t72,L9)=1.20
phi=0.995  kappa=0.0  ties=True  rank AC(1)=0.974 AC(9)=0.856 | 24h L=3:  5.2% 72h L=9:  5.9% 72h L=18:  4.6% 72h L=40:  4.2% 72h HH L=8:  3.7% | sd(t72,L9)=1.16
phi=0.0    kappa=0.5  ties=True  rank AC(1)=0.003 AC(9)=0.003 | 24h L=3:  5.3% 72h L=9:  5.3% 72h L=18:  5.4% 72h L=40:  5.7% 72h HH L=8:  5.5% | sd(t72,L9)=1.00
phi=0.9    kappa=0.5  ties=True  rank AC(1)=0.847 AC(9)=0.307 | 24h L=3:  6.6% 72h L=9:  7.6% 72h L=18:  6.6% 72h L=40:  6.2% 72h HH L=8:  5.9% | sd(t72,L9)=1.15
phi=0.98   kappa=0.5  ties=True  rank AC(1)=0.939 AC(9)=0.706 | 24h L=3:  7.1% 72h L=9:  8.3% 72h L=18:  6.8% 72h L=40:  5.9% 72h HH L=8:  5.1% | sd(t72,L9)=1.17
phi=0.995  kappa=0.5  ties=True  rank AC(1)=0.970 AC(9)=0.835 | 24h L=3:  7.9% 72h L=9:  9.2% 72h L=18:  6.9% 72h L=40:  6.6% 72h HH L=8:  5.6% | sd(t72,L9)=1.19
elapsed 75.0 s
```

## Sources

### s2_sim.py
```python
# SANDBOX ONLY. S2 discovery-test calibration/power and stability-test power under a persistent funding-rank predictor.
import numpy as np, sys, time
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import lfilter
rng = np.random.default_rng(777)
W = 270

def midrank(z):
    win = sliding_window_view(z[:-1], W); cur = z[W:]
    return ((win < cur[:, None]).sum(1) + 0.5 * (win == cur[:, None]).sum(1)) / W

def nw(x, y, L, flat=False):
    xc = x - x.mean(); yc = y - y.mean(); sxx = (xc * xc).sum(); b = (xc * yc).sum() / sxx
    s = xc * (yc - b * xc); om = (s * s).sum()
    for k in range(1, L + 1):
        om += 2 * (1.0 if flat else 1 - k / (L + 1)) * (s[k:] * s[:-k]).sum()
    v = om / sxx ** 2
    return b, (b / np.sqrt(v) if v > 0 else 0.0)

def simulate(N, phi, ties, c=0.0, sv=False, kappa=0.0):
    T = N + W + 14
    if sv:   # t(4) shocks with persistent log-volatility
        h = lfilter([1.0], [1.0, -0.98], rng.standard_normal(T) * np.sqrt(1 - 0.98 ** 2) * 0.6)
        xi = rng.standard_t(4, T) / np.sqrt(2.0)
        eps = np.exp(h / 2) * xi
    else:
        eps = rng.standard_normal(T)
    inn = rng.standard_normal(T) * np.sqrt(1 - phi ** 2) + kappa * eps
    z = lfilter([1.0], [1.0, -phi], inn)
    if ties: z = np.maximum(z, np.quantile(z, 0.40))
    xr = midrank(z)                         # xr[i] is the rank at index W+i
    xfull = np.full(T, 0.5); xfull[W:] = xr
    r = eps.copy()
    if c != 0.0:                             # return over the 8h after settlement s-1 depends on rank at s-1
        r[W + 1:] = eps[W + 1:] - c * (xfull[W:-1] - 0.5)
    cs = np.concatenate([[0], np.cumsum(r)]); idx = np.arange(W, W + N)
    return xfull[idx], cs[idx + 4] - cs[idx + 1], cs[idx + 10] - cs[idx + 1], (cs[idx + 10] - cs[idx + 1])

def shift_tests(x, y, R, B, n=270, kmin=300, rng_=None):
    N = len(x); xc = x - x.mean(); yc = y - y.mean(); sxx = (xc * xc).sum()
    ks = rng_.integers(kmin, N - kmin + 1, R)
    idx = (np.arange(N)[None, :] - ks[:, None]) % N
    Xs = xc[idx]                                    # (R,N) shifted rank vector
    slope_obs = (xc * yc).sum() / sxx; slope_r = Xs @ yc / sxx
    p_slope = (1 + (slope_r <= slope_obs).sum()) / (R + 1)       # one-sided negative
    m = B * n
    cb_obs = -(xc[:m] * yc[:m]).reshape(B, n).sum(1)
    cb_r = -(Xs[:, :m] * yc[None, :m]).reshape(R, B, n).sum(2)
    mu = cb_r.mean(0); sd = cb_r.std(0)
    T_obs = ((cb_obs - mu) / sd).sum() / np.sqrt(B); T_r = ((cb_r - mu) / sd).sum(1) / np.sqrt(B)
    p_stab = (1 + (T_r >= T_obs).sum()) / (R + 1)
    return p_slope, p_stab

def study(label, phi, ties, rho_list, npaths, N=6000, R=300, sv=False, kappa=0.0):
    # calibrate c for each target correlation with a pilot
    out = []
    for rho in rho_list:
        c = 0.0
        if rho != 0.0:
            c = 0.01
            for _ in range(4):
                xp, _, yp, _ = simulate(120000, phi, ties, c, sv, kappa); cur = np.corrcoef(xp, yp)[0, 1]
                c *= (rho / cur) if cur != 0 else 1
            xp, _, yp, _ = simulate(120000, phi, ties, c, sv, kappa); cur = np.corrcoef(xp, yp)[0, 1]
        cnt = dict(hac9=0, hac18=0, hac36=0, hh8=0, shift=0, stab=0, any2=0); corrs = []
        B = N // 270
        for _ in range(npaths):
            x, y24, y72, _ = simulate(N, phi, ties, c, sv, kappa)
            corrs.append(np.corrcoef(x, y72)[0, 1])
            for nm, L, flat in (("hac9", 9, False), ("hac18", 18, False), ("hac36", 36, False), ("hh8", 8, True)):
                _, t = nw(x, y72, L, flat); cnt[nm] += t < -1.645
            ps, pt = shift_tests(x, y72, R, B, rng_=rng); cnt["shift"] += ps < 0.05; cnt["stab"] += pt < 0.05
        print(f"{label:<30} rho_target={rho:+.2f} realized={np.mean(corrs):+.3f} | reject@5%: " +
              " ".join(f"{k}={v/npaths:5.1%}" for k, v in cnt.items() if k != 'any2'), flush=True)

if __name__ == "__main__":
    mode = sys.argv[1]
    t0 = time.time()
    if mode == "size":
        for (phi, ties, sv) in ((0.9, True, False), (0.98, True, False), (0.995, True, False), (0.98, False, False), (0.98, True, True), (0.995, True, True)):
            study(f"SIZE phi={phi} ties={int(ties)} sv={int(sv)}", phi, ties, [0.0], 500, sv=sv)
    else:
        for (phi, ties, sv) in ((0.98, True, False), (0.98, True, True)):
            study(f"POWER phi={phi} ties={int(ties)} sv={int(sv)}", phi, ties, [-0.03, -0.08, -0.16], 300, sv=sv)
    print("elapsed", round(time.time() - t0, 1), "s")
```

### extra_sim.py
```python
# SANDBOX ONLY. (1) 24h-cell HAC bandwidth check on the S2 design; (2) S1-like size check (persistent 40-day trend predictor, 5-day overlap).
import numpy as np, time
from scipy.signal import lfilter
import s2_sim as S
rng = np.random.default_rng(4242)
t0 = time.time()
# (1) 24h cell: rank predictor persistent, 3-step overlap
for (phi, ties, sv) in ((0.98, True, False), (0.995, True, False), (0.98, True, True)):
    cnt = {L: 0 for L in (3, 6, 12, 24)}; n = 800
    for _ in range(n):
        x, y24, y72, _ = S.simulate(6000, phi, ties, 0.0, sv)
        for L in cnt:
            _, t = S.nw(x, y24, L); cnt[L] += t < -1.645
    print(f"24h cell phi={phi} ties={int(ties)} sv={int(sv)}: " + " ".join(f"L={L}: {v/n:5.1%}" for L, v in cnt.items()), flush=True)
# (2) S1-like
def s1_path(N=2772):
    T = N + 160 + 40
    h = lfilter([1.0], [1.0, -0.98], rng.standard_normal(T) * np.sqrt(1 - 0.98 ** 2) * 0.6)
    r = np.exp(h / 2) * rng.standard_t(4, T) / np.sqrt(2.0) * 0.03
    lc = np.cumsum(r)
    out = []
    t = np.arange(160, 160 + N)
    r_s = r
    sig = np.array([r_s[i - 29:i + 1].std(ddof=1) for i in t])
    x = (lc[t] - lc[t - 40]) / sig
    y1 = lc[t + 1] - lc[t]; y5 = lc[t + 5] - lc[t]
    return x, y1, y5
n = 1000; c5 = {10: 0, 5: 0, 20: 0, 40: 0}; c1 = {5: 0, 10: 0}
for _ in range(n):
    x, y1, y5 = s1_path()
    for L in c5:
        _, t = S.nw(x, y5, L); c5[L] += t > 1.645
    for L in c1:
        _, t = S.nw(x, y1, L); c1[L] += t > 1.645
print("S1-like h=5 (positive one-sided 5%): " + " ".join(f"L={L}: {v/n:5.1%}" for L, v in c5.items()))
print("S1-like h=1: " + " ".join(f"L={L}: {v/n:5.1%}" for L, v in c1.items()))
print("elapsed", round(time.time() - t0, 1), "s")
```

### hac_size.py
```python
# SANDBOX ONLY. Size of the pre-registered S2 discovery test (OLS slope of forward return on rank, Newey-West Bartlett HAC)
# under the null, with a persistent funding predictor and overlapping forward returns (8h grid; 24h = 3 steps, 72h = 9 steps).
import numpy as np, sys, time
from numpy.lib.stride_tricks import sliding_window_view
rng = np.random.default_rng(20261020)
W = 270

def midrank(z):
    win = sliding_window_view(z[:-1], W)
    cur = z[W:]
    below = (win < cur[:, None]).sum(1)
    tied = (win == cur[:, None]).sum(1)
    return (below + 0.5 * tied) / W

def nw(x, y, L, kernel="bartlett"):
    xc = x - x.mean(); yc = y - y.mean()
    sxx = (xc * xc).sum(); b = (xc * yc).sum() / sxx
    u = yc - b * xc; s = xc * u
    om = (s * s).sum()
    for k in range(1, L + 1):
        w = (1 - k / (L + 1)) if kernel == "bartlett" else 1.0
        om += 2 * w * (s[k:] * s[:-k]).sum()
    var = om / sxx ** 2
    return b, b / np.sqrt(var) if var > 0 else np.nan

def one_path(N, phi, kappa, ties=False):
    T = N + W + 12
    eps = rng.standard_normal(T)
    eta = rng.standard_normal(T)
    from scipy.signal import lfilter
    inn = eta * np.sqrt(1 - phi ** 2) + kappa * eps
    z = lfilter([1.0], [1.0, -phi], inn)
    if ties:   # ~40% of observations tied at a baseline value (the low end), as in the real funding series
        z = np.maximum(z, np.quantile(z, 0.40))
    x = midrank(z)[:N]                     # rank at origin t (t = W..W+N-1)
    cs = np.concatenate([[0], np.cumsum(eps)])
    idx = np.arange(W, W + N)              # origin index in eps/z arrays
    y72 = cs[idx + 10] - cs[idx + 1]       # eps[t+1..t+9]
    y24 = cs[idx + 4] - cs[idx + 1]        # eps[t+1..t+3]
    return x, y24, y72

def run(phi, kappa, npaths, N=6000, ties=False):
    rej = {k: 0 for k in ("24h L=3", "72h L=9", "72h L=18", "72h L=40", "72h HH L=8")}
    tvals = []; ac1 = []; ac9 = []
    for _ in range(npaths):
        x, y24, y72 = one_path(N, phi, kappa, ties)
        if _ < 3:
            xc = x - x.mean(); ac1.append((xc[1:] * xc[:-1]).sum() / (xc * xc).sum()); ac9.append((xc[9:] * xc[:-9]).sum() / (xc * xc).sum())
        _, t = nw(x, y24, 3); rej["24h L=3"] += t < -1.645
        _, t = nw(x, y72, 9); rej["72h L=9"] += t < -1.645; tvals.append(t)
        _, t = nw(x, y72, 18); rej["72h L=18"] += t < -1.645
        _, t = nw(x, y72, 40); rej["72h L=40"] += t < -1.645
        _, t = nw(x, y72, 8, "flat"); rej["72h HH L=8"] += t < -1.645
    n = npaths
    tv = np.array(tvals)
    print(f"phi={phi:<6} kappa={kappa:<4} ties={ties!s:<5} rank AC(1)={np.mean(ac1):.3f} AC(9)={np.mean(ac9):.3f} | " +
          " ".join(f"{k}: {v/n:5.1%}" for k, v in rej.items()) + f" | sd(t72,L9)={tv.std():.2f}", flush=True)

if __name__ == "__main__":
    npaths = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    t0 = time.time()
    for ties in (False, True):
        for kappa in (0.0, 0.5):
            for phi in (0.0, 0.9, 0.98, 0.995):
                run(phi, kappa, npaths, ties=ties)
    print("elapsed", round(time.time() - t0, 1), "s")
```
