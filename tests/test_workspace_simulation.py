"""Isolated scenario persistence, exact project binding and historical replay."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import simulation, workspace_simulation
from sixd.project_examples import example_projects
from sixd.workspace import ConflictError, WorkspaceError, WorkspaceStore, _digest, _encode
from sixd.workspace_simulation import WorkspaceSimulation


class WorkspaceSimulationTests(unittest.TestCase):
    def setUp(self):
        directory = ROOT / "work"
        directory.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "workspace.sqlite3"
        self.store = WorkspaceStore(self.path)
        self.original = self.store.create_project(example_projects()["baseline"])
        self.identity = self.original["project_id"]
        self.scenarios = WorkspaceSimulation(self.store)
        self.spec = simulation.default_spec()

    def run_scenario(self, revision=1, spec=None):
        return self.scenarios.run(self.identity, revision, spec or self.spec)

    def rows(self, table):
        with self.store._connect() as connection:
            return [tuple(row) for row in connection.execute("SELECT * FROM " + table).fetchall()]

    def test_run_persists_exact_explicit_scenario_without_changing_project_or_findings(self):
        before = {table: self.rows(table) for table in ("projects", "revisions", "runs")}
        detail = self.run_scenario()
        receipt = detail["receipt"]
        self.assertEqual(receipt["project_snapshot"], self.original["project"])
        self.assertEqual(receipt["project_snapshot_digest"], _digest(self.original["project"]))
        self.assertEqual(receipt["spec"], simulation.validate_spec(self.spec))
        self.assertEqual(receipt["result"]["spec"], receipt["spec"])
        self.assertEqual(receipt["live_model_calls"], 0)
        self.assertTrue(detail["integrity"]["unsigned"])
        self.assertEqual(detail["receipt_digest"], _digest(receipt))
        self.assertFalse(detail["freshness"]["historical"])
        self.assertEqual(before, {table: self.rows(table) for table in before})
        self.assertIn("not derived", receipt["binding_note"])

    def test_reopen_and_history_read_never_recompute_or_revalidate_old_scenarios(self):
        detail = self.run_scenario()
        saved_rows = self.rows("simulations")
        with patch.object(simulation, "simulate", side_effect=AssertionError("History cannot execute physics")), \
             patch.object(simulation, "validate_spec", side_effect=AssertionError("History cannot revalidate with new rules")):
            reopened = WorkspaceSimulation(WorkspaceStore(self.path))
            self.assertEqual(reopened.get(detail["receipt"]["simulation_id"]), detail)
            listed = reopened.list(self.identity, 1)
        self.assertEqual(listed["simulations"][0]["receipt_digest"], detail["receipt_digest"])
        self.assertEqual(self.rows("simulations"), saved_rows)

    def test_source_change_preserves_old_samples_and_marks_them_historical(self):
        detail = self.run_scenario()
        stored_rows = self.rows("simulations")
        sources = {**workspace_simulation._LOADED_SOURCES, "simulation.py": "a" * 64}
        with patch.object(workspace_simulation, "_sources", return_value=sources):
            historical = self.scenarios.get(detail["receipt"]["simulation_id"])
            listed = self.scenarios.list(self.identity, 1)
            with self.assertRaisesRegex(ConflictError, "Restart"):
                self.run_scenario()
        self.assertFalse(historical["freshness"]["source_current"])
        self.assertTrue(historical["freshness"]["historical"])
        self.assertTrue(listed["simulations"][0]["historical"])
        self.assertEqual(historical["receipt"], detail["receipt"])
        self.assertEqual(self.rows("simulations"), stored_rows)

    def test_changed_kernel_file_is_detected_even_when_loaded_kernel_hash_is_unchanged(self):
        detail = self.run_scenario()
        loaded_hash = simulation.source_fingerprint()
        changed_file = Path(self.temporary.name) / "changed_simulation.py"
        changed_file.write_text("# Changed kernel on disk, old imported code still loaded.\n", encoding="utf-8")
        with patch.object(simulation, "__file__", str(changed_file)):
            self.assertEqual(simulation.source_fingerprint(), loaded_hash)
            historical = self.scenarios.get(detail["receipt"]["simulation_id"])
            self.assertTrue(historical["freshness"]["historical"])
            self.assertNotEqual(historical["current_sources"]["simulation.py"], loaded_hash)
            with self.assertRaisesRegex(ConflictError, "Restart"):
                self.run_scenario()
        self.assertEqual(historical["receipt"], detail["receipt"])

    def test_run_on_saved_earlier_revision_returns_requested_context(self):
        updated = deepcopy(self.original["project"])
        updated["inputs"]["heat_input"]["value"] = 700
        self.store.save_revision(self.identity, 1, updated)
        detail = self.run_scenario(1)
        self.assertEqual(detail["freshness"]["context_revision"], 1)
        self.assertTrue(detail["freshness"]["selected_revision_matches"])
        latest_context = self.scenarios.get(detail["receipt"]["simulation_id"])
        self.assertEqual(latest_context["freshness"]["context_revision"], 2)
        self.assertFalse(latest_context["freshness"]["selected_revision_matches"])

    def test_revision_history_remains_bound_and_comparable_for_same_explicit_physics(self):
        first = self.run_scenario()
        updated = deepcopy(self.original["project"])
        updated["inputs"]["heat_input"]["value"] = 700
        self.store.save_revision(self.identity, 1, updated)
        second_spec = {**self.spec, "name": "Finer time resolution", "steps": self.spec["steps"] * 2}
        # Keep the kernel's public work ceiling in this independent storage test.
        if second_spec["steps"] > 4096:
            second_spec["steps"] = self.spec["steps"]
        second = self.run_scenario(2, second_spec)
        summaries = self.scenarios.list(self.identity, 2)["simulations"]
        self.assertEqual([row["revision"] for row in summaries], [2, 1])
        self.assertTrue(summaries[1]["historical"])
        self.assertFalse(summaries[0]["historical"])
        self.assertEqual(len(self.scenarios.list(self.identity, 1)["simulations"]), 1)
        first_after = self.scenarios.get(first["receipt"]["simulation_id"])
        self.assertTrue(first_after["freshness"]["historical"])
        self.assertEqual(first_after["receipt"], first["receipt"])
        comparison = self.scenarios.compare(first["receipt"]["simulation_id"], second["receipt"]["simulation_id"])
        self.assertTrue(comparison["compatible"], comparison)
        self.assertIn("name", comparison["changed_spec_fields"])

    def test_comparison_blocks_changed_gravity_exclusion_or_unrelated_project(self):
        first = self.run_scenario()
        first_id = first["receipt"]["simulation_id"]
        for field, factor, message in (("mu_m3_s2", 1.001, "Gravitational"),
                                       ("exclusion_radius_m", .99, "Exclusion")):
            spec = {**self.spec, field: self.spec[field] * factor}
            changed = self.run_scenario(spec=spec)
            comparison = self.scenarios.compare(first_id, changed["receipt"]["simulation_id"])
            self.assertFalse(comparison["compatible"])
            self.assertTrue(any(message in reason for reason in comparison["reasons"]))
            self.assertIsNone(comparison["shared_time_domain_s"])
        other_project = deepcopy(self.original["project"])
        other_project["project_id"] += "-other"
        self.store.create_project(other_project)
        other = self.scenarios.run(other_project["project_id"], 1, self.spec)
        self.assertFalse(self.scenarios.compare(first_id, other["receipt"]["simulation_id"])["compatible"])
        self.assertFalse(self.scenarios.compare(first_id, first_id)["compatible"])

    def test_changed_duration_reports_comparison_window_not_identical_extrema_scope(self):
        first = self.run_scenario()
        second = self.run_scenario(spec={**self.spec, "duration_s": self.spec["duration_s"] / 2})
        comparison = self.scenarios.compare(first["receipt"]["simulation_id"], second["receipt"]["simulation_id"])
        self.assertTrue(comparison["compatible"])
        self.assertFalse(comparison["same_duration"])
        self.assertEqual(comparison["shared_time_domain_s"], [0, self.spec["duration_s"] / 2])
        self.assertIn("different time intervals", comparison["note"])

    def test_digest_corruption_is_rejected_by_detail_and_history(self):
        detail = self.run_scenario()
        identity = detail["receipt"]["simulation_id"]
        with self.store._connect(write=True) as connection:
            connection.execute("UPDATE simulations SET digest=? WHERE simulation_id=?", ("0" * 64, identity))
        for operation in (lambda: self.scenarios.get(identity), lambda: self.scenarios.list(self.identity, 1)):
            with self.assertRaisesRegex(WorkspaceError, "digest"):
                operation()

    def test_recomputed_digest_cannot_hide_an_incorrect_project_binding(self):
        detail = self.run_scenario()
        receipt = deepcopy(detail["receipt"])
        receipt["project_snapshot"]["name"] = "Wrong project snapshot"
        receipt["project_snapshot_digest"] = _digest(receipt["project_snapshot"])
        with self.store._connect(write=True) as connection:
            connection.execute("UPDATE simulations SET receipt=?,digest=? WHERE simulation_id=?",
                               (_encode(receipt), _digest(receipt), receipt["simulation_id"]))
        with self.assertRaisesRegex(WorkspaceError, "exact project revision"):
            self.scenarios.get(receipt["simulation_id"])

    def test_recomputed_digest_cannot_hide_an_incorrect_scenario_result_binding(self):
        detail = self.run_scenario()
        receipt = deepcopy(detail["receipt"])
        receipt["spec"]["duration_s"] *= 2
        with self.store._connect(write=True) as connection:
            connection.execute("UPDATE simulations SET receipt=?,digest=? WHERE simulation_id=?",
                               (_encode(receipt), _digest(receipt), receipt["simulation_id"]))
        with self.assertRaisesRegex(WorkspaceError, "scenario binding"):
            self.scenarios.get(receipt["simulation_id"])

    def test_invalid_requests_and_busy_compute_do_not_write_receipts(self):
        for identity, revision in ((None, 1), ([], 1), (self.identity, True), (self.identity, 2), ("missing", 1)):
            with self.subTest(identity=identity, revision=revision), self.assertRaises(WorkspaceError):
                self.scenarios.run(identity, revision, self.spec)
        for spec in ({**self.spec, "steps": 4097}, {**self.spec, "provider": "live"}):
            with self.assertRaises(ValueError):
                self.run_scenario(spec=spec)
        self.scenarios._run_lock.acquire()
        try:
            with self.assertRaisesRegex(ConflictError, "already running"):
                self.run_scenario()
        finally:
            self.scenarios._run_lock.release()
        self.assertEqual(self.rows("simulations"), [])

    def test_source_change_during_compute_saves_nothing(self):
        original = simulation.simulate
        sources = deepcopy(workspace_simulation._LOADED_SOURCES)

        def change_during_run(spec):
            result = original(spec)
            sources["simulation.py"] = "b" * 64
            return result

        with patch.object(workspace_simulation, "_sources", side_effect=lambda: deepcopy(sources)), \
             patch.object(simulation, "simulate", side_effect=change_during_run):
            with self.assertRaisesRegex(ConflictError, "during execution"):
                self.run_scenario()
        self.assertEqual(self.rows("simulations"), [])


if __name__ == "__main__":
    unittest.main()
