"""Minute-by-minute simulation on simglucose's patient model (SIMULATION.md §1-2).

Drives `simglucose.patient.t1dpatient.T1DPatient` directly instead of its environment, so that
plasma truth is recorded every minute, insulin sensitivity can change over time, each meal gets
one bolus, and a run is not stopped when glucose leaves the model's range (it is flagged).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd

from .context import cob, iob
from .scenario import Scenario

SAMPLE_MIN = 5
DEVICE_LIMITS = (40.0, 400.0)  # ASSUMPTION: G6/G7 reportable range (SIMULATION.md §1)
VALIDITY_FLOOR = 10.0  # SOURCE: simglucose (episode ends when glucose < 10 mg/dL)
GROUPS = ("adolescent", "adult", "child")
PATIENTS = [f"{g}#{i:03d}" for g in GROUPS for i in range(1, 11)]
DEFAULT_START = pd.Timestamp("2026-01-05")  # a Monday; calendar dates carry no meaning


@dataclass(frozen=True)
class Therapy:
    """Open-loop basal-bolus settings for one patient (D17)."""

    bolus_scale: float = 1.0  # carb ratio and correction factor are multiplied by this
    basal_factor: float = 1.0
    target: float = 140.0  # SOURCE: simglucose (BBController target)
    correction_above: float = 150.0  # SOURCE: simglucose (BBController correction threshold)


@dataclass(frozen=True)
class HypoTreatment:
    """Self-treatment of lows (SIMULATION.md §2, amendment A6): fast carbohydrate when the
    displayed CGM is low, eaten but not logged. The 2008 model has no counter-regulation, so
    without treatment a low lasts until the insulin wears off and plasma glucose can reach 0."""

    # SOURCE: CDC 2024 (15-15 rule: 15 g of carbs, wait 15 min, repeat while below 70 mg/dL)
    # CLINICAL-REVIEW: CR17
    grams: float = 15.0
    recheck_min: int = 15
    awake_threshold: float = 70.0
    # SOURCE: Garg 2022 (Urgent Low alarm at 55 mg/dL) CLINICAL-REVIEW: CR17
    night_threshold: float = 55.0
    # ASSUMPTION: at night only the urgent-low alarm wakes the person; once awake, the 70 mg/dL
    # rule applies for the next 30 min. Same night window as the PISA onsets.
    night_hours: tuple[int, int] = (23, 7)
    awake_min: int = 30

    def threshold(self, minute_of_day: int, minutes_since_treatment: float) -> float:
        hour = minute_of_day // 60
        night = hour >= self.night_hours[0] or hour < self.night_hours[1]
        awake = minutes_since_treatment < self.awake_min
        return self.night_threshold if night and not awake else self.awake_threshold

    def treats(self, cgm: float, minute_of_day: int, minutes_since_treatment: float) -> bool:
        if minutes_since_treatment < self.recheck_min:
            return False
        threshold = self.threshold(minute_of_day, minutes_since_treatment)
        # the urgent-low alarm fires at <= 55; the 15-15 rule treats below 70
        return cgm <= threshold if threshold == self.night_threshold else cgm < threshold


@dataclass
class SimResult:
    samples: pd.DataFrame  # 5-min rows, common schema plus simulation columns
    truth: pd.DataFrame  # 1-min plasma glucose
    events: pd.DataFrame  # doses, carb entries, meals eaten, exercise
    valid: bool  # False if plasma fell below VALIDITY_FLOOR
    nadir: float


@cache
def _tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    import importlib.resources

    root = importlib.resources.files("simglucose") / "params"
    read = lambda name: pd.read_csv(root / name)  # noqa: E731
    return read("vpatient_params.csv"), read("Quest.csv"), read("sensor_params.csv")


def patient_params(name: str) -> pd.Series:
    params, _, _ = _tables()
    row = params.loc[params["Name"] == name]
    if row.empty:
        raise ValueError(f"unknown virtual patient {name!r}")
    return row.iloc[0].copy()


def quest(name: str) -> tuple[float, float]:
    """Carb ratio (g/U) and correction factor (mg/dL/U). SOURCE: simglucose (Quest.csv)."""
    _, q, _ = _tables()
    row = q.loc[q["Name"] == name].iloc[0]
    return float(row["CR"]), float(row["CF"])


def sensor_params() -> pd.Series:
    """Noise parameters shared by simglucose's bundled sensors, sampled every 5 min."""
    # SOURCE: simglucose (sensor_params.csv: all rows share the noise model of Breton 2008)
    _, _, sensors = _tables()
    row = sensors.loc[sensors["Name"] == "GuardianRT"].iloc[0].copy()
    row["Name"], row["sample_time"] = "ghostlows_5min", float(SAMPLE_MIN)
    return row


