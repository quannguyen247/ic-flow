# Scan-shift mode: the inserted clock mux selects scan_clk.
create_clock -name scan_clock -period 100 [get_ports scan_clk]
set_case_analysis 1 [get_ports {test_mode scan_enable}]
set_case_analysis 0 [get_ports {enable clk}]
# The tester holds rst_n high while shifting.
set_case_analysis 1 [get_ports rst_n]
set_input_delay -clock scan_clock 10 [get_ports scan_in]
set_output_delay -clock scan_clock 10 [all_outputs]
