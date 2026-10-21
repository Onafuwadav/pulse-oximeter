"""Generate the simulation figures and numbers used in the README.

Reference implementation written in 2026. Usage (from the sim/ folder):

    python3 run_demo.py            # writes ../docs/img/sim-*.png and results.md
"""
from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from ppg_sim import (  # noqa: E402
    FrontEnd,
    FrontEndConfig,
    Subject,
    encode_bcd,
    heart_rate_fft,
    spo2_ratio_of_ratios,
)

HERE = pathlib.Path(__file__).resolve().parent
IMG = HERE.parent / "docs" / "img"

# Light-surface palette (validated categorical slots; text never in series colour)
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
RED, IR, AQUA, ORANGE = "#e34948", "#2a78d6", "#1baf7a", "#eb6834"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titlelocation": "left",
    "axes.titlesize": 10, "lines.linewidth": 1.6,
})

WINDOW_S = 6.4  # 512 samples per wavelength at 80 S/s


def measure(acq, cfg, method="rms", bandpass=True):
    hr = heart_rate_fft(acq.ac_ir, acq.fs)
    sp = spo2_ratio_of_ratios(acq.ac_red, acq.dc_red, acq.ac_ir, acq.dc_ir, acq.fs,
                              ac_gain=cfg.ac_gain, method=method, bandpass=bandpass)
    return hr, sp


def fig_acquisition(fe: FrontEnd, subj: Subject, path: pathlib.Path) -> dict:
    acq = fe.capture(subj, WINDOW_S, keep_analog_s=0.05)
    cfg = fe.cfg
    fig, axes = plt.subplots(3, 1, figsize=(10, 7.2))

    # (a) multiplexed TIA output over four PWM periods
    ax = axes[0]
    ta = acq.t_analog * 1e3
    on = acq.led_red_on
    edges = np.flatnonzero(np.diff(on.astype(int)) != 0) + 1
    bounds = np.concatenate(([0], edges, [on.size]))
    for a, b in zip(bounds[:-1], bounds[1:]):
        ax.axvspan(ta[a], ta[b - 1], color=RED if on[a] else IR, alpha=0.08, lw=0)
    ax.plot(ta, acq.v_tia, color=INK_2, lw=1.0)
    in_win = acq.t < acq.t_analog[-1]
    ts_red = acq.t[in_win] * 1e3
    ts_ir = ts_red + 0.5e3 / cfg.pwm_hz
    ax.plot(ts_red, acq.dc_red[in_win], "o", color=RED, ms=6, mec=SURFACE, mew=1.5, label="red sample")
    ax.plot(ts_ir, acq.dc_ir[in_win], "o", color=IR, ms=6, mec=SURFACE, mew=1.5, label="IR sample")
    ax.set_title("(a) TIA output: red and IR alternate at 80 Hz; the ADC samples late in each on-time")
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("V")
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), frameon=False, ncol=2,
              borderaxespad=0.2)

    # (b) DC channel, demultiplexed
    ax = axes[1]
    ax.plot(acq.t, acq.dc_red, color=RED)
    ax.plot(acq.t, acq.dc_ir, color=IR)
    ax.text(acq.t[-1] + 0.05, np.median(acq.dc_red), "red", color=INK_2, va="center")
    ax.text(acq.t[-1] + 0.05, np.median(acq.dc_ir), "IR", color=INK_2, va="center")
    lsb = cfg.vref / 2**cfg.adc_bits
    ax.set_title(f"(b) DC channel (straight after the TIA): the whole IR trace spans only "
                 f"~{np.ptp(acq.dc_ir) / lsb:.0f} ADC codes")
    ax.set_ylabel("V")
    ax.set_xlim(0, acq.t[-1] + 0.5)

    # (c) AC channel, demultiplexed
    ax = axes[2]
    ax.plot(acq.t, acq.ac_red, color=RED)
    ax.plot(acq.t, acq.ac_ir, color=IR)
    ax.text(acq.t[-1] + 0.05, np.median(acq.ac_red), "red", color=INK_2, va="center")
    ax.text(acq.t[-1] + 0.05, np.median(acq.ac_ir), "IR", color=INK_2, va="center")
    ax.axhline(cfg.ac_bias_v, color=INK_2, lw=0.8, ls=(0, (3, 3)))
    ax.set_title(f"(c) AC channel (high-pass + x{cfg.ac_gain:.0f}): same trace spans "
                 f"~{np.ptp(acq.ac_ir) / lsb:.0f} codes; the red/IR offset is the multiplexing step")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("V")
    ax.set_xlim(0, acq.t[-1] + 0.5)
    ax.set_ylim(0, cfg.vref)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return {
        "dc_pulse_codes": float(np.ptp(acq.dc_ir) / lsb),
        "ac_pulse_codes": float(np.ptp(acq.ac_ir) / lsb),
    }


