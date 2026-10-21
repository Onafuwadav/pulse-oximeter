-- =============================================================================
-- rx_control.vhd  --  UART receive control logic (state machine + counters)
--
-- REFERENCE IMPLEMENTATION WRITTEN IN 2026, following the scheme in the module
-- handout: 8x oversampling, start bit confirmed by four consecutive low
-- samples (which lands the sampling point near the middle of the start bit),
-- then one sample every 8 ticks for the 8 data bits and the stop bit.
--
--   IDLE  --rx=0-->  START  --4th consecutive 0-->  DATA  --8 bits-->  STOP
--     ^                |  rx=1 (glitch)                                  |
--     +----------------+-------------<--- stop bit = 1 ------------------+
--     ^                                                                  |
--     +---- rx=1 ----  WAIT_IDLE  <--------- stop bit = 0 ---------------+
--
-- Outputs are registered single-cycle pulses:
--   shift_en    : shift the current rx value into the shift register
--   byte_done   : a full byte has been received with a valid (high) stop bit
--   framing_err : the stop bit was sampled low; the byte is discarded
--
-- Returning to IDLE at the middle of the stop bit (rather than its end) lets a
-- start bit that immediately follows the stop bit be caught, as the handout
-- requires ("the line does not need to go idle between characters").
--
-- WAIT_IDLE is an addition in this rewrite: after a framing error the line may
-- still be low (e.g. a break or a disconnected cable), and without it the
-- receiver would read that low level as a fresh start bit and invent a 0xFF.
-- =============================================================================
library ieee;
use ieee.std_logic_1164.all;

entity rx_control is
  generic (
    OVERSAMPLE    : positive := 8;  -- ticks per bit
    START_SAMPLES : positive := 4;  -- consecutive low samples to accept a start bit
    DATA_BITS     : positive := 8
  );
  port (
    clk         : in  std_logic;
    rst         : in  std_logic;
    tick        : in  std_logic;    -- oversampling enable from clk_div
    rx          : in  std_logic;    -- already synchronised to clk
    shift_en    : out std_logic;
    byte_done   : out std_logic;
    framing_err : out std_logic
  );
end entity rx_control;

architecture rtl of rx_control is
  type state_t is (IDLE, START, DATA, STOP, WAIT_IDLE);
  signal state     : state_t := IDLE;
  signal zeros     : natural range 0 to START_SAMPLES - 1 := 0;  -- start-bit detector
  signal tick_cnt  : natural range 0 to OVERSAMPLE - 1 := 0;     -- "count to 8" counter
  signal bit_cnt   : natural range 0 to DATA_BITS - 1 := 0;      -- "count to 9/10" counter
begin

  process (clk)
  begin
    if rising_edge(clk) then
      -- default: pulses last one clock
      shift_en    <= '0';
      byte_done   <= '0';
      framing_err <= '0';

      if rst = '1' then
        state    <= IDLE;
        zeros    <= 0;
        tick_cnt <= 0;
        bit_cnt  <= 0;

      elsif tick = '1' then
        case state is

          when IDLE =>
            if rx = '0' then          -- first low sample: possible start bit
              zeros <= 0;
              state <= START;
              if START_SAMPLES = 1 then
                state <= DATA; tick_cnt <= 0; bit_cnt <= 0;
              end if;
            end if;

          when START =>
            if rx = '1' then          -- went high again: noise, not a start bit
              state <= IDLE;
            elsif zeros = START_SAMPLES - 2 then
              -- this is the START_SAMPLES-th consecutive low sample:
              -- we are roughly half way through the start bit
              state    <= DATA;
              tick_cnt <= 0;
              bit_cnt  <= 0;
            else
              zeros <= zeros + 1;
            end if;

          when DATA =>
            if tick_cnt = OVERSAMPLE - 1 then   -- one bit period later: mid-bit
              tick_cnt <= 0;
              shift_en <= '1';
              if bit_cnt = DATA_BITS - 1 then
                state <= STOP;
              else
                bit_cnt <= bit_cnt + 1;
              end if;
            else
              tick_cnt <= tick_cnt + 1;
            end if;

          when STOP =>
            if tick_cnt = OVERSAMPLE - 1 then   -- middle of the stop bit
              tick_cnt <= 0;
              if rx = '1' then
                byte_done <= '1';
                state     <= IDLE;
              else
                framing_err <= '1';
                state       <= WAIT_IDLE;
              end if;
            else
              tick_cnt <= tick_cnt + 1;
            end if;

          when WAIT_IDLE =>                     -- after a framing error
            if rx = '1' then
              state <= IDLE;
            end if;

        end case;
      end if;
    end if;
  end process;

end architecture rtl;
