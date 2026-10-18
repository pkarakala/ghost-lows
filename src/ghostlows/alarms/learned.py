"""Gated alarms, the learned combiner for the context arms (D2), and the GBM alarm.

Training frames carry the alarm view (`time`, `cgm`, and for context arms `iob`, `cob`) plus a
`label` column computed by the benchmark from truth: 1 when a true level 1 low is ongoing or
starts within the next 30 min (`ghostlows.bench.events.low_labels`). Alarms never see truth.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseAlarm, runs, time_of_day_features, trailing_slope
from .detectors import (
    BAYSAL_DEFAULT,
    BAYSAL_SETS,
    IForestScorer,
    baysal_flags,
    matched_filter_score,
    trailing_features,
)
from .rules import TREND_TARGET_MG_DL, trend_prediction

ARMS = {"": (), "_time": ("time",), "_ctx": ("ctx",), "_time_ctx": ("time", "ctx")}


# ------------------------------------------------------------------ detectors (feature makers)


class Detector:
    """Causal per-sample features of one detector; `gate` is its PISA evidence in [0, 1]."""

    name = "detector"

    def fit(self, train: pd.DataFrame) -> None:
        return None

    def features(self, run: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError

    def gate(self, run: pd.DataFrame) -> np.ndarray:
        return np.zeros(len(run))


class ThresholdDetector(Detector):
    name = "threshold"

    def features(self, run):
        return run[["cgm"]].to_numpy(float)


class TrendDetector(Detector):
    name = "trend"

    def features(self, run):
        cgm = run["cgm"].to_numpy(float)
        return np.column_stack([cgm, trailing_slope(run["time"], cgm, 15.0), trend_prediction(run)])


class BaysalDetector(Detector):
    def __init__(self, params: str = BAYSAL_DEFAULT):
        self.params = BAYSAL_SETS[params]
        self.name = "baysal" if params == BAYSAL_DEFAULT else f"baysal_{params}"

    def gate(self, run):
        return baysal_flags(run["time"], run["cgm"].to_numpy(float), self.params)

    def features(self, run):
        return np.column_stack([trend_prediction(run), self.gate(run)])


class MatchedFilterDetector(Detector):
    name = "matched_filter_causal"

    def gate(self, run):
        return matched_filter_score(run["cgm"].to_numpy(float))

    def features(self, run):
        return np.column_stack([trend_prediction(run), self.gate(run)])


class IForestDetector(Detector):
    name = "iforest_causal"

    def __init__(self, seed: int = 0):
        self.scorer = IForestScorer(seed=seed)

    def fit(self, train):
        blocks = [trailing_features(r["time"], r["cgm"].to_numpy(float)) for _, r in runs(train)]
        self.scorer.fit(blocks)

    def gate(self, run):
        return self.scorer(trailing_features(run["time"], run["cgm"].to_numpy(float)))

    def features(self, run):
        return np.column_stack([trend_prediction(run), self.gate(run)])


DETECTORS = {
    "threshold": ThresholdDetector,
    "trend": TrendDetector,
    "baysal": BaysalDetector,
    "matched_filter_causal": MatchedFilterDetector,
    "iforest_causal": IForestDetector,
}


def arm_features(run: pd.DataFrame, arm: str) -> np.ndarray:
    parts = []
    if "time" in ARMS[arm]:
        parts.append(time_of_day_features(run["time"]))
    if "ctx" in ARMS[arm]:
        parts.append(run[["iob", "cob"]].to_numpy(float))
    return np.column_stack(parts) if parts else np.empty((len(run), 0))


# ------------------------------------------------------------------ as-published gated alarm


class GatedAlarm(BaseAlarm):
    """Trend alarm suppressed by a PISA detector, as published. Score = 1[trend] x (1 - gate)."""

    default_threshold = 0.0

    def __init__(self, detector: Detector):
        self.detector = detector
        self.name = f"{detector.name}_gate"

    def fit(self, train):
        self.detector.fit(train)

    def _score_run(self, run):
        trend_fires = trend_prediction(run) < TREND_TARGET_MG_DL
        return np.where(
            np.isnan(run["cgm"].to_numpy(float)),
            np.nan,
            trend_fires * (1 - self.detector.gate(run)),
        )


# ------------------------------------------------------------------ learned combiner (context arms)


class CombinedAlarm(BaseAlarm):
    """A detector's features plus the arm's inputs through one regularised logistic regression."""

    default_threshold = 0.5

    def __init__(self, detector: Detector, arm: str = "", seed: int = 0):
        if arm not in ARMS:
            raise ValueError(f"unknown arm {arm!r}")
        self.detector, self.arm, self.seed = detector, arm, seed
        self.name = f"{detector.name}_combined{arm}"
        self.uses_context = "ctx" in ARMS[arm]
        self.model = None

    def _x(self, run):
        return np.column_stack([self.detector.features(run), arm_features(run, self.arm)])

    def fit(self, train):
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        self.detector.fit(train)
        xs, ys = [], []
        for _, run in runs(train):
            ok = ~np.isnan(run["cgm"].to_numpy(float))
            xs.append(self._x(run)[ok])
            ys.append(run["label"].to_numpy()[ok])
        x, y = np.vstack(xs), np.concatenate(ys)
        if len(np.unique(y)) < 2:  # no lows in training: nothing to learn, never fires
            self.model = None
            return
        # Normalisation statistics come from training patients only (D14).
        self.model = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(C=1.0, max_iter=2000),  # ASSUMPTION: default L2 strength
        ).fit(x, y)

    def _score_run(self, run):
        if self.model is None:
            return np.where(np.isnan(run["cgm"].to_numpy(float)), np.nan, 0.0)
        p = self.model.predict_proba(self._x(run))[:, 1]
        return np.where(np.isnan(run["cgm"].to_numpy(float)), np.nan, p)


# ------------------------------------------------------------------ gradient boosting


def gbm_features(run: pd.DataFrame) -> np.ndarray:
    """Causal CGM features in the style of [Navarathna 2023] (ASSUMPTION: exact set)."""
    cgm = run["cgm"].to_numpy(float)
    s = pd.Series(cgm, index=pd.DatetimeIndex(run["time"]))
    slopes = [trailing_slope(run["time"], cgm, w) for w in (10.0, 20.0, 30.0, 60.0)]
    lags = [s.shift(k).to_numpy() for k in range(1, 7)]
    roll = s.rolling("3630s", min_periods=3)
    curvature = slopes[0] - pd.Series(slopes[0]).shift(1).to_numpy()
    return np.column_stack(
        [
            cgm,
            *slopes,
            curvature,
            *lags,
            roll.min().to_numpy(),
            roll.max().to_numpy(),
            roll.mean().to_numpy(),
        ]
    )


class GBMAlarm(BaseAlarm):
    """Gradient-boosted classifier predicting a true low within 30 min; arms add inputs."""

    default_threshold = 0.5

    def __init__(self, arm: str = "", seed: int = 0):
        self.arm, self.seed = arm, seed
        self.name = f"gbm{arm}"
        self.uses_context = "ctx" in ARMS[arm]
        self.model = None

    def _x(self, run):
        return np.column_stack([gbm_features(run), arm_features(run, self.arm)])

    def fit(self, train):
        from sklearn.ensemble import HistGradientBoostingClassifier

        xs, ys = [], []
        for _, run in runs(train):
            ok = ~np.isnan(run["cgm"].to_numpy(float))
            xs.append(self._x(run)[ok])
            ys.append(run["label"].to_numpy()[ok])
        x, y = np.vstack(xs), np.concatenate(ys)
        if len(np.unique(y)) < 2:  # no lows in training: nothing to learn, never fires
            self.model = None
            return
        # ASSUMPTION: library defaults with a fixed seed; no tuning on test patients
        self.model = HistGradientBoostingClassifier(random_state=self.seed).fit(x, y)

    def _score_run(self, run):
        if self.model is None:
            return np.where(np.isnan(run["cgm"].to_numpy(float)), np.nan, 0.0)
        p = self.model.predict_proba(self._x(run))[:, 1]
        return np.where(np.isnan(run["cgm"].to_numpy(float)), np.nan, p)
