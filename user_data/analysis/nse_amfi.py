"""
Work Order 1.8 addendum section 3: the AMFI file and the draw.

  convert  : docs/amfi/AverageMarketCapitalization30Jun2025.xlsx -> .csv (every row and column of the sheet; one CSV per sheet if there are several)
  summary  : docs/amfi/summary-30Jun2025.txt (sheet names, title and header rows, number of companies, rank range, unit of the market cap column, average market cap
             at ranks 100, 101, 250 and 251, columns present, missing NSE symbol or ISIN among ranks 101..250, duplicate ISINs, SHA-256 of the xlsx)
  draw     : pool = AMFI rank 101..250 with an NSE symbol and an ISIN, minus `universe/owner-exclusions.txt` (one NSE symbol per line) if it exists;
             order = ascending SHA-256 hex digest of the UTF-8 string "20250831|<ISIN>". Writes universe/nse-midcap-draw-v1.csv
             (draw_order, isin, nse_symbol, company, amfi_rank, average_market_cap, sha256). The draw is reproducible with the ten lines in `independent_order`.

ONLY the 30 June 2025 workbook is ever used for the draw (published before the cutoff); the later AMFI files in docs/amfi/ are never opened by this module.

  python3 nse_amfi.py all --xlsx docs/amfi/AverageMarketCapitalization30Jun2025.xlsx
  python3 nse_amfi.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

from nse_common import PROJECT_ROOT, sha256_file

DRAW_SEED_PREFIX = "20250831"
BAND = (101, 250)
MISSING_TOKENS = {"", "-", "na", "n/a", "nan", "none", "null"}


def _clean(v) -> str:
    return "" if v is None else str(v).strip()


def is_missing(v) -> bool:
    return _clean(v).lower() in MISSING_TOKENS


def read_sheets(xlsx: Path) -> dict[str, list[list]]:
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


def write_csv(rows: list[list], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width = max((len(r) for r in rows), default=0)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        for r in rows:
            w.writerow([("" if v is None else v) for v in list(r) + [None] * (width - len(r))])


def csv_paths(csv_path: Path, sheet_names: list[str]) -> dict[str, Path]:
    """One sheet -> the given path; several sheets -> `<stem>-<sheet>.csv` each."""
    if len(sheet_names) == 1:
        return {sheet_names[0]: csv_path}
    return {n: csv_path.with_name(f"{csv_path.stem}-{re.sub(r'[^A-Za-z0-9]+', '_', n)}{csv_path.suffix}") for n in sheet_names}


def find_header(rows: list[list]) -> int:
    """Index of the first row that names both an ISIN and a company column (the rows above it are title rows)."""
    for i, r in enumerate(rows):
        cells = [_clean(c).lower() for c in r]
        if any("isin" in c for c in cells) and any("company" in c for c in cells):
            return i
    raise ValueError("no header row with ISIN and Company columns found")


def column_map(header: list) -> dict[str, int]:
    """Locate the columns by their header text (the layout of the AMFI file is described in the summary, not assumed)."""
    h = [_clean(c) for c in header]
    low = [c.lower() for c in h]

    def first(pred):
        for i, c in enumerate(low):
            if pred(c):
                return i
        raise ValueError(f"column not found in header {h}")

    return {
        "rank": first(lambda c: re.match(r"sr\.?\s*no", c) is not None),
        "company": first(lambda c: "company" in c),
        "isin": first(lambda c: "isin" in c),
        "nse_symbol": first(lambda c: "nse" in c and "symbol" in c),
        "avg_cap": first(lambda c: "average" in c and ("all" in c or "exchanges" in c)),
        "category": first(lambda c: "categori" in c),
    }


def parse_companies(rows: list[list]) -> tuple[int, list[dict], dict[str, int], list]:
    hi = find_header(rows)
    cm = column_map(rows[hi])
    out = []
    for r in rows[hi + 1:]:
        r = list(r) + [None] * (len(rows[hi]) - len(r))
        try:
            rank = int(float(_clean(r[cm["rank"]])))
        except ValueError:
            continue
        out.append({"rank": rank, "company": _clean(r[cm["company"]]), "isin": _clean(r[cm["isin"]]), "nse_symbol": _clean(r[cm["nse_symbol"]]),
                    "avg_cap": r[cm["avg_cap"]], "category": _clean(r[cm["category"]])})
    return hi, out, cm, rows[hi]


def unit_of(header_text: str) -> str:
    m = re.search(r"\(([^)]*)\)", header_text)
    return m.group(1).strip() if m else "not stated in the header"


def summary_text(xlsx: Path, sheets: dict[str, list[list]]) -> str:
    lines = [f"AMFI file: {xlsx.name}", f"SHA-256 of the xlsx: {sha256_file(xlsx)}", f"Sheets: {list(sheets)}"]
    for name, rows in sheets.items():
        hi, comp, cm, header = parse_companies(rows)
        ranks = [c["rank"] for c in comp]
        by_rank = {c["rank"]: c for c in comp}
        band = [c for c in comp if BAND[0] <= c["rank"] <= BAND[1]]
        isins = [c["isin"] for c in comp if not is_missing(c["isin"])]
        dup_all = sorted({i for i in isins if isins.count(i) > 1})
        band_isins = [c["isin"] for c in band if not is_missing(c["isin"])]
        dup_band = sorted({i for i in band_isins if band_isins.count(i) > 1})
        lines += [
            "",
            f"Sheet '{name}': {len(rows)} rows in the sheet, {max(len(r) for r in rows)} columns.",
            f"Title row(s) above the header: {[_clean(r[0]) for r in rows[:hi] if any(_clean(c) for c in r)]}",
            f"Header row: row {hi + 1} of the sheet: {[_clean(c) for c in header]}",
            f"Columns used: rank = '{_clean(header[cm['rank']])}', company = '{_clean(header[cm['company']])}', ISIN = '{_clean(header[cm['isin']])}', NSE symbol = '{_clean(header[cm['nse_symbol']])}', "
            f"average market cap = '{_clean(header[cm['avg_cap']])}', categorization = '{_clean(header[cm['category']])}'",
            f"Number of companies (rows with a numeric rank): {len(comp)}",
            f"Rank range: {min(ranks)} to {max(ranks)}; distinct ranks {len(set(ranks))}; rank column is {'strictly 1..N without gaps' if sorted(ranks) == list(range(1, len(ranks) + 1)) else 'NOT a gap-free 1..N sequence'}",
            f"Unit of the average market cap column: {unit_of(_clean(header[cm['avg_cap']]))} (as stated in its header)",
        ]
        for k in (100, 101, 250, 251):
            c = by_rank.get(k)
            lines.append(f"Average market cap at rank {k}: {c['avg_cap'] if c else 'rank not present'}" + (f"  ({c['company']}, NSE symbol '{c['nse_symbol']}', ISIN {c['isin']}, {c['category']})" if c else ""))
        miss_sym = [c for c in band if is_missing(c["nse_symbol"])]
        miss_isin = [c for c in band if is_missing(c["isin"])]
        lines += [
            f"Ranks {BAND[0]} to {BAND[1]}: {len(band)} rows; missing NSE symbol {len(miss_sym)}; missing ISIN {len(miss_isin)}; missing either {len({c['rank'] for c in miss_sym + miss_isin})}; "
            f"eligible for the pool (NSE symbol and ISIN present) {len([c for c in band if not is_missing(c['nse_symbol']) and not is_missing(c['isin'])])}",
            f"Duplicate ISINs: {len(dup_all)} in the whole sheet {dup_all[:10]}; {len(dup_band)} within ranks {BAND[0]}-{BAND[1]} {dup_band[:10]}",
            f"Categorization column, ranks 1 to {BAND[0] - 1}: {_counts([c['category'] for c in comp if c['rank'] < BAND[0]])}; ranks {BAND[0]} to {BAND[1]}: {_counts([c['category'] for c in band])}; "
            f"ranks above {BAND[1]}: {_counts([c['category'] for c in comp if c['rank'] > BAND[1]])} (a cross-check only; the pool is defined by rank)",
        ]
        if miss_sym or miss_isin:
            lines.append("Rows of the band without NSE symbol or ISIN: " + "; ".join(f"rank {c['rank']} {c['company']}" for c in (miss_sym + miss_isin)[:20]))
    return "\n".join(lines) + "\n"


def _counts(values: list[str]) -> dict:
    d: dict = {}
    for v in values:
        d[v] = d.get(v, 0) + 1
    return dict(sorted(d.items()))


def draw_digest(isin: str) -> str:
    return hashlib.sha256(f"{DRAW_SEED_PREFIX}|{isin}".encode("utf-8")).hexdigest()


def read_exclusions(path: Path | None) -> set[str]:
    if path is None or not Path(path).exists():
        return set()
    return {ln.strip() for ln in Path(path).read_text().splitlines() if ln.strip() and not ln.strip().startswith("#")}


def draw_rows(companies: list[dict], exclusions: set[str]) -> list[dict]:
    pool = [c for c in companies if BAND[0] <= c["rank"] <= BAND[1] and not is_missing(c["isin"]) and not is_missing(c["nse_symbol"]) and c["nse_symbol"] not in exclusions]
    isins = [c["isin"] for c in pool]
    dup = sorted({i for i in isins if isins.count(i) > 1})
    if dup:  # not resolved silently: a duplicate ISIN inside the pool is a question for M2
        raise ValueError(f"duplicate ISINs inside the pool {dup[:5]}: stop and ask M2 how to resolve them")
    keyed = sorted(((draw_digest(c["isin"]), c) for c in pool), key=lambda t: t[0])
    return [{"draw_order": i, "isin": c["isin"], "nse_symbol": c["nse_symbol"], "company": c["company"], "amfi_rank": c["rank"], "average_market_cap": c["avg_cap"], "sha256": d}
            for i, (d, c) in enumerate(keyed, 1)]


def write_draw(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["draw_order", "isin", "nse_symbol", "company", "amfi_rank", "average_market_cap", "sha256"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def independent_order(draw_csv: Path) -> bool:
    """The draw in ten lines of plain Python (no numpy): recompute every digest, require ascending order, draw_order = 1..N, ranks within 101..250, no duplicate ISIN."""
    import csv as _csv, hashlib as _h
    rows = list(_csv.DictReader(open(draw_csv)))
    dig = [_h.sha256(("20250831|" + r["isin"]).encode("utf-8")).hexdigest() for r in rows]
    ok = dig == [r["sha256"] for r in rows] and dig == sorted(dig) and [int(r["draw_order"]) for r in rows] == list(range(1, len(rows) + 1))
    return ok and all(101 <= int(r["amfi_rank"]) <= 250 for r in rows) and len({r["isin"] for r in rows}) == len(rows)


def run_all(xlsx: Path, csv_out: Path, summary_out: Path, draw_out: Path, exclusions: Path | None) -> dict:
    sheets = read_sheets(xlsx)
    paths = csv_paths(csv_out, list(sheets))
    for name, rows in sheets.items():
        write_csv(rows, paths[name])
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(summary_text(xlsx, sheets))
    first = list(sheets)[0]
    _, comp, _, _ = parse_companies(sheets[first])
    ex = read_exclusions(exclusions)
    rows = draw_rows(comp, ex)
    write_draw(rows, draw_out)
    if not independent_order(draw_out):
        raise AssertionError("the independent ten-line recomputation of the draw order disagrees with the written file")
    return {"csv": [str(p) for p in paths.values()], "pool": len(rows), "exclusions": sorted(ex), "companies": len(comp)}


def _self_test() -> None:
    import tempfile

    import openpyxl

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["Average Market Capitalization of listed companies during the six months ended 30 June 2025"] + [None] * 10)
        ws.append(["Sr. No.", "Company Name", "ISIN", "BSE Symbol", "BSE 6 month Avg Total Market Cap (Rs. Cr.)", "NSE Symbol", "NSE 6 month Avg Total Market Cap (Rs. Cr.)", "MSEI Symbol",
                   "MSEI 6 month Avg Total Market Cap (Rs. Cr.)", "Average of All Exchanges (Rs. Cr.)", "Categorization as per SEBI Circular"])
        for k in range(1, 301):
            ws.append([k, f"Company {k}", f"INE{k:09d}", str(500000 + k), 1000.0 - k, ("SYM%d" % k) if k not in (110, 120) else None, 999.0 - k, None, None, 1000.0 - k,
                       "Large Cap" if k <= 100 else "Mid Cap" if k <= 250 else "Small Cap"])
        ws.cell(row=2 + 130, column=3).value = None  # rank 130: missing ISIN
        ws.cell(row=2 + 280, column=3).value = "INE000000290"  # rank 280 duplicates rank 290's ISIN (outside the band: reported, not an error)
        xlsx = tmp / "AverageMarketCapitalization30Jun2025.xlsx"
        wb.save(xlsx)
        (tmp / "owner-exclusions.txt").write_text("# names the owner never trades\nSYM200\n")
        res = run_all(xlsx, tmp / "amfi.csv", tmp / "summary.txt", tmp / "draw.csv", tmp / "owner-exclusions.txt")
        assert res["companies"] == 300 and res["exclusions"] == ["SYM200"]
        text = (tmp / "summary.txt").read_text()
        for needle in ("Sheets: ['Sheet1']", "Header row: row 2", "Number of companies (rows with a numeric rank): 300", "Rank range: 1 to 300", "Unit of the average market cap column: Rs. Cr.",
                       "Average market cap at rank 100: 900", "Average market cap at rank 101: 899", "Average market cap at rank 250: 750", "Average market cap at rank 251: 749",
                       "missing NSE symbol 2; missing ISIN 1", "Duplicate ISINs: 1 in the whole sheet ['INE000000290']; 0 within ranks 101-250", sha256_file(xlsx)):
            assert needle in text, needle
        csvrows = list(csv.reader(open(tmp / "amfi.csv")))
        assert len(csvrows) == 302 and len(csvrows[1]) == 11 and csvrows[0][0].startswith("Average Market Capitalization"), "every row (title, header, 300 companies) and column"
        drawn = list(csv.DictReader(open(tmp / "draw.csv")))
        # pool: ranks 101..250 = 150, minus rank 110/120 (no NSE symbol), 130 (no ISIN), SYM200 excluded => 146
        assert len(drawn) == 146 and res["pool"] == 146 and all(101 <= int(r["amfi_rank"]) <= 250 for r in drawn) and "SYM200" not in {r["nse_symbol"] for r in drawn}
        assert independent_order(tmp / "draw.csv")
        order = sorted(drawn, key=lambda r: hashlib.sha256(("20250831|" + r["isin"]).encode()).hexdigest())
        assert [r["isin"] for r in order] == [r["isin"] for r in drawn] and [r["draw_order"] for r in drawn][:3] == ["1", "2", "3"]
        bad = list(drawn)
        bad[0], bad[1] = bad[1], bad[0]
        with open(tmp / "bad.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(drawn[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(bad)
        assert not independent_order(tmp / "bad.csv"), "a swapped draw order must be detected"
        # a duplicate ISIN INSIDE the pool is refused, not resolved silently
        comp = [dict(c) for c in parse_companies(read_sheets(xlsx)["Sheet1"])[1]]
        comp[139]["isin"] = comp[149]["isin"]
        try:
            draw_rows(comp, set())
        except ValueError as e:
            assert "ask M2" in str(e)
        else:
            raise AssertionError("duplicate ISINs in the pool must stop the draw")
        # the xlsx is read-only input: it is never modified
        assert sha256_file(xlsx) in text
    print("Self-test passed: nse_amfi finds the header below a title row, converts every row and column, writes the summary (ranks 100/101/250/251, unit, missing NSE symbol or ISIN, duplicates, SHA-256), "
          "draws the pool of ranks 101-250 (NSE symbol and ISIN present, owner exclusions removed) in ascending SHA-256 order of '20250831|ISIN', and its ten-line independent check detects a swapped order.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", nargs="?", choices=["all"])
    p.add_argument("--xlsx", type=Path, default=PROJECT_ROOT / "docs/amfi/AverageMarketCapitalization30Jun2025.xlsx")
    p.add_argument("--csv", type=Path, default=PROJECT_ROOT / "docs/amfi/AverageMarketCapitalization30Jun2025.csv")
    p.add_argument("--summary", type=Path, default=PROJECT_ROOT / "docs/amfi/summary-30Jun2025.txt")
    p.add_argument("--draw", type=Path, default=PROJECT_ROOT / "universe/nse-midcap-draw-v1.csv")
    p.add_argument("--exclusions", type=Path, default=PROJECT_ROOT / "universe/owner-exclusions.txt")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test or a.command is None:
        _self_test()
        return
    if "30Jun2025" not in a.xlsx.name:
        raise SystemExit("only the 30 June 2025 AMFI workbook may be used for the draw")
    print(run_all(a.xlsx, a.csv, a.summary, a.draw, a.exclusions))


if __name__ == "__main__":
    main()
