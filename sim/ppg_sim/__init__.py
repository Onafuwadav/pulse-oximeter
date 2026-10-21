"""Pulse-oximeter signal-chain simulation.

REFERENCE IMPLEMENTATION WRITTEN IN 2026. The original STM32 firmware from the
2024-25 project is lost; this package re-creates the *method* (PWM-multiplexed
red/IR LEDs, two ADC channels, FFT heart rate, ratio-of-ratios SpO2) on
synthetic signals so it can be inspected and tested. Component values here are
illustrative, not the values used on the original board.
"""

from .physiology import Subject, ppg_pulse, r_from_spo2, spo2_from_r
from .frontend import FrontEnd, FrontEndConfig, Acquisition
from .processing import (
    HeartRateResult,
    SpO2Result,
    heart_rate_fft,
    spo2_ratio_of_ratios,
)
from .link import encode_bcd, decode_bcd, uart_frame_bits

__all__ = [
    "Subject",
    "ppg_pulse",
    "r_from_spo2",
    "spo2_from_r",
    "FrontEnd",
    "FrontEndConfig",
    "Acquisition",
    "HeartRateResult",
    "SpO2Result",
    "heart_rate_fft",
    "spo2_ratio_of_ratios",
    "encode_bcd",
    "decode_bcd",
    "uart_frame_bits",
]
