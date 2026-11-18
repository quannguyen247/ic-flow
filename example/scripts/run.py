#!/usr/bin/env python3
"""Run one teaching stage with the installed, pinned SKY130HD toolchain.

Adapted from tcl-train/eda/dft/capstone_scan/local/run_flow.py (MIT).
ORFS, the PDK and container images are read-only inputs. No downloads occur.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

EXAMPLE = Path(__file__).resolve().parents[1]
EXPECTED_ORFS = "68b1f26134c63d072a19b3a514c5a99effd08501"
PASS = "PASS: counter reset, count, rollover and hold"
STAGES = ("doctor", "sim", "synth", "chain", "atpg", "dftsim", "dft", "floorplan", "place", "cts", "route",
          "gds", "drc", "lvs", "lec", "sta", "signoff", "package", "check", "all", "fresh")
FOLDERS = ("01_rtl", "02_synthesis", "03_dft", "04_physical", "05_gds", "06_signoff")
SIM_FOLDERS = {"rtl": "01_rtl", "post_synth": "02_synthesis", "post_dft": "03_dft",
               "post_dft_scan": "03_dft", "post_route": "06_signoff", "post_route_scan": "06_signoff"}
PHYSICAL_RESULTS = ("gds", "gds_sha256", "drc_items", "drc_scope", "lvs", "sta",
                    "tap_instances_excluded_from_reference", "sim_post_route", "sim_post_route_scan",
                    "physical_input_sha256", "scope", "handoff",
                    "lec", "physical_signoff")


def require(*tools: str) -> None:
    missing = [tool for tool in tools if not shutil.which(tool)]
    if missing:
        raise RuntimeError("Missing tools: " + ", ".join(missing))


def revision(orfs: Path) -> str:
    if not (orfs / "flow/Makefile").is_file():
        raise RuntimeError(f"ORFS_ROOT must contain flow/Makefile: {orfs}")
    marker = orfs / ".orfs-commit"
    if marker.is_file():
        value = marker.read_text().strip()
    else:
        value = subprocess.check_output(["git", "-C", str(orfs), "rev-parse", "HEAD"], text=True).strip()
    if value != EXPECTED_ORFS:
        raise RuntimeError(f"Expected ORFS {EXPECTED_ORFS}, got {value}. See scripts/README.md.")
    return value


DEFAULTS = {
    "ORFS_ROOT": "~/.cache/tcl-train/orfs-68b1f261",
    "OPENROAD_IMAGE": "~/.local/share/eda/openroad.sif",
    "KLAYOUT_IMAGE": "docker.io/efabless/openlane:v0.22",
    "PDK_ROOT": "~/.local/share/eda/pdk-digital",
    "CORES": "4",
    "IC_FLOW_WORK_ROOT": "~/.cache/ic-flow",
}


def setting(name: str) -> str:
    """Environment value, or the default when unset or empty (make exports unset variables as "")."""
    return os.environ.get(name) or DEFAULTS[name]


def settings() -> dict[str, str]:
    def path(name: str) -> str:
        return str(Path(setting(name)).expanduser().resolve())

    return {
        "orfs": path("ORFS_ROOT"),
        "openroad_image": path("OPENROAD_IMAGE"),
        "klayout_image": setting("KLAYOUT_IMAGE"),
        "pdk_root": path("PDK_ROOT"),
        "cores": setting("CORES"),
        "work_root": path("IC_FLOW_WORK_ROOT"),
    }


def doctor(config: dict[str, str]) -> None:
    require("iverilog", "vvp", "yosys", "fault", "make", "apptainer", "podman", "magic", "netgen")
    pdk = Path(config["pdk_root"]) / "sky130A"
    for name in ("libs.tech/magic/sky130A.magicrc", "libs.tech/netgen/sky130A_setup.tcl",
                 "libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"):
        if not (pdk / name).is_file():
            raise RuntimeError(f"PDK_ROOT must contain sky130A/{name}")
    import yaml
    print(f"PyYAML: {yaml.__version__}")
    print(f"ORFS: {revision(Path(config['orfs']))}")
    if not Path(config["openroad_image"]).is_file():
        raise RuntimeError("OPENROAD_IMAGE does not name an existing SIF file")
    commands = (["iverilog", "-V"], ["yosys", "-V"], ["fault", "--version"],
                ["apptainer", "exec", config["openroad_image"], "openroad", "-version"],
                ["podman", "run", "--rm", "--pull=never", "--network", "none",
                 "--security-opt", "label=disable", "--userns=keep-id",
                 "-e", "QT_QPA_PLATFORM=offscreen", "-e", "HOME=/tmp",
                 "--entrypoint", "/usr/bin/klayout", config["klayout_image"], "-b", "-v"])
    for command in commands:
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
        print(result.stdout.strip())
        if command[0] == "podman" and "KLayout 0.26.9" not in result.stdout:
            raise RuntimeError("The local GDS compatibility scripts require KLayout 0.26.9")
    print("Tools found. No installation or download performed.")


def workspace(config: dict[str, str], fresh: bool) -> Path:
    for key in ("orfs", "openroad_image", "work_root"):
        if any(char.isspace() for char in config[key]):
            raise RuntimeError(f"{key} needs a path without whitespace; the source repository may contain spaces")
    if int(config["cores"]) < 1:
        raise RuntimeError("CORES must be positive")
    sources = [path for folder in FOLDERS
               for path in sorted((EXAMPLE / folder).rglob("*"))
               if "view3d" not in path.relative_to(EXAMPLE).parts and path.suffix in (".v", ".sv", ".tcl", ".mk", ".sdc", ".py", ".yml", ".sh")]
    sources.append(EXAMPLE / "scripts/run.py")
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode())
    for path in sources:
        digest.update(str(path.relative_to(EXAMPLE)).encode())
        digest.update(path.read_bytes())
    fingerprint = digest.hexdigest()
    build = EXAMPLE / "build"
    build.mkdir(exist_ok=True)
    latest = build / "latest"
    if os.path.lexists(latest) and not latest.is_symlink():
        raise RuntimeError(f"Expected a symlink at {latest}; preserving the existing file or directory")
    if latest.is_symlink() and not fresh:
        manifest = latest / "run.json"
        if manifest.is_file() and json.loads(manifest.read_text()).get("fingerprint") == fingerprint:
            return latest.resolve()
    repo_key = hashlib.sha256(str(EXAMPLE).encode()).hexdigest()[:12]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    work = Path(config["work_root"]) / repo_key / stamp
    work.mkdir(parents=True)
    for path in sources:
        target = work / "inputs" / path.relative_to(EXAMPLE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    (work / "run.json").write_text(json.dumps({"fingerprint": fingerprint, "source": str(EXAMPLE),
        "created_utc": stamp, "settings": config}, indent=2) + "\n")
    link = build / f".latest-{os.getpid()}"
    link.symlink_to(work, target_is_directory=True)
    link.replace(latest)
    return work


class Flow:
    def __init__(self, config: dict[str, str], work: Path):
        self.config, self.work = config, work
        self.inputs = work / "inputs"
        self.logs = work / "driver_logs"
        self.logs.mkdir(exist_ok=True)
        self.orfs = Path(config["orfs"])
        self.platform = self.orfs / "flow/platforms/sky130hd"
        self.pdk = (Path(config["pdk_root"]) / "sky130A").resolve()
        self.results = work / "results/sky130hd/counter4/base"
        self.reports = work / "reports/sky130hd/counter4/base"
        self.objects = work / "objects/sky130hd/counter4/base"
        self.tools = work / "tools"
        self.tools.mkdir(exist_ok=True)
        self.outputs = {name: work / name for name in FOLDERS}
        for folder in self.outputs.values():
            folder.mkdir(exist_ok=True)
        self.synth_netlist = self.outputs["02_synthesis"] / "counter4_synth.v"
        self.scan_netlist = self.outputs["03_dft"] / "counter4_scan.v"
        self.cell_models = self.platform / "work_around_yosys/formal_pdk.v"
        self.modules = {}
        self.runtime_ready = False
        self.physical_ready = False
        summary = work / "summary.json"
        self.summary = json.loads(summary.read_text()) if summary.is_file() else {"design": "counter4"}
        self.synth_done = self.synth_netlist.is_file() and str(self.summary.get("sim_post_synth", "")).startswith("passed")
        self.chain_done = self.scan_netlist.is_file() and all(str(self.summary.get(key, "")).startswith("passed")
            for key in ("sim_post_dft", "sim_post_dft_scan"))
        self.atpg_done = "fault_atpg" in self.summary and all((self.outputs["03_dft"] / name).is_file()
            for name in ("cut.v", "patterns.json", "coverage.yml"))
        self.gds_done = self.atpg_done and self.recorded_gds_is_current()

    def recorded_gds_is_current(self) -> bool:
        """True when the GDS in the summary exists and still has its recorded checksum."""
        gds = Path(self.summary.get("gds", ""))
        if not gds.is_file() or not (self.results / "6_final.def").is_file():
            return False
        return hashlib.sha256(gds.read_bytes()).hexdigest() == self.summary.get("gds_sha256")

    def record(self, **values: object) -> None:
        self.summary.update(values)
        temporary = self.work / "summary.json.tmp"
        temporary.write_text(json.dumps(self.summary, indent=2) + "\n")
        temporary.replace(self.work / "summary.json")

    def invalidate(self, *keys: str) -> None:
        """Remove earlier results before repeating a check that may fail."""
        for key in keys:
            self.summary.pop(key, None)
        self.record()

    def execute(self, stage: str) -> None:
        """Run a requested stage and persist success or failure."""
        self.record(requested_stage=stage, status="running", failure=None)
        try:
            if stage == "all":
                self.sim()
                self.synth()
                self.dft()
                self.package()
            elif stage in ("floorplan", "place", "cts", "route"):
                self.invalidate(*PHYSICAL_RESULTS)
                self.physical(stage)
            elif stage != "fresh":
                getattr(self, stage)()
        except Exception as error:
            self.record(status="failed", failure=str(error))
            raise
        self.record(status="passed")

    def run(self, stage: str, name: str, command: list[str], env: dict[str, str] | None = None) -> str:
        """Run a command, keep its log and link the log into the stage folder."""
        if stage not in self.outputs:
            raise RuntimeError(f"Unknown stage folder for {name}: {stage}")
        log = self.logs / (name + ".log")
        link = self.outputs[stage] / (name + ".log")
        if not link.is_symlink():
            link.symlink_to(log)
        print(f"[{name}] {shlex.join(command)}", flush=True)
        with log.open("w") as output:
            output.write("$ " + shlex.join(command) + "\n")
            output.flush()
            result = subprocess.run(command, cwd=self.work, env=env, stdout=output,
                                    stderr=subprocess.STDOUT, check=False)
        content = log.read_text(errors="replace")
        if result.returncode:
            raise RuntimeError(f"{name} failed (exit {result.returncode}): {log}\n" +
                               "\n".join(content.splitlines()[-18:]))
        return content

    def runtime(self) -> None:
        if self.runtime_ready:
            return
        require("make", "yosys", "apptainer")
        import yaml
        self.record(orfs_revision=revision(self.orfs))
        image = Path(self.config["openroad_image"])
        if not image.is_file():
            raise RuntimeError("OPENROAD_IMAGE does not name an existing SIF file")
        runtime = self.tools / "runtime"
        runtime.mkdir(mode=0o700, exist_ok=True)
        py_path = self.tools / "python"
        py_path.mkdir(exist_ok=True)
        if not (py_path / "yaml").is_dir():
            shutil.copytree(Path(yaml.__file__).parent, py_path / "yaml")
        quote = shlex.quote
        openroad = self.tools / "openroad"
        openroad.write_text("#!/bin/sh\nexec apptainer exec "
            f"--bind {quote(str(self.work)+':'+str(self.work))} "
            f"--bind {quote(str(self.orfs)+':'+str(self.orfs)+':ro')} "
            f"--bind {quote(str(self.pdk)+':'+str(self.pdk)+':ro')} "
            f"--env PYTHONPATH={quote(str(py_path))} --env QT_QPA_PLATFORM=offscreen "
            f"--env XDG_RUNTIME_DIR={quote(str(runtime))} --pwd \"$PWD\" {quote(str(image))} openroad \"$@\"\n")
        openroad.chmod(0o755)
        klayout = self.tools / "klayout"
        klayout.write_text("#!/bin/sh\nexec podman run --rm --pull=never --network none "
            "--security-opt label=disable --userns=keep-id -e QT_QPA_PLATFORM=offscreen "
            "-e HOME=/tmp -e XDG_CONFIG_HOME=/tmp/ic-flow-config "
            f"-v {quote(str(self.work)+':'+str(self.work)+':rw')} "
            f"-v {quote(str(self.orfs)+':'+str(self.orfs)+':ro')} "
            f"-w \"$PWD\" --entrypoint /usr/bin/klayout {quote(self.config['klayout_image'])} -b \"$@\"\n")
        klayout.chmod(0o755)
        self.runtime_ready = True

    def stage_module(self, folder: str):
        if folder not in self.modules:
            file = self.inputs / folder / {"02_synthesis": "run_synthesis.py", "03_dft": "run_dft.py",
                                           "05_gds": "run_gds.py", "06_signoff": "run_signoff.py"}[folder]
            spec = importlib.util.spec_from_file_location("stage_" + folder, file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.modules[folder] = module
        return self.modules[folder]

    def environment(self):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env.update(LIBERTY=str(self.platform / "lib/sky130_fd_sc_hd__tt_025C_1v80.lib"))
        return env

    def make(self, name: str, *targets: str) -> None:
        self.runtime()
        env = self.environment()
        env.update(ORFS_ROOT=str(self.orfs), DESIGN_CONFIG=str(self.inputs / "04_physical/config.mk"),
                   RUN_DIR=str(self.work), DFT_NETLIST=str(self.scan_netlist),
                   FLOW_CONSTRAINTS=str(self.inputs / "04_physical/constraint.sdc"),
                   OPENROAD_EXE=str(self.tools / "openroad"), YOSYS_EXE=shutil.which("yosys"),
                   KLAYOUT_CMD=str(self.tools / "klayout"), CORES=self.config["cores"])
        self.run("04_physical", name, ["bash", str(self.inputs / "04_physical/run_physical.sh"), *targets], env)

    def sim(self, name="rtl", netlist=None, scan_test=False):
        self.invalidate("sim_" + name)
        require("iverilog", "vvp")
        if name not in SIM_FOLDERS:
            raise RuntimeError(f"Unknown simulation: {name}")
        folder = SIM_FOLDERS[name]
        top = "tb_scan" if scan_test else "tb_counter4"
        sim_dir = self.outputs[folder] / name
        sim_dir.mkdir(parents=True, exist_ok=True)
        testbench = self.inputs / ("03_dft/tb_scan.sv" if scan_test else "01_rtl/tb_counter4.sv")
        sources = [str(netlist or self.inputs / "01_rtl/counter4.v"), str(testbench)]
        if netlist is not None:
            sources.insert(0, str(self.cell_models))
        self.run(folder, "sim_" + name + "_compile", ["iverilog", "-g2012", "-s", top, "-o", str(sim_dir / "sim.vvp"),
                                              *sources])
        output = self.run(folder, "sim_" + name, ["vvp", "-n", str(sim_dir / "sim.vvp"), f"+vcd={sim_dir / 'waveform.vcd'}"])
        expected = "PASS: inserted scan chain, 16 words and functional capture" if scan_test else PASS
        if expected not in output:
            raise RuntimeError("Simulation finished without the testbench PASS message")
        self.record(**{"sim_" + name: "passed; Icarus functional simulation, no SDF"})
        print(f"PASS: simulation {name}", flush=True)

    def synth(self):
        if not self.synth_done:
            # A new synthesized netlist makes every later result stale
            self.chain_done = self.atpg_done = self.physical_ready = self.gds_done = False
            self.invalidate("sim_post_synth", "scan_insertion", "sim_post_dft", "sim_post_dft_scan",
                            "fault_atpg", *PHYSICAL_RESULTS)
            require("yosys")
            revision(self.orfs)
            self.stage_module("02_synthesis").run(self)
            self.sim("post_synth", self.synth_netlist)
            self.synth_done = True

    def chain(self):
        if not self.chain_done:
            self.synth()
            # A new scan netlist makes ATPG and layout results stale
            self.atpg_done = self.physical_ready = self.gds_done = False
            self.invalidate("scan_insertion", "fault_atpg", "sim_post_dft", "sim_post_dft_scan", *PHYSICAL_RESULTS)
            require("fault", "yosys")
            self.stage_module("03_dft").insert_scan(self)
            self.sim("post_dft", self.scan_netlist)
            self.sim("post_dft_scan", self.scan_netlist, scan_test=True)
            self.chain_done = True

    def atpg(self):
        if self.atpg_done:
            return
        self.chain()
        self.invalidate("fault_atpg")
        require("fault", "iverilog", "vvp")
        self.stage_module("03_dft").atpg(self)
        self.atpg_done = True

    def dftsim(self):
        self.chain()

    def dft(self):
        self.atpg()

    def prepare_physical(self):
        """Make sure the scan netlist and the tool wrappers exist."""
        if not self.physical_ready:
            self.dft()
            self.runtime()
            self.physical_ready = True

    def physical(self, target):
        self.prepare_physical()
        self.make(target, target)
        self.publish_physical()

    def finish_physical(self):
        self.prepare_physical()
        self.make("physical_finish", str(self.results / "6_final.def"), str(self.results / "6_final.sdc"),
                  str(self.objects / "klayout.lyt"), str(self.objects / "6_final_concat.cdl"))
        imported = self.results / "1_synth.v"
        if imported.read_bytes() != self.scan_netlist.read_bytes():
            raise RuntimeError("Physical design did not import the DFT netlist unchanged")
        self.record(physical_input_sha256=hashlib.sha256(imported.read_bytes()).hexdigest())
        self.publish_physical()

    def publish_physical(self):
        for label, filename in (("floorplan.odb", "2_floorplan.odb"), ("placement.odb", "3_place.odb"),
                                ("cts.odb", "4_cts.odb"), ("routing.odb", "5_route.odb"),
                                ("final.odb", "6_final.odb"), ("final.def", "6_final.def")):
            target = self.results / filename
            link = self.outputs["04_physical"] / label
            if target.is_file() and not link.exists():
                link.symlink_to(target)
        for label, target in (("reports", self.reports), ("logs", self.work / "logs/sky130hd/counter4/base")):
            link = self.outputs["04_physical"] / label
            if target.is_dir() and not link.exists():
                link.symlink_to(target, target_is_directory=True)

    def gds(self):
        if not self.gds_done:
            self.invalidate(*PHYSICAL_RESULTS)
            self.finish_physical()
            self.stage_module("05_gds").assemble(self)
            self.gds_done = True

    def drc(self):
        self.gds()
        self.invalidate("drc_items", "drc_scope")
        self.stage_module("06_signoff").klayout_drc(self)

    def lvs(self):
        self.gds()
        self.invalidate("lvs", "tap_instances_excluded_from_reference")
        self.stage_module("06_signoff").klayout_lvs(self)

    def post_route_sim(self):
        self.gds()
        self.sim("post_route", self.results / "6_final.v")
        self.sim("post_route_scan", self.results / "6_final.v", scan_test=True)

    def lec(self):
        self.gds()
        require("yosys")
        self.invalidate("lec")
        self.stage_module("06_signoff").lec(self)

    def sta(self):
        self.gds()
        self.invalidate("sta")
        self.stage_module("06_signoff").sta(self)

    def signoff(self):
        """Every check on the GDS and the routed netlist (06_signoff)."""
        require("magic", "netgen", "yosys")
        self.drc()
        self.lvs()
        self.post_route_sim()
        self.lec()
        self.sta()
        self.invalidate("physical_signoff", "scope")
        self.stage_module("06_signoff").physical_checks(self)
        self.record(scope="block-level macro: SKY130 open-source signoff clean "
                          "(KLayout and Magic DRC, KLayout and netgen LVS, antenna, Yosys LEC "
                          "RTL to routed netlist, STA 5 PVT x 3 RC corners in functional and "
                          "scan-shift mode); no power, IR drop, crosstalk or EM analysis; "
                          "no pad ring, density fill or seal ring (chip-level)")

    def check(self):
        """Alias of signoff, so `make check` still works."""
        self.signoff()

    def package(self):
        self.signoff()
        self.stage_module("06_signoff").package(self)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=STAGES)
    args = parser.parse_args()
    config = settings()
    if args.stage == "doctor":
        doctor(config)
        return
    build = EXAMPLE / "build"
    build.mkdir(exist_ok=True)
    with (build / ".lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another example stage is running; wait for it to finish") from exc
        work = workspace(config, args.stage == "fresh")
        print(f"Outputs: {EXAMPLE / 'build/latest'} -> {work}", flush=True)
        flow = Flow(config, work)
        for folder, target in flow.outputs.items():
            link = EXAMPLE / folder / "build"
            if not link.parent.is_dir():
                continue
            if os.path.lexists(link) and not link.is_symlink():
                raise RuntimeError(f"Preserving existing output directory: {link}")
            temporary = link.with_name(".build-link-" + str(os.getpid()))
            temporary.symlink_to(target, target_is_directory=True)
            temporary.replace(link)
        flow.execute(args.stage)
        print(f"Completed: {args.stage}. Logs: {work / 'driver_logs'}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
