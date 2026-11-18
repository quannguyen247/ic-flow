.DEFAULT_GOAL := help
.NOTPARALLEL:
PYTHON ?= python3

# Optional machine-specific overrides. See scripts/README.md.
-include local.mk
# Defaults live in settings() in scripts/run.py; set values here only to override
export ORFS_ROOT OPENROAD_IMAGE KLAYOUT_IMAGE IC_FLOW_WORK_ROOT PDK_ROOT CORES
# Python with the klayout pip module, for make view3d (see 06_signoff/view3d/README.md)
KLAYOUT_PY ?= $(HOME)/.local/share/eda/klayout-venv/bin/python

.PHONY: help doctor sim synth chain atpg dftsim dft floorplan place cts route gds drc lvs lec sta signoff package check all fresh test view3d
help:
	@printf '%s\n' \
	  'make doctor     Check the installed tools and the pinned ORFS platform' \
	  'make sim        Simulate RTL with Icarus Verilog' \
	  'make synth      Map RTL to SKY130HD cells with Yosys via ORFS' \
	  'make dft        Insert scan with Fault, simulate and run ATPG' \
	  'make floorplan  Create the core, pins and power grid' \
	  'make place      Place standard cells' \
	  'make cts        Build the clock tree' \
	  'make route      Route signal wires' \
	  'make gds        Write the GDS from the routed DEF (05_gds)' \
	  'make drc        KLayout DRC on the GDS (06_signoff)' \
	  'make lvs        KLayout LVS on the GDS (06_signoff)' \
	  'make lec        Prove RTL, synth, scan and routed netlists equivalent' \
	  'make sta        STA in 5 PVT x 3 RC corners, functional and scan-shift mode' \
	  'make signoff    All of 06: DRC, LVS, post-route sim, LEC, STA, antenna' \
	  'make check      Same as make signoff' \
	  'make package    Signoff plus the handoff folder (06_signoff/build/handoff)' \
	  'make all        Run sim -> synth -> dft -> physical -> gds -> signoff' \
	  'make fresh      Start a new output directory; keep previous runs' \
	  'make test       Run driver regressions' \
	  'make view3d     3D WebGL viewer of the GDS (06_signoff/view3d/build)'

doctor sim synth chain atpg dftsim dft floorplan place cts route gds drc lvs lec sta signoff package check all fresh:
	$(PYTHON) scripts/run.py $@

test:
	$(MAKE) -C .. test

# 3D layout viewer, part of 06_signoff
view3d:
	$(KLAYOUT_PY) 06_signoff/view3d/gds_to_3d.py 05_gds/build/counter4.gds \
	  -o 06_signoff/view3d/build/counter4_3d.html --json 06_signoff/view3d/build/counter4_3d.json
