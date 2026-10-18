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
