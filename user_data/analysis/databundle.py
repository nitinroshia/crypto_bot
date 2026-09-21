"""
Multi-pair data bundle (work order #1, Task 0: "Extend `data` keys to
PAIR:timeframe; existing formulas keep working on the default pair").

`data` was a plain dict keyed by timeframe ("1m", "5m", ...). It is now a
DataBundle: a dict whose canonical keys are "PAIR:timeframe"
(e.g. "ETH_USDT:1m"), that ALSO answers to a bare timeframe key by resolving
it against the default pair. So every existing formula -- `data["5m"]`,
`"5m" in data` -- behaves exactly as before, while new formulas can ask for
`data["ETH_USDT:1m"]` or `data["ETH_FDUSD:1m"]` side by side.

Key grammar (all accepted anywhere a key is accepted):
    "5m"                 default pair, native (freqtrade) file
    "ETH_USDT:1m"        that pair; looked up in --data-dir first, then --raw-dir
    "ETH/USDT:1m"        same ("/" is normalised to "_")
    "ETH_FDUSD:1m:raw"   force the raw-kline store (has n_trades, taker_buy_* columns)

The raw store (default <data-dir>/../binance_raw) is kept separate from
freqtrade's data dir on purpose: freqtrade assigns its six standard column
names when it reads a feather file, so files with extra columns must not sit
where freqtrade can find them.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_PAIR = "ETH_FDUSD"
KNOWN_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "1d", "1w")


def normalize_pair(pair: str) -> str:
    return pair.replace("/", "_").strip().upper()


def parse_key(key: str, default_pair: str = DEFAULT_PAIR) -> tuple[str, str, bool]:
    """-> (pair, timeframe, force_raw)."""
    parts = key.split(":")
    if len(parts) == 1:
        return normalize_pair(default_pair), parts[0], False
    if len(parts) == 2:
        return normalize_pair(parts[0]), parts[1], False
    if len(parts) == 3 and parts[2] == "raw":
        return normalize_pair(parts[0]), parts[1], True
    raise ValueError(f"bad data key {key!r}: expected TF, PAIR:TF or PAIR:TF:raw")


def canonical_key(pair: str, timeframe: str, raw: bool = False) -> str:
    return f"{normalize_pair(pair)}:{timeframe}" + (":raw" if raw else "")


class DataBundle(dict):
    """dict[str, DataFrame] with canonical PAIR:tf keys and bare-tf aliasing."""

    def __init__(self, default_pair: str = DEFAULT_PAIR, items=None):
        super().__init__()
        self.default_pair = normalize_pair(default_pair)
        for k, v in dict(items or {}).items():
            self[k] = v

    def _canon(self, key: str) -> str:
        pair, tf, raw = parse_key(key, self.default_pair)
        return canonical_key(pair, tf, raw)

    def __setitem__(self, key, value):
        super().__setitem__(self._canon(key), value)

    def __getitem__(self, key):
        return super().__getitem__(self._canon(key))

    def __contains__(self, key):
        try:
            return super().__contains__(self._canon(key))
        except (ValueError, AttributeError):
            return False

    def get(self, key, default=None):
        return self[key] if key in self else default

    def sliced(self, start: pd.Timestamp, end: pd.Timestamp) -> "DataBundle":
        """Half-open [start, end) slice of every frame. Half-open on purpose:
        bars are left-labeled, so the bar labeled `end` opens AFTER the window
        and belongs to the next one (an inclusive .loc[start:end] would put
        the boundary bar in both a fit and its validate window)."""
        out = DataBundle(self.default_pair)
        for k, df in super().items():
            out[k] = df.loc[(df.index >= start) & (df.index < end)]
        return out


def _read_feather(path: Path) -> pd.DataFrame:
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df.set_index("date").sort_index()


def default_raw_dir(data_dir: Path) -> Path:
    return Path(data_dir).parent / "binance_raw"


def load_bundle(
    data_dir: Path,
    default_pair: str,
    keys: list[str],
    raw_dir: Path | None = None,
) -> DataBundle:
    data_dir = Path(data_dir)
    raw_dir = Path(raw_dir) if raw_dir is not None else default_raw_dir(data_dir)
    bundle = DataBundle(default_pair)
    missing = []
    for key in keys:
        pair, tf, force_raw = parse_key(key, default_pair)
        searched = [raw_dir] if force_raw else [data_dir, raw_dir]
        df = None
        for folder in searched:
            path = folder / f"{pair}-{tf}.feather"
            if path.exists():
                df = _read_feather(path)
                break
        if df is None:
            missing.append(f"{pair}-{tf}" + (" (raw)" if force_raw else ""))
        else:
            bundle[key] = df
    if missing:
        raise FileNotFoundError(f"No feather file for {', '.join(missing)} in {data_dir} or {raw_dir}")
    return bundle


if __name__ == "__main__":
    import tempfile

    assert parse_key("5m") == ("ETH_FDUSD", "5m", False)
    assert parse_key("eth/usdt:1m") == ("ETH_USDT", "1m", False)
    assert parse_key("ETH_FDUSD:1m:raw") == ("ETH_FDUSD", "1m", True)
    for bad in ("a:b:c", "a:b:raw:x"):
        try:
            parse_key(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(bad)

    idx = pd.date_range("2026-03-01", periods=10, freq="5min", tz="UTC")
    mk = lambda base: pd.DataFrame({"open": base, "high": base, "low": base, "close": base, "volume": 1.0}, index=idx)
    b = DataBundle("ETH_FDUSD")
    b["5m"] = mk(1.0)               # bare key -> default pair
    b["ETH/USDT:5m"] = mk(2.0)
    assert "ETH_FDUSD:5m" in b and "5m" in b and "ETH_USDT:5m" in b and "ETH/USDT:5m" in b
    assert "15m" not in b and "garbage:a:b:c" not in b
    assert b["5m"]["close"].iloc[0] == 1.0 and b["ETH_USDT:5m"]["close"].iloc[0] == 2.0
    assert b.get("15m") is None and sorted(b.keys()) == ["ETH_FDUSD:5m", "ETH_USDT:5m"]

    # Half-open slicing: the boundary bar belongs to exactly one window.
    fit = b.sliced(idx[0], idx[5])
    val = b.sliced(idx[5], idx[9])
    assert idx[5] not in fit["5m"].index and idx[5] in val["5m"].index
    assert fit["5m"].index.max() < val["5m"].index.min()
    assert isinstance(fit, DataBundle) and "5m" in fit and "ETH_USDT:5m" in fit

    # Loading: data-dir first, raw store for the rest, ":raw" forces the raw store.
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_dir, raw_dir = tmp / "binance", tmp / "binance_raw"
        data_dir.mkdir(); raw_dir.mkdir()
        for folder, pair, val_ in ((data_dir, "ETH_FDUSD", 1.0), (raw_dir, "ETH_USDT", 2.0), (raw_dir, "ETH_FDUSD", 9.0)):
            df = mk(val_).reset_index(names="date")
            df.to_feather(folder / f"{pair}-5m.feather")
        loaded = load_bundle(data_dir, "ETH_FDUSD", ["5m", "ETH_USDT:5m", "ETH_FDUSD:5m:raw"])
        assert loaded["5m"]["close"].iloc[0] == 1.0          # freqtrade file
        assert loaded["ETH_USDT:5m"]["close"].iloc[0] == 2.0  # found in raw store
        assert loaded["ETH_FDUSD:5m:raw"]["close"].iloc[0] == 9.0
        try:
            load_bundle(data_dir, "ETH_FDUSD", ["1h"])
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("missing file must raise")
    print("Self-test passed: bare-tf aliasing, PAIR:tf keys, raw-store routing, half-open slicing.")
