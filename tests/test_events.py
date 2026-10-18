"""Low-event detection and the leak metric on hand-built traces with known answers."""

import numpy as np
import pandas as pd
import pytest

from ghostlows.bench.events import auc, detect_events, leak_auc, true_events


def trace(*segments):
    """Concatenate (value, minutes) segments into a 1-min signal."""
    return np.concatenate([np.full(n, v, dtype=float) for v, n in segments])


def test_event_needs_15_minutes_below():
    assert detect_events(trace((100, 30), (60, 14), (100, 30)), 70) == []
    assert detect_events(trace((100, 30), (60, 15), (100, 30)), 70) == [(30, 45)]


def test_event_ends_after_15_minutes_above_and_short_recoveries_merge():
    # 20 min low, 10 min above (too short to end), 20 min low, then 15 min above ends it at 80
    x = trace((100, 30), (60, 20), (80, 10), (60, 20), (100, 15), (60, 5))
    assert detect_events(x, 70) == [(30, 80)]


def test_two_separate_events_and_open_ended_event():
    x = trace((60, 15), (100, 15), (50, 30))
    assert detect_events(x, 70) == [(0, 15), (30, 60)]


def test_threshold_is_strict_and_nan_is_not_low():
    assert detect_events(trace((70, 20)), 70) == []
    assert detect_events(np.r_[trace((60, 10)), np.nan, trace((60, 10))], 70) == []


def test_five_minute_sampling_uses_three_samples():
    assert detect_events(trace((100, 3), (60, 3), (100, 3)), 70, step_min=5) == [(3, 6)]
    assert detect_events(trace((100, 3), (60, 2), (100, 3)), 70, step_min=5) == []


def test_true_events_levels_nest():
    times = pd.date_range("2026-01-05 01:00", periods=120, freq="min")
    values = trace((100, 30), (60, 10), (50, 20), (60, 10), (100, 50))
    truth = pd.DataFrame({"patient_id": "p", "time": times, "truth_glucose": values})
    ev = true_events(truth)
    l1, l2 = ev[ev.level == 1].iloc[0], ev[ev.level == 2].iloc[0]
    assert (l1.onset, l1.end) == (times[30], times[70])
    assert (l2.onset, l2.end) == (times[40], times[60])


def test_auc():
    assert auc([3, 4], [1, 2]) == 1.0
    assert auc([1], [1]) == 0.5
    assert auc([1, 2], [3, 4]) == 0.0


def test_leak_auc_uses_last_sample_before_onset():
    times = pd.date_range("2026-01-05 22:00", periods=24, freq="5min")  # 22:00-23:55
    samples = pd.DataFrame(
        {"patient_id": "p", "time": times, "iob": np.r_[np.zeros(20), [5, 5, 5, 5]]}
    )
    events = pd.DataFrame(
        {
            "patient_id": ["p"],
            "level": [1],
            "onset": [pd.Timestamp("2026-01-05 23:42")],
            "end": [pd.NaT],
        }
    )
    # onset 23:42 takes IOB from 23:40 (= 5); night samples are 23:00-23:55
    assert leak_auc(samples, events) == pytest.approx((8 + 4 * 0.5) / 12)
