yosys -import

# Read the reference design (gold) and flatten it
read_verilog $::env(CELL_MODELS)
read_verilog -sv {*}$::env(GOLD_FILES)
hierarchy -top $::env(GOLD_TOP)
yosys proc
flatten
yosys rename $::env(GOLD_TOP) gold
design -stash gold

# Read the implementation (gate) and flatten it
read_verilog $::env(CELL_MODELS)
read_verilog -sv {*}$::env(GATE_FILES)
hierarchy -top $::env(GATE_TOP)
yosys proc
flatten
yosys rename $::env(GATE_TOP) gate
design -stash gate

# Pair the outputs and the matching nets of both designs
design -copy-from gold -as gold gold
design -copy-from gate -as gate gate
equiv_make gold gate equiv
hierarchy -top equiv

# Treat the asynchronous reset as a normal input for the proof
async2sync

# Prove each pair, then by induction over clock cycles
equiv_simple -seq 5
equiv_induct -seq 5

# Fail if any pair is not proven
equiv_status -assert
