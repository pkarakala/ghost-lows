"""A plug-in alarm in about 20 lines: score it with

    uv run ghostlows score --alarm examples/custom_alarm.py:FallingBelow70 \\
        --config experiments/configs/smoke.yaml

Subclass `BaseAlarm` and return one score per sample from `_score_run`, using only the `time` and
`cgm` columns (plus `iob`/`cob` if `uses_context = True`) at or before each sample. The alarm fires
where the score is above `default_threshold`; the urgent-low floor is added automatically.
"""

import numpy as np

from ghostlows.alarms import BaseAlarm


class FallingBelow70(BaseAlarm):
    """Fires when CGM is below 70 mg/dL and has fallen over the last 15 minutes."""

    name = "falling_below_70"
    default_threshold = 0.5

    def _score_run(self, run):
        cgm = run["cgm"].to_numpy(float)
        earlier = np.r_[np.full(3, np.nan), cgm[:-3]]  # value 15 min ago (5-min samples)
        return ((cgm < 70) & (cgm < earlier)).astype(float)
