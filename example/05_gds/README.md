# 05. GDS

This stage turns the routed design into the GDSII layout. It only builds the
file; every check on it runs in [06_signoff](../06_signoff/README.md).

## Files

| File | Purpose |
| --- | --- |
| [run_gds.py](run_gds.py) | Merges the routed DEF with the cell layouts |
| [prepare_gds.py](prepare_gds.py) | Adds pin shapes, pin names and power labels to the GDS |
| [Makefile](Makefile) | Stage entry point |

## Steps

| Step | Tool | Action |
| --- | --- | --- |
| `gds_merge` | KLayout + ORFS `def2stream.py` | Read `6_final.def` (cell names, positions, wires) and copy in each cell's polygons from `sky130_fd_sc_hd.gds` |
| `gds_pins` | KLayout + `prepare_gds.py` | Add pin shapes and labels, label the VDD/VSS power stripes, write the LVS copy |

The DEF only names each cell; the GDS holds the real shapes. ORFS can write
its own `6_final.gds`; this flow writes the GDS here instead, so the layer map
and pin labels are under its control.

## Run

From this directory:

```sh
make
```

Outputs in `build/`:

| File | Contents |
| --- | --- |
| `counter4.gds` | Final layout (input to step 06) |
| `lvs_input.gds` | Same layout plus a virtual substrate on layer 236/0, for KLayout LVS |
| `mapped.gds` | GDS before pins and labels were added |
| `def2stream_compat.py` | ORFS DEF-to-GDS script patched with the SKY130 layer purposes |
| `klayout_version.log`, `gds_*.log` | Tool logs |

## Exercise

Open `build/counter4.gds` in KLayout. Find the four flip-flops and the
pin labels. Compare it with `mapped.gds` and find the pin shapes that
`prepare_gds.py` added.

Next: [signoff](../06_signoff/README.md).
