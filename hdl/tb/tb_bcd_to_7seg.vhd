-- =============================================================================
-- tb_bcd_to_7seg.vhd  --  exhaustive check of the K-map decoder for 0..9
-- REFERENCE IMPLEMENTATION WRITTEN IN 2026.
-- =============================================================================
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.tb_pkg.all;

entity tb_bcd_to_7seg is
end entity tb_bcd_to_7seg;

architecture sim of tb_bcd_to_7seg is
  signal bcd : std_logic_vector(3 downto 0) := (others => '0');
  signal seg : std_logic_vector(6 downto 0);
begin

  dut : entity work.bcd_to_7seg port map (bcd => bcd, seg => seg);

  stim : process
    variable errors : natural := 0;
  begin
    for d in 0 to 9 loop
      bcd <= std_logic_vector(to_unsigned(d, 4));
      wait for 10 ns;
      if seg /= SEG_TABLE(d) then
        report "digit " & integer'image(d) & ": got " & to_bits(seg)
             & ", expected " & to_bits(SEG_TABLE(d)) severity error;
        errors := errors + 1;
      end if;
    end loop;

    assert errors = 0
      report "tb_bcd_to_7seg FAILED with " & integer'image(errors) & " error(s)"
      severity failure;
    report "tb_bcd_to_7seg PASSED (10/10 digits)";
    wait;
  end process stim;

end architecture sim;
