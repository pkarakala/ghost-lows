"""Alarm tests (BENCHMARK.md §1-2): causality for every alarm, and known answers per alarm."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ghostlows.alarms import (
    FLOOR_MG_DL,
    CombinedAlarm,
    GatedAlarm,
    ThresholdAlarm,
    TrendAlarm,
    benchmark_alarms,
    fire_events,
    stretch_alarms,
    view,
)
from ghostlows.alarms.detectors import baysal_flags, matched_filter_score
from ghostlows.alarms.learned import Detector, GBMAlarm, MatchedFilterDetector
from ghostlows.bench.events import detect_events, low_labels
from ghostlows.cli import load_alarm
from ghostlows.faults.pisa import from_size

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "custom_alarm.py"
TIMES = pd.date_range("2026-01-05", periods=2 * 288, freq="5min")


def synthetic_run(seed: int, patient: str) -> pd.DataFrame:
    """Two days: a daily wave, one slow true low with insulin on board, one PISA at night."""
    rng = np.random.default_rng(seed)
    t = np.arange(len(TIMES)) * 5.0
    truth = 130 + 30 * np.sin(2 * np.pi * t / 1440)
    low_start = 1440 + 600 + rng.uniform(-60, 60)  # day 2, around 10:00
    dip = np.clip(1 - np.abs(t - low_start - 60) / 60, 0, None)
    truth = truth - 85 * dip
    iob = 3.0 * np.exp(-np.clip(t - (low_start - 90), 0, None) / 120) * (t >= low_start - 90)
    pisa = from_size(1440 + 120 + rng.uniform(0, 120), 30.0, 45.0).attenuation(t)  # day 2 night
    cgm = truth - pisa + rng.normal(0, 4, len(t))
    df = pd.DataFrame(
        {"patient_id": patient, "time": TIMES, "cgm": cgm, "iob": iob, "cob": 0.0, "truth": truth}
    )
    events = [
        {"patient_id": patient, "level": 1, "onset": TIMES[s], "end": TIMES[min(e, len(TIMES) - 1)]}
        for s, e in detect_events(truth, 70, step_min=5)
    ]
    df["label"] = low_labels(
        df, pd.DataFrame(events, columns=["patient_id", "level", "onset", "end"])
    )
    return df


@pytest.fixture(scope="module")
def train():
    return pd.concat([synthetic_run(s, f"train:{s}") for s in range(6)], ignore_index=True)


@pytest.fixture(scope="module")
def fitted(train):
    alarms = benchmark_alarms(seed=0) + stretch_alarms()
    for a in alarms:
        a.fit(train.drop(columns="truth"))
    return {a.name: a for a in alarms}


def test_labels_mark_ongoing_and_upcoming_lows(train):
    run = train[train["patient_id"] == "train:0"]
    assert run["label"].sum() > 0
    first = run.index[run["label"] == 1][0]
    below = run.index[run["truth"] < 70][0]
    assert run.loc[below, "time"] - run.loc[first, "time"] >= pd.Timedelta("25min")


def assert_causal(alarm):
    """Changing samples after a cutoff never changes scores (or alarms) up to the cutoff.

    Random futures can leave a thresholded score unchanged by chance, so the future is also set
    to a deep low and to a high: an alarm that reads even one sample ahead changes under one of
    them.
    """
    test = synthetic_run(99, "test:0").drop(columns=["truth", "label"])
    cut = 300
    later = test.index > cut
    rng = np.random.default_rng(1)
    noisy = test.copy()
    noisy.loc[later, "cgm"] = rng.uniform(30, 350, later.sum())
    noisy.loc[later & (rng.random(len(noisy)) < 0.2), "cgm"] = np.nan
    noisy.loc[later, "iob"] = rng.uniform(0, 10, later.sum())
    noisy.loc[later, "cob"] = rng.uniform(0, 80, later.sum())
    futures = [noisy]
    for cgm, iob, cob in ((40.0, 10.0, 80.0), (350.0, 0.0, 0.0)):
        fixed = test.copy()
        fixed.loc[later, ["cgm", "iob", "cob"]] = cgm, iob, cob
        futures.append(fixed)
    cutoff = test.loc[cut, "time"]
    a, ea = alarm.score(test), alarm.alarms(test)
    for future in futures:
        b, eb = alarm.score(future), alarm.alarms(future)
        np.testing.assert_allclose(a.loc[:cut], b.loc[:cut], equal_nan=True)
        # check_dtype=False: a frame with no alarms at all has an object-typed time column
        pd.testing.assert_frame_equal(
            ea[ea["time"] <= cutoff].reset_index(drop=True),
            eb[eb["time"] <= cutoff].reset_index(drop=True),
            check_dtype=False,
        )


@pytest.mark.parametrize("name", [a.name for a in benchmark_alarms() + stretch_alarms()])
def test_every_alarm_is_causal(name, fitted):
    assert_causal(fitted[name])


def test_example_alarm_is_causal(train):
    """The plug-in example (examples/custom_alarm.py) obeys hard rule 4 like the built-in alarms."""
    alarm = load_alarm(str(EXAMPLE) + ":FallingBelow70")
    alarm.fit(train.drop(columns="truth"))
    assert_causal(alarm)


def run_of(values, start="2026-01-05 00:00"):
    times = pd.date_range(start, periods=len(values), freq="5min")
    return pd.DataFrame(
        {"patient_id": "p", "time": times, "cgm": np.asarray(values, float), "iob": 0.0, "cob": 0.0}
    )


def test_threshold_fires_strictly_below_70():
    events = ThresholdAlarm().alarms(run_of([90, 80, 70, 69, 68]))
    assert events["time"].tolist() == [pd.Timestamp("2026-01-05 00:15")]
    assert not events["is_floor"].any()


def test_trend_fires_before_the_crossing_and_not_when_flat():
    falling = run_of(110 - 2.0 * 5 * np.arange(10))  # -2 mg/dL/min: predicts < 55 early
    first = TrendAlarm().alarms(falling)["time"].iloc[0]
    assert first < falling.loc[falling["cgm"] < 55, "time"].iloc[0]
    assert TrendAlarm().alarms(run_of(np.full(20, 100.0))).empty


class AlwaysPisa(Detector):
    name = "always"

    def gate(self, run):
        return np.ones(len(run))


def test_floor_is_never_suppressed():
    values = np.r_[np.linspace(120, 50, 15), np.full(10, 50.0)]
    events = GatedAlarm(AlwaysPisa()).alarms(run_of(values))
    assert len(events) > 0 and events["is_floor"].all()
    assert (run_of(values).set_index("time").loc[events["time"], "cgm"] <= FLOOR_MG_DL).all()


class SomewhatPisa(Detector):
    name = "somewhat"

    def gate(self, run):
        return np.full(len(run), 0.7)


def test_gate_threshold_tunes_only_the_gate():
    from ghostlows.bench.pipeline import is_learned

    falling = run_of(110 - 2.0 * 5 * np.arange(10))
    alarm = GatedAlarm(SomewhatPisa())
    assert is_learned(alarm)  # the operating-point rule chooses the gate threshold (D5)
    kept = alarm.alarms(falling, threshold=0.2)  # 1 - 0.7 = 0.3 > 0.2: trend alarm kept
    cut = alarm.alarms(falling, threshold=0.5)  # 0.3 < 0.5: suppressed, the floor remains
    assert (~kept["is_floor"]).any()
    assert len(cut) > 0 and cut["is_floor"].all()
    assert alarm.alarms(run_of(np.full(20, 100.0)), threshold=-1.0).empty  # no trend, no alarm


def test_refractory_and_flicker():
    times = pd.date_range("2026-01-05", periods=24, freq="5min").to_numpy()
    on = np.ones(24, bool)
    events = fire_events(times, on, np.zeros(24, bool))
    assert [pd.Timestamp(t).strftime("%H:%M") for t in events["time"]] == [
        "00:00",
        "00:30",
        "01:00",
        "01:30",
    ]
    toggling = np.array([1, 0, 1, 0, 0, 0, 0, 1] + [0] * 16, bool)
    assert fire_events(times, toggling, np.zeros(24, bool)).attrs["flicker"] == 1


def test_baysal_flags_a_pisa_but_not_a_slow_fall():
    t = np.arange(72) * 5.0
    times = pd.date_range("2026-01-06", periods=72, freq="5min")
    pisa = 110 - from_size(60.0, 30.0, 45.0).attenuation(t)
    slow = 110 - np.clip(t - 60, 0, None) * 0.5
    flags = baysal_flags(times, pisa)
    assert flags.sum() > 0 and flags[: 60 // 5 + 1].sum() == 0
    assert baysal_flags(times, slow).sum() == 0


def test_matched_filter_prefers_the_pisa_shape():
    t = np.arange(72) * 5.0
    pisa = 110 - from_size(60.0, 30.0, 45.0).attenuation(t)
    slow = 110 - np.clip(t - 60, 0, None) * 0.5
    assert matched_filter_score(pisa).max() > 0.9 > matched_filter_score(slow).max()


def test_context_arms_see_context_and_cgm_arms_do_not(fitted):
    assert fitted["trend_combined_ctx"].uses_context and not fitted["trend_combined"].uses_context
    test = synthetic_run(7, "test:1").drop(columns=["truth", "label"])
    changed = test.assign(iob=test["iob"] + 5.0)
    np.testing.assert_allclose(
        fitted["trend_combined"].score(test),
        fitted["trend_combined"].score(changed),
        equal_nan=True,
    )
    assert not np.allclose(
        fitted["trend_combined_ctx"].score(test),
        fitted["trend_combined_ctx"].score(changed),
        equal_nan=True,
    )


def test_kalman_fit_chooses_from_its_grid(fitted):
    from ghostlows.alarms.kalman_pisa import TUNE_GRID

    for name in ("kalman_pisa", "kalman_pisa_cgm"):
        params = fitted[name].params
        for key, grid in TUNE_GRID.items():
            assert getattr(params, key) in grid, (name, key)
    assert fitted["kalman_pisa"].params.gain_insulin >= 0  # insulin lowers glucose
    assert fitted["kalman_pisa_cgm"].params.gain_insulin == 0  # no inputs, no gains


def test_view_hides_truth_and_faults():
    df = pd.DataFrame(
        {
            "patient_id": ["p"],
            "time": [pd.Timestamp("2026-01-05")],
            "cgm_observed": [100.0],
            "truth_glucose": [90.0],
            "fault_type": ["pisa"],
            "iob": [1.0],
            "cob": [0.0],
        }
    )
    assert list(view(df).columns) == ["patient_id", "time", "cgm"]
    assert list(view(df, context=True).columns) == ["patient_id", "time", "cgm", "iob", "cob"]


def test_combined_alarm_rejects_unknown_arm():
    with pytest.raises(ValueError):
        CombinedAlarm(MatchedFilterDetector(), arm="_bogus")


def test_refractory_period_is_configurable_per_alarm():
    times = pd.date_range("2026-01-01", periods=24, freq="5min").to_numpy()
    on = np.ones(24, bool)
    off = np.zeros(24, bool)
    assert len(fire_events(times, on, off)) == 4  # every 30 min over 115 min
    assert len(fire_events(times, on, off, refractory_min=60.0)) == 2


@pytest.mark.parametrize("alarm", [GBMAlarm(), CombinedAlarm(MatchedFilterDetector(), "_time")])
def test_learned_alarm_with_no_lows_in_training_never_fires(alarm, train):
    """With nothing to learn, a learned alarm fires only at the ungated floor, at every candidate
    threshold the operating-point rule can pick (audit 2026-10; it used to score 0, and the
    rule's candidate just below 0 made it fire every refractory period)."""
    from ghostlows.bench.stats import candidate_thresholds

    no_lows = train.drop(columns="truth").assign(label=0)
    alarm.fit(no_lows)
    assert alarm.model is None
    test = synthetic_run(7, "test:7").drop(columns=["truth", "label"])
    scores = alarm.score(test)
    for theta in candidate_thresholds(scores.to_numpy()):
        fired = alarm.alarms_from_scores(test, scores, theta)
        assert fired.empty or fired["is_floor"].all()
