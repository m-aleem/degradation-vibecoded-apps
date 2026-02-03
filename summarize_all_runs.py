#!/usr/bin/env python3
"""
summarize_all_runs.py

Purpose
-------
produce ONE summary row per application (6 rows total), containing:

  memory_slope_mib_per_hour
  memory_mk_pvalue
  p95_slope_ms_per_hour
  p95_mk_pvalue
  delta_memory_early_late
  delta_p95_early_late
  total_errors

Why these statistics?
---------------------
- Performance and resource measurements are noisy and often non-normal.
- MK is a non-parametric trend test: it does not assume a normal distribution.
- Theil–Sen slope is robust: a few spikes/outliers do not dominate the slope.
- We compute p95 latency in time bins because raw per-request latency is very noisy,
  and the paper focuses on long-run degradation patterns.

Important design choices (transparent + defensible):
----------------------------------------------------
1) Warm-up exclusion:
   We discard the first --warmup-hours (default 0.5h) to avoid startup effects
   (cache warm-up, initialization) being misinterpreted as aging.

2) p95 on "served" requests by default:
   If an app rate-limits heavily (e.g., HTTP 429), response times for rejected
   requests can look artificially low. By default we compute p95 trends on requests
   that were truly served successfully (success==True and HTTP < 400).
   You can override with --latency-filter all.

3) Memory series selection:
   If monitor_results.csv contains project-level aggregation (scope == "project" or
   container_name == "ALL"), we use it. Otherwise, we aggregate by summing container
   memory across containers at each timestamp.

Usage
-----
From repo root:
  python3 summarize_all_runs.py --test-root ./Test --out summary.csv

Optional:
  --warmup-hours 1.0
  --bin-minutes 5
  --latency-filter all
"""

from __future__ import annotations

import argparse
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import theilslopes, norm


# -----------------------------
# Trend statistics
# -----------------------------

def mann_kendall_pvalue(y: np.ndarray) -> float:
    """
    Mann–Kendall (MK) test for monotonic trend (two-sided p-value).

    Intuition:
    - Compare all pairs of points (i<j).
    - Count how often y[j] > y[i] (up) vs y[j] < y[i] (down).
    - If there are many more "up" than "down" pairs, the series has an upward trend.

    Implementation notes:
    - Includes tie correction (repeated equal values).
    - Returns NaN if fewer than 3 points.
    """
    y = np.asarray(y, dtype=float)
    y = y[~np.isnan(y)]
    n = len(y)
    if n < 3:
        return float("nan")

    # S statistic
    S = 0
    for k in range(n - 1):
        S += np.sign(y[k + 1:] - y[k]).sum()

    # Tie correction
    _, counts = np.unique(y, return_counts=True)
    tie_term = np.sum(counts * (counts - 1) * (2 * counts + 5))
    varS = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    if varS <= 0:
        return 1.0

    # Continuity correction
    if S > 0:
        z = (S - 1) / math.sqrt(varS)
    elif S < 0:
        z = (S + 1) / math.sqrt(varS)
    else:
        z = 0.0

    p = 2 * (1 - norm.cdf(abs(z)))
    return float(p)


def theil_sen_slope(y: np.ndarray, x: np.ndarray) -> float:
    """
    Robust slope estimate (Sen's slope / Theil–Sen estimator).

    Computes slopes between all pairs:
      (y[j] - y[i]) / (x[j] - x[i])
    and returns the median slope (robust to outliers).

    Returns NaN if fewer than 2 valid points.
    """
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    m = ~np.isnan(y) & ~np.isnan(x)
    y = y[m]
    x = x[m]
    if len(y) < 2:
        return float("nan")
    slope, intercept, lo, hi = theilslopes(y, x)
    return float(slope)


# -----------------------------
# Parsing helpers
# -----------------------------

def _to_bool(v) -> bool:
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    s = str(v).strip().lower()
    return s in {"true", "1", "yes", "y"}


def _to_int_or_nan(v) -> float:
    try:
        return int(str(v).strip())
    except Exception:
        return float("nan")


