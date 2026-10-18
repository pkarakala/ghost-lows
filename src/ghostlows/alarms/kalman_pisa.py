"""`kalman_pisa`: a multiple-model Kalman filter with an explicit compressed state (RQ3,
BENCHMARK.md §2).

Precedents: real-time failure alerts from Kalman predictions of an individual CGM and insulin
model [Facchinetti 2013]; CGM fault detection with a glucose, insulin and meal model and an
unscented Kalman filter [Turksoy 2017]; Kalman filters for CGM fault and meal detection
[Mahmoudi 2017]. The compressed state follows the PISA model of [Facchinetti 2016], a first-order
response to a rectangular pressure input. Sensor error is autocorrelated, not white
[Breton 2008]. Combining these in an interacting multiple model filter is this project's design.

Per run, causally, the filter tracks

    g  artifact-free interstitial glucose (mg/dL)
    r  glucose rate the inputs do not explain (mg/dL/min), a damped random walk
    c  compression artifact (mg/dL): first-order towards -a under pressure, back to 0 after
    a  pressure amplitude (mg/dL): constant under pressure, drawn afresh from its prior otherwise
    n  autocorrelated sensor error (mg/dL), first-order towards 0

in three modes that switch as a Markov chain: steady, manoeuvre (the rate may change quickly,
as after a meal, an insulin peak or exercise) and pressure. The CGM reads g + c + n plus white
noise. With inputs (`kalman_pisa`), g also moves by the insulin and carbohydrate absorbed since
the previous sample (the fall in recorded IOB and COB) times gains fitted on training patients;
`kalman_pisa_cgm` has no inputs. The noise settings are chosen on training patients by how well
the score ranks upcoming lows (average precision), because maximum likelihood cannot separate a
smooth sensor error from glucose and picks an agile filter that tracks compression as glucose
(BENCHMARK.md §2).

Score: the probability, under the filter's mixture of modes, that artifact-free glucose is below
55 mg/dL 20 min ahead, the target of the trend alarm.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy.special import ndtr

from ..faults import pisa as pisa_model
from ..faults.calibrate import TARGET_PER_HOUR
from .base import BaseAlarm, minutes, runs
from .rules import TREND_HORIZON_MIN, TREND_TARGET_MG_DL

# SOURCE: Facchinetti 2016 (first-order response to a rectangular pressure input; median size)
_MEDIAN = pisa_model.from_size(0.0, pisa_model.DEPTH.median, pisa_model.DURATION.median)
_AMP_P5 = pisa_model.from_size(0.0, pisa_model.DEPTH.p5, pisa_model.DURATION.median).amplitude
_AMP_P95 = pisa_model.from_size(0.0, pisa_model.DEPTH.p95, pisa_model.DURATION.median).amplitude

G, R, C, A, N = range(5)  # state indices
# ASSUMPTION: grid for the noise settings (BENCHMARK.md §2); a sensor error variance of 0 is the
# white-noise model, so the grid nests it
TUNE_GRID = {
    "obs_var": (4.0, 16.0),  # (mg/dL)^2
    "rate_var": (1e-4, 3e-4, 1e-3),  # (mg/dL/min)^2 per min
    "noise_var": (0.0, 100.0, 225.0, 400.0),  # (mg/dL)^2
    "noise_tau_min": (20.0, 40.0, 60.0),
}
TUNE_RUNS = 16  # ASSUMPTION: training runs used to choose the noise settings (evenly chosen)


@dataclass(frozen=True)
class KalmanParams:
    """Filter settings. `fit` chooses the noise settings and estimates the input gains on
    training patients; the pressure mode comes from the PISA model and the literature."""

    obs_var: float = 16.0  # white sensor noise, (mg/dL)^2; tuned
    rate_var: float = 3e-4  # (mg/dL/min)^2 per min in the steady mode; tuned
    noise_var: float = 100.0  # autocorrelated sensor error, (mg/dL)^2; tuned
    noise_tau_min: float = 20.0  # its time constant; tuned
    # ASSUMPTION: small level noise, so that real changes go through the rate state
    level_var: float = 0.1  # (mg/dL)^2 per min
    # ASSUMPTION: the unexplained rate decays slowly (240-min time constant)
    rate_tau_min: float = 240.0
    # ASSUMPTION: the generator's time constant and the amplitude of its median PISA, with the
    # spread of amplitudes between the 5th and 95th percentile depths (faults/pisa.py)
    artifact_tau_min: float = pisa_model.TAU_MIN
    amp_mean: float = _MEDIAN.amplitude
    amp_sd: float = (_AMP_P95 - _AMP_P5) / (2 * pisa_model.Z95)
    # ASSUMPTION: the amplitude is constant while pressure lasts (the model's rectangular input);
    # the artifact may deviate a little from the first-order shape (tolerates shape mismatch)
    amp_var: float = 0.0  # (mg/dL)^2 per min
    artifact_var: float = 0.5  # (mg/dL)^2 per min
    pressure_mode: bool = True  # False: the ablation without a compressed state
    # SOURCE: Lobo 2026 (pooled abstract counts: about one PISA per 74.8 h of wear)
    onset_per_min: float = TARGET_PER_HOUR / 60.0
    # ASSUMPTION: mean pressure time = that of the median PISA under the realised-size mapping
    release_per_min: float = 1.0 / _MEDIAN.pressure_min
    # ASSUMPTION: in the manoeuvre mode the rate variance is 30 times the steady one; the mode is
    # entered about every 2 h and left after about 20 min. 0 disables the mode.
    manoeuvre_factor: float = 30.0
    manoeuvre_onset_per_min: float = 1.0 / 120.0
    manoeuvre_end_per_min: float = 1.0 / 20.0
    gain_insulin: float = 0.0  # mg/dL per U absorbed; fitted
    gain_carb: float = 0.0  # mg/dL per g absorbed; fitted
    target: float = TREND_TARGET_MG_DL
    horizon_min: float = TREND_HORIZON_MIN


def absorbed(on_board: np.ndarray, dt: np.ndarray) -> np.ndarray:
    """Amount absorbed per minute since the previous sample: the fall in insulin or carbohydrate
    on board. A rise is a new bolus or meal and counts as nothing absorbed. Causal."""
    x = np.nan_to_num(np.asarray(on_board, float))
    return np.maximum(0.0, -np.diff(x, prepend=x[:1])) / dt


def stack(df: pd.DataFrame, inputs: bool):
    """Runs side by side, padded to the longest: CGM (NaN when missing and as padding), minutes
    since the previous sample, and insulin and carbohydrate absorbed per minute."""
    groups = [run for _, run in runs(df)]
    n, length = len(groups), max(len(run) for run in groups)
    y = np.full((n, length), np.nan)
    dt = np.full((n, length), 5.0)
    ins, carb = np.zeros((n, length)), np.zeros((n, length))
    for i, run in enumerate(groups):
        m = len(run)
        y[i, :m] = run["cgm"].to_numpy(float)
        dt[i, 1:m] = np.maximum(np.diff(minutes(run["time"])), 0.5)  # repeated times
        if inputs:
            ins[i, :m] = absorbed(run["iob"].to_numpy(float), dt[i, :m])
            carb[i, :m] = absorbed(run["cob"].to_numpy(float), dt[i, :m])
    return groups, y, dt, ins, carb


def fit_gains(y, dt, ins, carb) -> tuple[float, float]:
    """(insulin, carbohydrate) gains: non-negative least squares of the CGM rate on carbohydrate
    and minus insulin absorbed."""
    from scipy.optimize import nnls

    rate = np.diff(y, axis=1) / dt[:, 1:]
    x = np.stack([carb[:, 1:], -ins[:, 1:]], axis=-1)
    ok = np.isfinite(rate) & (x != 0).any(axis=-1)
    if ok.sum() < 10:
        return 0.0, 0.0
    coef, _ = nnls(x[ok], rate[ok])
    return float(coef[1]), float(coef[0])


def modes(p: KalmanParams):
    """Pressure flag, rate-variance multiplier and per-minute switching rates of each mode:
    steady (0), manoeuvre (1, if enabled), pressure (last, if enabled). Pressure starts from
    either no-pressure mode and ends into the steady mode."""
    manoeuvre = p.manoeuvre_factor > 0
    pressure = np.array([False] * (1 + manoeuvre) + [True] * p.pressure_mode)
    factor = np.ones(len(pressure))
    rates = np.zeros((len(pressure), len(pressure)))
    if p.pressure_mode:
        rates[:-1, -1] = p.onset_per_min
        rates[-1, 0] = p.release_per_min
    if manoeuvre:
        factor[1] = p.manoeuvre_factor
        rates[0, 1], rates[1, 0] = p.manoeuvre_onset_per_min, p.manoeuvre_end_per_min
    return pressure, factor, rates


def _first_observed(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Index and value of each run's first reading (100 mg/dL for a run with none)."""
    first = np.isfinite(y).argmax(axis=1)
    value = y[np.arange(len(y)), first]
    return first, np.where(np.isfinite(value), value, 100.0)


