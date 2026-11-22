"""Compression artifacts (PISA) after Facchinetti 2016 (SIMULATION.md §4.1).

The artifact is "the output of a first-order linear dynamic system driven by a rectangular
function" with transfer function G(s) = P/(1 + s*tau) [Facchinetti 2016, Eq. 6]: an attenuation
that rises as P(1 - exp(-t/tau)) while pressure is applied for D minutes, then decays as
exp(-(t - D)/tau). The paper's names are kept: P is the gain (mg/dL), D the pressure duration,
tau the time constant, and A = (1 - exp(-D/tau))P the peak deviation [Eq. 7].

Two ways to draw an artifact:
- `sample_sizes` + `from_size` (the default): A and the observed duration follow the paper's
  reported percentiles, and tau is fixed. P and D follow from Eq. 7.
- `sample_parameters` (robustness arm): P, D and tau are drawn from the paper's fitted parameter
  distributions, with their published correlations, so tau varies per event.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

Z95 = 1.6448536269514722  # standard normal 95th percentile

# SOURCE: Facchinetti 2016 (median and 5th-95th percentiles of the observed artifact's duration
# and amplitude, abstract and p.268; the amplitude is the peak deviation A)
# CLINICAL-REVIEW: CR2 (Dexcom G4 Platinum on the abdomen; do they hold for G6/G7?)
DURATION_MIN = (45.0, 30.0, 70.0)  # median, 5th, 95th percentile, minutes
PEAK_MG_DL = (24.0, 10.0, 48.0)  # A: median, 5th, 95th percentile, mg/dL

# SOURCE: Facchinetti 2016 (Fig. 8 right, p.270: tau median 9.1 min, 5th-95th 3.9-21.7)
TAU_MIN = 9.1
TAU_PERCENTILES = (9.1, 3.9, 21.7)  # median, 5th, 95th percentile, minutes
# ASSUMPTION: the artifact "lasts" from onset until the attenuation decays to 10% of its peak.
# Checked (DECISIONS.md A14): with P, D and tau drawn from the paper's Fig. 8 percentiles, this end
# gives an observed duration of median 47 min (5th-95th 30-76) against the published 45 (30-70).
END_FRACTION = 0.10
# ASSUMPTION: the tail below 1% of the peak is dropped
TAIL_FRACTION = 0.01


@dataclass(frozen=True)
class TwoPieceLogNormal:
    """Log-normal with different log-scale spreads below and above the median.

    Matches a published median and 5th/95th percentiles exactly, which a single log-normal cannot
    do when they are asymmetric in log space (A: 0.88 below vs. 0.69 above).
    """

    # ASSUMPTION: a two-piece log-normal fits the published median and 5th/95th percentiles
    median: float
    p5: float
    p95: float

    @property
    def sigma_low(self) -> float:
        return (np.log(self.median) - np.log(self.p5)) / Z95

    @property
    def sigma_high(self) -> float:
        return (np.log(self.p95) - np.log(self.median)) / Z95

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        z = rng.standard_normal(n)
        sigma = np.where(z < 0, self.sigma_low, self.sigma_high)
        return self.median * np.exp(sigma * z)

    def quantile(self, q: float) -> float:
        from statistics import NormalDist

        z = NormalDist().inv_cdf(q)
        return float(self.median * np.exp((self.sigma_low if z < 0 else self.sigma_high) * z))


DURATION = TwoPieceLogNormal(*DURATION_MIN)
PEAK = TwoPieceLogNormal(*PEAK_MG_DL)

# SOURCE: Facchinetti 2016 (p.270: P and D log-normal, P mu = 3.17, sigma = 0.57; D mu = 3.19,
# sigma = 0.42; tau "beta (a = 2.35, b = 4.81)", tested against a gamma distribution)
GAIN_LOG = (3.17, 0.57)  # log-normal (mu, sigma) of P, mg/dL
PRESSURE_LOG = (3.19, 0.42)  # log-normal (mu, sigma) of D, minutes
# ASSUMPTION: "beta" is a typo for gamma(shape 2.35, scale 4.81 min). A beta lives on [0, 1]
# (median 0.31 min); the gamma has median 9.7 min, near the reported 9.1, and the paper's own
# goodness-of-fit test is against a gamma distribution.
TAU_GAMMA = (2.35, 4.81)  # shape, scale (minutes)
# SOURCE: Facchinetti 2016 (p.270: r(P, tau) = -0.54, r(P, D) = 0.2, r(D, tau) = -0.18)
PARAMETER_CORRELATION = {("P", "tau"): -0.54, ("P", "D"): 0.20, ("D", "tau"): -0.18}
# Derived: Gaussian-copula correlations that give the published Pearson r on the fitted margins
# (solved by quadrature; tests/test_faults.py checks the realised r). Order P, D, tau.
_LATENT_CORRELATION = np.array(
    [[1.0, 0.2214, -0.6686], [0.2214, 1.0, -0.2007], [-0.6686, -0.2007, 1.0]]
)
_LATENT_CHOLESKY = np.linalg.cholesky(_LATENT_CORRELATION)


@dataclass(frozen=True)
class Pisa:
    """One artifact: onset (minutes from the trace start), pressure duration D, gain P, tau."""

    onset: float
    pressure_min: float  # D
    gain: float  # P, mg/dL
    tau: float = TAU_MIN

    @property
    def peak(self) -> float:
        """A = (1 - exp(-D/tau)) P, the largest deviation [Facchinetti 2016, Eq. 7]."""
        return self.gain * (1 - np.exp(-self.pressure_min / self.tau))

    @property
    def duration(self) -> float:
        return self.pressure_min + self.tau * np.log(1 / END_FRACTION)

    @property
    def length(self) -> float:
        """Minutes from onset until the attenuation drops below TAIL_FRACTION of the peak."""
        return self.pressure_min + self.tau * np.log(1 / TAIL_FRACTION)

    def attenuation(self, minutes: np.ndarray) -> np.ndarray:
        """mg/dL subtracted from the clean CGM at each time (minutes from the trace start)."""
        t = np.asarray(minutes, dtype=float) - self.onset
        rise = self.gain * (1 - np.exp(-np.clip(t, 0, None) / self.tau))
        decay = self.peak * np.exp(-np.clip(t - self.pressure_min, 0, None) / self.tau)
        out = np.where(t <= self.pressure_min, rise, decay)
        return np.where((t < 0) | (t > self.length), 0.0, out)

    def active(self, minutes: np.ndarray) -> np.ndarray:
        """True from onset until the attenuation decays to END_FRACTION of the peak."""
        t = np.asarray(minutes, dtype=float) - self.onset
        return (t >= 0) & (t <= self.duration)


def from_size(onset: float, peak: float, duration: float, tau: float = TAU_MIN) -> Pisa:
    """The artifact whose realised peak deviation A and duration are the given values.

    D = duration - tau ln(1/END_FRACTION); P = A / (1 - exp(-D/tau)) [Facchinetti 2016, Eq. 7].
    """
    pressure = duration - tau * np.log(1 / END_FRACTION)
    if pressure <= 0:
        raise ValueError(f"duration {duration:.1f} min is too short for tau = {tau} min")
    return Pisa(onset, pressure, peak / (1 - np.exp(-pressure / tau)), tau)


def sample_sizes(
    rng: np.random.Generator, n: int, tau: float = TAU_MIN
) -> tuple[np.ndarray, np.ndarray]:
    """Peak deviations A and durations; durations too short for `tau` are redrawn: about 0.2% at
    tau = 9.1, 57% at tau = 20, where the redraw raises the median duration from 45 to 55 min."""
    peak = PEAK.sample(rng, n)
    duration = DURATION.sample(rng, n)
    floor = tau * np.log(1 / END_FRACTION) + 1.0
    while (short := duration < floor).any():
        duration[short] = DURATION.sample(rng, int(short.sum()))
    return peak, duration


def sample_parameters(
    rng: np.random.Generator, n: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """P (mg/dL), D (min) and tau (min) from the paper's fitted distributions, correlated.

    Margins: log-normal P and D, gamma tau (TAU_GAMMA); a Gaussian copula gives the published
    pairwise correlations. Nothing is redrawn, so durations are whatever the parameters imply.
    """
    z = rng.standard_normal((n, 3)) @ _LATENT_CHOLESKY.T
    gain = np.exp(GAIN_LOG[0] + GAIN_LOG[1] * z[:, 0])
    pressure = np.exp(PRESSURE_LOG[0] + PRESSURE_LOG[1] * z[:, 1])
    u = 0.5 * (1 + np.vectorize(math.erf)(z[:, 2] / math.sqrt(2)))  # standard normal CDF
    tau = TAU_GAMMA[1] * gamma_ppf(u, TAU_GAMMA[0])
    return gain, pressure, np.maximum(tau, 0.1)  # ASSUMPTION: tau floor 0.1 min (numerics only)


def gamma_cdf(x: np.ndarray, shape: float, terms: int = 200) -> np.ndarray:
    """Regularised lower incomplete gamma P(shape, x), by its power series (numpy only, so the
    module stays importable in the browser app, which has no scipy)."""
    x = np.asarray(x, float)
    term = np.ones_like(x) / shape
    total = term.copy()
    for k in range(1, terms):
        term = term * x / (shape + k)
        total = total + term
    log_front = shape * np.log(np.maximum(x, 1e-300)) - x - math.lgamma(shape)
    return np.where(x > 0, np.clip(total * np.exp(log_front), 0.0, 1.0), 0.0)


def gamma_ppf(u: np.ndarray, shape: float) -> np.ndarray:
    """Quantile of a unit-scale gamma by bisection (60 halvings; error far below 1e-6)."""
    u = np.asarray(u, float)
    lo, hi = np.zeros_like(u), np.full_like(u, shape + 40 * math.sqrt(shape) + 40)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        below = gamma_cdf(mid, shape) < u
        lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
    return 0.5 * (lo + hi)
