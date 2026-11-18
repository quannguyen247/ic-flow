# Read the layout libraries and the routed design
read_lef $::env(TECH_LEF)
read_lef $::env(CELL_LEF)
read_db $::env(FINAL_ODB)

# Write the netlist with power pins, for LVS
write_verilog -include_pwr_gnd $::env(POWER_NETLIST)
