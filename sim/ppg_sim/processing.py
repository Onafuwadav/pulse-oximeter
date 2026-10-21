"""Heart rate (FFT) and SpO2 (ratio of ratios) from the demultiplexed samples.

Reference implementation written in 2026. Mirrors what the STM32 firmware did
with CMSIS-DSP (arm_rfft_fast_f32 + arm_cmplx_mag_f32 + arm_max_f32), written
in NumPy so it can be tested on a PC.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

from .physiology import spo2_from_r


@dataclass
class HeartRateResult:
    bpm: float
    peak_hz: float
    freqs: np.ndarray
    magnitude: np.ndarray
    resolution_bpm: float      # bin spacing of the un-padded FFT


@dataclass
class SpO2Result:
    spo2: float
    ratio: float
    ac_red: float
    dc_red: float
    ac_ir: float
    dc_ir: float


def heart_rate_fft(
    x: np.ndarray,
    fs: float,
    band_hz: tuple[float, float] = (0.6, 3.5),
    zero_pad: int = 8,
    interpolate: bool = True,
    harmonic_check: bool = True,
) -> HeartRateResult:
    """Heart rate from the dominant frequency of a PPG window.

    Steps: remove the mean, apply a Hann window, zero-pad to a power of two
    (CMSIS's real FFT needs one, 32..4096 points), take the magnitude, pick the
    largest bin inside the physiological band (36-210 bpm by default), refine
    the peak with a parabola through the three bins around it.

    The PPG is not a sinusoid: its diastolic bump puts a lot of energy at twice
    the heart rate. With ``harmonic_check`` on, if the bin at half the peak
    frequency (and inside the band) has at least half the peak's magnitude,
    the lower one is taken as the fundamental.
    """
    x = np.asarray(x, dtype=float)
    n = x.size
    nfft = 1 << int(np.ceil(np.log2(n * zero_pad)))
    w = np.hanning(n)
    spec = np.abs(np.fft.rfft((x - x.mean()) * w, nfft))
    freqs = np.fft.rfftfreq(nfft, 1.0 / fs)

    band = (freqs >= band_hz[0]) & (freqs <= band_hz[1])
    k = int(np.flatnonzero(band)[np.argmax(spec[band])])

    if harmonic_check:
        # look for a genuine peak near half the frequency, inside the band
        in_band = np.flatnonzero(band)
        k_half = int(round(k / 2))
        lo = max(k_half - zero_pad, int(in_band[0]))
        hi = min(k_half + zero_pad + 1, int(in_band[-1]) + 1)
        if hi - lo >= 3:
            k_sub = lo + int(np.argmax(spec[lo:hi]))
            is_peak = lo < k_sub < hi - 1 and spec[k_sub - 1] < spec[k_sub] > spec[k_sub + 1]
            if is_peak and spec[k_sub] >= 0.5 * spec[k]:
                k = k_sub

    f = freqs[k]
    if interpolate and 0 < k < spec.size - 1:
        y0, y1, y2 = np.log(spec[k - 1: k + 2] + 1e-300)
        denom = y0 - 2 * y1 + y2
        if denom != 0:
            f += 0.5 * (y0 - y2) / denom * (freqs[1] - freqs[0])

    return HeartRateResult(
        bpm=60.0 * f,
        peak_hz=f,
        freqs=freqs,
        magnitude=spec,
        resolution_bpm=60.0 * fs / n,
    )


def _ac_amplitude(x: np.ndarray, fs: float, method: str, bandpass: bool) -> float:
    x = np.asarray(x, dtype=float) - np.mean(x)
    if bandpass:
        sos = signal.butter(2, (0.5, 8.0), btype="bandpass", fs=fs, output="sos")
        x = signal.sosfiltfilt(sos, x)
    if method == "p2p":
        # robust peak-to-peak: ignore the most extreme 1 % at each end
        return float(np.percentile(x, 99) - np.percentile(x, 1))
    if method == "rms":
        return float(np.sqrt(np.mean(x**2)))
    raise ValueError(f"unknown method {method!r}")


def spo2_ratio_of_ratios(
    ac_red: np.ndarray,
    dc_red: np.ndarray,
    ac_ir: np.ndarray,
    dc_ir: np.ndarray,
    fs: float,
    ac_gain: float = 1.0,
    method: str = "rms",
    bandpass: bool = True,
) -> SpO2Result:
    """SpO2 from R = (AC_red / DC_red) / (AC_ir / DC_ir), SpO2 = 110 - 25 R.

    ``ac_*`` are AC-channel samples (after the second stage), ``dc_*`` are
    DC-channel samples (straight after the TIA). The AC amplitude is divided by
    the second-stage gain so that AC and DC are in the same units; the gain
    cancels in R anyway, as does the TIA gain. Any amplitude measure works as
    long as both wavelengths use the same one, because the two pulses have the
    same shape.
    """
    a_red = _ac_amplitude(ac_red, fs, method, bandpass) / ac_gain
    a_ir = _ac_amplitude(ac_ir, fs, method, bandpass) / ac_gain
    d_red = float(np.mean(dc_red))
    d_ir = float(np.mean(dc_ir))
    r = (a_red / d_red) / (a_ir / d_ir)
    return SpO2Result(
        spo2=float(np.clip(spo2_from_r(r), 0.0, 100.0)),
        ratio=float(r),
        ac_red=a_red,
        dc_red=d_red,
        ac_ir=a_ir,
        dc_ir=d_ir,
    )
