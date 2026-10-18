"""The mixed fault suite (SIMULATION.md §4.2-4.3) and real-data injection (§5).

Faults act on the clean CGM only: `cgm_observed` is derived from it and every other column,
`truth_glucose` above all, is left untouched. Faults are applied in a fixed order: drift
(multiplicative), PISA (subtractive), spikes (additive), stale readings (hold), dropout (missing).

Common random numbers: each fault type draws from its own random stream, and candidate faults are
drawn at full severity and kept by thinning (a fault with uniform u is kept when u < severity).
So a sweep over severity is nested (the PISAs at 10% of nights are a subset of those at 25%), and
switching one fault type on or off never changes another's realisation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import pisa as pisa_model

DEVICE_LIMITS = (40.0, 400.0)  # ASSUMPTION: as in ghostlows.sim (SIMULATION.md §1)
LABEL_PRIORITY = ("dropout", "stale", "pisa", "spike", "drift")
FAULT_STREAMS = {"pisa": 0, "drift": 1, "spike": 2, "stale": 3, "dropout": 4}
RUN_KEYS = ("patient_id", "seed", "mix")


@dataclass(frozen=True)
class FaultConfig:
    """Fault rates and sizes. Severity `s` scales the non-PISA faults; PISAs have their own knob."""

    pisa_fraction: float = 0.0  # fraction of complete nights with one PISA (D13)
    pisa_tau: float = pisa_model.TAU_MIN
    night_hours: tuple[float, float] = (23.0, 7.0)  # ASSUMPTION: PISA onset window
    severity: float = 0.5  # s in [0, 1]; 0.5 is the "moderate" default level
    # ASSUMPTION: rates and sizes at s = 1 (SIMULATION.md §4.2); rates thin and sizes scale with s
    dropout_per_day: float = 4.0
    stale_per_day: float = 2.0
    stale_minutes: tuple[float, float] = (10.0, 30.0)
    spike_per_day: float = 2.0
    spike_minutes: tuple[float, float] = (15.0, 30.0)
    spike_sd: float = 20.0
    drift_range: tuple[float, float] = (0.10, 0.20)  # |bias| reached at the end of a sensor's life
    drift_label_above: float = 0.05  # label a sample "drift" once |bias| reaches this
    sensor_days: float = 10.0
    enabled: frozenset[str] = field(
        default_factory=lambda: frozenset({"pisa", "dropout", "stale", "spike", "drift"})
    )


# SOURCE: Facchinetti 2016 (about 90% of disconnections last less than 20 min)
# ASSUMPTION: exponential gap length until the paper's three-state Markov model is read
DROPOUT_RATE_PER_MIN = np.log(10) / 20.0


def stream(seed: int, kind: str, *more: int) -> np.random.Generator:
    """The random stream of one fault type (and optionally one instance) in one run."""
    return np.random.default_rng(np.random.SeedSequence([seed, FAULT_STREAMS[kind], *more]))


def _nights(days: float, night_hours: tuple[float, float]) -> list[tuple[float, float]]:
    """Complete night windows [start, end) in minutes from the trace start."""
    start_h, end_h = night_hours
    out = []
    for d in range(int(np.floor(days))):
        lo, hi = d * 1440 + start_h * 60, (d + 1) * 1440 + end_h * 60
        if hi <= days * 1440:
            out.append((lo, hi))
    return out


def draw_pisas(rng: np.random.Generator, days: float, config: FaultConfig) -> list[pisa_model.Pisa]:
    """A candidate PISA for every complete night; kept when its uniform u < `pisa_fraction`."""
    nights = _nights(days, config.night_hours)
    n = len(nights)
    keep_u, onset_u = rng.random(n), rng.random(n)
    depth, duration = pisa_model.sample_sizes(rng, n, config.pisa_tau)
    return [
        pisa_model.from_size(lo + ou * (hi - lo), d, t, config.pisa_tau)
        for (lo, hi), u, ou, d, t in zip(nights, keep_u, onset_u, depth, duration, strict=True)
        if u < config.pisa_fraction
    ]


def _candidates(
    rng: np.random.Generator, days: float, per_day: float, length
) -> list[tuple[float, float, float]]:
    """(start, end, u) for faults at full severity, by start time."""
    n = rng.poisson(per_day * days)
    starts = rng.uniform(0, days * 1440, n)
    lengths = np.array([length(rng) for _ in range(n)])
    keep_u = rng.random(n)
    order = np.argsort(starts)
    return [(starts[i], starts[i] + lengths[i], keep_u[i]) for i in order]


def apply_run(
    run: pd.DataFrame, config: FaultConfig, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Faults for one patient-run (rows sorted by time). Returns (samples, fault instances)."""
    t0 = run["time"].iloc[0]
    minutes = ((run["time"] - t0) / pd.Timedelta("1min")).to_numpy()
    days = (minutes[-1] + 5) / 1440
    if {"isf_glucose", "cgm_noise"} <= set(run):
        raw = (run["isf_glucose"] + run["cgm_noise"]).to_numpy(dtype=float)  # before clipping
    else:
        raw = run["glucose"].to_numpy(dtype=float)
    s = config.severity
    on = config.enabled
    label = np.full(len(run), "none", dtype=object)
    fault_id = np.full(len(run), -1)
    instances = []

    def mark(kind: str, mask: np.ndarray, fid: int) -> None:
        rank = LABEL_PRIORITY.index(kind)
        current = np.array([LABEL_PRIORITY.index(x) if x != "none" else 99 for x in label[mask]])
        take = np.flatnonzero(mask)[rank < current]
        label[take] = kind
        fault_id[take] = fid

    # drift: per-sensor linear multiplicative bias, reset at each sensor change
    bias = np.ones(len(run))
    if "drift" in on and s > 0:
        rng = stream(seed, "drift")
        life = config.sensor_days * 1440
        for k, start in enumerate(np.arange(0, days * 1440, life)):
            size = rng.uniform(*config.drift_range) * rng.choice([-1.0, 1.0]) * s
            seg = (minutes >= start) & (minutes < start + life)
            bias[seg] = 1 + size * (minutes[seg] - start) / life
            instances.append(
                {
                    "fault_type": "drift",
                    "fault_id": k,
                    "start": start,
                    "end": start + life,
                    "size": size,
                }
            )
            mark("drift", seg & (np.abs(bias - 1) >= config.drift_label_above), k)
    obs = raw * bias

    if "pisa" in on and config.pisa_fraction > 0:
        for k, p in enumerate(draw_pisas(stream(seed, "pisa"), days, config)):
            obs = obs - p.attenuation(minutes)
            mark("pisa", p.active(minutes), k)
            instances.append(
                {
                    "fault_type": "pisa",
                    "fault_id": k,
                    "start": p.onset,
                    "end": p.onset + p.duration,
                    "size": p.depth,
                    "duration": p.duration,
                    "tau": p.tau,
                }
            )

    if "spike" in on and s > 0:
        rng = stream(seed, "spike")
        spikes = _candidates(
            rng, days, config.spike_per_day, lambda r: r.uniform(*config.spike_minutes)
        )
        for k, (a, b, u) in enumerate(spikes):
            if u >= s:
                continue
            seg = (minutes >= a) & (minutes < b)
            z = stream(seed, "spike", k).standard_normal(int(seg.sum()))
            obs[seg] += z * config.spike_sd * s
            mark("spike", seg, k)
            instances.append(
                {
                    "fault_type": "spike",
                    "fault_id": k,
                    "start": a,
                    "end": b,
                    "size": config.spike_sd * s,
                }
            )

    if "stale" in on and s > 0:
        rng = stream(seed, "stale")
        stale = _candidates(
            rng, days, config.stale_per_day, lambda r: r.uniform(*config.stale_minutes)
        )
        for k, (a, b, u) in enumerate(stale):
            seg = np.flatnonzero((minutes >= a) & (minutes < b))
            if u < s and seg.size > 1:
                obs[seg[1:]] = obs[seg[0]]
                mark("stale", np.isin(np.arange(len(run)), seg[1:]), k)
                instances.append({"fault_type": "stale", "fault_id": k, "start": a, "end": b})

    if "dropout" in on and s > 0:
        rng = stream(seed, "dropout")
        gaps = _candidates(
            rng, days, config.dropout_per_day, lambda r: r.exponential(1 / DROPOUT_RATE_PER_MIN)
        )
        for k, (a, b, u) in enumerate(gaps):
            if u >= s:
                continue
            seg = (minutes >= a) & (minutes < b)
            obs[seg] = np.nan
            mark("dropout", seg, k)
            instances.append({"fault_type": "dropout", "fault_id": k, "start": a, "end": b})

    lo, hi = DEVICE_LIMITS
    flag = np.where(
        np.isnan(obs),
        "missing",
        np.where(obs < lo, "below_range", np.where(obs > hi, "above_range", "ok")),
    )
    out = run.assign(
        cgm_observed=np.clip(obs, lo, hi),
        cgm_observed_flag=flag,
        fault_type=label.astype(str),
        fault_id=fault_id,
    )
    faults = pd.DataFrame(instances)
    if len(faults):
        for col in ("start", "end"):
            faults[col] = (t0 + pd.to_timedelta(faults[col], unit="min")).astype("datetime64[ns]")
    return out, faults


