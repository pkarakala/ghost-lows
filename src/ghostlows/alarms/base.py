"""Alarm interface, firing rules and causal CGM features (BENCHMARK.md §1).

Alarms see a narrow view of the data: `time`, `cgm` (the observed CGM, NaN when missing) and, for
context arms only, `iob`, `cob`. They never see truth or fault columns, so they cannot leak them.
Scores are computed per patient-run and may use only samples at or before each time.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd

RUN_KEYS = ("patient_id", "seed", "mix")

# SOURCE: Garg 2022 (G7 Urgent Low fixed at 55 mg/dL) CLINICAL-REVIEW: CR14
FLOOR_MG_DL = 55.0
REFRACTORY_MIN = 30.0  # ASSUMPTION: BENCHMARK.md §1
FLICKER_MIN = 15.0  # ASSUMPTION: BENCHMARK.md §1


class Alarm(Protocol):
    name: str
    uses_context: bool

    def fit(self, train: pd.DataFrame) -> None: ...
    def score(self, df: pd.DataFrame) -> pd.Series: ...
    def alarms(self, df: pd.DataFrame, threshold: float) -> pd.DataFrame: ...


def view(df: pd.DataFrame, cgm_column: str = "cgm_observed", context: bool = False) -> pd.DataFrame:
    """The columns an alarm may see. `cgm_column` is the CGM it is scored on."""
    keys = [k for k in RUN_KEYS if k in df]
    cols = {k: df[k] for k in keys}
    cols["time"] = df["time"]
    cols["cgm"] = df[cgm_column].astype(float)
    if context:
        cols["iob"], cols["cob"] = df["iob"].astype(float), df["cob"].astype(float)
    return pd.DataFrame(cols, index=df.index)


def runs(df: pd.DataFrame):
    """(key, run) pairs, each run sorted by time."""
    keys = [k for k in RUN_KEYS if k in df]
    if not keys:
        yield (), df.sort_values("time")
        return
    for key, run in df.groupby(keys, sort=False):
        yield key, run.sort_values("time")


def fire_events(
    times: np.ndarray,
    condition: np.ndarray,
    floor: np.ndarray,
    refractory_min: float = REFRACTORY_MIN,
    flicker_min: float = FLICKER_MIN,
) -> pd.DataFrame:
    """Alarm events from a per-sample condition and the ungated floor (D4).

    An event is raised at a sample where `condition or floor` holds and no event was raised in the
    previous `refractory_min` minutes, so a persisting condition re-alarms every refractory period.
    `is_floor` marks events raised by the floor alone. `flicker` marks condition onsets that come
    within `flicker_min` minutes of the condition last switching off.
    """
    active = np.asarray(condition, bool) | np.asarray(floor, bool)
    t = minutes(times)
    events, last = [], -np.inf
    for i in np.flatnonzero(active):
        if t[i] - last >= refractory_min:
            events.append({"time": times[i], "is_floor": bool(floor[i] and not condition[i])})
            last = t[i]
    out = pd.DataFrame(events, columns=["time", "is_floor"])
    onsets = np.flatnonzero(active[1:] & ~active[:-1]) + 1
    offsets = np.flatnonzero(~active[1:] & active[:-1]) + 1
    flicker = [
        i
        for i in onsets
        if len(offsets[offsets < i]) and t[i] - t[offsets[offsets < i][-1]] < flicker_min
    ]
    out.attrs["flicker"] = len(flicker)
    return out


class BaseAlarm:
    """Shared machinery: subclasses implement `_score_run` (and `fit` if they learn)."""

    name = "base"
    uses_context = False
    default_threshold = 0.0
    refractory_min = REFRACTORY_MIN  # set per alarm, or for a run by BenchConfig.refractory_min

    def fit(self, train: pd.DataFrame) -> None:  # rule-based alarms learn nothing
        return None

    def _score_run(self, run: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError

    def score(self, df: pd.DataFrame) -> pd.Series:
        out = pd.Series(np.nan, index=df.index, dtype=float)
        for _, run in runs(df):
            out.loc[run.index] = self._score_run(run)
        return out

    def alarms(self, df: pd.DataFrame, threshold: float | None = None) -> pd.DataFrame:
        return self.alarms_from_scores(df, self.score(df), threshold)

    def alarms_from_scores(
        self, df: pd.DataFrame, scores: pd.Series, threshold: float | None = None
    ) -> pd.DataFrame:
        """Alarm events from precomputed scores (lets threshold sweeps score only once)."""
        threshold = self.default_threshold if threshold is None else threshold
        rows = []
        for key, run in runs(df):
            s = scores.loc[run.index].to_numpy()
            cgm = run["cgm"].to_numpy()
            condition = np.nan_to_num(s, nan=-np.inf) > threshold
            floor = np.nan_to_num(cgm, nan=np.inf) <= FLOOR_MG_DL
            ev = fire_events(run["time"].to_numpy(), condition, floor, self.refractory_min)
            keys = [k for k in RUN_KEYS if k in run]
            key = key if isinstance(key, tuple) else (key,)
            for k, v in zip(keys, key, strict=True):
                ev[k] = v
            ev["alarm_name"] = self.name
            rows.append(ev)
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


# ---------- causal features (each uses only samples at or before t) ----------


def trailing_slope(times, y: np.ndarray, window_min: float, min_points: int = 3) -> np.ndarray:
    """Least-squares slope (mg/dL/min) over samples in [t - window_min, t], NaN-aware.

    Rolling sums over a time window, so irregular sampling and gaps are handled.
    """
    y = np.asarray(y, dtype=float)
    t = minutes(times)
    t = t - t[0]
    ok = ~np.isnan(y)
    parts = pd.DataFrame(
        {
            "n": ok.astype(float),
            "t": np.where(ok, t, 0.0),
            "y": np.where(ok, y, 0.0),
            "tt": np.where(ok, t * t, 0.0),
            "ty": np.where(ok, t * y, 0.0),
        },
        index=pd.DatetimeIndex(times),
    )
    r = parts.rolling(f"{int(round((window_min + 0.5) * 60))}s").sum()
    n = r["n"].to_numpy()
    denom = n * r["tt"].to_numpy() - r["t"].to_numpy() ** 2
    with np.errstate(invalid="ignore", divide="ignore"):
        slope = (n * r["ty"].to_numpy() - r["t"].to_numpy() * r["y"].to_numpy()) / denom
    slope[(n < min_points) | (denom <= 1e-9)] = np.nan
    return slope


def minutes(times) -> np.ndarray:
    """Minutes since the epoch, whatever the datetime unit (pandas 3 defaults to microseconds)."""
    return pd.DatetimeIndex(times).as_unit("ns").asi8 / 6e10


def time_of_day_features(times) -> np.ndarray:
    """sin/cos of the time of day (the `_time` arm)."""
    idx = pd.DatetimeIndex(times)
    frac = (idx.hour * 60 + idx.minute) / 1440.0
    return np.column_stack([np.sin(2 * np.pi * frac), np.cos(2 * np.pi * frac)])
