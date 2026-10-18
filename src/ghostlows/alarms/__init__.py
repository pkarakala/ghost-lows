"""Real-time low-glucose alarms behind a common causal interface (docs/BENCHMARK.md §1-2)."""

from .base import FLOOR_MG_DL, Alarm, BaseAlarm, fire_events, view
from .learned import ARMS, DETECTORS, CombinedAlarm, GatedAlarm, GBMAlarm
from .rules import FloorOnlyAlarm, ThresholdAlarm, TrendAlarm


def benchmark_alarms(seed: int = 0) -> list:
    """Every alarm of BENCHMARK.md §2: references, as-published gates, four arms per detector."""
    alarms = [FloorOnlyAlarm(), ThresholdAlarm(), TrendAlarm()]
    for name in ("baysal", "matched_filter_causal", "iforest_causal"):
        detector = DETECTORS[name]() if name != "iforest_causal" else DETECTORS[name](seed=seed)
        alarms.append(GatedAlarm(detector))
    for name, make in DETECTORS.items():
        for arm in ARMS:
            detector = make(seed=seed) if name == "iforest_causal" else make()
            alarms.append(CombinedAlarm(detector, arm, seed=seed))
    alarms += [GBMAlarm(arm, seed=seed) for arm in ARMS]
    return alarms


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
    "ThresholdAlarm",
    "TrendAlarm",
    "benchmark_alarms",
    "fire_events",
    "view",
]
