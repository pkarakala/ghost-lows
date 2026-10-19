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
    summary = curves.curve_summary(curves.per_patient_at(points, chosen), 20)
    return bench, chosen, summary, config, pd.read_csv(tmp / "curves" / "points.csv")


def test_r1_is_the_pre_registered_operating_point(runs):
    bench, chosen, summary = runs[:3]
    t = bench["thresholds"]
    learned = t[t["alarm_name"] != "trend"]
    r1 = chosen[chosen["point"] == "r=1.00"].merge(
        learned, on=["mix", "fold", "alarm_name"], suffixes=("", "_bench")
    )
    assert len(r1) == len(learned) > 0
    np.testing.assert_allclose(r1["threshold"], r1["threshold_bench"])
    np.testing.assert_allclose(r1["train_sens"], r1["train_sens_bench"], equal_nan=True)


def test_r1_and_published_points_reproduce_the_summary(runs):
    bench, _, summary = runs[:3]
    cols = ["sens_l2", "false_per_day", "false_compression_per_day"]
    cols += [f"{c}_{e}" for c in cols for e in ("lo", "hi")]
    s = bench["summary"]
    for name in ALARMS:
        point = "published" if name == "trend" else "r=1.00"
        a = summary[(summary["alarm_name"] == name) & (summary["point"] == point)]
        b = s[s["alarm_name"] == name]
        np.testing.assert_allclose(a[cols].to_numpy(float), b[cols].to_numpy(float), equal_nan=True)


def test_lower_retention_never_costs_training_false_alarms(runs):
    _, chosen, _ = runs[:3]
    sweep = chosen[chosen["retention"].notna()].sort_values("retention")
    for _, g in sweep.groupby(["mix", "fold", "alarm_name"]):
        fpd = g["train_false_per_day"].to_numpy()
        assert (np.diff(fpd) >= -1e-12).all()  # a looser constraint never forces more alarms
    assert set(pd.unique(sweep["retention"])) == set(curves.RETENTIONS)


def synthetic_curve(name: str, fpd: tuple, comp: tuple) -> pd.DataFrame:
    """Every patient identical: level 2 sensitivity 0.6 / 0.8 / 1.0 at r = 0.5 / 0.75 / 1.0, and
    the given total and compression false alarms per day."""
    rows = []
    for i in range(6):
        for k, r in enumerate((0.5, 0.75, 1.0)):
            rows.append(
                {
                    "alarm_name": name,
                    "mix": "default",
                    "retention": r,
                    "patient_id": f"sim:{('adult', 'child')[i % 2]}#{i:03d}",
                    "caught_l2": (3, 4, 5)[k],
                    "events_l2": 5,
                    "n_false": 10 * fpd[k],
                    "false_compression": 10 * comp[k],
                    "days": 10.0,
                }
            )
    return pd.DataFrame(rows)


def test_matched_comparison_interpolates_at_matched_sensitivity():
    ref = synthetic_curve("trend", (1.0, 2.0, 3.0), (0.5, 0.5, 1.0))
    gate = synthetic_curve("baysal_gate", (0.5, 1.0, 1.5), (0.25, 0.25, 0.5))
    out = curves.matched_comparison(
        pd.concat([ref, gate]), comparators=["baysal_gate"], offsets=(0.1, 0.3), n_boot=50
    )
    r = out.set_index("offset")
    assert r.at[0.3, "sens_l2"] == pytest.approx(0.7)
    assert r.at[0.3, "total_per_day_reference"] == pytest.approx(1.5)  # halfway between 1 and 2
    assert r.at[0.3, "total_per_day"] == pytest.approx(0.75)
    assert r.at[0.1, "compression_ratio"] == pytest.approx(0.5)
    np.testing.assert_allclose(out[["total_ratio_lo", "total_ratio_hi"]], 0.5)
    assert (out["reading"] == "adds value").all()


def test_an_alarm_compared_with_itself_is_a_ratio_of_one():
    ref = synthetic_curve("trend", (1.0, 2.0, 3.0), (0.5, 0.5, 1.0))
    twin = ref.assign(alarm_name="gbm")
    rng = np.random.default_rng(0)
    for frame in (ref, twin):  # patients differ, so the bootstrap is not degenerate
        frame["n_false"] = frame["n_false"] + np.repeat(rng.integers(0, 5, 6), 3)
    twin["n_false"] = ref["n_false"].to_numpy()
    out = curves.matched_comparison(pd.concat([ref, twin]), comparators=["gbm"], n_boot=200)
    np.testing.assert_allclose(out[["total_ratio", "total_ratio_lo", "total_ratio_hi"]], 1.0)
    assert (out["reading"] == "no detectable difference").all()


def test_matched_comparison_resamples_patients_not_rows():
    """Splitting each patient's counts over two rows (two runs) changes nothing."""
    rng = np.random.default_rng(1)
    ref = synthetic_curve("trend", (1.0, 2.0, 3.0), (0.5, 0.5, 1.0))
    gate = synthetic_curve("baysal_gate", (0.5, 1.0, 1.5), (0.25, 0.25, 0.5))
    both = pd.concat([ref, gate], ignore_index=True)
    both["n_false"] = both["n_false"] + rng.integers(0, 6, len(both))
    one = curves.matched_comparison(both, comparators=["baysal_gate"], n_boot=200)
    half = both.assign(**{c: both[c] / 2 for c in curves.A13_COUNTS})
    two = curves.matched_comparison(
        pd.concat([half, half]), comparators=["baysal_gate"], n_boot=200
    )
    pd.testing.assert_frame_equal(one, two)


def test_an_incremental_sweep_equals_a_full_sweep(runs, tmp_path):
    config = runs[3]
    part = pipeline.BenchConfig(**{**vars(config), "alarms": ["trend", "baysal_gate"]})
    curves.run_curves(part, tmp_path / "inc")
    added = curves.run_curves(config, tmp_path / "inc")  # sweeps only the missing alarms
    full = runs[4]
    keys = ["alarm_name", "mix", "fold", "threshold", "patient_id"]
    a = added.sort_values(keys).reset_index(drop=True)
    b = full.sort_values(keys).reset_index(drop=True)[a.columns]
    pd.testing.assert_frame_equal(a, b, check_dtype=False)
