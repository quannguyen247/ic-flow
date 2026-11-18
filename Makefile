.DEFAULT_GOAL := help
.NOTPARALLEL:
PYTHON ?= python3

.PHONY: help doctor sim synth chain atpg dftsim dft floorplan place cts route gds drc lvs lec sta signoff package check all fresh view3d test
help doctor sim synth chain atpg dftsim dft floorplan place cts route gds drc lvs lec sta signoff package check all fresh view3d:
	$(MAKE) -C example $@

test:
	$(PYTHON) -m unittest discover -s example/scripts -p 'test_*.py' -v
