import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

# Stage folder, used for logs and outputs
STAGE = "06_signoff"


MODES = {"functional": "constraint.sdc", "scan_shift": "scan_shift.sdc"}
CORNERS = ("ss_100C_1v60", "ss_n40C_1v60", "tt_025C_1v80", "ff_n40C_1v95", "ff_100C_1v95")
RC_CORNERS = ("min", "nom", "max")


def prepare_reference(top_path: Path, combined_path: Path, out_path: Path) -> int:
    """Write the LVS reference CDL without tap cells; return the tap count."""
    top = top_path.read_text()
    lines = top.splitlines()
    taps = sum(line.startswith("XTAP_TAPCELL_") for line in lines)
    if not taps:
        raise RuntimeError("No expected tap instances found in the reference CDL")
    top = "\n".join(line for line in lines if not line.startswith("XTAP_TAPCELL_")) + "\n"
    source = combined_path.read_text().replace(" topography=normal", "")
    source = "\n".join(line.replace(" / ", " ") if line.lstrip().upper().startswith("X") else line
                       for line in source.splitlines()) + "\n"
    blocks = {match.group(1).lower(): match.group(0) for match in re.finditer(
        r"(?ims)^\.SUBCKT\s+(\S+)[^\n]*\n.*?^\.ENDS[^\n]*\n", source)}
    used = {name.lower() for name in re.findall(r"sky130_fd_sc_hd__\w+", top, re.I)}
    pending = list(used)
    while pending:
        cell = pending.pop()
        if cell not in blocks:
            raise RuntimeError("Missing CDL definition: " + cell)
        for dep in re.findall(r"sky130_fd_sc_hd__\w+", blocks[cell], re.I):
            dep = dep.lower()
            if dep != cell and dep not in used:
                used.add(dep)
                pending.append(dep)
    if not used:
        raise RuntimeError("No functional cells found in reference CDL")
    out_path.write_text(top + "\n" + "".join(blocks[cell] for cell in sorted(used)))
    return taps


def layout_env(flow):
    env = flow.environment()
    env["TECH_LEF"] = str(flow.platform / "lef/sky130_fd_sc_hd.tlef")
    env["CELL_LEF"] = str(flow.platform / "lef/sky130_fd_sc_hd_merged.lef")
    env["FINAL_ODB"] = str(flow.results / "6_final.odb")
    return env


def lec(flow):
    script = flow.inputs / STAGE / "lec.tcl"
    rtl = flow.inputs / "01_rtl/counter4.v"
    wrapper = flow.inputs / STAGE / "scan_off.v"
    routed = flow.results / "6_final.v"

    # Each pair: (name, gold files, gold top, gate files, gate top)
    pairs = (
        ("rtl_vs_synth", [rtl], "counter4", [flow.synth_netlist], "counter4"),
        ("rtl_vs_scan_off", [rtl], "counter4", [flow.scan_netlist, wrapper], "scan_off"),
        ("scan_vs_route", [flow.scan_netlist], "counter4", [routed], "counter4"),
    )

    results = {}
    for name, gold, gold_top, gate, gate_top in pairs:
        # Inputs read by lec.tcl
        env = flow.environment()
        env["CELL_MODELS"] = str(flow.cell_models)
        env["GOLD_FILES"] = " ".join(str(path) for path in gold)
        env["GOLD_TOP"] = gold_top
        env["GATE_FILES"] = " ".join(str(path) for path in gate)
        env["GATE_TOP"] = gate_top

        log = flow.run(STAGE, "lec_" + name, ["yosys", "-Q", "-T", "-c", str(script)], env)
        proven = re.search(r"Of those cells (\d+) are proven and 0 are unproven", log)
        if proven is None or "Equivalence successfully proven!" not in log:
            raise RuntimeError("LEC failed: " + name)
        results[name] = "equivalent (%s output and net pairs)" % proven.group(1)

    flow.record(lec=results)


