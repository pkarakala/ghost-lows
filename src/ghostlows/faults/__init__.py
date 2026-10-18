"""Sensor-fault suite: PISA, dropout, stale, drift, spikes (docs/SIMULATION.md §4)."""

from .calibrate import realistic_fraction
from .pisa import DEPTH, DURATION, Pisa, from_size, sample_sizes
from .suite import FaultConfig, apply_faults, inject_real, stable_onsets

__all__ = [
    "DEPTH",
    "DURATION",
    "FaultConfig",
    "Pisa",
    "apply_faults",
    "from_size",
    "inject_real",
    "realistic_fraction",
    "sample_sizes",
    "stable_onsets",
]
