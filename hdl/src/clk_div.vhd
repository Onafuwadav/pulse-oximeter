-- =============================================================================
-- clk_div.vhd  --  oversampling tick generator
--
-- REFERENCE IMPLEMENTATION WRITTEN IN 2026. This is not the original Quartus
-- schematic (which is lost); it re-implements the same block in VHDL.
--
-- The display board runs from a 1.8432 MHz crystal. 1.8432 MHz / 57 600 baud
-- = 32 clocks per bit, so 8x oversampling needs one sample tick every
-- 32 / 8 = 4 clocks (460.8 kHz). That is two cascaded divide-by-2 stages in
-- the original schematic.
--
-- Difference from the original: instead of producing a new, derived clock,
-- this block produces a one-clock-wide enable pulse ("tick"). Everything then
-- runs on the single crystal clock, which avoids clock-domain and skew issues
-- and is the usual practice for CPLD/FPGA designs.
-- =============================================================================
library ieee;
use ieee.std_logic_1164.all;

entity clk_div is
  generic (
    DIVIDE : positive := 4   -- 1.8432 MHz / 4 = 460.8 kHz = 8 x 57 600
  );
  port (
    clk  : in  std_logic;
    rst  : in  std_logic;
    tick : out std_logic     -- high for one clk cycle every DIVIDE cycles
  );
end entity clk_div;

architecture rtl of clk_div is
  signal count : natural range 0 to DIVIDE - 1 := 0;
begin
  process (clk)
  begin
    if rising_edge(clk) then
      if rst = '1' then
        count <= 0;
        tick  <= '0';
      elsif count = DIVIDE - 1 then
        count <= 0;
        tick  <= '1';
      else
        count <= count + 1;
        tick  <= '0';
      end if;
    end if;
  end process;
end architecture rtl;