def extract_rc(flow):
    folder = flow.outputs[STAGE]
    rules = flow.pdk / "libs.tech/librelane"
    spefs = {}

    for corner in RC_CORNERS:
        # Inputs read by extract_rc.tcl
        env = layout_env(flow)
        env["RCX_RULES"] = str(rules / ("rules.openrcx.sky130A." + corner + ".calibre"))
        env["SPEF_FILE"] = str(folder / ("counter4_" + corner + ".spef"))

        script = flow.inputs / STAGE / "extract_rc.tcl"
        Path(env["SPEF_FILE"]).unlink(missing_ok=True)
        flow.run(STAGE, "rcx_" + corner, [str(flow.tools / "openroad"), "-exit", str(script)], env)
        if not Path(env["SPEF_FILE"]).is_file():
            raise RuntimeError("RC extraction wrote no SPEF for " + corner)
        spefs[corner] = Path(env["SPEF_FILE"])

    return spefs


def run_sta(flow, name, mode, liberty, spef):
    # Inputs read by sta.tcl
    env = layout_env(flow)
    env["LIBERTY"] = str(liberty)
    env["FINAL_SPEF"] = str(spef)
    env["TIMING_SDC"] = str(flow.inputs / "04_physical" / MODES[mode])
    env["TIMING_MODE"] = mode

    script = flow.inputs / STAGE / "sta.tcl"
    log = flow.run(STAGE, name, [str(flow.tools / "openroad"), "-exit", str(script)], env)

    # check_setup prints "There are N ..." for unclocked or unconstrained pins
    if re.search(r"There (is|are) \d+", log):
        raise RuntimeError("Missing timing constraints in " + name)

    # Read the worst slacks and limit violations printed by sta.tcl
    setup = re.search(r"SETUP_CHECK\s+worst slack\s+(-?[0-9.]+)", log)
    hold = re.search(r"HOLD_CHECK\s+worst slack\s+(-?[0-9.]+)", log)
    drv = re.search(r"DRV_CHECK slew (\d+) cap (\d+) fanout (\d+)", log)
    if setup is None or hold is None or drv is None:
        raise RuntimeError("Missing STA summary for " + name)

    return {
        "setup_slack_ns": float(setup.group(1)),
        "hold_slack_ns": float(hold.group(1)),
        "limit_violations": sum(int(value) for value in drv.groups()),
    }


def sta(flow):
    spefs = extract_rc(flow)
    libs = flow.pdk / "libs.ref/sky130_fd_sc_hd/lib"
    results = {}

    # Every cell corner with every wire corner, in both modes
    for corner in CORNERS:
        liberty = libs / ("sky130_fd_sc_hd__" + corner + ".lib")
        for rc in RC_CORNERS:
            for mode in MODES:
                name = "sta_%s_%s_%s" % (corner, rc, mode)
                results[corner + "/" + rc + "/" + mode] = run_sta(flow, name, mode, liberty, spefs[rc])

    worst = {
        "setup_slack_ns": min(value["setup_slack_ns"] for value in results.values()),
        "hold_slack_ns": min(value["hold_slack_ns"] for value in results.values()),
        "limit_violations": sum(value["limit_violations"] for value in results.values()),
    }
    flow.record(sta={"worst": worst, "runs": results})

    if worst["setup_slack_ns"] < 0 or worst["hold_slack_ns"] < 0:
        raise RuntimeError("Timing violation: %s" % worst)
    if worst["limit_violations"]:
        raise RuntimeError("Slew, capacitance or fanout violation: %s" % worst)


