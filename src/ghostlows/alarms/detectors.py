"""PISA detectors used as gates on the trend alarm (BENCHMARK.md §2, D7).

- `baysal_flags`: the real-time rule-based detector of [Baysal 2014], with the Kalman glucose
  estimate it relies on [Cameron 2012].
- `matched_filter_score`: a *causal adaptation* of the matched filter of [Idi 2023]: only past
  samples, template = drop phase of the Facchinetti PISA shape [Facchinetti 2016].
- `IForestScorer`: a *causal adaptation* of the isolation-forest detector of [Idi 2024] on
  trailing-window features.

Each returns a gate value in [0, 1] per sample: 1 = "this looks like a compression artifact".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..faults import pisa as pisa_model
from ..retro.baysal import (  # noqa: F401  (re-exported for the alarms)
    BAYSAL_DEFAULT,
    BAYSAL_SETS,
    BaysalParams,
    baysal_flags,
)
from .base import trailing_slope

# ---------------------------------------------------------------- matched filter (causal)

# ASSUMPTION: template = drop phase of the median Facchinetti PISA at 5-min sampling, compared
# with first differences over the same span; Idi 2023 is retrospective (D7).
_MEDIAN = pisa_model.from_size(0.0, pisa_model.DEPTH.median, pisa_model.DURATION.median)
_DROP = _MEDIAN.attenuation(np.arange(0.0, _MEDIAN.pressure_min + 1e-9, 5.0))  # onset to nadir
TEMPLATE_DIFFS = -np.diff(_DROP)  # expected CGM changes per 5 min during the drop


def matched_filter_score(cgm: np.ndarray) -> np.ndarray:
    """Normalised correlation of recent CGM changes with the PISA drop, times its relative size.

    In [0, 1]: 0 = no PISA-like drop, 1 = a drop with the template's shape and at least its depth.
    """
    y = np.asarray(cgm, float)
    d = np.diff(y, prepend=np.nan)
    m = len(TEMPLATE_DIFFS)
    tmpl = TEMPLATE_DIFFS - TEMPLATE_DIFFS.mean()
    out = np.zeros(len(y))
    for i in range(m, len(y)):
        seg = d[i - m + 1 : i + 1]
        if np.isnan(seg).any():
            continue
        s = seg - seg.mean()
        denom = np.sqrt((s**2).sum() * (tmpl**2).sum())
        ncc = (s * tmpl).sum() / denom if denom > 0 else 0.0
        drop = -seg.sum()
        out[i] = max(0.0, ncc) * float(np.clip(drop / -TEMPLATE_DIFFS.sum(), 0.0, 1.0))
    return out


# ---------------------------------------------------------------- isolation forest (causal)


def trailing_features(times, cgm: np.ndarray) -> np.ndarray:
    """Five trailing-window features of the sensor state (Idi 2024 used five).

    rate over 10 min, minimum 10-min rate over the last 30 min, change in rate, drop from the
    trailing 60-min median, and the CGM itself.
    """
    # ASSUMPTION: which five features, and their windows (Idi 2024's own set is retrospective)
    y = np.asarray(cgm, float)
    s = pd.Series(y, index=pd.DatetimeIndex(times))
    rate = trailing_slope(times, y, 10.0, min_points=2)
    rate_s = pd.Series(rate, index=s.index)
    min_rate = rate_s.rolling("1830s", min_periods=1).min().to_numpy()
    change = rate - rate_s.shift(1).to_numpy()
    median = s.rolling("3630s", min_periods=3).median().to_numpy()
    return np.column_stack([rate, min_rate, change, y - median, y])


class IForestScorer:
    """Isolation forest fitted on training CGM features; gate = training ECDF of anomaly score."""

    def __init__(self, seed: int = 0, n_estimators: int = 200):
        self.seed, self.n_estimators = seed, n_estimators
        self.model = None
        self.reference = None

    def fit(self, feature_blocks: list[np.ndarray]) -> IForestScorer:
        from sklearn.ensemble import IsolationForest

        x = np.vstack(feature_blocks)
        x = x[~np.isnan(x).any(axis=1)]
        self.model = IsolationForest(n_estimators=self.n_estimators, random_state=self.seed).fit(x)
        self.reference = np.sort(-self.model.score_samples(x))
        return self

    def __call__(self, features: np.ndarray) -> np.ndarray:
        out = np.zeros(len(features))
        ok = ~np.isnan(features).any(axis=1)
        if ok.any():
            anomaly = -self.model.score_samples(features[ok])
            out[ok] = np.searchsorted(self.reference, anomaly, side="right") / len(self.reference)
        return out
