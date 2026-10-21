"""Draw a timing diagram of one received byte from the testbench VCD.

Reference implementation written in 2026. Run `make wave` first, then:

    python3 scripts/plot_timing.py build/tb_display_top.vcd ../docs/img/uart-rx-timing.png

Works with VCDs from GHDL or nvc. Signals are matched by name suffix, so the
exact scope naming of each simulator doesn't matter.
"""
from __future__ import annotations

import sys
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
VIOLET = "#6250d6"


def parse_vcd(path: str, wanted: list[str]) -> tuple[dict[str, list[tuple[int, str]]], float]:
    """Return {suffix: [(time, value), ...]} for the first variable whose
    hierarchical name ends with each wanted suffix, plus the timescale in ns."""
    scope: list[str] = []
    ids: dict[str, str] = {}
    timescale_ns = 1.0
    units = {"fs": 1e-6, "ps": 1e-3, "ns": 1.0, "us": 1e3}
    with open(path) as f:
        lines = iter(f)
        for line in lines:
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "$timescale":
                ts = tok[1:] if len(tok) > 1 else next(lines).split()
                txt = "".join(t for t in ts if t != "$end")
                num = "".join(c for c in txt if c.isdigit()) or "1"
                timescale_ns = int(num) * units[txt.lstrip("0123456789")]
            elif tok[0] == "$scope":
                scope.append(tok[2])
            elif tok[0] == "$upscope":
                scope.pop()
            elif tok[0] == "$var":
                code, name = tok[3], tok[4].split("[")[0]
                full = ".".join(scope + [name])
                for w in wanted:
                    if w not in ids and (full == w or full.endswith("." + w)):
                        ids[w] = code
            elif tok[0] == "$enddefinitions":
                break
        by_code = defaultdict(list)
        for w, c in ids.items():
            by_code[c].append(w)
        out: dict[str, list[tuple[int, str]]] = {w: [] for w in ids}
        t = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            c0 = line[0]
            if c0 == "#":
                t = int(line[1:])
            elif c0 in "01xXzZuUwWlLhH-" and line[1:] in by_code:
                for w in by_code[line[1:]]:
                    out[w].append((t, c0))
            elif c0 in "bBsSrR":
                val, code = line[1:].split()
                for w in by_code.get(code, []):
                    out[w].append((t, val))
    missing = [w for w in wanted if w not in ids]
    if missing:
        raise SystemExit(f"signals not found in VCD: {missing}")
    return out, timescale_ns


def value_at(changes: list[tuple[int, str]], t: int) -> str:
    v = changes[0][1]
    for tc, vc in changes:
        if tc > t:
            break
        v = vc
    return v


def steps(changes, t0, t1):
    """Step-plot points for a 1-bit signal between t0 and t1."""
    xs, ys = [t0], [1 if value_at(changes, t0) == "1" else 0]
    for t, v in changes:
        if t0 < t < t1:
            xs += [t, t]
            ys += [ys[-1], 1 if v == "1" else 0]
    xs.append(t1)
    ys.append(ys[-1])
    return xs, ys


def segments(changes, t0, t1):
    """(start, end, value) runs for a multi-bit or string signal."""
    runs, cur_t, cur_v = [], t0, value_at(changes, t0)
    for t, v in changes:
        if t0 < t < t1 and v != cur_v:
            runs.append((cur_t, t, cur_v))
            cur_t, cur_v = t, v
    runs.append((cur_t, t1, cur_v))
    return runs


def bin_to_hex(v: str) -> str:
    try:
        return f"{int(v, 2):02X}"
    except ValueError:
        return v


