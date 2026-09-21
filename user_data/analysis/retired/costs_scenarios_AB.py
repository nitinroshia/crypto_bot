# RETIRED (work order 1.2, 2026-09-20). ARCHIVE ONLY -- do not import from live code.
# This is the Scenario A / Scenario B cost model (maker 0% legs, A-stress, hurdle constants) that
# was the cost model of work orders 1.0 and 1.1. Work order 1.2 replaced it with the two-case
# taker model in ../costs.py. Kept as history; its own self-test still runs:
#     python3 retired/costs_scenarios_AB.py
"""
Cost model -- single source of truth for fees and the two cost scenarios in
work order #1 ("Conventions for every task").

Fees are NOT assumed: they are the ETH/FDUSD values read off the account's
Binance fee page and reported by the project owner on 2026-09-19 (regular
user tier): maker 0%, taker 0.100%, both buy and sell.

Scenario A: maker entry, profit exit at maker (0%); stops and time exits are
            taker (0.10%). Requires post-only entries/profit exits
            (LIMIT_MAKER), otherwise a "maker" order that crosses the book
            would silently be a taker.
Scenario B: everything taker, 0.10% per side.

freqtrade can only apply ONE fee to a whole backtest, so it cannot express
scenario A. The convention is: backtest at fee 0, then re-cost every trade
here by its exit type. `net_return` reproduces freqtrade's own accounting
(open_value = rate_open * (1 + fee_entry); close_value = rate_close *
(1 - fee_exit); ratio = close_value / open_value - 1) so re-costing a
fee-0 backtest gives exactly what freqtrade would have reported at those
fees, and nothing else.
"""

from __future__ import annotations

FEE_SOURCE = "Binance fee page for ETH/FDUSD, regular user, as reported by project owner 2026-09-19"
MAKER_FEE = 0.0
TAKER_FEE = 0.001

# Work order #1, Task 3 triage hurdles (fractions, not percent).
HURDLE_VIABLE_AS_TAKER = 0.0020   # mean >= 0.20%
HURDLE_MAKER_CANDIDATE = 0.0005   # 0.05% - 0.20%

EXIT_KINDS = ("profit", "stop", "time")
SCENARIOS = ("A", "B")


def entry_fee(scenario: str) -> float:
    _check(scenario)
    return MAKER_FEE if scenario == "A" else TAKER_FEE


def exit_fee(scenario: str, exit_kind: str) -> float:
    _check(scenario)
    if exit_kind not in EXIT_KINDS:
        raise ValueError(f"exit_kind must be one of {EXIT_KINDS}, got {exit_kind!r}")
    if scenario == "B":
        return TAKER_FEE
    return MAKER_FEE if exit_kind == "profit" else TAKER_FEE


def net_return(gross_open: float, gross_close: float, scenario: str, exit_kind: str) -> float:
    """Trade return after fees, freqtrade-style, for a long spot trade."""
    fe, fx = entry_fee(scenario), exit_fee(scenario, exit_kind)
    return gross_close * (1 - fx) / (gross_open * (1 + fe)) - 1


def round_trip_fee_fraction(scenario: str, exit_kind: str) -> float:
    """Approximate round-trip fee drag (sum of the two fees), for quick
    comparison against the 0.05% / 0.20% hurdles."""
    return entry_fee(scenario) + exit_fee(scenario, exit_kind)


def _check(scenario: str) -> None:
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {SCENARIOS}, got {scenario!r}")


if __name__ == "__main__":
    assert (MAKER_FEE, TAKER_FEE) == (0.0, 0.001)
    # Scenario A, profit exit: zero fees both sides -> net == gross exactly.
    assert abs(net_return(100.0, 101.0, "A", "profit") - 0.01) < 1e-15
    # Scenario A, stop exit: only the exit pays 0.10%.
    assert abs(net_return(100.0, 99.0, "A", "stop") - (99.0 * 0.999 / 100.0 - 1)) < 1e-15
    # Scenario B: both sides 0.10% (multiplicative, freqtrade-style).
    assert abs(net_return(100.0, 101.0, "B", "profit") - (101.0 * 0.999 / (100.0 * 1.001) - 1)) < 1e-15
    # Scenario B never depends on exit type.
    assert net_return(100.0, 101.0, "B", "stop") == net_return(100.0, 101.0, "B", "time")
    assert round_trip_fee_fraction("A", "profit") == 0.0
    assert round_trip_fee_fraction("A", "time") == 0.001
    assert round_trip_fee_fraction("B", "profit") == 0.002
    assert HURDLE_VIABLE_AS_TAKER == 2 * TAKER_FEE  # the 0.20% hurdle IS the all-taker round trip
    for bad in (("C", "profit"), ("A", "gap")):
        try:
            exit_fee(*bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad}")
    print("Self-test passed: cost scenarios A/B reproduce freqtrade-style fee accounting.")
    print(f"  Source: {FEE_SOURCE}")
    print(f"  maker={MAKER_FEE:.4%}  taker={TAKER_FEE:.4%}  |  A profit-exit round trip={round_trip_fee_fraction('A','profit'):.4%}, "
          f"A stop/time={round_trip_fee_fraction('A','stop'):.4%}, B={round_trip_fee_fraction('B','profit'):.4%}")
