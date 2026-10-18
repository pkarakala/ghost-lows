"""The real-time PISA rules of [Baysal 2014] with the Kalman estimate they use [Cameron 2012].

Lives in `ghostlows.retro` so the in-browser upload tool can run it (numpy only); the benchmark's
`baysal_gate` alarm imports it from here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def minutes(times) -> np.ndarray:
    """Minutes since the epoch, whatever the datetime unit."""
    return pd.DatetimeIndex(times).as_unit("ns").asi8 / 6e10


@dataclass(frozen=True)
class BaysalParams:
    """One parameter set of the PISA rules. SOURCE: Baysal 2014 (Table 3)"""

    g_in: float  # entry: rate of change below this (mg/dL/min)
    g_out: float  # exit: rate of change above this
    g_ratio: float  # entry: current / previous rate of change above this
    ratio_band: float  # exit rules iii-iv: ratios within 1 +/- band
    # ASSUMPTION: t_PISA,max and t_dropout,max are not given in the paper's tables
    max_pisa_min: float = 120.0
    max_dropout_min: float = 20.0


# SOURCE: Baysal 2014 (Table 3 parameter sets; "trial" was used in a clinical trial)
BAYSAL_SETS = {
    "aggressive": BaysalParams(-1.90, -2.80, 1.20, 0.10),
    "trial": BaysalParams(-2.00, -3.10, 1.50, 0.30),
    "nominal": BaysalParams(-2.50, -2.80, 1.30, 0.30),
    "cautious": BaysalParams(-3.10, -2.80, 1.30, 0.30),
}
# ASSUMPTION: pre-specified set for the benchmark (D7, SR7); the others are a sensitivity analysis
BAYSAL_DEFAULT = "trial"

# ASSUMPTION: Kalman tuning; [Cameron 2012] gives the structure (glucose and rate estimated every
# minute, updated at each sensor reading) but its appendix values were not available.
KF_MEASUREMENT_SD = 10.0  # mg/dL
KF_RATE_SD_PER_MIN = 0.1  # mg/dL/min per sqrt(min), random walk on the rate of change
# SOURCE: Cameron 2012 (after 20 min of dropout, predictions are gradually reset to 140 mg/dL)
KF_DROPOUT_RESET_MIN = 20.0
KF_RESET_TARGET = 140.0
KF_RESET_TAU_MIN = 30.0  # ASSUMPTION: "gradually"


def baysal_flags(times, cgm: np.ndarray, params: BaysalParams | None = None) -> np.ndarray:
    """1.0 where the Baysal rules mark a reading as attenuated (PISA), else 0.0; NaN stays 0.

    Rules a-c start a PISA; d-f end it [Baysal 2014]. Readings marked as PISA are not used to
    update the Kalman estimate, which the paper's exit rule (i) compares against.
    """
    p = params or BAYSAL_SETS[BAYSAL_DEFAULT]
    t_all = minutes(times)
    flags = np.zeros(len(cgm))
    valid = np.flatnonzero(~np.isnan(cgm))
    if valid.size < 3:
        return flags
    t, g = t_all[valid], np.asarray(cgm, float)[valid]

    # Kalman filter on [glucose, rate], propagated minute by minute between readings.
    x = np.array([g[0], 0.0])
    cov = np.diag([KF_MEASUREMENT_SD**2, 1.0])
    r = KF_MEASUREMENT_SD**2
    q = KF_RATE_SD_PER_MIN**2

    def predict(x, cov, dt):
        f = np.array([[1.0, dt], [0.0, 1.0]])
        qd = q * np.array([[dt**3 / 3, dt**2 / 2], [dt**2 / 2, dt]])
        x = f @ x
        if dt > KF_DROPOUT_RESET_MIN:  # long dropout: relax toward the reset target
            w = 1 - np.exp(-(dt - KF_DROPOUT_RESET_MIN) / KF_RESET_TAU_MIN)
            x = np.array([(1 - w) * x[0] + w * KF_RESET_TARGET, (1 - w) * x[1]])
        return x, f @ cov @ f.T + qd

    def update(x, cov, z):
        h = np.array([1.0, 0.0])
        s = h @ cov @ h + r
        k = cov @ h / s
        return x + k * (z - x[0]), cov - np.outer(k, h @ cov)

    roc = np.full(len(g), np.nan)
    roc[1:] = np.diff(g) / np.diff(t)
    curv = np.full(len(g), np.nan)
    curv[2:] = np.diff(roc[1:]) / np.diff(t[1:])
    in_pisa, n_pisa, start = False, 0, 0
    band = (1 - p.ratio_band, 1 + p.ratio_band)

    def within(a, b):
        if b == 0 or np.isnan(a) or np.isnan(b):
            return False
        return band[0] <= a / b <= band[1]

    for k in range(len(g)):
        if k > 0:
            x, cov = predict(x, cov, t[k] - t[k - 1])
        estimate = x[0]
        if not in_pisa:
            rule_a = k >= 2  # third valid reading onwards (0-based index 2)
            rule_b = rule_a and roc[k] < p.g_in
            # ASSUMPTION: a previous rate of exactly 0 counts like a positive one (infinite ratio)
            rule_c = rule_b and (roc[k - 1] >= 0 or roc[k] / roc[k - 1] > p.g_ratio)
            if rule_c:
                in_pisa, n_pisa, start = True, 1, k
        else:
            n_pisa += 1
            rule_d = t[k - 1] - t[start] >= p.max_pisa_min
            rule_e = t[k] - t[k - 1] >= p.max_dropout_min
            rule_f = roc[k] > p.g_out and (
                estimate < g[k]
                or (n_pisa >= 3 and curv[k] < 0 and curv[k - 1] < 0)
                or (k >= 3 and within(roc[k - 3], roc[k - 1]) and within(roc[k - 3], roc[k]))
                or (k >= 4 and within(roc[k - 4], roc[k - 1]) and within(roc[k - 4], roc[k]))
            )
            if rule_d or rule_e or rule_f:
                in_pisa = False
        if in_pisa:
            flags[valid[k]] = 1.0
        else:
            x, cov = update(x, cov, g[k])  # attenuated readings are not used
    return flags
