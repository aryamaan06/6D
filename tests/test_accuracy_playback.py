"""Compact accuracy provenance reaches saved project playback and JSON export."""
from copy import deepcopy
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import engineering, orbital_adapter, simulation
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore, _digest
from sixd.workspace_simulation import WorkspaceSimulation


class AccuracyPlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parameters = {"mu_m3_s2": 398600441800000., "exclusion_radius_m": 6371000.,
            "position_x": 7000000., "position_y": 0., "position_z": 0.,
            "velocity_x": 0., "velocity_y": math.sqrt(398600441800000. / 7000000.), "velocity_z": 0.,
            "duration_s": 500., "steps": 1024}
        cls.criteria = {"position_tolerance_m": 1., "velocity_tolerance_m_s": .001,
                        "source": "Constructed playback accuracy criterion"}
        metrics, artifact, accuracy = orbital_adapter.evaluate_with_accuracy(cls.parameters, cls.criteria)
        cls.canonical_run = {"run_id": "a" * 32, "project_id": "playback-accuracy", "revision": 1,
            "created_at": "2026-10-19T00:00:00Z", "model_origins": {"orbit": {"run_id": "a" * 32, "revision": 1, "disposition": "executed"}},
            "model_results": {"orbit": {"model_type": "orbital_trajectory", "status": "completed", "simulation": artifact,
                "metrics": metrics, "numerical_accuracy": accuracy, "applicability": engineering.model_applicability("orbital_trajectory")}},
            "review": {"project": {"project_id": "playback-accuracy", "requirements": []},
                "verification_sources": {"simulation.py": simulation.source_fingerprint()},
                "digest": "b" * 64, "adapter_versions": {"orbital_trajectory": "3"}, "findings": {}}}
        cls.viewer = WorkspaceSimulation.__new__(WorkspaceSimulation)

    def test_projection_keeps_accuracy_and_applicability_without_duplicating_reference_grids(self):
        before = _digest(self.canonical_run)
        receipt = self.viewer._project_receipt(self.canonical_run, "orbit")
        accuracy = receipt["numerical_accuracy"]
        self.assertEqual(accuracy["status"], "supported")
        self.assertEqual(accuracy["criteria"], self.criteria)
        self.assertEqual(accuracy["comparisons"], self.canonical_run["model_results"]["orbit"]["numerical_accuracy"]["comparisons"])
        self.assertNotIn("reference_levels", accuracy)
        self.assertEqual(receipt["applicability"]["physical_applicability"], "not_assessed")
        self.assertIn("canonical project review", receipt["accuracy_evidence_note"])
        self.assertEqual(len(self.canonical_run["model_results"]["orbit"]["numerical_accuracy"]["reference_levels"]), 2)
        # Export round-trips compact evidence; changing a view cannot mutate the
        # retained canonical reference grids or its digest.
        exported = json.loads(json.dumps(receipt))
        self.assertEqual(exported["numerical_accuracy"], accuracy)
        receipt["numerical_accuracy"]["criteria"]["position_tolerance_m"] = 99
        self.assertEqual(_digest(self.canonical_run), before)

    def test_history_listing_retains_the_same_compact_accuracy_context(self):
        receipt = self.viewer._project_receipt(self.canonical_run, "orbit")
        summary = self.viewer._summary(receipt, _digest(receipt), receipt["sources"], 1)
        self.assertEqual(summary["numerical_accuracy"], receipt["numerical_accuracy"])
        self.assertEqual(summary["applicability"], receipt["applicability"])
        self.assertNotIn("reference_levels", summary["numerical_accuracy"])

    def test_legacy_project_wrapper_does_not_invent_new_assessment_or_modify_history(self):
        legacy = deepcopy(self.canonical_run)
        legacy["model_results"]["orbit"].pop("numerical_accuracy")
        legacy["model_results"]["orbit"].pop("applicability")
        before = _digest(legacy)
        receipt = self.viewer._project_receipt(legacy, "orbit")
        self.assertNotIn("numerical_accuracy", receipt)
        self.assertNotIn("accuracy_evidence_note", receipt)
        self.assertNotIn("applicability", receipt)
        self.assertEqual(_digest(legacy), before)

    def test_exploratory_receipt_does_not_borrow_project_accuracy(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
            store = WorkspaceStore(Path(directory) / "workspace.sqlite3")
            project = store.create_project(example_projects()["orbital_review"])["project"]
            viewer = WorkspaceSimulation(store)
            detail = viewer.run(project["project_id"], 1, simulation.default_spec())
            receipt = detail["receipt"]
            self.assertNotIn("numerical_accuracy", receipt)
            self.assertNotIn("applicability", receipt)
            self.assertNotEqual(receipt.get("binding_kind"), "project_model")
            self.assertEqual(viewer.get(receipt["simulation_id"])["receipt"], receipt)

    @unittest.skipUnless(shutil.which("node"), "Node is required for the actual playback renderer check")
    def test_actual_playback_renderer_distinguishes_supported_gap_legacy_and_exploratory(self):
        receipt = self.viewer._project_receipt(self.canonical_run, "orbit")
        receipt = {key: value for key, value in receipt.items() if key in {
            "binding_kind", "numerical_accuracy", "applicability", "accuracy_evidence_note"}}
        unresolved = deepcopy(receipt)
        unresolved["numerical_accuracy"].update(status="insufficient_accuracy", reason="The saved difference exceeds the supplied tolerance.")
        legacy = deepcopy(receipt)
        legacy.pop("numerical_accuracy")
        exploratory = deepcopy(receipt)
        exploratory["binding_kind"] = "standalone"
        # Use the real rendering function in a VM, without changing the public
        # product API or requiring DOM/canvas initialization for a pure section.
        script = """
const fs = require('fs'), vm = require('vm'), assert = require('assert');
let source = fs.readFileSync(process.argv[1], 'utf8');
source = source.replace('window.SixDSimulation={mount,unmount};', 'window.SixDSimulation={mount,unmount,accuracyPanel};');
const context = {window:{}}; vm.createContext(context); vm.runInContext(source, context);
const render = context.window.SixDSimulation.accuracyPanel;
const [supported, unresolved, legacy, exploratory] = JSON.parse(fs.readFileSync(0, 'utf8'));
let html = render(supported);
assert(html.includes('Refinement criteria supported'));
assert(html.includes('Declared position tolerance'));
assert(html.includes('Constructed playback accuracy criterion'));
assert(html.includes('Physical applicability not assessed'));
assert(html.includes('not rigorous bounds'));
html = render(unresolved); assert(html.includes('Insufficient accuracy')); assert(html.includes('exceeds the supplied tolerance'));
html = render(legacy); assert(html.includes('Historical accuracy evidence unavailable')); assert(!html.includes('Refinement criteria supported'));
html = render(exploratory); assert(html.includes('exploratory scenario')); assert(!html.includes('Constructed playback accuracy criterion'));
supported.numerical_accuracy.criteria.source = '<script>bad()</script>';
assert(!render(supported).includes('<script>bad()'));
"""
        completed = subprocess.run([shutil.which("node"), "-e", script,
            str(ROOT / "src/sixd/web/simulation.js")], input=json.dumps([receipt, unresolved, legacy, exploratory]),
            text=True, capture_output=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
