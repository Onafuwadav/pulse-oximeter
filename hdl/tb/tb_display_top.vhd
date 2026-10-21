-- =============================================================================
-- tb_display_top.vhd  --  self-checking testbench for the remote display
--
-- REFERENCE IMPLEMENTATION WRITTEN IN 2026.
--
-- Drives the rx pin like the STM32 + RS-485 link would (57 600 baud, 8N1,
-- LSB first) from a 1.8432 MHz clock, and checks the received bytes and the
-- segment outputs. Test cases:
--   1. displays are blank after reset
--   2. a single reading (98 %)
--   3. back-to-back bytes with no idle time between stop and start bits
--   4. a short low glitch on an idle line is rejected (no byte, no error)
--   5. a byte with a low stop bit raises framing_err and is discarded;
--      the receiver recovers for the next byte
--   6. a byte that is not valid BCD is received but not displayed
--   7. transmitter baud rate off by +3.5 % and -3.5 %
--   8. every reading 00..99 sent back-to-back
-- The run fails (non-zero exit) if any check fails.
-- =============================================================================
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.tb_pkg.all;

entity tb_display_top is
end entity tb_display_top;

architecture sim of tb_display_top is
  signal clk     : std_logic := '0';
  signal rst     : std_logic := '1';
  signal rx      : std_logic := '1';
  signal done    : boolean   := false;

  signal seg_ms, seg_ls : std_logic_vector(6 downto 0);
  signal rx_byte        : std_logic_vector(7 downto 0);
  signal rx_valid       : std_logic;
  signal rx_ferr        : std_logic;

  type byte_log_t is array (0 to 255) of std_logic_vector(7 downto 0);
  signal log       : byte_log_t := (others => (others => '0'));
  signal rx_count  : natural := 0;
  signal ferr_count: natural := 0;

  constant BLANK : std_logic_vector(6 downto 0) := (others => '1');  -- common anode: all off
