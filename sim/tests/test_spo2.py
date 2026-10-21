"""Ratio-of-ratios SpO2 (reference implementation, 2026)."""
import numpy as np
import pytest

from ppg_sim import (
    FrontEnd,
    FrontEndConfig,
    Subject,
    r_from_spo2,
    spo2_from_r,
    spo2_ratio_of_ratios,
)

FS = 80.0


def test_calibration_line():
    assert spo2_from_r(0.4) == pytest.approx(100.0)
    assert spo2_from_r(1.0) == pytest.approx(85.0)
    for s in (80, 90, 97, 100):
        assert spo2_from_r(r_from_spo2(s)) == pytest.approx(s)


def test_ratio_of_ratios_on_ideal_signals():
    t = np.arange(512) / FS
    beat = np.sin(2 * np.pi * 1.2 * t)
    r_true = 0.6
    dc_red, dc_ir = 1.3, 0.9                  # different DC levels must not matter
    pi_ir = 0.02
    gain = 40.0                               # second-stage gain must cancel
    ac_red = gain * dc_red * r_true * pi_ir * beat
    ac_ir = gain * dc_ir * pi_ir * beat
    res = spo2_ratio_of_ratios(ac_red, np.full_like(t, dc_red), ac_ir, np.full_like(t, dc_ir),
                               FS, ac_gain=gain)
    assert res.ratio == pytest.approx(r_true, rel=1e-3)
    assert res.spo2 == pytest.approx(spo2_from_r(r_true), abs=0.05)


@pytest.mark.parametrize("method", ["rms", "p2p"])
def test_amplitude_method_does_not_change_r_for_same_pulse_shape(method):
    acq = FrontEnd().capture(Subject(spo2=94, seed=3), 6.4)
    res = spo2_ratio_of_ratios(acq.ac_red, acq.dc_red, acq.ac_ir, acq.dc_ir, acq.fs,
                               ac_gain=50.0, method=method, bandpass=True)
    assert res.spo2 == pytest.approx(94, abs=1.0)


@pytest.mark.parametrize("spo2", [85, 90, 94, 97, 99])
@pytest.mark.parametrize("bpm", [50, 80, 140])
def test_end_to_end_through_front_end(spo2, bpm):
    fe = FrontEnd()
    acq = fe.capture(Subject(heart_rate_bpm=bpm, spo2=spo2, seed=spo2 + bpm), 6.4)
    assert not acq.clipped
    res = spo2_ratio_of_ratios(acq.ac_red, acq.dc_red, acq.ac_ir, acq.dc_ir, acq.fs,
                               ac_gain=fe.cfg.ac_gain)
    assert res.spo2 == pytest.approx(spo2, abs=1.5)


def test_breathing_wander_biases_unfiltered_max_min_low():
    """Wander adds the same relative swing to both channels, pulling R towards 1
    (SpO2 towards 85 %); band-pass filtering before measuring removes it."""
    fe = FrontEnd()
    acq = fe.capture(Subject(spo2=98, baseline_wander=0.01, seed=11), 6.4)
    args = (acq.ac_red, acq.dc_red, acq.ac_ir, acq.dc_ir, acq.fs)
    raw = spo2_ratio_of_ratios(*args, ac_gain=50.0, method="p2p", bandpass=False)
    filt = spo2_ratio_of_ratios(*args, ac_gain=50.0, method="rms", bandpass=True)
    assert raw.spo2 < 96.0
    assert filt.spo2 == pytest.approx(98, abs=1.0)


def test_large_red_ir_mismatch_saturates_ac_stage():
    """The high-pass filter sits before demultiplexing, so the red/IR step is
    amplified by the second stage; a big mismatch clips it."""
    ok = FrontEnd(FrontEndConfig(led_current_ir_ua=1.02)).capture(Subject(), 6.4)
    bad = FrontEnd(FrontEndConfig(led_current_ir_ua=1.10)).capture(Subject(), 6.4)
    assert not ok.clipped
    assert bad.clipped


def test_ac_channel_offset_matches_mismatch_times_gain():
    cfg = FrontEndConfig(led_current_ir_ua=1.03, noise_v_rms=0.0)
    acq = FrontEnd(cfg).capture(Subject(baseline_wander=0.0, hrv=0.0), 6.4)
    step = np.mean(acq.ac_ir) - np.mean(acq.ac_red)
    tia_step = np.mean(acq.dc_ir) - np.mean(acq.dc_red)
    assert step == pytest.approx(cfg.ac_gain * tia_step, rel=0.05)
