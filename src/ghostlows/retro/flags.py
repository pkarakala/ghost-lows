"""Retrospective "possible compression artifact" flags for uploads (PRIVACY_AND_SAFETY.md).

Two published CGM-only methods run on the whole trace after the fact:
- the PISA rules of [Baysal 2014] (`baysal.py`), and
- a matched filter for the PISA shape, after [Idi 2023]: the full drop-and-recovery template of
  the median Facchinetti PISA [Facchinetti 2016] correlated with the dip below a local baseline.
  This is the tool's own adaptation; the paper's exact procedure was not available.

Overlapping detections are merged and listed with every method that raised them and why. A
detection becomes a *flag* only if both methods agree and it starts at night: on test traces the
rate rules alone also fire on genuine fast falls, and a flag must not hide a real low from time
below range. The label is always "possible compression artifact": a flag never says a low was
not real.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..faults.pisa import DEPTH, DURATION, from_size
from .baysal import BAYSAL_DEFAULT, BAYSAL_SETS, baysal_flags, minutes

LABEL = "possible compression artifact"
METHODS = {
    "baysal": "Baysal 2014: rule-based PISA detection on the CGM rate of change "
    "(parameter set 'trial')",
    "matched_filter": "after Idi 2023: matched filter for the PISA shape of Facchinetti 2016 "
    "(this tool's adaptation)",
}
# ASSUMPTION: a flag needs both methods and a night-time start, because compression artifacts
# occur mostly at night [Facchinetti 2016] and single-method detections include genuine falls
# (CLINICAL-REVIEW: CR12)
REQUIRE_ALL_METHODS = True
NIGHT_ONLY = True
NIGHT_HOURS = (23, 7)  # ASSUMPTION: same night window as the benchmark
MIN_DEPTH_MG_DL = 10.0  # ASSUMPTION: the 5th percentile of PISA depth [Facchinetti 2016]
MF_MIN_CORRELATION = 0.85  # ASSUMPTION: shape agreement needed for a matched-filter flag
BASELINE_MIN = 30.0  # ASSUMPTION: baseline = median CGM in the 30 min before a flag


def _readings(df: pd.DataFrame) -> pd.DataFrame:
    r = df.loc[df["glucose"].notna(), ["time", "glucose"]].drop_duplicates("time")
    return r.sort_values("time").reset_index(drop=True)


def _interval_min(times: pd.Series) -> float:
    gaps = times.diff().dt.total_seconds().div(60).dropna()
    gaps = gaps[gaps > 0]
    return float(min((1.0, 5.0, 15.0), key=lambda v: abs(v - gaps.median()))) if len(gaps) else 5.0


def _template(interval: float) -> np.ndarray:
    """Attenuation of the median PISA from onset to its end, sampled every `interval` minutes."""
    pisa = from_size(0.0, DEPTH.median, DURATION.median)
    return pisa.attenuation(np.arange(0.0, pisa.duration + 1e-9, interval))


def matched_filter_windows(
    times: pd.Series, glucose: np.ndarray
) -> list[tuple[int, int, float, float]]:
    """(start, end, correlation, depth) of non-overlapping PISA-shaped dips, best first."""
    interval = _interval_min(times)
    tmpl = _template(interval)
    m = len(tmpl)
    t = minutes(times)
    y = np.asarray(glucose, float)
    tc = tmpl - tmpl.mean()
    candidates = []
    for i in range(1, len(y) - m):
        # a regular stretch: m + 2 readings spaced by the nominal interval
        if not np.allclose(np.diff(t[i - 1 : i + m + 1]), interval, atol=1.0):
            continue
        before, seg, after = y[i - 1], y[i : i + m], y[i + m]
        base = before + (after - before) * np.arange(1, m + 1) / (m + 1)
        dip = base - seg
        depth = float(dip.max())
        if depth < MIN_DEPTH_MG_DL:
            continue
        dc = dip - dip.mean()
        denom = np.sqrt((dc**2).sum() * (tc**2).sum())
        r = float((dc * tc).sum() / denom) if denom > 0 else 0.0
        if r >= MF_MIN_CORRELATION:
            candidates.append((i, i + m, r, depth))
    chosen, taken = [], np.zeros(len(y), bool)
    for start, end, r, depth in sorted(candidates, key=lambda c: (-c[2], -c[3])):
        if not taken[start:end].any():
            chosen.append((start, end, r, depth))
            taken[start:end] = True
    return sorted(chosen)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    edges = np.diff(np.r_[0, mask.astype(int), 0])
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True))


def detections(df: pd.DataFrame, methods=("baysal", "matched_filter")) -> pd.DataFrame:
    """Every merged detection with its reasons; `flagged` marks those that count as flags."""
    r = _readings(df)
    columns = [
        "start",
        "end",
        "label",
        "methods",
        "citations",
        "duration_min",
        "baseline",
        "nadir",
        "depth",
        "max_drop_rate",
        "below_70",
        "night",
        "start_clock",
        "reasons",
        "flagged",
    ]
    if len(r) < 4:
        return pd.DataFrame(columns=columns)
    y = r["glucose"].to_numpy(float)
    segments = []
    if "baysal" in methods:
        flags = baysal_flags(r["time"], y, BAYSAL_SETS[BAYSAL_DEFAULT])
        segments += [(s, e, "baysal") for s, e in _runs(flags > 0)]
    if "matched_filter" in methods:
        segments += [
            (s, e, "matched_filter") for s, e, _, _ in matched_filter_windows(r["time"], y)
        ]
    if not segments:
        return pd.DataFrame(columns=columns)
    segments.sort()
    merged = []
    for s, e, name in segments:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
            merged[-1][2].add(name)
        else:
            merged.append([s, e, {name}])
    t = r["time"]
    rate = np.r_[np.nan, np.diff(y) / np.diff(minutes(t))]
    rows = []
    for s, e, names in merged:
        window_start = t.iloc[s] - pd.Timedelta(minutes=BASELINE_MIN)
        before = r[(t >= window_start) & (t < t.iloc[s])]["glucose"]
        baseline = float(before.median()) if len(before) else float(y[max(s - 1, 0)])
        nadir = float(y[s:e].min())
        depth = baseline - nadir
        if depth < MIN_DEPTH_MG_DL:
            continue
        drop = float(np.nanmin(rate[s : max(s + 1, (s + e) // 2 + 1)]))
        start, end = t.iloc[s], t.iloc[e - 1]
        hour = start.hour
        night = hour >= NIGHT_HOURS[0] or hour < NIGHT_HOURS[1]
        duration = (end - start).total_seconds() / 60 + _interval_min(t)
        ordered = [m for m in METHODS if m in names]
        agreed = set(methods) <= names if REQUIRE_ALL_METHODS else True
        flagged = agreed and (night or not NIGHT_ONLY)
        reasons = (
            f"fell {depth:.0f} mg/dL below the preceding level (to {nadir:.0f}) "
            f"at up to {abs(drop):.1f} mg/dL/min, lasted about {duration:.0f} min, "
            f"{'at night' if night else 'during the day'} ({start:%H:%M})"
        )
        rows.append(
            {
                "start": start,
                "end": end,
                "label": LABEL,
                "methods": ", ".join(ordered),
                "citations": "; ".join(METHODS[m] for m in ordered),
                "duration_min": duration,
                "baseline": baseline,
                "nadir": nadir,
                "depth": depth,
                "max_drop_rate": drop,
                "below_70": nadir < 70,
                "night": night,
                "start_clock": f"{start:%H:%M}",
                "reasons": reasons,
                "flagged": flagged,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def flag_possible_artifacts(df: pd.DataFrame, methods=("baysal", "matched_filter")) -> pd.DataFrame:
    """The detections that count as flags (both methods agree, night-time start)."""
    found = detections(df, methods)
    return found[found["flagged"].astype(bool)].reset_index(drop=True)


def without_flagged(df: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    """The trace without readings inside flags (time below range "without possible artifacts")."""
    keep = pd.Series(True, index=df.index)
    for _, f in flags.iterrows():
        keep &= ~((df["time"] >= f["start"]) & (df["time"] <= f["end"]) & df["glucose"].notna())
    return df[keep]
