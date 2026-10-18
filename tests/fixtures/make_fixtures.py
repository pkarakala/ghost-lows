"""Write the synthetic device-export fixtures in this folder. Deterministic; no real data.

    uv run python tests/fixtures/make_fixtures.py

The glucose curve is invented: a daily wave, three meal rises, a short night-time dip shaped
like a compression artifact (night 1, 02:00), a slow genuine-looking low (day 2, 16:00),
three readings below the sensor range (day 3, 04:00) and two above it (day 3, 19:00).
"""

from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta
from pathlib import Path

from ghostlows.io.clarity import EXPORT_COLUMNS

HERE = Path(__file__).resolve().parent
START = datetime(2026, 1, 13)
DAYS = 3
MEALS = [(7, 30, 45, 4.5), (12, 30, 70, 7.0), (18, 30, 80, 8.0)]  # hour, minute, carbs g, units
BASAL = (22, 0, 20.0)  # long-acting insulin at 22:00, units

CLARITY_HEADER = EXPORT_COLUMNS
LIBRE_HEADER = [
    "Device",
    "Serial Number",
    "Device Timestamp",
    "Record Type",
    "Historic Glucose mg/dL",
    "Scan Glucose mg/dL",
    "Non-numeric Rapid-Acting Insulin",
    "Rapid-Acting Insulin (units)",
    "Non-numeric Food",
    "Carbohydrates (grams)",
    "Carbohydrates (servings)",
    "Non-numeric Long-Acting Insulin",
    "Long-Acting Insulin Value (units)",
    "Notes",
    "Strip Glucose mg/dL",
    "Ketone mmol/L",
    "Meal Insulin (units)",
    "Correction Insulin (units)",
    "User Change Insulin (units)",
]


def glucose_at(t: datetime) -> float | str:
    """Synthetic glucose (mg/dL), or 'Low'/'High' outside the sensor range."""
    day = (t - START).days
    minutes = (t - START).total_seconds() / 60 % 1440
    g = 120 + 25 * math.sin(2 * math.pi * (minutes - 360) / 1440)
    for hour, minute, carbs, _ in MEALS:
        dt = minutes - (hour * 60 + minute)
        if 0 <= dt < 240:
            g += carbs * 0.9 * (dt / 60) * math.exp(1 - dt / 60)
    if day == 0 and 120 <= minutes < 180:  # compression-like: fast drop, fast recovery
        dt = minutes - 120
        g -= 45 * (1 - math.exp(-dt / 6)) if dt < 30 else 45 * math.exp(-(dt - 30) / 8)
    if day == 1 and 900 <= minutes < 1080:  # slow genuine-looking low around 16:00
        g -= 75 * math.sin(math.pi * (minutes - 900) / 180)
    if day == 2 and 240 <= minutes < 255:
        return "Low"
    if day == 2 and 1140 <= minutes < 1150:
        return "High"
    return round(g)


def in_gap(t: datetime) -> bool:
    """Day 2, 08:00-08:55: sensor signal lost."""
    return (t - START).days == 1 and t.hour == 8


def clarity_rows() -> list[list[str]]:
    blank = [""] * len(CLARITY_HEADER)
    rows = []

    def add(**cells):
        row = list(blank)
        for key, value in cells.items():
            row[CLARITY_HEADER.index(key)] = str(value)
        rows.append(row)

    ts, et, st = "Timestamp (YYYY-MM-DDThh:mm:ss)", "Event Type", "Event Subtype"
    add(**{et: "FirstName", "Patient Info": "Synthetic"})
    add(**{et: "LastName", "Patient Info": "Fixture"})
    add(**{et: "Device", "Device Info": "Synthetic G7 receiver", "Source Device ID": "fixture"})
    stamp = START
    while stamp < START + timedelta(days=DAYS):
        if not in_gap(stamp):
            add(
                **{
                    ts: stamp.isoformat(),
                    et: "EGV",
                    "Glucose Value (mg/dL)": glucose_at(stamp),
                    "Source Device ID": "fixture",
                    "Transmitter ID": "FIXTURE",
                }
            )
        stamp += timedelta(minutes=5)
    for day in range(DAYS):
        base = START + timedelta(days=day)
        for hour, minute, carbs, units in MEALS:
            t = base + timedelta(hours=hour, minutes=minute)
            add(**{ts: t.isoformat(), et: "Carbs", "Carb Value (grams)": carbs})
            add(**{ts: t.isoformat(), et: "Insulin", st: "Fast-Acting", "Insulin Value (u)": units})
        t = base + timedelta(hours=BASAL[0], minutes=BASAL[1])
        add(**{ts: t.isoformat(), et: "Insulin", st: "Long-Acting", "Insulin Value (u)": BASAL[2]})
    add(**{ts: (START + timedelta(hours=2, minutes=20)).isoformat(), et: "Alert", st: "Low"})
    add(**{ts: (START + timedelta(days=2, hours=4)).isoformat(), et: "Alert", st: "Urgent Low"})
    add(**{ts: (START + timedelta(days=2, hours=19)).isoformat(), et: "Alert", st: "High"})
    add(
        **{
            ts: (START + timedelta(hours=9)).isoformat(),
            et: "Calibration",
            "Glucose Value (mg/dL)": 118,
        }
    )
    rows.sort(key=lambda r: (r[1] != "", r[1]))  # metadata first, then time order
    for i, row in enumerate(rows, 1):
        row[0] = str(i)
    return rows


