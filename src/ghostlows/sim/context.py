"""Insulin and carbohydrates on board from recorded events (SIMULATION.md §2).

Pure numpy, so the same functions serve simulated and real data. Every value at time t uses only
events at or before t.
"""

from __future__ import annotations

import numpy as np


def iob_fraction(minutes_ago: np.ndarray, dia_h: float = 5.0, peak_min: float = 75.0) -> np.ndarray:
    """Fraction of a bolus still on board after `minutes_ago` minutes.

    Exponential insulin action curve of the kind used by open-source dosing software, with
    duration `dia_h` and activity peak `peak_min`; 1 at the time of the bolus and 0 from the
    end of the action duration.
    """
    # ASSUMPTION: exponential action curve, peak 75 min, duration 5 h; configurable, with
    # sensitivity at 3 and 7 h (SIMULATION.md §2).
    end = dia_h * 60.0
    if not 0 < 2 * peak_min < end:
        raise ValueError("need 0 < 2 * peak_min < dia_h * 60")
    tau = peak_min * (1 - peak_min / end) / (1 - 2 * peak_min / end)
    a = 2 * tau / end
    s = 1 / (1 - a + (1 + a) * np.exp(-end / tau))
    t = np.clip(np.asarray(minutes_ago, dtype=float), 0.0, end)
    frac = 1 - s * (1 - a) * ((t**2 / (tau * end * (1 - a)) - t / tau - 1) * np.exp(-t / tau) + 1)
    return np.where(np.asarray(minutes_ago) >= end, 0.0, np.clip(frac, 0.0, 1.0))


def cob_fraction(minutes_ago: np.ndarray, absorption_h: float = 3.0) -> np.ndarray:
    """Fraction of announced carbohydrate not yet absorbed, linear over `absorption_h` hours."""
    # ASSUMPTION: linear absorption over 3 h (SIMULATION.md §2)
    return np.clip(1 - np.asarray(minutes_ago, dtype=float) / (absorption_h * 60.0), 0.0, 1.0)


def on_board(
    event_minutes: np.ndarray,
    amounts: np.ndarray,
    query_minutes: np.ndarray,
    kernel,
    horizon_min: float,
) -> np.ndarray:
    """Sum of `amount * kernel(query - event)` over events at or before each query time."""
    event_minutes = np.asarray(event_minutes, dtype=float)
    amounts = np.asarray(amounts, dtype=float)
    query = np.asarray(query_minutes, dtype=float)
    out = np.zeros(query.shape)
    order = np.argsort(event_minutes)
    event_minutes, amounts = event_minutes[order], amounts[order]
    for t_event, amount in zip(event_minutes, amounts, strict=True):
        lo, hi = np.searchsorted(query, [t_event, t_event + horizon_min])
        if lo < hi and amount:
            out[lo:hi] += amount * kernel(query[lo:hi] - t_event)
    return out


def iob(bolus_minutes, bolus_units, query_minutes, dia_h: float = 5.0, peak_min: float = 75.0):
    """Insulin on board (units) at each sorted query minute."""
    return on_board(
        bolus_minutes,
        bolus_units,
        query_minutes,
        lambda dt: iob_fraction(dt, dia_h, peak_min),
        dia_h * 60,
    )


def cob(carb_minutes, carb_grams, query_minutes, absorption_h: float = 3.0):
    """Carbohydrates on board (grams) at each sorted query minute."""
    return on_board(
        carb_minutes,
        carb_grams,
        query_minutes,
        lambda dt: cob_fraction(dt, absorption_h),
        absorption_h * 60,
    )