def imm_filter(y, dt, u, p: KalmanParams, per_run: dict | None = None):
    """Interacting multiple model filter over all runs at once.

    Returns (p_low, p_pressure), shaped like `y`, NaN where the CGM is missing or before a run's
    first reading. Every output at step k uses only y, dt and u up to step k. `per_run` may give
    obs_var, rate_var, noise_var or noise_tau_min per run (to try many settings in one pass).
    """
    pressure, factor, rates = modes(p)
    m_count, (n, length) = len(pressure), y.shape
    per_run = per_run or {}

    def setting(name):
        return np.broadcast_to(np.asarray(per_run.get(name, getattr(p, name)), float), (n,))

    obs_var, rate_var = setting("obs_var"), setting("rate_var")
    noise_var, noise_tau = setting("noise_var"), setting("noise_tau_min")
    mode_rate = factor[:, None] * rate_var[None, :]  # (modes, runs)
    first, start = _first_observed(y)
    p_low, p_pressure = np.full((n, length), np.nan), np.full((n, length), np.nan)
    x = np.zeros((m_count, n, 5))
    x[:, :, G], x[:, :, A] = start, p.amp_mean
    cov = np.zeros((m_count, n, 5, 5))
    # ASSUMPTION: initial uncertainty of glucose, rate and artifact at a run's first reading
    cov[:, :, G, G] = obs_var + 100.0
    cov[:, :, R, R], cov[:, :, C, C], cov[:, :, A, A] = 0.25, 1.0, p.amp_sd**2
    cov[:, :, N, N] = noise_var
    mu = np.full((m_count, n), 1e-6)
    mu[0] = 1 - 1e-6 * (m_count - 1)
    h_gain = p.rate_tau_min * (1 - np.exp(-p.horizon_min / p.rate_tau_min))
    h_var = p.level_var * p.horizon_min + mode_rate * p.horizon_min**3 / 3
    off = ~np.eye(m_count, dtype=bool)
    diag = np.arange(m_count)
    for k in range(length):
        live = k > first
        d = np.where(live, dt[:, k], 0.0)
        # ---- mixing (Markov switching between modes)
        trans = np.where(off[..., None], 1 - np.exp(-rates[..., None] * d), 0.0)
        trans[diag, diag] = 1 - trans.sum(axis=1)
        cbar = np.einsum("in,ijn->jn", mu, trans)
        w = mu[:, None, :] * trans / np.maximum(cbar[None, :, :], 1e-300)
        x0 = np.einsum("ijn,ins->jns", w, x)
        dx = x[:, None] - x0[None]
        c0 = np.einsum("ijn,inrs->jnrs", w, cov) + np.einsum("ijn,ijnr,ijns->jnrs", w, dx, dx)
        # ---- prediction per mode
        e_r = np.exp(-d / p.rate_tau_min)
        alpha = np.exp(-d / p.artifact_tau_min)
        e_n = np.exp(-d / noise_tau)
        f = np.zeros((m_count, n, 5, 5))
        f[:, :, G, G] = 1.0
        f[:, :, G, R] = p.rate_tau_min * (1 - e_r)
        f[:, :, R, R] = e_r
        f[:, :, C, C] = alpha
        f[pressure, :, C, A] = -(1 - alpha)
        f[pressure, :, A, A] = 1.0
        f[:, :, N, N] = e_n
        b = np.zeros((m_count, n, 5))
        b[:, :, G] = d * u[:, k]
        b[~pressure, :, A] = p.amp_mean
        q = np.zeros((m_count, n, 5, 5))
        q[:, :, G, G] = p.level_var * d
        q[:, :, R, R] = mode_rate * d
        q[pressure, :, C, C] = p.artifact_var * d
        q[~pressure, :, A, A] = p.amp_sd**2
        q[pressure, :, A, A] = p.amp_var * d
        q[:, :, N, N] = noise_var * (1 - e_n**2)
        xp = np.einsum("mnrs,mns->mnr", f, x0) + b
        cp = f @ c0 @ np.swapaxes(f, -1, -2) + q
        # ---- update with the reading (the CGM reads g + c + n); none at a run's first reading
        yk = y[:, k]
        upd = live & np.isfinite(yk)
        pht = cp[..., :, G] + cp[..., :, C] + cp[..., :, N]
        s = pht[..., G] + pht[..., C] + pht[..., N] + obs_var
        nu = np.where(upd, yk - xp[..., G] - xp[..., C] - xp[..., N], 0.0)
        gain = pht / s[..., None]
        x = xp + gain * nu[..., None]
        cov = cp - np.where(upd[None, :, None, None], gain[..., :, None] * pht[..., None, :], 0.0)
        cov = 0.5 * (cov + np.swapaxes(cov, -1, -2))
        loglik = np.where(upd, -0.5 * (np.log(2 * np.pi * s) + nu * nu / s), 0.0)
        logmu = np.log(np.maximum(cbar, 1e-300)) + loglik
        mu = np.exp(logmu - logmu.max(axis=0))
        mu /= mu.sum(axis=0)
        # ---- outputs: P(artifact-free glucose < target at the horizon), P(pressure)
        mean = x[..., G] + h_gain * x[..., R] + p.horizon_min * u[:, k]
        var = cov[..., G, G] + 2 * h_gain * cov[..., G, R] + h_gain**2 * cov[..., R, R] + h_var
        z = (p.target - mean) / np.sqrt(np.maximum(var, 1e-6))
        seen = np.isfinite(yk) & (k >= first)
        p_low[seen, k] = (mu * ndtr(z)).sum(axis=0)[seen]
        p_pressure[seen, k] = mu[pressure].sum(axis=0)[seen]
    return p_low, p_pressure


