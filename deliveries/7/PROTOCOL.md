# crypto_bot working protocol

Set by the owner, 2026-10-14. Applies to every agent, present and future (mathematicians and developers).
The three hard limits in section 1 are the owner's and are not negotiable.

## 1. The owner's hard limits

1. **No money.** No agent proposes, requires or nudges toward anything that costs the owner money (tools,
   subscriptions, paid agents, data feeds, servers, API plans) until the project has earned money.
   If work is blocked for lack of something paid, write `BLOCKED: <what is missing>` and stop. The owner decides
   whether to raise it. Free tools and what the owner already has are fine.
2. **The loop.** An agent hands the owner a script and whole files. The owner puts the files in place, runs the
   script, pushes to GitHub and shares the link. The agent reads what was pushed. History and context live in the
   repo, not in any chat's memory.
3. **Agents talk only through the repo.** Mathematician to mathematician, mathematician to developer, developer to
   developer: always by files, through the same loop. No agent relies on another agent's chat.

## 2. Agent IDs

Mathematicians are `M1, M2, ...`; developers are `D1, D2, ...`. Each new agent takes the next free number and adds
its row to the table in section 6 (as a file, like any other change). Sessions before this protocol are `M0` and `D0`.

## 3. Where things live

| Path | What | Who edits |
|---|---|---|
| `context/mathematician/NOTES.md` | mathematician's state and rules | mathematicians only |
| `context/developer/NOTES.md`, `context/STATUS.md` | developer's state, project status | developers only |
| `docs/work-orders/` | mathematician -> developer specifications | mathematicians |
| `docs/correspondence/` | every message between agents (`message-NN`, `answer-NN`, `question-NN`) | sender |
| `docs/handoffs/` | handoff written by an agent that is leaving (`<ID>-handoff.md`) | the leaving agent |
| `deliveries/<n>/` | files and runner script of one hand-over (inside the repo, never `/tmp`) | the delivering agent |
| `user_data/analysis/` | code and self-tests | developers |
| `user_data/analysis/results/registry.jsonl` | append-only test registry | only runs with `--commit-to-registry` |

Every correspondence file starts with one line: `From: <ID> | To: <ID> | Re: <subject> | Date: <yyyy-mm-dd>`.
Never edit another role's NOTES file.

## 4. Delivery contract

- **Whole files only**, never patches or diffs, as downloadable files. If downloads are impossible: one file per
  message, in one code block, under about 150 lines (split bigger files into modules).
- **One runner script per delivery** (`deliveries/<n>/apply.sh`), starting with `set -e`, compatible with macOS
  bash 3.2, with no placeholders. It must:
  1. print the SHA-256 of every delivered file and stop if the owner's copy differs from the list the agent gave
     (the owner can check with `shasum -a 256 <file>`);
  2. copy the files into place, inside the repo;
  3. run the relevant self-test;
  4. only if everything passed: `git add` exactly those paths, commit, push, and print `PASS` and the commit hash.
     On any failure print `FAIL` and commit nothing.
- The owner is never asked to paste code. The owner pastes outputs (logs) back, or commits them.
- Every delivery ends with one sentence: what changed, the one command to run, what `PASS` looks like.

## 5. Working rules (lessons of handoff v2.3)

- "Verified" means output from the owner's machine says so, pasted or committed. Anything run only in an agent's
  sandbox is labelled "sandbox only".
- Self-tests and exploratory runs never write to the live registry.
- Same problem twice: stop and write down what is blocking, in `docs/correspondence/`.
- When a conversation gets long or confused, the agent writes its handoff file and says so. It does not push on.
- Research design is the mathematician's call, code design the developer's. The owner is asked only for decisions
  that are the owner's.

## 6. Agents

| ID | Role | Started | Status | Notes |
|---|---|---|---|---|
| M0 | mathematician | before 2026-10-14 | ended | sessions before this protocol |
| D0 | developer | before 2026-10-14 | ended | sessions before this protocol |
| M1 | mathematician | 2026-10-14 | active | wrote this protocol |
| D1 | developer | 2026-10-17 | ended | built the S1 pipeline and report; last message `message-19` |
| D2 | developer | 2026-10-20 | active | took Work Order 1.6 (S2) from the repo |
