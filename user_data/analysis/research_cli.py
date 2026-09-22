"""
research_cli.py — the one place to run a formula against real data.

FORMULA CONTRACT (read this before writing a new one; also documented in
project_context.md's "Formula contract" section for non-Python readers):

    def my_formula(*, data: dict[str, pd.DataFrame], max_lag: int, **params):
        ...
        return result_df, best_summary

  - `data` is every dataset you asked to load, keyed by string, each a raw
    OHLCV dataframe (columns: open, high, low, close, volume; datetime
    index). Keys are "PAIR:timeframe" (e.g. "ETH_USDT:1m"), and a bare
    timeframe ("1m", "5m", ...) means the same timeframe on the default
    pair, so every formula written against bare keys keeps working. Append
    ":raw" (e.g. "ETH_FDUSD:1m:raw") to read the raw-kline store, whose
    files also carry n_trades / taker_buy_* columns. See databundle.py.
    Pull whatever series and columns your idea needs out of this -- one,
    two, or all of them.
    Nothing about the CLI or the registry assumes you're comparing exactly
    two timeframes; that's just what the three built-in formulas happen to
    do.
  - `max_lag` is how far out to test. `**params` is whatever your formula
    needs beyond that (a timeframe pair, a lookback window, a weighting
    scheme) -- supplied on the command line as repeated `--param key=value`
    flags, or as prompts in guided mode if you add them there.
  - Return a DataFrame with one row per lag tested (columns: whatever your
    lag column is called, n, an effect-size column, and
    `significant_at_5pct`), plus a `summarize_best_lag(df, corr_col=...)`
    call on it for the second return value. That shared output shape is
    what makes manifests, walk-forward validation, and comparison across
    formulas all work the same way regardless of what the formula computes
    internally. summarize_best_lag's default (work order 1.2) picks the
    lag with the smallest p, with no "significant" pre-filter and not the
    largest effect size; see its docstring in leadlag.py.
  - The one question every formula must be able to answer "no" to before
    it's trusted: does this comparison let the same price data appear on
    both sides? (project_context.md's mistake log is the full explanation
    of why that question exists and what it catches.)

Two ways to run it:

  1. GUIDED MODE -- run with no --formula, and it prompts you for
     everything. Never touches a source file.

         python3 research_cli.py

  2. FLAG MODE -- for scripting and repeat runs:

         python3 research_cli.py --formula event_anchored --param pair=5m:15m --max-lag 20
         python3 research_cli.py --list-formulas

Every run, guided or flag, writes ONE manifest JSON to
analysis/results/runs/<run_id>.json: formula, every parameter, the
timeframes and data range actually used, the git commit (if this is a git
checkout), and the result. That folder is your experiment log.

Walk-forward validation (--walkforward) wires walkforward.py's
generate_walk_forward_splits to whichever formula you pick: run it on each
fit window, run it again on the corresponding validate window, and check
whether the same lag (same sign, within 1 step) shows up in both. A result
that replicates across every split is a real, evidenced finding. A result
found in fit that vanishes in validate was noise.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import statsmodels.api as sm

from config_schema import SUPPORTED_TIMEFRAMES
from databundle import DataBundle, load_bundle
from leadlag import (
    align_to_common_grid,
    event_anchored_lead_lag,
    grid_returns,
    hac_lagged_regression,
    nonoverlapping_lagged_correlation,
    summarize_best_lag,
)
from multitest import annotate_family, family_stats_for_best
from run_fingerprint import TIMEFRAME_MINUTES
from walkforward import generate_walk_forward_splits

# --------------------------------------------------------------------------
# Registry -- adding a new formula means adding one function here with a
# @register decorator, matching the contract in this file's module
# docstring. Nothing else in this file needs to know it exists.
# --------------------------------------------------------------------------
FORMULAS: dict[str, dict] = {}


def register(name: str, description: str):
    def wrap(fn):
        FORMULAS[name] = {"fn": fn, "description": description}
        return fn

    return wrap


def _prepare_pair(data: dict, pair: str) -> dict:
    """Shared by all three built-in formulas: given a 'tf_a:tf_b' pair
    string and the full data bundle, produce the aligned series each of
    them needs. A NEW formula does not have to use this at all -- it's
    just what a pairwise lead-lag test happens to need."""
    if not pair or ":" not in pair:
        raise ValueError("this formula needs --param pair=TF_A:TF_B, e.g. pair=5m:15m")
    tf_a, tf_b = pair.split(":")
    for tf in (tf_a, tf_b):
        if tf not in data:
            raise KeyError(f"timeframe '{tf}' was not loaded -- pass --timeframes including it")
    returns_a = data[tf_a]["close"].pct_change().dropna()
    returns_b = data[tf_b]["close"].pct_change().dropna()
    minutes_a, minutes_b = TIMEFRAME_MINUTES[tf_a], TIMEFRAME_MINUTES[tf_b]
    # Gap-aware returns for the event-anchored path only (a pct_change() across
    # a missing row spans more than one bar -- see leadlag.grid_returns). The
    # row-sliding hac/nonoverlap paths below keep their original inputs.
    grid_a = grid_returns(data[tf_a]["close"], step=pd.Timedelta(minutes=minutes_a))
    grid_b = grid_returns(data[tf_b]["close"], step=pd.Timedelta(minutes=minutes_b))
    coarse_native, fine_native = None, None
    if minutes_a == minutes_b:
        fine_a, fine_b = returns_a, returns_b
        upsample_factor = 1
    elif minutes_a < minutes_b:
        fine_a = returns_a
        fine_b = align_to_common_grid(returns_b, returns_a, shift_periods=1)
        upsample_factor = minutes_b // minutes_a
        coarse_native, fine_native = grid_b, grid_a
    else:
        fine_a = align_to_common_grid(returns_a, returns_b, shift_periods=1)
        fine_b = returns_b
        upsample_factor = minutes_a // minutes_b
        coarse_native, fine_native = grid_a, grid_b
    return dict(
        fine_a=fine_a, fine_b=fine_b, upsample_factor=upsample_factor,
        coarse_native=coarse_native, fine_native=fine_native,
    )


@register(
    "event_anchored",
    "TRUSTED for cross-timeframe pairs. Needs --param pair=TF_A:TF_B. Anchors "
    "once per closed coarse bar, tests fine-grid minutes at/after its close "
    "-- immune to the composition-overlap artifact (mistake #5).",
)
def _run_event_anchored(*, data, max_lag, pair=None, **_ignored):
    prepared = _prepare_pair(data, pair)
    if prepared["coarse_native"] is None:
        return None, {"status": "NOT_APPLICABLE", "reason": "same-timeframe pair -- nothing to anchor on"}
    df = event_anchored_lead_lag(prepared["coarse_native"], prepared["fine_native"], max_lag=max_lag)
    return df, summarize_best_lag(df, corr_col="beta")


@register(
    "hac",
    "KNOWN CONTAMINATED for cross-timeframe pairs (mistake #5) -- comparison/"
    "history only. Needs --param pair=TF_A:TF_B. HAC/Newey-West regression, "
    "row-sliding lag.",
)
def _run_hac(*, data, max_lag, pair=None, **_ignored):
    prepared = _prepare_pair(data, pair)
    df = hac_lagged_regression(prepared["fine_a"], prepared["fine_b"], max_lag=max_lag, upsample_factor=prepared["upsample_factor"])
    return df, summarize_best_lag(df, corr_col="beta")


@register(
    "nonoverlap",
    "KNOWN CONTAMINATED for cross-timeframe pairs (mistake #5) -- comparison/"
    "history only. Needs --param pair=TF_A:TF_B. Block-subsampled "
    "correlation, row-sliding lag.",
)
def _run_nonoverlap(*, data, max_lag, pair=None, **_ignored):
    prepared = _prepare_pair(data, pair)
    df = nonoverlapping_lagged_correlation(prepared["fine_a"], prepared["fine_b"], max_lag=max_lag, upsample_factor=prepared["upsample_factor"])
    return df, summarize_best_lag(df, corr_col="correlation")


@register(
    "volume_leads_volatility",
    "EXAMPLE of a non-pairwise formula -- single timeframe only (needs "
    "--param timeframe=5m, optional --param window=20). Tests whether "
    "elevated volume on a bar predicts a BIGGER absolute return `lag` bars "
    "later, same timeframe. This is a forward-looking extension of the "
    "project's own volume-participation finding, which only showed volume "
    "and move size are associated at the SAME bar -- not that one predicts "
    "the other. No pair, no upsample_factor, no mistake-#5 exposure: "
    "predictor and target are two different measurements of price action, "
    "never arithmetically built from each other, so this is safe at any "
    "lag including 0 (lag=0 is a contemporaneous check; lag>=1 is the new, "
    "genuinely predictive question).",
)
def _run_volume_leads_volatility(*, data, max_lag, timeframe=None, window=20, **_ignored):
    if not timeframe or timeframe not in data:
        raise ValueError("this formula needs --param timeframe=<one of the loaded timeframes>")
    df = data[timeframe]
    window = int(window)
    volume_ratio = df["volume"] / df["volume"].rolling(window, min_periods=window).median()
    abs_return = df["close"].pct_change().abs()

    rows = []
    for lag in range(0, max_lag + 1):
        combined = pd.DataFrame(
            {"volume_ratio": volume_ratio, "abs_return_future": abs_return.shift(-lag)}
        ).dropna()
        if len(combined) < 30:
            rows.append({"lag": lag, "n": len(combined), "status": "INSUFFICIENT_DATA"})
            continue
        X = sm.add_constant(combined["volume_ratio"])
        model = sm.OLS(combined["abs_return_future"], X).fit(cov_type="HAC", cov_kwds={"maxlags": max(max_lag, 1)})
        rows.append(
            {
                "lag": lag,
                "n": int(len(combined)),
                "beta": float(model.params["volume_ratio"]),
                "t_stat_hac": float(model.tvalues["volume_ratio"]),
                "p_value_hac": float(model.pvalues["volume_ratio"]),
                "significant_at_5pct": bool(model.pvalues["volume_ratio"] < 0.05),
            }
        )
    result = pd.DataFrame(rows)
    return result, summarize_best_lag(result, corr_col="beta")


# --------------------------------------------------------------------------
# Data loading -- loads every timeframe a run might need into one bundle.
# A formula reaches into `data[tf]` for whichever it actually uses.
# --------------------------------------------------------------------------
def load_all_dataframes(
    data_dir: Path, asset_pair: str, timeframes: list[str], raw_dir: Path | None = None
) -> DataBundle:
    """Every key in `timeframes` may be a bare timeframe (default pair), a
    PAIR:timeframe, or PAIR:timeframe:raw -- see databundle.py."""
    return load_bundle(data_dir, asset_pair, timeframes, raw_dir=raw_dir)


def _data_ranges(data: dict) -> dict:
    return {k: [str(df.index.min()), str(df.index.max()), int(len(df))] for k, df in data.items()}


def _infer_timeframes(explicit: list[str] | None, params: dict) -> list[str]:
    if explicit:
        return list(explicit)
    if params.get("pair") and ":" in params["pair"]:
        return list(params["pair"].split(":"))
    if params.get("timeframe"):
        return [params["timeframe"]]
    return list(SUPPORTED_TIMEFRAMES)


# --------------------------------------------------------------------------
# Manifests -- the experiment log. One JSON per run, ever appended to, never
# edited by hand.
# --------------------------------------------------------------------------
def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def git_commit_hash() -> str | None:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except Exception:
        return None


def write_manifest(output_dir: Path, run_id: str, record: dict) -> Path:
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{run_id}.json"
    path.write_text(json.dumps(record, indent=2, default=str))
    return path


# --------------------------------------------------------------------------
# Single run
# --------------------------------------------------------------------------
def run_once(formula_name, data_dir, asset_pair, params, max_lag, output_dir, timeframes=None, tag=None, raw_dir=None):
    tfs = _infer_timeframes(timeframes, params)
    data = load_all_dataframes(data_dir, asset_pair, tfs, raw_dir=raw_dir)
    result_df, best = FORMULAS[formula_name]["fn"](data=data, max_lag=max_lag, **params)
    # Work order #1: every result states its family size and adjusted p. The
    # family here is the lags this table tested; both Bonferroni and Holm are
    # recorded (see multitest.py) and neither is silently preferred.
    family = {}
    if result_df is not None and len(result_df):
        result_df = annotate_family(result_df)
        family = family_stats_for_best(result_df, best)

    tag_bits = "_".join(str(v) for v in params.values()).replace(":", "-") or "run"
    run_id = f"{_timestamp()}_{formula_name}_{tag_bits}" + (f"_{tag}" if tag else "")
    manifest = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit_hash(),
        "formula": formula_name,
        "formula_description": FORMULAS[formula_name]["description"],
        "asset_pair": asset_pair,
        "params": params,
        "max_lag": max_lag,
        "timeframes_loaded": tfs,
        "data_dir": str(data_dir),
        "data_date_range": [
            str(min(df.index.min() for df in data.values())),
            str(max(df.index.max() for df in data.values())),
        ],
        "data_ranges": _data_ranges(data),
        "result": best,
        "family": family,
    }
    if result_df is not None and len(result_df):
        csv_path = output_dir / "runs" / f"{run_id}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(csv_path, index=False)
        manifest["result_csv"] = str(csv_path)
    manifest_path = write_manifest(output_dir, run_id, manifest)
    return manifest, manifest_path


# --------------------------------------------------------------------------
# Walk-forward validation
# --------------------------------------------------------------------------
def _first_col(row_or_df_cols, prefix=None, names=None):
    cols = list(row_or_df_cols)
    if names:
        return next((n for n in names if n in cols), None)
    return next((c for c in cols if c.startswith(prefix)), None)


def evaluate_fixed_lag(fit_best: dict, fit_df, val_df) -> dict:
    """
    Walk-forward verdict for ONE split, per work order #1: the lag is chosen
    in the FIT window only, and the VALIDATE window is asked one
    pre-specified question -- at that same lag, is the effect the same sign
    and significant at 5%? (One lag, one test: no family, no adjustment.)

    The previous version re-ran the whole lag scan in validate and compared
    "best lag within 1 step", which lets validate pick its own winner among
    many lags -- a multiple-testing leak that flatters replication.
    """
    fit_row = fit_best.get("best_lag") if isinstance(fit_best, dict) else None
    if not fit_row:
        return {"replicated": False, "reason": "NO_SIGNIFICANT_LAG_IN_FIT"}
    lag_col = _first_col(fit_row.keys(), prefix="lag")
    eff_col = _first_col(fit_row.keys(), names=("beta", "correlation"))
    p_col = _first_col(fit_row.keys(), names=("p_value_hac", "p_value"))
    fit_lag = fit_row[lag_col]
    out = {
        "fit_lag": fit_lag,
        "fit_effect": float(fit_row[eff_col]),
        "fit_p": float(fit_row[p_col]) if p_col else None,
        "fit_n": int(fit_row["n"]) if "n" in fit_row else None,
    }
    if "lag_minutes" in fit_row:
        out["fit_lag_minutes"] = float(fit_row["lag_minutes"])
    if "correlation" in fit_row and eff_col != "correlation":
        out["fit_correlation"] = float(fit_row["correlation"])
    if fit_df is not None and len(fit_df):
        out["fit_family"] = family_stats_for_best(annotate_family(fit_df), fit_best)
    if val_df is None or not len(val_df) or lag_col not in val_df.columns or eff_col not in val_df.columns:
        return {**out, "replicated": False, "reason": "VALIDATE_TABLE_UNAVAILABLE"}
    match = val_df[val_df[lag_col] == fit_lag]
    if match.empty or pd.isna(match.iloc[0][eff_col]):
        return {**out, "replicated": False, "reason": "VALIDATE_INSUFFICIENT_DATA_AT_FIT_LAG"}
    v = match.iloc[0]
    same_sign = bool((v[eff_col] > 0) == (fit_row[eff_col] > 0))
    val_sig = bool(v["significant_at_5pct"])
    out.update(
        {
            "validate_effect_at_fit_lag": float(v[eff_col]),
            "validate_correlation_at_fit_lag": float(v["correlation"]) if "correlation" in v.index and not pd.isna(v["correlation"]) else None,
            "validate_p_at_fit_lag": float(v[p_col]) if p_col and p_col in v else None,
            "validate_n": int(v["n"]),
            "same_sign": same_sign,
            "validate_significant": val_sig,
            "replicated": same_sign and val_sig,
            "reason": "OK" if (same_sign and val_sig)
            else ("SIGN_FLIPPED" if not same_sign else "NOT_SIGNIFICANT_IN_VALIDATE"),
        }
    )
    return out


def run_walkforward(
    formula_name, data_dir, asset_pair, params, max_lag, fit_days, validate_days, step_days, output_dir,
    timeframes=None, raw_dir=None,
):
    tfs = _infer_timeframes(timeframes, params)
    data = load_all_dataframes(data_dir, asset_pair, tfs, raw_dir=raw_dir)
    start = max(df.index.min() for df in data.values())
    end = min(df.index.max() for df in data.values())

    splits = generate_walk_forward_splits(
        start=start,
        end=end,
        fit_period=pd.Timedelta(days=fit_days),
        validate_period=pd.Timedelta(days=validate_days),
        step=pd.Timedelta(days=step_days) if step_days else None,
    )
    if not splits:
        print(
            f"No splits fit in the available range ({start.date()} to {end.date()}) "
            f"with fit={fit_days}d / validate={validate_days}d -- try shorter windows."
        )
        return None

    fn = FORMULAS[formula_name]["fn"]
    split_results = []
    for i, s in enumerate(splits):
        # Half-open windows [start, end): the bar labeled fit_end opens after
        # the fit window and belongs to validate, never to both.
        fit_data = data.sliced(s.fit_start, s.fit_end)
        val_data = data.sliced(s.validate_start, s.validate_end)
        fit_df, fit_best = fn(data=fit_data, max_lag=max_lag, **params)
        val_df, _val_rescan_best = fn(data=val_data, max_lag=max_lag, **params)  # only the fit-selected lag's row is read
        ev = evaluate_fixed_lag(fit_best, fit_df, val_df)
        split_results.append(
            {
                "split": i,
                "fit_range": [str(s.fit_start.date()), str(s.fit_end.date())],
                "validate_range": [str(s.validate_start.date()), str(s.validate_end.date())],
                "fit_best": fit_best,
                **ev,
            }
        )
        if "fit_lag" in ev:
            fam = ev.get("fit_family", {})
            fam_txt = f" (fit family {fam['family_size']}, Holm p={fam['p_holm']:.3g})" if fam else ""
            val_txt = (
                f"validate @ lag {ev['fit_lag']}: effect={ev['validate_effect_at_fit_lag']:+.4g} "
                f"p={ev['validate_p_at_fit_lag']:.3g} n={ev['validate_n']}"
                if "validate_effect_at_fit_lag" in ev else f"validate: {ev['reason']}"
            )
            print(
                f"Split {i}: fit lag={ev['fit_lag']} effect={ev['fit_effect']:+.4g} p={ev['fit_p']:.3g}{fam_txt} "
                f"-> {val_txt} -- {'REPLICATED' if ev['replicated'] else 'did not replicate (' + ev['reason'] + ')'}"
            )
        else:
            print(f"Split {i}: {ev['reason']} -- did not replicate")

    n_replicated = sum(1 for r in split_results if r["replicated"])
    if len(splits) < 2:
        verdict = "NOT ENOUGH SPLITS TO JUDGE -- widen the date range or shorten fit/validate windows"
    elif n_replicated == len(splits):
        verdict = f"{n_replicated}/{len(splits)} splits replicated -- treat as a real, walk-forward-supported finding"
    elif n_replicated > 0:
        verdict = f"{n_replicated}/{len(splits)} splits replicated -- inconsistent across time, treat with caution"
    else:
        verdict = f"0/{len(splits)} splits replicated -- did not survive out-of-sample, treat as noise"

    tag_bits = "_".join(str(v) for v in params.values()).replace(":", "-") or "run"
    run_id = f"{_timestamp()}_{formula_name}_{tag_bits}_walkforward"
    manifest = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit_hash(),
        "formula": formula_name,
        "mode": "walkforward",
        "validation_rule": "lag chosen in fit only; validate tests that single lag (same sign AND p<0.05); "
                           "windows are half-open [start, end)",
        "asset_pair": asset_pair,
        "params": params,
        "max_lag": max_lag,
        "timeframes_loaded": tfs,
        "data_ranges": _data_ranges(data),
        "fit_days": fit_days,
        "validate_days": validate_days,
        "step_days": step_days or validate_days,
        "n_splits": len(splits),
        "n_replicated": n_replicated,
        "splits": split_results,
        "verdict": verdict,
    }
    write_manifest(output_dir, run_id, manifest)
    print(f"\nVerdict: {verdict}")
    return manifest


# --------------------------------------------------------------------------
# Guided mode -- plain input() prompts, no new dependency.
# --------------------------------------------------------------------------
def _prompt_choice(prompt: str, choices: list[str]) -> str:
    while True:
        raw = input(prompt).strip()
        if raw in choices:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        print(f"  Please enter one of: {', '.join(choices)} (or its number)")


def _prompt_text(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [default {default}]: ").strip()
    return raw if raw else default


def _prompt_int(prompt: str, default):
    raw = input(f"{prompt} [default {default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("  Please enter a whole number.")
        return _prompt_int(prompt, default)


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    raw = input(f"{prompt} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    if not raw:
        return default
    return raw.startswith("y")


def guided_mode(args) -> None:
    print("=== Research CLI -- guided mode ===")
    print("Answer the prompts; nothing here touches any source file.\n")
    print("Available formulas:")
    names = list(FORMULAS.keys())
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name} -- {FORMULAS[name]['description']}")
    formula_name = _prompt_choice("\nPick a formula (number or name): ", names)

    params: dict = {}
    pair_spec = _prompt_text("\nTimeframe pair this formula needs, e.g. 5m:15m (leave blank if not needed)", "5m:15m")
    if pair_spec:
        params["pair"] = pair_spec
    extra = _prompt_text("Any other params as key=value,key2=value2 (blank for none)", "")
    if extra:
        for kv in extra.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k.strip()] = v.strip()

    max_lag = _prompt_int("Max lag to test", 20)
    asset_pair = _prompt_text("Asset pair", args.pair)
    data_dir = Path(_prompt_text("Data directory", str(args.data_dir)))

    do_wf = _prompt_yes_no("\nRun as a walk-forward validation instead of a single pass?", default=False)
    if do_wf:
        fit_days = _prompt_int("Fit window, days", 270)
        validate_days = _prompt_int("Validate window, days", 90)
        step_days = _prompt_int("Step forward, days (0 = same as validate window)", 0) or None
        run_walkforward(formula_name, data_dir, asset_pair, params, max_lag, fit_days, validate_days, step_days, args.output_dir)
    else:
        manifest, path = run_once(formula_name, data_dir, asset_pair, params, max_lag, args.output_dir)
        print(f"\nResult:\n{json.dumps(manifest['result'], indent=2, default=str)}")
        print(f"\nManifest written to {path}")


# --------------------------------------------------------------------------
# Flag mode / entry point
# --------------------------------------------------------------------------
class _ParamAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        d = getattr(namespace, self.dest) or {}
        if "=" not in values:
            parser.error(f"--param must be key=value, got: {values}")
        k, v = values.split("=", 1)
        d[k.strip()] = v.strip()
        setattr(namespace, self.dest, d)


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("user_data/data/binance"))
    p.add_argument("--raw-dir", type=Path, default=None,
                    help="raw-kline store (default: <data-dir>/../binance_raw); used for PAIR:tf keys "
                         "not found in --data-dir and for any key ending in :raw")
    p.add_argument("--pair", type=str, default="ETH_FDUSD", help="asset pair, e.g. ETH_FDUSD")
    p.add_argument("--output-dir", type=Path, default=Path("user_data/analysis/results"))
    p.add_argument("--formula", choices=list(FORMULAS), help="which registered formula to run")
    p.add_argument("--param", action=_ParamAction, default={}, metavar="key=value",
                    help="repeatable, e.g. --param pair=5m:15m --param lookback=10")
    p.add_argument("--lead-lag-pair", type=str, default=None,
                    help="shortcut for --param pair=TF_A:TF_B, kept for the three built-in formulas")
    p.add_argument("--timeframes", nargs="+", default=None,
                    help="which timeframes to load; default: inferred from --param pair=A:B or "
                         "--param timeframe=X, else all of " + str(SUPPORTED_TIMEFRAMES))
    p.add_argument("--max-lag", type=int, default=20)
    p.add_argument("--list-formulas", action="store_true")
    p.add_argument("--walkforward", action="store_true", help="validate out-of-sample instead of a single pass")
    p.add_argument("--fit-days", type=int, default=270)
    p.add_argument("--validate-days", type=int, default=90)
    p.add_argument("--step-days", type=int, default=None)
    return p


def main() -> None:
    args = build_argparser().parse_args()

    if args.list_formulas:
        for name, meta in FORMULAS.items():
            print(f"{name}: {meta['description']}")
        return

    params = dict(args.param)
    if args.lead_lag_pair:
        params.setdefault("pair", args.lead_lag_pair)

    if args.formula is None or (not params and args.lead_lag_pair is None):
        guided_mode(args)
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.walkforward:
        run_walkforward(
            args.formula, args.data_dir, args.pair, params, args.max_lag,
            args.fit_days, args.validate_days, args.step_days, args.output_dir,
            timeframes=args.timeframes, raw_dir=args.raw_dir,
        )
    else:
        manifest, path = run_once(args.formula, args.data_dir, args.pair, params, args.max_lag, args.output_dir, timeframes=args.timeframes, raw_dir=args.raw_dir)
        print(json.dumps(manifest, indent=2, default=str))
        print(f"\nManifest: {path}")


if __name__ == "__main__":
    main()