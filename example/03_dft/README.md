# 03. DFT

Fault inserts a scan chain into the synthesized netlist, then generates
stuck-at test patterns (ATPG). The RTL in step 01 stays unchanged.

## Files

| File | Purpose |
| --- | --- |
| [run_dft.py](run_dft.py) | Runs Fault and Yosys for this stage |
| [sky130.yml](sky130.yml) | Tells Fault the SKY130HD flip-flop pin names |
| [map_scan.tcl](map_scan.tcl) | Maps Fault's scan netlist back to SKY130HD cells |
| [tb_scan.sv](tb_scan.sv) | Scan chain testbench |
| [Makefile](Makefile) | Stage entry point |

## Flow

| Step | Tool | Action |
| --- | --- | --- |
| `fault chain` | Fault | Add scan muxes and the five scan ports |
| `map_scan.tcl` | Yosys | Keep the 4-FF scan core and map it to SKY130HD |
| Simulation | Icarus | Run `tb_counter4` and `tb_scan` on the scan netlist |
| `fault cut` | Fault | Cut the scan FFs into pseudo inputs/outputs |
| `fault atpg` | Fault | Generate stuck-at patterns and coverage |

## Run

From this directory:

```sh
make chain   # scan insertion and simulation
make atpg    # test pattern generation
make         # both
```

Outputs in `build/`:

| File | Contents |
| --- | --- |
| `counter4_scan.v` | Scan netlist (input to step 04) |
| `chain.json` | Scan chain order |
| `scan_cell_statistics.rpt` | Cell counts and area after scan |
| `sim_post_dft.log` | Functional test on the scan netlist |
| `sim_post_dft_scan.log` | Scan test on the scan netlist |
| `cut.v`, `patterns.json`, `coverage.yml` | ATPG netlist, patterns and coverage |
| `fault_*.log`, `scan_mapping.log` | Tool logs |

## Scan ports

| Port | Normal mode | Shift mode |
| --- | --- | --- |
| `test_mode` | 0 | 1 |
| `scan_enable` | 0 | 1 |
| `scan_clk` | 0 | pulsed |
| `scan_in` | 0 | serial data in |
| `scan_out` | unused | serial data out |

Change modes while both clocks are low.

Fault also writes a boundary wrapper; `map_scan.tcl` drops it and keeps the
internal 4-FF chain. The full Fault output is in
`build/counter4.chain-intermediate.v`. ATPG patterns are checked by Fault's own
Icarus backend, separately from the Icarus simulations above.

## Exercise

Compare `build/counter4_scan.v` with `../02_synthesis/build/counter4_synth.v`.
Find the five new ports and the added muxes. Follow the four FFs in the order
given in `chain.json`. Then read `tb_scan.sv` to see how a word is shifted in,
captured and shifted out.

Next: [physical design](../04_physical/README.md).
