import json
import math
import re

# Stage folder, used for logs and outputs
STAGE = "03_dft"
# Fault 0.9.4 sometimes crashes (SIGSEGV) in ATPG; the seed is fixed, so a rerun is identical
ATPG_ATTEMPTS = 2
# One SKY130HD reset flip-flop instance; group 1 is its name
FLOP = re.compile(r"sky130_fd_sc_hd__dfrtp_\d+\s+(\S+)\s*\(")


def fault_result(metadata: dict, vectors: list[dict]) -> dict:
    """Validate compacted coverage and derive counts from the covered sets."""
    def normalize(name: str) -> str:
        return name.lstrip("\\")

    sites = {normalize(name) for name in metadata["faultPoints"]}
    if not sites or len(sites) != len(metadata["faultPoints"]):
        raise RuntimeError("Empty or ambiguous fault sites")
    count, consistent = 0, True
    for kind in ("sa0", "sa1"):
        covered = {normalize(name) for name in metadata[kind + "Covered"]}
        uncovered = {normalize(name) for name in metadata[kind + "Uncovered"]}
        from_vectors = {normalize(name) for vector in vectors for name in vector["coverage"][kind]}
        if not covered <= sites or covered != from_vectors:
            raise RuntimeError("Covered fault sites disagree with compacted test vectors")
        consistent &= uncovered == sites - covered
        count += len(covered)
    total = 2 * len(sites)
    ratio = count / total
    reported_ratio = float(metadata["ratio"])
    if not math.isfinite(reported_ratio) or abs(ratio - reported_ratio) > 0.00001:
        raise RuntimeError("Fault coverage ratio disagrees with the covered site sets")
    return {"simulator": "Fault internal Icarus backend", "fault_sites": len(sites),
            "detected_stuck_faults": count, "total_stuck_faults": total,
            "uncovered_stuck_faults": total - count,
            "coverage_percent": round(100 * ratio, 4), "compacted_vectors": len(vectors),
            "reported_uncovered_lists_consistent": bool(consistent),
            "scope": "pre-layout cut scan netlist; scan_enable=0, test_mode=0; pseudo-I/O vectors"}


