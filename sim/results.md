# Simulation results (reference implementation, 2026)

Synthetic signals only - these are not measurements from the original hardware.
Regenerate with `python3 run_demo.py`.

* Demo capture (72 bpm, 97 %): HR 72.7 bpm, R = 0.538, SpO2 96.6 %
* Pulse size in ADC codes: DC channel 39, AC channel 1535
* Sweep of 54 captures, 40-180 bpm x 85-99 %:
  * heart rate error: mean 0.58 bpm, worst 2.69 bpm
  * SpO2 error (band-pass + RMS): mean 0.17 %, worst 0.74 %
  * SpO2 error (raw max-min, no filter): mean -1.46 %, worst -3.20 %

## FFT window length vs heart-rate error (IR channel, 80 S/s)

| window | samples | bin spacing | mean error | worst error |
|---|---|---|---|---|
| 1.6 s | 128 | 37.5 bpm | 3.07 bpm | 9.42 bpm |
| 3.2 s | 256 | 18.8 bpm | 1.05 bpm | 2.55 bpm |
| 6.4 s | 512 | 9.4 bpm | 0.53 bpm | 2.12 bpm |
| 12.8 s | 1024 | 4.7 bpm | 0.22 bpm | 0.67 bpm |

## Red/IR level mismatch vs second-stage headroom (gain x50, SpO2 97 %)

| IR level vs red | AC channel clipped | SpO2 estimate |
|---|---|---|
| +0 % | no | 96.6 % |
| +2 % | no | 96.6 % |
| +4 % | no | 96.6 % |
| +6 % | yes | 98.9 % |
| +10 % | yes | 100.0 % |
