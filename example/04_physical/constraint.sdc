# Functional mode: the inserted clock mux selects clk.
create_clock -name core_clk -period 10 [get_ports clk]
set_case_analysis 0 [get_ports {test_mode scan_enable scan_in scan_clk}]
# I/O budget: 20% of the period outside the block (OpenLane default).
set_input_delay -clock core_clk 2 [get_ports enable]
set_output_delay -clock core_clk 2 [all_outputs]
# rst_n asserts at any time but is released by a reset synchronizer in the
# parent, clocked by clk: time its release (recovery and removal checks).
set_input_delay -clock core_clk 2 [get_ports rst_n]