def run_seed(seed: int, key: tuple) -> int:
    """Fault seed of one patient-run, from the suite seed and the run's identity."""
    text = "|".join(str(k) for k in key)
    return int(np.random.SeedSequence([seed, *text.encode()]).generate_state(1)[0])


def apply_faults(
    samples: pd.DataFrame, config: FaultConfig, seed: int = 0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the suite to every patient-run. A run's faults depend only on (seed, run identity)."""
    keys = [k for k in RUN_KEYS if k in samples]
    outs, faults = [], []
    for key, run in samples.sort_values(keys + ["time"]).groupby(keys, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        out, f = apply_run(run.reset_index(drop=True), config, run_seed(seed, key))
        outs.append(out)
        if len(f):
            faults.append(f.assign(**dict(zip(keys, key, strict=True))))
    faults_df = pd.concat(faults, ignore_index=True) if faults else pd.DataFrame()
    return pd.concat(outs, ignore_index=True), faults_df


def stable_onsets(
    run: pd.DataFrame, night_hours=(23.0, 7.0), window_min=120.0, max_sd=15.0
) -> list[pd.Timestamp]:
    """Candidate PISA onsets in a real trace: night samples whose next `window_min` minutes have
    complete 5-min data, no reading below 70 mg/dL and a standard deviation of at most `max_sd`."""
    # ASSUMPTION: injection sites are 2 h of complete, steady night data (SD <= 15, no reading < 70)
    # ASSUMPTION: stability rule for semi-synthetic injection (SIMULATION.md §5)
    r = (
        run.loc[run["glucose"].notna(), ["time", "glucose"]]
        .sort_values("time")
        .reset_index(drop=True)
    )
    hours = r["time"].dt.hour + r["time"].dt.minute / 60
    start_h, end_h = night_hours
    night = (hours >= start_h) | (hours < end_h)
    times, values = r["time"].to_numpy(), r["glucose"].to_numpy()
    need = int(window_min // 5)
    out = []
    for i in np.flatnonzero(night.to_numpy()):
        j = i + need
        if j >= len(r):
            break
        span = (times[j] - times[i]) / np.timedelta64(1, "m")
        seg = values[i : j + 1]
        if span <= window_min + 2.5 and seg.min() >= 70 and seg.std() <= max_sd:
            out.append(pd.Timestamp(times[i]))
    return out


def inject_real(
    run: pd.DataFrame, per_night: float, seed: int, tau: float = pisa_model.TAU_MIN
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inject PISAs into a real CGM trace (semi-synthetic track, SIMULATION.md §5).

    At most one PISA per calendar night with probability `per_night`, at a random stable onset.
    `glucose` is kept as the reference; the injected trace is `cgm_observed`.
    """
    rng = np.random.default_rng(seed)
    run = run.sort_values("time").reset_index(drop=True)
    onsets = pd.Series(stable_onsets(run), dtype="datetime64[ns]")
    night_of = (onsets - pd.Timedelta(hours=12)).dt.normalize()
    obs = run["glucose"].to_numpy(dtype=float).copy()
    minutes = ((run["time"] - run["time"].iloc[0]) / pd.Timedelta("1min")).to_numpy()
    label = np.full(len(run), "none", dtype=object)
    rows = []
    for k, (_, candidates) in enumerate(onsets.groupby(night_of)):
        if rng.random() >= per_night:
            continue
        onset = candidates.iloc[int(rng.integers(len(candidates)))]
        depth, duration = pisa_model.sample_sizes(rng, 1, tau)
        start = (onset - run["time"].iloc[0]) / pd.Timedelta("1min")
        p = pisa_model.from_size(start, float(depth[0]), float(duration[0]), tau)
        obs = obs - p.attenuation(minutes)
        label[p.active(minutes)] = "pisa"
        rows.append(
            {
                "fault_type": "pisa",
                "fault_id": k,
                "start": onset,
                "end": onset + pd.Timedelta(minutes=p.duration),
                "size": p.depth,
                "duration": p.duration,
                "tau": tau,
            }
        )
    lo, hi = DEVICE_LIMITS
    out = run.assign(cgm_observed=np.clip(obs, lo, hi), fault_type=label.astype(str))
    return out, pd.DataFrame(rows)
