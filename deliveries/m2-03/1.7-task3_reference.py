#!/usr/bin/env python3
"""
Work Order 1.7 reference for Task 3 (shock_response).  M2, 2026-10-20.

SANDBOX-ONLY reference.  It defines the event rules and statistics by example, generates the synthetic series used by the
acceptance tests, and reproduces the reference results quoted in Work Order 1.7.  It is NOT production code, it never reads
project data and it never touches the registry.  The production code must reproduce its outputs (see Work Order 1.7 section 4).

Usage:
  python3 1.7-task3_reference.py --selfcheck        vectorised event clock against a brute-force loop (seconds)
  python3 1.7-task3_reference.py --one-series SEED  prints the reference numbers of one seeded t4+SV series (for exact comparison)
  python3 1.7-task3_reference.py --reduced          acceptance rates, 60 paths per null and 30 per edge row
  python3 1.7-task3_reference.py --full             200 paths per row (the real acceptance run)
  python3 1.7-task3_reference.py --null N          null rows only, N paths each
  python3 1.7-task3_reference.py --edge N          injected-edge rows only, N paths each
  python3 1.7-task3_reference.py --confirm N        N-path confirmation of the null rows only (use N >= 1000)

Conventions (gap-free synthetic series; production must add gap masking as the work order says):
  bar j has open O[j] = C[j-1] and close C[j]; return r[j] = ln(C[j]/C[j-1]), r[0] undefined (set to 0 and never used).
  z[j] = r[j] / sd(r[j-288..j-1]) (ddof=1), first usable j = 289.  Event: |z[j]| >= 3.
  Shared clock: keep the first event, then the first event at j' >= j+13; both sides share the clock.
  Target R_k(j) = ln(C[j+k] / O[j+1]) = r[j+1] + ... + r[j+k], k = 1..12.  Origins: j = 289 .. n-1-12.
  mu_k = mean of R_k over all origins.  Excess e = R_k - mu_k.  Cluster = UTC day of the entry bar j+1 (288 bars per day).
"""
import sys
import numpy as np
from scipy.signal import lfilter
from scipy.stats import norm

BAR_DAY = 288
W = 288
KMAX = 12
GAP = 13
THR = 3.0
M = 0.0035
BLOCK_BARS = 90 * BAR_DAY
NMIN_BLOCK = 30
NDAYS = 2935            # discovery length used in the reference (2017-08-18 .. 2025-08-31 at 5m is about this long)

KINDS = {
    "gauss": dict(sigma5=0.0028, phi=0.9985, vlv=1e-9, tdf=200, seasonal=False),
    "t4sv":  dict(sigma5=0.0028, phi=0.9985, vlv=0.045, tdf=4, seasonal=True),
    "t3sv":  dict(sigma5=0.0028, phi=0.9985, vlv=0.07, tdf=3, seasonal=True),
}


def make_returns(nbars, rng, kind="t4sv"):
    p = KINDS[kind]
    h = lfilter([1.0], [1.0, -p["phi"]], rng.standard_normal(nbars) * p["vlv"])
    h = h - 0.5 * h.var()
    xi = rng.standard_t(p["tdf"], nbars) / np.sqrt(p["tdf"] / (p["tdf"] - 2.0))
    if p["seasonal"]:
        slot = np.arange(nbars) % BAR_DAY
        s = 1.0 + 0.30 * np.sin(2 * np.pi * (slot - 90) / BAR_DAY) + 0.25 * np.exp(-0.5 * ((slot - 150) / 12.0) ** 2)
        s = s / np.sqrt(np.mean(s ** 2))
    else:
        s = 1.0
    r = p["sigma5"] * np.exp(h / 2) * s * xi
    r[0] = 0.0
    return r


def closes_opens(r):
    C = np.exp(np.cumsum(r))
    O = np.empty_like(C); O[0] = C[0]; O[1:] = C[:-1]
    return C, O


def z_scores(r, w=W):
    n = len(r); j = np.arange(w + 1, n)
    cs1 = np.concatenate([[0.0], np.cumsum(r)]); cs2 = np.concatenate([[0.0], np.cumsum(r * r)])
    S1 = cs1[j] - cs1[j - w]; S2 = cs2[j] - cs2[j - w]
    var = np.maximum((S2 - S1 * S1 / w) / (w - 1), 0.0)
    sd = np.sqrt(var)
    z = np.where(sd > 0, r[j] / np.where(sd > 0, sd, 1.0), 0.0)
    return j, z


def event_clock(r, thr=THR, gap=GAP, w=W):
    """Shared clock.  Uses only information available at the event bar (past returns and the bar's own return)."""
    j, z = z_scores(r, w)
    m = np.abs(z) >= thr
    kept, side, last = [], [], -10 ** 12
    for c, zz in zip(j[m], z[m]):
        if c >= last + gap:
            kept.append(int(c)); side.append(1 if zz > 0 else -1); last = int(c)
    return np.array(kept, dtype=int), np.array(side, dtype=int)


