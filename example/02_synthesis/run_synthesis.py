# Stage folder, used for logs and outputs
STAGE = "02_synthesis"


def run(flow):
    rtl = flow.inputs / "01_rtl/counter4.v"
    script = flow.inputs / STAGE / "synth.tcl"
    netlist = flow.synth_netlist
    report = flow.outputs[STAGE] / "cell_statistics.rpt"

    # Inputs and outputs read by synth.tcl
    env = flow.environment()
    env["RTL_FILE"] = str(rtl)
    env["SYNTH_NETLIST"] = str(netlist)
    env["SYNTH_REPORT"] = str(report)

    # -Q: no banner, -T: no footer, -c: run a Tcl script
    flow.run(STAGE, "synthesis", ["yosys", "-Q", "-T", "-c", str(script)], env)

    if not netlist.is_file():
        raise RuntimeError(f"Yosys did not create {netlist.name}")
