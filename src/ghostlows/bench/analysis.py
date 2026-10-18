"""Pre-registered contrasts for H1-H2 (RESEARCH.md §3, D6).

H2: rate ratio of compression false alarms per night, [CGM + time + IOB/COB] over [CGM + time],
per detector and scenario mix, with a paired patient bootstrap (same patients, faults and seeds
in both arms). H1: per-patient least-squares slope of false alarms per day against the fraction
of compressed nights, trend minus threshold.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .stats import bootstrap_ci

SESOI_RATE_RATIO = 0.75  # ASSUMPTION: smallest effect size of interest for H2 (CR9, CR16)
CONTEXT_ARM, BASE_ARM = "_combined_time_ctx", "_combined_time"


def h2_reading(estimate: float, lo: float, hi: float, sesoi: float = SESOI_RATE_RATIO) -> str:
    """The pre-registered reading of a rate ratio and its CI (RESEARCH.md §3)."""
    if not np.isfinite(estimate):
        return "not estimable"
    if hi < 1 and estimate <= sesoi:
        return "meaningful reduction"
    if lo > sesoi:
        return "no meaningful reduction"
    return "inconclusive"


def context_contrasts(
    metrics: pd.DataFrame, n_boot: int = 2000, cause: str = "compression"
) -> pd.DataFrame:
    """H2 rate ratios per detector x fault level x mix, paired over patients."""
    col = f"false_{cause}" if cause else "n_false"
    rows = []
    detectors = sorted(
        {n[: -len(CONTEXT_ARM)] for n in metrics["alarm_name"] if n.endswith(CONTEXT_ARM)}
    )
    for det in detectors:
        a, b = det + CONTEXT_ARM, det + BASE_ARM
        sub = metrics[metrics["alarm_name"].isin([a, b])]
        for key, g in sub.groupby(["level", "mix"]):
            pp = g.pivot_table(
                index="patient_id", columns="alarm_name", values=col, aggfunc="sum"
            ).reset_index()
            if a not in pp or b not in pp:
                continue

            def ratio(df, a=a, b=b):
                den = df[b].sum()
                return float(df[a].sum() / den) if den > 0 else float("nan")

            est, lo, hi = bootstrap_ci(pp, ratio, n_boot=n_boot)
            rows.append(
                {
                    "detector": det,
                    "level": key[0],
                    "mix": key[1],
                    "cause": cause or "all",
                    "count_context": float(pp[a].sum()),
                    "count_base": float(pp[b].sum()),
                    "rate_ratio": est,
                    "lo": lo,
                    "hi": hi,
                    "reading": h2_reading(est, lo, hi),
                }
            )
    columns = [
        "detector",
        "level",
        "mix",
        "cause",
        "count_context",
        "count_base",
        "rate_ratio",
        "lo",
        "hi",
        "reading",
    ]
    return pd.DataFrame(rows, columns=columns)


def severity_slopes(metrics: pd.DataFrame, rate: str = "false_per_day") -> pd.DataFrame:
    """Per patient and alarm: least-squares slope of `rate` against the fault level (H1)."""
    rows = []
    agg = metrics.groupby(["alarm_name", "mix", "patient_id", "level"])[[rate]].mean().reset_index()
    for (alarm, mix, pid), g in agg.groupby(["alarm_name", "mix", "patient_id"]):
        if g["level"].nunique() < 2:
            continue
        slope = np.polyfit(g["level"].to_numpy(float), g[rate].to_numpy(float), 1)[0]
        rows.append({"alarm_name": alarm, "mix": mix, "patient_id": pid, "slope": slope})
    return pd.DataFrame(rows)


def h1_contrast(
    metrics: pd.DataFrame, n_boot: int = 2000, a: str = "trend", b: str = "threshold"
) -> pd.DataFrame:
    """Median paired slope difference (a - b) per mix with a patient bootstrap CI."""
    slopes = severity_slopes(metrics)
    rows = []
    for mix, g in slopes.groupby("mix"):
        wide = g.pivot_table(index="patient_id", columns="alarm_name", values="slope").reset_index()
        if a not in wide or b not in wide:
            continue
        wide["diff"] = wide[a] - wide[b]
        est, lo, hi = bootstrap_ci(wide, lambda df: float(np.median(df["diff"])), n_boot=n_boot)
        rows.append(
            {
                "mix": mix,
                "contrast": f"{a} - {b}",
                "median_slope_diff": est,
                "lo": lo,
                "hi": hi,
                "supported": bool(lo > 1e-9),  # strictly above 0, not a rounding epsilon
            }
        )
    return pd.DataFrame(rows)
