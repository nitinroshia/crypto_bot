"""
Item 2, second piece: the append-only registry (mathematician NOTES.md
section 6, "Registry"; section 9's item-2 scope; work order 1.3 A.7 /
handoff v2.2 section 7.12; pair-qualified naming from Work Order 1.4).

FORMAT: one JSON object per line (JSONL) at `registry.jsonl`, opened in
append ("a") mode ONLY -- see `append_record`. There is deliberately no
"update" or "delete" function in this module: a candidate's history is a
sequence of appended records (discovery -> stability -> economic_gate ->
frozen -> holdout_consumed -> pass/dead/inconclusive), never a single row
mutated in place, so the full history of every verdict a candidate ever
received is always reconstructable from the file itself.

FAMILY NAMING (Work Order 1.4, confirmed section 6): every ETH/USDT-phase
family name is pair-qualified, `<TASK>-<PAIR>` with PAIR in {ETHUSDT,
BTCUSDT} -- e.g. `S1-ETHUSDT`, `Task3-BTCUSDT`. `validate_family` enforces
this for every status EXCEPT `history` and `void_pre_fix`, which are the two
statuses used to import the pre-existing ETH/FDUSD-era runs (section 6:
"Registry: starts empty for the ETH/USDT phase. Earlier ETH/FDUSD runs are
imported as `history` [...] as `void_pre_fix`"). Those predate the
pair-qualified scheme entirely, so their family names are whatever the
ETH/FDUSD-era name already was (e.g. `event_anchored_lead_lag`) -- forcing
them into the new `<TASK>-<PAIR>` shape would misrepresent history that
already happened under different rules. Both statuses are excluded from
`cumulative_count` and from `holm_at_step`, per the same section.

CUMULATIVE COUNT vs HOLM: these answer two different questions and must not
be confused. `cumulative_count` is just "how many ETH/USDT-phase candidates
for this pair have we tried" (context 6, Conventions: "cumulative count in
the append-only registry") -- a count of distinct families, not a
statistical adjustment. `holm_at_step` is the actual multiple-testing
adjustment "across candidates that reach" a given step (section 6, "Sample
design": "Holm across candidates that reach it [...], per pair"), applied
only to the candidates that reached that specific step with a p-value, not
to every candidate ever tried.

STEP MEMBERSHIP FOR HOLM (Work Order 1.5, ruling R1, supersedes the earlier
"currently at that step" reading): at every step that uses an across-candidate
Holm, the family is EVERY live candidate of the pair that has a record at that
step, whatever its outcome and whether or not it later moved on. Records are
keyed by (family, step): a candidate that advances from stability to the
economic gate stays in stability's Holm family, and a candidate that failed
there stays too. For each (family, step) the latest live record at that step
speaks for the family.

VOIDING (Work Order 1.5 step 1 and amendment A1). `void_family` appends ONE
record with status `void_pre_fix` and `detail["voids_earlier_records"] = True`
(a "void marker"); it never edits or deletes a line. Every record of that
(family, pair) written BEFORE its most recent void marker is void: ignored by
`cumulative_count`, `cumulative_cells` and `holm_at_step`, but still in the file.
Records written AFTER the marker (a re-run) are live again. This is a slightly
stricter reading of A1's "a family is live unless its latest record is
`void_pre_fix`": with the plain reading, a re-run that has written only its
discovery record would still leave the old, voided stability record as the
"latest record at the stability step" and count it. A void marker lists the
1-based record numbers, statuses and timestamps it voids. The `void_pre_fix`
status is also what legacy ETH/FDUSD imports use; those carry no marker flag,
so they stay uncounted exactly as before and void nothing.
`void_family` is a no-op (returns None) when the family has no live record, so
voiding twice writes nothing the second time, and it REFUSES to void a family
with a live `holdout_consumed` or `frozen` record (the one-shot locks cannot be
reset by voiding; that needs the mathematician).

REGISTRY HYGIENE (Work Order 1.5 step 2). No self-test, debug run or exploratory run
may write to the live registry. Mechanism: `append_record` (the only function that
writes a line) REFUSES to write to the live registry file unless it is called with
`commit_to_registry=True`; it raises `LiveRegistryWriteRefused` otherwise. The live
file is `LIVE_REGISTRY_PATH`, an ABSOLUTE path computed from this module's own
location (never from the current directory) and recognised by file identity
(`os.path.samefile`), so a relative path, a differently spelled path, a symlink or
another working directory cannot slip past. `DEFAULT_REGISTRY_PATH` is now a SCRATCH
registry (`temp/scratch-registry.jsonl`, gitignored): any tool called with its default
registry path writes scratch, not live. Reading or writing the live file needs
`registry.LIVE_REGISTRY_PATH` named explicitly, and writing it needs the flag as well.
Callers that can write live today: `run_s1` and the void CLI below
(`--commit-to-registry`). `freeze_manifest`, `holdout_lock` and `forward_test` do not
pass the flag, so they cannot write live until a later work order threads it through.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from multitest import bonferroni_adjust, holm_adjust

_REPO_ROOT = Path(__file__).resolve().parents[2]  # <repo>/user_data/analysis/registry.py -> <repo>
LIVE_REGISTRY_PATH = _REPO_ROOT / "user_data" / "analysis" / "results" / "registry.jsonl"
SCRATCH_REGISTRY_PATH = _REPO_ROOT / "temp" / "scratch-registry.jsonl"
# Default for every function that takes a registry path: SCRATCH, never live (see REGISTRY HYGIENE).
DEFAULT_REGISTRY_PATH = SCRATCH_REGISTRY_PATH


class LiveRegistryWriteRefused(RuntimeError):
    """Raised when something tries to append to the live registry without
    `commit_to_registry=True` (Work Order 1.5 step 2)."""


def is_live_registry(path: Path) -> bool:
    """True if `path` is the live registry file (by file identity when both exist,
    else by resolved absolute path). Reads the module global at call time."""
    p, live = Path(path), Path(LIVE_REGISTRY_PATH)
    try:
        if p.exists() and live.exists():
            return os.path.samefile(p, live)
    except OSError:
        pass
    return p.resolve() == live.resolve()

PAIR_SUFFIXES = ("ETHUSDT", "BTCUSDT")
_FAMILY_RE = re.compile(rf"^[A-Za-z0-9]+-(?:{'|'.join(PAIR_SUFFIXES)})$")

# The full lifecycle a counted (non-history) candidate can move through.
# Not all candidates reach every step (e.g. an event-type cell has no
# "economic_gate" step -- that step is S1/S2 only, section 6 step 3).
STATUSES = frozenset(
    {
        "discovery",
        "stability",
        "economic_gate",
        "frozen",
        "holdout_consumed",
        "pass",
        "dead",
        "inconclusive",
        "history",
        "void_pre_fix",
        "descriptive_access",
    }
)
# "descriptive_access" (holdout_lock.py's log_descriptive_access) is a
# data-batch tool's audit-trail entry for a full-range, no-returns-computed
# read (section 6: "logged as 'descriptive, no returns computed'") -- not a
# candidate at all, so it's exempt from family naming exactly like the two
# history statuses, and excluded from cumulative_count/holm_at_step the same
# way.
UNCOUNTED_STATUSES = frozenset({"history", "void_pre_fix", "descriptive_access"})

REQUIRED_KEYS = ("family", "pair", "status", "timestamp_utc")


def validate_family(family: str, status: str) -> None:
    """Raise ValueError unless `family` is well-formed for `status`. History
    imports and descriptive-access audit entries are exempt (see module
    docstring and UNCOUNTED_STATUSES); every other status must be
    `<TASK>-<PAIR>` with PAIR in PAIR_SUFFIXES."""
    if status in UNCOUNTED_STATUSES:
        if not family:
            raise ValueError("family must be non-empty even for a history import")
        return
    if not _FAMILY_RE.match(family):
        raise ValueError(
            f"family {family!r} is not pair-qualified as <TASK>-<PAIR> "
            f"(PAIR in {PAIR_SUFFIXES}) -- required for status {status!r}"
        )


def _validate_record(record: dict) -> None:
    missing = [k for k in REQUIRED_KEYS if k not in record]
    if missing:
        raise ValueError(f"record missing required key(s): {missing}")
    if record["status"] not in STATUSES:
        raise ValueError(f"status {record['status']!r} is not one of {sorted(STATUSES)}")
    validate_family(record["family"], record["status"])


def new_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_record(record: dict, path: Path, *, commit_to_registry: bool = False) -> dict:
    """Validate and append ONE record as one JSON line. Opens in append mode
    only -- this function cannot overwrite or edit an existing line. `path` is
    required (no default). Writing to the LIVE registry additionally needs
    `commit_to_registry=True`, else LiveRegistryWriteRefused is raised and nothing
    is written. Returns the record unchanged (after validation)."""
    _validate_record(record)
    path = Path(path)
    if is_live_registry(path) and not commit_to_registry:
        raise LiveRegistryWriteRefused(
            f"refusing to write to the live registry {path} without commit_to_registry=True "
            "(Work Order 1.5 step 2: self-tests, debug and exploratory runs must use a scratch registry)"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return record


def import_legacy_run(
    family: str,
    detail: dict,
    void: bool = False,
    path: Path = DEFAULT_REGISTRY_PATH,
    *,
    commit_to_registry: bool = False,
) -> dict:
    """Import one pre-existing ETH/FDUSD-era run as history (or void_pre_fix
    if it predates the strict-alignment fix -- section 4/6). `detail` is
    whatever the original result was (p-value, effect size, etc.), stored
    as-is for the record; nothing here recomputes or re-validates it."""
    record = {
        "family": family,
        "pair": "ETH_FDUSD",
        "status": "void_pre_fix" if void else "history",
        "timestamp_utc": new_timestamp(),
        "detail": dict(detail),
    }
    return append_record(record, path, commit_to_registry=commit_to_registry)


def load_records(path: Path = DEFAULT_REGISTRY_PATH) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    records = []
    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def is_counted(record: dict) -> bool:
    return record["status"] not in UNCOUNTED_STATUSES


VOID_MARKER_KEY = "voids_earlier_records"
NEVER_VOIDABLE = frozenset({"holdout_consumed", "frozen"})


class VoidRefusedError(ValueError):
    """Raised when voiding would reset a one-shot lock (frozen / holdout_consumed)."""


def is_void_marker(record: dict) -> bool:
    """True for a record written by `void_family`. Legacy `void_pre_fix` imports
    (no marker flag in `detail`) are NOT markers and void nothing."""
    return record.get("status") == "void_pre_fix" and bool(
        (record.get("detail") or {}).get(VOID_MARKER_KEY)
    )


def _live_indices(records: list[dict], pair: str | None = None) -> list[int]:
    """Positions (0-based, file order) of counted records that are still live:
    for each (family, pair), only the records written AFTER that family's most
    recent void marker (all of them if it was never voided)."""
    last_marker: dict[tuple[str, str], int] = {}
    for i, r in enumerate(records):
        if is_void_marker(r):
            last_marker[(r["family"], r["pair"])] = i
    live = []
    for i, r in enumerate(records):
        if not is_counted(r):
            continue
        if pair is not None and r["pair"] != pair:
            continue
        if i < last_marker.get((r["family"], r["pair"]), -1):
            continue
        live.append(i)
    return live


def live_records(records: list[dict], pair: str | None = None) -> list[dict]:
    """The counted, non-void records (optionally for one `pair`), in file order."""
    return [records[i] for i in _live_indices(records, pair)]


def cumulative_count(records: list[dict], pair: str) -> int:
    """Distinct LIVE counted families for `pair` (a record's `pair` field, e.g.
    \"ETHUSDT\"). History imports, descriptive-access entries, void markers and
    every record voided by a marker are ignored (Work Order 1.5, R1: distinct
    non-void families). Not a statistical adjustment -- see `holm_at_step`."""
    return len({r["family"] for r in live_records(records, pair)})


def cumulative_cells(records: list[dict], pair: str) -> int:
    """Number of pre-registered CELLS across the live families of `pair`
    (Work Order 1.5, R1: \"also report the number of cells\"). For each live
    family, the cells in its latest live `discovery` record's
    `detail[\"all_cells\"]` (S1: 10); a live family without that list counts as
    one cell. INTERPRETIVE CHOICE: this is the only place the registry knows a
    family's cell count."""
    latest_discovery: dict[str, dict] = {}
    families = set()
    for r in live_records(records, pair):
        families.add(r["family"])
        if r["status"] == "discovery":
            latest_discovery[r["family"]] = r
    total = 0
    for fam in families:
        cells = (latest_discovery.get(fam, {}).get("detail") or {}).get("all_cells")
        total += len(cells) if isinstance(cells, list) and cells else 1
    return total


def holm_at_step(records: list[dict], pair: str, step: str, p_key: str = "p_value") -> dict:
    """Holm (and Bonferroni, for reference -- never silently preferred) across
    EVERY live counted family of `pair` that has a record at `step` (Work Order
    1.5, ruling R1): keyed by (family, step), whatever the candidate's outcome
    and whether or not it later moved on. For each family the latest LIVE record
    whose status == `step` supplies the p-value. Records voided by a void marker
    are ignored. Returns {family: {\"p_raw\", \"p_bonferroni\", \"p_holm\"}}."""
    at_step: dict[str, dict] = {}
    for r in live_records(records, pair):
        if r["status"] == step:
            at_step[r["family"]] = r  # last live record at this step wins
    # A record whose detail carries an `entries` mapping {entry_id: p} (Work Order 1.7: a family with two primary cells) contributes
    # ONE candidate per entry, named "<family>:<entry_id>". Records without `entries` (S1, S2) behave exactly as before.
    families, raw = [], []
    for fam, rec in at_step.items():
        detail = rec.get("detail", {}) or {}
        entries = detail.get("entries")
        if isinstance(entries, dict) and entries:
            for entry_id, p in entries.items():
                families.append(f"{fam}:{entry_id}")
                raw.append(p)
        else:
            families.append(fam)
            raw.append(detail.get(p_key))
    pvals = [float(p) if p is not None else float("nan") for p in raw]
    holm = holm_adjust(pvals)
    bonf = bonferroni_adjust(pvals)
    return {
        fam: {"p_raw": pvals[i], "p_bonferroni": float(bonf[i]), "p_holm": float(holm[i])}
        for i, fam in enumerate(families)
    }


def _plan_void(records: list[dict], family: str, pair: str):
    """What `void_family` would void: (record_numbers, statuses, timestamps) of the
    live records of (family, pair), or None if there are none. Raises
    VoidRefusedError if any is a one-shot lock record."""
    nums, statuses, stamps = [], [], []
    for i in _live_indices(records, pair):
        r = records[i]
        if r["family"] != family:
            continue
        if r["status"] in NEVER_VOIDABLE:
            raise VoidRefusedError(
                f"{family}/{pair} has a live {r['status']!r} record (record {i + 1}); a one-shot lock "
                f"cannot be reset by voiding -- ask the mathematician"
            )
        nums.append(i + 1)
        statuses.append(r["status"])
        stamps.append(r["timestamp_utc"])
    return (nums, statuses, stamps) if nums else None


def _check_void_args(family: str, pair: str, reason: str) -> None:
    if pair not in PAIR_SUFFIXES:
        raise ValueError(f"pair {pair!r} is not one of {PAIR_SUFFIXES}")
    validate_family(family, "discovery")  # must be <TASK>-<PAIR>
    if not family.endswith("-" + pair):
        raise ValueError(f"family {family!r} does not belong to pair {pair!r}")
    if not reason or not str(reason).strip():
        raise ValueError("a void needs a non-empty reason")


def void_family(
    family: str,
    pair: str,
    reason: str,
    path: Path = DEFAULT_REGISTRY_PATH,
    *,
    work_order: str = "1.5",
    code_commit: str | None = None,
    commit_to_registry: bool = False,
) -> dict | None:
    """Void every live record of (family, pair) by appending ONE void marker
    (status `void_pre_fix`). Appends only; edits and deletes nothing. Returns the
    marker, or None if the family has no live record (so voiding twice is a
    no-op). Raises VoidRefusedError for a family with a live frozen or
    holdout_consumed record, ValueError for a bad family/pair/empty reason."""
    _check_void_args(family, pair, reason)
    plan = _plan_void(load_records(path), family, pair)
    if plan is None:
        return None
    nums, statuses, stamps = plan
    record = {
        "family": family,
        "pair": pair,
        "status": "void_pre_fix",
        "timestamp_utc": new_timestamp(),
        "detail": {
            "kind": "void_pre_fix",
            VOID_MARKER_KEY: True,
            "reason": str(reason).strip(),
            "target_record_numbers": nums,
            "target_statuses": statuses,
            "target_timestamps_utc": stamps,
            "work_order": work_order,
            "code_commit": code_commit,
        },
    }
    return append_record(record, path, commit_to_registry=commit_to_registry)


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Void a pre-fix family in the registry (appends one void marker; edits nothing). "
        "DRY RUN unless --commit-to-registry is given."
    )
    p.add_argument("--void-family", required=True, metavar="FAMILY", help="e.g. S1-ETHUSDT")
    p.add_argument("--pair", required=True, choices=PAIR_SUFFIXES)
    p.add_argument("--reason", required=True)
    p.add_argument("--registry-path", type=Path, default=LIVE_REGISTRY_PATH)
    p.add_argument("--code-commit", default=None, help="git commit of the code at void time")
    p.add_argument("--commit-to-registry", action="store_true", help="actually append (default: dry run)")
    a = p.parse_args(argv)
    _check_void_args(a.void_family, a.pair, a.reason)
    records = load_records(a.registry_path)
    plan = _plan_void(records, a.void_family, a.pair)
    if plan is None:
        print(f"NO-OP: {a.void_family}/{a.pair} has no live record in {a.registry_path}; nothing written")
        return 0
    nums, statuses, _ = plan
    print(f"{'WOULD VOID' if not a.commit_to_registry else 'VOIDING'} {a.void_family}/{a.pair}: "
          f"records {nums} ({', '.join(statuses)})")
    if not a.commit_to_registry:
        print("DRY RUN: nothing written (add --commit-to-registry to append the void marker)")
        return 0
    rec = void_family(
        a.void_family, a.pair, a.reason, a.registry_path, code_commit=a.code_commit, commit_to_registry=True
    )
    print("appended void marker at", rec["timestamp_utc"])
    return 0


def _rec(family: str, status: str, p: float | None = None, **extra) -> dict:
    detail = {"p_value": p} if p is not None else {}
    detail.update(extra)
    pair = family.split("-")[-1]
    return {"family": family, "pair": pair, "status": status, "timestamp_utc": new_timestamp(), "detail": detail}


def _self_test() -> None:
    import contextlib
    import io
    import tempfile

    # ---- Family-name validation --------------------------------------------
    validate_family("S1-ETHUSDT", "discovery")  # must not raise
    validate_family("Task3-BTCUSDT", "frozen")  # must not raise
    validate_family("event_anchored_lead_lag", "history")  # exempt, must not raise
    validate_family("locate_gaps.py", "descriptive_access")  # exempt, must not raise
    for bad_family, status in (
        ("S1_ETHUSDT", "discovery"),  # underscore, not hyphen
        ("S1-ETHFDUSD", "discovery"),  # not a live-phase pair
        ("S1-ethusdt", "discovery"),  # must be uppercase pair
        ("S1-ETHUSDT-extra", "discovery"),
    ):
        try:
            validate_family(bad_family, status)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected validate_family to reject {bad_family!r}")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "registry.jsonl"

        # ---- append-only: two appends -> two lines, never a rewrite -------
        append_record(_rec("S1-ETHUSDT", "discovery", 0.01), path)
        append_record(_rec("S1-ETHUSDT", "stability", 0.04), path)
        assert len(path.read_text().splitlines()) == 2

        # A record missing a required key, or with a bad status, must be rejected
        # WITHOUT writing a line (validate before any file write).
        for bad in (
            {"family": "S1-ETHUSDT", "pair": "ETHUSDT", "status": "discovery"},  # no timestamp
            {"family": "S1-ETHUSDT", "pair": "ETHUSDT", "status": "not_a_status", "timestamp_utc": "x"},
            {"family": "bad_name", "pair": "ETHUSDT", "status": "discovery", "timestamp_utc": "x"},
        ):
            try:
                append_record(bad, path)
            except ValueError:
                pass
            else:
                raise AssertionError(f"expected append_record to reject {bad}")
        assert len(path.read_text().splitlines()) == 2, "a rejected record must not add a line"

        # ---- Second family, second pair, plus two history imports ---------
        append_record(_rec("S2-BTCUSDT", "discovery", 0.03), path)
        import_legacy_run("event_anchored_lead_lag", {"p_value": 0.020, "note": "ETH/FDUSD, pre-1.2 rule"}, path=path)
        import_legacy_run("some_pre_fix_run", {"p_value": 0.5}, void=True, path=path)
        records = load_records(path)
        assert len(records) == 5

        # ---- cumulative_count excludes history / legacy void_pre_fix -------
        assert cumulative_count(records, "ETHUSDT") == 1  # S1-ETHUSDT only
        assert cumulative_count(records, "BTCUSDT") == 1  # S2-BTCUSDT
        assert cumulative_count(records, "ETH_FDUSD") == 0  # legacy imports never counted
        assert not any(is_void_marker(r) for r in records), "a legacy void_pre_fix import is not a void marker"

        # ---- R1: holm_at_step keys by (family, step): S1-ETHUSDT advanced from
        # discovery to stability and STAYS in discovery's Holm family. -----------
        at_discovery = holm_at_step(records, "ETHUSDT", "discovery")
        assert list(at_discovery) == ["S1-ETHUSDT"], "a family that advanced stays in the earlier step's Holm"
        assert abs(at_discovery["S1-ETHUSDT"]["p_raw"] - 0.01) < 1e-12
        at_stability = holm_at_step(records, "ETHUSDT", "stability")
        assert list(at_stability) == ["S1-ETHUSDT"]
        assert abs(at_stability["S1-ETHUSDT"]["p_raw"] - 0.04) < 1e-12
        assert abs(at_stability["S1-ETHUSDT"]["p_holm"] - 0.04) < 1e-12  # family of 1: no adjustment

        # ---- R1 across candidates: one advanced, one failed at the step, one
        # never reached it; Holm matches multitest.py's worked example. -----------
        multi = Path(tmp) / "registry_multi.jsonl"
        for fam, p in (("S1-ETHUSDT", 0.01), ("S2-ETHUSDT", 0.04), ("Task3-ETHUSDT", 0.03)):
            append_record(_rec(fam, "stability", p), multi)
        append_record(_rec("S1-ETHUSDT", "economic_gate"), multi)  # S1 moved on; must stay at stability
        append_record(_rec("Task4-ETHUSDT", "discovery", 0.2), multi)  # never reached stability
        res = holm_at_step(load_records(multi), "ETHUSDT", "stability")
        assert sorted(res) == ["S1-ETHUSDT", "S2-ETHUSDT", "Task3-ETHUSDT"]
        assert abs(res["S1-ETHUSDT"]["p_holm"] - 0.03) < 1e-12
        assert abs(res["S2-ETHUSDT"]["p_holm"] - 0.06) < 1e-12
        assert abs(res["Task3-ETHUSDT"]["p_holm"] - 0.06) < 1e-12
        assert abs(res["S1-ETHUSDT"]["p_bonferroni"] - 0.03) < 1e-12
        assert cumulative_count(load_records(multi), "ETHUSDT") == 4

        # ---- Voiding: the real situation (two identical runs of 3 records per
        # family, written before the fix) ----------------------------------------
        real = Path(tmp) / "registry_real.jsonl"
        cells10 = [{"L": 40, "h": 5}] * 10
        for _run in range(2):
            for fam, p in (("S1-ETHUSDT", 0.089), ("S1-BTCUSDT", 0.0097)):
                append_record(_rec(fam, "discovery", p, all_cells=cells10), real)
                append_record(_rec(fam, "stability", 0.99), real)
                append_record(_rec(fam, "economic_gate"), real)
        original_bytes = real.read_bytes()
        assert len(original_bytes.splitlines()) == 12
        assert cumulative_count(load_records(real), "ETHUSDT") == 1
        assert cumulative_count(load_records(real), "BTCUSDT") == 1
        assert cumulative_cells(load_records(real), "ETHUSDT") == 10

        m1 = void_family("S1-ETHUSDT", "ETHUSDT", "pre-fix S1: wrong origin sets", real, code_commit="abc1234")
        assert m1 is not None and m1["status"] == "void_pre_fix" and m1["detail"][VOID_MARKER_KEY] is True
        assert m1["detail"]["target_record_numbers"] == [1, 2, 3, 7, 8, 9]  # ETH records in file order
        assert m1["detail"]["target_statuses"] == ["discovery", "stability", "economic_gate"] * 2
        assert len(m1["detail"]["target_record_numbers"]) == 6
        assert m1["detail"]["code_commit"] == "abc1234" and m1["detail"]["work_order"] == "1.5"
        after = real.read_bytes()
        assert after.startswith(original_bytes), "original lines must be untouched (append-only)"
        assert len(after.splitlines()) == 13
        recs = load_records(real)
        assert cumulative_count(recs, "ETHUSDT") == 0, "counts revert after the void"
        assert cumulative_cells(recs, "ETHUSDT") == 0
        assert cumulative_count(recs, "BTCUSDT") == 1, "the other family is untouched"
        for step in ("discovery", "stability", "economic_gate"):
            assert holm_at_step(recs, "ETHUSDT", step) == {}, f"voided records must not enter Holm at {step}"
        assert list(holm_at_step(recs, "BTCUSDT", "discovery")) == ["S1-BTCUSDT"]

        # voiding twice is a no-op: nothing written
        assert void_family("S1-ETHUSDT", "ETHUSDT", "again", real) is None
        assert real.read_bytes() == after

        m2 = void_family("S1-BTCUSDT", "BTCUSDT", "pre-fix S1: wrong origin sets", real)
        assert m2 is not None and m2["detail"]["target_record_numbers"] == [4, 5, 6, 10, 11, 12]
        assert real.read_bytes().startswith(after) and len(real.read_bytes().splitlines()) == 14
        recs = load_records(real)
        assert cumulative_count(recs, "ETHUSDT") == 0 and cumulative_count(recs, "BTCUSDT") == 0
        assert real.read_bytes().startswith(original_bytes)

        # ---- Re-run after the void: new records are live, old stay void, and a
        # PARTIAL re-run (discovery only) must not resurrect the old stability record.
        append_record(_rec("S1-ETHUSDT", "discovery", 0.02, all_cells=cells10), real)
        recs = load_records(real)
        assert cumulative_count(recs, "ETHUSDT") == 1 and cumulative_cells(recs, "ETHUSDT") == 10
        d = holm_at_step(recs, "ETHUSDT", "discovery")
        assert list(d) == ["S1-ETHUSDT"] and abs(d["S1-ETHUSDT"]["p_raw"] - 0.02) < 1e-12, "old voided p 0.089 must not count"
        assert holm_at_step(recs, "ETHUSDT", "stability") == {}, "old voided stability record must not count"
        assert holm_at_step(recs, "ETHUSDT", "economic_gate") == {}
        append_record(_rec("S1-ETHUSDT", "stability", 0.03), real)
        s = holm_at_step(load_records(real), "ETHUSDT", "stability")
        assert abs(s["S1-ETHUSDT"]["p_raw"] - 0.03) < 1e-12
        # the re-run family can be voided again (second marker), then is not live
        assert void_family("S1-ETHUSDT", "ETHUSDT", "second void", real) is not None
        assert cumulative_count(load_records(real), "ETHUSDT") == 0
        assert real.read_bytes().startswith(original_bytes)

        # ---- One-shot locks cannot be voided away --------------------------
        lock = Path(tmp) / "registry_lock.jsonl"
        append_record(_rec("S1-ETHUSDT", "discovery", 0.01), lock)
        append_record(_rec("S1-ETHUSDT", "frozen"), lock)
        before = lock.read_bytes()
        try:
            void_family("S1-ETHUSDT", "ETHUSDT", "should refuse", lock)
        except VoidRefusedError:
            pass
        else:
            raise AssertionError("voiding a family with a live frozen record must be refused")
        append_record(_rec("S1-BTCUSDT", "holdout_consumed", 0.04), lock)
        try:
            void_family("S1-BTCUSDT", "BTCUSDT", "should refuse", lock)
        except VoidRefusedError:
            pass
        else:
            raise AssertionError("voiding a family with a live holdout_consumed record must be refused")
        assert lock.read_bytes().startswith(before) and len(lock.read_bytes().splitlines()) == 3

        # ---- Bad void arguments write nothing --------------------------------
        n_before = len(real.read_bytes().splitlines())
        for args in (
            ("S1-ETHUSDT", "ETHUSDT", ""),  # empty reason
            ("S1-ETHUSDT", "ETHUSDT", "   "),
            ("S1-ETHUSDT", "BTCUSDT", "wrong pair"),
            ("S1_ETHUSDT", "ETHUSDT", "bad family"),
            ("S1-ETHUSDT", "ETH_USDT", "bad pair spelling"),
        ):
            try:
                void_family(*args, real)
            except ValueError:
                pass
            else:
                raise AssertionError(f"expected void_family to reject {args}")
        assert len(real.read_bytes().splitlines()) == n_before

        # ---- CLI: dry run writes nothing; the flag appends ---------------------
        cli = Path(tmp) / "registry_cli.jsonl"
        append_record(_rec("S1-ETHUSDT", "discovery", 0.01), cli)
        base = ["--void-family", "S1-ETHUSDT", "--pair", "ETHUSDT", "--reason", "cli test", "--registry-path", str(cli)]
        b0 = cli.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            assert _cli(base) == 0 and cli.read_bytes() == b0, "dry run must not write"
            assert _cli(base + ["--commit-to-registry", "--code-commit", "deadbee"]) == 0
            assert len(cli.read_bytes().splitlines()) == 2 and cumulative_count(load_records(cli), "ETHUSDT") == 0
            b1 = cli.read_bytes()
            assert _cli(base + ["--commit-to-registry"]) == 0 and cli.read_bytes() == b1, "second void is a no-op"

        # ---- Registry hygiene (Work Order 1.5 step 2) ------------------------
        # "Live" is faked as a temp file so a broken guard could never touch the real registry.
        global LIVE_REGISTRY_PATH
        saved_live = LIVE_REGISTRY_PATH
        fake_live = Path(tmp) / "fake_live" / "registry.jsonl"
        fake_live.parent.mkdir(parents=True)
        fake_live.write_text("")
        LIVE_REGISTRY_PATH = fake_live
        try:
            assert not is_live_registry(Path(tmp) / "registry.jsonl") and is_live_registry(fake_live)
            assert is_live_registry(fake_live.parent / ".." / "fake_live" / "registry.jsonl"), "another spelling"
            link = Path(tmp) / "link.jsonl"
            os.symlink(fake_live, link)
            assert is_live_registry(link), "a symlink to the live file is the live file"
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                assert is_live_registry(Path("fake_live/registry.jsonl")), "relative path, other cwd"
            finally:
                os.chdir(cwd)
            for writer in (
                lambda: append_record(_rec("S1-ETHUSDT", "discovery", 0.01), fake_live),
                lambda: append_record(_rec("S1-ETHUSDT", "discovery", 0.01), link),
                lambda: import_legacy_run("x", {"p_value": 0.5}, path=fake_live),
            ):
                try:
                    writer()
                except LiveRegistryWriteRefused:
                    pass
                else:
                    raise AssertionError("a live-registry write without the flag must be refused")
            assert fake_live.read_text() == "", "a refused write must leave the live file untouched"
            append_record(_rec("S1-ETHUSDT", "discovery", 0.01), fake_live, commit_to_registry=True)
            assert len(fake_live.read_text().splitlines()) == 1, "with the flag the write lands"
            try:
                void_family("S1-ETHUSDT", "ETHUSDT", "no flag", fake_live)
            except LiveRegistryWriteRefused:
                pass
            else:
                raise AssertionError("void_family on the live registry needs the flag")
            assert len(fake_live.read_text().splitlines()) == 1
            with contextlib.redirect_stdout(io.StringIO()):
                cli_live = ["--void-family", "S1-ETHUSDT", "--pair", "ETHUSDT", "--reason", "t", "--registry-path", str(fake_live)]
                assert _cli(cli_live) == 0 and len(fake_live.read_text().splitlines()) == 1, "CLI dry run on live writes nothing"
                assert _cli(cli_live + ["--commit-to-registry"]) == 0 and len(fake_live.read_text().splitlines()) == 2
        finally:
            LIVE_REGISTRY_PATH = saved_live
        assert not is_live_registry(DEFAULT_REGISTRY_PATH), "the default registry must be scratch, not live"
        assert DEFAULT_REGISTRY_PATH.is_absolute() and DEFAULT_REGISTRY_PATH.parent.name == "temp"
        assert LIVE_REGISTRY_PATH.is_absolute() and LIVE_REGISTRY_PATH.name == "registry.jsonl"

    print(
        "Self-test passed: family-name validation; append-only (rejected records write nothing); "
        "cumulative_count/cumulative_cells exclude history, legacy void_pre_fix and voided records; "
        "holm_at_step keys by (family, step) per R1 (advanced and failed candidates stay at the earlier step) "
        "and matches multitest.py's worked Holm example; void_family appends one marker, original lines stay "
        "byte-identical, counts revert, voiding twice is a no-op, a partial re-run does not resurrect voided "
        "records, frozen/holdout_consumed families cannot be voided, bad arguments write nothing; the CLI is a "
        "dry run unless --commit-to-registry is given; live-registry hygiene: a write to the live file "
        "(any spelling, symlink or cwd) is refused without commit_to_registry=True and the default registry is scratch."
    )


if __name__ == "__main__":
    if "--void-family" in sys.argv:
        sys.exit(_cli(sys.argv[1:]))
    _self_test()
