"""
Work Order 1.8 (NSE mid-cap panel, phase E1): shared helpers.

  * CUTOFF_DATE (2025-08-31, a calendar date): everything the research code sees is truncated at this date before any computation; data after it lives in
    a separate holdout file/view that only the forward-test command may read (see nse_loader.py).
  * read_env(): reads the owner's `.env` (DATABASE_URL, PG*, UPSTOX_ANALYTICS_TOKEN, UPSTOX_ACCESS_TOKEN) at run time. Values are returned to the caller
    and NEVER printed, logged or written anywhere by this module; `redact()` removes them from any text before it can be shown.
  * canonical CSV + SHA-256 + pull manifests: a pull is stored once, dated and hashed, never overwritten (Work Order 1.8 section 2 and the v24 addendum).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from datetime import date
from pathlib import Path

CUTOFF_DATE = date(2025, 8, 31)
SECRET_NAMES = ("DATABASE_URL", "PGPASSWORD", "UPSTOX_ANALYTICS_TOKEN", "UPSTOX_ACCESS_TOKEN")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def read_env(path: Path | None = None) -> dict:
    """Parse KEY=VALUE lines of `.env` (comments and blank lines skipped, optional surrounding quotes removed) and overlay the process environment for the
    same keys. Returns {} entries only for keys that exist. Never prints. A missing file is not an error (the process environment may hold the values)."""
    path = Path(path) if path is not None else PROJECT_ROOT / ".env"
    out: dict = {}
    if path.exists():
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            out[key] = val
    for key in list(SECRET_NAMES) + ["PGHOST", "PGPORT", "PGDATABASE", "PGUSER"]:
        if os.environ.get(key):
            out[key] = os.environ[key]
    return out


def secrets_of(env: dict) -> list[str]:
    """The secret values present in `env` (used only for redaction)."""
    vals = []
    for name in SECRET_NAMES:
        v = env.get(name)
        if v:
            vals.append(v)
            if name == "DATABASE_URL" and "@" in v and "://" in v:  # also the password part of the URL
                cred = v.split("://", 1)[1].split("@", 1)[0]
                if ":" in cred:
                    vals.append(cred.split(":", 1)[1])
    return [v for v in vals if len(v) >= 4]


def redact(text: str, env: dict) -> str:
    """Replace every secret value (and Bearer tokens) in `text` by <redacted>."""
    out = str(text)
    for v in sorted(secrets_of(env), key=len, reverse=True):
        out = out.replace(v, "<redacted>")
    import re

    return re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+", r"\1<redacted>", out)


# ----------------------------------------------------------------------------- canonical CSV, hashes, manifests
CANDLE_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def canonical_csv(rows: list[tuple]) -> str:
    """Rows (date, open, high, low, close, volume) -> canonical CSV text: header, ascending by date, '\\n' line ends, prices repr'd as delivered, no spaces."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CANDLE_COLUMNS)
    for r in sorted(rows, key=lambda x: x[0]):
        w.writerow([str(r[0]), repr(float(r[1])) if not isinstance(r[1], str) else r[1], repr(float(r[2])) if not isinstance(r[2], str) else r[2],
                    repr(float(r[3])) if not isinstance(r[3], str) else r[3], repr(float(r[4])) if not isinstance(r[4], str) else r[4], int(r[5])])
    return buf.getvalue()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_pull(pull_dir: Path, symbol_rows: dict[str, list[tuple]], pull_time: str, source: str, holdout_dir_name: str = "holdout") -> dict:
    """Write one pull: `<pull_dir>/<SYMBOL>.csv` (dates <= CUTOFF_DATE) and `<pull_dir>/holdout/<SYMBOL>.csv` (dates after it), plus `manifest.json`
    (symbol, rows, first and last date, SHA-256, pull time, source; separate entries for the holdout files). A pull folder is never overwritten."""
    pull_dir = Path(pull_dir)
    if pull_dir.exists() and any(pull_dir.iterdir()):
        raise FileExistsError(f"{pull_dir} already exists and is not empty: a re-pull is a NEW folder")
    (pull_dir / holdout_dir_name).mkdir(parents=True, exist_ok=True)
    manifest = {"pull_time": pull_time, "source": source, "cutoff": CUTOFF_DATE.isoformat(), "symbols": {}, "holdout": {}}
    for sym, rows in sorted(symbol_rows.items()):
        rows = sorted(rows, key=lambda r: str(r[0]))
        disc = [r for r in rows if str(r[0]) <= CUTOFF_DATE.isoformat()]
        hold = [r for r in rows if str(r[0]) > CUTOFF_DATE.isoformat()]
        for target, part, key in ((pull_dir / f"{sym}.csv", disc, "symbols"), (pull_dir / holdout_dir_name / f"{sym}.csv", hold, "holdout")):
            if not part and key == "holdout":
                continue
            text = canonical_csv(part)
            target.write_text(text)
            manifest[key][sym] = {"symbol": sym, "rows": len(part), "first_date": str(part[0][0]) if part else None, "last_date": str(part[-1][0]) if part else None,
                                  "sha256": sha256_text(text), "pull_time": pull_time, "source": source}
    (pull_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    manifest["manifest_sha256"] = sha256_file(pull_dir / "manifest.json")
    return manifest


def verify_pull(pull_dir: Path) -> list[str]:
    """Re-hash every file named in the manifest; returns a list of problems (empty = intact)."""
    pull_dir = Path(pull_dir)
    mf = json.loads((pull_dir / "manifest.json").read_text())
    bad = []
    for key, sub in (("symbols", ""), ("holdout", "holdout")):
        for sym, ent in mf[key].items():
            p = pull_dir / sub / f"{sym}.csv" if sub else pull_dir / f"{sym}.csv"
            if not p.exists():
                bad.append(f"{key}/{sym}: file missing")
            elif sha256_file(p) != ent["sha256"]:
                bad.append(f"{key}/{sym}: SHA-256 differs from the manifest")
    return bad


def _self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        envf = tmp / ".env"
        envf.write_text("# c\nDATABASE_URL='postgresql://u:pw123456@h:5432/d'\nUPSTOX_ANALYTICS_TOKEN=abc.DEF-123456\nPGHOST=localhost\n\nbad line\n")
        env = read_env(envf)
        assert env["DATABASE_URL"].startswith("postgresql://") and env["UPSTOX_ANALYTICS_TOKEN"] == "abc.DEF-123456" and env["PGHOST"] == "localhost"
        msg = redact(f"error at {env['DATABASE_URL']} with Authorization: Bearer {env['UPSTOX_ANALYTICS_TOKEN']} and pw123456", env)
        assert "pw123456" not in msg and "abc.DEF-123456" not in msg and "postgresql://u:" not in msg and "<redacted>" in msg, msg
        assert read_env(tmp / "nope.env").get("UPSTOX_ANALYTICS_TOKEN") in (None, os.environ.get("UPSTOX_ANALYTICS_TOKEN"))
        rows = [("2025-08-29", 10.0, 11.0, 9.5, 10.5, 100), ("2025-09-01", 10.5, 12.0, 10.0, 11.5, 200), ("2025-08-28", 9.0, 10.0, 8.5, 9.5, 50)]
        t1 = canonical_csv(rows)
        assert t1.splitlines()[0] == "date,open,high,low,close,volume" and t1.splitlines()[1].startswith("2025-08-28,") and canonical_csv(list(reversed(rows))) == t1
        m = write_pull(tmp / "pull-20261106", {"AAA": rows, "BBB": rows[:1]}, "2026-11-06T00:00:00Z", "api")
        assert m["symbols"]["AAA"]["rows"] == 2 and m["symbols"]["AAA"]["last_date"] == "2025-08-29" and m["holdout"]["AAA"]["rows"] == 1 and "BBB" not in m["holdout"]
        assert "2025-09-01" not in (tmp / "pull-20261106" / "AAA.csv").read_text() and "2025-09-01" in (tmp / "pull-20261106" / "holdout" / "AAA.csv").read_text()
        assert verify_pull(tmp / "pull-20261106") == []
        try:
            write_pull(tmp / "pull-20261106", {"AAA": rows}, "x", "api")
        except FileExistsError:
            pass
        else:
            raise AssertionError("a pull folder must never be overwritten")
        (tmp / "pull-20261106" / "AAA.csv").write_text(t1 + "tamper\n")
        assert any("differs" in b for b in verify_pull(tmp / "pull-20261106"))
    print("Self-test passed: nse_common reads .env without printing, redacts secrets and Bearer tokens, writes canonical CSVs with SHA-256 manifests, splits holdout rows (> 2025-08-31) into a separate file, "
          "never overwrites a pull and detects a tampered file.")


if __name__ == "__main__":
    _self_test()
