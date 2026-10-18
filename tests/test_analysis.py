"""H1/H2 contrasts on synthetic metrics with known answers (RESEARCH.md §3)."""

import numpy as np
import pandas as pd
import pytest

from ghostlows.bench.analysis import context_contrasts, h1_contrast, h2_reading


def test_h2_reading_rules():
    assert h2_reading(0.6, 0.4, 0.9) == "meaningful reduction"
    assert h2_reading(0.9, 0.8, 1.1) == "no meaningful reduction"
    assert h2_reading(0.7, 0.5, 1.2) == "inconclusive"
    assert h2_reading(float("nan"), 0, 0) == "not estimable"


def metrics_rows():
    rows = []
    for i in range(10):
        pid = f"sim:adult#{i + 1:03d}"
        for frac in (0.0, 0.5, 1.0):
            rows.append(
                {
                    "alarm_name": "trend_combined_time",
                    "patient_id": pid,
                    "level": frac,
                    "mix": "default",
                    "false_compression": 10.0 * frac,
                    "false_per_day": 1 + 2 * frac,
                }
            )
            rows.append(
                {
                    "alarm_name": "trend_combined_time_ctx",
                    "patient_id": pid,
                    "level": frac,
                    "mix": "default",
                    "false_compression": 5.0 * frac,
                    "false_per_day": 1 + frac,
                }
            )
            rows.append(
                {
                    "alarm_name": "trend",
                    "patient_id": pid,
                    "level": frac,
                    "mix": "default",
                    "false_compression": 0.0,
                    "false_per_day": 1 + 3 * frac,
                }
            )
            rows.append(
                {
                    "alarm_name": "threshold",
                    "patient_id": pid,
                    "level": frac,
                    "mix": "default",
                    "false_compression": 0.0,
                    "false_per_day": 1 + 1 * frac,
                }
            )
    return pd.DataFrame(rows)


def test_context_contrast_rate_ratio_is_paired():
    c = context_contrasts(metrics_rows(), n_boot=100).set_index("level")
    assert c.loc[1.0, "rate_ratio"] == pytest.approx(0.5)
    assert c.loc[1.0, "lo"] == pytest.approx(0.5) and c.loc[1.0, "hi"] == pytest.approx(0.5)
    assert c.loc[1.0, "reading"] == "meaningful reduction"
    assert np.isnan(c.loc[0.0, "rate_ratio"])  # no compression false alarms in either arm


def test_h1_slope_contrast():
    h = h1_contrast(metrics_rows(), n_boot=100).iloc[0]
    assert h["median_slope_diff"] == pytest.approx(2.0)  # slopes 3 vs 1
    assert h["supported"]


def test_gbm_arms_get_a_context_contrast_too():
    rows = metrics_rows()
    gbm = rows[rows["alarm_name"].str.startswith("trend_combined")].copy()
    gbm["alarm_name"] = gbm["alarm_name"].map(
        {"trend_combined_time": "gbm_time", "trend_combined_time_ctx": "gbm_time_ctx"}
    )
    c = context_contrasts(pd.concat([rows, gbm]), n_boot=50)
    assert set(c["detector"]) == {"trend", "gbm"}
    g = c[(c["detector"] == "gbm") & (c["level"] == 1.0)].iloc[0]
    assert g["rate_ratio"] == pytest.approx(0.5)


def test_per_run_counts_are_integers_even_from_object_columns():
    from ghostlows.bench.scoring import per_run_metrics

    hours = pd.DataFrame({"patient_id": ["p"], "seed": [1], "mix": ["m"], "hours": [24.0]})
    classified = pd.DataFrame(
        {
            "patient_id": ["p", "p"],
            "seed": [1, 1],
            "mix": ["m", "m"],
            "alarm_name": ["a", "a"],
            "time": pd.to_datetime(["2026-01-05 01:00", "2026-01-05 02:00"]),
            "is_floor": pd.Series([True, False], dtype=object),
            "matched": pd.Series([False, True], dtype=object),
            "cause": ["noise", None],
        }
    )
    m = per_run_metrics(classified, pd.DataFrame(), hours, ["a"])
    assert m["n_floor"].tolist() == [1] and m["n_false"].tolist() == [1]
    assert m["n_floor"].dtype.kind == "i" and m["n_false"].dtype.kind == "i"


def test_warning_times_come_with_the_miss_rate():
    from ghostlows.bench.analysis import warning_times

    rows = []
    for i in range(6):
        rows.append(
            {
                "alarm_name": "trend",
                "level": 1.0,
                "mix": "default",
                "patient_id": f"sim:adult#{i + 1:03d}",
                "warning_median_min_l2": 8.0 + i,
                "caught_l2": 3,
                "events_l2": 4,
            }
        )
    w = warning_times(pd.DataFrame(rows), n_boot=50)
    r = w[w["low_level"] == 2].iloc[0]
    assert r["warning_median_min"] == pytest.approx(10.5)
    assert r["lo"] <= r["warning_median_min"] <= r["hi"]
    assert r["miss_rate"] == pytest.approx(0.25)


def warning_rows(runs_per_patient: int) -> pd.DataFrame:
    rows = []
    for i in range(12):
        group = ("adult", "child")[i % 2]
        for seed in range(runs_per_patient):
            rows.append(
                {
                    "alarm_name": "trend",
                    "level": 1.0,
                    "mix": "default",
                    "patient_id": f"sim:{group}#{i + 1:03d}",
                    "seed": seed,
                    "warning_median_min_l2": 5.0 + 3 * i,
                    "caught_l2": 1,
                    "events_l2": 2,
                }
            )
    return pd.DataFrame(rows)


def test_warning_time_bootstrap_unit_is_the_patient():
    """Hard rule 5 (amendment A10): giving every patient five identical runs instead of one adds
    no information, so the estimate and CI must not change. A run-level bootstrap would narrow
    the CI."""
    from ghostlows.bench.analysis import warning_times

    one, five = (warning_times(warning_rows(k), n_boot=400) for k in (1, 5))
    cols = ["warning_median_min", "lo", "hi", "miss_rate", "patients"]
    pd.testing.assert_frame_equal(one[cols], five[cols])
    assert five["patients"].iloc[0] == 12 and five["runs"].iloc[0] == 60


def test_warning_h1_and_h2_bootstraps_resample_patients(monkeypatch):
    """Each call of the patient bootstrap gets one row per patient (hard rule 5)."""
    from ghostlows.bench import analysis

    real = analysis.bootstrap_ci
    seen = []

    def checked(per_patient, *args, **kwargs):
        assert per_patient["patient_id"].is_unique, "bootstrap rows must be patients"
        seen.append(len(per_patient))
        return real(per_patient, *args, **kwargs)

    monkeypatch.setattr(analysis, "bootstrap_ci", checked)
    m = metrics_rows()
    analysis.warning_times(warning_rows(5), n_boot=20)
    analysis.context_contrasts(m, n_boot=20)
    analysis.h1_contrast(m, n_boot=20)
    assert len(seen) >= 3
