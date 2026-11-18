# Read the netlist extracted from the layout
set layout [readnet spice $::env(LAYOUT_SPICE)]

# Read the standard cells, then the routed netlist that uses them
set source [readnet spice $::env(CELL_SPICE)]
readnet verilog $::env(POWER_NETLIST) $source

# Compare layout and netlist with the SKY130 rules
lvs "$layout counter4" "$source counter4" $::env(NETGEN_SETUP) $::env(LVS_REPORT)
