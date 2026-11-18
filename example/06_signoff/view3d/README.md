# 06 · 3D layout viewer (GDS → KLayout Python → WebGL)

Part of [06_signoff](../README.md). It turns the final layout
`05_gds/build/counter4.gds` into one HTML file that shows the chip in 3D in a
browser. No signoff check depends on it; it is for looking at the layout and
making pictures.

## How it works

```text
counter4.gds
  │  klayout.db (pip module, not the GUI)
  │    1. read GDS, take the top cell
  │    2. per SKY130 layer: Region(top.begin_shapes_rec(layer))   ← flatten all cells
  │    3. .merged()                                                ← join touching shapes
  │    4. .decompose_trapezoids_to_region()                        ← convex 3/4-point pieces
  │    5. give each layer a z range (approximate SKY130 stack)
  ▼
JSON {design, bbox, layers[{name, gds, z0, z1, color, quads[]}], cells[[name, box]]}
  │  embedded into viewer_template.html (placeholder /*__LAYOUT_JSON__*/null)
  ▼
build/counter4_3d.html   ← three.js extrudes every trapezoid into a prism
```

The data is embedded in the HTML, so it opens straight from disk
(`file://`), no web server needed. three.js 0.160.0 loads from jsDelivr, so
the first open needs internet.

## Files

| File | Purpose |
| --- | --- |
| [gds_to_3d.py](gds_to_3d.py) | GDS → layer trapezoids + cell boxes → HTML (and optional JSON) |
| [viewer_template.html](viewer_template.html) | three.js viewer; the script fills in the data |
| [../Makefile](../Makefile) | `make view3d` entry point |

## Setup (once)

The KLayout the flow runs (0.26.9 in the OpenLane image named by
`KLAYOUT_IMAGE`) has no importable Python module. Install the pip package in its
own venv instead:

```sh
python3 -m venv ~/.local/share/eda/klayout-venv
~/.local/share/eda/klayout-venv/bin/pip install klayout     # tested: 0.30.13
```

## Run

From `example/` (`make -C 06_signoff view3d` does the same):

```sh
make view3d                                  # after make gds
xdg-open 06_signoff/view3d/build/counter4_3d.html
```

By hand, for any SKY130 GDS:

```sh
~/.local/share/eda/klayout-venv/bin/python gds_to_3d.py path/to/design.gds \
    -o build/design_3d.html --json build/design_3d.json [--top TOPCELL]
```

`KLAYOUT_PY=/other/python make view3d` picks another interpreter.

## Viewer controls

| Control | Effect |
| --- | --- |
| Drag / right-drag / wheel | Rotate / pan / zoom |
| Iso, Top, Side | Camera presets |
| Z scale | Exaggerate heights (the die is 42 µm wide, the stack ~6 µm tall) |
| Explode layers | Lift each layer apart to see the stack |
| Opacity | See through metal |
| All / Metal only / FEOL only | Layer presets |
| Cell boxes | Outline every standard-cell instance |
| Hover | Layer, x/y in µm and the cell under the pointer |
| Save PNG | Download the current view as an image |

## Layer stack used

| Layer | GDS | z (µm) | | Layer | GDS | z (µm) |
| --- | --- | --- | --- | --- | --- | --- |
| nwell (hidden) | 64/20 | −0.40…−0.05 | | met1 | 68/20 | 1.38…1.74 |
| diff | 65/20 | −0.05…0.10 | | via | 68/44 | 1.74…2.01 |
| tap | 65/44 | −0.05…0.10 | | met2 | 69/20 | 2.01…2.37 |
| poly | 66/20 | 0.33…0.51 | | via2 | 69/44 | 2.37…2.79 |
| licon | 66/44 | 0.10…0.94 | | met3 | 70/20 | 2.79…3.63 |
| li1 | 67/20 | 0.94…1.04 | | via3 | 70/44 | 3.63…4.02 |
| mcon | 67/44 | 1.04…1.38 | | met4 / via4 / met5 | 71/20, 71/44, 72/20 | 4.02…6.63 |

Implants (nsdm, psdm, lvtn, npc), pin (`x/16`), label (`x/5`) and boundary
layers are skipped. Heights are close to the SKY130 cross-section but not
exact; edit `SKY130_STACK` in `gds_to_3d.py` for another PDK.

## Result for counter4

42.32 × 42.32 µm, 343 instances, 3,935 trapezoids, HTML about 230 KB. The two
orange bars are the met4 power straps, met1 (blue) carries the cell-row rails
and short signal wires, met2 (pink) the vertical routes, including those to the
top and bottom pins, and met3 (teal) the horizontal routes to the left and right pins.

A copy of the viewer for the reference run (see `../../REF_RESULT.md`) and two
screenshots are kept in the repository's [docs/](../../../docs/) folder. After
a new reference run, regenerate them with `make view3d` and copy
`build/counter4_3d.html` there.

## Limits

- Everything is flattened: fine for blocks up to a few hundred thousand
  shapes. For a big chip, clip to a window or skip li1/licon/mcon.
- The "`.db` file" route (KLayout LVS `lvs.lvsdb`, DRC `drc.lyrdb`) holds
  netlist and marker data, not extra geometry; this viewer reads the GDS.
