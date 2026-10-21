"""The STM32 -> display-board link format.

Reference implementation written in 2026, following the module's link
specification: 57 600 baud, 8 data bits, no parity, 1 stop bit, SpO2 sent as
one byte holding two packed BCD digits (tens in the high nibble). The largest
value that fits is 99, so readings are clamped to 0..99 before sending.
"""
from __future__ import annotations

BAUD = 57_600


def encode_bcd(spo2: float) -> int:
    """Round, clamp to 0..99 and pack as two BCD digits, e.g. 97.6 -> 0x98."""
    v = int(round(spo2))
    v = max(0, min(99, v))
    return ((v // 10) << 4) | (v % 10)


def decode_bcd(byte: int) -> int:
    """Inverse of :func:`encode_bcd`. Raises ValueError for non-BCD bytes."""
    if not 0 <= byte <= 0xFF:
        raise ValueError("not a byte")
    hi, lo = byte >> 4, byte & 0x0F
    if hi > 9 or lo > 9:
        raise ValueError(f"0x{byte:02X} is not packed BCD")
    return 10 * hi + lo


def uart_frame_bits(byte: int) -> list[int]:
    """Line levels for one 8N1 frame: start (0), 8 data bits LSB first, stop (1)."""
    return [0] + [(byte >> i) & 1 for i in range(8)] + [1]