def klayout_drc(flow):
    source = flow.platform / "drc/sky130hd.lydrc"
    deck = flow.outputs[STAGE] / "drc_full.lydrc"
    report = flow.outputs[STAGE] / "drc.lyrdb"

    # The ORFS deck turns front-end (FEOL) rules off; turn them on
    text = source.read_text()
    scope = (r"FEOL\s*=\s*false", r"BEOL\s*=\s*true", r"OFFGRID\s*=\s*true")
    if not all(re.search(pattern, text) for pattern in scope):
        raise RuntimeError("Unexpected DRC deck scope")
    deck.write_text(re.sub(r"FEOL\s*=\s*false", "FEOL = true", text, count=1))

    report.unlink(missing_ok=True)
    flow.run(STAGE, "drc", [
        str(flow.tools / "klayout"), "-zz",
        "-rd", "in_gds=" + flow.summary["gds"],
        "-rd", "report_file=" + str(report),
        "-r", str(deck),
    ])

    # Each <item> in the report is one DRC error
    count = len(ET.parse(report).getroot().findall(".//item"))
    flow.record(drc_items=count, drc_scope="FEOL, BEOL and off-grid")
    if count:
        raise RuntimeError("DRC reported %d items: %s" % (count, report))


def klayout_lvs(flow):
    output = flow.outputs[STAGE]
    klayout = str(flow.tools / "klayout")
    reference = output / "functional_reference.cdl"
    deck = output / "lvs_compat.lylvs"
    report = output / "lvs.lvsdb"

    # Build the reference netlist without tap cells
    taps = prepare_reference(
        flow.results / "6_final.cdl",
        flow.objects / "6_final_concat.cdl",
        reference,
    )

    # Patch the ORFS deck to write an LVS database
    source = (flow.platform / "lvs/sky130hd.lylvs").read_text()
    if source.count("  report($report_file)") != 1:
        raise RuntimeError("Unexpected LVS deck format")
    deck.write_text(source.replace("  report($report_file)", "  report_lvs($report_file)"))

    # Compare the layout with the reference netlist
    log = flow.run(STAGE, "lvs", [
        klayout, "-b",
        "-rd", "in_gds=" + str(flow.outputs["05_gds"] / "lvs_input.gds"),
        "-rd", "cdl_file=" + str(reference),
        "-rd", "report_file=" + str(report),
        "-rd", "target_netlist=" + str(output / "counter4_extracted.cir"),
        "-r", str(deck),
    ])
    if "Netlists match." not in log or "Netlists don't match" in log:
        raise RuntimeError("LVS did not report a match")

    # Check every circuit pair in the LVS database
    log = flow.run(STAGE, "lvs_database", [
        klayout, "-zz",
        "-rd", "lvs_file=" + str(report),
        "-r", str(flow.inputs / STAGE / "check_lvs.py"),
    ])
    if "LVS database:" not in log or "ERROR" in log:
        raise RuntimeError("LVS database contains unmatched circuit pairs")

    flow.record(
        lvs="matched with virtual substrate and functional-cell reference",
        tap_instances_excluded_from_reference=taps,
    )


def physical_checks(flow):
    """Magic DRC, Magic + Netgen LVS and the antenna check."""
    results = {"magic_drc_errors": magic_drc(flow)}
    results["netgen_lvs"] = netgen_lvs(flow)
    results["antenna_violations"] = antenna(flow)
    flow.record(physical_signoff=results)


def magic_command(flow):
    return ["magic", "-dnull", "-noconsole", "-rcfile", str(flow.pdk / "libs.tech/magic/sky130A.magicrc")]


def magic_drc(flow):
    """Magic DRC with the full SKY130 deck, on the flattened layout."""
    env = flow.environment()
    env["GDS_FILE"] = flow.summary["gds"]
    log = flow.run(STAGE, "magic_drc", magic_command(flow) + [str(flow.inputs / STAGE / "magic_drc.tcl")], env)
    total = re.search(r"MAGIC_DRC_TOTAL (\d+)", log)
    if total is None:
        raise RuntimeError("Magic DRC did not finish")
    if int(total.group(1)):
        raise RuntimeError("Magic DRC found %s errors" % total.group(1))
    return int(total.group(1))


