"""Scenario generation: meals, recording errors, sensitivity drift and exercise (SIMULATION.md §3).

Everything here is drawn up front from one seeded generator, so a scenario can be inspected and
reproduced without running the simulator. Times are minutes from the start of day 0 (00:00).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

# SOURCE: simglucose (RandomScenario meal slots: breakfast, snack, lunch, snack, dinner, snack)
MEAL_PROB = (0.95, 0.3, 0.95, 0.3, 0.95, 0.3)
MEAL_TIME_LB_H = (5, 9, 10, 14, 16, 20)
MEAL_TIME_UB_H = (9, 10, 14, 16, 20, 23)
MEAL_TIME_MU_H = (7, 9.5, 12, 15, 18, 21.5)
MEAL_TIME_SD_MIN = (60, 30, 60, 30, 60, 30)
MEAL_AMOUNT_MU_G = (45, 10, 70, 10, 80, 10)
MEAL_AMOUNT_SD_G = (10, 5, 10, 5, 10, 5)


@dataclass(frozen=True)
class Mix:
    """Scenario-family settings. The values of `DEFAULT` are SIMULATION.md §3."""

    name: str
    carb_error_sd: float = 0.0  # announced = true x (1 + e), e ~ N(0, sd)
    p_missed_bolus: float = 0.0  # meal eaten, no bolus and no carb entry
    p_skipped_meal: float = 0.0  # bolus given and carbs entered, meal not eaten
    sensitivity_range: tuple[float, float] = (1.0, 1.0)  # day-level multiplier ~ U(lo, hi)
    exercise_per_week: tuple[int, int] = (0, 0)  # sessions per week ~ U{lo..hi}
    exercise_minutes: tuple[int, int] = (30, 60)
    # ASSUMPTION: exercise raises insulin-independent uptake during the session and insulin
    # sensitivity afterwards, decaying exponentially (CR13; the 2008 model has no exercise).
    exercise_uptake_gain: float = 0.5  # Vm0 x (1 + gain) during the session
    exercise_sensitivity_gain: float = 0.5  # Vmx, kp3 x (1 + gain * exp(-dt / tau))
    exercise_sensitivity_tau_min: float = 360.0
    exercise_window_h: tuple[float, float] = (16.0, 20.0)  # session start, local time


STANDARD = Mix("standard")
# ASSUMPTION: SIMULATION.md §3 values (CR13)
DEFAULT = Mix(
    "default",
    carb_error_sd=0.2,
    p_missed_bolus=0.05,
    p_skipped_meal=0.02,
    sensitivity_range=(0.7, 1.3),
    exercise_per_week=(2, 4),
)
# ASSUMPTION: every perturbation doubled relative to DEFAULT (D3)
HIGH = Mix(
    "high",
    carb_error_sd=0.4,
    p_missed_bolus=0.10,
    p_skipped_meal=0.04,
    sensitivity_range=(0.4, 1.6),
    exercise_per_week=(4, 8),
)
MIXES = {m.name: m for m in (STANDARD, DEFAULT, HIGH)}


def get_mix(name: str, **overrides) -> Mix:
    if name not in MIXES:
        raise ValueError(f"unknown scenario mix {name!r}; expected one of {sorted(MIXES)}")
    return replace(MIXES[name], **overrides)


@dataclass
class Scenario:
    """Pre-drawn events for one patient-run."""

    meals: pd.DataFrame  # minute, carbs_true, carbs_announced, bolus_given, eaten, slot
    sensitivity: np.ndarray  # per-minute multiplier on insulin action (Vmx, kp3)
    uptake: np.ndarray  # per-minute multiplier on insulin-independent uptake (Vm0)
    exercise: pd.DataFrame  # start, end (minutes)
    days: int
    mix: Mix = field(default=STANDARD)


def _truncnorm(rng: np.random.Generator, mu: float, sd: float, lo: float, hi: float) -> float:
    while True:
        x = rng.normal(mu, sd)
        if lo <= x <= hi:
            return x


def draw_meals(rng: np.random.Generator, days: int) -> pd.DataFrame:
    rows = []
    for day in range(days):
        for slot in range(len(MEAL_PROB)):
            if rng.random() >= MEAL_PROB[slot]:
                continue
            t = _truncnorm(
                rng,
                MEAL_TIME_MU_H[slot] * 60,
                MEAL_TIME_SD_MIN[slot],
                MEAL_TIME_LB_H[slot] * 60,
                MEAL_TIME_UB_H[slot] * 60,
            )
            carbs = max(round(rng.normal(MEAL_AMOUNT_MU_G[slot], MEAL_AMOUNT_SD_G[slot])), 0)
            if carbs > 0:
                rows.append(
                    {"minute": day * 1440 + int(round(t)), "carbs_true": float(carbs), "slot": slot}
                )
    return pd.DataFrame(rows, columns=["minute", "carbs_true", "slot"])


def make_scenario(mix: Mix, days: int, meal_seed: int, perturb_seed: int) -> Scenario:
    """Meals come from `meal_seed` alone, so one patient-seed has the same meals in every mix;
    recording errors, sensitivity drift and exercise come from `perturb_seed`."""
    meals = draw_meals(np.random.default_rng(meal_seed), days)
    rng = np.random.default_rng(perturb_seed)
    n = len(meals)
    error = rng.normal(0.0, mix.carb_error_sd, n) if mix.carb_error_sd else np.zeros(n)
    missed = rng.random(n) < mix.p_missed_bolus
    skipped = (rng.random(n) < mix.p_skipped_meal) & ~missed
    meals["carbs_announced"] = np.where(
        missed, 0.0, np.round(meals["carbs_true"] * np.clip(1 + error, 0.1, None))
    )
    meals["bolus_given"] = ~missed
    meals["eaten"] = ~skipped

    minutes = days * 1440
    sensitivity = np.ones(minutes)
    lo, hi = mix.sensitivity_range
    if hi > lo:
        # ASSUMPTION: the day-level multiplier switches at 12:00, away from the night window, so
        # that the switch itself does not create nocturnal transients.
        for day in range(days + 1):
            start, end = max(0, day * 1440 - 720), min(minutes, day * 1440 + 720)
            if start < end:
                sensitivity[start:end] = rng.uniform(lo, hi)

    uptake = np.ones(minutes)
    sessions = []
    if mix.exercise_per_week[1] > 0:
        for week in range(int(np.ceil(days / 7))):
            week_days = list(range(week * 7, min(days, week * 7 + 7)))
            k = int(rng.integers(mix.exercise_per_week[0], mix.exercise_per_week[1] + 1))
            k = min(k, len(week_days))
            for day in sorted(rng.choice(week_days, size=k, replace=False)):
                start = int(day * 1440 + rng.uniform(*mix.exercise_window_h) * 60)
                end = start + int(
                    rng.integers(mix.exercise_minutes[0], mix.exercise_minutes[1] + 1)
                )
                sessions.append({"start": start, "end": end})
    t = np.arange(minutes)
    after = np.zeros(minutes)
    for s in sessions:
        uptake[s["start"] : min(s["end"], minutes)] *= 1 + mix.exercise_uptake_gain
        dt = t - s["end"]
        boost = np.where(
            dt >= 0,
            mix.exercise_sensitivity_gain * np.exp(-dt / mix.exercise_sensitivity_tau_min),
            0.0,
        )
        after = np.maximum(after, boost)
    sensitivity = sensitivity * (1 + after)
    return Scenario(
        meals=meals.reset_index(drop=True),
        sensitivity=sensitivity,
        uptake=uptake,
        exercise=pd.DataFrame(sessions, columns=["start", "end"]),
        days=days,
        mix=mix,
    )