def event_clock_bruteforce(r, thr=THR, gap=GAP, w=W):
    kept, side, last = [], [], -10 ** 12
    for c in range(w + 1, len(r)):
        sd = np.std(r[c - w:c], ddof=1)
        if sd <= 0:
            continue
        z = r[c] / sd
        if abs(z) >= thr and c >= last + gap:
            kept.append(c); side.append(1 if z > 0 else -1); last = c
    return np.array(kept, dtype=int), np.array(side, dtype=int)


def origins(n, w=W, kmax=KMAX):
    return np.arange(w + 1, n - kmax)           # j with r[j-288..j] defined and bars j+1..j+12 present


def target_sums(r, j, k):
    cs = np.concatenate([[0.0], np.cumsum(r)])
    return cs[j + 1 + k] - cs[j + 1]            # r[j+1] + ... + r[j+k]


def cell_stats(e, entry_idx):
    n = len(e); mean = e.mean(); sd = e.std(ddof=1)
    day = entry_idx // BAR_DAY
    _, inv = np.unique(day, return_inverse=True)
    cl = np.bincount(inv, weights=e - mean)
    se_cl = np.sqrt((cl ** 2).sum()) / n
    se_naive = sd / np.sqrt(n)
    t = mean / se_cl
    return dict(n=n, mean=mean, sd=sd, se=se_cl, se_naive=se_naive, t=t, p_one=1 - norm.cdf(t), p_two=2 * (1 - norm.cdf(abs(t))),
                mde=2.486 * se_cl, upper95=mean + 1.645 * se_cl)


def classify(st, holm_p, m=M):
    if holm_p < 0.05 and st["mean"] >= m:
        return "pass"
    if st["upper95"] < m and st["mde"] <= m:
        return "dead"
    return "inconclusive"


def block_T(e, entry_idx, first_entry, last_entry):
    nblk = (last_entry - first_entry + 1) // BLOCK_BARS
    blk = (entry_idx - first_entry) // BLOCK_BARS
    ts = []
    for b in range(nblk):
        eb = e[blk == b]
        if len(eb) >= NMIN_BLOCK:
            ts.append(eb.mean() / (eb.std(ddof=1) / np.sqrt(len(eb))))
    if not ts:
        return dict(T=np.nan, p=np.nan, B=0, B_full=nblk, ts=ts)
    T = float(np.sum(ts) / np.sqrt(len(ts)))
    return dict(T=T, p=1 - norm.cdf(T), B=len(ts), B_full=nblk, ts=ts)


def inject(r, kept, side, which, delta, k=6):
    """Add delta in total, spread equally, over bars j+1..j+k after every kept event of the given side (kept found on the un-injected series)."""
    r2 = r.copy()
    for j, s in zip(kept, side):
        if s == which and j + k < len(r2):
            r2[j + 1:j + 1 + k] += delta / k
    return r2


def primary_results(r, kept=None, side=None, k=6, thr=THR):
    """Both primary cells (down, up) on a gap-free series: stats, classification (Holm over the two cells only, a stand-in), block T."""
    n = len(r)
    if kept is None:
        kept, side = event_clock(r, thr)
    orig = origins(n)
    mu = target_sums(r, orig, k).mean()
    ok = kept + KMAX < n
    kept, side = kept[ok], side[ok]
    e_all = target_sums(r, kept, k) - mu
    first_entry, last_entry = orig[0] + 1, orig[-1] + 1
    out = {}
    for nm, which in (("down", -1), ("up", 1)):
        msk = side == which
        st = cell_stats(e_all[msk], kept[msk] + 1)
        bt = block_T(e_all[msk], kept[msk] + 1, first_entry, last_entry)
        out[nm] = dict(stats=st, block=bt)
    # Holm over the two primary cells (the reference's stand-in for the family of 48)
    ps = np.array([out["down"]["stats"]["p_one"], out["up"]["stats"]["p_one"]])
    order = np.argsort(ps); adj = np.empty(2); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (2 - rank) * ps[i])); adj[i] = run
    for i, nm in enumerate(("down", "up")):
        out[nm]["holm"] = adj[i]
        out[nm]["class"] = classify(out[nm]["stats"], adj[i])
    out["mu"] = mu
    out["n_events"] = dict(down=int((side == -1).sum()), up=int((side == 1).sum()))
    return out


def dose_response(r, k=6):
    res = {}
    for thr in (3.0, 4.0):
        res[thr] = primary_results(r, thr=thr, k=k)
    return res


def selfcheck():
    rng = np.random.default_rng(5)
    r = make_returns(30000, rng, "t4sv")
    a = event_clock(r); b = event_clock_bruteforce(r)
    ok = np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
    print("event clock vectorised == brute force:", ok, "| kept events:", len(a[0]))
    gaps = np.diff(a[0]); print("minimum spacing between kept events:", gaps.min(), "(must be >= 13)")
    assert ok and gaps.min() >= 13
    print("selfcheck OK")


