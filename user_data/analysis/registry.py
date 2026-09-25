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

INTERPRETIVE CHOICE: "candidates that reach" a step is read here as
"candidates CURRENTLY AT that step" -- a family's single most recent record
overall (whatever its status) must equal `step` for it to be included. If a
family has since moved on (discovery -> stability -> frozen), it no longer
counts toward an earlier step's Holm call: only its latest, current status
speaks for it. This avoids double-counting the same candidate at two steps
at once, and means `holm_at_step(..., step="discovery")` naturally empties
out as candidates graduate past discovery -- which is the intended
behavior, not a bug: a superseded checkpoint p-value shouldn't still be
influencing a live multiple-testing adjustment.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from multitest import bonferroni_adjust, holm_adjust

DEFAULT_REGISTRY_PATH = Path("user_data/analysis/results/registry.jsonl")

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
    }
)
UNCOUNTED_STATUSES = frozenset({"history", "void_pre_fix"})

REQUIRED_KEYS = ("family", "pair", "status", "timestamp_utc")


def validate_family(family: str, status: str) -> None:
    """Raise ValueError unless `family` is well-formed for `status`. History
    imports are exempt (see module docstring); every other status must be
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


def append_record(record: dict, path: Path = DEFAULT_REGISTRY_PATH) -> dict:
    """Validate and append ONE record as one JSON line. Opens in append mode
    only -- this function cannot overwrite or edit an existing line. Returns
    the record unchanged (after validation) for convenience."""
    _validate_record(record)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return record


def import_legacy_run(
    family: str, detail: dict, void: bool = False, path: Path = DEFAULT_REGISTRY_PATH
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
    return append_record(record, path)


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


def cumulative_count(records: list[dict], pair: str) -> int:
    """Distinct counted (non-history) families ever registered for `pair`
    (a pair suffix like "ETHUSDT", or the bare family's own `pair` field --
    both are accepted since a record's `pair` field records the same thing
    the family suffix does, and callers may have either handy)."""
    return len({r["family"] for r in records if is_counted(r) and r["pair"] == pair})


def holm_at_step(records: list[dict], pair: str, step: str, p_key: str = "p_value") -> dict:
    """Holm (and Bonferroni, for reference -- never silently preferred, per
    project convention) across every counted candidate for `pair` that IS
    CURRENTLY at `step` -- i.e. each family's single MOST RECENT record
    (across all statuses, not just `step`) has status == `step`. Returns
    {family: {"p_raw", "p_bonferroni", "p_holm"}}.

    Correctly reading "most recent" here means each family's LATEST record
    overall, not its latest record among only-`step` records: a family that
    has since moved on (e.g. discovery -> stability) is no longer "at"
    discovery, so a `holm_at_step(..., step="discovery")` call must not
    still count its now-superseded discovery p-value. Otherwise a candidate
    could be double-counted at two different steps at once."""
    latest_per_family: dict[str, dict] = {}
    for r in records:
        if not is_counted(r) or r["pair"] != pair:
            continue
        latest_per_family[r["family"]] = r  # last record in file order wins, whatever its status
    at_step = {fam: r for fam, r in latest_per_family.items() if r["status"] == step}
    families = list(at_step)
    pvals = [at_step[fam].get("detail", {}).get(p_key) for fam in families]
    pvals = [float(p) if p is not None else float("nan") for p in pvals]
    holm = holm_adjust(pvals)
    bonf = bonferroni_adjust(pvals)
    return {
        fam: {"p_raw": pvals[i], "p_bonferroni": float(bonf[i]), "p_holm": float(holm[i])}
        for i, fam in enumerate(families)
    }


if __name__ == "__main__":
    import tempfile

    # ---- Family-name validation --------------------------------------------
    validate_family("S1-ETHUSDT", "discovery")  # must not raise
    validate_family("Task3-BTCUSDT", "frozen")  # must not raise
    validate_family("event_anchored_lead_lag", "history")  # exempt, must not raise
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
        append_record({"family": "S1-ETHUSDT", "pair": "ETHUSDT", "status": "discovery",
                        "timestamp_utc": new_timestamp(), "detail": {"p_value": 0.01}}, path)
        append_record({"family": "S1-ETHUSDT", "pair": "ETHUSDT", "status": "stability",
                        "timestamp_utc": new_timestamp(), "detail": {"p_value": 0.04}}, path)
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

        # ---- Second family, second pair, plus a history import ------------
        append_record({"family": "S2-BTCUSDT", "pair": "BTCUSDT", "status": "discovery",
                        "timestamp_utc": new_timestamp(), "detail": {"p_value": 0.03}}, path)
        import_legacy_run("event_anchored_lead_lag", {"p_value": 0.020, "note": "ETH/FDUSD, pre-1.2 rule"}, path=path)
        import_legacy_run("some_pre_fix_run", {"p_value": 0.5}, void=True, path=path)

        records = load_records(path)
        assert len(records) == 5

        # ---- cumulative_count excludes history/void_pre_fix ---------------
        assert cumulative_count(records, "ETHUSDT") == 1  # S1-ETHUSDT only (the two ETH/FDUSD imports don't count)
        assert cumulative_count(records, "BTCUSDT") == 1  # S2-BTCUSDT
        assert cumulative_count(records, "ETH_FDUSD") == 0  # legacy imports never counted, for any pair spelling

        # ---- holm_at_step: only S1-ETHUSDT's MOST RECENT record reaches ----
        # "stability" (p=0.04); its "discovery" p=0.01 is superseded and must
        # not leak into a stability-step Holm call.
        at_discovery = holm_at_step(records, "ETHUSDT", "discovery")
        assert list(at_discovery) == [], "S1-ETHUSDT's discovery record was superseded by its stability one"
        at_stability = holm_at_step(records, "ETHUSDT", "stability")
        assert list(at_stability) == ["S1-ETHUSDT"]
        assert abs(at_stability["S1-ETHUSDT"]["p_raw"] - 0.04) < 1e-12
        assert abs(at_stability["S1-ETHUSDT"]["p_holm"] - 0.04) < 1e-12  # family of 1: no adjustment

        # ---- Cross-check holm_at_step's numbers against multitest.py's own
        # worked example ([0.01, 0.04, 0.03] -> holm [0.03, 0.06, 0.06]),
        # this time across three DIFFERENT families reaching the same step,
        # which is the actual "Holm across candidates" scenario section 6
        # describes (never within a single family's own table -- that's
        # multitest.annotate_family's job, used inside a single run).
        multi_path = Path(tmp) / "registry_multi.jsonl"
        for fam, p in (("S1-ETHUSDT", 0.01), ("S2-ETHUSDT", 0.04), ("Task3-ETHUSDT", 0.03)):
            append_record({"family": fam, "pair": "ETHUSDT", "status": "holdout_consumed",
                           "timestamp_utc": new_timestamp(), "detail": {"p_value": p}}, multi_path)
        multi_records = load_records(multi_path)
        result = holm_at_step(multi_records, "ETHUSDT", "holdout_consumed")
        assert abs(result["S1-ETHUSDT"]["p_holm"] - 0.03) < 1e-12
        assert abs(result["S2-ETHUSDT"]["p_holm"] - 0.06) < 1e-12
        assert abs(result["Task3-ETHUSDT"]["p_holm"] - 0.06) < 1e-12
        assert abs(result["S1-ETHUSDT"]["p_bonferroni"] - 0.03) < 1e-12

    print(
        "Self-test passed: family-name validation enforces <TASK>-<PAIR> except for history imports; "
        "append-only (rejected records write nothing); cumulative_count excludes history/void_pre_fix; "
        "holm_at_step reads only each family's most recent record at the given step and matches "
        "multitest.py's own worked Holm example across three candidates reaching the same step."
    )
