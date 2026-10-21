-- =============================================================================
-- tb_pkg.vhd  --  shared testbench constants and helpers
-- REFERENCE IMPLEMENTATION WRITTEN IN 2026.
-- =============================================================================
library ieee;
use ieee.std_logic_1164.all;

package tb_pkg is

  -- Reference segment patterns, written out by hand from the digit shapes
  -- (independent of the K-map equations under test). Bit order: g f e d c b a.
  type seg_table_t is array (0 to 9) of std_logic_vector(6 downto 0);
  constant SEG_TABLE : seg_table_t := (
    0 => "0111111",  -- a b c d e f
    1 => "0000110",  -- b c
    2 => "1011011",  -- a b d e g
    3 => "1001111",  -- a b c d g
    4 => "1100110",  -- b c f g
    5 => "1101101",  -- a c d f g
    6 => "1111101",  -- a c d e f g
    7 => "0000111",  -- a b c
    8 => "1111111",  -- all
    9 => "1101111"   -- a b c d f g
  );

  -- 1.8432 MHz crystal. 542.535 ns is within 1 ppm of the exact period.
  constant CLK_PERIOD : time := 542535 ps;
  -- 57 600 baud = exactly 32 crystal periods per bit
  constant BIT_TIME   : time := 32 * CLK_PERIOD;

  function to_bits(v : std_logic_vector) return string;
  function to_hex(v : std_logic_vector(7 downto 0)) return string;

end package tb_pkg;

package body tb_pkg is

  function to_bits(v : std_logic_vector) return string is
    variable s : string(1 to v'length);
    variable i : positive := 1;
  begin
    for k in v'range loop
      s(i) := std_logic'image(v(k))(2);
      i := i + 1;
    end loop;
    return s;
  end function;

  function to_hex(v : std_logic_vector(7 downto 0)) return string is
    constant HEX : string(1 to 16) := "0123456789ABCDEF";
    variable hi, lo : natural := 0;
  begin
    for k in 7 downto 4 loop
      hi := hi * 2;
      if v(k) = '1' then hi := hi + 1; end if;
    end loop;
    for k in 3 downto 0 loop
      lo := lo * 2;
      if v(k) = '1' then lo := lo + 1; end if;
    end loop;
    return "0x" & HEX(hi + 1) & HEX(lo + 1);
  end function;

end package body tb_pkg;
