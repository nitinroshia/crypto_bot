#!/usr/bin/env python3
"""Compare two S2 record files (JSONL; three records per pair: discovery, stability, economic_gate).

  check_equal.py OLD NEW --mode lagsafe   OLD = delivery 8's dry-run records, NEW = the ruled dry run: every figure the HAC lags cannot
                                          change must be equal (slopes, correlations, n, origin counts and exclusions, funding facts, stability
                                          T / p_stab / s_b / passes, the whole economic gate); only se, t, p, Holm, Bonferroni, MDE, hac_lags,
                                          the sensitivity and the new gate fields may differ.
  check_equal.py OLD NEW --mode exact [--new-from-line N]   every field equal except timestamp_utc (live records against the dry run).
Exit 0 only if every comparison holds. Prints what was compared."""
import json
import math
import sys


def load(path, start=1):
    with open(path) as fh:
        return [json.loads(line) for i, line in enumerate(fh, 1) if line.strip() and i >= start]


def same(a, b, path, bad):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            bad.append(f"{path}: keys differ {sorted(set(a) ^ set(b))}")
            return
        for k in a:
            same(a[k], b[k], f"{path}.{k}", bad)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            bad.append(f"{path}: lengths {len(a)} != {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            same(x, y, f"{path}[{i}]", bad)
    elif isinstance(a, float) or isinstance(b, float):
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and (a == b or math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15) or (a != a and b != b))):
            bad.append(f"{path}: {a!r} != {b!r}")
    elif a != b:
        bad.append(f"{path}: {a!r} != {b!r}")


def main():
    old_path, new_path, mode = sys.argv[1], sys.argv[2], sys.argv[sys.argv.index("--mode") + 1]
    start = int(sys.argv[sys.argv.index("--new-from-line") + 1]) if "--new-from-line" in sys.argv else 1
    old, new = load(old_path), load(new_path, start)
    bad = []
    if len(old) != 6 or len(new) != 6:
        print(f"STOP: expected 6 records in each file, found {len(old)} and {len(new)}")
        return 1
    n_cmp = 0
    for i, (o, n) in enumerate(zip(old, new)):
        tag = f"{o['family']}/{o['status']}"
        for k in ("family", "pair", "status"):
            same(o[k], n[k], f"{tag}.{k}", bad)
        od, nd = o["detail"], n["detail"]
        if mode == "exact":
            same({k: v for k, v in o.items() if k != "timestamp_utc"}, {k: v for k, v in n.items() if k != "timestamp_utc"}, tag, bad)
            n_cmp += 1
            continue
        if o["status"] == "discovery":
            for k in ("slope", "n", "origins", "funding", "post_cutoff_rows"):
                same(od[k], nd[k], f"{tag}.{k}", bad); n_cmp += 1
            for oc, nc in zip(od["all_cells"], nd["all_cells"]):
                for k in ("H", "slope", "corr", "n"):
                    same(oc[k], nc[k], f"{tag}.cell{oc['H']}.{k}", bad); n_cmp += 1
        elif o["status"] == "stability":
            same(od, nd, f"{tag}.detail", bad); n_cmp += 1
        else:
            same({k: v for k, v in od.items() if k != "rule_mode"}, {k: nd[k] for k in od if k != "rule_mode"}, f"{tag}.detail", bad); n_cmp += 1
            print(f"  {tag}: old rule_mode {od.get('rule_mode')!r}, new rule_mode {nd.get('rule_mode')!r}; settlements held in cash because of an invalid rank: {nd.get('cash_masked_rank_settlements')}")
    if bad:
        print("EQUALITY CHECK FAILED:")
        for b in bad[:40]:
            print("  ", b)
        return 1
    print(f"EQUALITY CHECK PASSED ({mode}): {n_cmp} comparisons over 6 records; allowed to differ in lagsafe mode: se, t, p, Holm, Bonferroni, MDE, hac_lags, new gate fields" if mode == "lagsafe"
          else f"EQUALITY CHECK PASSED ({mode}): 6 records equal field by field except timestamp_utc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