def main(vcd: str, png: str) -> None:
    names = ["tb_display_top.rx", "tb_display_top.rst", "u_rx.rx_sync", "u_div.tick",
             "u_ctrl.state", "u_rx.shift_en", "u_rx.shreg", "u_rx.valid", "dut.reading", "dut.have_value"]
    sig, tsc = parse_vcd(vcd, names)

    # first falling edge on rx after reset is released = start of the first byte
    rst_release = next(t for t, v in sig["tb_display_top.rst"] if v == "0")
    t_edge = next(t for t, v in sig["tb_display_top.rx"] if v == "0" and t > rst_release)
    bit_ns = 17361.1
    bit = bit_ns / tsc                                  # bit time in VCD units
    t0, t1 = int(t_edge - 0.8 * bit), int(t_edge + 10.6 * bit)
    to_bits = lambda t: (t - t_edge) / bit           # noqa: E731  x axis in bit periods

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.edgecolor": GRID, "text.color": INK,
                         "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2})
    rows = ["rx line", "rx (synchronised)", "8x sample tick", "FSM state",
            "shift_en (sample)", "shift register", "valid", "displayed reading"]
    fig, ax = plt.subplots(figsize=(11, 4.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    n = len(rows)
    ypos = {r: n - 1 - i for i, r in enumerate(rows)}
    h = 0.6

    def draw_bit(row, changes, color, lw=2.0):
        xs, ys = steps(changes, t0, t1)
        ax.plot([to_bits(x) for x in xs], [ypos[row] + y * h for y in ys],
                color=color, lw=lw, solid_joinstyle="miter")

    def draw_bus(row, changes, fmt, color):
        for a, b, v in segments(changes, t0, t1):
            xa, xb = to_bits(a), to_bits(b)
            y = ypos[row]
            ax.fill_between([xa, xb], y + 0.05, y + h - 0.05, color=color, alpha=0.12, lw=0)
            ax.plot([xa, xb], [y + 0.05, y + 0.05], color=color, lw=1.2)
            ax.plot([xa, xb], [y + h - 0.05, y + h - 0.05], color=color, lw=1.2)
            ax.plot([xa, xa], [y + 0.05, y + h - 0.05], color=color, lw=1.2)
            if xb - xa > 0.35:
                ax.text((xa + xb) / 2, y + h / 2, fmt(v), ha="center", va="center",
                        fontsize=8, color=INK)

    # bit-period guides and labels
    labels = ["start"] + [f"D{i}" for i in range(8)] + ["stop"]
    for k in range(11):
        ax.axvline(k, color=GRID, lw=0.8, zorder=0)
    for k, lab in enumerate(labels):
        ax.text(k + 0.5, n - 0.15, lab, ha="center", va="bottom", fontsize=8, color=INK_2)

    draw_bit("rx line", sig["tb_display_top.rx"], BLUE)
    draw_bit("rx (synchronised)", sig["u_rx.rx_sync"], BLUE, lw=1.4)

    for t, v in sig["u_div.tick"]:
        if v == "1" and t0 < t < t1:
            x = to_bits(t)
            ax.plot([x, x], [ypos["8x sample tick"], ypos["8x sample tick"] + h * 0.7],
                    color=INK_2, lw=0.7)

    draw_bus("FSM state", sig["u_ctrl.state"], lambda v: v.lower(), VIOLET)

    samples = [t for t, v in sig["u_rx.shift_en"] if v == "1" and t0 < t < t1]
    draw_bit("shift_en (sample)", sig["u_rx.shift_en"], ORANGE)
    for t in samples:  # mark where each data bit is taken on the rx trace
        x = to_bits(t)
        ax.plot([x, x], [ypos["shift_en (sample)"] + h, ypos["rx line"] + h + 0.15],
                color=ORANGE, lw=0.8, ls=(0, (2, 2)), zorder=1)

    draw_bus("shift register", sig["u_rx.shreg"], bin_to_hex, AQUA)
    draw_bit("valid", sig["u_rx.valid"], ORANGE)
    # the digits are blanked until the first good byte (have_value = 0)
    shown = [(t, v if value_at(sig["dut.have_value"], t) == "1" else "blank")
             for t, v in sorted(sig["dut.reading"] + [(t, value_at(sig["dut.reading"], t))
                                                      for t, _ in sig["dut.have_value"]])]
    draw_bus("displayed reading", shown,
             lambda v: v if v == "blank" else bin_to_hex(v), AQUA)

    ax.set_yticks([ypos[r] + h / 2 for r in rows])
    ax.set_yticklabels(rows)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(to_bits(t0), to_bits(t1))
    ax.set_ylim(-0.3, n + 0.3)
    ax.set_xlabel("time (bit periods from the start-bit edge; 1 bit = 17.36 µs at 57 600 baud)")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_title("UART receiver, testbench byte 0x98 (SpO₂ = 98 %)  —  "
                 "dashed lines: where each bit is sampled",
                 loc="left", fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(png, dpi=160, facecolor=SURFACE)
    print(f"wrote {png}; sample points (bit periods): "
          + ", ".join(f"{to_bits(t):.2f}" for t in samples))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
