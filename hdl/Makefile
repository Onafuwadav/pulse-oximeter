# VHDL reference implementation (written in 2026) -- build and run testbenches.
#
#   make            # run all testbenches with GHDL (default)
#   make SIM=nvc    # same with the nvc simulator
#   make wave       # also dump tb_display_top.vcd for a waveform viewer
#   make clean

SIM   ?= ghdl
BUILD := build

SRC := src/clk_div.vhd \
       src/shift_reg.vhd \
       src/rx_control.vhd \
       src/uart_rx.vhd \
       src/bcd_to_7seg.vhd \
       src/display_top.vhd

TB  := tb/tb_pkg.vhd \
       tb/tb_bcd_to_7seg.vhd \
       tb/tb_display_top.vhd

TESTS := tb_bcd_to_7seg tb_display_top

.PHONY: all test wave clean

all: test

test: $(SIM)-test

# ---------------------------------------------------------------- GHDL
ghdl-test:
	mkdir -p $(BUILD)
	cd $(BUILD) && ghdl -a --std=08 $(addprefix ../,$(SRC) $(TB))
	@for t in $(TESTS); do \
	  echo "== $$t"; \
	  (cd $(BUILD) && ghdl -e --std=08 $$t && ghdl -r --std=08 $$t --assert-level=error) || exit 1; \
	done

# ---------------------------------------------------------------- nvc
nvc-test:
	mkdir -p $(BUILD)
	nvc --std=2008 --work=work:$(BUILD)/work -a $(SRC) $(TB)
	@for t in $(TESTS); do \
	  echo "== $$t"; \
	  nvc --std=2008 --work=work:$(BUILD)/work -e $$t -r --exit-severity=error || exit 1; \
	done

wave:
	mkdir -p $(BUILD)
ifeq ($(SIM),nvc)
	nvc --std=2008 --work=work:$(BUILD)/work -a $(SRC) $(TB)
	nvc --std=2008 --work=work:$(BUILD)/work -e tb_display_top -r --format=vcd --wave=$(BUILD)/tb_display_top.vcd
else
	cd $(BUILD) && ghdl -a --std=08 $(addprefix ../,$(SRC) $(TB))
	cd $(BUILD) && ghdl -e --std=08 tb_display_top && ghdl -r --std=08 tb_display_top --vcd=tb_display_top.vcd
endif

clean:
	rm -rf $(BUILD)