def tune_noise(y, dt, u, labels, p: KalmanParams, max_runs: int = TUNE_RUNS) -> dict:
    """The TUNE_GRID point whose score best ranks the training label (average precision), on up
    to `max_runs` evenly chosen training runs, every grid point in one vectorised pass. Returns
    {} (keep the defaults) when those runs have no positive label."""
    from sklearn.metrics import average_precision_score

    keep = np.unique(np.linspace(0, len(y) - 1, min(len(y), max_runs)).astype(int))
    lab = labels[keep]
    if not np.nansum(lab) > 0:
        return {}
    names = list(TUNE_GRID)
    grid = np.array(list(itertools.product(*TUNE_GRID.values())))
    reps = len(grid)
    per_run = {name: np.tile(grid[:, i], len(keep)) for i, name in enumerate(names)}
    p_low, _ = imm_filter(
        np.repeat(y[keep], reps, axis=0),
        np.repeat(dt[keep], reps, axis=0),
        np.repeat(u[keep], reps, axis=0),
        p,
        per_run,
    )
    p_low = p_low.reshape(len(keep), reps, -1)
    ap = []
    for j in range(reps):
        score = p_low[:, j]
        ok = np.isfinite(score) & np.isfinite(lab)
        ap.append(average_precision_score(lab[ok], score[ok]))
    best = grid[int(np.argmax(ap))]
    return {name: float(v) for name, v in zip(names, best, strict=True)}