def insert_scan(flow):
    folder = flow.outputs[STAGE]
    config = flow.inputs / STAGE / "sky130.yml"
    script = flow.inputs / STAGE / "map_scan.tcl"
    liberty = flow.platform / "lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
    chained = folder / "counter4.chained.v"
    raw = folder / "counter4.chain-intermediate.v"
    report = folder / "scan_cell_statistics.rpt"

    # Fault adds the scan chain and the five scan ports
    flow.run(STAGE, "fault_chain", [
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
    flow.run(STAGE, "scan_mapping", ["yosys", "-Q", "-T", "-c", str(script)], env)

    flops = FLOP.findall(flow.scan_netlist.read_text())
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

    folder = flow.outputs[STAGE]
    patterns = folder / "patterns.json"
    coverage = folder / "coverage.yml"
    run_fault_atpg(flow, folder / "cut.v", patterns, coverage)

    # Check that the coverage numbers agree with the pattern list
    metadata = yaml.safe_load(coverage.read_text())
    result = fault_result(metadata, json.loads(patterns.read_text())["coverageList"])

    detected, missed = scan_test_atpg_misses(flow, metadata)
    total = 2 * len(metadata["faultPoints"])
    if result["detected_stuck_faults"] + detected + len(missed) != total:
        raise RuntimeError("Fault counts do not add up")

    flop_detected, flop_missed = scan_test_flop_pins(flow)
    flop_faults = flop_detected + len(flop_missed)
    detected += flop_detected
    missed += flop_missed
    total += flop_faults

    result["scan_test_detected_stuck_faults"] = detected
    result["flip_flop_pin_faults_added"] = flop_faults
    result["undetected_stuck_faults"] = missed
    result["total_fault_list"] = total
    result["total_coverage_percent"] = round(100.0 * (total - len(missed)) / total, 4)
    result["total_coverage_scope"] = ("Fault list plus flip-flop CLK/RESET_B/Q pins; "
                                      "ATPG patterns plus serial scan test (tb_scan.sv) in Icarus")
    flow.record(fault_atpg=result)


def run_fault_atpg(flow, cut, patterns, coverage):
    """Cut the scan flip-flops and generate stuck-at patterns with scan held off."""
    # Fault cuts the scan flip-flops into pseudo inputs/outputs
    flow.run(STAGE, "fault_cut", [
        "fault", "cut",
        "--clock", "clk",
        "--reset", "rst_n", "--reset-active-low",
        "--scl-config", str(flow.inputs / STAGE / "sky130.yml"),
        "-o", str(cut),
        str(flow.scan_netlist),
    ])
    if FLOP.search(cut.read_text()):
        raise RuntimeError("Fault did not cut the scan flip-flops")

    command = [
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
    ]
    output = run_retrying_on_crash(flow, "fault_atpg", command)
    if "Simulations concluded: Coverage" not in output:
        raise RuntimeError("Fault did not complete its ATPG campaign")


def run_retrying_on_crash(flow, name, command):
    """Run a command again when a signal killed it; a normal failure is raised at once."""
    for attempt in range(1, ATPG_ATTEMPTS + 1):
        try:
            return flow.run(STAGE, name, command)
        except RuntimeError as error:
            if "(exit -" not in str(error) or attempt == ATPG_ATTEMPTS:
                raise
            print(f"[{name}] killed by a signal; retrying ({attempt}/{ATPG_ATTEMPTS - 1})", flush=True)


def scan_test_atpg_misses(flow, metadata):
    """Fault-simulate tb_scan on every fault ATPG left uncovered.

    ATPG holds scan_enable and test_mode at 0, so it cannot see faults on the
    scan path; the scan testbench (shift, capture, shift) can.
    """
    detected, missed = 0, []
    for value in (0, 1):
        covered = {name.lstrip("\\") for name in metadata["sa%dCovered" % value]}
        for site in metadata["faultPoints"]:
            if site.lstrip("\\") in covered:
                continue
            if scan_test_detects(flow, site, value):
                detected += 1
            else:
                missed.append("%s/sa%d" % (site, value))
    return detected, missed


def scan_test_flop_pins(flow):
    """Fault-simulate the CLK, RESET_B and Q pins that Fault's cut list lacks."""
    detected, missed = 0, []
    for flop in FLOP.findall(flow.scan_netlist.read_text()):
        for pin in ("CLK", "RESET_B", "Q"):
            for value in (0, 1):
                if scan_test_detects(flow, flop + "." + pin, value):
                    detected += 1
                else:
                    missed.append("%s.%s/sa%d" % (flop, pin, value))
    return detected, missed


def inject_fault(netlist, site, value):
    instance, pin = site.lstrip("\\").split(".")
    pin = "D" if pin == "d" else pin
    cell = re.search(r"sky130_fd_sc_hd__\w+ %s \((.*?)\);" % re.escape(instance), netlist, re.S)
    if cell is None:
        raise RuntimeError("Fault site not in scan netlist: " + site)

    pins = cell.group(1)
    connection = re.search(r"\.%s\(([^)]*)\)" % pin, pins)
    if connection is None:
        raise RuntimeError("Fault site pin not in scan netlist: " + site)
    constant = "1'b%d" % value

    # Input pin: tie it to the constant
    if pin not in ("X", "Y", "Q"):
        pins = pins.replace(connection.group(0), ".%s(%s)" % (pin, constant))
        return netlist[:cell.start(1)] + pins + netlist[cell.end(1):]

    # Output pin: disconnect it and drive its net with the constant
    pins = pins.replace(connection.group(0), ".%s(fault_open)" % pin)
    netlist = netlist[:cell.start(1)] + pins + netlist[cell.end(1):]
    header = netlist.index(");") + 2
    netlist = netlist[:header] + "\n  wire fault_open;\n" + netlist[header:]
    driver = "  assign %s = %s;\nendmodule" % (connection.group(1).strip(), constant)
    return netlist.replace("endmodule", driver, 1)


def scan_test_detects(flow, site, value):
    folder = flow.outputs[STAGE] / "scan_test_faults"
    folder.mkdir(exist_ok=True)
    name = re.sub(r"\W", "_", site.lstrip("\\")) + "_sa%d" % value
    netlist = folder / (name + ".v")
    simulation = folder / (name + ".vvp")
    netlist.write_text(inject_fault(flow.scan_netlist.read_text(), site, value))

    # The fault is detected when tb_scan no longer prints its PASS line
    flow.run(STAGE, "scan_fault_" + name + "_compile", [
        "iverilog", "-g2012",
        "-s", "tb_scan",
        "-o", str(simulation),
        str(flow.cell_models), str(netlist), str(flow.inputs / STAGE / "tb_scan.sv"),
    ])
    output = flow.run(STAGE, "scan_fault_" + name, ["vvp", "-n", str(simulation)])
    return "PASS: inserted scan chain" not in output
