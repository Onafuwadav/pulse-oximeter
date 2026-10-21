-- =============================================================================
-- shift_reg.vhd  --  serial-in, parallel-out shift register
--
-- REFERENCE IMPLEMENTATION WRITTEN IN 2026.
--
-- UART sends the least significant bit first, so each new bit enters at the
-- MSB end and everything moves one place towards bit 0. After 8 enabled
-- shifts, q holds the received byte in normal bit order.
-- =============================================================================
library ieee;
use ieee.std_logic_1164.all;

entity shift_reg is
  generic (
    WIDTH : positive := 8
  );
  port (
    clk : in  std_logic;
    rst : in  std_logic;
    en  : in  std_logic;
    din : in  std_logic;
    q   : out std_logic_vector(WIDTH - 1 downto 0)
  );
end entity shift_reg;

architecture rtl of shift_reg is
  signal reg : std_logic_vector(WIDTH - 1 downto 0) := (others => '0');
begin
  process (clk)
  begin
    if rising_edge(clk) then
      if rst = '1' then
        reg <= (others => '0');
      elsif en = '1' then
        reg <= din & reg(WIDTH - 1 downto 1);
      end if;
    end if;
  end process;

  q <= reg;
end architecture rtl;