def libre_stamp(t: datetime) -> str:
    return t.strftime("%m-%d-%Y %H:%M")


def libre_rows() -> list[list[str]]:
    rows = []

    def add(t: datetime, record_type: int, **cells):
        row = [""] * len(LIBRE_HEADER)
        row[:4] = ["FreeStyle LibreLink", "SYNTHETIC-0000", libre_stamp(t), str(record_type)]
        for key, value in cells.items():
            row[LIBRE_HEADER.index(key)] = str(value)
        rows.append(row)

    stamp = START
    while stamp < START + timedelta(days=DAYS):
        if not in_gap(stamp):
            g = glucose_at(stamp)
            g = {"Low": "LO", "High": "HI"}.get(g, g)
            add(stamp, 0, **{"Historic Glucose mg/dL": g})
        stamp += timedelta(minutes=15)
    for day in range(DAYS):
        base = START + timedelta(days=day)
        for hour, minute, carbs, units in MEALS:
            t = base + timedelta(hours=hour, minutes=minute)
            add(t + timedelta(minutes=2), 1, **{"Scan Glucose mg/dL": glucose_at(t)})
            add(t, 5, **{"Carbohydrates (grams)": carbs})
            add(t, 4, **{"Rapid-Acting Insulin (units)": units})
        t = base + timedelta(hours=BASAL[0], minutes=BASAL[1])
        add(t, 4, **{"Long-Acting Insulin Value (units)": BASAL[2]})
    rows.sort(key=lambda r: datetime.strptime(r[2], "%m-%d-%Y %H:%M"))
    return rows


def write(out: Path, name: str, rows: list[list[str]], preamble: list[list[str]] = ()) -> None:
    with (out / name).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows([*preamble, *rows])


def main(out: Path = HERE) -> None:
    write(out, "clarity_sample.csv", clarity_rows(), [CLARITY_HEADER])
    meta = ["Glucose Data", "Generated on", "01-16-2026 09:00 UTC", "Generated by", "Synthetic"]
    write(out, "libreview_sample.csv", libre_rows(), [meta, LIBRE_HEADER])

    mmol_header = [
        h.replace("(mg/dL)", "(mmol/L)").replace("mg/dL/min", "mmol/L/min") for h in CLARITY_HEADER
    ]
    mmol = []
    for i, value in enumerate(["5.5", "3.9", "Low", "10.0"]):
        row = [""] * len(mmol_header)
        row[0], row[1], row[2], row[7] = str(i + 1), f"2026-01-13T00:{5 * i:02d}:00", "EGV", value
        mmol.append(row)
    write(out, "clarity_mmol.csv", mmol, [mmol_header])

    dayfirst = []
    for stamp, value in (
        ("13-01-2026 23:45", "110"),
        ("14-01-2026 00:00", "LO"),
        ("14-01-2026 00:15", "95"),
    ):
        row = [""] * len(LIBRE_HEADER)
        row[:5] = ["FreeStyle Libre 3", "SYNTHETIC-0001", stamp, "0", value]
        dayfirst.append(row)
    write(out, "libreview_dayfirst.csv", dayfirst, [meta, LIBRE_HEADER])


if __name__ == "__main__":
    main()
