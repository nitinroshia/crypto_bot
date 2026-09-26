"""
Item 2, third piece: the holdout lock (mathematician NOTES.md section 6,
"Sample design" -- the LOCKED HOLDOUT rule and "Holdout exposure"; work
order 1.1, correspondence message-01/02/03).

WHAT cutoff.py DOESN'T DO. cutoff.py's `--end-date` guard truncates when a
caller PASSES `end_date` -- it does nothing to stop a caller from simply
not passing it. The actual rule (section 6) is stronger: "Outside the
forward-test command, no statistic that relates a predictor to a return...
may be computed on data after the cutoff," and the holdout is "readable
only by the forward-test command, ONCE PER CANDIDATE." This module turns
that rule into an auditable code path instead of a convention someone has
to remember: reading post-cutoff data for a hypothesis-specific purpose has
exactly one sanctioned entry point, `unlock_holdout_for_forward_test`, and
it is IMPOSSIBLE to get that data through this function without (a) the
required registry disclosure being logged first, and (b) the call being
refused outright if that candidate has already had its one look.

This module cannot stop a determined caller from calling
`databundle.load_bundle` directly with no guard at all -- Python has no real
access control, and nothing short of a code review can. What it does is
make the SANCTIONED path the only convenient, already-wired-up one (the
not-yet-built forward-test command should use nothing else), and make every
use of it self-logging, so `registry.jsonl` is a true audit trail of every
candidate that ever saw holdout data, when, and under which disclosure.
Section 6's rule is a research-process discipline; this is the tooling that
makes following it easy and violating it visible after the fact.

TWO KINDS OF POST-CUTOFF ACCESS, TWO NOTES (section 6):
1. Hypothesis-specific (relates a predictor to a return) -- ONLY through
   `unlock_holdout_for_forward_test`. For `pair="ETHUSDT"` it logs
   DISCLOSURE_NOTE_ETHUSDT (verbatim -- see below -- do not paraphrase when
   logging; a future reader of the registry needs the wording that was
   actually agreed, not a summary of it) into the registry for that
   (family, pair) BEFORE returning the full series. `pair="BTCUSDT"` still
   gets an audit entry (status="holdout_consumed") but with no note --
   BTC/USDT holdout tests were never exposed to ETH/FDUSD data, so nothing
   in DISCLOSURE_NOTE_ETHUSDT applies to them (see the note's own text).
2. Purely descriptive (no return of any series computed -- counts, spans,
   gaps, zero-trade shares, volume/trade tables, funding tie share/interval
   checks -- section 4's data-batch tools are all of this kind) -- through
   `log_descriptive_access`, which logs DESCRIPTIVE_ACCESS_NOTE and returns
   nothing: callers load their own data their own way (they're not
   candidates and don't go through the guard at all); this only produces
   the audit-trail entry the section 6 rule requires alongside that read.

ONE-SHOT ENFORCEMENT: `unlock_holdout_for_forward_test` checks the registry
for an existing `holdout_consumed` record for the same (family, pair)
BEFORE appending a new one, and raises `HoldoutAlreadyConsumedError` if one
exists. This is the actual "once per candidate" gate, not just an audit
log -- it is what stops a candidate from getting a second, better-luck
holdout look after a disappointing first one.

TWO-STEP PATTERN FOR THE (NOT YET BUILT) FORWARD-TEST COMMAND: this
function's own `holdout_consumed` record carries no p-value (the module
doesn't compute statistics, it only gates access) -- it exists purely to
make "this candidate has now looked at holdout data" true and logged the
instant the data is handed out, even before any test statistic exists. The
eventual forward-test command appends a SECOND `holdout_consumed` record
for the same family once it has actually computed the verdict, with the
real p-value in `detail`. `registry.holm_at_step` already reads each
family's single MOST RECENT record (see registry.py), so the second,
p-value-bearing record is what a `holm_at_step(..., step="holdout_consumed")`
call sees -- the bare access-log record is superseded automatically, by
design, not by any special-casing here. The ONE-SHOT check above still
blocks a genuine second access attempt, since it looks for ANY prior
holdout_consumed record for that family, not just ones with a p-value.
"""

from __future__ import annotations

from pathlib import Path

from databundle import DataBundle, load_bundle
import registry

