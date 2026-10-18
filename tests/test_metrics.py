from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ghostlows import metrics

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tiny():
    df = pd.read_csv(FIXTURES / "metrics_tiny.csv", parse_dates=["time"])
    return df


def test_summary_matches_hand_computed_values(tiny):
    # Readings: 40 (Low), 50, 60, 70, 100, 180, 181, 250, 251, 400 (High); two 5-min gaps.
    s = metrics.summary(tiny)
    assert s["n_readings"] == 10
    assert s["mean"] == pytest.approx(158.2)  # 1582 / 10
    # sum of squared deviations 122989.6; / 9 = 13665.511; sqrt = 116.8996
    assert s["sd"] == pytest.approx(116.8996, abs=1e-4)
    assert s["cv_pct"] == pytest.approx(73.8935, abs=1e-4)  # 116.8996 / 158.2
    assert s["gmi_pct"] == pytest.approx(7.094144)  # 3.31 + 0.02392 * 158.2
    assert s["tir_70_180_pct"] == pytest.approx(30.0)  # 70, 100, 180 (bounds inclusive)
    assert s["tbr_70_pct"] == pytest.approx(30.0)  # 40, 50, 60
    assert s["tbr_54_pct"] == pytest.approx(20.0)  # 40, 50
    assert s["tar_180_pct"] == pytest.approx(40.0)  # 181, 250, 251, 400
    assert s["tar_250_pct"] == pytest.approx(20.0)  # 251, 400 (250 is not above 250)
    assert s["wear_pct"] == pytest.approx(100 * 10 / 12)  # 12 slots from 00:00 to 00:55
    assert s["days"] == 1


def test_rows_without_glucose_are_ignored(tiny):
    event = pd.DataFrame(
        {"time": [pd.Timestamp("2026-01-13 00:30")], "glucose": [np.nan], "carbs": [30.0]}
    )
    with_event = pd.concat([tiny, event], ignore_index=True)
    assert metrics.summary(with_event) == metrics.summary(tiny)


def test_sampling_interval_snaps_to_nominal():
    five = pd.Series(pd.date_range("2026-01-01", periods=50, freq="5min")).drop(index=[3, 4, 9])
    fifteen = pd.Series(pd.date_range("2026-01-01", periods=50, freq="15min") + pd.Timedelta("1s"))
    assert metrics.sampling_interval(five) == 5
    assert metrics.sampling_interval(fifteen) == 15


def test_wear_uses_inferred_interval():
    times = pd.date_range("2026-01-01", periods=96, freq="15min")
    df = pd.DataFrame({"time": times, "glucose": 100.0}).drop(index=range(10, 34))
    assert metrics.wear_percent(df) == pytest.approx(100 * 72 / 96)


def test_agp_percentiles_by_time_of_day():
    times = pd.to_datetime(
        ["2026-01-01 00:05", "2026-01-02 00:10", "2026-01-03 00:01", "2026-01-01 12:00"]
    )
    df = pd.DataFrame({"time": times, "glucose": [100.0, 200.0, 300.0, 50.0]})
    out = metrics.agp(df, bin_min=15)
    assert len(out) == 96 and list(out.columns) == ["p5", "p25", "p50", "p75", "p95", "n"]
    first = out.loc["00:00"]
    assert first["n"] == 3 and first["p50"] == 200.0 and first["p25"] == 150.0
    assert out.loc["12:00", "p50"] == 50.0
    assert np.isnan(out.loc["06:00", "p50"])


def test_agp_smoothing_is_circular():
    times = pd.date_range("2026-01-01", periods=96, freq="15min")
    df = pd.DataFrame({"time": times, "glucose": np.r_[200.0, np.full(94, 100.0), 200.0]})
    out = metrics.agp(df, smooth_bins=3)
    # 00:00 averages 23:45 (200), 00:00 (200) and 00:15 (100)
    assert out.loc["00:00", "p50"] == pytest.approx(500 / 3)


def test_summary_by_patient(tiny):
    other = tiny.assign(patient_id="tiny:2", glucose=100.0, glucose_flag="ok")
    out = metrics.summary_by_patient(pd.concat([tiny, other]))
    assert list(out.index) == ["tiny:1", "tiny:2"]
    assert out.loc["tiny:2", "tir_70_180_pct"] == 100.0