def simulate(
    name: str,
    scenario: Scenario,
    therapy: Therapy,
    noise_seed: int,
    start: pd.Timestamp = DEFAULT_START,
    limits: tuple[float, float] = DEVICE_LIMITS,
    dia_h: float = 5.0,  # ASSUMPTION: insulin action duration for IOB (SIMULATION.md §2)
    cob_h: float = 3.0,  # ASSUMPTION: carbohydrate absorption time for COB (SIMULATION.md §2)
    treatment: HypoTreatment | None = None,
) -> SimResult:
    """Simulate one patient-run. With `treatment`, the virtual person treats lows they see on
    the (fault-free) CGM; rescue carbohydrate is eaten but never logged, so it is invisible to
    recorded context (IOB/COB) and to alarms."""
    from simglucose.patient.t1dpatient import Action, T1DPatient
    from simglucose.sensor.noise_gen import CGMNoise

    base = patient_params(name)
    init = np.asarray(base.iloc[2:15].to_numpy(), dtype=float)
    patient = T1DPatient(base.copy(), init_state=init)
    vg = float(base["Vg"])
    cr, cf = quest(name)
    basal = therapy.basal_factor * float(base["u2ss"]) * float(base["BW"]) / 6000  # U/min
    noise = CGMNoise(sensor_params(), seed=noise_seed)

    minutes = scenario.days * 1440
    plasma = np.empty(minutes)
    isf = np.empty(minutes)
    meals = scenario.meals.set_index("minute")
    sens, uptake = scenario.sensitivity, scenario.uptake
    n_samples = minutes // SAMPLE_MIN
    cgm = np.empty(n_samples)
    cgm_noise = np.empty(n_samples)
    events = []
    last_cgm = np.nan
    current = (None, None)
    day_offset = start.hour * 60 + start.minute
    last_treatment, rescue = -np.inf, 0.0

    for m in range(minutes):
        if (sens[m], uptake[m]) != current:
            params = base.copy()
            params["Vmx"] = float(base["Vmx"]) * sens[m]
            params["kp3"] = float(base["kp3"]) * sens[m]
            params["Vm0"] = float(base["Vm0"]) * uptake[m]
            patient._params = params
            current = (sens[m], uptake[m])
        plasma[m] = patient.state[3] / vg
        isf[m] = patient.state[12] / vg
        if m % SAMPLE_MIN == 0:
            k = m // SAMPLE_MIN
            cgm_noise[k] = next(noise)
            cgm[k] = isf[m] + cgm_noise[k]
            last_cgm = min(max(cgm[k], limits[0]), limits[1])  # what the device would display
            if treatment is not None and treatment.treats(
                last_cgm, (day_offset + m) % 1440, m - last_treatment
            ):
                rescue, last_treatment = treatment.grams, m
                events.append((m, "rescue", treatment.grams))

        cho, bolus = rescue, 0.0
        rescue = 0.0
        if m in meals.index:
            for _, meal in meals.loc[[m]].iterrows():
                if meal["eaten"]:
                    cho += meal["carbs_true"]
                    events.append((m, "meal_eaten", meal["carbs_true"]))
                if meal["bolus_given"]:
                    dose = meal["carbs_announced"] / (cr * therapy.bolus_scale)
                    if last_cgm > therapy.correction_above:
                        dose += (last_cgm - therapy.target) / (cf * therapy.bolus_scale)
                    bolus += dose
                    events.append((m, "carbs_announced", meal["carbs_announced"]))
                    events.append((m, "bolus", dose))
        patient.step(Action(CHO=cho, insulin=basal + bolus))

    for _, s in scenario.exercise.iterrows():
        events += [(s["start"], "exercise_start", 1.0), (s["end"], "exercise_end", 1.0)]
    ev = pd.DataFrame(events, columns=["minute", "kind", "value"]).sort_values(
        "minute", kind="stable"
    )
    ev["time"] = (start + pd.to_timedelta(ev["minute"], unit="min")).astype("datetime64[ns]")

    sample_min = np.arange(n_samples) * SAMPLE_MIN
    boluses = ev[ev["kind"] == "bolus"]
    entries = ev[ev["kind"] == "carbs_announced"]
    rescues = ev[ev["kind"] == "rescue"]
    lo, hi = limits
    flag = np.where(cgm < lo, "below_range", np.where(cgm > hi, "above_range", "ok"))
    # Doses and carb entries go on the first sample at or after them, so features stay causal.
    slot = lambda minutes: (np.ceil(np.asarray(minutes) / SAMPLE_MIN)).astype(int)  # noqa: E731
    per_sample = lambda frame: np.bincount(  # noqa: E731
        np.minimum(slot(frame["minute"]), n_samples - 1),
        weights=frame["value"],
        minlength=n_samples,
    )
    exercising = np.zeros(n_samples, dtype=bool)
    for _, s in scenario.exercise.iterrows():
        exercising[(sample_min >= s["start"]) & (sample_min < s["end"])] = True
    samples = pd.DataFrame(
        {
            "patient_id": f"sim:{name}",
            "time": (start + pd.to_timedelta(sample_min, unit="min")).astype("datetime64[ns]"),
            "glucose": np.clip(cgm, lo, hi),
            "glucose_flag": flag,
            "source": "simglucose",
            "insulin_bolus": per_sample(boluses),
            "insulin_basal": basal * SAMPLE_MIN,
            "carbs": per_sample(entries),
            "truth_glucose": plasma[sample_min],
            "isf_glucose": isf[sample_min],
            "cgm_noise": cgm_noise,
            "iob": iob(boluses["minute"], boluses["value"], sample_min, dia_h=dia_h),
            "cob": cob(entries["minute"], entries["value"], sample_min, absorption_h=cob_h),
            "sensitivity": sens[sample_min],
            "exercising": exercising,
            "rescue_carbs": per_sample(rescues),  # eaten, never logged (truth side)
        }
    )
    truth = pd.DataFrame(
        {
            "patient_id": f"sim:{name}",
            "time": (start + pd.to_timedelta(np.arange(minutes), unit="min")).astype(
                "datetime64[ns]"
            ),
            "truth_glucose": plasma.astype(np.float32),
        }
    )
    return SimResult(
        samples=samples,
        truth=truth,
        events=ev.reset_index(drop=True),
        valid=bool(plasma.min() >= VALIDITY_FLOOR),
        nadir=float(plasma.min()),
    )


def first_order_lag(signal_1min: np.ndarray, tau_min: float) -> np.ndarray:
    """First-order low-pass of a 1-min signal (blood-to-interstitial lag, SIMULATION.md §1).

    y[0] = x[0]; y[n] = y[n-1] + a * (x[n-1] - y[n-1]) with a = 1 - exp(-1/tau).
    """
    from scipy.signal import lfilter

    x = np.asarray(signal_1min, dtype=float)
    a = 1 - np.exp(-1.0 / tau_min)
    # transposed direct form: y[0] = b0 * x[0] + zi with b0 = 0, so zi = x[0] starts at x[0]
    y, _ = lfilter([0.0, a], [1.0, -(1 - a)], x, zi=[x[0]])
    return y
