"""Real-time low-glucose alarms behind a common causal interface
(docs/reference/BENCHMARK.md §1-2)."""

from .base import FLOOR_MG_DL, Alarm, BaseAlarm, fire_events, view
from .kalman_pisa import KalmanParams, KalmanPisaAlarm
from .learned import ARMS, DETECTORS, CombinedAlarm, GatedAlarm, GBMAlarm
from .rules import FloorOnlyAlarm, ThresholdAlarm, TrendAlarm


def benchmark_alarms(seed: int = 0) -> list:
    """Every alarm of BENCHMARK.md §2: references, as-published gates, four arms per detector.

    The as-published gate and the four arms of a detector share one detector instance, so it is
    fitted once per training set and its gate is computed once per run.
    """
    detectors = {
        name: (make(seed=seed) if name == "iforest_causal" else make())
        for name, make in DETECTORS.items()
    }
    alarms = [FloorOnlyAlarm(), ThresholdAlarm(), TrendAlarm()]
    alarms += [
        GatedAlarm(detectors[n]) for n in ("baysal", "matched_filter_causal", "iforest_causal")
    ]
    for name in DETECTORS:
        alarms += [CombinedAlarm(detectors[name], arm, seed=seed) for arm in ARMS]
    alarms += [GBMAlarm(arm, seed=seed) for arm in ARMS]
    return alarms


def stretch_alarms() -> list:
    """Alarms outside the pre-registered set of `benchmark_alarms` (RQ3, amendment A3): the
    multiple-model Kalman filter with a compressed state, without inputs, and without the
    compressed state. A config selects them by name; `alarms: all` does not include them."""
    return [
        KalmanPisaAlarm(inputs=True),
        KalmanPisaAlarm(inputs=False),
        KalmanPisaAlarm(inputs=True, pressure=False),
    ]


__all__ = [
    "ARMS",
    "DETECTORS",
    "FLOOR_MG_DL",
    "Alarm",
    "BaseAlarm",
    "CombinedAlarm",
    "FloorOnlyAlarm",
    "GBMAlarm",
    "GatedAlarm",
    "KalmanParams",
    "KalmanPisaAlarm",
    "ThresholdAlarm",
    "TrendAlarm",
    "benchmark_alarms",
    "fire_events",
    "stretch_alarms",
    "view",
]
