From: D1 | To: M1 | Re: Work Order 1.5 step 0, owner's folder state | Date: 2026-10-18

Read, as asked: PROTOCOL, WO 1.5 (with section 8), stability_reference.py, handoff v2.3, developer NOTES, STATUS, message-12, your NOTES sections 6 and 7. I follow your answer to my two points (whole-origin-set centring including the partial block; 90 calendar-day blocks with per-block index arrays; bootstrap returns aligned to closes with r[0] = 0). It is filed as answer-04 in delivery 1.

## 1. What the owner's folder contained (from the owner's diag output, run 2026-10-17T14:05:49Z)
- Branch main, local HEAD = origin/main = 1b776f4 after the diag's own `git fetch`; 0 commits on either side; no modified or untracked files; no stash entries.
- `registry.jsonl`: 12 lines locally, 12 on GitHub, no line that exists only locally.
- The 13 root logs (4 `temp_s1_*.log`, 9 `wo1.4_*.log`) were still at the repo root, tracked. `docs/PROTOCOL.md`, `docs/work-orders/1.5.md` and `user_data/analysis/stability_reference.py` were MISSING locally. 176 tracked files.
- venv Python 3.12.7. Raw data present for ETH_USDT and BTC_USDT 1d, 1h, 5m, funding.

## 2. A mismatch with your message
Your message says the diag was made after commit 7aa4c99 (after the owner ran apply_organise.sh). The output shows the opposite: at that moment the owner's origin/main was still 1b776f4. In my read-only clone, GitHub's main is 7aa4c99. So the diag predates the push, or the push came later. I do not know which; the delivery-0 runner does not assume either. It refuses to touch anything unless the folder is clean and a strict ancestor of origin/main, then fast-forwards only.

## 3. What delivery 0 does
Guards (clean tree, on main, local is an ancestor of GitHub's main, expected hash of the STATUS.md it replaces), a backup of registry.jsonl, STATUS.md and NOTES.md plus HEAD and status text into `temp/backup-<UTC>/` (secret_keys.txt is never referenced and the runner fails if one appears in a backup), `git fetch` and `git merge --ff-only`, then the existing 33 self-tests run unchanged with their scratch redirected into `temp/` (TMPDIR), a check that `registry.jsonl` is byte-identical before and after, and only then a commit of STATUS.md, this file and the delivery folder. Nothing is deleted.

## 4. Two things I noticed that matter for steps 1 and 2
- `registry.DEFAULT_REGISTRY_PATH` is a relative path. `selftest_all.sh` does `cd` into `user_data/analysis`, so a self-test that wrote to the default path would not hit the live file; it would create a stray `user_data/analysis/user_data/...` folder. Delivery 0 fails if any such stray appears. In step 2 the default will be removed: a live write will need an explicit flag and an explicit path.
- The 12 registry lines are two complete runs of the same six records (2026-09-28 and 2026-09-30) with identical numbers. Step 1 voids by family, so all 12 are covered, and the original lines stay in the file.

- Rehearsal finding (sandbox only): the owner's rule is that scratch stays inside the project, but `freeze_manifest.py`'s self-test builds a "genuinely non-repo directory" with `tempfile` and asserts `_current_commit(...) == "unknown"`. With TMPDIR inside the repo that directory is inside the repo, git finds a commit, and the test fails. Delivery 0 therefore sets `GIT_CEILING_DIRECTORIES=<repo>/temp` for the self-test run only, so git does not look above `temp/`; no code is changed. Step 2 will decide the permanent mechanism (I expect to make the test set the ceiling itself).

Nothing is blocked. Sandbox only: I rehearsed the runner against a simulated copy of the owner's folder; nothing has run on the owner's machine yet.
