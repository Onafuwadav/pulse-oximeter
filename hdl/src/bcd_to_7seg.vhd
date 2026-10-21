-- =============================================================================
-- bcd_to_7seg.vhd  --  BCD digit to seven-segment decoder
--
-- REFERENCE IMPLEMENTATION WRITTEN IN 2026, written the way the module asked
-- for it: as minimised sum-of-products equations from Karnaugh maps rather
-- than as a lookup table.
--
-- Inputs b3..b0 (b3 = MSB). Codes 10-15 never occur in BCD, so they were
-- treated as "don't care" cells in the K-maps; that is what makes the
-- equations this short. The output for 10-15 is therefore meaningless, and
-- display_top blanks the digit instead of showing it.
--
-- Output is active-high per segment, bit order seg(0) = a ... seg(6) = g:
--
--        a
--      f   b
--        g
--      e   c
--        d
--
-- Segment equations (' = NOT):
--   a = b3 + b1 + b2.b0 + b2'.b0'
--   b = b2' + b1'.b0' + b1.b0
--   c = b2 + b1' + b0
--   d = b3 + b2'.b0' + b2'.b1 + b1.b0' + b2.b1'.b0
--   e = b2'.b0' + b1.b0'
--   f = b3 + b1'.b0' + b2.b1' + b2.b0'
--   g = b3 + b2'.b1 + b2.b1' + b1.b0'
--
-- With these, 6 and 9 are drawn with their "tails" (segment a on 6,
-- segment d on 9) and 7 is drawn as a, b, c.
-- =============================================================================
library ieee;
use ieee.std_logic_1164.all;

entity bcd_to_7seg is
  port (
    bcd : in  std_logic_vector(3 downto 0);
    seg : out std_logic_vector(6 downto 0)   -- g f e d c b a, active high
  );
end entity bcd_to_7seg;

architecture kmap of bcd_to_7seg is
  signal b3, b2, b1, b0 : std_logic;
begin
  b3 <= bcd(3);
  b2 <= bcd(2);
  b1 <= bcd(1);
  b0 <= bcd(0);

  seg(0) <= b3 or b1 or (b2 and b0) or (not b2 and not b0);                                      -- a
  seg(1) <= (not b2) or (not b1 and not b0) or (b1 and b0);                                      -- b
  seg(2) <= b2 or (not b1) or b0;                                                                -- c
  seg(3) <= b3 or (not b2 and not b0) or (not b2 and b1) or (b1 and not b0) or (b2 and not b1 and b0); -- d
  seg(4) <= (not b2 and not b0) or (b1 and not b0);                                              -- e
  seg(5) <= b3 or (not b1 and not b0) or (b2 and not b1) or (b2 and not b0);                     -- f
  seg(6) <= b3 or (not b2 and b1) or (b2 and not b1) or (b1 and not b0);                         -- g
end architecture kmap;
