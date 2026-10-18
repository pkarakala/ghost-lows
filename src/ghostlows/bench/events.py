"""True low events (BENCHMARK.md §3, D11) and the context leak metric (BENCHMARK.md §4, D3)."""

from __future__ import annotations

import numpy as np
import pandas as pd

# SOURCE: Battelino 2023 (event starts after >=15 consecutive minutes below the threshold and
# ends after >=15 consecutive minutes at or above it) CLINICAL-REVIEW: CR6
EVENT_MIN = 15
LEVEL_THRESHOLDS = {1: 70.0, 2: 54.0}  # SOURCE: IHSG 2017; Battelino 2019 CLINICAL-REVIEW: CR6
NIGHT_HOURS = (23, 7)  # ASSUMPTION: same window as PISA onsets (SIMULATION.md §4.1)


def detect_events(
    values: np.ndarray, threshold: float, step_min: float = 1.0
) -> list[tuple[int, int]]:
    """(start, end) sample indices of low events in a regularly sampled signal.

    An event starts at the first sample of a run below `threshold` lasting at least 15 minutes and
    ends at the first sample of a run at or above it lasting at least 15 minutes (`end` is that
    sample, or len(values) if the signal ends first). Shorter excursions above the threshold
    inside an event do not end it. NaN counts as "at or above" (no evidence of a low).
    """
    below = np.asarray(values, dtype=float) < threshold
    need = int(np.ceil(EVENT_MIN / step_min))
    if below.size == 0:
        return []
    change = np.flatnonzero(np.diff(below.astype(np.int8))) + 1
    starts = np.r_[0, change]
    lengths = np.diff(np.r_[starts, below.size])
    events, start = [], None
    for run_start, length in zip(starts, lengths, strict=True):
        if below[run_start]:
            if start is None and length >= need:
                start = int(run_start)
        elif start is not None and length >= need:
            events.append((start, int(run_start)))
            start = None
    if start is not None:
        events.append((start, int(below.size)))
    return events


def true_events(truth: pd.DataFrame, levels=(1, 2)) -> pd.DataFrame:
    """True low events per patient (and run tags) from 1-minute truth (D11)."""
    keys = [c for c in ("patient_id", "seed", "mix") if c in truth]
    rows = []
    for group_key, g in truth.groupby(keys, sort=False):
        group_key = group_key if isinstance(group_key, tuple) else (group_key,)
        times = g["time"].to_numpy()
        values = g["truth_glucose"].to_numpy()
        for level in levels:
            for s, e in detect_events(values, LEVEL_THRESHOLDS[level]):
                end_time = times[e] if e < len(times) else times[-1] + np.timedelta64(1, "m")
                rows.append(
                    {
                        **dict(zip(keys, group_key, strict=True)),
                        "level": level,
                        "onset": times[s],
                        "end": end_time,
                    }
                )
    out = pd.DataFrame(rows, columns=keys + ["level", "onset", "end"])
    return out.astype({"onset": "datetime64[ns]", "end": "datetime64[ns]"})


def is_night(times: pd.Series) -> np.ndarray:
    hours = pd.DatetimeIndex(times).hour
    start, end = NIGHT_HOURS
    return np.asarray((hours >= start) | (hours < end))


def auc(positive: np.ndarray, negative: np.ndarray) -> float:
    """P(positive > negative) + P(tie) / 2, via ranks (Mann-Whitney)."""
    pos, neg = np.asarray(positive, float), np.asarray(negative, float)
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    ranks = pd.Series(np.r_[pos, neg]).rank().to_numpy()
    return float((ranks[: pos.size].sum() - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size))


def leak_auc(samples: pd.DataFrame, events: pd.DataFrame, feature: str = "iob") -> float:
    """AUC of `feature` at nocturnal level-1 onsets vs. all nocturnal samples (D3).

    The feature value at an onset is taken from the last sample at or before it (causal).
    """
    keys = [c for c in ("patient_id", "seed", "mix") if c in samples and c in events]
    onsets = events[(events["level"] == 1) & is_night(events["onset"])]
    onsets = onsets.astype({"onset": "datetime64[ns]"})
    right = samples[keys + ["time", feature]].astype({"time": "datetime64[ns]"})
    at_onset = pd.merge_asof(
        onsets.sort_values("onset"),
        right.sort_values("time"),
        left_on="onset",
        right_on="time",
        by=keys,
        direction="backward",
    )[feature]
    night = samples.loc[is_night(samples["time"]), feature]
    return auc(at_onset.dropna().to_numpy(), night.dropna().to_numpy())


# ASSUMPTION: training target horizon, 30 min like the default early matching window (D12). The
# window robustness arms keep it at 30 (proposed amendment P4 in DECISIONS.md)
LABEL_HORIZON_MIN = 30.0


def low_labels(
    samples: pd.DataFrame, events: pd.DataFrame, horizon_min: float = LABEL_HORIZON_MIN
) -> pd.Series:
    """1 where a true level 1 low is ongoing or starts within `horizon_min` minutes, else 0.

    Computed by the benchmark from truth and handed to alarms only as a training target.
    """
    keys = [c for c in ("patient_id", "seed", "mix") if c in samples and c in events]
    level1 = events[events["level"] == 1]
    by_run = {k if isinstance(k, tuple) else (k,): g for k, g in level1.groupby(keys, sort=False)}
    horizon = np.timedelta64(int(horizon_min * 60), "s")
    labels = pd.Series(0, index=samples.index, dtype=int)
    for key, run in samples.groupby(keys, sort=False):
        ev = by_run.get(key if isinstance(key, tuple) else (key,))
        if ev is None:
            continue
        t = run["time"].to_numpy()
        hit = np.zeros(len(run), dtype=bool)
        for onset, end in zip(ev["onset"].to_numpy(), ev["end"].to_numpy(), strict=True):
            hit |= (t >= onset - horizon) & (t < end)
        labels.loc[run.index] = hit.astype(int)
    return labels