class KalmanPisaAlarm(BaseAlarm):
    """Multiple-model Kalman filter alarm. `inputs=False` gives the CGM-only `kalman_pisa_cgm`;
    `pressure=False` drops the compressed state (`kalman_nopisa`, an ablation).

    Fitted on training patients (input gains by non-negative least squares, noise settings by
    the average precision of the score for the training label); its threshold is chosen by the
    operating-point rule (D5).
    """

    learned = True
    default_threshold = 0.5  # ASSUMPTION: untuned default; the benchmark tunes it (D5)

    def __init__(
        self, inputs: bool = True, pressure: bool = True, params: KalmanParams | None = None
    ):
        self.inputs = inputs
        self.uses_context = inputs
        self.name = ("kalman_pisa" if pressure else "kalman_nopisa") + ("" if inputs else "_cgm")
        self.params = replace(params or KalmanParams(), pressure_mode=pressure)

    def _u(self, ins, carb):
        return self.params.gain_carb * carb - self.params.gain_insulin * ins

    def fit(self, train: pd.DataFrame) -> None:
        groups, y, dt, ins, carb = stack(train, self.inputs)
        if self.inputs:
            g_ins, g_carb = fit_gains(y, dt, ins, carb)
            self.params = replace(self.params, gain_insulin=g_ins, gain_carb=g_carb)
        labels = np.full(y.shape, np.nan)
        for i, run in enumerate(groups):
            labels[i, : len(run)] = run["label"].to_numpy(float)
        tuned = tune_noise(y, dt, self._u(ins, carb), labels, self.params)
        self.params = replace(self.params, **tuned)

    def filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """Per sample: `p_low` (the score) and `p_pressure` (probability of the pressure mode)."""
        out = pd.DataFrame(np.nan, index=df.index, columns=["p_low", "p_pressure"])
        if df.empty:
            return out
        groups, y, dt, ins, carb = stack(df, self.inputs)
        p_low, p_pressure = imm_filter(y, dt, self._u(ins, carb), self.params)
        for i, run in enumerate(groups):
            out.loc[run.index, "p_low"] = p_low[i, : len(run)]
            out.loc[run.index, "p_pressure"] = p_pressure[i, : len(run)]
        return out

    def score(self, df: pd.DataFrame) -> pd.Series:
        return self.filter(df)["p_low"]
