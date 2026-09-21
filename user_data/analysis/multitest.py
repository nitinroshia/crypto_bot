"""
Multiple-testing adjustments. Work order #1: "Every result states its family
size and adjusted p."

The work order does not name a method, and the choice can change which
results look promotable, so BOTH are always reported and neither is silently
preferred:
  - Bonferroni: p * m (capped at 1). Simple, most conservative.
  - Holm step-down: uniformly at least as powerful as Bonferroni while
    controlling the same family-wise error rate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

P_COLUMNS = ("p_value_hac", "p_value")


def bonferroni_adjust(pvals) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    return np.minimum(1.0, p * np.isfinite(p).sum())


def holm_adjust(pvals) -> np.ndarray:
    """Holm-Bonferroni adjusted p-values; NaNs are ignored (not counted)."""
    p = np.asarray(pvals, dtype=float)
    out = np.full(p.shape, np.nan)
    finite = np.isfinite(p)
    m = int(finite.sum())
    if m == 0:
        return out
    idx = np.flatnonzero(finite)
    order = idx[np.argsort(p[idx], kind="stable")]
    running = 0.0
    for rank, i in enumerate(order):  # rank 0 = smallest p
        adj = min(1.0, (m - rank) * p[i])
        running = max(running, adj)  # enforce monotonicity
        out[i] = running
    return out


def find_p_column(df: pd.DataFrame) -> str | None:
    return next((c for c in P_COLUMNS if c in df.columns), None)


def annotate_family(df: pd.DataFrame, p_col: str | None = None) -> pd.DataFrame:
    """Copy of a lag-table with family_size, p_bonferroni, p_holm columns.
    The family is every row that actually has a p-value (INSUFFICIENT_DATA
    rows were never tested, so they aren't counted)."""
    out = df.copy()
    p_col = p_col or find_p_column(out)
    if p_col is None or p_col not in out.columns:
        return out
    p = out[p_col].astype(float).to_numpy()
    out["family_size"] = int(np.isfinite(p).sum())
    out["p_bonferroni"] = bonferroni_adjust(p)
    out["p_holm"] = holm_adjust(p)
    return out


def family_stats_for_best(annotated: pd.DataFrame, best: dict, lag_col_prefix: str = "lag") -> dict:
    """Family size and adjusted p for the row a summarize_best_lag() call picked."""
    if "family_size" not in annotated.columns:
        return {}
    row = best.get("best_lag") if isinstance(best, dict) else None
    if row is None:
        # Nothing significant: still state how many lags were tested.
        return {"family_size": int(annotated["family_size"].iloc[0])}
    lag_col = next((c for c in annotated.columns if c.startswith(lag_col_prefix)), None)
    p_col = find_p_column(annotated)
    match = annotated[annotated[lag_col] == row[lag_col]].iloc[0]
    return {
        "family_size": int(match["family_size"]),
        "p_raw": float(match[p_col]),
        "p_bonferroni": float(match["p_bonferroni"]),
        "p_holm": float(match["p_holm"]),
    }


if __name__ == "__main__":
    p = [0.01, 0.04, 0.03]
    assert np.allclose(bonferroni_adjust(p), [0.03, 0.12, 0.09])
    assert np.allclose(holm_adjust(p), [0.03, 0.06, 0.06])
    # Cross-check against statsmodels on random p-values, including NaNs.
    from statsmodels.stats.multitest import multipletests

    rng = np.random.default_rng(3)
    pv = rng.uniform(0, 0.2, 40)
    for name, mine in (("holm", holm_adjust), ("bonferroni", bonferroni_adjust)):
        ref = multipletests(pv, method=name)[1]
        assert np.allclose(mine(pv), ref), f"{name} disagrees with statsmodels"
    with_nan = np.array([0.01, np.nan, 0.04, 0.03])
    assert np.allclose(holm_adjust(with_nan)[[0, 2, 3]], [0.03, 0.06, 0.06]) and np.isnan(holm_adjust(with_nan)[1])
    # Table annotation: INSUFFICIENT_DATA rows (no p) must not count toward the family.
    tbl = pd.DataFrame(
        {"lag": [1, 2, 3, 4], "p_value_hac": [0.001, 0.5, np.nan, 0.04], "beta": [0.1, 0.0, np.nan, 0.02]}
    )
    ann = annotate_family(tbl)
    assert ann["family_size"].iloc[0] == 3
    stats = family_stats_for_best(ann, {"best_lag": {"lag": 1, "p_value_hac": 0.001}})
    assert stats["family_size"] == 3 and abs(stats["p_bonferroni"] - 0.003) < 1e-12
    assert family_stats_for_best(ann, {"status": "NO_SIGNIFICANT_LAG_FOUND"}) == {"family_size": 3}
    print("Self-test passed: Bonferroni and Holm match statsmodels; family size excludes untested rows.")
