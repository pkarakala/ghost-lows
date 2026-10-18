"""Scoring on hand-built cases with known answers (BENCHMARK.md §4, D10, D12)."""

import numpy as np
import pandas as pd
import pytest

from ghostlows.bench.scoring import (
    classify_alarms,
    fda_rates,
    per_run_metrics,
    run_hours,
    score_events,
)

T0 = pd.Timestamp("2026-01-05 00:00")


def at(minutes):
    return T0 + pd.Timedelta(minutes=minutes)


RUN = {"patient_id": "p", "seed": 1, "mix": "default"}
EVENTS = pd.DataFrame(
    [
        {**RUN, "level": 1, "onset": at(600), "end": at(660)},  # 10:00-11:00
        {**RUN, "level": 2, "onset": at(615), "end": at(645)},
    ]
)
FAULTS = pd.DataFrame(
    [{**RUN, "fault_type": "pisa", "fault_id": 0, "start": at(120), "end": at(165)}]  # 02:00-02:45
)
LABELS = pd.DataFrame(
    {**RUN, "time": [at(300), at(305)], "fault_type": ["stale", "stale"]}  # 05:00-05:05
)


def alarms(*minutes, floor=()):
    return pd.DataFrame(
        {
            **RUN,
            "time": [at(m) for m in minutes],
            "is_floor": [m in floor for m in minutes],
            "alarm_name": "a",
        }
    )


def test_matching_window_and_causes():
    a = alarms(130, 170, 302, 400, 545, 560, 590, 640, 700, 900)
    c = classify_alarms(a, EVENTS, FAULTS, LABELS).set_index(a["time"].dt.strftime("%H:%M"))
    # 02:10 inside the PISA, 02:50 within 30 min after it ended -> compression
    assert c.loc["02:10", "cause"] == "compression" and c.loc["02:50", "cause"] == "compression"
    assert c.loc["05:02", "cause"] == "other_fault"  # stale readings in [t - 30, t]
    assert c.loc["06:40", "cause"] == "noise"
    assert c.loc["09:05", "cause"] == "near_event"  # 55 min before onset (30-60 min band)
    assert c.loc["09:20", "cause"] == "near_event"  # 40 min before onset: outside the 30-min window
    assert c.loc["09:50", "matched"]  # within 30 min before onset
    assert c.loc["10:40", "matched"]  # during the event: late, not false
    assert c.loc["11:40", "cause"] == "near_event"  # within 60 min after the event ended
    assert c.loc["15:00", "cause"] == "noise"
    assert not c.loc["09:05", "matched"]


def test_events_caught_warning_and_late_announcement():
    s = score_events(alarms(590, 640, floor=(640,)), EVENTS).set_index("level")
    assert s.loc[1, "caught"] and s.loc[1, "warning_min"] == 10  # 09:50 is 10 min before onset
    # level 2 onset 10:15: 09:50 is 25 min before -> caught, warning 25
    assert s.loc[2, "caught"] and s.loc[2, "warning_min"] == 25
    late = score_events(alarms(640, floor=(640,)), EVENTS).set_index("level")
    assert not late.loc[1, "caught"] and late.loc[1, "late_min"] == 40  # floor 40 min after onset
    assert not late.loc[2, "caught"] and late.loc[2, "late_min"] == 25  # 25 min after its onset


def test_fda_rates_against_reference():
    minutes = np.arange(0, 720)
    glucose = np.where((minutes >= 600) & (minutes < 660), 60.0, 120.0)
    truth = pd.DataFrame({**RUN, "time": [at(m) for m in minutes], "truth_glucose": glucose})
    r = fda_rates(alarms(590, 300), truth).iloc[0]
    assert r["n_alerts"] == 2 and r["n_true_alerts"] == 1  # 09:50 is within 15 min of 10:00
    assert r["n_reference_lows"] == 4  # references at 10:00, 10:15, 10:30, 10:45
    assert r["n_detected"] == 1  # only 10:00 has an alert within 15 min


def test_per_run_metrics_fill_zeros_for_silent_alarms():
    samples = pd.DataFrame({**RUN, "time": [at(m) for m in range(0, 1440, 5)]})
    a = alarms(130, 590)
    c = classify_alarms(a, EVENTS, FAULTS, LABELS)
    s = score_events(a, EVENTS)
    m = per_run_metrics(c, s, run_hours(samples), alarm_names=["a", "silent"]).set_index(
        "alarm_name"
    )
    assert m.loc["a", "n_false"] == 1 and m.loc["a", "false_compression_per_day"] == pytest.approx(
        1.0
    )
    assert m.loc["a", "caught_l1"] == 1 and m.loc["a", "events_l1"] == 1
    assert m.loc["silent", "n_alarms"] == 0 and m.loc["silent", "false_per_day"] == 0
    assert m.loc["a", "hours"] == pytest.approx(24.0)
