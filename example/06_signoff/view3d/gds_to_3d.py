#!/usr/bin/env python3
"""Turn a SKY130 GDS into a single-file 3D WebGL viewer (three.js loads from jsDelivr).

Flow:  GDS --(klayout.db: flatten, merge, trapezoids)--> JSON --(three.js)--> HTML

Each drawn layer is flattened from the top cell, merged, split into trapezoids
(convex 3- or 4-point polygons) and given a z range from an approximate SKY130
metal stack. The browser extrudes every trapezoid into a prism. Standard-cell
instances are exported as boxes so the viewer can name the cell under the mouse.

Needs the `klayout` Python module (pip install klayout), not the KLayout GUI.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import klayout.db as kdb
except ImportError:  # pragma: no cover - depends on the environment
    sys.exit("klayout Python module missing: pip install klayout "
             "(or run with ~/.local/share/eda/klayout-venv/bin/python)")

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "viewer_template.html"
PLACEHOLDER = "/*__LAYOUT_JSON__*/null"

# (gds layer, datatype) -> name, z bottom, z top (um), colour, default visible.
# Heights follow the SKY130 stack only roughly; vias span the gap between
# the layers they connect. Implant / marker layers are left out.
SKY130_STACK = [
    ((64, 20), "nwell",  -0.40, -0.05, "#7c8a99", False),
    ((65, 20), "diff",   -0.05,  0.10, "#22c55e", True),
    ((65, 44), "tap",    -0.05,  0.10, "#86efac", True),
    ((66, 20), "poly",    0.33,  0.51, "#ef4444", True),
    ((66, 44), "licon",   0.10,  0.94, "#fde68a", True),
    ((67, 20), "li1",     0.94,  1.04, "#a78bfa", True),
    ((67, 44), "mcon",    1.04,  1.38, "#f5f5f4", True),
    ((68, 20), "met1",    1.38,  1.74, "#3b82f6", True),
    ((68, 44), "via",     1.74,  2.01, "#e7e5e4", True),
    ((69, 20), "met2",    2.01,  2.37, "#ec4899", True),
    ((69, 44), "via2",    2.37,  2.79, "#d6d3d1", True),
    ((70, 20), "met3",    2.79,  3.63, "#14b8a6", True),
    ((70, 44), "via3",    3.63,  4.02, "#d6d3d1", True),
    ((71, 20), "met4",    4.02,  4.86, "#f59e0b", True),
    ((71, 44), "via4",    4.86,  5.37, "#d6d3d1", True),
    ((72, 20), "met5",    5.37,  6.63, "#eab308", True),
]


def layer_region(layout: "kdb.Layout", top: "kdb.Cell", ld: tuple[int, int]):
    index = layout.find_layer(ld[0], ld[1])
    if index is None:
        return None
    region = kdb.Region(top.begin_shapes_rec(index))
    return region.merged() if not region.is_empty() else None


def trapezoid_coords(region: "kdb.Region", dbu: float) -> list[float]:
    """Flat list x0,y0,..,x3,y3 (um) per trapezoid; triangles repeat a point."""
    coords: list[float] = []
    for poly in region.decompose_trapezoids_to_region().each():
        pts = [(p.x * dbu, p.y * dbu) for p in poly.each_point_hull()]
        if len(pts) == 3:
            pts.append(pts[-1])
        if len(pts) != 4:  # decomposition guarantees <= 4; be strict anyway
            raise ValueError(f"unexpected trapezoid with {len(pts)} points")
        for x, y in pts:
            coords.extend((round(x, 3), round(y, 3)))
    return coords


def cell_instances(top: "kdb.Cell", dbu: float, max_count: int) -> list[list]:
    """First-level instances: [name, x0, y0, x1, y1] in um."""
    items: list[list] = []
    for inst in top.each_inst():
        box = inst.bbox()
        items.append([inst.cell.name, round(box.left * dbu, 3), round(box.bottom * dbu, 3),
                      round(box.right * dbu, 3), round(box.top * dbu, 3)])
        if len(items) >= max_count:
            break
    return items


def build_model(gds: Path, top_name: str | None, max_cells: int) -> dict:
    layout = kdb.Layout()
    layout.read(str(gds))
    top = layout.cell(top_name) if top_name else layout.top_cell()
    if top is None:
        raise SystemExit(f"top cell not found in {gds}")
    dbu = layout.dbu
    bbox = top.dbbox()

    layers = []
    for ld, name, z0, z1, colour, visible in SKY130_STACK:
        region = layer_region(layout, top, ld)
        if region is None:
            continue
        coords = trapezoid_coords(region, dbu)
        layers.append({"name": name, "gds": f"{ld[0]}/{ld[1]}", "z0": z0, "z1": z1,
                       "color": colour, "visible": visible, "quads": coords})
        print(f"  {name:6s} {ld[0]}/{ld[1]:<3d} {len(coords) // 8:6d} trapezoids")

    return {
        "design": top.name,
        "source": gds.name,
        "dbu": dbu,
        "bbox": [bbox.left, bbox.bottom, bbox.right, bbox.top],
        "layers": layers,
        "cells": cell_instances(top, dbu, max_cells),
    }


def write_html(model: dict, out: Path) -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise SystemExit(f"placeholder {PLACEHOLDER!r} missing from {TEMPLATE}")
    payload = json.dumps(model, separators=(",", ":")).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(template.replace(PLACEHOLDER, payload), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("gds", type=Path, help="input GDS file")
    parser.add_argument("-o", "--out", type=Path, help="output HTML (default: <design>_3d.html)")
    parser.add_argument("--top", help="top cell name (default: the only top cell)")
    parser.add_argument("--json", type=Path, help="also write the raw model JSON here")
    parser.add_argument("--max-cells", type=int, default=20000, help="cap on exported instances")
    args = parser.parse_args()

    if not args.gds.is_file():
        raise SystemExit(f"GDS not found: {args.gds}")
    print(f"reading {args.gds}")
    model = build_model(args.gds, args.top, args.max_cells)
    out = args.out or Path(f"{model['design']}_3d.html")
    write_html(model, out)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(model), encoding="utf-8")
    size_kb = out.stat().st_size / 1024
    print(f"wrote {out} ({size_kb:.0f} KB, {len(model['cells'])} cell instances)")


if __name__ == "__main__":
    main()