def netgen_lvs(flow):
    """Magic extracts the layout, OpenROAD writes the power netlist, Netgen compares them."""
    folder = flow.outputs[STAGE]
    layout_spice = folder / "counter4_layout.spice"
    power_netlist = folder / "counter4_pwr.v"
    lvs_report = folder / "lvs_netgen.rpt"

    env = flow.environment()
    env["GDS_FILE"] = flow.summary["gds"]
    env["SIGNOFF_DIR"] = str(folder)
    env["LAYOUT_SPICE"] = str(layout_spice)
    layout_spice.unlink(missing_ok=True)
    flow.run(STAGE, "magic_extract", magic_command(flow) + [str(flow.inputs / STAGE / "magic_extract.tcl")], env)
    if not layout_spice.is_file():
        raise RuntimeError("Magic did not write the layout netlist")

    env = layout_env(flow)
    env["POWER_NETLIST"] = str(power_netlist)
    script = flow.inputs / STAGE / "write_netlist.tcl"
    flow.run(STAGE, "write_power_netlist", [str(flow.tools / "openroad"), "-exit", str(script)], env)

    env = flow.environment()
    env["LAYOUT_SPICE"] = str(layout_spice)
    env["CELL_SPICE"] = str(flow.pdk / "libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice")
    env["POWER_NETLIST"] = str(power_netlist)
    env["NETGEN_SETUP"] = str(flow.pdk / "libs.tech/netgen/sky130A_setup.tcl")
    env["LVS_REPORT"] = str(lvs_report)
    log = flow.run(STAGE, "netgen_lvs", ["netgen", "-batch", "source",
                                         str(flow.inputs / STAGE / "netgen_lvs.tcl")], env)
    if "Circuits match uniquely." not in log[log.rfind("Final result"):]:
        raise RuntimeError("Netgen LVS mismatch: " + str(lvs_report))
    return "Circuits match uniquely"


def antenna(flow):
    """OpenROAD antenna check on the routed design; returns the violation count."""
    script = flow.inputs / STAGE / "antenna.tcl"
    log = flow.run(STAGE, "antenna", [str(flow.tools / "openroad"), "-exit", str(script)], layout_env(flow))
    nets = re.search(r"Found (\d+) net violations", log)
    pins = re.search(r"Found (\d+) pin violations", log)
    if nets is None or pins is None:
        raise RuntimeError("Antenna check did not finish")
    violations = int(nets.group(1)) + int(pins.group(1))
    if violations:
        raise RuntimeError("Antenna check found violations")
    return violations


def package(flow):
    folder = flow.outputs[STAGE]
    output = folder / "handoff"
    output.mkdir(exist_ok=True)

    # Files to hand off, by their name in the package
    sources = {
        "counter4.gds": Path(flow.summary["gds"]),
        "counter4.v": flow.results / "6_final.v",
        "counter4.def": flow.results / "6_final.def",
        "functional.sdc": flow.inputs / "04_physical/constraint.sdc",
        "scan_shift.sdc": flow.inputs / "04_physical/scan_shift.sdc",
    }
    for corner in RC_CORNERS:
        sources["counter4_" + corner + ".spef"] = folder / ("counter4_" + corner + ".spef")

    # Copy each file and record its SHA-256
    hashes = {}
    for name, source in sources.items():
        shutil.copyfile(source, output / name)
        hashes[name] = hashlib.sha256((output / name).read_bytes()).hexdigest()

    checks = ("drc_items", "drc_scope", "lvs", "sim_post_route", "sim_post_route_scan", "lec", "physical_signoff")
    manifest = {
        "design": "counter4",
        "foundry_signoff": False,
        "files_sha256": hashes,
        "checks": {key: flow.summary[key] for key in checks},
        "sta_worst": flow.summary["sta"]["worst"],
        "scope": flow.summary["scope"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    flow.record(handoff=str(output))
