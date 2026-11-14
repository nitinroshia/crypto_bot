"""
Work Order 1.8 section 4: the rules files and their validators.

  rules/IN-equity-costs-v1.json  -> round_trip_cost_fraction(position_value_inr, case)  (delivery trades; slippage cases base/stress)
  rules/IN-tax-v1.json           -> validate_tax() only (the after-tax layer is Work Order 1.9; the file says confirmed_by_owner: false)

The numbers are M2's (Work Order 1.8 section 4, retrieved 2026-10-29), not D2's: the exchange transaction charge uses the Zerodha-listed NSE rate and is flagged
as unconfirmed for Upstox; slippage and position value are ASSUMPTIONS stated as such. The validators check structure, types and ranges and refuse anything else.

Round trip (one buy order, one sell order, one DP charge), as a fraction of the position value V:
  percentage charges = STT buy + STT sell + stamp (buy) + 2 x exchange + 2 x SEBI + GST x (2 x exchange + 2 x SEBI)
  fixed charges      = 2 x brokerage + DP charge + GST x (2 x brokerage + DP charge)
  cost               = percentage charges + fixed / V + 2 x slippage_per_side   (the last term only when slippage is included)
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from nse_common import PROJECT_ROOT

COSTS_PATH = PROJECT_ROOT / "rules" / "IN-equity-costs-v1.json"
TAX_PATH = PROJECT_ROOT / "rules" / "IN-tax-v1.json"
CASES = ("base", "stress")


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def _is_date(s) -> bool:
    try:
        date.fromisoformat(str(s))
        return isinstance(s, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) is not None
    except ValueError:
        return False


def _num(v, lo=None, hi=None) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and (lo is None or v >= lo) and (hi is None or v <= hi)


def _common(d: dict, problems: list) -> None:
    if not isinstance(d.get("version"), str) or not re.fullmatch(r"v\d+", d.get("version", "")):
        problems.append("version must look like 'v1'")
    if d.get("market") != "IN":
        problems.append("market must be 'IN'")
    if not _is_date(d.get("retrieved")):
        problems.append("retrieved must be an ISO date (YYYY-MM-DD)")
    if not isinstance(d.get("confirmed_by_owner"), bool):
        problems.append("confirmed_by_owner must be a boolean")
    srcs = d.get("sources")
    if not isinstance(srcs, list) or not srcs or not all(isinstance(s, dict) and s.get("name") and isinstance(s.get("confirmed"), bool) for s in srcs):
        problems.append("sources must be a non-empty list of {name, note, confirmed}")


def validate_costs(d: dict) -> list[str]:
    """Problems found in a costs rules dict (empty list = valid)."""
    problems: list[str] = []
    _common(d, problems)
    p = d.get("params", {})
    spec = {"brokerage_per_order_inr": (0, 1000), "stt_buy_pct": (0, 5), "stt_sell_pct": (0, 5), "stamp_buy_pct": (0, 1), "exchange_per_side_pct": (0, 1), "sebi_inr_per_crore": (0, 1000),
            "gst_pct": (0, 100), "dp_charge_inr_per_sell": (0, 1000), "default_position_value_inr": (1, 1e12)}
    for k, (lo, hi) in spec.items():
        if k not in p or not _num(p[k], lo, hi):
            problems.append(f"params.{k} missing or outside [{lo}, {hi}]")
    sl = p.get("slippage_per_side_pct", {})
    if not isinstance(sl, dict) or set(sl) != set(CASES) or not all(_num(sl[c], 0, 5) for c in sl) or (set(sl) == set(CASES) and sl["stress"] < sl["base"]):
        problems.append("params.slippage_per_side_pct must hold numeric 'base' and 'stress' in [0, 5] with stress >= base")
    if not isinstance(d.get("assumptions"), list) or not d.get("assumptions"):
        problems.append("assumptions must be a non-empty list (slippage and position value are assumptions and must say so)")
    return problems


def validate_tax(d: dict) -> list[str]:
    problems: list[str] = []
    _common(d, problems)
    r = d.get("rules", {})
    for k, (lo, hi) in {"short_term_rate": (0, 1), "long_term_rate": (0, 1), "cess_rate": (0, 1), "short_term_max_holding_months": (1, 120), "long_term_exemption_inr_per_financial_year": (0, 1e9)}.items():
        if k not in r or not _num(r[k], lo, hi):
            problems.append(f"rules.{k} missing or outside [{lo}, {hi}]")
    if not isinstance(r.get("surcharge_modelled"), bool):
        problems.append("rules.surcharge_modelled must be a boolean")
    if not re.fullmatch(r"(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])", str(r.get("financial_year_start", ""))):
        problems.append("rules.financial_year_start must be MM-DD")
    if not isinstance(d.get("to_be_confirmed"), list) or not d.get("to_be_confirmed"):
        problems.append("to_be_confirmed must list the open rules")
    if not d.get("disclaimer"):
        problems.append("disclaimer is required (not tax advice)")
    if d.get("confirmed_by_owner") is True and d.get("to_be_confirmed"):
        problems.append("confirmed_by_owner cannot be true while to_be_confirmed is non-empty")
    return problems


def round_trip_cost_fraction(position_value_inr: float | None = None, case: str = "base", rules: dict | None = None, include_slippage: bool = True) -> float:
    """Round-trip cost as a fraction of the position value (0.0029 = 0.29%). `case` is 'base' or 'stress' (slippage per side 0.05% / 0.10%, assumptions)."""
    rules = rules if rules is not None else load_json(COSTS_PATH)
    problems = validate_costs(rules)
    if problems:
        raise ValueError(f"invalid costs rules: {problems}")
    if case not in CASES:
        raise ValueError(f"case must be one of {CASES}")
    p = rules["params"]
    v = float(position_value_inr if position_value_inr is not None else p["default_position_value_inr"])
    if v <= 0:
        raise ValueError("position value must be positive")
    gst = p["gst_pct"] / 100.0
    sebi_pct = p["sebi_inr_per_crore"] / 1e7 * 100.0  # INR 10 per crore = 0.0001%
    pct = p["stt_buy_pct"] + p["stt_sell_pct"] + p["stamp_buy_pct"] + 2 * p["exchange_per_side_pct"] + 2 * sebi_pct + gst * (2 * p["exchange_per_side_pct"] + 2 * sebi_pct)
    fixed = 2 * p["brokerage_per_order_inr"] + p["dp_charge_inr_per_sell"]
    fixed += gst * fixed
    cost = pct / 100.0 + fixed / v
    if include_slippage:
        cost += 2 * p["slippage_per_side_pct"][case] / 100.0
    return cost


def _self_test() -> None:
    costs, tax = load_json(COSTS_PATH), load_json(TAX_PATH)
    assert validate_costs(costs) == [] and validate_tax(tax) == [], (validate_costs(costs), validate_tax(tax))
    assert costs["confirmed_by_owner"] is False and tax["confirmed_by_owner"] is False and tax["retrieved"] == "2026-10-29" == costs["retrieved"]
    # the by-hand check of Work Order 1.8: about 0.22% percentage charges plus about INR 71 fixed
    p = costs["params"]
    pct_only = round_trip_cost_fraction(1e12, "base", costs, include_slippage=False)  # fixed part vanishes
    assert abs(pct_only * 100 - 0.2225) < 0.0005, pct_only
    fixed_inr = (round_trip_cost_fraction(1e5, "base", costs, include_slippage=False) - pct_only) * 1e5
    assert abs(fixed_inr - 70.8) < 0.01, fixed_inr  # 60 x 1.18
    c1, c5 = round_trip_cost_fraction(1e5, "base", costs, include_slippage=False), round_trip_cost_fraction(5e5, "base", costs, include_slippage=False)
    assert round(c1 * 100, 2) == 0.29 and round(c5 * 100, 2) == 0.24, (c1, c5)
    # exact value by hand at INR 1 lakh: 0.1+0.1+0.015+2*0.00307+2*0.0001 = 0.22134 %; GST on exchange+SEBI 18% x 0.00634 = 0.0011412 %; fixed 70.8 -> 0.0708 %
    assert abs(c1 - (0.22134 + 0.0011412) / 100 - 70.8 / 1e5) < 1e-12
    # slippage: base 0.05% and stress 0.10% per side => 0.10% and 0.20% round trip; stress > base
    assert abs((round_trip_cost_fraction(1e5, "base", costs) - c1) - 0.0010) < 1e-12 and abs((round_trip_cost_fraction(1e5, "stress", costs) - c1) - 0.0020) < 1e-12
    assert round_trip_cost_fraction(None, "base", costs) == round_trip_cost_fraction(p["default_position_value_inr"], "base", costs), "default position value INR 100,000"
    assert round_trip_cost_fraction(2e5, "base", costs) < round_trip_cost_fraction(1e5, "base", costs), "the fixed part falls with the position value"
    for bad_case in ("", "bogus"):
        try:
            round_trip_cost_fraction(1e5, bad_case, costs)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown case must be refused")
    # validators refuse malformed files
    import copy

    def mutate(d, f):
        e = copy.deepcopy(d)
        f(e)
        return e

    for label, e in {
        "negative STT": mutate(costs, lambda e: e["params"].__setitem__("stt_buy_pct", -0.1)),
        "missing brokerage": mutate(costs, lambda e: e["params"].pop("brokerage_per_order_inr")),
        "stress below base": mutate(costs, lambda e: e["params"]["slippage_per_side_pct"].__setitem__("stress", 0.01)),
        "no sources": mutate(costs, lambda e: e.__setitem__("sources", [])),
        "bad date": mutate(costs, lambda e: e.__setitem__("retrieved", "29-10-2026")),
        "no assumptions": mutate(costs, lambda e: e.__setitem__("assumptions", [])),
        "wrong market": mutate(costs, lambda e: e.__setitem__("market", "US")),
    }.items():
        assert validate_costs(e), f"validate_costs accepted: {label}"
        try:
            round_trip_cost_fraction(1e5, "base", e)
        except ValueError:
            pass
        else:
            raise AssertionError(f"the cost function used an invalid file: {label}")
    for label, e in {
        "rate above 1": mutate(tax, lambda e: e["rules"].__setitem__("long_term_rate", 12.5)),
        "missing cess": mutate(tax, lambda e: e["rules"].pop("cess_rate")),
        "bad FY start": mutate(tax, lambda e: e["rules"].__setitem__("financial_year_start", "April 1")),
        "confirmed while open": mutate(tax, lambda e: e.__setitem__("confirmed_by_owner", True)),
        "no disclaimer": mutate(tax, lambda e: e.__setitem__("disclaimer", "")),
        "surcharge flag not bool": mutate(tax, lambda e: e["rules"].__setitem__("surcharge_modelled", "no")),
    }.items():
        assert validate_tax(e), f"validate_tax accepted: {label}"
    print(f"Self-test passed: nse_rules validates both rules files; the round-trip cost is {c1 * 100:.3f}% at INR 1 lakh and {c5 * 100:.3f}% at INR 5 lakh before slippage (by hand: 0.22% + INR 70.8 fixed, "
          f"0.29% and 0.24%), base/stress slippage adds 0.10% / 0.20%; unknown cases and malformed rules files are refused.")


if __name__ == "__main__":
    _self_test()
