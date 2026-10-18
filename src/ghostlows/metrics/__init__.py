"""Consensus CGM metrics (TIR, TBR, TAR, CV, GMI, AGP). Pyodide-safe."""

from .consensus import agp, sampling_interval, summary, summary_by_patient, wear_percent

__all__ = ["agp", "sampling_interval", "summary", "summary_by_patient", "wear_percent"]
