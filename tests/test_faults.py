"""Fault-suite tests (SIMULATION.md §4-5)."""

import numpy as np
import pandas as pd
import pytest

from ghostlows.faults import pisa
from ghostlows.faults.suite import (
    DROPOUT_RATE_PER_MIN,
    FaultConfig,
    apply_faults,
    draw_pisas,
    inject_real,
    stable_onsets,
)


def clean_run(days=4, level=110.0, seed=0, patient="sim:adult#001"):
    times = pd.date_range("2026-01-05", periods=days * 288, freq="5min")
    rng = np.random.default_rng(seed)
    isf = level + 15 * np.sin(np.arange(len(times)) / 40)
    noise = rng.normal(0, 3, len(times))
    return pd.DataFrame(
        {
            "patient_id": patient,
            "time": times,
            "glucose": np.clip(isf + noise, 40, 400),
            "truth_glucose": isf + 2.0,
            "isf_glucose": isf,
            "cgm_noise": noise,
            "seed": 1,
            "mix": "default",
        }
    )


def test_two_piece_lognormal_matches_published_quantiles_exactly():
    for dist, (med, p5, p95) in [
        (pisa.DEPTH, pisa.DEPTH_MG_DL),
        (pisa.DURATION, pisa.DURATION_MIN),
    ]:
        assert dist.quantile(0.5) == pytest.approx(med)
        assert dist.quantile(0.05) == pytest.approx(p5)
        assert dist.quantile(0.95) == pytest.approx(p95)


def test_realised_depth_and_duration_measured_on_traces_match_the_paper():
    """Quantiles measured on generated artifacts (1-min resolution), not on the parameters."""
    rng = np.random.default_rng(42)
    depths, durations = pisa.sample_sizes(rng, 4000)
    t = np.arange(0, 400, 1.0)
    measured_depth, measured_duration = [], []
    for d, u in zip(depths, durations, strict=True):
        a = pisa.from_size(0.0, d, u).attenuation(t)
        peak = int(np.argmax(a))
        measured_depth.append(a[peak])
        after = np.flatnonzero(a[peak:] <= pisa.END_FRACTION * a[peak])
        measured_duration.append(peak + after[0])
    for values, (med, p5, p95) in [
        (measured_depth, pisa.DEPTH_MG_DL),
        (measured_duration, pisa.DURATION_MIN),
    ]:
        q5, q50, q95 = np.percentile(values, [5, 50, 95])
        assert q50 == pytest.approx(med, rel=0.04)
        assert q5 == pytest.approx(p5, rel=0.08)
        assert q95 == pytest.approx(p95, rel=0.08)


def test_pisa_shape_is_a_first_order_response_to_a_rectangle():
    p = pisa.Pisa(onset=100.0, pressure_min=30.0, amplitude=40.0, tau=10.0)
    t = np.array([99, 100, 110, 130, 140, 300.0])
    a = p.attenuation(t)
    assert a[0] == 0 and a[1] == 0
    assert a[2] == pytest.approx(40 * (1 - np.exp(-1)))
    assert a[3] == pytest.approx(p.depth) and p.depth == pytest.approx(40 * (1 - np.exp(-3)))
    assert a[4] == pytest.approx(p.depth * np.exp(-1))
    assert a[5] == 0  # past the 1% tail
    with pytest.raises(ValueError):
        pisa.from_size(0, 20, 15)  # too short for tau = 10


def test_pisas_fall_in_complete_nights_at_the_requested_fraction():
    rng = np.random.default_rng(1)
    every = draw_pisas(rng, 14, FaultConfig(pisa_fraction=1.0))
    assert len(every) == 13  # complete nights in 14 days
    for p in every:
        minute_of_day = p.onset % 1440
        assert minute_of_day >= 23 * 60 or minute_of_day < 7 * 60
    counts = [
        len(draw_pisas(np.random.default_rng(s), 14, FaultConfig(pisa_fraction=0.25)))
        for s in range(200)
    ]
    assert np.mean(counts) == pytest.approx(13 * 0.25, rel=0.1)


def test_faults_never_touch_truth_or_clean_signals():
    run = clean_run()
    out, faults = apply_faults(run, FaultConfig(pisa_fraction=1.0, severity=1.0), seed=3)
    for col in ["truth_glucose", "isf_glucose", "glucose", "cgm_noise", "time", "patient_id"]:
        pd.testing.assert_series_equal(out[col], run[col])
    assert set(faults["fault_type"]) == {"pisa", "dropout", "stale", "spike", "drift"}
    assert out["cgm_observed"].isna().any() and (out["cgm_observed_flag"] == "missing").any()
    assert set(out["fault_type"]) >= {"pisa", "dropout"}


def test_no_faults_at_zero_severity():
    run = clean_run()
    out, faults = apply_faults(run, FaultConfig(pisa_fraction=0.0, severity=0.0), seed=3)
    assert faults.empty and (out["fault_type"] == "none").all()
    assert np.allclose(out["cgm_observed"], np.clip(run["isf_glucose"] + run["cgm_noise"], 40, 400))


