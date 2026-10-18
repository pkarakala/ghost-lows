"""Rule-based alarms: threshold and trend (BENCHMARK.md §2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseAlarm, trailing_slope

# SOURCE: IHSG 2017 (level 1 hypoglycaemia threshold, 70 mg/dL) CLINICAL-REVIEW: CR6
THRESHOLD_MG_DL = 70.0
# SOURCE: Garg 2022 (G7 Urgent Low Soon: predicted 55 mg/dL within 20 min) CLINICAL-REVIEW: CR14
TREND_TARGET_MG_DL = 55.0
TREND_HORIZON_MIN = 20.0
# ASSUMPTION: the stand-in fits a line to the last 15 min (4 readings at 5 min); the device's
# prediction model is not public (RESEARCH.md §6)
TREND_WINDOW_MIN = 15.0


def trend_prediction(run: pd.DataFrame, horizon_min: float = TREND_HORIZON_MIN) -> np.ndarray:
    """Linear extrapolation of the trailing-window fit `horizon_min` ahead (causal)."""
    cgm = run["cgm"].to_numpy(dtype=float)
    slope = trailing_slope(run["time"], cgm, TREND_WINDOW_MIN)
    return cgm + slope * horizon_min


class ThresholdAlarm(BaseAlarm):
    """Fires while CGM < 70 mg/dL. Score = -CGM, so the operating threshold is -70."""

    name = "threshold"
    default_threshold = -THRESHOLD_MG_DL

    def _score_run(self, run: pd.DataFrame) -> np.ndarray:
        return -run["cgm"].to_numpy(dtype=float)


class TrendAlarm(BaseAlarm):
    """Fires when the 20-min linear prediction is below 55 mg/dL. Score = -prediction."""

    name = "trend"
    default_threshold = -TREND_TARGET_MG_DL

    def _score_run(self, run: pd.DataFrame) -> np.ndarray:
        return -trend_prediction(run)


class FloorOnlyAlarm(BaseAlarm):
    """The ungated urgent-low floor alone (the 55 mg/dL threshold variant)."""

    name = "floor_only"
    default_threshold = np.inf

    def _score_run(self, run: pd.DataFrame) -> np.ndarray:
        return np.full(len(run), -np.inf)
