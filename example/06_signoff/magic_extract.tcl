# Work in the signoff folder, where Magic writes its .ext files
cd $::env(SIGNOFF_DIR)

# Read the final layout
gds read $::env(GDS_FILE)
load counter4
select top cell

# Extract the devices and wires
extract do local
extract all

# Write a SPICE netlist for LVS
ext2spice lvs
ext2spice -o $::env(LAYOUT_SPICE)

quit -noprompt
