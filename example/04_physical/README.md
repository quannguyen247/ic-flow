# 04. Physical design

OpenROAD (through ORFS) places and routes the scan netlist from step 03. The
RTL is not synthesized again here.

## Files

| File | Purpose |
| --- | --- |
| [config.mk](config.mk) | Design name, platform, input netlist and core size |
| [constraint.sdc](constraint.sdc) | Functional timing: `clk` at 10 ns, scan off |
| [scan_shift.sdc](scan_shift.sdc) | Scan-shift timing: `scan_clk` at 100 ns |
| [run_physical.sh](run_physical.sh) | Feeds the scan netlist to ORFS and runs it |
| [Makefile](Makefile) | Stage entry point |

## Flow

| Step | Action |
| --- | --- |
| `floorplan` | Set the core size, rows, pins, tap cells and power grid |
| `place` | Place the cells |
| `cts` | Build the clock tree |
| `route` | Route the signal wires |

## Run

From this directory:

```sh
make floorplan
make place
make cts
make route
make         # all of the above
```

Outputs in `build/`:

| File | Contents |
| --- | --- |
| `floorplan.odb` | Design after floorplan |
| `placement.odb` | Design after placement |
| `cts.odb` | Design after clock tree synthesis |
| `routing.odb` | Design after routing |
| `final.odb`, `final.def` | Routed design after ORFS `finish` (written by `make gds`, read by step 05) |
| `reports/`, `logs/` | ORFS reports and logs |

When `make gds` runs the ORFS `finish` step, the driver checks that the ORFS
input is byte-identical to `../03_dft/build/counter4_scan.v`. In functional mode `rst_n` is timed like a
synchronous input (reset recovery and removal checks); in scan-shift mode it
is held at 1. Step 06 times both modes in every corner.

## Exercise

Open the `.odb` files in OpenROAD and compare the clock net before and after
CTS. Change `CORE_UTILIZATION` from 20 to 30 in `config.mk`, rerun, and
compare the core size and routing. Set it back to 20 afterwards.

Next: [GDS](../05_gds/README.md).
