# Read the SKY130HD cell timing
read_liberty $::env(LIBERTY)

# Read the technology and cell layouts
read_lef $::env(TECH_LEF)
read_lef $::env(CELL_LEF)

# Read the routed design
read_db $::env(FINAL_ODB)

# Read the timing constraints for this mode
read_sdc $::env(TIMING_SDC)

# Read the extracted wire parasitics
read_spef $::env(FINAL_SPEF)

# Use the real clock tree delays
set_propagated_clock [all_clocks]

# Print the timing mode
puts "Timing mode: $::env(TIMING_MODE)"

# Check for missing constraints and unclocked flip-flops
check_setup -verbose

# Report the worst setup and recovery slack
puts "SETUP_CHECK"
report_worst_slack -max

# Report the worst hold and removal slack
puts "HOLD_CHECK"
report_worst_slack -min

# Count the slew, capacitance and fanout limit violations
puts "DRV_CHECK slew [sta::max_slew_violation_count] cap [sta::max_capacitance_violation_count] fanout [sta::max_fanout_violation_count]"

# Report the full setup and hold paths
report_checks -path_delay min_max -format full_clock_expanded

# Report the reset recovery and removal paths
report_checks -path_delay min_max -from [get_ports rst_n]

# Report the slew and capacitance margins
report_check_types -max_slew -max_capacitance -max_fanout
