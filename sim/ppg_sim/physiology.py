"""Synthetic finger PPG: pulse shape, heart rate, perfusion and SpO2.

Reference implementation written in 2026.

The model is deliberately simple. Light through the finger has a large steady
part (tissue, venous blood, bone) and a small part that rises and falls with
each heartbeat (arterial blood). For each wavelength

    I(t) = I0 * (1 + wander(t)) * (1 - PI * p(t))

where p(t) is a 0..1 pulse waveform and PI (the perfusion index, AC/DC) is a
few percent. Oxygenated and deoxygenated haemoglobin absorb red and infrared
light differently, so the red and IR perfusion indices differ; their ratio is
the "ratio of ratios" R used by the empirical calibration

    SpO2 = 110 - 25 R

from the module notes. To generate a subject with a chosen SpO2 we invert that
calibration and set PI_red = R * PI_ir.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def spo2_from_r(r: float | np.ndarray) -> float | np.ndarray:
    """Linear calibration used in the module: SpO2 [%] = 110 - 25 R."""
    return 110.0 - 25.0 * r


def r_from_spo2(spo2: float | np.ndarray) -> float | np.ndarray:
    """Inverse of :func:`spo2_from_r`."""
    return (110.0 - spo2) / 25.0


def ppg_pulse(phase: np.ndarray) -> np.ndarray:
    """One-beat PPG shape as a function of beat phase (0..1, wraps).

    A systolic peak followed by a smaller diastolic (reflected-wave) bump, the
    shape seen in the module's example red/IR traces. Normalised to 0..1.
    """
    ph = np.mod(phase, 1.0)

    def bump(centre: float, width: float) -> np.ndarray:
        # wrapped Gaussian so the waveform is smooth across beat boundaries
        d = np.minimum(np.abs(ph - centre), 1.0 - np.abs(ph - centre))
        return np.exp(-0.5 * (d / width) ** 2)

    y = bump(0.18, 0.07) + 0.45 * bump(0.48, 0.09)
    return (y - y.min()) / (y.max() - y.min()) if y.size > 1 else y


@dataclass(frozen=True)
class Subject:
    """Physiological parameters of the simulated finger."""

    heart_rate_bpm: float = 72.0
    spo2: float = 97.0              # % - sets R through the calibration line
    perfusion_ir: float = 0.02      # IR AC/DC (2 % is typical for a fingertip)
    resp_rate_bpm: float = 15.0     # breathing modulates the baseline
    baseline_wander: float = 0.005  # fractional baseline change from breathing
    hrv: float = 0.03               # beat-to-beat rate variation (fraction)
    seed: int = 0

    @property
    def ratio(self) -> float:
        return float(r_from_spo2(self.spo2))

    @property
    def perfusion_red(self) -> float:
        return self.ratio * self.perfusion_ir

    def beat_phase(self, t: np.ndarray) -> np.ndarray:
        """Cumulative beat phase (in beats) with slow random rate variation."""
        rng = np.random.default_rng(self.seed)
        f0 = self.heart_rate_bpm / 60.0
        # slowly varying instantaneous rate: a few random low-frequency sines
        mod = np.zeros_like(t)
        for _ in range(3):
            fm = rng.uniform(0.05, 0.3)
            mod += np.sin(2 * np.pi * fm * t + rng.uniform(0, 2 * np.pi))
        f_inst = f0 * (1.0 + self.hrv * mod / 3.0)
        dt = np.diff(t, prepend=t[0])
        return np.cumsum(f_inst * dt)

    def transmission(self, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Relative light transmitted (red, ir) at times t; 1.0 = no pulse."""
        p = ppg_pulse(self.beat_phase(t))
        wander = 1.0 + self.baseline_wander * np.sin(2 * np.pi * self.resp_rate_bpm / 60.0 * t)
        red = wander * (1.0 - self.perfusion_red * p)
        ir = wander * (1.0 - self.perfusion_ir * p)
        return red, ir
