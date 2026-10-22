"""Loaders for datasets and device exports into the common schema (DATA.md §3). Pyodide-safe."""

from importlib import resources
from pathlib import Path

import pandas as pd

from .azt1d import load_azt1d
from .clarity import load_clarity
from .glucobench import load_glucobench
from .libreview import load_libreview
from .schema import COLUMNS, FLAGS, Source, read_text, validate


def detect_export(source: Source) -> str:
    """'clarity' or 'libreview', from the export's header lines."""
    head = read_text(source)[:4000]
    if "Event Type" in head and "Glucose Value" in head:
        return "clarity"
    if "Device Timestamp" in head and "Record Type" in head:
        return "libreview"
    raise ValueError("not a recognised Dexcom Clarity or LibreView CSV export")


def load_export(source: Source, patient_id: str = "upload") -> pd.DataFrame:
    """Load a Dexcom Clarity or LibreView CSV export, whichever it is.

    `source` is a path, bytes or an open file. Returns the common schema (DATA.md §3): one row
    per reading or event, glucose in mg/dL (mmol/L exports are converted), `patient_id` prefixed
    with the export type.
    """
    text = read_text(source)
    kind = detect_export(text.encode())
    loader = load_clarity if kind == "clarity" else load_libreview
    return loader(text.encode(), patient_id=patient_id)


def sample_export() -> bytes:
    """The synthetic 14-day Dexcom Clarity export used by the upload report's sample data.

    One simulated benchmark run (a virtual adult) with injected sensor faults, including
    compression artifacts; no real person's data. Returns the CSV as bytes, ready for
    `load_clarity`.
    """
    packaged = resources.files("ghostlows").joinpath("data", "sample_clarity_export.csv")
    if packaged.is_file():
        return packaged.read_bytes()
    # editable install: the wheel copies it from app/ (pyproject.toml, force-include)
    return (Path(__file__).resolve().parents[3] / "app" / "sample_clarity_export.csv").read_bytes()


__all__ = [
    "COLUMNS",
    "FLAGS",
    "detect_export",
    "load_azt1d",
    "load_clarity",
    "load_export",
    "load_glucobench",
    "load_libreview",
    "sample_export",
    "validate",
]
