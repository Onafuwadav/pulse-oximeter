"""Front-end sampling model (reference implementation, 2026)."""
import numpy as np
import pytest

from ppg_sim import FrontEnd, FrontEndConfig, Subject


def test_one_sample_per_wavelength_per_pwm_period():
    acq = FrontEnd().capture(Subject(), 6.4)
    n = acq.ac_red.size
    assert n == acq.ac_ir.size == acq.dc_red.size == acq.dc_ir.size == 512
    assert np.allclose(np.diff(acq.t), 1 / 80.0)


def test_sample_rate_covers_ppg_band():
    # PPG content of interest sits below ~10 Hz; 80 S/s per channel gives a
    # 40 Hz Nyquist limit, four times that.
    cfg = FrontEndConfig()
    assert cfg.fs_channel / 2 >= 4 * 10


def test_tia_settles_before_sampling():
    # first-order settling after a red/IR switch: exp(-t / tau) must be tiny
    cfg = FrontEndConfig()
    t_settle = cfg.sample_point * 0.5 / cfg.pwm_hz
    tau = 1 / (2 * np.pi * cfg.tia_bw_hz)
    assert np.exp(-t_settle / tau) < 1e-6


def test_dc_levels_match_led_currents():
    cfg = FrontEndConfig(noise_v_rms=0.0)
    s = Subject(baseline_wander=0.0)
    acq = FrontEnd(cfg).capture(s, 6.4)
    # mean transmission is 1 - PI * mean(pulse); compare against the no-pulse level loosely
    assert np.max(acq.dc_red) == pytest.approx(cfg.led_current_red_ua * cfg.tia_gain_v_per_ua, rel=0.01)
    assert np.max(acq.dc_ir) == pytest.approx(cfg.led_current_ir_ua * cfg.tia_gain_v_per_ua, rel=0.01)


def test_capture_is_deterministic():
    a = FrontEnd().capture(Subject(seed=5), 3.2)
    b = FrontEnd().capture(Subject(seed=5), 3.2)
    assert np.array_equal(a.ac_ir, b.ac_ir)
