"""Loaders for datasets and device exports into the common schema (DATA.md §3). Pyodide-safe."""

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


def load_export(source: Source, patient_id: str = "upload"):
    """Load a Clarity or LibreView export, whichever it is."""
    text = read_text(source)
    kind = detect_export(text.encode())
    loader = load_clarity if kind == "clarity" else load_libreview
    return loader(text.encode(), patient_id=patient_id)


__all__ = [
    "COLUMNS",
    "FLAGS",
    "detect_export",
    "load_clarity",
    "load_export",
    "load_glucobench",
    "load_libreview",
    "validate",
]