def fig_processing(fe: FrontEnd, subj: Subject, path: pathlib.Path) -> dict:
    acq = fe.capture(subj, WINDOW_S)
    hr, sp = measure(acq, fe.cfg)
    fig, ax = plt.subplots(figsize=(10, 3.4))
    m = hr.magnitude / hr.magnitude.max()
    sel = hr.freqs <= 6
    ax.axvspan(0.6, 3.5, color=AQUA, alpha=0.08, lw=0)
    ax.text(0.65, 1.02, "search band 36-210 bpm", color=INK_2, fontsize=8, va="bottom")
    ax.plot(hr.freqs[sel], m[sel], color=IR)
    ax.plot([hr.peak_hz], [np.interp(hr.peak_hz, hr.freqs, m)], "o", color=IR, ms=8, mec=SURFACE, mew=2)
    ax.annotate(f"{hr.bpm:.1f} bpm (true {subj.heart_rate_bpm:.0f})",
                (hr.peak_hz, np.interp(hr.peak_hz, hr.freqs, m)),
                xytext=(12, -4), textcoords="offset points", color=INK)
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("normalised |FFT|")
    ax.set_ylim(0, 1.12)
    ax.set_title(f"IR AC channel, {acq.ac_ir.size}-sample Hann window zero-padded to "
                 f"{hr.freqs.size * 2 - 2}: R = {sp.ratio:.3f} -> SpO₂ = {sp.spo2:.1f} % "
                 f"(true {subj.spo2:.0f} %), sent as byte 0x{encode_bcd(sp.spo2):02X}")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return {"hr": hr.bpm, "spo2": sp.spo2, "R": sp.ratio}


def sweep(fe: FrontEnd):
    hrs = [40, 50, 60, 75, 90, 105, 120, 150, 180]
    spo2s = [85, 88, 91, 94, 97, 99]
    rows = []
    for i, h in enumerate(hrs):
        for j, s in enumerate(spo2s):
            subj = Subject(heart_rate_bpm=h, spo2=s, seed=100 + 10 * i + j)
            acq = fe.capture(subj, WINDOW_S)
            hr, sp = measure(acq, fe.cfg)
            _, sp_raw = measure(acq, fe.cfg, method="p2p", bandpass=False)
            rows.append((h, s, hr.bpm, sp.spo2, sp_raw.spo2))
    return np.array(rows)


