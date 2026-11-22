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


# ASSUMPTION: log-spaced firing fractions from 5% down to 0.01% of training samples are added to
# the evenly spaced quantiles, so the rule can reach the sparse operating points that low alarms
# need (time below range is a few percent); amendment A2
TAIL_FRACTIONS = (0.05, 1e-4)


def candidate_thresholds(scores: np.ndarray, n: int = 60, low: float = 0.5) -> np.ndarray:
    """Candidate thresholds from the finite training scores: quantiles evenly spaced from `low`
    to 0.999, quantiles at `n // 2` log-spaced upper-tail fractions (TAIL_FRACTIONS), and the
    extremes. Gated alarms use low = 0: their finite scores are the trend alarm's firings, and
    every suppression fraction is a candidate."""
    s = np.asarray(scores, float)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return np.array([0.5])
    tail = 1 - np.geomspace(*TAIL_FRACTIONS, max(n // 2, 2))
    qs = np.unique(np.quantile(s, np.r_[np.linspace(low, 0.999, n), tail, [0.0, 1.0]]))
    return qs - 1e-9  # alarms fire when score > threshold


# A18 (P13, audit fix 4): the primary 95% interval is a bootstrap-standard-error t interval,
# on the log scale for positive statistics, with n_patients - n_age_groups degrees of freedom;
# the percentile interval is kept beside it, with the share of non-finite draws.
# ASSUMPTION: t interval primary because percentile intervals under-cover with 3 x 10 patients
# (about 87-93% at a nominal 95% in the 2026-11 audit's simulation)


def t_quantile(p: float, df: int) -> float:
    """Student t quantile (Cornish-Fisher expansion; error below 1e-4 for df >= 5)."""
    from statistics import NormalDist

    z = NormalDist().inv_cdf(p)
    g1 = (z**3 + z) / 4
    g2 = (5 * z**5 + 16 * z**3 + 3 * z) / 96
    g3 = (3 * z**7 + 19 * z**5 + 17 * z**3 - 15 * z) / 384
    g4 = (79 * z**9 + 776 * z**7 + 1482 * z**5 - 1920 * z**3 - 945 * z) / 92160
    return z + g1 / df + g2 / df**2 + g3 / df**3 + g4 / df**4


def t_bounds(
    estimate: float, draws: np.ndarray, df: int, level: float = 0.95
) -> tuple[float, float]:
    """estimate +- t * SE(draws), on the log scale when the estimate and every draw are > 0."""
    d = np.asarray(draws, float)
    d = d[np.isfinite(d)]
    if d.size < 2 or not np.isfinite(estimate) or df < 1:
        return float("nan"), float("nan")
    if np.ptp(d) == 0:  # no spread: the interval is the point (avoids log/exp rounding)
        return float(estimate), float(estimate)
    q = t_quantile(1 - (1 - level) / 2, df)
    if estimate > 0 and (d > 0).all():
        se = float(np.std(np.log(d), ddof=1))
        return float(estimate * np.exp(-q * se)), float(estimate * np.exp(q * se))
    se = float(np.std(d, ddof=1))
    return float(estimate - q * se), float(estimate + q * se)


def bootstrap_ci(
    per_patient: pd.DataFrame,
    statistic: Callable[[pd.DataFrame], float],
    n_boot: int = N_BOOT,
    seed: int = 0,
    level: float = 0.95,
    detail: bool = False,
):
    """(estimate, low, high) from a patient bootstrap stratified by age group: the t interval
    (A18). With `detail`, a dict that adds the percentile interval and the non-finite share.

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
    finite = draws[np.isfinite(draws)]
    alpha = (1 - level) / 2
    lo, hi = np.quantile(finite, [alpha, 1 - alpha]) if finite.size else (np.nan, np.nan)
    df = len(per_patient) - len(groups)
    lo_t, hi_t = t_bounds(estimate, finite, df, level)
    if not detail:
        return estimate, lo_t, hi_t
    return {
        "estimate": estimate,
        "lo": lo_t,
        "hi": hi_t,
        "lo_pct": float(lo),
        "hi_pct": float(hi),
        "nonfinite_share": float(1 - finite.size / max(len(draws), 1)),
    }


def bootstrap_ratios(
    numerators: np.ndarray,
    denominators: np.ndarray,
    patient_ids,
    n_boot: int = N_BOOT,
    seed: int = 0,
    level: float = 0.95,
    detail: bool = False,
):
    """Vectorised `bootstrap_ci` for ratio-of-sums statistics.

    `numerators` / `denominators` are (patients x statistics); returns estimates, lows and highs
    (t intervals, A18) per statistic; with `detail`, also percentile lows and highs and the
    non-finite share. Resampling is stratified by age group, as in `bootstrap_ci`.
    """
    num = np.atleast_2d(np.asarray(numerators, float).T).T
    den = np.atleast_2d(np.asarray(denominators, float).T).T
    rng = np.random.default_rng(seed)
    index = []
    labels = np.array([age_group(p) for p in patient_ids])
    strata = sorted(set(labels))
    for g in strata:
        rows = np.flatnonzero(labels == g)
        index.append(rows[rng.integers(0, len(rows), size=(n_boot, len(rows)))])
    idx = np.concatenate(index, axis=1)  # n_boot x n_patients
    with np.errstate(invalid="ignore", divide="ignore"):
        est = num.sum(0) / den.sum(0)
        draws = num[idx].sum(1) / den[idx].sum(1)  # n_boot x statistics
    alpha = (1 - level) / 2
    clean = np.where(np.isfinite(draws), draws, np.nan)
    lo = np.nanquantile(clean, alpha, axis=0)
    hi = np.nanquantile(clean, 1 - alpha, axis=0)
    est = np.where(den.sum(0) > 0, est, np.nan)
    df = len(labels) - len(strata)
    bounds = [t_bounds(est[j], draws[:, j], df, level) for j in range(draws.shape[1])]
    lo_t = np.array([b[0] for b in bounds])
    hi_t = np.array([b[1] for b in bounds])
    if not detail:
        return est, lo_t, hi_t
    nonfinite = 1 - np.isfinite(draws).mean(axis=0)
    return est, lo_t, hi_t, lo, hi, nonfinite
