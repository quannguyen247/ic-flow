# 02. Synthesis

Yosys maps the RTL counter to SKY130HD standard cells and writes a gate-level
netlist. Scan is added later, in step 03.

## Files

| File | Purpose |
| --- | --- |
| [synth.tcl](synth.tcl) | Yosys synthesis script |
| [run_synthesis.py](run_synthesis.py) | Sets the file paths and runs Yosys |
| [Makefile](Makefile) | Stage entry point |

## Script

| Command | Action |
| --- | --- |
| `read_verilog` | Read `counter4.v` |
| `synth` | Generic synthesis and optimization |
| `dfflibmap` | Map flip-flops to SKY130HD cells |
| `abc` | Map logic gates to SKY130HD cells |
| `clean` | Remove unused wires and cells |
| `check` | Report undriven or multi-driven nets |
| `stat` | Write cell counts and area |
| `write_verilog` | Write the netlist |

## Run

From this directory:

```sh
make
```

Outputs in `build/`:

| File | Contents |
| --- | --- |
| `counter4_synth.v` | Netlist |
| `cell_statistics.rpt` | Cell counts and area |
| `synthesis.log` | Yosys log |
| `sim_post_synth.log` | Step 01 testbench run on the netlist |

The netlist simulation has no gate delays (no SDF).

## Exercise

Compare `../01_rtl/counter4.v` with `build/counter4_synth.v`. Find the four
`sky130_fd_sc_hd__dfrtp_1` flip-flops and their `CLK`, `D`, `Q` and `RESET_B`
pins. Count the other cells in `build/cell_statistics.rpt`. Check that the
netlist has no `scan_in`, `scan_enable` or `test_mode` port yet.

Next: [DFT](../03_dft/README.md).
