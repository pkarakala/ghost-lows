"""Trade-off curves (amendment A11): the r = 1 point is the benchmark's own operating point."""

import numpy as np
import pandas as pd
import pytest
import yaml

pytest.importorskip("simglucose")

from ghostlows.bench import curves, pipeline  # noqa: E402
from ghostlows.sim import run as sim_run  # noqa: E402

ALARMS = ["trend", "baysal_gate", "trend_combined_time", "trend_combined_time_ctx", "gbm_time"]


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("curves")
    sim_run.DATA = tmp  # cache the tiny cohort outside data/
    sim_cfg = tmp / "sim.yaml"
    sim_cfg.write_text(
        yaml.safe_dump(
            {
                "name": "tiny",
                "patients": ["adolescent#002", "child#001"],
                "days": 1,
                "seeds": [1],
                "mixes": ["default"],
            }
        )
    )
    config = pipeline.BenchConfig(
        name="tiny", simulation=str(sim_cfg), levels=[1.0], alarms=ALARMS, n_folds=2, n_boot=20
    )
    bench = pipeline.run_benchmark(config, tmp / "bench")
    points = curves.run_curves(config, tmp / "curves")
    chosen = curves.choices(points)
    return bench, chosen, curves.curve_summary(curves.per_patient_at(points, chosen), 20)


def test_r1_is_the_pre_registered_operating_point(runs):
    bench, chosen, summary = runs
    t = bench["thresholds"]
    learned = t[t["alarm_name"] != "trend"]
    r1 = chosen[chosen["point"] == "r=1.00"].merge(
        learned, on=["mix", "fold", "alarm_name"], suffixes=("", "_bench")
    )
    assert len(r1) == len(learned) > 0
    np.testing.assert_allclose(r1["threshold"], r1["threshold_bench"])
    np.testing.assert_allclose(r1["train_sens"], r1["train_sens_bench"], equal_nan=True)


def test_r1_and_published_points_reproduce_the_summary(runs):
    bench, _, summary = runs
    cols = ["sens_l2", "false_per_day", "false_compression_per_day"]
    cols += [f"{c}_{e}" for c in cols for e in ("lo", "hi")]
    s = bench["summary"]
    for name in ALARMS:
        point = "published" if name == "trend" else "r=1.00"
        a = summary[(summary["alarm_name"] == name) & (summary["point"] == point)]
        b = s[s["alarm_name"] == name]
        np.testing.assert_allclose(a[cols].to_numpy(float), b[cols].to_numpy(float), equal_nan=True)


def test_lower_retention_never_costs_training_false_alarms(runs):
    _, chosen, _ = runs
    sweep = chosen[chosen["retention"].notna()].sort_values("retention")
    for _, g in sweep.groupby(["mix", "fold", "alarm_name"]):
        fpd = g["train_false_per_day"].to_numpy()
        assert (np.diff(fpd) >= -1e-12).all()  # a looser constraint never forces more alarms
    assert set(pd.unique(sweep["retention"])) == set(curves.RETENTIONS)
