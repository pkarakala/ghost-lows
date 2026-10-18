"""The synthetic sample behind the app's "Try it with sample data" (scripts/make_sample_export.py).

Checks the committed files, not a re-simulation: the export is labelled synthetic, loads as the
app loads it, and the app's flags on it still show what the sample is for (its answer key).
"""

import importlib.util
import json
from pathlib import Path

import pandas as pd

from ghostlows import io as gio
from ghostlows import retro

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "app" / "sample_clarity_export.csv"
KEY = ROOT / "app" / "sample_answer_key.json"


def script():
    spec = importlib.util.spec_from_file_location(
        "make_sample_export", ROOT / "scripts" / "make_sample_export.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_header_rows_say_the_sample_is_synthetic():
    rows = SAMPLE.read_text().splitlines()[1:4]
    assert ",FirstName,,SYNTHETIC," in rows[0]
    assert "not a real person" in rows[1]
    assert "synthetic sample" in rows[2]


def test_sample_loads_as_a_14_day_clarity_export():
    data = gio.load_export(SAMPLE.read_bytes())
    assert set(data["source"]) == {"dexcom_clarity"}
    readings = data[data["glucose"].notna()]
    assert pd.Timedelta(days=13.9) < readings["time"].max() - readings["time"].min()
    assert len(readings) > 0.95 * 14 * 288
    assert data["insulin_bolus"].notna().any() and data["carbs"].notna().any()


def test_flags_on_the_sample_still_show_both_kinds_of_event():
    module = script()
    key = json.loads(KEY.read_text())
    data = gio.load_export(SAMPLE.read_bytes())
    counts = module.conditions(key, data, retro.flag_possible_artifacts(data))
    assert module.meets(counts), counts


def test_answer_key_true_glucose_spans_the_export():
    tg = json.loads(KEY.read_text())["true_glucose"]
    assert tg["step_min"] == 5 and len(tg["mg_dl"]) == 14 * 288
    assert tg["start"] == "2026-01-05T00:00:00"
