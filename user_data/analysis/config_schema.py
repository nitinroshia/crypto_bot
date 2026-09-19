"""
Task 5 — Config scaffolding.

Pure plumbing: a schema that lists available timeframes with an on/off flag
and lookback windows, so that testing timeframe combinations later is a
config edit, not a code change. Nothing in this file feeds into strategy
entry/exit logic -- that wiring is Phase 2, after Phase 1 findings are
reviewed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SUPPORTED_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "1d", "1w")


@dataclass
class TimeframeConfig:
    enabled: bool = False
    lookbacks: list[int] = field(default_factory=lambda: [1])


@dataclass
class MultiTimeframeConfig:
    primary_timeframe: str = "1m"
    timeframes: dict[str, TimeframeConfig] = field(default_factory=dict)

    def __post_init__(self):
        # Ensure every supported timeframe has an entry, defaulting to off,
        # so the config file is always self-documenting about what exists.
        for tf in SUPPORTED_TIMEFRAMES:
            if tf not in self.timeframes:
                self.timeframes[tf] = TimeframeConfig(enabled=(tf == self.primary_timeframe))
        if self.primary_timeframe not in SUPPORTED_TIMEFRAMES:
            raise ValueError(
                f"primary_timeframe '{self.primary_timeframe}' not in {SUPPORTED_TIMEFRAMES}"
            )

    def enabled_timeframes(self) -> list[str]:
        return [tf for tf, cfg in self.timeframes.items() if cfg.enabled]

    def to_dict(self) -> dict:
        return {
            "primary_timeframe": self.primary_timeframe,
            "timeframes": {tf: asdict(cfg) for tf, cfg in self.timeframes.items()},
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "MultiTimeframeConfig":
        raw = json.loads(Path(path).read_text())
        timeframes = {
            tf: TimeframeConfig(**cfg) for tf, cfg in raw.get("timeframes", {}).items()
        }
        return cls(primary_timeframe=raw.get("primary_timeframe", "1m"), timeframes=timeframes)


def default_config() -> MultiTimeframeConfig:
    """A starting point: only the primary timeframe on, everything else off,
    matching 'don't use all timeframes at once' from the discussion."""
    cfg = MultiTimeframeConfig(primary_timeframe="1m")
    cfg.timeframes["1m"].lookbacks = [1, 3, 5]
    return cfg


if __name__ == "__main__":
    import tempfile

    cfg = default_config()
    assert cfg.enabled_timeframes() == ["1m"], "only the primary timeframe should be on by default"

    # Round-trip through JSON to make sure save/load actually works.
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    cfg.save(path)
    loaded = MultiTimeframeConfig.load(path)
    assert loaded.enabled_timeframes() == ["1m"]
    assert loaded.timeframes["1m"].lookbacks == [1, 3, 5]

    # Confirm a timeframe can be toggled on purely via the config file, with
    # no code change, matching the point of this task.
    loaded.timeframes["5m"].enabled = True
    loaded.timeframes["5m"].lookbacks = [3]
    loaded.save(path)
    reloaded = MultiTimeframeConfig.load(path)
    assert sorted(reloaded.enabled_timeframes()) == ["1m", "5m"]

    print("Self-test passed: config save/load round-trips and toggling works without code changes.")
    print(json.dumps(reloaded.to_dict(), indent=2))