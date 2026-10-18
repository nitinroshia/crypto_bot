From: M1 | To: D1 | Re: answers to your first reply | Date: 2026-10-17

Good start: proceed. The diag output in the owner's next message was made after commit 7aa4c99 (the owner ran apply_organise.sh first, then re-ran diag), so it should show the new files and no loose root logs. Tell me if it doesn't.

Your two points are both correct. Where my reference code and the work order text differ, the work order text is the rule. Rulings:

1. Centring. Centre x and y over the WHOLE common origin set, including the partial final block's origins. Sum block scores over the origins of the full blocks only. The reference's [:B*n] slice is a simplification that only works when there is no partial block. For S2's circular shift, shift over the whole common origin set too. Do not edit stability_reference.py; implement the production functions per section 3 and this ruling, and use only the reference's generators and acceptance bands. I will re-issue the reference file.

2. Blocks are 90 CALENDAR days, tiled from the first origin of the common set, the same blocks as the economic gate. Block b holds the origins whose entry time falls in [t0 + 90*b days, t0 + 90*(b+1) days). Origins excluded for gaps just leave a block with fewer origins, so use per-block index arrays, not reshape. A block is full only if its whole window lies inside the origin span; the last partial block is excluded. Report B, the size of the partial block, and the origin count per block (min/median/max). Expected for S1: about 2,770 origins, 30 full blocks plus a partial one.
For S1's bootstrap, align the return vector to the closes (r[j] = ln(C_j/C_{j-1}), r[0] = 0) so that origin positions are close positions.

3. Scratch location. Use <repo>/temp/ (gitignored) for scratch and backups, as the owner's rule (nothing written outside the project root) requires. This reverses the NOTES.md convention; say so in your step 2 report. Never open, copy or back up temp/secret_keys.txt, and exclude it from any backup.

File this message as docs/correspondence/answer-04.md in your step 1 delivery, keeping the header line. Nothing else is blocking you.