begin

  clk <= not clk after CLK_PERIOD / 2 when not done;

  dut : entity work.display_top
    generic map (CLK_PER_TICK => 4, COMMON_ANODE => true)
    port map (
      clk_ext        => clk,
      rst            => rst,
      rx             => rx,
      seg_ms         => seg_ms,
      seg_ls         => seg_ls,
      rx_byte        => rx_byte,
      rx_valid       => rx_valid,
      rx_framing_err => rx_ferr
    );

  -- Record every byte the receiver reports
  monitor : process (clk)
  begin
    if rising_edge(clk) then
      if rx_valid = '1' then
        log(rx_count mod 256) <= rx_byte;
        rx_count <= rx_count + 1;
      end if;
      if rx_ferr = '1' then
        ferr_count <= ferr_count + 1;
      end if;
    end if;
  end process monitor;

  stim : process
    variable errors : natural := 0;
    variable checks : natural := 0;
    variable base   : natural;

    procedure uart_send (b        : in std_logic_vector(7 downto 0);
                         bit_t    : in time      := BIT_TIME;
                         stop_val : in std_logic := '1') is
    begin
      rx <= '0';                       -- start bit
      wait for bit_t;
      for i in 0 to 7 loop             -- data, LSB first
        rx <= b(i);
        wait for bit_t;
      end loop;
      rx <= stop_val;                  -- stop bit
      wait for bit_t;
      rx <= '1';                       -- idle (no-op if the next byte follows)
    end procedure;

    procedure check (cond : in boolean; msg : in string) is
    begin
      checks := checks + 1;
      if not cond then
        errors := errors + 1;
        report "CHECK FAILED: " & msg severity error;
      end if;
    end procedure;

    procedure check_display (tens, ones : in natural; msg : in string) is
    begin
      check(seg_ms = not SEG_TABLE(tens),
            msg & ": tens digit shows " & to_bits(seg_ms) & ", expected " & integer'image(tens));
      check(seg_ls = not SEG_TABLE(ones),
            msg & ": units digit shows " & to_bits(seg_ls) & ", expected " & integer'image(ones));
    end procedure;

    function bcd_byte (n : natural) return std_logic_vector is
    begin
      return std_logic_vector(to_unsigned(n / 10, 4)) & std_logic_vector(to_unsigned(n mod 10, 4));
    end function;

  begin
    ---------------------------------------------------------------- 1. reset
    wait for 10 * CLK_PERIOD;
    rst <= '0';
    wait for 10 * BIT_TIME;
    check(seg_ms = BLANK and seg_ls = BLANK, "displays blank after reset");

    ---------------------------------------------------------------- 2. one reading
    uart_send(x"98");
    wait for 2 * BIT_TIME;
    check(rx_count = 1, "one byte received");
    check(log(0) = x"98", "first byte is 0x98, got " & to_hex(log(0)));
    check_display(9, 8, "after 0x98");

    ---------------------------------------------------------------- 3. back-to-back
    uart_send(x"00");
    uart_send(x"57");
    uart_send(x"99");
    wait for 2 * BIT_TIME;
    check(rx_count = 4, "three back-to-back bytes received, count = " & integer'image(rx_count));
    check(log(1) = x"00" and log(2) = x"57" and log(3) = x"99",
          "back-to-back bytes: " & to_hex(log(1)) & " " & to_hex(log(2)) & " " & to_hex(log(3)));
    check_display(9, 9, "after back-to-back bytes");

    ---------------------------------------------------------------- 4. glitch
    rx <= '0';
    wait for 2 us;                      -- shorter than 4 sample ticks (~8.7 us)
    rx <= '1';
    wait for 20 * BIT_TIME;
    check(rx_count = 4 and ferr_count = 0, "2 us glitch ignored");
    check_display(9, 9, "after glitch");

    ---------------------------------------------------------------- 5. framing error
    uart_send(x"42", BIT_TIME, '0');    -- stop bit low
    wait for 5 * BIT_TIME;
    check(ferr_count = 1, "framing error flagged");
    check(rx_count = 4, "byte with bad stop bit discarded");
    check_display(9, 9, "after framing error");
    uart_send(x"95");
    wait for 2 * BIT_TIME;
    check(rx_count = 5 and log(4) = x"95", "receiver recovers after framing error");
    check_display(9, 5, "after recovery");

    ---------------------------------------------------------------- 6. not BCD
    uart_send(x"A5");
    wait for 2 * BIT_TIME;
    check(rx_count = 6 and log(5) = x"A5", "non-BCD byte received");
    check_display(9, 5, "non-BCD byte not displayed");

    ---------------------------------------------------------------- 7. baud tolerance
    -- Alternating bit patterns, so sampling even slightly into a neighbouring
    -- bit (or reading the stop bit too early/late) changes the result.
    -- With 4-sample start detection the sampling point sits near mid-bit, which
    -- leaves roughly +/-4 % of clock mismatch before the stop bit is misread;
    -- +/-3.5 % is tested here.
    uart_send(x"55", BIT_TIME * 1035 / 1000);
    uart_send(x"AA", BIT_TIME * 1035 / 1000);
    wait for 2 * BIT_TIME;
    check(rx_count = 8 and log(6) = x"55" and log(7) = x"AA",
          "transmitter 3.5 % slow: got " & to_hex(log(6)) & " " & to_hex(log(7)));
    uart_send(x"55", BIT_TIME * 965 / 1000);
    uart_send(x"AA", BIT_TIME * 965 / 1000);
    wait for 2 * BIT_TIME;
    check(rx_count = 10 and log(8) = x"55" and log(9) = x"AA",
          "transmitter 3.5 % fast: got " & to_hex(log(8)) & " " & to_hex(log(9)));
    check(ferr_count = 1, "no framing errors from the off-speed bytes");
    uart_send(x"87");
    wait for 2 * BIT_TIME;
    check_display(8, 7, "after baud tolerance tests");

    ---------------------------------------------------------------- 8. sweep 00..99
    base := rx_count;
    for n in 0 to 99 loop
      uart_send(bcd_byte(n));
    end loop;
    wait for 2 * BIT_TIME;
    check(rx_count = base + 100, "100 sweep bytes received, count = " & integer'image(rx_count - base));
    for n in 0 to 99 loop
      check(log((base + n) mod 256) = bcd_byte(n),
            "sweep value " & integer'image(n) & " received as " & to_hex(log((base + n) mod 256)));
    end loop;
    check_display(9, 9, "after sweep");
    check(ferr_count = 1, "no further framing errors");

    ---------------------------------------------------------------- summary
    assert errors = 0
      report "tb_display_top FAILED: " & integer'image(errors) & " of "
             & integer'image(checks) & " checks"
      severity failure;
    report "tb_display_top PASSED (" & integer'image(checks) & " checks)";
    done <= true;
    wait;
  end process stim;

end architecture sim;
