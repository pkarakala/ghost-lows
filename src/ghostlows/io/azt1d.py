"""Loader for AZT1D [AZT1D 2025] (docs/DATA.md §1), read from the archive saved by
`scripts/download_data.py --azt1d`: 25 adults with type 1 diabetes on automated insulin delivery,
Dexcom CGM every 5 min, local Arizona time (no daylight saving time).

Boluses are split into user-entered (`insulin_bolus`) and automatic (`insulin_bolus_auto`). The
automatic ones respond to the CGM, so context built from them would carry the CGM's own
information, compression lows included; context uses user-entered boluses and carbs only (D9).
Exact duplicate rows are dropped. A timestamp with two different CGM values cannot be resolved,
so its CGM is set missing (185 of 300,923 timestamps in the archive checked on 2026-10-18).
"""

from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .schema import DEVICE_LIMITS_MG_DL, finalize, read_csv_text

# Repository checkout by default; GHOSTLOWS_DATA_DIR points elsewhere (it replaces `data/`).
_DATA = os.environ.get("GHOSTLOWS_DATA_DIR") or Path(__file__).resolve().parents[3] / "data"
DEFAULT_ZIP = Path(_DATA) / "raw" / "azt1d" / "AZT1D_2025.zip"
MEMBER = re.compile(r"^AZT1D 2025/CGM Records/Subject (\d+)/Subject \1\.csv$")
GLUCOSE_COLUMNS = ("CGM", "Readings (CGM / BGM)")  # the second name appears in one subject
AUTOMATIC = "Automatic Bolus/Correction"
# User-entered bolus types in the archive; for an extended bolus only the part delivered at the
# time is recorded.
# ASSUMPTION: the extended remainder, in about 60 of 300,000 rows, is ignored
USER = re.compile(r"^(Standard|BLE Standard Bolus|Quick|Extended)")
MODES = {"sleep": "sleep", "sleepsleep": "sleep", "exercise": "exercise"}


def load_azt1d(path: str | Path | None = None, subjects=None) -> pd.DataFrame:
    """AZT1D in the common schema plus `insulin_bolus_auto` (U) and `device_mode` ('sleep',
    'exercise' or ''). Patient IDs are `azt1d:<subject>`. `subjects` limits the subjects read."""
    with zipfile.ZipFile(path or DEFAULT_ZIP) as zf:
        members = {int(m.group(1)): n for n in zf.namelist() if (m := MEMBER.match(n))}
        if not members:
            raise ValueError("no 'CGM Records/Subject N/Subject N.csv' files in the archive")
        frames = [
            _subject(zf.read(members[s]), s)
            for s in sorted(members)
            if subjects is None or s in subjects
        ]
    return finalize(pd.concat(frames, ignore_index=True))


def _subject(data: bytes, subject: int) -> pd.DataFrame:
    raw = read_csv_text(data.decode("utf-8-sig", errors="replace")).drop_duplicates()
    column = next((c for c in GLUCOSE_COLUMNS if c in raw), None)
    if column is None:
        raise ValueError(f"subject {subject}: no glucose column among {GLUCOSE_COLUMNS}")
    time = pd.to_datetime(raw["EventDateTime"])
    glucose = pd.to_numeric(raw[column], errors="coerce")
    conflict = glucose.groupby(time).transform("nunique") > 1
    glucose = glucose.where(~conflict)
    lo, hi = DEVICE_LIMITS_MG_DL
    flag = np.select([glucose <= lo, glucose >= hi], ["below_range", "above_range"], "ok")
    kind = raw["BolusType"]
    units = pd.to_numeric(raw["TotalBolusInsulinDelivered"], errors="coerce")
    carbs = pd.to_numeric(raw["CarbSize"], errors="coerce")
    return pd.DataFrame(
        {
            "patient_id": f"azt1d:{subject}",
            "time": time,
            "glucose": glucose.clip(lo, hi),
            "glucose_flag": flag,
            "source": "azt1d",
            "insulin_bolus": units.where(kind.str.match(USER) & (units > 0)),
            "insulin_bolus_auto": units.where((kind == AUTOMATIC) & (units > 0)),
            "insulin_basal": pd.to_numeric(raw["Basal"], errors="coerce"),
            "carbs": carbs.where(carbs > 0),
            "device_mode": raw["DeviceMode"].map(MODES).fillna(""),
        }
    )
