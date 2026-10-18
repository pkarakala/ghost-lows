"""Realistic default PISA frequency (SIMULATION.md §4.1, CR3).

[Lobo 2026] counts PISAs whose minimum sensor glucose falls below 85 mg/dL: 846 in 59,122 h,
89 in 8,189 h and 325 in 26,890 h, pooled 1,260 in 94,201 h (about one per 74.8 h of wear). How
many injected PISAs reach that depth depends on the cohort's overnight glucose, so the fraction
of nights that reproduces the rate is computed on the simulated cohort itself. Faults are thinned
(suite.py), so the expected rate is exactly linear in the fraction: rate(f) = f * rate(1).
"""

from __future__ import annotations

import pandas as pd

from .suite import FaultConfig, apply_faults

# SOURCE: Lobo 2026 (abstract: 1,260 PISAs with minimum sensor glucose < 85 mg/dL in 94,201 h)
# CLINICAL-REVIEW: CR3
LOBO_PISAS, LOBO_HOURS = 846 + 89 + 325, 59_122 + 8_189 + 26_890
LOBO_THRESHOLD = 85.0
TARGET_PER_HOUR = LOBO_PISAS / LOBO_HOURS


def pisa_rate_at_full(
    samples: pd.DataFrame, seed: int = 0, threshold: float = LOBO_THRESHOLD
) -> float:
    """PISAs per hour of wear reaching an observed CGM below `threshold`, one PISA every night."""
    config = FaultConfig(pisa_fraction=1.0, enabled=frozenset({"pisa"}))
    observed, faults = apply_faults(samples, config, seed=seed)
    keys = [k for k in ("patient_id", "seed", "mix") if k in observed]
    deep = 0
    for _, f in faults.iterrows():
        run = observed
        for k in keys:
            run = run[run[k] == f[k]]
        window = run[(run["time"] >= f["start"]) & (run["time"] <= f["end"])]
        deep += bool((window["cgm_observed"] < threshold).any())
    hours = observed.groupby(keys)["time"].agg(
        lambda t: (t.max() - t.min()) / pd.Timedelta("1h") + 5 / 60
    )
    return deep / float(hours.sum())


def realistic_fraction(samples: pd.DataFrame, seed: int = 0) -> dict:
    """Fraction of nights with a PISA that reproduces the Lobo 2026 rate on this cohort."""
    at_full = pisa_rate_at_full(samples, seed)
    fraction = TARGET_PER_HOUR / at_full if at_full > 0 else float("nan")
    return {
        "target_per_hour": TARGET_PER_HOUR,
        "rate_at_full": at_full,
        "fraction": min(fraction, 1.0),
        "reachable": bool(fraction <= 1.0),
    }
