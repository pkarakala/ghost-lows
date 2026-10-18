"""Loader for Dexcom Clarity CSV exports (docs/DATA.md §4)."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .schema import (
    DEVICE_LIMITS_MG_DL,
    MG_DL_PER_MMOL_L,
    Source,
    finalize,
    read_csv_text,
    read_text,
)

SOURCE_NAME = "dexcom_clarity"
# The 14 columns of a US (mg/dL) export (docs/DATA.md §4); used to write synthetic files
EXPORT_COLUMNS = [
    "Index",
    "Timestamp (YYYY-MM-DDThh:mm:ss)",
    "Event Type",
    "Event Subtype",
    "Patient Info",
    "Device Info",
    "Source Device ID",
    "Glucose Value (mg/dL)",
    "Insulin Value (u)",
    "Carb Value (grams)",
    "Duration (hh:mm:ss)",
    "Glucose Rate of Change (mg/dL/min)",
    "Transmitter Time (Long Integer)",
    "Transmitter ID",
]


def _column(df: pd.DataFrame, prefix: str) -> str:
    """The column whose name starts with `prefix` (case-insensitive), ignoring units."""
    for col in df.columns:
        if col.lower().startswith(prefix):
            return col
    raise ValueError(f"not a Clarity export: no column starting with {prefix!r}")


def _number(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values.str.replace(",", ".", regex=False), errors="coerce")


def load_clarity(
    source: Source,
    patient_id: str = "upload",
    limits: tuple[float, float] = DEVICE_LIMITS_MG_DL,
) -> pd.DataFrame:
    """A Clarity export in the common schema.

    Keeps EGV rows as glucose readings and Insulin/Carbs rows as events; ignores metadata
    rows (names, devices), alerts and calibrations. "Low"/"High" become the device limits
    with a flag. mmol/L exports are converted to mg/dL. Personal details in the export are
    never read into the table.
    """
    df = read_csv_text(read_text(source))
    ts_col, type_col = _column(df, "timestamp"), _column(df, "event type")
    sub_col, gl_col = _column(df, "event subtype"), _column(df, "glucose value")
    unit = re.search(r"\((.*?)\)", gl_col)
    mmol = bool(unit and "mmol" in unit.group(1).lower())

    df = df[df[ts_col] != ""]
    times = pd.to_datetime(df[ts_col].str.replace("T", " ", regex=False), errors="coerce")
    if times.isna().any():
        bad = df.loc[times.isna(), ts_col].iloc[0]
        raise ValueError(f"unreadable Clarity timestamp {bad!r}")
    event = df[type_col].str.lower()

    out = pd.DataFrame({"time": times, "glucose_flag": "ok"})
    egv = event == "egv"
    text = df[gl_col].str.lower()
    glucose = _number(df[gl_col]) * (MG_DL_PER_MMOL_L if mmol else 1.0)
    low, high = egv & (text == "low"), egv & (text == "high")
    glucose[low], glucose[high] = limits[0], limits[1]
    out["glucose"] = glucose.where(egv, np.nan)
    out.loc[low, "glucose_flag"] = "below_range"
    out.loc[high, "glucose_flag"] = "above_range"

    insulin = _number(df[_column(df, "insulin value")])
    subtype = df[sub_col].str.lower()
    is_insulin = event == "insulin"
    out["insulin_bolus"] = insulin.where(is_insulin & ~subtype.str.contains("long"), np.nan)
    out["insulin_basal"] = insulin.where(is_insulin & subtype.str.contains("long"), np.nan)
    out["carbs"] = _number(df[_column(df, "carb value")]).where(event == "carbs", np.nan)

    keep = egv | out[["insulin_bolus", "insulin_basal", "carbs"]].notna().any(axis=1)
    out = out[keep & (out["glucose"].notna() | ~egv)]
    out["patient_id"] = f"clarity:{patient_id}"
    out["source"] = SOURCE_NAME
    return finalize(out)
