"""Retrospective upload flags (PRIVACY_AND_SAFETY.md): conservative, explained, safe wording."""

from pathlib import Path

import pandas as pd

from ghostlows import io, retro

FIXTURES = Path(__file__).parent / "fixtures"
FORBIDDEN = ("not real", "fake", "ignore", "false low", "can be ignored")


def clarity():
    return io.load_clarity(FIXTURES / "clarity_sample.csv")


def test_flags_only_the_night_time_compression_dip():
    flags = retro.flag_possible_artifacts(clarity())
    assert len(flags) == 1
    f = flags.iloc[0]
    assert f["start"] == pd.Timestamp("2026-01-13 02:00") and f["night"] and f["below_70"]
    assert f["methods"] == "baysal, matched_filter"
    assert f["label"] == "possible compression artifact"
    assert "Baysal 2014" in f["citations"] and "Idi 2023" in f["citations"]
    assert "mg/dL" in f["reasons"] and "02:00" in f["reasons"]


def test_genuine_daytime_low_is_detected_but_never_flagged():
    found = retro.detections(clarity())
    daytime_low = found[
        (found["start"].dt.date == pd.Timestamp("2026-01-14").date()) & found["below_70"]
    ]
    assert len(daytime_low) == 1 and not daytime_low["flagged"].iloc[0]
    assert not found.loc[~found["night"], "flagged"].any()


def test_no_number_can_be_computed_without_flagged_readings():
    """PRIVACY_AND_SAFETY.md rule 3 (amendment A12): a flag never lowers a number in the report,
    so the library offers no way to drop flagged readings and the app never tries."""
    assert not any("without" in name for name in retro.__all__)
    app = (Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py").read_text()
    assert "without_flagged" not in app and "metrics.summary(data)" in app
    assert app.count("metrics.summary(") == 1  # one summary, of every reading


def test_app_quotes_the_measured_flag_performance():
    """The flag performance the app states is the saved survey (amendment A12)."""
    import json
    import re

    root = Path(__file__).resolve().parents[1]
    survey = json.loads((root / "results" / "tables" / "flag_survey.json").read_text())
    app = (root / "app" / "streamlit_app.py").read_text()
    caught, on_real = map(
        int, re.search(r"FLAG_CAUGHT_PCT, FLAG_ON_REAL_LOW_PCT = (\d+), (\d+)", app).groups()
    )
    assert caught == round(100 * survey["flagged_artifact_share"])
    assert on_real == round(100 * survey["share_of_runs_with_a_flag_on_a_real_low"])


def test_no_flags_on_short_or_flat_traces():
    times = pd.date_range("2026-01-13 23:00", periods=48, freq="5min")
    flat = pd.DataFrame({"time": times, "glucose": 110.0})
    assert retro.flag_possible_artifacts(flat).empty
    assert retro.flag_possible_artifacts(flat.head(3)).empty


def test_user_facing_text_is_safely_worded():
    found = retro.detections(clarity())
    text = " ".join(
        [retro.LABEL, *retro.METHODS.values(), *found["reasons"], *found["citations"]]
    ).lower()
    for phrase in FORBIDDEN:
        assert phrase not in text, phrase
