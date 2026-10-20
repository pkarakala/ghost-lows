"""Loader for LibreView CSV exports (docs/reference/DATA.md §4)."""

from __future__ import annotations

import re
import warnings

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

SOURCE_NAME = "libreview"
HISTORIC, SCAN = "0", "1"  # Record Type codes for CGM history and scans

_STAMP = re.compile(
    r"^(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?$"
)


def parse_timestamps(values: pd.Series, dayfirst: bool | None = None) -> pd.Series:
    """Parse LibreView device timestamps, whose date order depends on the export's locale.

    ISO dates (year first) are unambiguous. Otherwise, with `dayfirst=None` the order is
    inferred: a first field above 12 means day first, a second field above 12 means month
    first. If neither occurs the order cannot be known; month first (US) is used with a warning.
    """
    parts = values.str.extract(_STAMP)
    if parts[0].isna().any():
        bad = values[parts[0].isna()].iloc[0]
        raise ValueError(f"unreadable LibreView timestamp {bad!r}")
    a, b, c = (parts[i].astype(int) for i in range(3))
    hour, minute = parts[3].astype(int), parts[4].astype(int)
    second = parts[5].fillna("0").astype(int)
    ampm = parts[6].fillna("").str.lower()
    twelve_hour = ampm != ""
    hour = hour.where(~twelve_hour, hour % 12 + 12 * (ampm == "pm"))
    if (parts[0].str.len() == 4).all():
        year, month, day = a, b, c
    else:
        if dayfirst is None:
            if (a > 12).any():
                dayfirst = True
            elif (b > 12).any():
                dayfirst = False
            else:
                warnings.warn(
                    "LibreView dates are ambiguous (no day above 12); assuming month first",
                    stacklevel=2,
                )
                dayfirst = False
        day, month = (a, b) if dayfirst else (b, a)
        year = c.where(c >= 100, c + 2000)
    stamps = pd.to_datetime(
        pd.DataFrame(
            {
                "year": year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
            }
        ),
        errors="coerce",
    )
    if stamps.isna().any():
        raise ValueError("invalid LibreView date (check the day/month order)")
    return stamps


def _find(df: pd.DataFrame, *prefixes: str) -> str | None:
    for col in df.columns:
        if col.lower().startswith(prefixes):
            return col
    return None


def load_libreview(
    source: Source,
    patient_id: str = "upload",
    dayfirst: bool | None = None,
    include_scans: bool = False,
    limits: tuple[float, float] = DEVICE_LIMITS_MG_DL,
) -> pd.DataFrame:
    """A LibreView export in the common schema.

    Uses historic CGM rows (Record Type 0) as glucose readings; scans only if `include_scans`.
    Insulin and carbohydrate entries become event rows. "LO"/"HI" become the device limits with
    a flag. The metadata line above the header (export date, patient name) is skipped and never
    read into the table.
    """
    text = read_text(source)
    lines = text.splitlines()
    header = next((i for i, line in enumerate(lines[:10]) if "Device Timestamp" in line), None)
    if header is None:
        raise ValueError("not a LibreView export: no 'Device Timestamp' header")
    df = read_csv_text(text, skiprows=header)
    df = df[df["Device Timestamp"] != ""]
    times = parse_timestamps(df["Device Timestamp"], dayfirst)
    rtype = df["Record Type"]

    historic = _find(df, "historic glucose")
    if historic is None:
        raise ValueError("not a LibreView export: no 'Historic Glucose' column")
    mmol = "mmol" in historic.lower()
    out = pd.DataFrame({"time": times, "glucose_flag": "ok"})
    raw = df[historic].where(rtype == HISTORIC, "")
    scan = _find(df, "scan glucose")
    if include_scans and scan:
        raw = raw.where(rtype != SCAN, df[scan])
    lower = raw.str.lower()
    glucose = pd.to_numeric(raw.str.replace(",", ".", regex=False), errors="coerce")
    glucose = glucose * (MG_DL_PER_MMOL_L if mmol else 1.0)
    low, high = lower.isin(["lo", "low"]), lower.isin(["hi", "high"])
    glucose[low], glucose[high] = limits[0], limits[1]
    out["glucose"] = glucose
    out.loc[low, "glucose_flag"] = "below_range"
    out.loc[high, "glucose_flag"] = "above_range"

    def number(*prefixes: str) -> pd.Series:
        col = _find(df, *prefixes)
        if col is None:
            return pd.Series(np.nan, index=df.index)
        return pd.to_numeric(df[col].str.replace(",", ".", regex=False), errors="coerce")

    out["insulin_bolus"] = number("rapid-acting insulin (units)", "meal insulin")
    out["insulin_basal"] = number("long-acting insulin")
    out["carbs"] = number("carbohydrates (grams)")

    out = out[
        out["glucose"].notna()
        | out[["insulin_bolus", "insulin_basal", "carbs"]].notna().any(axis=1)
    ]
    out["patient_id"] = f"libreview:{patient_id}"
    out["source"] = SOURCE_NAME
    return finalize(out)
