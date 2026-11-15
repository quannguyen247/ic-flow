# Allow Yosys commands directly
yosys -import

# Read the functional RTL
read_verilog $::env(RTL_FILE)

# Synthesize and optimize counter4
synth -top counter4

# Map generic flip-flops to SKY130HD flip-flops
dfflibmap -liberty $::env(LIBERTY)

# Map generic combinational logic to SKY130HD gates
abc -liberty $::env(LIBERTY)

# Remove unused wires and cells
clean

# Check for problems
check

# Write cell counts and area to the report
tee -o $::env(SYNTH_REPORT) stat -liberty $::env(LIBERTY)

# Write the gate-level netlist without attributes
write_verilog -noattr $::env(SYNTH_NETLIST)
