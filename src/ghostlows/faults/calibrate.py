"""Realistic PISA frequency: a range with two ends (SIMULATION.md §4.1, CR3, amendment A14).

Upper end (the D19 training level): Lobo 2026's rate of deep PISAs, reproduced on the cohort.
Lower end: Facchinetti 2016's night-time rate of all visually identified compression artifacts,
which needs no cohort. They differ several-fold; neither is "the" realistic level.

[Lobo 2026] counts "PISAs of interest" (a drop of at least 20 mg/dL from a start of at least
70 mg/dL to below 85, a matching rise, 15-180 min): 846 in 59,122 h, 89 in 8,189 h and 325 in
26,890 h, pooled 1,260 in 94,201 sensor-hours (about one per 74.8 h). Injected PISAs are counted
with the same tests on the observed CGM (A15). How many qualify depends on the cohort's overnight
glucose, so the fraction of nights that reproduces the rate is computed on the simulated cohort
itself. Faults are thinned (suite.py), so the expected rate is exactly linear in the fraction:
rate(f) = f * rate(1).
"""

from __future__ import annotations

import pandas as pd

from .suite import FaultConfig, apply_faults

# SOURCE: Facchinetti 2016 (p.268: 143 artifacts in 108 traces of 7 days, about one per 127 h;
# p.270: probability of an artifact 0.0014 per sample in 00:00-07:59, 0.0003 in 08:00-23:59)
# CLINICAL-REVIEW: CR3
FACCHINETTI_NIGHT_PER_SAMPLE = 0.0014
FACCHINETTI_NIGHT_SAMPLES = 96  # 8 h of 5-min samples
# ASSUMPTION: the per-sample probability applies to each sample of our 8-h night window
# (23:00-07:00 rather than 00:00-07:59); daytime artifacts are not modelled (one PISA per night)
FACCHINETTI_FRACTION = 1 - (1 - FACCHINETTI_NIGHT_PER_SAMPLE) ** FACCHINETTI_NIGHT_SAMPLES

# SOURCE: Lobo 2026 (Table 1: 1,260 PISAs of interest in 94,201 h of CGM data, 405 series from
# 111 adults with T1D each wearing 2-4 Dexcom G7 sensors at once; so the hours are sensor-hours)
# CLINICAL-REVIEW: CR3
LOBO_PISAS, LOBO_HOURS = 846 + 89 + 325, 59_122 + 8_189 + 26_890
TARGET_PER_HOUR = LOBO_PISAS / LOBO_HOURS
# SOURCE: Lobo 2026 (Methods, "Definition of a PISA of Interest": a drop of at least 20 mg/dL, a
# matching rise, 15 to 180 min from start to end, at least one reading below 85 mg/dL, and a
# starting value of at least 70 mg/dL)
LOBO_THRESHOLD = 85.0
LOBO_MIN_DROP = 20.0
LOBO_MIN_START = 70.0
LOBO_LENGTH_MIN = (15.0, 180.0)
# ASSUMPTION: "a matching rise" = the reading at the artifact's end is at least LOBO_MIN_DROP above
# its minimum (Lobo labels semi-automatically against other sensors; we have one trace)
LOBO_MIN_RISE = LOBO_MIN_DROP
# SOURCE: Lobo 2026 (training set: starting value of a PISA of interest mean 104.9 mg/dL, SD 27.7)
LOBO_START_MEAN_SD = (104.9, 27.7)


def lobo_criteria(window: pd.DataFrame, length_min: float) -> dict[str, bool | float]:
    """Lobo 2026's tests for a PISA of interest, on the observed CGM readings that bracket an
    injected artifact: the start value is the last reading at or before onset and the end value
    the first at or after the end (`pisa_census` builds that window). The first reading inside
    the artifact comes on average 2.5 min after onset, already 6.6 mg/dL lower, which failed the
    20 mg/dL drop test for PISAs that pass it (2026-11 audit check)."""
    cgm = window["cgm_observed"].dropna().to_numpy(float)
    if cgm.size == 0:
        return {
            "start": float("nan"),
            "below": False,
            "drop": False,
            "rise": False,
            "start_ok": False,
            "length": False,
            "of_interest": False,
        }
    start, low = float(cgm[0]), float(cgm.min())
    out = {
        "start": start,
        "below": low < LOBO_THRESHOLD,
        "drop": start - low >= LOBO_MIN_DROP,
        "rise": float(cgm[-1]) - low >= LOBO_MIN_RISE,
        "start_ok": start >= LOBO_MIN_START,
        "length": LOBO_LENGTH_MIN[0] <= length_min <= LOBO_LENGTH_MIN[1],
    }
    out["of_interest"] = all(out[k] for k in ("below", "drop", "rise", "start_ok", "length"))
    return out


