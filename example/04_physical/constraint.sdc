# Functional mode: the inserted clock mux selects clk.
create_clock -name core_clk -period 10 [get_ports clk]
set_case_analysis 0 [get_ports {test_mode scan_enable scan_in scan_clk}]
set_input_delay -clock core_clk 1 [get_ports enable]
set_output_delay -clock core_clk 1 [all_outputs]
set_false_path -from [get_ports rst_n]
