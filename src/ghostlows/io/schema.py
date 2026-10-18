"""The common long-table schema every loader returns (docs/DATA.md §3)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import IO

import numpy as np
import pandas as pd

COLUMNS = [
    "patient_id",
    "time",
    "glucose",
    "glucose_flag",
    "source",
    "insulin_bolus",
    "insulin_basal",
    "carbs",
]
FLAGS = ["ok", "below_range", "above_range", "missing"]
EVENT_COLUMNS = ["insulin_bolus", "insulin_basal", "carbs"]

# ASSUMPTION: reportable range of current Dexcom and Libre sensors; censored "Low"/"High"
# readings are stored at these limits (with a flag). Configurable per loader call.
DEVICE_LIMITS_MG_DL = (40.0, 400.0)

# ASSUMPTION: devices convert with 1 mmol/L = 18 mg/dL (the molar-mass factor is 18.016).
MG_DL_PER_MMOL_L = 18.0

Source = str | Path | bytes | IO[str] | IO[bytes]


def read_text(source: Source) -> str:
    """Text of a CSV given as a path, bytes or an open file (e.g. a browser upload)."""
    if isinstance(source, str | Path):
        data = Path(source).read_bytes()
    elif isinstance(source, bytes):
        data = source
    else:
        data = source.read()
    if isinstance(data, str):
        return data
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("could not decode the file as text")


def read_csv_text(text: str, skiprows: int = 0) -> pd.DataFrame:
    """All cells as stripped strings; empty cells become ''."""
    df = pd.read_csv(
        io.StringIO(text),
        skiprows=skiprows,
        dtype=str,
        keep_default_na=False,
        skipinitialspace=True,
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df.apply(lambda col: col.str.strip())


def finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Add missing columns, fix dtypes and order, sort by patient and time."""
    df = df.copy()
    for col in EVENT_COLUMNS + ["glucose"]:
        if col not in df:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    if "glucose_flag" not in df:
        df["glucose_flag"] = "ok"
    df.loc[df["glucose"].isna(), "glucose_flag"] = "missing"
    df["glucose_flag"] = pd.Categorical(df["glucose_flag"], categories=FLAGS)
    df["patient_id"] = df["patient_id"].astype(str)
    df["source"] = df["source"].astype(str)
    df["time"] = pd.to_datetime(df["time"])
    extra = [c for c in df.columns if c not in COLUMNS]
    df = df[COLUMNS + extra].sort_values(["patient_id", "time"], kind="stable")
    return df.reset_index(drop=True)


def validate(df: pd.DataFrame) -> None:
    """Raise ValueError if `df` does not follow the common schema."""
    missing = [c for c in COLUMNS if c not in df]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    if not pd.api.types.is_datetime64_any_dtype(df["time"]):
        raise ValueError("time must be datetime64")
    if getattr(df["time"].dt, "tz", None) is not None:
        raise ValueError("time must be naive local time")
    bad = set(df["glucose_flag"].astype(str)) - set(FLAGS)
    if bad:
        raise ValueError(f"unknown glucose_flag values: {sorted(bad)}")
    if (df["glucose"].isna() != (df["glucose_flag"] == "missing")).any():
        raise ValueError("glucose is NaN exactly when glucose_flag is 'missing'")
