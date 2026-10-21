"""FFT heart-rate estimation (reference implementation, 2026)."""
import numpy as np
import pytest

from ppg_sim import FrontEnd, Subject, heart_rate_fft

FS = 80.0


@pytest.mark.parametrize("bpm", [42, 60, 77, 100, 135, 175])
def test_pure_tone(bpm):
    t = np.arange(512) / FS
    x = np.sin(2 * np.pi * bpm / 60 * t)
    assert heart_rate_fft(x, FS).bpm == pytest.approx(bpm, abs=0.5)


def test_resolution_reported_for_unpadded_window():
    res = heart_rate_fft(np.random.default_rng(0).normal(size=512), FS)
    assert res.resolution_bpm == pytest.approx(60 * FS / 512)


def test_picks_fundamental_when_second_harmonic_is_larger():
    # A PPG's diastolic bump can make the 2nd harmonic the biggest peak
    t = np.arange(512) / FS
    f = 1.1
    x = 0.8 * np.sin(2 * np.pi * f * t) + 1.0 * np.sin(2 * np.pi * 2 * f * t)
    assert heart_rate_fft(x, FS).bpm == pytest.approx(66, abs=1.0)
    assert heart_rate_fft(x, FS, harmonic_check=False).bpm == pytest.approx(132, abs=1.0)


def test_ignores_breathing_and_out_of_band_content():
    t = np.arange(512) / FS
    x = (3.0 * np.sin(2 * np.pi * 0.25 * t)      # breathing, below the band
         + 0.5 * np.sin(2 * np.pi * 1.3 * t)     # heart, 78 bpm
         + 2.0 * np.sin(2 * np.pi * 9.0 * t))    # interference, above the band
    assert heart_rate_fft(x, FS).bpm == pytest.approx(78, abs=1.0)


@pytest.mark.parametrize("bpm", [40, 55, 72, 95, 130, 180])
def test_end_to_end_through_front_end(bpm):
    acq = FrontEnd().capture(Subject(heart_rate_bpm=bpm, seed=bpm), duration_s=6.4)
    assert acq.ac_ir.size == 512
    assert heart_rate_fft(acq.ac_ir, acq.fs).bpm == pytest.approx(bpm, abs=3.0)
