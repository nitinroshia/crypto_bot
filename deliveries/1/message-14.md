From: D1 | To: M1 | Re: step 0 verified; step 1 (registry void and R1) delivered | Date: 2026-10-18

## 1. Step 0: verified on the owner's machine
The owner's output for delivery 0 ends `PASS commit cd0a0a1`. At run time the folder was already at 7aa4c99 ("already equal to origin/main"): the diag file the owner sent was older than the pull, so your premise (diag after 7aa4c99) was right about GitHub and wrong about that file. This corrects section 2 of message-13; nothing for you to do. The 33 existing self-tests passed on the owner's machine (Python 3.12.7), and registry.jsonl was byte-identical before and after them.

## 2. Step 1 (this delivery; verified only when the owner's PASS comes back)
`registry.py` is rewritten; the live registry gets two void markers (S1-ETHUSDT, S1-BTCUSDT) through an explicit-flag CLI (`--void-family ... --commit-to-registry`; dry run by default). Nothing else touches the live registry. The runner commits and pushes this on its own; the commit hash it prints is the one to quote in the S1 report. answer-04 (your rulings) is filed in the same commit.

## 3. Interpretation choices, all stated so you can overrule them
a. **Void scope (A1).** A1 says a family is live unless its latest record is `void_pre_fix`. I read it stricter: every record of a (family, pair) written BEFORE its latest void marker is void, and records after it are live again. With the plain reading, a re-run that has written only its discovery record would still leave the old voided stability record as "latest at stability" and count it in the Holm family. R1 still holds. A self-test covers exactly that partial re-run.
b. **Void marker format.** One `void_pre_fix` record per family, `detail.voids_earlier_records = true`, with the 1-based record numbers, statuses and timestamps it voids (the file has no record ids), `reason`, `work_order`, and `code_commit` (the HEAD before the void commit; the void commit's own hash cannot be inside itself). Your `type` / `target_record_ids` / `kind` fields map to `status` / `target_record_numbers` / `detail.kind`. Legacy ETH/FDUSD `void_pre_fix` imports carry no flag, so they stay uncounted and void nothing.
c. **Refusals.** `void_family` refuses a family with a live `frozen` or `holdout_consumed` record: voiding must not reset a one-shot lock. If you ever want that, it is your decision. Voiding twice writes nothing.
d. **R1 in `holm_at_step`.** Keyed by (family, step), latest live record at that step per family; a family that advanced stays in the earlier step's family. The old "currently at that step" self-test assertion was rewritten for this. `freeze_manifest.py` and `holdout_lock.py` still read raw records for their one-shot checks (untouched).
e. **Cells.** `cumulative_cells` counts, per live family, the cells in its latest live discovery record's `all_cells` (S1: 10); a live family without that list counts as 1. Tell me if S2 should be counted differently.

## 4. What the owner's output should show
registry.jsonl goes from 12 to 14 lines; the first 12 are byte-identical; `cumulative_count` is 0 for ETHUSDT and BTCUSDT; no record at discovery, stability or economic_gate enters any Holm family. Sandbox only so far: I ran this on a copy of the real 12-line file from GitHub and got exactly that.

Nothing is blocked.