# Verbatim, per mathematician NOTES.md section 6, "Holdout exposure" --
# see the module docstring for why this must not be paraphrased.
DISCLOSURE_NOTE_ETHUSDT = (
    "Holdout exposure (disclosed, not a violation): aggregate, non-hypothesis-specific "
    "2026 ETH/FDUSD statistics -- the fingerprint, the dead lead-lag result, and the "
    "Task 2 baseline -- fall inside the ETH/USDT holdout window (2026-01-30 onward is "
    "past the 2025-08-31 cutoff). None of them relates an ETH/USDT, BTC/USDT or funding "
    "predictor to an ETH/USDT return, so none is hypothesis-specific for this phase."
)

DESCRIPTIVE_ACCESS_NOTE = "descriptive, no returns computed"


class HoldoutAlreadyConsumedError(RuntimeError):
    """Raised when a candidate that has already had its one-shot holdout
    look tries to take a second one. This is the actual enforcement, not
    just a warning -- section 6: holdout is readable only once per
    candidate."""


def unlock_holdout_for_forward_test(
    data_dir: Path,
    asset_pair: str,
    timeframes: list[str],
    family: str,
    pair: str,
    raw_dir: Path | None = None,
    registry_path: Path = registry.DEFAULT_REGISTRY_PATH,
) -> DataBundle:
    """THE ONLY sanctioned way to load the full (untruncated) series for a
    hypothesis-specific forward test. Raises `HoldoutAlreadyConsumedError`
    if `family` has already consumed its holdout look for `pair`; otherwise
    logs the required disclosure (see module docstring) BEFORE returning
    data -- there is no path through this function that returns data
    without the log entry landing first, and no path that grants a second
    look."""
    if pair not in registry.PAIR_SUFFIXES:
        raise ValueError(f"pair must be one of {registry.PAIR_SUFFIXES}, got {pair!r}")

    existing = registry.load_records(registry_path)
    prior = [
        r for r in existing
        if r["family"] == family and r["pair"] == pair and r["status"] == "holdout_consumed"
    ]
    if prior:
        raise HoldoutAlreadyConsumedError(
            f"{family} ({pair}) already consumed its one-shot holdout test at "
            f"{prior[-1]['timestamp_utc']} -- section 6: holdout is readable only once "
            "per candidate. Refusing a second look."
        )

    note = DISCLOSURE_NOTE_ETHUSDT if pair == "ETHUSDT" else None
    registry.append_record(
        {
            "family": family,
            "pair": pair,
            "status": "holdout_consumed",
            "timestamp_utc": registry.new_timestamp(),
            "detail": {"note": note, "holdout_access": True, "p_value": None},
        },
        registry_path,
    )
    # Deliberately the RAW loader, not load_all_dataframes / cutoff.py's
    # guard -- the whole point of this function is that it's the one place
    # allowed to return the untruncated series.
    return load_bundle(data_dir, asset_pair, timeframes, raw_dir=raw_dir)


def log_descriptive_access(
    tool_name: str, pair: str, registry_path: Path = registry.DEFAULT_REGISTRY_PATH
) -> dict:
    """Audit-trail entry for a purely descriptive, no-returns-computed read
    of the full data range (locate_gaps.py, liquidity_table.py, funding tie
    share, etc.). Does not gate or return data -- callers load however they
    already do; this only appends the audit-trail entry section 6 requires
    alongside that read. `tool_name` stands in for `family` (these aren't
    candidates, so there's no pair-qualified name to give -- same exemption
    as a history import, see registry.py)."""
    return registry.append_record(
        {
            "family": tool_name,
            "pair": pair,
            "status": "descriptive_access",
            "timestamp_utc": registry.new_timestamp(),
            "detail": {"note": DESCRIPTIVE_ACCESS_NOTE},
        },
        registry_path,
    )


