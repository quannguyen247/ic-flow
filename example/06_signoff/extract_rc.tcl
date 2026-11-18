# Read the layout libraries and the routed design
read_lef $::env(TECH_LEF)
read_lef $::env(CELL_LEF)
read_db $::env(FINAL_ODB)

# Extract the wire parasitics with this corner's rules
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file $::env(RCX_RULES)

# Write them for STA
write_spef $::env(SPEF_FILE)
