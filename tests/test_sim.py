"""Simulation tests (SIMULATION.md §1-3). Short runs only; the full config runs outside CI."""

import dataclasses

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("simglucose")

from ghostlows.sim import context, run  # noqa: E402
from ghostlows.sim.engine import Therapy, first_order_lag, simulate  # noqa: E402
from ghostlows.sim.scenario import DEFAULT, STANDARD, Mix, get_mix, make_scenario  # noqa: E402


@pytest.fixture(scope="module")
def one_day():
    scenario = make_scenario(DEFAULT, 1, meal_seed=11, perturb_seed=12)
    return scenario, simulate("adult#001", scenario, Therapy(), noise_seed=13)


def test_scenarios_are_reproducible_and_paired_across_mixes():
    a = make_scenario(DEFAULT, 3, 1, 2)
    b = make_scenario(DEFAULT, 3, 1, 2)
    pd.testing.assert_frame_equal(a.meals, b.meals)
    assert np.array_equal(a.sensitivity, b.sensitivity)
    s = make_scenario(STANDARD, 3, 1, 2)
    pd.testing.assert_series_equal(s.meals["carbs_true"], a.meals["carbs_true"])
    assert (s.sensitivity == 1).all() and s.exercise.empty
    assert (s.meals["carbs_announced"] == s.meals["carbs_true"]).all()
    assert s.meals["bolus_given"].all() and s.meals["eaten"].all()


def test_recording_error_families():
    missed = make_scenario(Mix("t", p_missed_bolus=1.0), 2, 1, 2).meals
    assert not missed["bolus_given"].any() and (missed["carbs_announced"] == 0).all()
    skipped = make_scenario(Mix("t", p_skipped_meal=1.0), 2, 1, 2).meals
    assert skipped["bolus_given"].all() and not skipped["eaten"].any()
    assert (skipped["carbs_announced"] == skipped["carbs_true"]).all()


def test_sensitivity_changes_only_at_noon():
    scenario = make_scenario(Mix("t", sensitivity_range=(0.7, 1.3)), 3, 1, 2)
    changes = np.flatnonzero(np.diff(scenario.sensitivity)) + 1
    assert len(changes) > 0 and set(changes % 1440) == {720}


def test_truth_is_plasma_and_cgm_lags_it(one_day):
    _, r = one_day
    s = r.samples
    assert not np.allclose(s["truth_glucose"], s["isf_glucose"])
    x, y = s["truth_glucose"].to_numpy(), s["isf_glucose"].to_numpy()
    corr = [np.corrcoef(x[: len(x) - k], y[k:])[0, 1] for k in range(6)]
    assert int(np.argmax(corr)) >= 1  # interstitial glucose trails plasma
    assert s["glucose"].between(40, 400).all()
    assert np.allclose(s["glucose"], np.clip(s["isf_glucose"] + s["cgm_noise"], 40, 400))
    assert len(r.truth) == 1440 and r.valid


def test_one_bolus_per_bolused_meal(one_day):
    scenario, r = one_day
    n_bolused = int(scenario.meals["bolus_given"].sum())
    assert (r.events["kind"] == "bolus").sum() == n_bolused
    assert np.isclose(
        r.samples["insulin_bolus"].sum(), r.events.loc[r.events.kind == "bolus", "value"].sum()
    )


def test_context_is_recomputable_from_logged_events(one_day):
    _, r = one_day
    minutes = ((r.samples["time"] - r.samples["time"].iloc[0]) / pd.Timedelta("1min")).to_numpy()
    b = r.events[r.events.kind == "bolus"]
    c = r.events[r.events.kind == "carbs_announced"]
    assert np.allclose(context.iob(b["minute"], b["value"], minutes), r.samples["iob"])
    assert np.allclose(context.cob(c["minute"], c["value"], minutes), r.samples["cob"])


def test_context_is_causal():
    q = np.arange(0, 600, 5)
    full = context.iob([100, 400], [2.0, 3.0], q)
    first = context.iob([100], [2.0], q)
    assert np.allclose(full[q < 400], first[q < 400])
    assert context.iob_fraction(0) == 1 and context.iob_fraction(300) == 0


def test_exercise_and_sensitivity_cause_lows_that_insulin_does_not_explain():
    """Same meals, same recorded doses; raised insulin sensitivity alone adds lows (SR14, D3)."""
    days, patient = 2, "adolescent#002"  # no lows in 2 standard days (checked 2026-10-18)
    perturbed_mix = Mix("t", sensitivity_range=(1.3, 1.3), exercise_per_week=(7, 7))
    base = make_scenario(STANDARD, days, 21, 22)
    perturbed = make_scenario(perturbed_mix, days, 21, 22)
    # Corrections depend on the CGM, so pin doses: no correction boluses in either run.
    therapy = dataclasses.replace(Therapy(), correction_above=1e9)
    a = simulate(patient, base, therapy, noise_seed=23)
    b = simulate(patient, perturbed, therapy, noise_seed=23)
    assert np.allclose(a.samples["iob"], b.samples["iob"])  # recorded insulin is identical
    low_a = (a.truth["truth_glucose"] < 70).mean()
    low_b = (b.truth["truth_glucose"] < 70).mean()
    assert low_b > low_a + 0.02, (low_a, low_b)
    assert b.truth["truth_glucose"].min() < a.truth["truth_glucose"].min() - 10


def test_first_order_lag_step_response():
    y = first_order_lag(np.r_[np.zeros(1), np.ones(60)], tau_min=6.0)
    assert y[1 + 6] == pytest.approx(1 - np.exp(-1), abs=0.02)


def test_task_seeds_differ_by_patient_and_seed_not_by_mix():
    a, b = run.task_seeds(1, "adult#001"), run.task_seeds(1, "adult#002")
    assert a != b and a != run.task_seeds(2, "adult#001")
    assert a == run.task_seeds(1, "adult#001")


def test_get_mix_rejects_unknown():
    with pytest.raises(ValueError):
        get_mix("nope")


def test_run_writes_and_reuses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "DATA", tmp_path)
    config = run.SimConfig(name="t", patients=["adult#001"], days=1, seeds=[1], mixes=["standard"])
    out = run.run(config, workers=1)
    assert {p.name for p in out.iterdir()} >= {
        "samples",
        "truth",
        "events",
        "runs.csv",
        "meta.json",
    }
    assert len(list((out / "truth").glob("*.parquet"))) == 1
    stamp = (out / "meta.json").stat().st_mtime_ns
    assert run.run(config, workers=1) == out and (out / "meta.json").stat().st_mtime_ns == stamp
    longer = dataclasses.replace(config, days=2)
    assert longer.key() != config.key()
    loaded = run.load(out)
    assert len(loaded["truth"]) == 1440 and set(loaded["samples"]["mix"]) == {"standard"}
