# Counter RTL-to-GDSII walkthrough

Start with a four-bit counter: active-low asynchronous reset, count enable,
and modulo-16 rollover. Its RTL has four ports and no test hardware.
The later stages add scan, build layout and check the result.

## Flow overview

```text
01_rtl/counter4.v
    -> 02_synthesis/build/counter4_synth.v
    -> 03_dft/build/counter4_scan.v
    -> 04_physical/build/{floorplan,placement,cts,routing}.odb
    -> 05_gds/build/counter4.gds
    -> 06_signoff/build/handoff/
```

## Practice sequence

From `example/`, run each command and inspect its output before continuing:

| Command | Read or change | Inspect afterward |
| --- | --- | --- |
| `make -C 01_rtl` | `counter4.v`, `tb_counter4.sv` | `01_rtl/build/rtl/` and `sim_rtl.log` |
| `make -C 02_synthesis` | `synth.tcl` | `02_synthesis/build/counter4_synth.v`, `cell_statistics.rpt` |
| `make -C 03_dft` | `sky130.yml`, `map_scan.tcl`, `tb_scan.sv` | `03_dft/build/counter4_scan.v`, `chain.json`, `patterns.json` |
| `make -C 04_physical` | `config.mk`, timing SDCs, `run_physical.sh` | `04_physical/build/routing.odb` and stage reports |
| `make -C 05_gds` | `run_gds.py`, `prepare_gds.py` | `05_gds/build/counter4.gds` |
| `make -C 06_signoff` | `run_signoff.py`, `sta.tcl`, `lec.tcl` | `06_signoff/build/drc.lyrdb`, `lvs.lvsdb`, `lec_*.log`, `sta_*.log`, `handoff/` |
| `make view3d` | `06_signoff/view3d/gds_to_3d.py` | `06_signoff/view3d/build/counter4_3d.html` |

Each stage has a Makefile, scripts, a guide and a short exercise. Missing
prerequisites are built automatically. Verified synthesis and DFT outputs are
reused while inputs remain unchanged.

## Run storage

The source tree may contain spaces. Inputs are snapshotted into a cache path
without spaces, selected by a source/configuration fingerprint. Every numbered
`build/` link points to its stage in that run. `build/latest/` holds the complete
run, including `run.json`, `summary.json` and `driver_logs/`.

A changed script, RTL or constraint creates a new run and keeps the old outputs.
Use `make fresh` after changing installed tools. Failures are recorded in the
summary and named logs. Tool versions and measured limits are in
[REF_RESULT.md](REF_RESULT.md).

Direct simulations use Icarus Verilog (`iverilog` + `vvp`), the same simulator Fault uses for ATPG.
The final package is an educational core; the
[signoff guide](06_signoff/README.md) defines the checks performed.
