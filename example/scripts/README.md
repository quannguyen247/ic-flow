# Shared driver and environment

[run.py](run.py) manages prerequisites, snapshots, logs and result summaries.
Tool commands live in the numbered stage directories. Each stage has a local
Makefile and a `build/` link to its generated outputs.

## Environment overview

Defaults come from `settings()` in [run.py](run.py); set a variable in the
environment or in `example/local.mk` to override it.

| Variable | Default |
| --- | --- |
| `ORFS_ROOT` | `~/.cache/tcl-train/orfs-68b1f261` |
| `OPENROAD_IMAGE` | `~/.local/share/eda/openroad.sif` |
| `KLAYOUT_IMAGE` | `docker.io/efabless/openlane:v0.22` |
| `IC_FLOW_WORK_ROOT` | `~/.cache/ic-flow` |
| `CORES` | `4` |
| `PDK_ROOT` | `~/.local/share/eda/pdk-digital` |
| `KLAYOUT_PY` | `~/.local/share/eda/klayout-venv/bin/python` (only `make view3d`) |

Use ORFS revision `68b1f26134c63d072a19b3a514c5a99effd08501` and KLayout
0.26.9. SKY130HD data comes from this ORFS snapshot. Host tools are Python
3.10+, PyYAML, Make, Yosys, Icarus Verilog, Fault, Magic, Netgen, Apptainer and
Podman.

Override settings in `example/local.mk`. For example:

```make
ORFS_ROOT = /absolute/path/to/pinned-orfs
OPENROAD_IMAGE = /absolute/path/to/openroad.sif
CORES = 2
```

ORFS, image and cache paths must have no whitespace. The repository path may
contain spaces. Images must already be installed; the driver does not download
them. Run `make doctor` to check tools and `make sim` to check the simulator.

## Storage and dependencies

Changed stage inputs create a new cached run. Verified synthesis and DFT
outputs are reused within that snapshot. `make fresh` starts another run and
keeps earlier outputs; use it after changing installed tools.

The summary records running, failed or passed status. Commands and stdout/stderr
are kept in `driver_logs/` and linked into each stage's `build/`. A lock prevents
concurrent writes. Physical inputs are checked against the DFT netlist.

Run `make test` from the root for driver regressions. `make all` exercises the
actual tools, including post-insertion and post-route scan simulation.

Physical design reuses ORFS. GDS compatibility code is adapted from
[tcl-train](https://github.com/quannguyen247/tcl-train), under MIT.
