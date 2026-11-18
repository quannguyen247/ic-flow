import hashlib
import re
from pathlib import Path

# Stage folder, used for logs and outputs
STAGE = "05_gds"


def assemble(flow):
    output = flow.outputs[STAGE]
    klayout = str(flow.tools / "klayout")
    tech = flow.objects / "klayout.lyt"
    final_def = flow.results / "6_final.def"
    cell_gds = flow.platform / "gds/sky130_fd_sc_hd.gds"
    converter = output / "def2stream_compat.py"
    raw = output / "mapped.gds"
    final = output / "counter4.gds"

    # The GDS scripts need KLayout 0.26.9
    version = flow.run(STAGE, "klayout_version", [klayout, "-v"])
    if "KLayout 0.26.9" not in version:
        raise RuntimeError("GDS assembly requires KLayout 0.26.9")

    # Make the LEF paths in the KLayout technology file absolute
    def absolute_lef(match):
        path = Path(match.group(1))
        if not path.is_absolute():
            path = (flow.results / path).resolve()
        if not path.is_file():
            raise RuntimeError("Missing LEF: " + str(path))
        return "<lef-files>" + str(path) + "</lef-files>"

    text, count = re.subn(r"<lef-files>([^<]+)</lef-files>", absolute_lef, tech.read_text())
    if count != 2:
        raise RuntimeError("Expected two LEFs in the KLayout technology file")
    tech.write_text(text)

    # Patch the ORFS DEF-to-GDS script with the SKY130 layer purposes
    upstream = (flow.orfs / "flow/util/def2stream.py").read_text()
    anchor = "layoutOptions = tech.load_layout_options\n"
    if upstream.count(anchor) != 1:
        raise RuntimeError("Unexpected ORFS DEF-to-GDS converter version")

    mapping = (
        "config = layoutOptions.lefdef_config\n"
        "config.routing_suffix = '.drawing'\n"
        "config.routing_datatype = 20\n"
        "config.via_geometry_suffix = '.drawing'\n"
        "config.via_geometry_datatype = 44\n"
        "config.pins_suffix = '.pin'\n"
        "config.pins_datatype = 16\n"
    )
    converter.write_text(upstream.replace(anchor, anchor + mapping))

    # Remove outputs of an earlier attempt so a silent tool failure cannot reuse them
    for stale in (raw, final, output / "lvs_input.gds"):
        stale.unlink(missing_ok=True)

    # Merge the routed DEF with the standard-cell GDS
    flow.run(STAGE, "gds_merge", [
        klayout, "-zz",
        "-rd", "design_name=counter4",
        "-rd", "in_def=" + str(final_def),
        "-rd", "in_files=" + str(cell_gds),
        "-rd", "seal_file=",
        "-rd", "out_file=" + str(raw),
        "-rd", "tech_file=" + str(tech),
        "-rd", "layer_map=",
        "-r", str(converter),
    ])

    # Add pin shapes and power labels; also write the LVS input
    flow.run(STAGE, "gds_pins", [
        klayout, "-zz",
        "-rd", "in_gds=" + str(raw),
        "-rd", "in_def=" + str(final_def),
        "-rd", "out_gds=" + str(final),
        "-rd", "lvs_gds=" + str(output / "lvs_input.gds"),
        "-r", str(flow.inputs / STAGE / "prepare_gds.py"),
    ])

    if not final.is_file() or not final.stat().st_size:
        raise RuntimeError("GDS assembly produced no output")

    flow.record(gds=str(final), gds_sha256=hashlib.sha256(final.read_bytes()).hexdigest())
