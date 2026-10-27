#!/usr/bin/env python3
"""Regression check of a regenerated S1 or S2 report against the committed one (read-only).

  check_reports.py COMMITTED REGENERATED --kind s1|s2 --mode before|after

before: no other family exists yet; the two files must differ ONLY in the generation stamp (and, for S2, the persistent-null paragraph,
        because the regeneration uses --skip-null).
after : another family's records exist; the summary table of recorded figures must be identical (for S2 every column except the Holm-across-candidates
        one), and the only other differing lines may be the across-candidate Holm rows, the cumulative counts and the persistent-null paragraph.
Optional --ref-diff FILE (after mode): the file written by an earlier delivery listing the differing lines of the same regeneration; the new run's
'>' lines (stamp aside) must equal that file's '>' lines exactly, so the regenerated report reproduces the earlier post-record state to the last digit.
Prints every differing line; exit 0 only if the check holds."""
import re
import subprocess
import sys

a_path, b_path = sys.argv[1], sys.argv[2]
kind = sys.argv[sys.argv.index("--kind") + 1]
mode = sys.argv[sys.argv.index("--mode") + 1]
A, B = open(a_path).read().splitlines(), open(b_path).read().splitlines()


def section(lines, start, end):
    out, on = [], False
    for ln in lines:
        if ln.startswith(start):
            on = True
        elif on and ln.startswith(end):
            break
        if on:
            out.append(ln)
    return out


end_marker = "## ETH_USDT" if kind == "s1" else "### Persistent-null"
sa, sb = section(A, "### Summary of recorded outcomes", end_marker), section(B, "### Summary of recorded outcomes", end_marker)
bad = []
if not sa or not sb:
    bad.append("summary section missing")
rows_changed = []
if sa != sb:
    if mode == "before":
        bad.append("summary table differs before any new record exists")
    else:
        hdr = [c.strip() for c in sa[1].strip("|").split("|")] if len(sa) > 1 else []
        skip = {i for i, c in enumerate(hdr) if "Holm across candidates" in c}
        for la, lb in zip(sa, sb):
            if la == lb:
                continue
            ca, cb = [c.strip() for c in la.strip("|").split("|")], [c.strip() for c in lb.strip("|").split("|")]
            if len(ca) != len(cb) or any(x != y for i, (x, y) in enumerate(zip(ca, cb)) if i not in skip):
                bad.append(f"summary row differs outside the Holm column: {la[:80]} -> {lb[:80]}")
            else:
                rows_changed.append(lb[:60])
        if len(sa) != len(sb):
            bad.append("summary table length differs")
allowed = [r"^[<>] Generated ", r"^[<>] The persistent null was not run", r"^[<>] \d+ paths; one-sided p"]
if mode == "after":
    allowed += [r"^[<>] \| (discovery|stability|economic_gate) \|", r"cumulative_count", r"^[<>] - \*\*Across-candidate Holm"]
    if rows_changed:
        allowed += [r"^[<>] \| (ETH_USDT|BTC_USDT) \| "]
diff = subprocess.run(["diff", a_path, b_path], capture_output=True, text=True).stdout.splitlines()
shown = [ln for ln in diff if ln.startswith(("<", ">"))]
for ln in shown:
    if not any(re.search(p, ln) for p in allowed):
        bad.append("unexpected difference: " + ln[:160])
if "--ref-diff" in sys.argv:
    ref = open(sys.argv[sys.argv.index("--ref-diff") + 1]).read().splitlines()
    ref_gt = [ln for ln in ref if ln.startswith("> ") and not ln.startswith("> Generated ")]
    new_gt = [ln for ln in shown if ln.startswith("> ") and not ln.startswith("> Generated ")]
    if ref_gt != new_gt:
        bad.append(f"the regenerated report's changed lines differ from the reference diff ({len(new_gt)} lines against {len(ref_gt)})")
        for x, y in zip(new_gt, ref_gt):
            if x != y:
                bad.append("   new: " + x[:120] + "   ref: " + y[:120])
                break
print(f"{kind} report regression ({mode}): {len(shown)} differing lines, summary table {'identical' if sa == sb else 'differs only in the Holm-across-candidates column'}")
for ln in shown:
    print("  " + ln[:200])
if bad:
    print("REGRESSION CHECK FAILED:")
    for b in bad:
        print("  ", b)
    sys.exit(1)
print("REGRESSION CHECK PASSED")
