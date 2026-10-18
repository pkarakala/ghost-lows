"""End-to-end: a tiny simulated cohort through faults, CV, operating point and scoring, plus the
plug-in example (PUBLICATION.md: the example must run in CI)."""

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
def result(tmp_path_factory):
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
