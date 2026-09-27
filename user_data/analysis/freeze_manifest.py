"""
Item 2, final piece (part 1): the freeze manifest (mathematician NOTES.md
section 6, pipeline step 4). Verbatim: "Freeze: timestamp, code commit,
cell, direction, discovery estimate and dispersion in the manifest."

WHY THIS MUST BE ONE-SHOT, LIKE holdout_lock.py: freezing commits a
candidate's discovery-side estimate and direction BEFORE the holdout is
ever touched (step 5 runs "exactly the frozen primary cell" -- the frozen
manifest, not a moving target). If a family could be frozen twice, its
"frozen" estimate could be quietly moved after an early holdout peek,
defeating the entire point of freezing before the one-shot look. So
freezing checks the registry for a prior `frozen` record for the same
(family, pair) and refuses a second one, exactly as
`holdout_lock.unlock_holdout_for_forward_test` refuses a second holdout
look.

The manifest is just a `registry.jsonl` record with `status="frozen"` --
this project's registry is already the append-only, auditable manifest
mechanism used everywhere else in the pipeline; there is no separate
manifest file format to invent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import registry


class AlreadyFrozenError(RuntimeError):
    """Raised when a candidate that already has a frozen manifest is frozen
    again. See the module docstring for why a second freeze is refused
    rather than merely discouraged."""


def _current_commit(repo_dir: Path | None = None) -> str:
    """Best-effort git commit hash of HEAD. Returns "unknown" rather than
    raising if git isn't available or `repo_dir` isn't a repo -- freezing
    the manifest must not fail just because commit information couldn't be
    captured; a "code commit" of "unknown" is a visible degraded state, not
    a silent one."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def freeze_candidate(
    family: str,
    pair: str,
    direction: int,
    discovery_estimate: float,
    dispersion: float,
    n_discovery: int,
    registry_path: Path = registry.DEFAULT_REGISTRY_PATH,
    repo_dir: Path | None = None,
) -> dict:
    """Freeze one candidate's discovery-side result. `direction` must be +1
    or -1 (matches `stability_check.py`'s convention). `dispersion` is
    discovery's own standard error (SE_discovery) -- named "dispersion" to
    match section 6's own wording; `forward_test.py`'s SE-scaling formula
    reads it under that name. `n_discovery` is "the primary cell's origin
    count after the purge" (section 6, step 5) -- whatever counting
    convention the candidate's own `count_origins` function uses; this
    module has no opinion on it, only stores what it's given.

    Raises ValueError for an invalid `pair`/`direction`, or
    AlreadyFrozenError if `family` already has a frozen manifest for
    `pair`. Returns the appended record."""
    if pair not in registry.PAIR_SUFFIXES:
        raise ValueError(f"pair must be one of {registry.PAIR_SUFFIXES}, got {pair!r}")
    if direction not in (1, -1):
        raise ValueError(f"direction must be +1 or -1, got {direction!r}")

    existing = registry.load_records(registry_path)
    prior = [r for r in existing if r["family"] == family and r["pair"] == pair and r["status"] == "frozen"]
    if prior:
        raise AlreadyFrozenError(
            f"{family} ({pair}) was already frozen at {prior[-1]['timestamp_utc']} -- "
            "freezing is one-shot, refusing to move the committed estimate."
        )

    record = {
        "family": family,
        "pair": pair,
        "status": "frozen",
        "timestamp_utc": registry.new_timestamp(),
        "detail": {
            "code_commit": _current_commit(repo_dir),
            "direction": direction,
            "discovery_estimate": discovery_estimate,
            "dispersion": dispersion,
            "n_discovery": n_discovery,
        },
    }
    return registry.append_record(record, registry_path)


def get_frozen_manifest(family: str, pair: str, registry_path: Path = registry.DEFAULT_REGISTRY_PATH) -> dict:
    """Retrieve the frozen manifest for (family, pair). Raises ValueError
    if none exists -- callers (e.g. `forward_test.py`) should not proceed
    to the holdout without one."""
    records = registry.load_records(registry_path)
    frozen = [r for r in records if r["family"] == family and r["pair"] == pair and r["status"] == "frozen"]
    if not frozen:
        raise ValueError(f"no frozen manifest found for {family} ({pair})")
    return frozen[-1]


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        registry_path = Path(tmp) / "registry.jsonl"

        record = freeze_candidate(
            "S1-ETHUSDT", "ETHUSDT", direction=1, discovery_estimate=0.012, dispersion=0.004,
            n_discovery=240, registry_path=registry_path, repo_dir=None,
        )
        assert record["status"] == "frozen"
        assert record["detail"]["direction"] == 1
        assert record["detail"]["discovery_estimate"] == 0.012
        assert record["detail"]["dispersion"] == 0.004
        assert record["detail"]["n_discovery"] == 240
        assert isinstance(record["detail"]["code_commit"], str) and record["detail"]["code_commit"]

        # ---- A genuinely non-git directory must degrade to "unknown"
        # rather than raise -- freezing must never fail just because commit
        # info couldn't be captured. -------------------------------------
        non_repo_dir = Path(tmp) / "not_a_repo"
        non_repo_dir.mkdir()
        assert _current_commit(non_repo_dir) == "unknown"

        retrieved = get_frozen_manifest("S1-ETHUSDT", "ETHUSDT", registry_path=registry_path)
        assert retrieved == record

        # ---- Refreezing the SAME family+pair is refused. -----------------
        try:
            freeze_candidate(
                "S1-ETHUSDT", "ETHUSDT", direction=1, discovery_estimate=0.5, dispersion=0.001,
                n_discovery=999, registry_path=registry_path,
            )
        except AlreadyFrozenError:
            pass
        else:
            raise AssertionError("expected a second freeze of the same family+pair to be refused")
        # And the refused attempt must not have moved the committed estimate.
        assert get_frozen_manifest("S1-ETHUSDT", "ETHUSDT", registry_path=registry_path)["detail"]["discovery_estimate"] == 0.012

        # ---- A DIFFERENT family may still be frozen independently. -------
        freeze_candidate(
            "S2-ETHUSDT", "ETHUSDT", direction=-1, discovery_estimate=-0.008, dispersion=0.003,
            n_discovery=180, registry_path=registry_path,
        )
        assert get_frozen_manifest("S2-ETHUSDT", "ETHUSDT", registry_path=registry_path)["detail"]["direction"] == -1

        # ---- Retrieving an unfrozen candidate's manifest raises. ---------
        try:
            get_frozen_manifest("Task3-ETHUSDT", "ETHUSDT", registry_path=registry_path)
        except ValueError:
            pass
        else:
            raise AssertionError("expected retrieval of a never-frozen candidate to raise")

        # ---- Invalid direction/pair rejected before anything is logged. --
        before = len(registry.load_records(registry_path))
        try:
            freeze_candidate("Task3-ETHUSDT", "ETHUSDT", direction=0, discovery_estimate=1, dispersion=1, n_discovery=1, registry_path=registry_path)
        except ValueError:
            pass
        else:
            raise AssertionError("expected an invalid direction to be rejected")
        assert len(registry.load_records(registry_path)) == before

    print(
        "Self-test passed: freeze_candidate records the timestamp/commit/direction/estimate/dispersion "
        "manifest, degrades to code_commit='unknown' rather than raising with no repo given, refuses a "
        "second freeze of the same candidate without altering the committed estimate, allows a "
        "different candidate to freeze independently, and rejects invalid input before logging anything."
    )
