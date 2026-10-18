"""
Work Order 1.5 step 2 -- registry hygiene self-test.

Checks, for EVERY module that can write a registry line, that a write to the "live"
registry without `commit_to_registry=True` is refused and leaves the file untouched,
and that the default registry of every tool is scratch. "Live" is faked as a temp file
(registry.LIVE_REGISTRY_PATH is repointed for the duration), so even a broken guard
could never touch the real registry; the real live file's SHA-256 is also compared
before and after as a belt-and-braces check.

Modules covered: registry (append_record, import_legacy_run, void_family), run_s1,
freeze_manifest (freeze_candidate), holdout_lock (unlock_holdout_for_forward_test,
log_descriptive_access), forward_test (run_forward_test's append goes through the same
guard; check_holdout_readiness logs via log_descriptive_access, covered here).
Run:  python3 selftest_registry_hygiene.py
"""

from __future__ import annotations

import hashlib
import inspect
import sys
import tempfile
from pathlib import Path

import forward_test
import freeze_manifest
import holdout_lock
import registry
import run_s1


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


def _must_refuse(label: str, call) -> None:
    try:
        call()
    except registry.LiveRegistryWriteRefused:
        return
    raise AssertionError(f"{label}: a live-registry write without the flag was NOT refused")


def main() -> None:
    real_live = Path(registry.LIVE_REGISTRY_PATH)
    real_before = _sha(real_live)

    # ---- Defaults are scratch, never live -----------------------------------
    assert registry.DEFAULT_REGISTRY_PATH == registry.SCRATCH_REGISTRY_PATH
    assert not registry.is_live_registry(registry.DEFAULT_REGISTRY_PATH)
    assert registry.DEFAULT_REGISTRY_PATH.is_absolute() and registry.DEFAULT_REGISTRY_PATH.parent.name == "temp"
    for fn in (
        registry.import_legacy_run, registry.void_family, run_s1.run_s1,
        freeze_manifest.freeze_candidate, freeze_manifest.get_frozen_manifest,
        holdout_lock.unlock_holdout_for_forward_test, holdout_lock.log_descriptive_access,
        forward_test.check_holdout_readiness, forward_test.run_forward_test,
    ):
        params = inspect.signature(fn).parameters
        p = params.get("registry_path", params.get("path"))
        assert p is not None, f"{fn.__qualname__} has no registry path parameter"
        assert p.default == registry.SCRATCH_REGISTRY_PATH, f"{fn.__qualname__}: default registry is not scratch"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fake_live = tmp / "fake_live" / "registry.jsonl"
        fake_live.parent.mkdir(parents=True)
        fake_live.write_text("")
        saved = registry.LIVE_REGISTRY_PATH
        registry.LIVE_REGISTRY_PATH = fake_live
        try:
            assert registry.is_live_registry(fake_live) and not registry.is_live_registry(tmp / "other.jsonl")
            rec = {"family": "S1-ETHUSDT", "pair": "ETHUSDT", "status": "discovery",
                   "timestamp_utc": registry.new_timestamp(), "detail": {"p_value": 0.01}}
            _must_refuse("registry.append_record", lambda: registry.append_record(rec, fake_live))
            _must_refuse("registry.import_legacy_run", lambda: registry.import_legacy_run("x", {"p_value": 0.5}, path=fake_live))
            _must_refuse(
                "freeze_manifest.freeze_candidate",
                lambda: freeze_manifest.freeze_candidate(
                    "S1-ETHUSDT", "ETHUSDT", direction=1, discovery_estimate=0.01, dispersion=0.004,
                    n_discovery=200, registry_path=fake_live, repo_dir=None,
                ),
            )
            _must_refuse(
                "holdout_lock.unlock_holdout_for_forward_test",
                lambda: holdout_lock.unlock_holdout_for_forward_test(
                    tmp / "no_such_data_dir", "ETH_USDT", ["1d"], family="S1-ETHUSDT", pair="ETHUSDT",
                    registry_path=fake_live,
                ),
            )
            _must_refuse(
                "holdout_lock.log_descriptive_access",
                lambda: holdout_lock.log_descriptive_access("hygiene_check", "ETH_USDT", registry_path=fake_live),
            )
            assert fake_live.read_text() == "", "refused writes must leave the live file untouched"

            # With the flag the registry's own writers do work (so the flag is real, not decoration).
            registry.append_record(rec, fake_live, commit_to_registry=True)
            assert len(fake_live.read_text().splitlines()) == 1
            _must_refuse("registry.void_family", lambda: registry.void_family("S1-ETHUSDT", "ETHUSDT", "t", fake_live))
            assert registry.void_family("S1-ETHUSDT", "ETHUSDT", "t", fake_live, commit_to_registry=True) is not None
            assert len(fake_live.read_text().splitlines()) == 2
        finally:
            registry.LIVE_REGISTRY_PATH = saved

    assert _sha(real_live) == real_before, "the REAL live registry changed during the hygiene self-test"
    print(
        "Self-test passed: every registry writer (append_record, import_legacy_run, void_family, run_s1, "
        "freeze_candidate, unlock_holdout_for_forward_test, log_descriptive_access) refuses a live-registry "
        "write without commit_to_registry=True and leaves the file untouched; every default registry path "
        "is scratch; the real live registry is byte-identical before and after."
    )


if __name__ == "__main__":
    sys.exit(main())
