# hdl/: CPLD display logic in VHDL

**Reference implementation.** The original Quartus Prime schematic design is lost; this is a VHDL-2008 rewrite of the same blocks for the Altera MAX II EPM240, with self-checking testbenches. It uses no vendor primitives, so it simulates in GHDL or nvc and should synthesise in Quartus Prime.

| File | Block |
|---|---|
| `src/clk_div.vhd` | 1.8432 MHz → one-clock "tick" every 4 clocks (8 × 57 600 baud) |
| `src/rx_control.vhd` | Receive state machine: 4-sample start detection, mid-bit sampling, stop-bit check |
| `src/shift_reg.vhd` | Serial-in, parallel-out register (LSB arrives first) |
| `src/uart_rx.vhd` | Two-flop synchroniser + control + shift register + output register |
| `src/bcd_to_7seg.vhd` | Karnaugh-map segment equations |
| `src/display_top.vhd` | Top level: hold last valid reading, blank until first reading, active-low outputs for common-anode digits |
| `tb/tb_bcd_to_7seg.vhd` | All ten digits against a hand-written segment table |
| `tb/tb_display_top.vhd` | 131 checks through the full receiver and decoder |

Differences from the original design, made on purpose:

- **Clock enable instead of a divided clock.** Everything runs on the crystal clock; the divider produces an enable pulse. This avoids clock skew and multiple clock domains.
- **Synchroniser on `rx`.** The serial line is asynchronous to the CPLD clock, so it passes through two flip-flops before the state machine sees it.
- **`WAIT_IDLE` state.** After a framing error the line may still be low (a break, or a disconnected cable). Without this state the receiver would read that as a new start bit and invent a `0xFF`.
- **Non-BCD bytes are ignored** and the display keeps the last valid reading.

## Running

```bash
make            # GHDL
make SIM=nvc    # nvc
make wave       # VCD of tb_display_top in build/
python3 scripts/plot_timing.py build/tb_display_top.vcd ../docs/img/uart-rx-timing.png
```

## Testbench coverage

`tb_display_top` drives the `rx` pin as the STM32 and RS-485 link would, from a 1.8432 MHz clock:

1. displays blank after reset
2. a single reading (`0x98`)
3. three bytes back-to-back with no idle time between stop and start bits
4. a 2 µs low glitch on an idle line is ignored
5. a byte with a low stop bit is flagged and discarded, and the next byte is received normally
6. a byte that isn't valid BCD (`0xA5`) is received but not displayed
7. alternating-bit bytes (`0x55`, `0xAA`) with the transmitter 3.5 % slow and 3.5 % fast
8. every reading from 00 to 99, back-to-back

To check that the testbench actually detects faults, each of these deliberate bugs was introduced in turn, and every one made the run fail: a wrong segment equation, MSB-first shifting, accepting a start bit after 2 samples instead of 4, removing the glitch filter, removing `WAIT_IDLE`, removing the BCD check, and feeding the state machine a 16× tick.
