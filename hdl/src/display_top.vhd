-- =============================================================================
-- display_top.vhd  --  remote SpO2 display: UART receiver -> two 7-seg digits
--
-- REFERENCE IMPLEMENTATION WRITTEN IN 2026 for the Intel/Altera MAX II
-- EPM240T100C5 (synthesisable VHDL-2008; no vendor primitives used).
--
-- The STM32 sends SpO2 as one byte holding two packed BCD digits:
--   bits 7..4 = tens digit (MS display), bits 3..0 = units digit (LS display)
-- e.g. 98 % -> 0x98. 99 % is the largest value that fits, which is why the
-- handout caps the display at 99.
--
-- Behaviour:
--   * the last good reading is held on the displays until a new one arrives
--   * bytes with a bad stop bit are discarded (rx_framing_err pulses)
--   * bytes that are not valid BCD (a nibble > 9) are discarded
--   * both digits stay blank until the first good reading
--
-- The handout's display (Kingbright SA56-11 series) is common-anode, so a
-- segment lights when its CPLD pin is driven LOW; set COMMON_ANODE => false
-- for a common-cathode part.
-- =============================================================================
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity display_top is
  generic (
    CLK_PER_TICK : positive := 4;     -- 1.8432 MHz / 4 = 8 x 57 600 baud
    COMMON_ANODE : boolean  := true
  );
  port (
    clk_ext        : in  std_logic;                     -- 1.8432 MHz crystal oscillator
    rst            : in  std_logic;                     -- active-high reset
    rx             : in  std_logic;                     -- from the RS-485 receiver (R pin)
    seg_ms         : out std_logic_vector(6 downto 0);  -- tens digit, g..a
    seg_ls         : out std_logic_vector(6 downto 0);  -- units digit, g..a
    -- status / debug
    rx_byte        : out std_logic_vector(7 downto 0);
    rx_valid       : out std_logic;
    rx_framing_err : out std_logic
  );
end entity display_top;

architecture rtl of display_top is
  signal tick       : std_logic;
  signal byte       : std_logic_vector(7 downto 0);
  signal valid      : std_logic;
  signal ferr       : std_logic;

  signal reading    : std_logic_vector(7 downto 0) := (others => '0');
  signal have_value : std_logic := '0';

  signal seg_ms_raw : std_logic_vector(6 downto 0);
  signal seg_ls_raw : std_logic_vector(6 downto 0);
  signal seg_ms_on  : std_logic_vector(6 downto 0);
  signal seg_ls_on  : std_logic_vector(6 downto 0);

  function is_bcd(n : std_logic_vector(3 downto 0)) return boolean is
  begin
    return unsigned(n) <= 9;
  end function;
begin

  u_div : entity work.clk_div
    generic map (DIVIDE => CLK_PER_TICK)
    port map (clk => clk_ext, rst => rst, tick => tick);

  u_rx : entity work.uart_rx
    port map (
      clk         => clk_ext,
      rst         => rst,
      tick        => tick,
      rx          => rx,
      data        => byte,
      valid       => valid,
      framing_err => ferr
    );

  -- Hold the last valid reading
  hold : process (clk_ext)
  begin
    if rising_edge(clk_ext) then
      if rst = '1' then
        reading    <= (others => '0');
        have_value <= '0';
      elsif valid = '1' and is_bcd(byte(7 downto 4)) and is_bcd(byte(3 downto 0)) then
        reading    <= byte;
        have_value <= '1';
      end if;
    end if;
  end process hold;

  u_dec_ms : entity work.bcd_to_7seg port map (bcd => reading(7 downto 4), seg => seg_ms_raw);
  u_dec_ls : entity work.bcd_to_7seg port map (bcd => reading(3 downto 0), seg => seg_ls_raw);

  seg_ms_on <= seg_ms_raw when have_value = '1' else (others => '0');
  seg_ls_on <= seg_ls_raw when have_value = '1' else (others => '0');

  seg_ms <= not seg_ms_on when COMMON_ANODE else seg_ms_on;
  seg_ls <= not seg_ls_on when COMMON_ANODE else seg_ls_on;

  rx_byte        <= byte;
  rx_valid       <= valid;
  rx_framing_err <= ferr;

end architecture rtl;
