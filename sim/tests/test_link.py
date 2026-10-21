"""Link format: packed BCD and UART framing (reference implementation, 2026)."""
import pytest

from ppg_sim import decode_bcd, encode_bcd, uart_frame_bits


@pytest.mark.parametrize(
    "spo2, byte",
    [(98, 0x98), (97.6, 0x98), (97.4, 0x97), (0, 0x00), (85, 0x85), (100, 0x99), (104.2, 0x99), (-3, 0x00)],
)
def test_encode_bcd(spo2, byte):
    assert encode_bcd(spo2) == byte


def test_bcd_round_trip_all_values():
    for v in range(100):
        assert decode_bcd(encode_bcd(v)) == v


@pytest.mark.parametrize("bad", [0xA5, 0x5A, 0xFF, 0x9A])
def test_decode_rejects_non_bcd(bad):
    with pytest.raises(ValueError):
        decode_bcd(bad)


def test_uart_frame_is_8n1_lsb_first():
    # 0x98 = 1001 1000 -> data bits LSB first: 0 0 0 1 1 0 0 1
    assert uart_frame_bits(0x98) == [0, 0, 0, 0, 1, 1, 0, 0, 1, 1]
    for b in range(256):
        bits = uart_frame_bits(b)
        assert len(bits) == 10 and bits[0] == 0 and bits[-1] == 1
        assert sum(bit << i for i, bit in enumerate(bits[1:9])) == b
