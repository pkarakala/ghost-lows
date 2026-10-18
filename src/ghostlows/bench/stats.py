"""Cross-validation folds, the pre-registered operating point and patient-level CIs (D5, D14).

All resampling is over patients, never over seeds or samples: a patient's runs (every seed and
scenario mix) stay together in one fold and are drawn together in the bootstrap.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

N_FOLDS = 5  # BENCHMARK.md §6
N_BOOT = 2000  # BENCHMARK.md §6
MIN_L2_EVENTS = 10  # ASSUMPTION: BENCHMARK.md §5 (D5)


def age_group(patient_id: str) -> str:
    """'adolescent', 'adult' or 'child' for simulated IDs like 'sim:adult#001'; else 'other'."""
    name = patient_id.split(":")[-1]
    return name.split("#")[0] if "#" in name else "other"


def patient_folds(patient_ids, n_folds: int = N_FOLDS, seed: int = 0) -> dict[str, int]:
    """Leave-patients-out folds, stratified by age group (each group dealt round-robin)."""
    rng = np.random.default_rng(seed)
    folds, offset = {}, 0
    ids = sorted(set(patient_ids))
    for group in sorted({age_group(p) for p in ids}):
        members = [p for p in ids if age_group(p) == group]
        for i, p in enumerate(rng.permutation(members)):
            folds[str(p)] = (i + offset) % n_folds
        offset += len(members)
    return folds


def choose_threshold(
    candidates: np.ndarray,
    sensitivity: Callable[[float], float],
    false_per_day: Callable[[float], float],
    reference_sensitivity: float,
    delta: float = 0.0,
) -> tuple[float, dict]:
    """The pre-registered rule (D5): fewest false alarms/day with level 2 sensitivity at least the
    reference minus `delta`; ties go to the more sensitive (lower) threshold. Training data only."""
    rows = [
        {"threshold": float(t), "sens": sensitivity(t), "fpd": false_per_day(t)}
        for t in sorted(candidates)
    ]
    table = pd.DataFrame(rows)
    ok = table[table["sens"] >= reference_sensitivity - delta - 1e-12]
    if ok.empty:  # nothing reaches the reference: take the most sensitive candidate, flagged
        best = table.sort_values(["sens", "fpd", "threshold"], ascending=[False, True, True]).iloc[
            0
        ]
        return float(best["threshold"]), {"feasible": False, "table": table}
    best = ok.sort_values(["fpd", "sens", "threshold"], ascending=[True, False, True]).iloc[0]
    return float(best["threshold"]), {"feasible": True, "table": table}


def candidate_thresholds(scores: np.ndarray, n: int = 60, low: float = 0.5) -> np.ndarray:
    """Quantiles `low`..0.999 of the finite training scores (by default the upper tail, where
    alarms live), plus the extremes. Gated alarms use low = 0: their finite scores are the trend
    alarm's firings, and every suppression fraction is a candidate."""
    s = np.asarray(scores, float)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return np.array([0.5])
    qs = np.unique(np.quantile(s, np.r_[np.linspace(low, 0.999, n), [0.0, 1.0]]))
    return qs - 1e-9  # alarms fire when score > threshold


def bootstrap_ci(
    per_patient: pd.DataFrame,
    statistic: Callable[[pd.DataFrame], float],
    n_boot: int = N_BOOT,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float, float]:
    """(estimate, low, high): percentile CI from a patient bootstrap stratified by age group.

    `per_patient` has one row per patient (column `patient_id`); `statistic` maps a resample
    (rows may repeat) to a number, e.g. a ratio of summed counts.
    """
    rng = np.random.default_rng(seed)
    groups = per_patient.groupby(per_patient["patient_id"].map(age_group)).indices
    estimate = float(statistic(per_patient))
    draws = []
    for _ in range(n_boot):
        idx = np.concatenate(
            [rng.choice(rows, size=len(rows), replace=True) for rows in groups.values()]
        )
        draws.append(statistic(per_patient.iloc[idx]))
    draws = np.asarray(draws, float)
    draws = draws[np.isfinite(draws)]
    alpha = (1 - level) / 2
    lo, hi = np.quantile(draws, [alpha, 1 - alpha]) if draws.size else (np.nan, np.nan)
    return estimate, float(lo), float(hi)


def ratio_of_sums(numerator: str, denominator: str) -> Callable[[pd.DataFrame], float]:
    """Statistic for rates pooled over patients (e.g. caught / events, or arm A / arm B counts)."""

    def stat(df: pd.DataFrame) -> float:
        d = df[denominator].sum()
        return float(df[numerator].sum() / d) if d > 0 else float("nan")

    return stat


def bootstrap_ratios(
    numerators: np.ndarray,
    denominators: np.ndarray,
    patient_ids,
    n_boot: int = N_BOOT,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised `bootstrap_ci` for ratio-of-sums statistics.

    `numerators` / `denominators` are (patients x statistics); returns estimates, lows and highs
    per statistic. Resampling is stratified by age group, as in `bootstrap_ci`.
    """
    num = np.atleast_2d(np.asarray(numerators, float).T).T
    den = np.atleast_2d(np.asarray(denominators, float).T).T
    rng = np.random.default_rng(seed)
    index = []
    labels = np.array([age_group(p) for p in patient_ids])
    for g in sorted(set(labels)):
        rows = np.flatnonzero(labels == g)
        index.append(rows[rng.integers(0, len(rows), size=(n_boot, len(rows)))])
    idx = np.concatenate(index, axis=1)  # n_boot x n_patients
    with np.errstate(invalid="ignore", divide="ignore"):
        est = num.sum(0) / den.sum(0)
        draws = num[idx].sum(1) / den[idx].sum(1)  # n_boot x statistics
    alpha = (1 - level) / 2
    lo = np.nanquantile(np.where(np.isfinite(draws), draws, np.nan), alpha, axis=0)
    hi = np.nanquantile(np.where(np.isfinite(draws), draws, np.nan), 1 - alpha, axis=0)
    est = np.where(den.sum(0) > 0, est, np.nan)
    return est, lo, hi