def read_jmeter_jtl(path: Path) -> pd.DataFrame:
    """
    Read JMeter output from .jtl.

    JMeter can output either:
    - CSV (common when explicitly configured)
    - XML (default in some setups)

    This function tries CSV first; if that fails, parses XML.

    Returns a DataFrame with at least:
      timeStamp (ms epoch),
      elapsed (ms),
      success (bool),
      responseCode (string/int when possible)
    """
    # Try CSV
    try:
        df = pd.read_csv(path)
        if {"timeStamp", "elapsed", "success"}.issubset(df.columns):
            return df
    except Exception:
        pass

    # Fallback: XML
    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        raise ValueError(f"Could not parse {path} as CSV or XML: {e}")

    # JMeter XML has <httpSample> and/or <sample> nodes with attributes:
    # t (elapsed), ts (timestamp), s (success), rc (response code), lb (label)
    rows = []
    for node in root.iter():
        if node.tag not in {"httpSample", "sample"}:
            continue
        rows.append({
            "timeStamp": node.attrib.get("ts"),
            "elapsed": node.attrib.get("t"),
            "success": node.attrib.get("s"),
            "responseCode": node.attrib.get("rc"),
            "label": node.attrib.get("lb"),
            "responseMessage": node.attrib.get("rm"),
        })

    if not rows:
        raise ValueError(f"No JMeter sample nodes found in XML JTL: {path}")

    df = pd.DataFrame(rows)
    # Cast minimal schema
    df["timeStamp"] = pd.to_numeric(df["timeStamp"], errors="coerce")
    df["elapsed"] = pd.to_numeric(df["elapsed"], errors="coerce")
    df["success"] = df["success"].apply(_to_bool)
    return df


def read_monitor_csv(path: Path) -> pd.DataFrame:
    """
    Read monitor_results.csv from monitor_docker.py.

    Expected columns (based on your shared example):
      timestamp (ms epoch),
      scope (container/project),
      container_name (string; 'ALL' for project in some cases),
      memory_mib (float),
      cpu_percent (float),
      ... other columns may exist

    Returns DataFrame sorted by timestamp.
    """
    df = pd.read_csv(path)
    if "timestamp" not in df.columns:
        raise ValueError(f"{path} missing 'timestamp' column")
    df = df.sort_values("timestamp")
    return df


# -----------------------------
# Metric computations
# -----------------------------

def build_memory_series(monitor: pd.DataFrame) -> pd.DataFrame:
    """
    Produce a single memory time series (timestamp, memory_mib) for the "project".

    Preference order:
    1) scope == 'project' rows (if present)
    2) container_name == 'ALL' rows (if present)
    3) else: sum container memory across containers at each timestamp
    """
    df = monitor.copy()

    if "scope" in df.columns and (df["scope"] == "project").any():
        proj = df[df["scope"] == "project"].copy()
        return proj[["timestamp", "memory_mib"]].dropna()

    if "container_name" in df.columns and (df["container_name"] == "ALL").any():
        proj = df[df["container_name"] == "ALL"].copy()
        return proj[["timestamp", "memory_mib"]].dropna()

    # Fallback: aggregate containers
    if "container_name" not in df.columns:
        raise ValueError("monitor_results.csv lacks both project markers and container_name; cannot aggregate.")

    # Some monitors report one row per container per sample time.
    agg = df.groupby("timestamp", as_index=False)["memory_mib"].sum()
    return agg[["timestamp", "memory_mib"]].dropna()


def compute_memory_metrics(
    monitor_path: Path,
    warmup_hours: float,
    early_start_h: float,
    early_end_h: float,
    late_duration_h: float,
) -> Tuple[float, float, float]:
    """
    Returns:
      memory_slope_mib_per_hour,
      memory_mk_pvalue,
      delta_memory_early_late  (median late window - median early window)
    """
    mon = read_monitor_csv(monitor_path)
    series = build_memory_series(mon).sort_values("timestamp")

    t0 = float(series["timestamp"].iloc[0])
    series["t_hours"] = (series["timestamp"] - t0) / 1000.0 / 3600.0

    # Warm-up exclusion
    series = series[series["t_hours"] >= warmup_hours].copy()
    if len(series) < 3:
        return float("nan"), float("nan"), float("nan")

    y = series["memory_mib"].to_numpy(dtype=float)
    x = series["t_hours"].to_numpy(dtype=float)

    slope = theil_sen_slope(y, x)
    pval = mann_kendall_pvalue(y)

    tmax = float(np.nanmax(x))
    early = series[(series["t_hours"] >= early_start_h) & (series["t_hours"] < early_end_h)]["memory_mib"]
    late_start = max(warmup_hours, tmax - late_duration_h)
    late = series[(series["t_hours"] >= late_start) & (series["t_hours"] <= tmax)]["memory_mib"]

    delta = float("nan")
    if len(early) > 0 and len(late) > 0:
        delta = float(np.nanmedian(late) - np.nanmedian(early))

    return slope, pval, delta


