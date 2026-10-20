"""Canonical project trajectory playback, freshness and immutable reuse evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import simulation, workspace, workspace_simulation
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore, WorkspaceError, _digest, _encode
from sixd.workspace_simulation import WorkspaceSimulation


class ProjectSimulationBridgeTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.temp.cleanup)
        self.store = WorkspaceStore(Path(self.temp.name) / "workspace.sqlite3")
        self.project = self.store.create_project(example_projects()["orbital_review"])["project"]
        self.pid = self.project["project_id"]
        self.viewer = WorkspaceSimulation(self.store)

    def calculate(self, revision=1):
        view = self.store.run(self.pid, revision)
        identity = self.viewer.project_identity(view["run"]["run_id"], "orbit")
        return view, self.viewer.get(identity, revision)

    def save(self, input_id, value):
        view = self.store.get(self.pid)
        project = deepcopy(view["project"])
        project["inputs"][input_id]["value"] = value
        return self.store.save_revision(self.pid, view["revision"], project)

    def counts(self):
        with self.store._connect() as connection:
            return {table: connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                    for table in ("projects", "revisions", "runs", "simulations")}

    def test_unrun_project_has_guidance_then_saved_model_has_exact_view_without_second_calculation(self):
        listing = self.viewer.list(self.pid, 1)
        self.assertEqual(listing["project_models"][0]["status"], "not_run")
        self.assertIsNone(listing["project_models"][0]["simulation_id"])
        view, detail = self.calculate()
        run, receipt = view["run"], detail["receipt"]
        self.assertEqual(receipt["result"], run["model_results"]["orbit"]["simulation"])
        self.assertEqual(receipt["spec"], receipt["result"]["spec"])
        self.assertEqual(receipt["workspace_run_id"], run["run_id"])
        # Presentation-only stale fields in the workspace view are not part of the saved run digest.
        canonical = {key: value for key, value in run.items() if key not in {"stale", "stale_reasons"}}
        self.assertEqual(receipt["workspace_run_digest"], _digest(canonical))
        self.assertEqual(receipt["review_digest"], run["review"]["digest"])
        self.assertEqual(receipt["findings"], [f for f in run["review"]["findings"].values() if f["model_id"] == "orbit"])
        self.assertEqual(receipt["project_snapshot"], self.project)
        self.assertEqual(receipt["project_snapshot_digest"], _digest(self.project))
        self.assertEqual(detail["receipt_digest"], _digest(receipt))
        self.assertTrue(detail["integrity"]["derived_view"])
        self.assertFalse(detail["freshness"]["historical"])
        before = self.counts()
        with patch.object(simulation, "simulate", side_effect=AssertionError("History must never rerun")), \
             patch.object(simulation, "validate_spec", side_effect=AssertionError("History must retain its historical contract")):
            self.assertEqual(self.viewer.get(receipt["simulation_id"]), detail)
            listing = self.viewer.list(self.pid, 1)
        self.assertEqual(before, self.counts())
        self.assertEqual(before["simulations"], 0)
        self.assertEqual(listing["project_models"][0]["status"], "current")
        self.assertEqual(listing["project_models"][0]["simulation_id"], receipt["simulation_id"])
        self.assertEqual(listing["simulations"][0]["binding_kind"], "project_model")

    def test_limit_change_needs_review_then_reuses_exact_trajectory_with_new_findings_and_origin(self):
        first_view, first = self.calculate()
        self.save("maximum_final_radius", 6.9e6)
        unreviewed = self.viewer.list(self.pid, 2)
        self.assertEqual(unreviewed["project_models"][0]["status"], "historical")
        self.assertIsNone(unreviewed["project_models"][0]["simulation_id"])
        self.assertTrue(unreviewed["simulations"][0]["historical"])
        second_view, second = self.calculate(2)
        a, b = first["receipt"], second["receipt"]
        self.assertEqual(a["result"], b["result"])
        self.assertNotEqual(a["simulation_id"], b["simulation_id"])
        self.assertEqual(b["model_origin"], {"run_id": first_view["run"]["run_id"], "revision": 1, "disposition": "reused"})
        self.assertEqual(second_view["run"]["review"]["findings"]["orbit_final_radius"]["status"], "not_met")
        self.assertEqual(next(f for f in a["findings"] if f["requirement_id"] == "orbit_final_radius")["status"], "met")
        self.assertEqual(self.viewer.get(a["simulation_id"])["receipt"], a)
        self.assertTrue(self.viewer.get(a["simulation_id"])["freshness"]["historical"])
        self.assertFalse(self.viewer.get(a["simulation_id"], 1)["freshness"]["historical"])
        comparison = self.viewer.compare(a["simulation_id"], b["simulation_id"])
        self.assertTrue(comparison["compatible"])
        self.assertTrue(comparison["left"]["historical"])
        self.assertFalse(comparison["right"]["historical"])

    def test_changed_state_reruns_orbit_and_preserves_old_samples_while_thermal_is_reused(self):
        before, first = self.calculate()
        self.save("position_x", 7.01e6)
        after, second = self.calculate(2)
        self.assertIn("orbit", after["run"]["executed_model_ids"])
        self.assertIn("thermal", after["run"]["reused_model_ids"])
        self.assertNotEqual(first["receipt"]["result"]["samples"], second["receipt"]["result"]["samples"])
        self.assertEqual(self.viewer.get(first["receipt"]["simulation_id"])["receipt"], first["receipt"])
        self.assertTrue(self.viewer.compare(first["receipt"]["simulation_id"], second["receipt"]["simulation_id"])["compatible"])

    def test_same_revision_rerun_marks_previous_review_historical_and_preserves_origin(self):
        first_view, first = self.calculate()
        second_view, second = self.calculate()
        self.assertTrue(self.viewer.get(first["receipt"]["simulation_id"])["freshness"]["historical"])
        self.assertFalse(second["freshness"]["historical"])
        self.assertEqual(second["receipt"]["model_origin"]["run_id"], first_view["run"]["run_id"])
        summaries = self.viewer.list(self.pid, 1)["simulations"]
        self.assertEqual(sum(not row["historical"] for row in summaries), 1)
        self.assertEqual(summaries[0]["workspace_run_id"], second_view["run"]["run_id"])

    def test_source_changes_keep_exact_history_but_no_current_project_model(self):
        _, detail = self.calculate()
        sources = {**workspace._sources(), "engineering.py": "b" * 64}
        with patch.object(workspace, "_sources", return_value=sources):
            old = self.viewer.get(detail["receipt"]["simulation_id"])
            listing = self.viewer.list(self.pid, 1)
        self.assertEqual(old["receipt"], detail["receipt"])
        self.assertFalse(old["freshness"]["source_current"])
        self.assertTrue(old["freshness"]["historical"])
        self.assertEqual(listing["project_models"][0]["status"], "historical")
        self.assertIsNone(listing["project_models"][0]["simulation_id"])

    def test_invalid_model_input_retains_old_run_without_current_trajectory(self):
        self.calculate()
        self.save("steps", 16)
        view = self.store.run(self.pid, 2)
        self.assertEqual(view["run"]["model_results"]["orbit"]["status"], "invalid_inputs")
        listing = self.viewer.list(self.pid, 2)
        self.assertEqual(listing["project_models"][0]["status"], "not_assessed")
        self.assertIsNone(listing["project_models"][0]["simulation_id"])
        self.assertTrue(all(row["historical"] for row in listing["simulations"]))
        with self.assertRaisesRegex(WorkspaceError, "no saved completed"):
            self.viewer.get(self.viewer.project_identity(view["run"]["run_id"], "orbit"))

    def test_standalone_and_project_compare_common_kernel_and_preserve_full_sources(self):
        _, project = self.calculate()
        standalone = self.viewer.run(self.pid, 1, project["receipt"]["spec"])
        self.assertNotEqual(standalone["receipt"]["sources"], project["receipt"]["sources"])
        comparison = self.viewer.compare(standalone["receipt"]["simulation_id"], project["receipt"]["simulation_id"])
        self.assertTrue(comparison["compatible"], comparison)
        self.assertEqual(comparison["left"]["binding_kind"], "standalone")
        self.assertEqual(comparison["right"]["binding_kind"], "project_model")
        self.assertEqual(comparison["right"]["sources"], project["receipt"]["sources"])
        # A wrapper-only source revision must not masquerade as changed physics.
        changed = deepcopy(standalone["receipt"])
        changed["sources"]["workspace_simulation.py"] = "c" * 64
        with self.store._connect(write=True) as connection:
            connection.execute("UPDATE simulations SET receipt=?,digest=? WHERE simulation_id=?",
                               (_encode(changed), _digest(changed), changed["simulation_id"]))
        self.assertTrue(self.viewer.compare(changed["simulation_id"], project["receipt"]["simulation_id"])["compatible"])

    def test_identity_revision_and_cross_project_boundaries(self):
        _, first = self.calculate()
        run_id = first["receipt"]["workspace_run_id"]
        for identity in ("p-" + "a" * 32 + "-" + "b" * 16,
                         self.viewer.project_identity(run_id, "missing"),
                         self.viewer.project_identity(run_id, "thermal"), "p-../db", []):
            with self.subTest(identity=identity), self.assertRaises(WorkspaceError):
                self.viewer.get(identity)
        self.save("maximum_final_radius", 7.1e6)
        _, second = self.calculate(2)
        with self.assertRaisesRegex(WorkspaceError, "later revision"):
            self.viewer.get(second["receipt"]["simulation_id"], 1)
        other = deepcopy(self.project)
        other["project_id"] += "-other"
        self.store.create_project(other)
        run = self.store.run(other["project_id"], 1)["run"]
        comparison = self.viewer.compare(first["receipt"]["simulation_id"], self.viewer.project_identity(run["run_id"], "orbit"))
        self.assertFalse(comparison["compatible"])
        self.assertTrue(any("different projects" in reason for reason in comparison["reasons"]))

    def test_canonical_digest_corruption_is_rejected_before_adapting_history(self):
        _, detail = self.calculate()
        with self.store._connect(write=True) as connection:
            connection.execute("UPDATE runs SET digest=? WHERE run_id=?", ("0" * 64, detail["receipt"]["workspace_run_id"]))
        for read in (lambda: self.viewer.get(detail["receipt"]["simulation_id"]), lambda: self.viewer.list(self.pid, 1)):
            with self.assertRaisesRegex(WorkspaceError, "digest"):
                read()


if __name__ == "__main__":
    unittest.main()
