"""Consensus CGM metrics and the ambulatory glucose profile (AGP).

All functions take a table in the common schema (docs/reference/DATA.md §3) and use only rows with a
glucose value. Censored readings (`below_range` / `above_range`) count at their device limit,
so a "Low" reading counts as below 54 mg/dL and a "High" reading as above 250 mg/dL.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# SOURCE: Battelino 2019 (glycaemic ranges for time in ranges) CLINICAL-REVIEW: CR6, CR7
TIR_RANGE = (70.0, 180.0)  # inclusive
TBR_THRESHOLDS = (70.0, 54.0)  # strictly below
TAR_THRESHOLDS = (180.0, 250.0)  # strictly above

# SOURCE: Bergenstal 2018 (GMI % = 3.31 + 0.02392 x mean glucose in mg/dL)
GMI_INTERCEPT = 3.31
GMI_SLOPE = 0.02392

# ASSUMPTION: the sampling interval of an export is the nearest of these to its median spacing
# (G6/G7/Libre 3 report every 5 min, Libre 1/2 history every 15 min).
NOMINAL_INTERVALS_MIN = (1, 5, 15)

AGP_PERCENTILES = (5, 25, 50, 75, 95)  # SOURCE: Battelino 2019 (AGP)


def _readings(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that carry a glucose reading, one per timestamp, in time order."""
    out = df.loc[df["glucose"].notna(), ["time", "glucose"]]
    return out.drop_duplicates("time").sort_values("time")


def sampling_interval(times: pd.Series) -> float:
    """Nominal sampling interval in minutes, inferred from the median spacing."""
    gaps = times.sort_values().diff().dt.total_seconds().div(60).dropna()
    gaps = gaps[gaps > 0]
    if gaps.empty:
        raise ValueError("need at least two distinct timestamps to infer the sampling interval")
    median = gaps.median()
    return float(min(NOMINAL_INTERVALS_MIN, key=lambda nominal: abs(nominal - median)))


def wear_percent(df: pd.DataFrame, interval_min: float | None = None) -> float:
    """Readings present as a percentage of those expected between the first and last reading."""
    r = _readings(df)
    if len(r) < 2:
        return float("nan")
    interval = interval_min or sampling_interval(r["time"])
    span = (r["time"].iloc[-1] - r["time"].iloc[0]).total_seconds() / 60
    expected = np.floor(span / interval + 1e-9) + 1
    return float(min(100.0, 100.0 * len(r) / expected))


def summary(df: pd.DataFrame, interval_min: float | None = None) -> dict[str, float]:
    """Consensus metrics for one trace (Battelino 2019). Percentages are % of readings.

    `df` has `time` and `glucose` (mg/dL); `interval_min` is the sampling interval for wear time
    (inferred if None). Returns a dict: readings, days, wear, mean and SD (mg/dL), CV, GMI, and
    time in, below and above range (%).
    """
    g = _readings(df)["glucose"].to_numpy(dtype=float)
    if g.size == 0:
        raise ValueError("no glucose readings")
    mean = float(g.mean())
    # ASSUMPTION: sample SD (ddof=1), matching the iglu reference implementation (Broll 2021)
    sd = float(g.std(ddof=1)) if g.size > 1 else float("nan")
    lo, hi = TIR_RANGE
    return {
        "n_readings": int(g.size),
        "days": float(_readings(df)["time"].dt.normalize().nunique()),
        "wear_pct": wear_percent(df, interval_min),
        "mean": mean,
        "sd": sd,
        "cv_pct": 100.0 * sd / mean,
        "gmi_pct": GMI_INTERCEPT + GMI_SLOPE * mean,
        "tir_70_180_pct": 100.0 * float(np.mean((g >= lo) & (g <= hi))),
        "tbr_70_pct": 100.0 * float(np.mean(g < TBR_THRESHOLDS[0])),
        "tbr_54_pct": 100.0 * float(np.mean(g < TBR_THRESHOLDS[1])),
        "tar_180_pct": 100.0 * float(np.mean(g > TAR_THRESHOLDS[0])),
        "tar_250_pct": 100.0 * float(np.mean(g > TAR_THRESHOLDS[1])),
    }


def summary_by_patient(df: pd.DataFrame) -> pd.DataFrame:
    """`summary` for each patient_id, one row per patient."""
    rows = {pid: summary(group) for pid, group in df.groupby("patient_id", sort=True)}
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("patient_id")


def agp(df: pd.DataFrame, bin_min: int = 15, smooth_bins: int = 0) -> pd.DataFrame:
    """AGP percentile curves (5/25/50/75/95) by time of day.

    Readings from all days are pooled into `bin_min`-minute time-of-day bins. With
    `smooth_bins` > 0, each curve gets a centred circular moving average over that many bins.
    `df` has `time` and `glucose` (mg/dL). Returns one row per bin (index `time_of_day`), with
    columns p5 to p95 (mg/dL) and n.
    """
    # ASSUMPTION: 15-min bins and no smoothing by default; the published AGP smoothing method
    # is not specified in the consensus, so it is left configurable.
    if 1440 % bin_min:
        raise ValueError("bin_min must divide 1440")
    r = _readings(df)
    minute = r["time"].dt.hour * 60 + r["time"].dt.minute
    bins = (minute // bin_min).astype(int)
    grouped = r["glucose"].groupby(bins)
    out = pd.DataFrame(
        {f"p{p}": grouped.quantile(p / 100) for p in AGP_PERCENTILES} | {"n": grouped.size()}
    )
    out = out.reindex(range(1440 // bin_min))
    if smooth_bins > 1:
        pct = [f"p{p}" for p in AGP_PERCENTILES]
        wrapped = pd.concat([out[pct].iloc[-smooth_bins:], out[pct], out[pct].iloc[:smooth_bins]])
        smoothed = wrapped.rolling(smooth_bins, center=True, min_periods=1).mean()
        out[pct] = smoothed.iloc[smooth_bins:-smooth_bins].to_numpy()
    out.index = pd.Index(
        [f"{b * bin_min // 60:02d}:{b * bin_min % 60:02d}" for b in out.index], name="time_of_day"
    )
    return out
