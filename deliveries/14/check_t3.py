#!/usr/bin/env python3
"""Automatic checks of delivery 14 (Work Order 1.7, M2's ruling 6c and 6d).

  check_t3.py variant OLD NEW         the variant file of delivery 13 against the same output regenerated with the masked reading as PRIMARY:
                                      old "[masked (variant)]" == new "[masked (primary)]" and old "[present (primary)]" == new "[present (literal reading, sensitivity)]",
                                      line by line (bars present, masked bars, eligible origins, MDE count, and n, mean, SE, t, p, Holm(48), MDE and class of the four primary
                                      cells), to the printed digits.
  check_t3.py dry-vs-variant DRY NEW  the four primary cells in the scratch dry-run records (discovery) equal the masked rows of the variant output, to the printed digits.
  check_t3.py live-vs-dry DRY LIVE [--new-from-line N]   four records, every field equal except timestamp_utc.
Exit 0 only if every comparison holds."""
import json
import math
import re
import sys


def sections(path):
    out, pair, label = {}, None, None
    for ln in open(path).read().splitlines():
        m = re.match(r"=== .*: (ETH_USDT|BTC_USDT) ===", ln)
        if m:
            pair, label = m.group(1), None
            continue
        m = re.match(r"\[(.+?)\] (.*)", ln)
        if m and pair:
            label = m.group(1)
            out[(pair, label)] = [m.group(2).strip()]
            continue
        if label and ln.startswith("    5m k=6"):
            out[(pair, label)].append(ln.strip())
    return out


def fmt(cid, r):
    nm = "down" if cid.endswith("down") else "up"
    return (f"5m k=6 {nm:<4}: n={r['n']} mean excess={r['mean_excess']:.6g} SE={r['se']:.6g} t={r['t']:.4f} one-sided p={r['p_one']:.6g} "
            f"Holm(48)={r['p_holm']:.6g} MDE={r['mde']:.6g} -> {r['classification'].upper()}")


def same(a, b, path, bad):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            bad.append(f"{path}: keys differ {sorted(set(a) ^ set(b))[:5]}")
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
    mode = sys.argv[1]
    bad = []
    if mode == "variant":
        old, new = sections(sys.argv[2]), sections(sys.argv[3])
        pairs = {"masked (variant)": "masked (primary)", "present (primary)": "present (literal reading, sensitivity)"}
        n = 0
        for pair in ("ETH_USDT", "BTC_USDT"):
            for olab, nlab in pairs.items():
                a, b = old.get((pair, olab)), new.get((pair, nlab))
                if a is None or b is None or len(a) != 3 or len(b) != 3:
                    bad.append(f"{pair} {olab}: section missing or incomplete")
                    continue
                for x, y in zip(a, b):
                    n += 1
                    if x != y:
                        bad.append(f"{pair} [{olab} -> {nlab}]: {x[:110]}  !=  {y[:110]}")
        print(f"variant check: {n} lines compared (4 sections x 3 lines per pair) ->", "FAILED" if bad else "all equal to the printed digits")
    elif mode == "dry-vs-variant":
        recs = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
        new = sections(sys.argv[3])
        n = 0
        for r in recs:
            if r["status"] != "discovery":
                continue
            pair = r["pair"][:3] + "_USDT"
            sec = new.get((pair, "masked (primary)"))
            if sec is None:
                bad.append(f"{pair}: masked section missing")
                continue
            for cid, cell in r["detail"]["primary_cells"].items():
                n += 1
                if fmt(cid, cell) not in sec:
                    bad.append(f"{pair} {cid}: dry-run record {fmt(cid, cell)[:120]} not found among the masked rows")
        print(f"dry-run records against the masked variant rows: {n} primary cells compared ->", "FAILED" if bad else "all equal to the printed digits")
    elif mode == "live-vs-dry":
        start = int(sys.argv[sys.argv.index("--new-from-line") + 1]) if "--new-from-line" in sys.argv else 1
        a = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
        b = [json.loads(l) for i, l in enumerate(open(sys.argv[3]), 1) if l.strip() and i >= start]
        if len(a) != 4 or len(b) != 4:
            bad.append(f"expected 4 records in each file, found {len(a)} and {len(b)}")
        else:
            for x, y in zip(a, b):
                same({k: v for k, v in x.items() if k != "timestamp_utc"}, {k: v for k, v in y.items() if k != "timestamp_utc"}, f"{x['family']}/{x['status']}", bad)
        print("live records against the dry-run records (4 records, every field except timestamp_utc) ->", "FAILED" if bad else "equal")
    else:
        bad.append("unknown mode")
    if bad:
        for b in bad[:30]:
            print("  ", b)
        print("CHECK FAILED")
        return 1
    print("CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
