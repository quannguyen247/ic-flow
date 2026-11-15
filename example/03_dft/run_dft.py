import json
import re


def insert_scan(flow):
    folder = flow.outputs["03_dft"]
    config = flow.inputs / "03_dft/sky130.yml"
    script = flow.inputs / "03_dft/map_scan.tcl"
    liberty = flow.platform / "lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
    chained = folder / "counter4.chained.v"
    raw = folder / "counter4.chain-intermediate.v"
    report = folder / "scan_cell_statistics.rpt"

    # Fault adds the scan chain and the five scan ports
    flow.run("fault_chain", [
        "fault", "chain",
        "--clock", "clk",
        "--reset", "rst_n", "--reset-active-low",
        "--bypassing", "enable",
        "--scl-config", str(config),
        "--liberty", str(liberty),
        "--sin", "scan_in",
        "--sout", "scan_out",
        "--shift", "scan_enable",
        "--test", "test_mode",
        "--tck", "scan_clk",
        "--skip-synth",
        "--output", str(chained),
        str(flow.synth_netlist),
    ])

    # Fault writes the chain order into the netlist as JSON
    match = re.search(r"FAULT METADATA: '(.*?)' END FAULT METADATA", raw.read_text())
    if match is None:
        raise RuntimeError("Fault scan metadata missing")
    metadata = json.loads(match.group(1))
    if metadata["internalCount"] != 4:
        raise RuntimeError("Fault must chain four internal flip-flops")

    # Inputs and outputs read by map_scan.tcl
    env = flow.environment()
    env["FAULT_NETLIST"] = str(raw)
    env["SCAN_NETLIST"] = str(flow.scan_netlist)
    env["SCAN_REPORT"] = str(report)

    # -Q: no banner, -T: no footer, -c: run a Tcl script
    flow.run("scan_mapping", ["yosys", "-Q", "-T", "-c", str(script)], env)

    flops = re.findall(r"sky130_fd_sc_hd__dfrtp_1\s+\S+\s*\(", flow.scan_netlist.read_text())
    if len(flops) != 4:
        raise RuntimeError("Mapped scan core must still have four flip-flops")

    # Save the chain order for the exercise and the run summary
    chain = {
        "length": 4,
        "order": [item for item in metadata["order"] if item["kind"] == "dff"],
        "ports_added": ["scan_in", "scan_out", "scan_enable", "scan_clk", "test_mode"],
        "selection": "Fault-generated internal scan core; boundary wrapper omitted",
        "fault_wrapper_boundary_bits_omitted": metadata["boundaryCount"],
    }
    (folder / "chain.json").write_text(json.dumps(chain, indent=2) + "\n")
    flow.record(scan_insertion=chain)


def atpg(flow):
    import yaml

    folder = flow.outputs["03_dft"]
    config = flow.inputs / "03_dft/sky130.yml"
    cut = folder / "cut.v"
    patterns = folder / "patterns.json"
    coverage = folder / "coverage.yml"

    # Fault cuts the scan flip-flops into pseudo inputs/outputs
    flow.run("fault_cut", [
        "fault", "cut",
        "--clock", "clk",
        "--reset", "rst_n", "--reset-active-low",
        "--scl-config", str(config),
        "-o", str(cut),
        str(flow.scan_netlist),
    ])

    if "sky130_fd_sc_hd__dfrtp_1" in cut.read_text():
        raise RuntimeError("Fault did not cut the scan flip-flops")

    # Fault generates stuck-at patterns, with scan held off
    output = flow.run("fault_atpg", [
        "fault", "atpg",
        "--cell-model", str(flow.cell_models),
        "--clock", "clk",
        "--reset", "rst_n", "--reset-active-low",
        "--bypassing", "scan_enable=0",
        "--bypassing", "scan_in=0",
        "--bypassing", "test_mode=0",
        "--bypassing", "scan_clk=0",
        "--rng-seed", "DEADCAFEDEADF00D",
        "--min-coverage", "80",
        "--tv-count", "100",
        "--ceiling", "200",
        "--output-coverage-metadata", str(coverage),
        "-o", str(patterns),
        str(cut),
    ])

    if "Simulations concluded: Coverage" not in output:
        raise RuntimeError("Fault did not complete its ATPG campaign")

    # Check that the coverage numbers agree with the pattern list
    result = flow.validate_coverage(
        yaml.safe_load(coverage.read_text()),
        json.loads(patterns.read_text())["coverageList"],
    )
    flow.record(fault_atpg=result)
