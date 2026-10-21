# sim/: pulse-oximeter signal chain in Python

**Reference implementation.** The original STM32 firmware is lost. This package re-creates the method on synthetic signals so that it can be inspected and tested. Component values (photocurrents, TIA gain, filter corner, second-stage gain) are illustrative, not the values from the original board.

| Module | Contents |
|---|---|
| `ppg_sim/physiology.py` | Pulse shape, heart-rate variability, breathing drift, red/IR perfusion set from a target SpO₂ |
| `ppg_sim/frontend.py` | 80 Hz red/IR multiplexing, TIA with bandwidth limit and noise, high-pass filter + second stage on the multiplexed signal, rail clipping, two 12-bit ADCs triggered once per LED phase |
| `ppg_sim/processing.py` | FFT heart rate (Hann window, zero-padding, peak interpolation, harmonic check) and ratio-of-ratios SpO₂ |
| `ppg_sim/link.py` | Packed-BCD byte and 8N1 UART frame |
| `run_demo.py` | Figures in `../docs/img/` and the numbers in `results.md` |

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest
python3 run_demo.py
```

Two things the tests pin down that are easy to get wrong:

- **Harmonics.** A PPG's diastolic bump puts strong energy at twice the heart rate. `heart_rate_fft` checks for a genuine peak at half the winning frequency (inside the band) before accepting it.
- **Breathing drift and SpO₂.** Drift adds the same relative swing to both wavelengths, pulling R towards 1. An unfiltered max − min therefore reads high saturations low; band-pass filtering before measuring the amplitude removes the bias.
