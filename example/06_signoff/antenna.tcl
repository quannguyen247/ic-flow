# Read the layout libraries and the routed design
read_lef $::env(TECH_LEF)
read_lef $::env(CELL_LEF)
read_db $::env(FINAL_ODB)

# Check the antenna rules on every net
check_antennas -verbose
