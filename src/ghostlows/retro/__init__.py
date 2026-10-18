"""Retrospective "possible compression artifact" flags for uploaded traces. Pyodide-safe."""

from .flags import (
    LABEL,
    METHODS,
    detections,
    flag_possible_artifacts,
    matched_filter_windows,
    without_flagged,
)

__all__ = [
    "LABEL",
    "METHODS",
    "detections",
    "flag_possible_artifacts",
    "matched_filter_windows",
    "without_flagged",
]
