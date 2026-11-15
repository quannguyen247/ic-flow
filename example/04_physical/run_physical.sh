#!/usr/bin/env bash
set -euo pipefail

# Folder where ORFS expects the synthesis results
results="$RUN_DIR/results/sky130hd/counter4/base"
mkdir -p "$results"

# Copy a file only if it changed, so ORFS does not redo later stages
copy_if_changed() {
  if ! cmp -s "$1" "$2"; then
    cp -p "$1" "$2"
  fi
}

# Use the scan netlist from step 03 as the ORFS synthesis result
copy_if_changed "$DFT_NETLIST" "$results/1_synth.v"
copy_if_changed "$FLOW_CONSTRAINTS" "$results/1_synth.sdc"

# Run ORFS; --old-file stops it from running its own synthesis
exec make -C "$ORFS_ROOT/flow" \
  --old-file="$results/1_synth.v" \
  --old-file="$results/1_synth.sdc" \
  DESIGN_CONFIG="$DESIGN_CONFIG" \
  WORK_HOME="$RUN_DIR" \
  DFT_NETLIST="$DFT_NETLIST" \
  FLOW_CONSTRAINTS="$FLOW_CONSTRAINTS" \
  OPENROAD_EXE="$OPENROAD_EXE" \
  YOSYS_EXE="$YOSYS_EXE" \
  KLAYOUT_CMD="$KLAYOUT_CMD" \
  NUM_CORES="$CORES" \
  "$@"