def bracket(run: pd.DataFrame, start, end) -> pd.DataFrame:
    """Readings from the last at or before `start` to the first at or after `end`."""
    t = run["time"]
    seen = run["cgm_observed"].notna()
    before = t[(t <= start) & seen]
    after = t[(t >= end) & seen]
    lo = before.max() if len(before) else start
    hi = after.min() if len(after) else end
    return run[(t >= lo) & (t <= hi)]


def pisa_census(samples: pd.DataFrame, seed: int = 0) -> tuple[pd.DataFrame, float]:
    """Every injected PISA with a PISA every night, with Lobo's tests; and the hours of wear."""
    config = FaultConfig(pisa_fraction=1.0, enabled=frozenset({"pisa"}))
    observed, faults = apply_faults(samples, config, seed=seed)
    keys = [k for k in ("patient_id", "seed", "mix") if k in observed]
    by_run = dict(tuple(observed.groupby(keys))) if keys else {(): observed}
    rows = []
    for _, f in faults.iterrows():
        run = by_run[tuple(f[k] for k in keys)] if keys else observed
        window = bracket(run, f["start"], f["end"])
        length = (f["end"] - f["start"]) / pd.Timedelta("1min")
        rows.append(lobo_criteria(window, length))
    hours = observed.groupby(keys)["time"].agg(
        lambda t: (t.max() - t.min()) / pd.Timedelta("1h") + 5 / 60
    )
    return pd.DataFrame(rows), float(hours.sum())


def pisa_rate_at_full(
    samples: pd.DataFrame, seed: int = 0, threshold: float = LOBO_THRESHOLD
) -> float:
    """PISAs of interest (Lobo 2026's definition) per hour of wear, one PISA every night."""
    census, hours = pisa_census(samples, seed)
    if census.empty:
        return 0.0
    return float(census["of_interest"].sum()) / hours


def realistic_fraction(samples: pd.DataFrame, seed: int = 0) -> dict:
    """Fraction of nights with a PISA that reproduces the Lobo 2026 rate on this cohort (the upper
    end of the realistic range; `FACCHINETTI_FRACTION` is the lower end), counting PISAs as Lobo
    does (A15), with the face-validity check of starting glucose."""
    census, hours = pisa_census(samples, seed)
    n = len(census)
    at_full = float(census["of_interest"].sum()) / hours if n else 0.0
    fraction = TARGET_PER_HOUR / at_full if at_full > 0 else float("nan")
    below_only = float(census["below"].sum()) / hours if n else 0.0  # the v0.4.0 count
    interest = census[census["of_interest"]] if n else census
    return {
        "target_per_hour": TARGET_PER_HOUR,
        "rate_at_full": at_full,
        "rate_at_full_below85_only": below_only,
        "fraction": min(fraction, 1.0),
        "reachable": bool(fraction <= 1.0),
        "pisas_at_full": n,
        "share_passing": {
            k: float(census[k].mean()) if n else float("nan")
            for k in ("below", "drop", "rise", "start_ok", "length", "of_interest")
        },
        "start_glucose_all": _describe(census["start"]) if n else {},
        "start_glucose_of_interest": _describe(interest["start"]) if len(interest) else {},
        "start_glucose_lobo": {"mean": LOBO_START_MEAN_SD[0], "sd": LOBO_START_MEAN_SD[1]},
    }


def _describe(x: pd.Series) -> dict[str, float]:
    x = x.dropna()
    q = x.quantile([0.05, 0.5, 0.95])
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "sd": float(x.std()),
        "p5": float(q.iloc[0]),
        "median": float(q.iloc[1]),
        "p95": float(q.iloc[2]),
    }
