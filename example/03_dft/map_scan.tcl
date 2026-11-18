# Allow Yosys commands directly
yosys -import

# Read the SKY130HD cells as black boxes
read_liberty -lib $::env(LIBERTY)

# Read the scan netlist from Fault
read_verilog $::env(FAULT_NETLIST)

# Keep the internal scan core and drop the Fault wrapper
hierarchy -check -top counter4.original

# Rename the core to counter4
yosys rename counter4.original counter4

# Synthesize and optimize counter4
synth -top counter4

# Map generic flip-flops to SKY130HD flip-flops
dfflibmap -liberty $::env(LIBERTY)

# Map generic combinational logic to SKY130HD gates
abc -liberty $::env(LIBERTY)

# Remove unused wires and cells
clean

# Give each output port its own net (scan_out and count[3] are the same signal)
insbuf -buf sky130_fd_sc_hd__buf_1 A X

# Check for problems
check

# Write cell counts and area to the report
tee -o $::env(SCAN_REPORT) stat -liberty $::env(LIBERTY)

# Write the gate-level netlist without attributes
write_verilog -noattr $::env(SCAN_NETLIST)
