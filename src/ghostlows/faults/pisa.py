"""Compression artifacts (PISA) after Facchinetti 2016 (SIMULATION.md §4.1).

The artifact is "the output of a first-order linear dynamic system driven by a rectangular
function" [Facchinetti 2016]: an attenuation that rises as 1 - exp(-t/tau) while pressure is
applied for D minutes, then decays as exp(-(t - D)/tau). Each artifact is drawn so that its
*realised* depth (peak attenuation) and duration match a draw from the published distributions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

Z95 = 1.6448536269514722  # standard normal 95th percentile

# SOURCE: Facchinetti 2016 (median and 5th-95th percentiles of PISA duration and amplitude)
DURATION_MIN = (45.0, 30.0, 70.0)  # median, 5th, 95th percentile, minutes
DEPTH_MG_DL = (24.0, 10.0, 48.0)  # median, 5th, 95th percentile, mg/dL

# ASSUMPTION: time constant until the full text is read (SIMULATION.md §4.1); swept 5/10/20 min
TAU_MIN = 10.0
# ASSUMPTION: the artifact "lasts" from onset until the attenuation decays to 10% of its peak
END_FRACTION = 0.10
# ASSUMPTION: the tail below 1% of the peak is dropped
TAIL_FRACTION = 0.01


@dataclass(frozen=True)
class TwoPieceLogNormal:
    """Log-normal with different log-scale spreads below and above the median.

    Matches a published median and 5th/95th percentiles exactly, which a single log-normal cannot
    do when they are asymmetric in log space (depth: 0.88 below vs. 0.69 above). ASSUMPTION.
    """

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
DEPTH = TwoPieceLogNormal(*DEPTH_MG_DL)


@dataclass(frozen=True)
class Pisa:
    """One artifact: onset (minutes from the trace start), pressure length D, amplitude A, tau."""

    onset: float
    pressure_min: float
    amplitude: float
    tau: float = TAU_MIN

    @property
    def depth(self) -> float:
        return self.amplitude * (1 - np.exp(-self.pressure_min / self.tau))

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
        rise = self.amplitude * (1 - np.exp(-np.clip(t, 0, None) / self.tau))
        decay = self.depth * np.exp(-np.clip(t - self.pressure_min, 0, None) / self.tau)
        out = np.where(t <= self.pressure_min, rise, decay)
        return np.where((t < 0) | (t > self.length), 0.0, out)

    def active(self, minutes: np.ndarray) -> np.ndarray:
        """True from onset until the attenuation decays to END_FRACTION of the peak."""
        t = np.asarray(minutes, dtype=float) - self.onset
        return (t >= 0) & (t <= self.duration)


def from_size(onset: float, depth: float, duration: float, tau: float = TAU_MIN) -> Pisa:
    """The artifact whose realised depth and duration are the given values."""
    pressure = duration - tau * np.log(1 / END_FRACTION)
    if pressure <= 0:
        raise ValueError(f"duration {duration:.1f} min is too short for tau = {tau} min")
    return Pisa(onset, pressure, depth / (1 - np.exp(-pressure / tau)), tau)


def sample_sizes(
    rng: np.random.Generator, n: int, tau: float = TAU_MIN
) -> tuple[np.ndarray, np.ndarray]:
    """Depths and durations; durations too short for `tau` are redrawn (about 0.3% at tau=10)."""
    depth = DEPTH.sample(rng, n)
    duration = DURATION.sample(rng, n)
    floor = tau * np.log(1 / END_FRACTION) + 1.0
    while (short := duration < floor).any():
        duration[short] = DURATION.sample(rng, int(short.sum()))
    return depth, duration
