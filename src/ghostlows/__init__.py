"""Ghost Lows: an open benchmark for real-time CGM low-glucose alarms under sensor faults.

The public API is what `__all__` lists; everything else may change between versions.

    import ghostlows as gl

    trace = gl.load_clarity(gl.sample_export())
    trace = trace[trace["glucose"].notna()]
    config = gl.FaultConfig(pisa_fraction=1.0, enabled=frozenset({"pisa"}))
    observed, faults = gl.apply_faults(trace, config, seed=1)
    gl.score_alarm(gl.TrendAlarm(), observed, gl.low_events(trace), faults)

See examples/quickstart.py. Glucose is in mg/dL and times are timestamps throughout.
"""

__version__ = "0.2.3"

from .alarms import Alarm, BaseAlarm, FloorOnlyAlarm, ThresholdAlarm, TrendAlarm, benchmark_alarms
from .bench.events import low_events
from .bench.scoring import Windows, score_alarm
from .faults import FaultConfig, apply_faults
from .io import load_clarity, load_export, load_libreview, sample_export
from .metrics import agp, summary

__all__ = [
    "Alarm",
    "BaseAlarm",
    "FaultConfig",
    "FloorOnlyAlarm",
    "ThresholdAlarm",
    "TrendAlarm",
    "Windows",
    "__version__",
    "agp",
    "apply_faults",
    "benchmark_alarms",
    "load_clarity",
    "load_export",
    "load_libreview",
    "low_events",
    "sample_export",
    "score_alarm",
    "summary",
]