def compute_latency_metrics(
    jtl_path: Path,
    warmup_hours: float,
    early_start_h: float,
    early_end_h: float,
    late_duration_h: float,
    bin_minutes: int,
    latency_filter: str,
    min_samples_per_bin: int,
) -> Tuple[float, float, float, int]:
    """
    Builds a binned p95 latency series and computes:
      p95_slope_ms_per_hour,
      p95_mk_pvalue,
      delta_p95_early_late,
      total_errors

    total_errors definition:
      error if (success == False) OR (HTTP responseCode >= 400) OR responseCode is missing/non-numeric.

    latency_filter:
      - 'http<400' (default): use successful requests with HTTP < 400 for p95 time series.
      - 'success': use success==True regardless of HTTP code parsing.
      - 'all': include all requests (including 429/403); can be misleading if rate-limiting dominates.
    """
    j = read_jmeter_jtl(jtl_path).sort_values("timeStamp").copy()

    if not {"timeStamp", "elapsed", "success"}.issubset(j.columns):
        raise ValueError(f"Unexpected JMeter schema in {jtl_path}")

    j["success_bool"] = j["success"].apply(_to_bool)
    if "responseCode" in j.columns:
        j["resp_int"] = j["responseCode"].apply(_to_int_or_nan)
    else:
        j["resp_int"] = float("nan")

    # Total errors (independent of latency filter)
    error_mask = (~j["success_bool"]) | (j["resp_int"] >= 400) | (j["resp_int"].isna())
    total_errors = int(error_mask.sum())

    # Time axis
    t0 = float(pd.to_numeric(j["timeStamp"], errors="coerce").dropna().iloc[0])
    j["t_hours"] = (pd.to_numeric(j["timeStamp"], errors="coerce") - t0) / 1000.0 / 3600.0
    j = j.dropna(subset=["t_hours", "elapsed"]).copy()

    # Warm-up exclusion
    j = j[j["t_hours"] >= warmup_hours].copy()
    if len(j) < 10:
        return float("nan"), float("nan"), float("nan"), total_errors

    # Latency subset
    if latency_filter == "all":
        jj = j
    elif latency_filter == "success":
        jj = j[j["success_bool"] == True]
    elif latency_filter == "http<400":
        jj = j[(j["success_bool"] == True) & (j["resp_int"] < 400)]
    else:
        raise ValueError("--latency-filter must be one of: all, success, http<400")

    if len(jj) < 10:
        return float("nan"), float("nan"), float("nan"), total_errors

    # Bin by time to compute p95 per bin
    jj["t_minutes"] = jj["t_hours"] * 60.0
    jj["bin"] = (jj["t_minutes"] // bin_minutes).astype(int)

    g = jj.groupby("bin")["elapsed"]
    p95 = g.quantile(0.95)
    cnt = g.size()

    valid_bins = cnt[cnt >= min_samples_per_bin].index
    p95 = p95.loc[valid_bins].astype(float)

    if len(p95) < 5:
        return float("nan"), float("nan"), float("nan"), total_errors

    bins = p95.index.to_numpy(dtype=int)
    t_hours = bins * (bin_minutes / 60.0)
    y = p95.to_numpy(dtype=float)

    slope = theil_sen_slope(y, t_hours)
    pval = mann_kendall_pvalue(y)

    # Early vs late delta
    tmax = float(np.nanmax(t_hours))
    early_mask = (t_hours >= early_start_h) & (t_hours < early_end_h)
    late_start = max(warmup_hours, tmax - late_duration_h)
    late_mask = (t_hours >= late_start) & (t_hours <= tmax)

    delta = float("nan")
    if early_mask.any() and late_mask.any():
        delta = float(np.nanmedian(y[late_mask]) - np.nanmedian(y[early_mask]))

    return slope, pval, delta, total_errors


# -----------------------------
# Run discovery + orchestration
# -----------------------------

@dataclass
class SummaryRow:
    app_name: str
    memory_slope_mib_per_hour: float
    memory_mk_pvalue: float
    p95_slope_ms_per_hour: float
    p95_mk_pvalue: float
    delta_memory_early_late: float
    delta_p95_early_late: float
    total_errors: int


def discover_runs(test_root: Path) -> List[Tuple[str, Path, Path]]:
    """
    Discover runs by looking for:
      Test/<APP>/Output/monitor_results.csv
      Test/<APP>/Output/jmeter_results.jtl

    Returns list of tuples:
      (app_name, monitor_path, jmeter_path)

    If an app folder exists but lacks outputs, it is skipped.
    """
    runs = []
    for app_dir in sorted([p for p in test_root.iterdir() if p.is_dir()]):
        out_dir = app_dir / "Output"
        monitor_path = out_dir / "monitor_results.csv"
        jmeter_path = out_dir / "jmeter_results.jtl"
        if monitor_path.exists() and jmeter_path.exists():
            runs.append((app_dir.name, monitor_path, jmeter_path))
    return runs


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize Mishaal SE experiment outputs into a 6-row table.")
    ap.add_argument("--test-root", required=True, help="Path to Test/ directory (e.g., ./Test)")
    ap.add_argument("--out", default="summary.csv", help="Output summary CSV")
    ap.add_argument("--warmup-hours", type=float, default=0.5, help="Warm-up to exclude (hours)")
    ap.add_argument("--early-start-hours", type=float, default=1.0, help="Early window start (hours)")
    ap.add_argument("--early-end-hours", type=float, default=2.0, help="Early window end (hours)")
    ap.add_argument("--late-duration-hours", type=float, default=2.0, help="Late window duration (hours)")
    ap.add_argument("--bin-minutes", type=int, default=1, help="Bin size (minutes) for p95 time series")
    ap.add_argument("--latency-filter", choices=["all", "success", "http<400"], default="http<400",
                    help="Which requests to include for p95 trend calculation")
    ap.add_argument("--min-samples-per-bin", type=int, default=5, help="Minimum samples per bin for p95")
    args = ap.parse_args()

    test_root = Path(args.test_root).expanduser().resolve()
    if not test_root.exists():
        raise SystemExit(f"Test root not found: {test_root}")

    runs = discover_runs(test_root)
    if not runs:
        raise SystemExit(f"No runs discovered under {test_root}. Expected Test/<APP>/Output/*.csv/.jtl")

    rows: List[SummaryRow] = []
    for app_name, monitor_path, jmeter_path in runs:
        mem_slope, mem_p, mem_delta = compute_memory_metrics(
            monitor_path=monitor_path,
            warmup_hours=args.warmup_hours,
            early_start_h=args.early_start_hours,
            early_end_h=args.early_end_hours,
            late_duration_h=args.late_duration_hours,
        )
        p95_slope, p95_p, p95_delta, total_errors = compute_latency_metrics(
            jtl_path=jmeter_path,
            warmup_hours=args.warmup_hours,
            early_start_h=args.early_start_hours,
            early_end_h=args.early_end_hours,
            late_duration_h=args.late_duration_hours,
            bin_minutes=args.bin_minutes,
            latency_filter=args.latency_filter,
            min_samples_per_bin=args.min_samples_per_bin,
        )

        rows.append(SummaryRow(
            app_name=app_name,
            memory_slope_mib_per_hour=mem_slope,
            memory_mk_pvalue=mem_p,
            p95_slope_ms_per_hour=p95_slope,
            p95_mk_pvalue=p95_p,
            delta_memory_early_late=mem_delta,
            delta_p95_early_late=p95_delta,
            total_errors=total_errors,
        ))

    df = pd.DataFrame([r.__dict__ for r in rows]).sort_values("app_name").reset_index(drop=True)
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    # Print for quick inspection
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(df)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
