-- =============================================================================
-- uart_rx.vhd  --  UART receiver: synchroniser + control logic + shift register
--
-- REFERENCE IMPLEMENTATION WRITTEN IN 2026.
--
-- 57 600 baud, 8 data bits, no parity, 1 stop bit (8N1), matching the link
-- specification in the module handout.
-- =============================================================================
library ieee;
use ieee.std_logic_1164.all;

entity uart_rx is
  port (
    clk         : in  std_logic;
    rst         : in  std_logic;
    tick        : in  std_logic;                     -- 8x baud enable
    rx          : in  std_logic;                     -- asynchronous serial input
    data        : out std_logic_vector(7 downto 0);  -- last good byte
    valid       : out std_logic;                     -- one-clock pulse per good byte
    framing_err : out std_logic                      -- one-clock pulse per bad stop bit
  );
end entity uart_rx;

architecture rtl of uart_rx is
  -- Two-flop synchroniser. The rx line comes from another board with its own
  -- clock, so it is asynchronous to clk; idling high keeps reset quiet.
  signal rx_meta, rx_sync : std_logic := '1';

  signal shift_en, byte_done, ferr : std_logic;
  signal shreg                     : std_logic_vector(7 downto 0);
  signal data_reg                  : std_logic_vector(7 downto 0) := (others => '0');
begin

  sync : process (clk)
  begin
    if rising_edge(clk) then
      if rst = '1' then
        rx_meta <= '1';
        rx_sync <= '1';
      else
        rx_meta <= rx;
        rx_sync <= rx_meta;
      end if;
    end if;
  end process sync;

  u_ctrl : entity work.rx_control
    generic map (OVERSAMPLE => 8, START_SAMPLES => 4, DATA_BITS => 8)
    port map (
      clk         => clk,
      rst         => rst,
      tick        => tick,
      rx          => rx_sync,
      shift_en    => shift_en,
      byte_done   => byte_done,
      framing_err => ferr
    );

  u_shift : entity work.shift_reg
    generic map (WIDTH => 8)
    port map (
      clk => clk,
      rst => rst,
      en  => shift_en,
      din => rx_sync,
      q   => shreg
    );

  -- Output register: only updated when a complete, correctly framed byte
  -- has arrived, so the outputs never show a half-shifted value.
  out_reg : process (clk)
  begin
    if rising_edge(clk) then
      valid <= '0';
      if rst = '1' then
        data_reg <= (others => '0');
      elsif byte_done = '1' then
        data_reg <= shreg;
        valid    <= '1';
      end if;
    end if;
  end process out_reg;

  data        <= data_reg;
  framing_err <= ferr;

end architecture rtl;
