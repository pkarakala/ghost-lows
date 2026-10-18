"""Retrospective upload flags (PRIVACY_AND_SAFETY.md): conservative, explained, safe wording."""

from pathlib import Path

import pandas as pd

from ghostlows import io, metrics, retro

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


def test_time_below_range_is_reported_with_and_without_flags():
    df = clarity()
    flags = retro.flag_possible_artifacts(df)
    with_flags = metrics.summary(df)["tbr_70_pct"]
    without = metrics.summary(retro.without_flagged(df, flags))["tbr_70_pct"]
    assert 0 < without < with_flags  # the genuine low and the Low readings stay counted


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
