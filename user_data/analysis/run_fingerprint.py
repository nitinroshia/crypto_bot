"""
Entry point for Phase 1. Run this once real feather files exist under
user_data/data/binance/ (after download_data.sh). Produces the Task 3
fingerprint tables and Task 4 lead-lag tables, saved to analysis/results/.

Usage:
    python3 run_fingerprint.py --data-dir user_data/data/binance --pair ETH_FDUSD
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from config_schema import SUPPORTED_TIMEFRAMES
from leadlag import (
    align_to_common_grid,
    event_anchored_lead_lag,
    grid_returns,
    hac_lagged_regression,
    nonoverlapping_lagged_correlation,
    summarize_best_lag,
)
from multitest import annotate_family, bonferroni_adjust, family_stats_for_best, holm_adjust
from resample import TIMEFRAME_TO_PANDAS_RULE, compare_resampled_vs_native, resample_ohlcv
from stats_fingerprint import run_full_fingerprint

# Minutes per timeframe, used to (a) find the finer of a lead-lag pair so
# results are expressed in that timeframe's own units, and (b) size the
# upsample_factor so HAC/block-size corrections cover one full coarse window.
TIMEFRAME_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": 60 * 24, "1w": 60 * 24 * 7}


def load_native_feather(data_dir: Path, pair: str, timeframe: str) -> pd.DataFrame | None:
    path = data_dir / f"{pair}-{timeframe}.feather"
    if not path.exists():
        return None
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df.set_index("date")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("user_data/data/binance"))
    parser.add_argument("--pair", type=str, default="ETH_FDUSD")
    parser.add_argument(
        "--timeframes",
        nargs="+",
        default=list(SUPPORTED_TIMEFRAMES),
        help=f"subset of {SUPPORTED_TIMEFRAMES}",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("user_data/analysis/results"))
    parser.add_argument("--lead-lag-pairs", nargs="+", default=["1m:5m", "5m:15m", "5m:1h"])
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip the ADF autolag search (fixed maxlag=20 instead). Much faster, "
        "but don't trust the stationarity p-values from a --fast run -- use it only "
        "for checking that the pipeline itself runs, not for reading results.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Optional: drop every bar before this UTC date (e.g. 2026-01-30 for post-fee-break data "
        "only) from ALL timeframes before anything is computed. Results go to "
        "<output-dir>/from_<date>/ so the full-history results are never overwritten. "
        "Default: use everything, exactly as before.",
    )
    args = parser.parse_args()

    start_ts = pd.Timestamp(args.start_date, tz="UTC") if args.start_date else None
    if start_ts is not None:
        args.output_dir = args.output_dir / f"from_{args.start_date}"
        print(f"--start-date given: using only bars >= {start_ts}; writing to {args.output_dir}")

    def _trim(frame):
        return frame if (frame is None or start_ts is None) else frame.loc[frame.index >= start_ts]

    args.output_dir.mkdir(parents=True, exist_ok=True)

    df_1m = _trim(load_native_feather(args.data_dir, args.pair, "1m"))
    if df_1m is None:
        raise FileNotFoundError(
            f"No 1m feather found for {args.pair} in {args.data_dir}. "
            "Run download_data.sh first."
        )

    dataframes: dict[str, pd.DataFrame] = {"1m": df_1m}
    resample_checks: dict[str, dict] = {}

    for tf in args.timeframes:
        if tf == "1m":
            continue
        native = _trim(load_native_feather(args.data_dir, args.pair, tf))
        resampled = resample_ohlcv(df_1m, tf)
        if native is not None:
            resample_checks[tf] = compare_resampled_vs_native(resampled, native)
            # ALWAYS prefer the natively downloaded file when it exists --
            # it's the authoritative, exchange-computed source. A MISMATCH
            # here is a diagnostic finding about resampling limitations
            # (see diagnose_gaps.py), not a reason to fall back to derived
            # data. Only use the resampled version when no native file
            # exists at all.
            dataframes[tf] = native
        else:
            dataframes[tf] = resampled
            resample_checks[tf] = {"status": "NO_NATIVE_FILE_TO_COMPARE"}

    (args.output_dir / "resample_checks.json").write_text(json.dumps(resample_checks, indent=2))
    # Per-timeframe history actually used -- the 1m file can be much shorter
    # than the coarser native files, and every cross-timeframe result is
    # only as long as the shorter side.
    (args.output_dir / "data_ranges.json").write_text(
        json.dumps({tf: [str(d.index.min()), str(d.index.max()), int(len(d))] for tf, d in dataframes.items()}, indent=2)
    )
    print("Resample self-checks:")
    print(json.dumps(resample_checks, indent=2))

    fingerprints = {}
    for tf, df in dataframes.items():
        print(f"\nFingerprinting {tf} ({len(df)} rows)...")
        fingerprints[tf] = run_full_fingerprint(df, lookbacks=[1, 3, 5], adf_maxlag=(20 if args.fast else None))
    (args.output_dir / "fingerprints.json").write_text(json.dumps(fingerprints, indent=2, default=str))

    leadlag_results = {}
    event_frames: dict[str, pd.DataFrame] = {}
    for pair_spec in args.lead_lag_pairs:
        tf_a, tf_b = pair_spec.split(":")
        if tf_a not in dataframes or tf_b not in dataframes:
            print(f"Skipping {pair_spec}: missing timeframe data")
            continue
        returns_a = dataframes[tf_a]["close"].pct_change().dropna()
        returns_b = dataframes[tf_b]["close"].pct_change().dropna()

        # If tf_a and tf_b run at different native frequencies, align the
        # coarser one onto the finer one's grid BEFORE lag-shifting, so the
        # resulting "lag" is unambiguously in units of the finer timeframe
        # (minutes, in most cases here) rather than silently collapsing to
        # whichever timeframe happens to be coarser -- see align_to_common_grid's
        # docstring for why this matters and what was wrong before it existed.
        minutes_a, minutes_b = TIMEFRAME_MINUTES[tf_a], TIMEFRAME_MINUTES[tf_b]
        # shift_periods=1 (see align_to_common_grid's docstring): the coarse
        # series must represent the MOST RECENTLY CLOSED window, not the one
        # currently in progress -- otherwise a fine-grid return gets compared
        # against the very coarse return it's mechanically a sub-component
        # of, producing a spurious near-1.0 "lag=0" result. Confirmed this
        # was happening in real fingerprint data before this fix.
        coarse_native, fine_native = None, None
        if minutes_a == minutes_b:
            fine_a, fine_b = returns_a, returns_b
            upsample_factor = 1
            lag_unit = tf_a
        elif minutes_a < minutes_b:
            fine_a = returns_a
            fine_b = align_to_common_grid(returns_b, returns_a, shift_periods=1)
            upsample_factor = minutes_b // minutes_a
            lag_unit = tf_a
            coarse_native, fine_native = returns_b, returns_a
        else:
            fine_a = align_to_common_grid(returns_a, returns_b, shift_periods=1)
            fine_b = returns_b
            upsample_factor = minutes_a // minutes_b
            lag_unit = tf_b
            coarse_native, fine_native = returns_a, returns_b

        nonoverlap = nonoverlapping_lagged_correlation(fine_a, fine_b, max_lag=10, upsample_factor=upsample_factor)
        hac = hac_lagged_regression(fine_a, fine_b, max_lag=10, upsample_factor=upsample_factor)

        leadlag_results[pair_spec] = {
            "lag_unit": lag_unit,
            # KNOWN CONTAMINATED (project_context.md mistake #5): both of
            # these report their "best lag" landing on _clip_max_lag's
            # boundary because the clip only removes the single fully-
            # overlapping point, not the partial overlap that ramps up to
            # it below upsample_factor. Kept for comparison, not for
            # decisions -- see event_anchored_best below.
            "nonoverlapping_best": summarize_best_lag(nonoverlap, corr_col="correlation"),
            "hac_best": summarize_best_lag(hac, corr_col="beta"),
        }
        nonoverlap.to_csv(args.output_dir / f"leadlag_{tf_a}_{tf_b}_nonoverlap.csv", index=False)
        hac.to_csv(args.output_dir / f"leadlag_{tf_a}_{tf_b}_hac.csv", index=False)

        if coarse_native is not None:
            # Gap-aware native returns for the trusted path (a positional
            # pct_change() across a missing row spans more than one bar --
            # see leadlag.grid_returns).
            coarse_tf, fine_tf = (tf_b, tf_a) if minutes_a < minutes_b else (tf_a, tf_b)
            coarse_native = grid_returns(
                dataframes[coarse_tf]["close"], step=pd.Timedelta(minutes=TIMEFRAME_MINUTES[coarse_tf])
            )
            fine_native = grid_returns(
                dataframes[fine_tf]["close"], step=pd.Timedelta(minutes=TIMEFRAME_MINUTES[fine_tf])
            )
            # The trustworthy result: anchored once per closed coarse bar,
            # reading only fine-grid minutes at/after the close, so no lag
            # can ever land back inside the bar the coarse return is made
            # of. No upsample_factor ceiling needed -- test well past it to
            # see whether any effect decays or was only ever the artifact.
            event_anchored = event_anchored_lead_lag(
                coarse_native, fine_native, max_lag=max(15, upsample_factor * 3)
            )
            leadlag_results[pair_spec]["event_anchored_best"] = summarize_best_lag(
                event_anchored, corr_col="beta"
            )
            event_frames[pair_spec] = event_anchored

    # Work order #1: every result states its family size and adjusted p. Two
    # families are reported for each pair's event-anchored table: that pair's
    # own lags, and ALL lags across ALL pairs run here (e.g. 15 + 15 + 36 =
    # 66 tests for the three standard pairs). Bonferroni and Holm are both
    # given; neither is silently preferred.
    if event_frames:
        pooled = pd.concat(
            [df.assign(_pair=k) for k, df in event_frames.items() if "p_value_hac" in df.columns],
            ignore_index=True,
        ) if any("p_value_hac" in df.columns for df in event_frames.values()) else None
        if pooled is not None:
            pooled["_p_bonf_all"] = bonferroni_adjust(pooled["p_value_hac"].to_numpy())
            pooled["_p_holm_all"] = holm_adjust(pooled["p_value_hac"].to_numpy())
            n_all = int(pooled["p_value_hac"].notna().sum())
        for pair_spec, df in event_frames.items():
            tf_a, tf_b = pair_spec.split(":")
            annotated = annotate_family(df)
            best = leadlag_results[pair_spec]["event_anchored_best"]
            family = {"this_pair": family_stats_for_best(annotated, best)}
            if pooled is not None and "p_value_hac" in df.columns:
                sub_pool = pooled[pooled["_pair"] == pair_spec].reset_index(drop=True)
                annotated["family_size_all_pairs"] = n_all
                annotated["p_bonferroni_all_pairs"] = sub_pool["_p_bonf_all"].to_numpy()
                annotated["p_holm_all_pairs"] = sub_pool["_p_holm_all"].to_numpy()
                family["all_pairs_family_size"] = n_all
                if best.get("best_lag"):
                    lag_col = "lag_bars"
                    row = annotated[annotated[lag_col] == best["best_lag"][lag_col]].iloc[0]
                    family["p_bonferroni_all_pairs"] = float(row["p_bonferroni_all_pairs"])
                    family["p_holm_all_pairs"] = float(row["p_holm_all_pairs"])
            best["family"] = family
            annotated.to_csv(args.output_dir / f"leadlag_{tf_a}_{tf_b}_event_anchored.csv", index=False)

    (args.output_dir / "leadlag_summary.json").write_text(json.dumps(leadlag_results, indent=2, default=str))
    print("\nLead-lag summary:")
    print(json.dumps(leadlag_results, indent=2, default=str))

    print(f"\nAll results written to {args.output_dir}/")


if __name__ == "__main__":
    main()