"""
Cost model (work order 1.2). Supersedes the Scenario A / Scenario B model of work orders 1.0
and 1.1, which is archived in retired/costs_scenarios_AB.py.

Two cases. Both assume TAKER execution at the NEXT BAR'S OPEN:

    base    fee 0.10% + slippage 0.02% per side  ->  0.12% per side, 0.24% round trip
    stress  fee 0.12% + slippage 0.03% per side  ->  0.15% per side, 0.30% round trip

The planning fee is 0.10% for makers AND takers. The account's current maker fee of 0% is a
promotion and is ignored; promotions are never modeled.

`round_trip(case)` is the simple sum of the two sides (0.24% / 0.30%), the number the work orders
quote. `net_return` applies the costs multiplicatively (price moved by slippage, then the fee on
top, on both legs), so a trade that exits at its entry price loses very slightly less than the
simple sum (about 0.2397% in the base case).

Use these functions; do not re-type the numbers elsewhere.

Command line (work order 1.3):

    python3 costs.py --per-side base      # prints 0.0012 and exits
    python3 costs.py --per-side stress    # prints 0.0015 and exits
    python3 costs.py                      # runs the self-test

`scripts/backtest.sh` takes its `--fee` from `--per-side`. freqtrade has no slippage setting, so
the per-side fee PLUS slippage is passed to it as the fee; freqtrade then values a trade as
exit*(1-f) / (entry*(1+f)) - 1 with f = per_side(case). That agrees with `net_return` (slippage
and fee applied separately, multiplicatively) to within 1e-8 (about 1e-9 measured); the self-test
asserts it.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

EXECUTION = "taker at the next bar's open"
FEE_NOTE = (
    "Planning fee 0.10% maker / 0.10% taker. The account's current maker 0% is a promotion and is "
    "ignored (work order 1.2)."
)

_CASES = {
    "base": {"fee": 0.0010, "slippage": 0.0002},
    "stress": {"fee": 0.0012, "slippage": 0.0003},
}
CASES = tuple(_CASES)


def _get(case: str) -> dict:
    if case not in _CASES:
        raise ValueError(f"case must be one of {CASES}, got {case!r}")
    return _CASES[case]


def fee_per_side(case: str) -> float:
    return _get(case)["fee"]


def slippage_per_side(case: str) -> float:
    return _get(case)["slippage"]


def per_side(case: str) -> float:
    """Fee plus slippage for ONE side (0.12% base, 0.15% stress)."""
    c = _get(case)
    return c["fee"] + c["slippage"]


def round_trip(case: str) -> float:
    """Simple-sum round-trip cost: 0.24% base, 0.30% stress."""
    return 2 * per_side(case)


def net_return(entry_open: float, exit_open: float, case: str) -> float:
    """Return of a long trade entered at `entry_open` and exited at `exit_open` (both the NEXT bar's
    open after the decision), after slippage and fees on both legs."""
    c = _get(case)
    bought = entry_open * (1 + c["slippage"]) * (1 + c["fee"])
    sold = exit_open * (1 - c["slippage"]) * (1 - c["fee"])
    return sold / bought - 1


def describe() -> dict:
    return {
        "execution": EXECUTION,
        "note": FEE_NOTE,
        "cases": {k: {"fee_per_side": v["fee"], "slippage_per_side": v["slippage"], "per_side": per_side(k),
                      "round_trip": round_trip(k)} for k, v in _CASES.items()},
    }


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cost model. With no flag, runs the self-test.")
    ap.add_argument("--per-side", choices=CASES, dest="per_side_case",
                    help="print the per-side cost (fee + slippage) for this case, e.g. 0.0012, and exit")
    args = ap.parse_args(argv)
    if args.per_side_case:
        print(f"{per_side(args.per_side_case):.4f}")
        return 0
    _self_test()
    return 0


def _self_test() -> None:
    assert CASES == ("base", "stress")
    assert abs(per_side("base") - 0.0012) < 1e-15 and abs(round_trip("base") - 0.0024) < 1e-15
    assert abs(per_side("stress") - 0.0015) < 1e-15 and abs(round_trip("stress") - 0.0030) < 1e-15
    assert fee_per_side("base") == 0.0010 and slippage_per_side("base") == 0.0002
    assert fee_per_side("stress") == 0.0012 and slippage_per_side("stress") == 0.0003
    # A trade that exits where it entered loses just under the simple-sum round trip, and stress > base.
    flat_base, flat_stress = net_return(3000.0, 3000.0, "base"), net_return(3000.0, 3000.0, "stress")
    assert -0.0024 < flat_base < -0.0023, flat_base
    assert -0.0030 < flat_stress < -0.0029, flat_stress
    assert flat_stress < flat_base < 0
    # Direction and scale: a +1.0% move nets about +1.0% - 0.24%; a -1.0% move about -1.0% - 0.24%.
    assert abs(net_return(3000.0, 3030.0, "base") - (0.01 - 0.0024)) < 5e-5
    assert abs(net_return(3000.0, 2970.0, "base") - (-0.01 - 0.0024)) < 5e-5
    # Costs are independent of price level (scale-invariant).
    assert abs(net_return(1.0, 1.01, "stress") - net_return(3000.0, 3030.0, "stress")) < 1e-12
    for bad in ("A", "Base", "taker"):
        try:
            per_side(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")
    d = describe()
    assert d["cases"]["base"]["round_trip"] == round_trip("base") and "promotion" in d["note"]

    # freqtrade accounting with fee = per-side fee + slippage agrees with net_return within 1e-8.
    for case in CASES:
        f = per_side(case)
        for entry, exit_ in ((100.0, 100.0), (3000.0, 3030.0), (3000.0, 2970.0), (2500.37, 2618.11), (1.0, 0.5), (1.0, 2.0)):
            freqtrade_style = exit_ * (1 - f) / (entry * (1 + f)) - 1
            assert abs(net_return(entry, exit_, case) - freqtrade_style) < 1e-8, (case, entry, exit_)

    # The --per-side flag prints exactly the number backtest.sh passes to freqtrade as --fee.
    for case, expected in (("base", "0.0012"), ("stress", "0.0015")):
        out = subprocess.run([sys.executable, __file__, "--per-side", case], capture_output=True, text=True)
        assert out.returncode == 0 and out.stdout == expected + "\n" and out.stderr == "", (case, out)
        assert float(out.stdout) == per_side(case) or abs(float(out.stdout) - per_side(case)) < 1e-12
    bad = subprocess.run([sys.executable, __file__, "--per-side", "A"], capture_output=True, text=True)
    assert bad.returncode != 0 and bad.stdout == "", "an unknown case must fail with no number on stdout"
    print("Self-test passed: two-case taker cost model (base 0.24%, stress 0.30% round trip; next-open execution).")
    print(f"  {FEE_NOTE}")
    print("  --per-side base -> 0.0012, --per-side stress -> 0.0015; agrees with freqtrade's fee accounting within 1e-8.")


if __name__ == "__main__":
    sys.exit(_main())