if __name__ == "__main__":
    import tempfile

    import pandas as pd

    from cutoff import CUTOFF

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_dir = tmp / "binance"
        registry_path = tmp / "registry.jsonl"

        idx = pd.date_range(CUTOFF - pd.Timedelta(days=3), CUTOFF + pd.Timedelta(days=10), freq="1D", tz="UTC")
        df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
        raw_dir = data_dir
        raw_dir.mkdir(parents=True, exist_ok=True)
        df.reset_index(names="date").to_feather(raw_dir / "ETH_USDT-1d.feather")

        # ---- First unlock: succeeds, returns the FULL (untruncated) series,
        # logs the ETHUSDT disclosure note verbatim. -------------------------
        bundle = unlock_holdout_for_forward_test(
            data_dir, "ETH_USDT", ["1d"], family="S1-ETHUSDT", pair="ETHUSDT", registry_path=registry_path,
        )
        assert bundle["1d"].index.max() > CUTOFF, "unlock must return the FULL series, not truncated"
        assert len(bundle["1d"]) == len(idx)

        records = registry.load_records(registry_path)
        assert len(records) == 1
        assert records[0]["status"] == "holdout_consumed"
        assert records[0]["family"] == "S1-ETHUSDT" and records[0]["pair"] == "ETHUSDT"
        assert records[0]["detail"]["note"] == DISCLOSURE_NOTE_ETHUSDT
        assert "ETH/FDUSD" in records[0]["detail"]["note"] and "2026" in records[0]["detail"]["note"]

        # ---- Second unlock attempt for the SAME family+pair: refused. ------
        try:
            unlock_holdout_for_forward_test(
                data_dir, "ETH_USDT", ["1d"], family="S1-ETHUSDT", pair="ETHUSDT", registry_path=registry_path,
            )
        except HoldoutAlreadyConsumedError:
            pass
        else:
            raise AssertionError("expected a second holdout look at the same family+pair to be refused")
        assert len(registry.load_records(registry_path)) == 1, "a refused attempt must not add a log entry"

        # ---- A DIFFERENT family may still unlock (the lock is per-candidate,
        # not global). ---------------------------------------------------------
        unlock_holdout_for_forward_test(
            data_dir, "ETH_USDT", ["1d"], family="S2-ETHUSDT", pair="ETHUSDT", registry_path=registry_path,
        )
        assert len(registry.load_records(registry_path)) == 2

        # ---- BTC/USDT gets an audit entry but NO ETH/FDUSD note. -----------
        (data_dir).mkdir(parents=True, exist_ok=True)
        df.reset_index(names="date").to_feather(raw_dir / "BTC_USDT-1d.feather")
        unlock_holdout_for_forward_test(
            data_dir, "BTC_USDT", ["1d"], family="S1-BTCUSDT", pair="BTCUSDT", registry_path=registry_path,
        )
        btc_record = [r for r in registry.load_records(registry_path) if r["family"] == "S1-BTCUSDT"][0]
        assert btc_record["detail"]["note"] is None, "BTC/USDT must not carry the ETH/FDUSD-specific note"

        # ---- Invalid pair is rejected before anything is logged. -----------
        before = len(registry.load_records(registry_path))
        try:
            unlock_holdout_for_forward_test(
                data_dir, "ETH_USDT", ["1d"], family="Task3-ETHUSDT", pair="ETH_FDUSD", registry_path=registry_path,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("expected an invalid pair to be rejected")
        assert len(registry.load_records(registry_path)) == before

        # ---- Descriptive access: logs the fixed note, gates nothing, and is
        # excluded from cumulative_count / holm_at_step (registry.py's
        # UNCOUNTED_STATUSES). --------------------------------------------------
        log_descriptive_access("locate_gaps.py", "ETH_USDT", registry_path=registry_path)
        all_records = registry.load_records(registry_path)
        desc = [r for r in all_records if r["status"] == "descriptive_access"]
        assert len(desc) == 1 and desc[0]["detail"]["note"] == DESCRIPTIVE_ACCESS_NOTE
        assert registry.cumulative_count(all_records, "ETH_USDT") == 0  # locate_gaps.py isn't a counted candidate
        assert not registry.is_counted(desc[0])

        # ---- A forward-test command's eventual SECOND append (the real
        # verdict, with a p-value) supersedes the bare access-log record for
        # holm_at_step purposes, per the module docstring's two-step pattern --
        # while the one-shot check above still would have blocked a genuine
        # second unlock call in between. -----------------------------------------
        registry.append_record(
            {
                "family": "S1-ETHUSDT", "pair": "ETHUSDT", "status": "holdout_consumed",
                "timestamp_utc": registry.new_timestamp(), "detail": {"p_value": 0.02, "note": None},
            },
            registry_path,
        )
        at_holdout = registry.holm_at_step(registry.load_records(registry_path), "ETHUSDT", "holdout_consumed")
        assert at_holdout["S1-ETHUSDT"]["p_raw"] == 0.02, "the later, p-value-bearing record must be the one used"

    print(
        "Self-test passed: unlock_holdout_for_forward_test returns the untruncated series, logs the "
        "verbatim ETH/FDUSD disclosure note for ETHUSDT (and none for BTCUSDT), refuses a second look "
        "at the same candidate without logging anything extra, still allows a different candidate to "
        "unlock, rejects an invalid pair before logging, and log_descriptive_access's entries stay "
        "excluded from cumulative_count/holm_at_step; the two-step access-log-then-verdict pattern "
        "resolves correctly for holm_at_step."
    )