def test_pisa_lowers_only_the_observed_signal_during_the_artifact():
    run = clean_run(days=3)
    out, faults = apply_faults(
        run, FaultConfig(pisa_fraction=1.0, enabled=frozenset({"pisa"})), seed=5
    )
    diff = (out["cgm_observed"] - out["glucose"]).to_numpy()
    assert (diff <= 1e-9).all() and diff.min() < -5
    active = out["fault_type"] == "pisa"
    # outside the active window only the decay tail (< 10% of the peak) remains
    tail = pisa.END_FRACTION * faults["size"].max() + 1e-6
    assert active.any() and (np.abs(diff[~active.to_numpy()]) <= tail).all()
    assert len(faults) == 2


def test_dropout_lengths_follow_facchinetti_90_percent_under_20_min():
    rng = np.random.default_rng(0)
    lengths = rng.exponential(1 / DROPOUT_RATE_PER_MIN, 100_000)
    assert np.mean(lengths < 20) == pytest.approx(0.90, abs=0.005)


def test_faults_are_reproducible_and_independent_across_runs():
    runs = pd.concat([clean_run(patient="sim:a"), clean_run(patient="sim:b")])
    config = FaultConfig(pisa_fraction=0.5, severity=0.5)
    a, fa = apply_faults(runs, config, seed=9)
    b, fb = apply_faults(runs, config, seed=9)
    pd.testing.assert_frame_equal(a, b)
    pd.testing.assert_frame_equal(fa, fb)
    obs = a.pivot(index="time", columns="patient_id", values="cgm_observed")
    assert not np.allclose(obs["sim:a"].fillna(0), obs["sim:b"].fillna(0))


def test_drift_resets_at_sensor_change():
    run = clean_run(days=12)
    config = FaultConfig(severity=1.0, enabled=frozenset({"drift"}))
    out, faults = apply_faults(run, config, seed=2)
    ratio = (
        out["cgm_observed"] / np.clip(run["isf_glucose"] + run["cgm_noise"], 40, 400)
    ).to_numpy()
    change = 10 * 288
    assert abs(ratio[change] - 1) < 0.01 and abs(ratio[change - 1] - 1) > 0.09
    assert len(faults) == 2


def real_night_trace():
    times = pd.date_range("2026-01-05 20:00", periods=12 * 24, freq="5min")  # 20:00 to 19:55
    return pd.DataFrame({"patient_id": "weinstock:1", "time": times, "glucose": 120.0})


def test_stable_onsets_avoid_lows_and_gaps():
    run = real_night_trace()
    assert len(stable_onsets(run)) > 0
    low = run.assign(
        glucose=np.where(run["time"].dt.hour.isin([23, 0, 1, 2, 3, 4, 5, 6]), 60.0, 120.0)
    )
    assert stable_onsets(low) == []


def test_inject_real_keeps_the_reference():
    run = real_night_trace()
    out, faults = inject_real(run, per_night=1.0, seed=4)
    assert len(faults) == 1
    pd.testing.assert_series_equal(out["glucose"], run["glucose"])
    assert out["cgm_observed"].min() < 120 - 5 and (out["fault_type"] == "pisa").any()


def test_sweeps_are_nested_and_fault_types_are_independent():
    """Common random numbers: PISAs at 25% of nights are a subset of those at 50%, and enabling
    other faults never changes the PISAs (SIMULATION.md §4.3)."""
    run = clean_run(days=14)

    def pisas(**kw):
        return apply_faults(run, FaultConfig(**kw), seed=11)[1].query("fault_type == 'pisa'")

    quarter = pisas(pisa_fraction=0.25, enabled=frozenset({"pisa"}))
    half = pisas(pisa_fraction=0.5, enabled=frozenset({"pisa"}))
    assert 0 < len(quarter) < len(half)
    assert set(quarter["start"]) <= set(half["start"])
    with_others = pisas(pisa_fraction=0.5, severity=1.0)
    assert list(with_others["start"]) == list(half["start"])
    assert np.allclose(with_others["size"], half["size"])


def test_run_faults_depend_only_on_seed_and_run_identity():
    a = clean_run(patient="sim:a")
    both = pd.concat([a, clean_run(patient="sim:b")])
    config = FaultConfig(pisa_fraction=0.5, severity=0.5)
    alone, _ = apply_faults(a, config, seed=3)
    together, _ = apply_faults(both, config, seed=3)
    pd.testing.assert_series_equal(
        alone["cgm_observed"],
        together.loc[together["patient_id"] == "sim:a", "cgm_observed"].reset_index(drop=True),
    )


def test_realistic_fraction_scales_linearly_with_the_lobo_rate():
    from ghostlows.faults.calibrate import TARGET_PER_HOUR, realistic_fraction

    assert 1 / TARGET_PER_HOUR == pytest.approx(74.76, abs=0.01)  # 94,201 h / 1,260 PISAs
    low_night = clean_run(days=8, level=95.0)  # clean CGM 80-110: every PISA can reach < 85
    out = realistic_fraction(low_night)
    assert out["reachable"] and 0 < out["fraction"] < 1
    # with a PISA every night the rate is (nights reaching < 85) / hours
    assert out["rate_at_full"] <= 7 / (8 * 24) + 1e-9
