"""Optical front end and ADC sampling, following the project's architecture.

Reference implementation written in 2026. Component values are illustrative.

    LED (red/IR, alternating at the PWM rate)
      -> finger -> photodiode -> transimpedance amplifier (TIA)  ---> ADC "DC"
                                       -> high-pass filter -> 2nd-stage gain ---> ADC "AC"

* One bicolour LED package alternates red and IR, so a single photodiode sees
  a time-multiplexed signal: red level, IR level, red level, ...
* Both ADCs are triggered by the same timer, once in each LED's on-time, so
  every PWM period yields one red and one IR sample on each ADC.
* The TIA is modelled as a gain with a first-order bandwidth limit (it has to
  settle within each LED's on-time before the ADC samples).
* The high-pass filter sits *before* the samples are separated into red and
  IR. It therefore removes the average of the two levels, not each level
  separately: the red/IR step passes straight through and is amplified by the
  second stage. That step is a constant per channel, so it drops out of the AC
  amplitude, but it uses up output swing. The simulation flags clipping.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import signal

from .physiology import Subject


@dataclass(frozen=True)
class FrontEndConfig:
    pwm_hz: float = 80.0            # LED switching frequency (red and IR each on half the period)
    sample_point: float = 0.75      # ADC trigger position within each LED on-time (0..1)
    fs_analog: float = 16_000.0     # internal time step for the "analogue" part
    led_current_red_ua: float = 1.00  # photocurrent with red on (uA) - illustrative
    led_current_ir_ua: float = 1.02   # photocurrent with IR on (uA): 2 % mismatch
    ambient_ua: float = 0.0         # ambient-light photocurrent, present in both phases
    tia_gain_v_per_ua: float = 1.0  # i.e. 1 MOhm feedback resistor - illustrative
    tia_bw_hz: float = 2_000.0      # TIA closed-loop bandwidth
    hpf_fc_hz: float = 0.5          # AC-coupling corner
    ac_gain: float = 50.0           # second-stage voltage gain
    ac_bias_v: float = 1.65         # second stage biased at mid-rail
    vref: float = 3.3               # ADC reference / supply rail
    adc_bits: int = 12              # STM32L476 ADC resolution
    noise_v_rms: float = 0.3e-3     # white noise referred to the TIA output
    settle_s: float = 8.0           # discarded start-up time (HPF settling)
    seed: int = 1

    @property
    def fs_channel(self) -> float:
        """Samples per second per wavelength per ADC (one per PWM period)."""
        return self.pwm_hz


@dataclass
class Acquisition:
    """Result of one simulated capture."""

    config: FrontEndConfig
    t: np.ndarray            # sample times per channel (s), red sample times
    dc_red: np.ndarray       # ADC volts, DC channel, red phase
    dc_ir: np.ndarray
    ac_red: np.ndarray       # ADC volts, AC channel, red phase
    ac_ir: np.ndarray
    clipped: bool
    # a short stretch of the continuous signals, for plotting
    t_analog: np.ndarray = field(repr=False, default_factory=lambda: np.empty(0))
    v_tia: np.ndarray = field(repr=False, default_factory=lambda: np.empty(0))
    v_ac: np.ndarray = field(repr=False, default_factory=lambda: np.empty(0))
    led_red_on: np.ndarray = field(repr=False, default_factory=lambda: np.empty(0))

    @property
    def fs(self) -> float:
        return self.config.fs_channel


class FrontEnd:
    def __init__(self, config: FrontEndConfig | None = None):
        self.cfg = config or FrontEndConfig()

    def _adc(self, v: np.ndarray) -> tuple[np.ndarray, bool]:
        c = self.cfg
        lsb = c.vref / (2**c.adc_bits)
        clipped = bool(np.any(v <= 0.0) or np.any(v >= c.vref - lsb))
        codes = np.clip(np.round(v / lsb), 0, 2**c.adc_bits - 1)
        return codes * lsb, clipped

    def capture(self, subject: Subject, duration_s: float, keep_analog_s: float = 0.1) -> Acquisition:
        c = self.cfg
        rng = np.random.default_rng(c.seed)
        total = duration_s + c.settle_s
        n = int(round(total * c.fs_analog))
        t = np.arange(n) / c.fs_analog

        # which LED is on: red for the first half of each PWM period, IR for the second
        phase = np.mod(t * c.pwm_hz, 1.0)
        red_on = phase < 0.5

        tr_red, tr_ir = subject.transmission(t)
        i_pd = np.where(red_on, c.led_current_red_ua * tr_red, c.led_current_ir_ua * tr_ir) + c.ambient_ua

        # TIA: gain + first-order bandwidth limit + noise
        b, a = signal.butter(1, c.tia_bw_hz, fs=c.fs_analog)
        v_tia = signal.lfilter(b, a, c.tia_gain_v_per_ua * i_pd,
                               zi=signal.lfilter_zi(b, a) * c.tia_gain_v_per_ua * i_pd[0])[0]
        v_tia = v_tia + rng.normal(0.0, c.noise_v_rms, n)

        # AC path: first-order high-pass on the multiplexed signal, then gain about mid-rail
        bh, ah = signal.butter(1, c.hpf_fc_hz, btype="highpass", fs=c.fs_analog)
        v_hp = signal.lfilter(bh, ah, v_tia - v_tia[:int(c.fs_analog / c.pwm_hz)].mean())
        v_ac = c.ac_bias_v + c.ac_gain * v_hp
        v_ac = np.clip(v_ac, 0.0, c.vref)  # op-amp output cannot leave the rails

        # Timer-triggered sampling: one red and one IR sample per PWM period
        n_periods = int(np.floor(total * c.pwm_hz))
        k = np.arange(n_periods)
        t_red = (k + 0.5 * c.sample_point) / c.pwm_hz
        t_ir = (k + 0.5 + 0.5 * c.sample_point) / c.pwm_hz
        keep = t_red >= c.settle_s
        idx_red = np.round(t_red[keep] * c.fs_analog).astype(int)
        idx_ir = np.round(t_ir[keep] * c.fs_analog).astype(int)
        idx_red, idx_ir = idx_red[idx_ir < n], idx_ir[idx_ir < n]

        dc_red, c1 = self._adc(v_tia[idx_red])
        dc_ir, c2 = self._adc(v_tia[idx_ir])
        ac_red, c3 = self._adc(v_ac[idx_red])
        ac_ir, c4 = self._adc(v_ac[idx_ir])

        # keep a short analogue window right after settling, for plots
        a0 = int(c.settle_s * c.fs_analog)
        a1 = a0 + int(keep_analog_s * c.fs_analog)
        return Acquisition(
            config=c,
            t=t[idx_red] - c.settle_s,
            dc_red=dc_red,
            dc_ir=dc_ir,
            ac_red=ac_red,
            ac_ir=ac_ir,
            clipped=c1 or c2 or c3 or c4,
            t_analog=t[a0:a1] - c.settle_s,
            v_tia=v_tia[a0:a1],
            v_ac=v_ac[a0:a1],
            led_red_on=red_on[a0:a1],
        )
