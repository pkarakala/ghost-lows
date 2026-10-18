"""End-to-end: a tiny simulated cohort through faults, CV, operating point and scoring, plus the
plug-in example (DECISIONS.md D18: the example must run in CI)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

pytest.importorskip("simglucose")

from ghostlows.bench import pipeline  # noqa: E402
from ghostlows.cli import load_alarm  # noqa: E402
from ghostlows.sim import run as sim_run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("bench")
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
    return tmp, sim_cfg


@pytest.fixture(scope="module")
def result(tiny):
    tmp, sim_cfg = tiny
    config = pipeline.BenchConfig(
        name="tiny",
        simulation=str(sim_cfg),
        pisa_fractions=[0.0],
        alarms=["trend", "threshold", "iforest_causal_gate"],
        n_folds=2,
        n_boot=20,
    )
    example = load_alarm(str(ROOT / "examples" / "custom_alarm.py") + ":FallingBelow70")
    out = tmp / "out"
    return pipeline.run_benchmark(config, out, extra_alarms=[example]), out


def test_rq3_kalman_alarms_and_contrasts_run_end_to_end(tiny):
    tmp, sim_cfg = tiny
    alarms = ["trend", "kalman_pisa", "kalman_pisa_cgm", "kalman_nopisa", "trend_combined"]
    alarms += ["trend_combined_ctx"]
    config = pipeline.BenchConfig(
        name="tiny_rq3",
        simulation=str(sim_cfg),
        levels=[0.0, 1.0],
        alarms=alarms,
        n_folds=2,
        n_boot=20,
    )
    res = pipeline.run_benchmark(config, tmp / "rq3")
    assert set(res["metrics"]["alarm_name"]) == set(alarms)
    t = res["thresholds"]
    assert t.loc[t["alarm_name"] == "kalman_pisa", "train_false_per_day"].notna().all()
    c = res["contrasts_rq3"]
    assert {"versus best discriminative", "ablation: compressed state"} <= set(c["contrast"])
    best = c[c["contrast"] == "versus best discriminative"]
    assert set(best["a"]) == {"kalman_pisa", "kalman_nopisa", "kalman_pisa_cgm"}
    assert best.loc[best["a"] == "kalman_pisa", "b"].str.contains("`trend_combined_ctx`").all()
    assert best.loc[best["a"] == "kalman_pisa_cgm", "b"].str.contains("`trend_combined`").all()
    assert (tmp / "rq3" / "contrasts_rq3.csv").exists()


def test_unknown_alarm_names_are_an_error():
    with pytest.raises(ValueError, match="unknown alarm"):
        pipeline.select_alarms(["trend", "trnd"])
    assert "kalman_pisa" not in {a.name for a in pipeline.select_alarms("all")}


def test_outputs_follow_benchmark_spec(result):
    res, out = result
    expected = {
        "metrics.csv",
        "summary.csv",
        "config.yaml",
        "git_commit.txt",
        "benchmark_version.txt",
        "assumptions.md",
    }
    assert expected <= {p.name for p in out.iterdir()}
    assert (out / "figures").is_dir()
    assert (out / "benchmark_version.txt").read_text().strip() == pipeline.BENCHMARK_VERSION
    assert (
        "ASSUMPTION" not in (out / "assumptions.md").read_text()[:40]
        and "- `src/" in (out / "assumptions.md").read_text()
    )


def test_every_patient_alarm_pair_is_scored(result):
    res, _ = result
    m = res["metrics"]
    assert set(m["alarm_name"]) == {"trend", "threshold", "iforest_causal_gate", "falling_below_70"}
    assert m.groupby("alarm_name")["patient_id"].nunique().eq(2).all()
    assert (m["hours"] > 23).all()
    s = res["summary"]
    assert {"sens_l1", "false_per_day", "false_compression_per_day"} <= set(s.columns)
    assert np.isfinite(s["false_per_day"]).all()


def test_gated_alarm_is_fitted_and_tuned_on_its_own(result):
    """A gate selected without its combiner arms still gets its detector fitted and its gate
    threshold chosen by the operating-point rule (D5)."""
    res, _ = result
    t = res["thresholds"]
    gate = t[t["alarm_name"] == "iforest_causal_gate"]
    assert len(gate) and gate["threshold"].between(-1e-6, 1.0).all()
    assert gate["feasible"].notna().all()


def test_example_alarm_fires_only_when_low_and_falling():
    alarm = load_alarm(str(ROOT / "examples" / "custom_alarm.py") + ":FallingBelow70")
    times = pd.date_range("2026-01-05", periods=8, freq="5min")
    run = pd.DataFrame(
        {"patient_id": "p", "time": times, "cgm": [90, 80, 72, 69, 66, 66, 66, 66.0]}
    )
    events = alarm.alarms(run)
    assert events["time"].tolist() == [times[3]]


def test_parallel_workers_give_identical_results(tiny):
    tmp, sim_cfg = tiny
    outs = {}
    for workers in (1, 2):
        config = pipeline.BenchConfig(
            name=f"tiny_w{workers}",
            simulation=str(sim_cfg),
            levels=[0.0, 1.0],
            alarms=["trend", "gbm", "baysal_gate", "kalman_pisa_cgm"],
            n_folds=2,
            n_boot=20,
            workers=workers,
        )
        outs[workers] = pipeline.run_benchmark(config, tmp / f"w{workers}")
    keys = ["alarm_name", "level", "patient_id", "seed", "mix"]
    a, b = (outs[w]["metrics"].sort_values(keys).reset_index(drop=True) for w in (1, 2))
    pd.testing.assert_frame_equal(a, b)
    pd.testing.assert_frame_equal(outs[1]["thresholds"], outs[2]["thresholds"])


def test_folds_with_few_level_2_lows_match_level_1_and_are_flagged(result):
    """A7: below MIN_L2_EVENTS level 2 lows in a training fold, D5 matches level 1 sensitivity
    (the tiny cohort has far fewer than 10 level 2 lows per fold)."""
    res, _ = result
    t = res["thresholds"]
    assert {"match_level", "reference_sens", "train_sens"} <= set(t.columns)
    few = t["l2_events_train"].notna() & (t["l2_events_train"] < pipeline.MIN_L2_EVENTS)
    assert few.any()
    assert (t.loc[few, "match_level"] == 1).all() and (~t.loc[few, "estimable"].astype(bool)).all()


def test_config_defaults_match_the_frozen_constants():
    """Configurable assumptions default to the values the v1 results were computed with."""
    from ghostlows.alarms.base import FLICKER_MIN, REFRACTORY_MIN, BaseAlarm
    from ghostlows.bench.analysis import SESOI_RATE_RATIO
    from ghostlows.bench.events import LABEL_HORIZON_MIN
    from ghostlows.bench.pipeline import BenchConfig
    from ghostlows.bench.scoring import DEFAULT_WINDOWS

    c = BenchConfig(name="x", simulation="x.yaml")
    assert c.sesoi == SESOI_RATE_RATIO
    assert c.label_horizon_min == LABEL_HORIZON_MIN
    assert c.refractory_min == REFRACTORY_MIN == BaseAlarm.refractory_min
    assert FLICKER_MIN == 15.0
    assert (c.early_min, c.late_min, c.cause_min, c.near_after_min, c.near_before_min) == (
        DEFAULT_WINDOWS.early,
        DEFAULT_WINDOWS.late,
        DEFAULT_WINDOWS.cause,
        DEFAULT_WINDOWS.after_event,
        DEFAULT_WINDOWS.before_event,
    )
