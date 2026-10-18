From: D1 | To: M1 | Re: step 1 verified; step 2 (registry hygiene) delivered | Date: 2026-10-18

## 1. Step 1: verified on the owner's machine
Void commit: **ac63ff2**. The owner's output ends `PASS commit ac63ff2`: registry.jsonl went from 12 to 14 lines, the first 12 are byte-identical to the backup, `cumulative_count` is 0 for ETHUSDT and BTCUSDT, and no record at discovery, stability or economic_gate enters any Holm family. All 33 self-tests passed on that run. This is the hash the S1 report will quote (report item 6).

## 2. Step 2: what I chose (you asked me to say)
- **One choke point.** `registry.append_record(record, path, *, commit_to_registry=False)` refuses to write the live registry file unless the flag is passed (`LiveRegistryWriteRefused`). The live file is `registry.LIVE_REGISTRY_PATH`, an absolute path computed from `registry.py`'s own location and recognised by file identity, so a relative path, another spelling, a symlink or another working directory cannot slip past. (The old default was a path relative to the current directory; that hazard is gone.)
- **Defaults are scratch.** `registry.DEFAULT_REGISTRY_PATH` is now `temp/scratch-registry.jsonl` (gitignored). Every tool called with its default registry path (run_s1, freeze_candidate, unlock_holdout_for_forward_test, log_descriptive_access, ...) writes scratch, never live.
- **Live writers.** `run_s1.py --commit-to-registry` and the void CLI. `run_s1.py` without the flag prints `REGISTRY: scratch (live registry untouched)`; naming the live file without the flag is an error. `freeze_manifest`, `holdout_lock` and `forward_test` were NOT given the flag: against the live file they fail closed. Nothing in WO 1.5 needs them live (S1 stops before freeze). Consequence for later: before any freeze or holdout step, a small delivery has to thread the flag through those three modules. I will not do that unasked.
- **Self-tests always use temp registries, and this is now enforced, not promised.** `selftest_all.sh` exports TMPDIR inside `<repo>/temp/`, so all self-test scratch stays inside the project (this reverses the NOTES.md convention, as you asked me to state; NOTES.md is corrected). It sets `GIT_CEILING_DIRECTORIES` so `freeze_manifest.py`'s non-repo-directory test still works. It also hashes the live registry before and after and fails the whole run if it changed. A new test, `selftest_registry_hygiene.py` (wired in; 34 tests now), checks every writer against a fake "live" file and that every default path is scratch.

## 3. Rehearsal (sandbox only; verified only when the owner's PASS comes back)
All 34 pass. I probed the hash guard with a deliberate append and it failed the run as designed. The run_s1 CLI on synthetic data: default writes 3 scratch records and leaves live untouched; naming the live file without the flag is refused; with the flag, run from a different working directory, it writes the live file (restored afterwards in my sandbox copy).

## 4. For you
Nothing is blocked and I have no research-design question. Next is step 3 (fix S1: warmup `max(L,30)`, x and y precomputed on the full series, the common origin set with calendar blocks per your ruling 2).
