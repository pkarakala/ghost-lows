"""Folds, operating point and bootstrap (BENCHMARK.md §5-6)."""

import numpy as np
import pandas as pd
import pytest

from ghostlows.bench.stats import (
    age_group,
    bootstrap_ci,
    bootstrap_ratios,
    candidate_thresholds,
    choose_threshold,
    patient_folds,
    ratio_of_sums,
)
from ghostlows.sim.engine import PATIENTS

IDS = [f"sim:{p}" for p in PATIENTS]


def test_folds_are_stratified_and_keep_patients_whole():
    folds = patient_folds(IDS, seed=3)
    assert set(folds) == set(IDS)
    table = pd.DataFrame(
        {"pid": IDS, "fold": [folds[p] for p in IDS], "group": [age_group(p) for p in IDS]}
    )
    counts = table.groupby(["fold", "group"]).size().unstack()
    assert (counts == 2).all().all()  # 10 per group over 5 folds
    assert patient_folds(IDS, seed=3) == folds and patient_folds(IDS, seed=4) != folds


def test_choose_threshold_follows_the_preregistered_rule():
    sens = {0.1: 0.9, 0.2: 0.8, 0.3: 0.8, 0.4: 0.6}
    fpd = {0.1: 3.0, 0.2: 2.0, 0.3: 2.0, 0.4: 0.5}
    theta, info = choose_threshold(
        np.array(list(sens)), sens.get, fpd.get, reference_sensitivity=0.8
    )
    assert info["feasible"] and theta == pytest.approx(0.2)  # tie on fpd -> more sensitive (lower)
    theta, _ = choose_threshold(
        np.array(list(sens)), sens.get, fpd.get, reference_sensitivity=0.8, delta=0.2
    )
    assert theta == pytest.approx(0.4)  # non-inferiority margin admits 0.6
    theta, info = choose_threshold(
        np.array(list(sens)), sens.get, fpd.get, reference_sensitivity=0.95
    )
    assert not info["feasible"] and theta == pytest.approx(0.1)


def test_candidate_thresholds_cover_the_upper_tail():
    c = candidate_thresholds(np.linspace(0, 1, 1001))
    assert c.min() < 0.01 and c.max() > 0.99 and len(c) > 50


def test_candidates_resolve_sparse_operating_points():
    """Firing fractions between 0.1% and 2% of samples are where low alarms operate (A2)."""
    scores = np.random.default_rng(0).uniform(size=200_000)
    c = candidate_thresholds(scores, n=30)
    fractions = np.array([(scores > t).mean() for t in c])
    assert ((fractions > 1e-3) & (fractions < 0.02)).sum() >= 5
    assert fractions[fractions > 0].min() < 3e-4


def test_bootstrap_ci_contains_estimate_and_is_degenerate_for_constant_data():
    df = pd.DataFrame({"patient_id": IDS, "x": 2.0, "n": 1.0})
    est, lo, hi = bootstrap_ci(df, ratio_of_sums("x", "n"), n_boot=200)
    assert est == lo == hi == 2.0
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"patient_id": IDS, "x": rng.poisson(3, len(IDS)).astype(float), "n": 1.0})
    est, lo, hi = bootstrap_ci(df, ratio_of_sums("x", "n"), n_boot=500)
    assert lo < est < hi and hi - lo < 2.0


def test_vectorised_bootstrap_agrees_with_the_reference():
    rng = np.random.default_rng(1)
    df = pd.DataFrame(
        {
            "patient_id": IDS,
            "x": rng.poisson(4, len(IDS)).astype(float),
            "n": rng.uniform(5, 15, len(IDS)),
        }
    )
    ref = bootstrap_ci(df, ratio_of_sums("x", "n"), n_boot=4000, seed=2)
    est, lo, hi = bootstrap_ratios(
        df[["x"]].to_numpy(), df[["n"]].to_numpy(), df["patient_id"], n_boot=4000, seed=5
    )
    assert est[0] == pytest.approx(ref[0])
    assert lo[0] == pytest.approx(ref[1], abs=0.03) and hi[0] == pytest.approx(ref[2], abs=0.03)
