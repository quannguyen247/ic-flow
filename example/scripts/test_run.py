"""Driver regressions that do not require EDA tools."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

import run


def stage(folder, filename):
    """Load a stage script the same way the driver does."""
    path = Path(__file__).resolve().parents[1] / folder / filename
    spec = importlib.util.spec_from_file_location("stage_" + folder, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dft = stage("03_dft", "run_dft.py")
signoff = stage("06_signoff", "run_signoff.py")


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="ic-flow-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.example = self.root / "source with spaces" / "example"
        for name, content in {
            "01_rtl/counter4.v": "module counter4; endmodule\n",
            "04_physical/config.mk": "export DESIGN_NAME = counter4\n",
            "05_gds/prepare_gds.py": "# GDS script\n",
            "scripts/run.py": "# Driver snapshot\n",
        }.items():
            path = self.example / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.config = {"orfs": str(self.root / "orfs"),
                       "openroad_image": str(self.root / "openroad.sif"),
                       "klayout_image": "local/image:fixed", "cores": "1",
                       "pdk_root": str(self.root / "pdk"),
                       "work_root": str(self.root / "cache")}
        self.example_patch = patch.object(run, "EXAMPLE", self.example)
        self.example_patch.start()
        self.addCleanup(self.example_patch.stop)

    def flow(self):
        return run.Flow(self.config, run.workspace(self.config, False))

    def main(self, stage):
        with patch.object(sys, "argv", ["run.py", stage]), patch.object(run, "settings", return_value=self.config):
            run.main()

    def test_main_links_each_stage_build_folder_into_the_run(self):
        self.main("fresh")
        latest = (self.example / "build/latest").resolve()
        for folder in ("01_rtl", "04_physical", "05_gds"):
            with self.subTest(folder=folder):
                link = self.example / folder / "build"
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), latest / folder)
        self.assertFalse((self.example / "06_signoff/build").exists())
        self.main("fresh")
        self.assertEqual((self.example / "01_rtl/build").resolve(), (self.example / "build/latest").resolve() / "01_rtl")
        self.assertNotEqual((self.example / "build/latest").resolve(), latest)
        self.assertEqual(list(self.example.glob("*/.build-link-*")), [])

    def test_main_keeps_a_real_build_directory(self):
        kept = self.example / "05_gds/build"
        kept.mkdir()
        (kept / "notes.txt").write_text("mine")
        with self.assertRaisesRegex(RuntimeError, "Preserving existing output directory"):
            self.main("fresh")
        self.assertEqual((kept / "notes.txt").read_text(), "mine")

    def test_snapshot_reuse_change_and_fresh_preserve_prior_runs(self):
        first = run.workspace(self.config, False)
        self.assertNotIn(" ", str(first))
        self.assertEqual(first, run.workspace(self.config, False))
        source = self.example / "01_rtl/counter4.v"
        original = source.read_text()
        source.write_text(original + "// Changed source\n")
        second = run.workspace(self.config, False)
        self.assertNotEqual(first, second)
        self.assertEqual((first / "inputs/01_rtl/counter4.v").read_text(), original)
        self.assertEqual((second / "inputs/01_rtl/counter4.v").read_text(), source.read_text())
        third = run.workspace(self.config, True)
        self.assertNotEqual(second, third)
        self.assertTrue(first.is_dir() and second.is_dir())
        self.assertEqual((self.example / "build/latest").resolve(), third)

    def test_existing_output_directory_is_preserved(self):
        latest = self.example / "build/latest"
        latest.mkdir(parents=True)
        note = latest / "keep.txt"
        note.write_text("existing work")
        with self.assertRaisesRegex(RuntimeError, "preserving"):
            run.workspace(self.config, False)
        self.assertEqual(note.read_text(), "existing work")

    def test_invalid_configuration_has_clear_errors(self):
        for changed, expected in (({"cores": "0"}, "CORES"),
                                  ({"work_root": str(self.root / "bad path")}, "whitespace")):
            with self.subTest(changed=changed), self.assertRaisesRegex(RuntimeError, expected):
                run.workspace(self.config | changed, False)

    def test_failed_simulation_clears_previous_pass(self):
        flow = self.flow()
        flow.record(sim_rtl="passed")
        with patch.object(run, "require"), patch.object(flow, "run", side_effect=RuntimeError("compile failed")):
            with self.assertRaisesRegex(RuntimeError, "compile failed"):
                flow.execute("sim")
        summary = json.loads((flow.work / "summary.json").read_text())
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["requested_stage"], "sim")
        self.assertNotIn("sim_rtl", summary)
        self.assertIn("compile failed", summary["failure"])

    def test_zero_exit_without_testbench_pass_is_rejected(self):
        flow = self.flow()
        with patch.object(run, "require"), patch.object(flow, "run", return_value="Compiler exited normally"):
            with self.assertRaisesRegex(RuntimeError, "without the testbench PASS"):
                flow.execute("sim")
        self.assertEqual(flow.summary["status"], "failed")

    def test_failed_physical_rerun_clears_prior_layout_checks(self):
        flow = self.flow()
        flow.record(gds="previous.gds", drc_items=0, lvs="matched")
        with patch.object(flow, "physical", side_effect=RuntimeError("route failed")):
            with self.assertRaisesRegex(RuntimeError, "route failed"):
                flow.execute("route")
        for key in ("gds", "drc_items", "lvs"):
            self.assertNotIn(key, flow.summary)
        self.assertEqual(flow.summary["status"], "failed")

    def test_failed_synthesis_clears_checks_of_previous_netlist(self):
        flow = self.flow()
        flow.record(sim_post_synth="passed", fault_atpg={"coverage_percent": 99}, gds="previous.gds")
        with patch.object(run, "require"), patch.object(run, "revision"), patch.object(flow, "stage_module") as stage_mock:
            stage_mock.return_value.run.side_effect = RuntimeError("synthesis failed")
            with self.assertRaisesRegex(RuntimeError, "synthesis failed"):
                flow.execute("synth")
        for key in ("sim_post_synth", "fault_atpg", "gds"):
            self.assertNotIn(key, flow.summary)

    def test_failed_command_retains_command_and_output(self):
        flow = self.flow()
        command = [sys.executable, "-c", "print('diagnostic output'); raise SystemExit(3)"]
        with self.assertRaisesRegex(RuntimeError, "exit 3"):
            flow.run("06_signoff", "failure_case", command)
        log = (flow.logs / "failure_case.log").read_text()
        self.assertTrue(log.startswith("$ "))
        self.assertIn("diagnostic output", log)

    def test_log_link_goes_to_the_named_stage(self):
        flow = self.flow()
        command = [sys.executable, "-c", "pass"]
        for folder, other, name in (("05_gds", "06_signoff", "gds_merge"),
                                    ("06_signoff", "05_gds", "drc"),
                                    ("06_signoff", "05_gds", "sim_post_route")):
            with self.subTest(name=name):
                flow.run(folder, name, command)
                self.assertTrue((flow.outputs[folder] / (name + ".log")).is_symlink())
                self.assertFalse((flow.outputs[other] / (name + ".log")).exists())

    def test_unknown_stage_is_rejected_before_running(self):
        flow = self.flow()
        with self.assertRaisesRegex(RuntimeError, "Unknown stage"):
            flow.run("99_unknown", "never_runs", [sys.executable, "-c", "raise SystemExit(1)"])
        self.assertFalse((flow.logs / "never_runs.log").exists())

    def test_every_stage_script_names_its_own_folder(self):
        for module, folder in ((dft, "03_dft"), (signoff, "06_signoff"),
                               (stage("05_gds", "run_gds.py"), "05_gds"),
                               (stage("02_synthesis", "run_synthesis.py"), "02_synthesis")):
            with self.subTest(folder=folder):
                self.assertEqual(module.STAGE, folder)
                self.assertIn(folder, run.FOLDERS)

    def test_signoff_runs_layout_checks_and_check_is_an_alias(self):
        flow = self.flow()
        calls = []
        module = type("Signoff", (), {"physical_checks": staticmethod(lambda _: calls.append("physical"))})
        with patch.object(run, "require"), patch.object(flow, "gds"), \
             patch.object(flow, "stage_module", return_value=module), \
             patch.object(flow, "drc", side_effect=lambda: calls.append("drc")), \
             patch.object(flow, "lvs", side_effect=lambda: calls.append("lvs")), \
             patch.object(flow, "post_route_sim", side_effect=lambda: calls.append("sim")), \
             patch.object(flow, "lec", side_effect=lambda: calls.append("lec")), \
             patch.object(flow, "sta", side_effect=lambda: calls.append("sta")):
            flow.check()
        self.assertEqual(calls, ["drc", "lvs", "sim", "lec", "sta", "physical"])
        self.assertIn("signoff clean", flow.summary["scope"])

    def test_settings_follow_environment_overrides(self):
        overrides = {"ORFS_ROOT": str(self.root / "orfs-x"), "CORES": "7", "PDK_ROOT": str(self.root / "pdk-x")}
        with patch.dict(run.os.environ, overrides):
            config = run.settings()
        self.assertEqual(config["orfs"], str((self.root / "orfs-x").resolve()))
        self.assertEqual(config["pdk_root"], str((self.root / "pdk-x").resolve()))
        self.assertEqual(config["cores"], "7")

    def test_empty_environment_values_fall_back_to_defaults(self):
        empty = {name: "" for name in run.DEFAULTS}
        with patch.dict(run.os.environ, empty):
            config = run.settings()
        self.assertEqual(config["cores"], "4")
        self.assertEqual(config["pdk_root"], str(Path("~/.local/share/eda/pdk-digital").expanduser().resolve()))
        self.assertNotEqual(config["work_root"], str(Path.cwd()))

    def test_failed_signoff_rerun_drops_its_old_result(self):
        flow = self.flow()
        flow.record(lvs="matched", tap_instances_excluded_from_reference=13, lec={"a": "b"}, sta={"worst": {}})
        module = MagicMock()
        module.klayout_lvs.side_effect = RuntimeError("lvs failed")
        module.lec.side_effect = RuntimeError("lec failed")
        module.sta.side_effect = RuntimeError("sta failed")
        with patch.object(run, "require"), patch.object(flow, "gds"), \
             patch.object(flow, "stage_module", return_value=module):
            for step, keys in ((flow.lvs, ("lvs", "tap_instances_excluded_from_reference")),
                               (flow.lec, ("lec",)), (flow.sta, ("sta",))):
                with self.subTest(step=step.__name__), self.assertRaises(RuntimeError):
                    step()
                for key in keys:
                    self.assertNotIn(key, flow.summary)

    def test_done_flags_come_from_the_recorded_summary(self):
        work = run.workspace(self.config, False)
        flow = run.Flow(self.config, work)
        self.assertFalse(flow.synth_done or flow.chain_done or flow.atpg_done)
        flow.synth_netlist.write_text("// synthesized\n")
        flow.scan_netlist.write_text("// scan\n")
        flow.record(sim_post_synth="passed", sim_post_dft="passed", sim_post_dft_scan="passed")
        flow = run.Flow(self.config, work)
        self.assertTrue(flow.synth_done and flow.chain_done)
        self.assertFalse(flow.atpg_done)

    def test_resynthesis_marks_later_stages_stale(self):
        flow = self.flow()
        flow.chain_done = flow.atpg_done = flow.physical_ready = flow.gds_done = True
        flow.record(sim_post_dft="passed", sim_post_dft_scan="passed", fault_atpg={})
        with patch.object(run, "require"), patch.object(run, "revision"), \
             patch.object(flow, "stage_module"), patch.object(flow, "sim"):
            flow.synth()
        self.assertFalse(flow.chain_done or flow.atpg_done or flow.physical_ready or flow.gds_done)
        for key in ("sim_post_dft", "sim_post_dft_scan", "fault_atpg"):
            self.assertNotIn(key, flow.summary)

    def test_recorded_gds_is_reused_only_while_its_checksum_holds(self):
        work = run.workspace(self.config, False)
        flow = run.Flow(self.config, work)
        for name in ("cut.v", "patterns.json", "coverage.yml"):
            (flow.outputs["03_dft"] / name).write_text("x\n")
        flow.results.mkdir(parents=True)
        (flow.results / "6_final.def").write_text("DESIGN counter4 ;\n")
        gds = flow.outputs["05_gds"] / "counter4.gds"
        gds.write_bytes(b"gds")
        flow.record(fault_atpg={}, gds=str(gds), gds_sha256=run.hashlib.sha256(b"gds").hexdigest())
        self.assertTrue(run.Flow(self.config, work).gds_done)
        gds.write_bytes(b"changed")
        self.assertFalse(run.Flow(self.config, work).gds_done)

    def test_view3d_is_outside_the_run_fingerprint(self):
        viewer = self.example / "06_signoff/view3d/gds_to_3d.py"
        viewer.parent.mkdir(parents=True)
        viewer.write_text("# viewer\n")
        first = run.workspace(self.config, False)
        viewer.write_text("# viewer, edited\n")
        self.assertEqual(first, run.workspace(self.config, False))
        self.assertFalse((first / "inputs/06_signoff/view3d").exists())

    def test_simulation_logs_go_to_the_stage_of_their_netlist(self):
        flow = self.flow()
        netlist = flow.work / "6_final.v"
        with patch.object(run, "require"), patch.object(flow, "run", return_value=run.PASS) as command:
            flow.sim("post_route", netlist)
        self.assertEqual({call.args[0] for call in command.call_args_list}, {"06_signoff"})
        self.assertTrue((flow.outputs["06_signoff"] / "post_route").is_dir())
        self.assertFalse((flow.outputs["05_gds"] / "post_route").exists())
        with patch.object(run, "require"), self.assertRaisesRegex(RuntimeError, "Unknown simulation"):
            flow.sim("post_gds", netlist)

    def test_physical_input_must_equal_the_scan_netlist(self):
        flow = self.flow()
        flow.physical_ready = True
        flow.scan_netlist.write_text("// netlist after scan insertion\n")
        flow.results.mkdir(parents=True)
        (flow.results / "1_synth.v").write_text("// wrong pre-DFT netlist\n")
        with patch.object(flow, "make"):
            with self.assertRaisesRegex(RuntimeError, "DFT netlist unchanged"):
                flow.finish_physical()
        self.assertNotIn("physical_input_sha256", flow.summary)

    def test_success_clears_previous_failure_status(self):
        flow = self.flow()
        flow.record(status="failed", failure="earlier error")
        flow.execute("fresh")
        self.assertEqual(flow.summary["status"], "passed")
        self.assertIsNone(flow.summary["failure"])


def fake_flow(root):
    """A flow object with real folders and a recorded command runner."""
    flow = MagicMock()
    flow.outputs = {name: root / name for name in run.FOLDERS}
    for folder in flow.outputs.values():
        folder.mkdir(parents=True, exist_ok=True)
    flow.results, flow.objects, flow.inputs = root / "results", root / "objects", root / "inputs"
    flow.platform, flow.tools = root / "platform", root / "tools"
    for folder in (flow.results, flow.objects, flow.inputs / "04_physical", flow.platform / "lvs"):
        folder.mkdir(parents=True, exist_ok=True)
    flow.summary = {}
    flow.record.side_effect = flow.summary.update
    return flow


class SignoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="ic-flow-signoff-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.flow = fake_flow(self.root)

    def test_klayout_lvs_reads_05_and_writes_everything_into_06(self):
        flow = self.flow
        (flow.results / "6_final.cdl").write_text(".SUBCKT counter4 a\nXTAP_TAPCELL_1 VPWR VGND "
                                                  "sky130_fd_sc_hd__tapvpwrvgnd_1\nX1 a b sky130_fd_sc_hd__inv_1\n.ENDS\n")
        (flow.objects / "6_final_concat.cdl").write_text(".SUBCKT sky130_fd_sc_hd__inv_1 A Y\n.ENDS\n")
        (flow.platform / "lvs/sky130hd.lylvs").write_text("  report($report_file)\n")
        flow.run.side_effect = ["Netlists match.", "LVS database: 1 pair"]
        signoff.klayout_lvs(flow)
        args = flow.run.call_args_list[0].args
        self.assertEqual(args[0], "06_signoff")
        options = args[2]
        signoff_dir, gds_dir = flow.outputs["06_signoff"], flow.outputs["05_gds"]
        self.assertIn("in_gds=" + str(gds_dir / "lvs_input.gds"), options)
        self.assertIn("target_netlist=" + str(signoff_dir / "counter4_extracted.cir"), options)
        self.assertIn("report_file=" + str(signoff_dir / "lvs.lvsdb"), options)
        self.assertEqual(flow.summary["tap_instances_excluded_from_reference"], 1)

    def test_package_copies_files_and_records_checksums(self):
        flow = self.flow
        gds = flow.outputs["05_gds"] / "counter4.gds"
        files = [gds, flow.results / "6_final.v", flow.results / "6_final.def",
                 flow.inputs / "04_physical/constraint.sdc", flow.inputs / "04_physical/scan_shift.sdc"]
        files += [flow.outputs["06_signoff"] / ("counter4_" + rc + ".spef") for rc in signoff.RC_CORNERS]
        for path in files:
            path.write_text(path.name + "\n")
        flow.summary.update(gds=str(gds), drc_items=0, drc_scope="all", lvs="matched", lec={},
                            sim_post_route="passed", sim_post_route_scan="passed",
                            physical_signoff={}, sta={"worst": {"setup_slack_ns": 1.0}}, scope="block")
        signoff.package(flow)
        handoff = flow.outputs["06_signoff"] / "handoff"
        manifest = json.loads((handoff / "manifest.json").read_text())
        self.assertFalse(manifest["foundry_signoff"])
        self.assertEqual(len(manifest["files_sha256"]), len(files))
        self.assertEqual((handoff / "counter4.gds").read_text(), "counter4.gds\n")
        self.assertEqual(flow.summary["handoff"], str(handoff))


class TimingAndDrcTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="ic-flow-sta-")
        self.addCleanup(self.temp.cleanup)
        self.flow = fake_flow(Path(self.temp.name))
        self.flow.environment.return_value = {}

    def test_sta_reads_slacks_and_limit_violations(self):
        self.flow.run.return_value = ("SETUP_CHECK worst slack 6.22\nHOLD_CHECK worst slack 0.35\n"
                                      "DRV_CHECK slew 0 cap 1 fanout 2\n")
        result = signoff.run_sta(self.flow, "sta_tt", "functional", "tt.lib", "nom.spef")
        self.assertEqual(result, {"setup_slack_ns": 6.22, "hold_slack_ns": 0.35, "limit_violations": 3})
        self.assertEqual(self.flow.run.call_args.args[0], "06_signoff")

    def test_sta_rejects_unconstrained_pins_and_missing_summary(self):
        for log, message in (("There are 2 unclocked register/latch pins.\n", "Missing timing constraints"),
                             ("SETUP_CHECK worst slack 1.0\n", "Missing STA summary")):
            with self.subTest(message=message):
                self.flow.run.return_value = log
                with self.assertRaisesRegex(RuntimeError, message):
                    signoff.run_sta(self.flow, "sta_tt", "functional", "tt.lib", "nom.spef")

    def test_klayout_drc_turns_feol_on_and_counts_items(self):
        flow = self.flow
        (flow.platform / "drc").mkdir()
        (flow.platform / "drc/sky130hd.lydrc").write_text("FEOL = false\nBEOL = true\nOFFGRID = true\n")
        flow.summary["gds"] = "counter4.gds"
        report = flow.outputs["06_signoff"] / "drc.lyrdb"
        for items, expected in ((0, None), (2, "DRC reported 2 items")):
            with self.subTest(items=items):
                flow.run.side_effect = lambda *args, n=items: report.write_text(
                    "<report-database><items>" + "<item/>" * n + "</items></report-database>")
                if expected:
                    with self.assertRaisesRegex(RuntimeError, expected):
                        signoff.klayout_drc(flow)
                else:
                    signoff.klayout_drc(flow)
                    self.assertEqual(flow.summary["drc_items"], 0)
        deck = (flow.outputs["06_signoff"] / "drc_full.lydrc").read_text()
        self.assertIn("FEOL = true", deck)

    def test_klayout_drc_rejects_an_unexpected_deck(self):
        (self.flow.platform / "drc").mkdir()
        (self.flow.platform / "drc/sky130hd.lydrc").write_text("FEOL = true\n")
        with self.assertRaisesRegex(RuntimeError, "Unexpected DRC deck"):
            signoff.klayout_drc(self.flow)


class LecStaTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="ic-flow-lec-")
        self.addCleanup(self.temp.cleanup)
        self.flow = fake_flow(Path(self.temp.name))
        self.flow.environment.return_value = {}

    def test_lec_records_proven_pairs_and_rejects_unproven(self):
        self.flow.run.return_value = ("Of those cells 4 are proven and 0 are unproven.\n"
                                      "Equivalence successfully proven!\n")
        signoff.lec(self.flow)
        self.assertEqual(len(self.flow.summary["lec"]), 3)
        self.assertEqual(self.flow.summary["lec"]["rtl_vs_synth"], "equivalent (4 output and net pairs)")
        self.flow.run.return_value = "Of those cells 3 are proven and 1 are unproven.\n"
        with self.assertRaisesRegex(RuntimeError, "LEC failed: rtl_vs_synth"):
            signoff.lec(self.flow)

    def test_extract_rc_needs_a_spef_per_corner(self):
        self.flow.pdk = Path(self.temp.name) / "pdk"
        self.flow.run.return_value = ""
        with self.assertRaisesRegex(RuntimeError, "no SPEF for min"):
            signoff.extract_rc(self.flow)

    def test_sta_records_the_worst_run_and_fails_on_violations(self):
        self.flow.pdk = Path(self.temp.name) / "pdk"
        spefs = {rc: rc + ".spef" for rc in signoff.RC_CORNERS}
        good = {"setup_slack_ns": 1.0, "hold_slack_ns": 0.2, "limit_violations": 0}
        cases = ((good, None), (dict(good, setup_slack_ns=-0.01), "Timing violation"),
                 (dict(good, limit_violations=1), "Slew, capacitance or fanout"))
        for worst_run, message in cases:
            def run_sta(flow, name, mode, liberty, spef, worst_run=worst_run):
                return worst_run if name == "sta_ss_n40C_1v60_max_functional" else good
            with self.subTest(message=message), patch.object(signoff, "extract_rc", return_value=spefs), \
                 patch.object(signoff, "run_sta", side_effect=run_sta):
                if message is None:
                    signoff.sta(self.flow)
                    self.assertEqual(len(self.flow.summary["sta"]["runs"]), 30)
                    self.assertEqual(self.flow.summary["sta"]["worst"], good)
                else:
                    with self.assertRaisesRegex(RuntimeError, message):
                        signoff.sta(self.flow)


class AtpgRetryTests(unittest.TestCase):
    def test_signal_crash_is_retried_once(self):
        flow = MagicMock()
        flow.run.side_effect = [RuntimeError("fault_atpg failed (exit -11): log"), "Simulations concluded"]
        self.assertEqual(dft.run_retrying_on_crash(flow, "fault_atpg", ["fault"]), "Simulations concluded")
        self.assertEqual(flow.run.call_count, 2)

    def test_normal_failure_and_repeated_crash_are_raised(self):
        for errors, calls in (([RuntimeError("fault_atpg failed (exit 1): log")], 1),
                              ([RuntimeError("failed (exit -11)")] * 2, 2)):
            with self.subTest(calls=calls):
                flow = MagicMock()
                flow.run.side_effect = errors
                with self.assertRaises(RuntimeError):
                    dft.run_retrying_on_crash(flow, "fault_atpg", ["fault"])
                self.assertEqual(flow.run.call_count, calls)


class ScanFaultSimTests(unittest.TestCase):
    def test_only_atpg_misses_and_flop_pins_are_simulated(self):
        flow = MagicMock()
        flow.scan_netlist.read_text.return_value = "sky130_fd_sc_hd__dfrtp_1 _14_ (\n"
        metadata = {"faultPoints": ["a", "\\b"], "sa0Covered": ["a"], "sa1Covered": ["a", "b"]}
        with patch.object(dft, "scan_test_detects", side_effect=lambda f, site, value: site != "\\b") as sim:
            self.assertEqual(dft.scan_test_atpg_misses(flow, metadata), (0, ["\\b/sa0"]))
        self.assertEqual([call.args[1:] for call in sim.call_args_list], [("\\b", 0)])
        with patch.object(dft, "scan_test_detects", return_value=True) as sim:
            self.assertEqual(dft.scan_test_flop_pins(flow), (6, []))
        self.assertEqual({call.args[1] for call in sim.call_args_list}, {"_14_.CLK", "_14_.RESET_B", "_14_.Q"})


class PhysicalCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="ic-flow-phys-")
        self.addCleanup(self.temp.cleanup)
        self.flow = fake_flow(Path(self.temp.name))
        self.flow.environment.return_value = {}
        self.flow.pdk = Path(self.temp.name) / "pdk"
        self.flow.summary["gds"] = "counter4.gds"

    def test_magic_drc_reads_the_total_and_fails_on_errors(self):
        self.flow.run.return_value = "MAGIC_DRC_TOTAL 0\n"
        self.assertEqual(signoff.magic_drc(self.flow), 0)
        for log, message in (("MAGIC_DRC_TOTAL 3\n", "found 3 errors"), ("crashed\n", "did not finish")):
            with self.subTest(message=message):
                self.flow.run.return_value = log
                with self.assertRaisesRegex(RuntimeError, message):
                    signoff.magic_drc(self.flow)

    def test_netgen_lvs_needs_a_unique_match_in_the_final_result(self):
        layout_spice = self.flow.outputs["06_signoff"] / "counter4_layout.spice"
        def run_step(stage, name, command, env=None):
            if name == "magic_extract":
                layout_spice.write_text("* layout\n")
            return self.netgen_log if name == "netgen_lvs" else ""
        self.flow.run.side_effect = run_step
        self.netgen_log = "Circuits match uniquely.\nFinal result: Circuits match uniquely.\n"
        self.assertEqual(signoff.netgen_lvs(self.flow), "Circuits match uniquely")
        self.netgen_log = "Circuits match uniquely.\nFinal result: Netlists do not match.\n"
        with self.assertRaisesRegex(RuntimeError, "Netgen LVS mismatch"):
            signoff.netgen_lvs(self.flow)

    def test_netgen_lvs_needs_the_magic_layout_netlist(self):
        self.flow.run.return_value = ""
        with self.assertRaisesRegex(RuntimeError, "did not write the layout netlist"):
            signoff.netgen_lvs(self.flow)

    def test_antenna_adds_net_and_pin_violations(self):
        self.flow.run.return_value = "Found 0 net violations.\nFound 0 pin violations.\n"
        self.assertEqual(signoff.antenna(self.flow), 0)
        for log, message in (("Found 1 net violations.\nFound 2 pin violations.\n", "found violations"),
                             ("Found 1 net violations.\n", "did not finish")):
            with self.subTest(message=message):
                self.flow.run.return_value = log
                with self.assertRaisesRegex(RuntimeError, message):
                    signoff.antenna(self.flow)


class GdsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="ic-flow-gds-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.flow = fake_flow(self.root)
        self.flow.orfs = self.root / "orfs"
        (self.flow.orfs / "flow/util").mkdir(parents=True)
        (self.flow.orfs / "flow/util/def2stream.py").write_text("layoutOptions = tech.load_layout_options\n")
        for name in ("a.lef", "b.lef"):
            (self.flow.results / name).write_text("")
        self.tech = self.flow.objects / "klayout.lyt"
        self.tech.write_text("<lef-files>a.lef</lef-files><lef-files>b.lef</lef-files>")
        self.gds = stage("05_gds", "run_gds.py")

    def test_assemble_rejects_another_klayout_version(self):
        self.flow.run.return_value = "KLayout 0.30.1"
        with self.assertRaisesRegex(RuntimeError, "requires KLayout 0.26.9"):
            self.gds.assemble(self.flow)

    def test_assemble_rejects_a_missing_lef_and_a_changed_converter(self):
        self.flow.run.return_value = "KLayout 0.26.9"
        self.tech.write_text("<lef-files>missing.lef</lef-files><lef-files>b.lef</lef-files>")
        with self.assertRaisesRegex(RuntimeError, "Missing LEF"):
            self.gds.assemble(self.flow)
        self.tech.write_text("<lef-files>a.lef</lef-files><lef-files>b.lef</lef-files>")
        (self.flow.orfs / "flow/util/def2stream.py").write_text("# another version\n")
        with self.assertRaisesRegex(RuntimeError, "Unexpected ORFS DEF-to-GDS"):
            self.gds.assemble(self.flow)

    def test_assemble_patches_the_converter_and_records_the_gds(self):
        final = self.flow.outputs["05_gds"] / "counter4.gds"
        def run_step(stage, name, command, env=None):
            if name == "gds_pins":
                final.write_bytes(b"layout")
            return "KLayout 0.26.9"
        self.flow.run.side_effect = run_step
        self.gds.assemble(self.flow)
        converter = (self.flow.outputs["05_gds"] / "def2stream_compat.py").read_text()
        self.assertIn("config.pins_datatype = 16", converter)
        self.assertIn(str((self.flow.results / "a.lef").resolve()), self.tech.read_text())
        self.assertEqual(self.flow.summary["gds"], str(final))
        self.assertEqual({call.args[0] for call in self.flow.run.call_args_list}, {"05_gds"})


class FaultInjectionTests(unittest.TestCase):
    NETLIST = ("module counter4(a, y);\n  input a;\n  output y;\n"
               "  sky130_fd_sc_hd__inv_1 _1_ (.A(a), .Y(n1));\n"
               "  sky130_fd_sc_hd__buf_1 _2_ (.A(n1), .X(y));\nendmodule\n")

    def test_input_pin_is_tied_to_the_constant(self):
        netlist = dft.inject_fault(self.NETLIST, "_2_.A", 1)
        self.assertIn(".A(1'b1)", netlist)
        self.assertIn(".A(a)", netlist)

    def test_output_pin_is_opened_and_its_net_driven(self):
        netlist = dft.inject_fault(self.NETLIST, "\\_1_.Y", 0)
        self.assertIn(".Y(fault_open)", netlist)
        self.assertIn("wire fault_open;", netlist)
        self.assertIn("assign n1 = 1'b0;", netlist)
        self.assertEqual(netlist.count("endmodule"), 1)

    def test_unknown_site_or_pin_is_rejected(self):
        for site in ("_9_.A", "_1_.B"):
            with self.subTest(site=site), self.assertRaisesRegex(RuntimeError, "not in scan netlist"):
                dft.inject_fault(self.NETLIST, site, 0)


class MakefileTests(unittest.TestCase):
    def test_make_targets_match_driver_stages(self):
        example = Path(__file__).resolve().parents[1]
        for makefile in (example / "Makefile", example.parent / "Makefile"):
            with self.subTest(makefile=makefile.name):
                text = makefile.read_text()
                rule = next(line for line in text.splitlines()
                            if line.endswith(":") and " sim " in line and not line.startswith("."))
                targets = set(rule[:-1].split()) - {"help", "view3d"}
                self.assertEqual(targets, set(run.STAGES))


class ReferenceTests(unittest.TestCase):
    def test_lvs_reference_drops_taps_and_keeps_used_cells(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "top.cdl").write_text(".SUBCKT counter4 a\nXTAP_TAPCELL_1 VPWR VGND sky130_fd_sc_hd__tapvpwrvgnd_1\n"
                                          "X1 a b sky130_fd_sc_hd__inv_1\n.ENDS\n")
            (root / "cells.cdl").write_text(".SUBCKT sky130_fd_sc_hd__inv_1 A Y\n.ENDS\n"
                                            ".SUBCKT sky130_fd_sc_hd__buf_1 A X\n.ENDS\n")
            taps = signoff.prepare_reference(root / "top.cdl", root / "cells.cdl", root / "ref.cdl")
            reference = (root / "ref.cdl").read_text()
        self.assertEqual(taps, 1)
        self.assertNotIn("XTAP_TAPCELL_", reference)
        self.assertIn("sky130_fd_sc_hd__inv_1 A Y", reference)
        self.assertNotIn("buf_1", reference)

    def test_lvs_reference_without_taps_is_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "top.cdl").write_text(".SUBCKT counter4 a\n.ENDS\n")
            (root / "cells.cdl").write_text("")
            with self.assertRaisesRegex(RuntimeError, "tap"):
                signoff.prepare_reference(root / "top.cdl", root / "cells.cdl", root / "ref.cdl")


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {"faultPoints": ["a", "b"], "sa0Covered": ["a"], "sa1Covered": ["b"],
                         "sa0Uncovered": ["b"], "sa1Uncovered": ["a"], "ratio": 0.5}
        self.vectors = [{"coverage": {"sa0": ["a"], "sa1": ["b"]}}]

    def test_correct_ratio_and_fault_backend_are_reported(self):
        result = dft.fault_result(self.metadata, self.vectors)
        self.assertEqual(result["coverage_percent"], 50.0)
        self.assertEqual(result["total_stuck_faults"], 4)
        self.assertEqual(result["uncovered_stuck_faults"], 2)
        self.assertTrue(result["reported_uncovered_lists_consistent"])
        self.assertIn("Icarus", result["simulator"])

    def test_inconsistent_uncovered_lists_do_not_change_derived_coverage(self):
        self.metadata["sa0Uncovered"] = []
        result = dft.fault_result(self.metadata, self.vectors)
        self.assertFalse(result["reported_uncovered_lists_consistent"])
        self.assertEqual(result["coverage_percent"], 50.0)
        self.assertEqual(result["uncovered_stuck_faults"], 2)

    def test_inconsistent_compacted_vectors_are_rejected(self):
        self.vectors[0]["coverage"]["sa0"] = []
        with self.assertRaisesRegex(RuntimeError, "compacted"):
            dft.fault_result(self.metadata, self.vectors)

    def test_incorrect_ratio_is_rejected(self):
        for value in (0.9, float("nan")):
            with self.subTest(value=value):
                self.metadata["ratio"] = value
                with self.assertRaisesRegex(RuntimeError, "ratio"):
                    dft.fault_result(self.metadata, self.vectors)

    def test_ambiguous_sites_are_rejected(self):
        self.metadata["faultPoints"] = ["a", "\\a"]
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            dft.fault_result(self.metadata, self.vectors)

    def test_escaped_site_names_are_normalized(self):
        metadata = deepcopy(self.metadata)
        metadata["faultPoints"] = ["\\a", "\\b"]
        self.assertEqual(dft.fault_result(metadata, self.vectors)["coverage_percent"], 50.0)


if __name__ == "__main__":
    unittest.main()