def fig_accuracy(res: np.ndarray, path: pathlib.Path) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    a1.plot([30, 190], [30, 190], color=GRID, lw=1.2, zorder=0)
    a1.plot(res[:, 0], res[:, 2], "o", color=IR, ms=6, mec=SURFACE, mew=1.2, alpha=0.9)
    a1.set_xlabel("true heart rate (bpm)")
    a1.set_ylabel("estimated (bpm)")
    a1.set_title(f"Heart rate: worst error {np.max(np.abs(res[:, 2] - res[:, 0])):.1f} bpm")

    jitter = (res[:, 0] - 110) / 110 * 0.6  # spread overlapping points sideways
    a2.plot([83, 100], [83, 100], color=GRID, lw=1.2, zorder=0)
    a2.plot(res[:, 1] + jitter, res[:, 4], "s", color=ORANGE, ms=5, mec=SURFACE, mew=1, label="raw max−min")
    a2.plot(res[:, 1] + jitter, res[:, 3], "o", color=AQUA, ms=6, mec=SURFACE, mew=1.2, label="band-pass + RMS")
    a2.set_xlabel("true SpO₂ (%)")
    a2.set_ylabel("estimated (%)")
    a2.set_title("SpO₂: breathing wander biases raw max−min low")
    a2.legend(frameon=False, loc="upper left")
    fig.suptitle(f"Simulated accuracy over {len(res)} synthetic captures ({WINDOW_S} s windows, "
                 "noise + breathing + heart-rate variability)", x=0.01, ha="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def window_study(fe: FrontEnd) -> list[tuple[float, float, float]]:
    out = []
    for n in (128, 256, 512, 1024):
        dur = n / fe.cfg.pwm_hz
        errs = []
        for i, h in enumerate([40, 60, 90, 120, 180]):
            for seed in range(4):
                acq = fe.capture(Subject(heart_rate_bpm=h, seed=1000 + 10 * i + seed), dur)
                errs.append(abs(heart_rate_fft(acq.ac_ir[:n], acq.fs).bpm - h))
        out.append((dur, float(np.mean(errs)), float(np.max(errs))))
    return out


def mismatch_study() -> list[tuple[float, bool, float]]:
    out = []
    for mm in (0.0, 0.02, 0.04, 0.06, 0.10):
        cfg = FrontEndConfig(led_current_ir_ua=1.0 * (1 + mm))
        fe = FrontEnd(cfg)
        acq = fe.capture(Subject(spo2=97), WINDOW_S)
        _, sp = measure(acq, cfg)
        out.append((mm, acq.clipped, sp.spo2))
    return out


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    fe = FrontEnd()
    demo = Subject(heart_rate_bpm=72, spo2=97, seed=7)
    a = fig_acquisition(fe, demo, IMG / "sim-acquisition.png")
    p = fig_processing(fe, demo, IMG / "sim-processing.png")
    res = sweep(fe)
    fig_accuracy(res, IMG / "sim-accuracy.png")
    win = window_study(fe)
    mm = mismatch_study()

    hr_err = np.abs(res[:, 2] - res[:, 0])
    sp_err = np.abs(res[:, 3] - res[:, 1])
    raw_err = res[:, 4] - res[:, 1]
    lines = [
        "# Simulation results (reference implementation, 2026)",
        "",
        "Synthetic signals only - these are not measurements from the original hardware.",
        "Regenerate with `python3 run_demo.py`.",
        "",
        f"* Demo capture (72 bpm, 97 %): HR {p['hr']:.1f} bpm, R = {p['R']:.3f}, SpO2 {p['spo2']:.1f} %",
        f"* Pulse size in ADC codes: DC channel {a['dc_pulse_codes']:.0f}, AC channel {a['ac_pulse_codes']:.0f}",
        f"* Sweep of {len(res)} captures, 40-180 bpm x 85-99 %:",
        f"  * heart rate error: mean {hr_err.mean():.2f} bpm, worst {hr_err.max():.2f} bpm",
        f"  * SpO2 error (band-pass + RMS): mean {sp_err.mean():.2f} %, worst {sp_err.max():.2f} %",
        f"  * SpO2 error (raw max-min, no filter): mean {raw_err.mean():+.2f} %, "
        f"worst {raw_err[np.argmax(np.abs(raw_err))]:+.2f} %",
        "",
        "## FFT window length vs heart-rate error (IR channel, 80 S/s)",
        "",
        "| window | samples | bin spacing | mean error | worst error |",
        "|---|---|---|---|---|",
    ]
    for dur, mean_e, max_e in win:
        n = int(round(dur * fe.cfg.pwm_hz))
        lines.append(f"| {dur:.1f} s | {n} | {60 / dur:.1f} bpm | {mean_e:.2f} bpm | {max_e:.2f} bpm |")
    lines += [
        "",
        "## Red/IR level mismatch vs second-stage headroom (gain x50, SpO2 97 %)",
        "",
        "| IR level vs red | AC channel clipped | SpO2 estimate |",
        "|---|---|---|",
    ]
    for m, clipped, s in mm:
        lines.append(f"| +{m * 100:.0f} % | {'yes' if clipped else 'no'} | {s:.1f} % |")
    (HERE / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
