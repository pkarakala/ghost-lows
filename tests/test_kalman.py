"""The multiple-model Kalman alarm (RQ3, BENCHMARK.md §2): known answers on hand-built traces,
batching, missing readings, the ablation, and the RQ3 comparator selection. Causality is tested
with every other alarm in test_alarms.py."""

import numpy as np
import pandas as pd

from ghostlows.alarms import KalmanPisaAlarm, TrendAlarm, stretch_alarms
from ghostlows.alarms.kalman_pisa import KalmanParams, modes
from ghostlows.bench.analysis import discriminative_pool, select_comparators
from ghostlows.faults.pisa import from_size

TIMES = pd.date_range("2026-01-05 22:00", periods=48, freq="5min")
T = np.arange(48) * 5.0
NOISE = np.random.default_rng(0).normal(0, 3, 48)
FALL = np.clip(T - 60, 0, None) * 1.5  # -1.5 mg/dL/min from minute 60
IOB = np.where(T < 60, 3.0, np.clip(3.0 - 0.03 * (T - 60), 0, None))  # 0.03 U/min absorbed


def frame(cgm, pid="p", iob=0.0):
    return pd.DataFrame(
        {
            "patient_id": pid,
            "time": TIMES[: len(cgm)],
            "cgm": np.asarray(cgm, float),
            "iob": iob,
            "cob": 0.0,
        }
    )


def test_no_low_is_predicted_during_a_pisa_on_flat_glucose():
    df = frame(100 - from_size(60.0, 24.0, 45.0).attenuation(T) + NOISE)
    assert (TrendAlarm().score(df) > -55).any()  # the trend alarm predicts < 55 mg/dL
    for alarm in stretch_alarms():
        assert alarm.filter(df)["p_low"].max() < 0.2, alarm.name


def test_an_insulin_driven_fall_is_predicted_early_and_not_called_compression():
    df = frame(120 - FALL + NOISE, iob=IOB)
    out = KalmanPisaAlarm(True, params=KalmanParams(gain_insulin=50.0)).filter(df)
    first = np.flatnonzero(out["p_low"].to_numpy() > 0.5)[0]
    assert df["cgm"].iloc[first] > 75  # warned while the CGM was still well above 55
    assert out["p_pressure"].max() < 0.1


def test_a_sustained_fall_is_not_explained_away_as_compression_without_inputs():
    out = KalmanPisaAlarm(False).filter(frame(np.clip(120 - FALL, 40, None) + NOISE))
    assert out["p_pressure"].max() < 0.5
    assert out["p_low"].max() > 0.9


def test_batched_runs_do_not_mix_and_padding_is_harmless():
    a = frame(100 - from_size(60.0, 24.0, 45.0).attenuation(T) + NOISE, "a")
    b = frame((120 - FALL + NOISE)[:30], "b")  # shorter run: padded inside the batch
    alarm = KalmanPisaAlarm(False)
    both = alarm.score(pd.concat([a, b], ignore_index=True))
    np.testing.assert_allclose(both.iloc[:48].to_numpy(), alarm.score(a).to_numpy())
    np.testing.assert_allclose(both.iloc[48:].to_numpy(), alarm.score(b).to_numpy())


def test_missing_readings_have_no_score_and_the_filter_continues():
    cgm = 100 + NOISE
    cgm[:3] = np.nan  # the run starts without readings
    cgm[10:16] = np.nan  # a 30-min gap
    p_low = KalmanPisaAlarm(False).filter(frame(cgm))["p_low"]
    assert p_low.iloc[:3].isna().all() and p_low.iloc[10:16].isna().all()
    assert p_low.iloc[3:10].notna().all() and p_low.iloc[16:].notna().all()
    assert p_low.max() < 0.05


def test_the_ablation_has_no_compressed_state():
    names = {a.name: a for a in stretch_alarms()}
    assert set(names) == {"kalman_pisa", "kalman_pisa_cgm", "kalman_nopisa"}
    assert modes(names["kalman_pisa"].params)[0].any()
    assert not modes(names["kalman_nopisa"].params)[0].any()
    assert names["kalman_pisa"].uses_context and not names["kalman_pisa_cgm"].uses_context
    flat = frame(100 + NOISE)
    assert names["kalman_nopisa"].filter(flat)["p_pressure"].max() == 0.0


def test_comparator_is_chosen_on_training_results_only():
    pool = discriminative_pool(
        ["gbm", "gbm_ctx", "trend_combined_ctx", "trend_combined_time_ctx", "kalman_pisa"], "_ctx"
    )
    assert pool == ["gbm_ctx", "trend_combined_ctx"]
    thresholds = pd.DataFrame(
        {
            "mix": "default",
            "fold": [0, 0, 1, 1],
            "alarm_name": ["gbm_ctx", "trend_combined_ctx"] * 2,
            "feasible": [True, True, False, True],
            "train_false_per_day": [0.4, 0.6, 0.1, 0.5],
            "train_sens": [0.9, 0.9, 0.8, 0.9],
        }
    )
    chosen = select_comparators(thresholds, pool).set_index("fold")["comparator"]
    assert chosen[0] == "gbm_ctx"  # fewest training false alarms
    assert chosen[1] == "trend_combined_ctx"  # gbm_ctx missed the sensitivity constraint