def one_series(seed, kind="t4sv"):
    rng = np.random.default_rng(seed)
    r = make_returns(NDAYS * BAR_DAY, rng, kind)
    res = primary_results(r)
    dr = dose_response(r)
    print(f"seed {seed} kind {kind} bars {len(r)}")
    print("kept events (down, up):", res["n_events"]["down"], res["n_events"]["up"], "| mu_6 = %.10f" % res["mu"])
    for nm in ("down", "up"):
        st = res[nm]["stats"]; bt = res[nm]["block"]
        print(f"{nm:<4} n={st['n']} mean={st['mean']:.10f} se_cluster={st['se']:.10f} se_naive={st['se_naive']:.10f} t={st['t']:.6f} "
              f"p_one={st['p_one']:.6g} class={res[nm]['class']} | blocks B={bt['B']} of {bt['B_full']} T={bt['T']:.6f} p_stab={bt['p']:.6g}")
    for nm in ("down", "up"):
        print(f"dose-response {nm}: |z|>=3 mean={dr[3.0][nm]['stats']['mean']:.8f} (n={dr[3.0][nm]['stats']['n']})  "
              f"|z|>=4 mean={dr[4.0][nm]['stats']['mean']:.8f} (n={dr[4.0][nm]['stats']['n']})")


def acceptance(npaths_null, npaths_edge, seed=1707):
    rng = np.random.default_rng(seed)
    n = NDAYS * BAR_DAY
    print(f"Acceptance rates (one-sided 5%, cluster SE), {npaths_null} null paths and {npaths_edge} edge paths per row")
    for kind in (("gauss", "t4sv", "t3sv") if npaths_null else ()):
        c = dict(down=[0, 0, 0], up=[0, 0, 0]); ev = []
        for _ in range(npaths_null):
            res = primary_results(make_returns(n, rng, kind))
            ev.append(res["n_events"]["down"])
            for nm in ("down", "up"):
                c[nm][0] += res[nm]["stats"]["p_one"] < 0.05
                c[nm][1] += res[nm]["block"]["p"] < 0.05
                c[nm][2] += res[nm]["class"] == "dead"
        print(f"null {kind:<5} events/side ~{np.mean(ev):6.0f} | false-pass p<.05: down {c['down'][0]/npaths_null:5.1%} up {c['up'][0]/npaths_null:5.1%}"
              f" | stability p_stab<.05: down {c['down'][1]/npaths_null:5.1%} up {c['up'][1]/npaths_null:5.1%}"
              f" | classified dead: down {c['down'][2]/npaths_null:5.1%} up {c['up'][2]/npaths_null:5.1%}", flush=True)
    for delta in ((0.0010, 0.0035, 0.0050) if npaths_edge else ()):
        cnt = dict(sig=0, stab=0, passed=0, dead=0, incon=0)
        for _ in range(npaths_edge):
            r = make_returns(n, rng, "t4sv"); kept, side = event_clock(r)
            r2 = inject(r, kept, side, -1, delta)
            res = primary_results(r2)["down"]
            cnt["sig"] += res["stats"]["p_one"] < 0.05; cnt["stab"] += res["block"]["p"] < 0.05
            cnt["passed"] += res["class"] == "pass"; cnt["dead"] += res["class"] == "dead"; cnt["incon"] += res["class"] == "inconclusive"
        print(f"edge +{delta*100:.2f}% after down-shocks (t4sv) | significant {cnt['sig']/npaths_edge:5.1%} | stability {cnt['stab']/npaths_edge:5.1%}"
              f" | pass {cnt['passed']/npaths_edge:5.1%} dead {cnt['dead']/npaths_edge:5.1%} inconclusive {cnt['incon']/npaths_edge:5.1%}", flush=True)


def confirm(npaths, seed=99):
    rng = np.random.default_rng(seed); n = NDAYS * BAR_DAY
    for kind in ("gauss", "t4sv", "t3sv"):
        c = dict(down=[0, 0], up=[0, 0])
        for _ in range(npaths):
            res = primary_results(make_returns(n, rng, kind))
            for nm in ("down", "up"):
                c[nm][0] += res[nm]["stats"]["p_one"] < 0.05; c[nm][1] += res[nm]["block"]["p"] < 0.05
        print(f"confirm {kind:<5} {npaths} paths | false-pass: down {c['down'][0]/npaths:5.1%} up {c['up'][0]/npaths:5.1%} | stability: down {c['down'][1]/npaths:5.1%} up {c['up'][1]/npaths:5.1%}", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:] or ["--selfcheck"]
    if a[0] == "--selfcheck": selfcheck()
    elif a[0] == "--one-series": one_series(int(a[1]))
    elif a[0] == "--reduced": acceptance(60, 30)
    elif a[0] == "--full": acceptance(200, 100)
    elif a[0] == "--null": acceptance(int(a[1]), 0)
    elif a[0] == "--edge": acceptance(0, int(a[1]))
    elif a[0] == "--confirm": confirm(int(a[1]))
    else: print(__doc__)
