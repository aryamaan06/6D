"""Explicit subsystem contracts stay separate from canonical physics evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import engineering, lifecycle, workspace
from sixd.project_examples import example_projects
from sixd.workspace import ConflictError, WorkspaceError, WorkspaceStore, _digest, _encode
from sixd.workspace_systems import WorkspaceSystems


def system_project():
    """Independent 300 N drag witness plus a declared 200 N load handoff."""
    project = example_projects()["baseline"]
    for identity, value in {"density": 1.2, "relative_speed": 50, "drag_coefficient": .8,
                            "reference_area": .25, "maximum_drag_force": 305}.items():
        project["inputs"][identity]["value"] = value
    project["inputs"]["load_budget"] = {"value": 250, "unit": "N", "source": "Constructed interface allowance"}
    project["systems"] = [
        {"id": "vehicle", "title": "Space vehicle", "description": "Constructed hierarchy, not a full vehicle model",
         "parent_id": None, "model_ids": []},
        {"id": "prop", "title": "Propulsion assembly", "description": "Explicit owner of the ideal burn model",
         "parent_id": "vehicle", "model_ids": ["propulsion"]},
        {"id": "frame", "title": "Support assembly", "description": "Explicit owner of the static beam model",
         "parent_id": "vehicle", "model_ids": ["mount"]},
        {"id": "environment", "title": "Atmospheric load case", "description": "Supplied atmospheric condition",
         "parent_id": "vehicle", "model_ids": ["atmospheric_load"]},
    ]
    project["interfaces"] = [
        {"id": "thrust_to_frame", "title": "Declared transverse force", "description": "User declared direction and applicability",
         "from_system": "prop", "to_system": "frame", "source": {"kind": "input", "input_id": "thrust"},
         "target_input": "load_budget", "quantity": "Force magnitude", "unit": "N", "operator": "<=", "critical": True},
        {"id": "drag_to_frame", "title": "Drag allowance", "description": "One supplied condition only",
         "from_system": "environment", "to_system": "frame",
         "source": {"kind": "model_metric", "model_id": "atmospheric_load", "metric": "drag_force"},
         "target_input": "maximum_drag_force", "quantity": "Force magnitude", "unit": "N", "operator": "<=", "critical": True},
    ]
    return project


class WorkspaceSystemsTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "work").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "workspace.sqlite3"
        self.store = WorkspaceStore(self.path)
        self.systems = WorkspaceSystems(self.store)
        self.project = system_project()
        self.identity = self.project["project_id"]

    def baseline(self):
        self.store.create_project(self.project)
        return self.store.run(self.identity, 1)

    def contents(self):
        with self.store._connect() as db:
            names = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name: [tuple(row) for row in db.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
                    for name in names}

    @staticmethod
    def rows(projection):
        return {row["id"]: row for row in projection["checks"]["rows"]}

    def test_optional_fields_preserve_legacy_snapshot_review_and_stored_bytes(self):
        legacy = example_projects()["baseline"]
        self.store.create_project(legacy)
        before = self.store.run(self.identity, 1)
        encoded_review = _encode(before["run"]["review"])
        stored = self.contents()
        self.assertNotIn("systems", before["project"])
        self.assertNotIn("interfaces", before["project"])
        self.assertNotIn("system_interfaces", before)
        projection = self.systems.get(self.identity, 1)
        self.assertEqual(projection["checks"]["rows"], [])
        self.assertEqual(self.contents(), stored)
        self.assertEqual(_encode(self.store.get(self.identity, 1)["run"]["review"]), encoded_review)
        self.assertTrue(lifecycle.verify_review(before["run"]["review"]))
        self.assertEqual(set(before["run"]["review"]["verification_sources"]),
                         {"engineering.py", "lifecycle.py", "__init__.py", "orbital_adapter.py", "simulation.py", "attitude.py", "chains.py", "powered_flight.py", "guided_ascent.py", "staged_ascent.py"})

    def test_saved_projection_checks_independent_values_without_new_physics_or_mutation(self):
        view = self.baseline()
        before = self.contents()
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No physics on interface read")), \
                patch.object(engineering, "evaluate_models", side_effect=AssertionError("No physics on interface read")):
            projection = self.systems.get(self.identity, 1)
            second = self.systems.get(self.identity, 1)
        self.assertEqual(projection, second)
        self.assertEqual(projection["schema"], "sixd.system-interfaces.v1")
        self.assertEqual(projection["context"], "saved")
        self.assertEqual(projection["run_id"], view["run"]["run_id"])
        self.assertEqual(projection["review_digest"], view["run"]["review"]["digest"])
        self.assertEqual(projection["project_digest"], _digest(view["project"]))
        self.assertEqual(self.rows(projection)["thrust_to_frame"]["status"], "met")
        self.assertEqual(self.rows(projection)["drag_to_frame"]["status"], "met")
        self.assertEqual(self.rows(projection)["thrust_to_frame"]["source_value"], {"value": 200, "unit": "N"})
        self.assertEqual(self.rows(projection)["drag_to_frame"]["source_value"], {"value": 300, "unit": "N"})
        # .5 * 1.2 * 50^2 * .8 * .25 = 300 N, independently below the 305 N allowance.
        self.assertEqual(view["run"]["review"]["evidence"]["atmospheric_load"]["metrics"]["drag_force"]["value"], 300)
        self.assertEqual(self.contents(), before)
        digest = projection["digest"]
        self.assertEqual(digest, _digest({key: value for key, value in projection.items() if key != "digest"}))
        self.assertEqual(view["system_interfaces"], projection)
        self.assertNotIn("interface_checks", view["run"]["review"])

    def test_unreviewed_model_metric_is_a_gap_and_never_uses_previous_revision_prediction(self):
        view = self.baseline()
        changed = deepcopy(view["project"])
        changed["inputs"]["relative_speed"]["value"] = 100
        saved = self.store.save_revision(self.identity, 1, changed)
        before = self.contents()
        projection = self.systems.get(self.identity, 2)
        self.assertIsNone(projection["run_id"])
        self.assertIsNone(projection["review_digest"])
        self.assertEqual(self.rows(projection)["drag_to_frame"]["status"], "not_assessed")
        self.assertIsNone(saved["run"])
        self.assertEqual(self.contents(), before)
        self.assertEqual(self.store.get(self.identity, 1)["run"], view["run"])

    def test_draft_preview_abstains_and_never_saves_or_recalculates(self):
        view = self.baseline()
        changed = deepcopy(view["project"])
        changed["inputs"]["load_budget"]["value"] = 100
        before = self.contents()
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No draft calculation")):
            projection = self.systems.preview(self.identity, 1, changed)
        self.assertEqual(projection["context"], "draft")
        self.assertTrue(all(row["status"] == "not_assessed" for row in projection["checks"]["rows"]))
        self.assertEqual(self.contents(), before)
        self.assertEqual(self.store.get(self.identity, 1), view)

    def test_architecture_only_revision_keeps_adapter_results_and_original_receipt(self):
        view = self.baseline()
        old_receipt = _encode(view["run"])
        changed = deepcopy(view["project"])
        changed["systems"][1]["title"] = "Renamed propulsion assembly"
        changed["interfaces"][0]["operator"] = ">="
        preview = self.store.preview_change(self.identity, 1, changed)
        self.assertEqual(preview["affected_model_ids"], [])
        self.assertEqual(preview["affected_requirement_ids"], [])
        self.store.save_revision(self.identity, 1, changed)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No input or model changes")):
            updated = self.store.run(self.identity, 2)
        self.assertEqual(updated["run"]["executed_model_ids"], [])
        self.assertEqual(set(updated["run"]["reused_model_ids"]), {m["id"] for m in changed["models"]})
        self.assertEqual(updated["run"]["model_results"], view["run"]["model_results"])
        self.assertEqual(self.rows(updated["system_interfaces"])["thrust_to_frame"]["status"], "not_met")
        self.assertEqual(_encode(self.store.get(self.identity, 1)["run"]), old_receipt)
        self.assertTrue(lifecycle.verify_review(updated["run"]["review"]))

    def test_real_bound_input_edit_runs_only_affected_model_with_architecture_present(self):
        view = self.baseline()
        changed = deepcopy(view["project"])
        changed["inputs"]["relative_speed"]["value"] = 100
        self.store.save_revision(self.identity, 1, changed)
        with patch.object(workspace, "evaluate_models", wraps=engineering.evaluate_models) as calculate:
            result = self.store.run(self.identity, 2)
        self.assertEqual([call.args[0]["models"][0]["id"] for call in calculate.call_args_list], ["atmospheric_load"])
        self.assertEqual(result["run"]["review"]["findings"]["drag_limit"]["status"], "not_met")
        self.assertEqual(result["run"]["model_results"]["atmospheric_load"]["metrics"]["drag_force"]["value"], 1200)
        self.assertEqual(self.rows(result["system_interfaces"])["drag_to_frame"]["status"], "not_met")
        self.assertEqual(result["run"]["model_origins"]["propulsion"]["run_id"], view["run"]["run_id"])

    def test_explicit_graph_has_hierarchy_and_unassigned_model_fallback(self):
        view = self.baseline()
        systems = {item["id"]: item for item in view["graph"]["systems"]}
        self.assertIn("subsystem:vehicle", systems)
        self.assertIn("subsystem:prop", systems)
        self.assertIn("system:radiative_equilibrium", systems)
        self.assertNotIn("system:ideal_propulsion", systems)
        self.assertEqual(systems["subsystem:prop"]["model_ids"], ["propulsion"])
        self.assertEqual(set(systems["subsystem:prop"]["requirement_ids"]), {"fuel_margin", "burn_duration"})

    def test_unit_mismatch_and_missing_metric_remain_separate_from_canonical_findings(self):
        self.project["interfaces"][0]["unit"] = "kN"
        self.project["interfaces"][1]["source"]["metric"] = "not_a_metric"
        view = self.baseline()
        checks = self.rows(view["system_interfaces"])
        self.assertEqual(checks["thrust_to_frame"]["status"], "not_assessed")
        self.assertEqual(checks["drag_to_frame"]["status"], "not_assessed")
        self.assertEqual(view["run"]["review"]["findings"]["drag_limit"]["status"], "met")
        self.assertEqual(view["run"]["review"]["review_status"], "supported_requirements_met")

    def test_reopen_preserves_architecture_and_prior_projection(self):
        view = self.baseline()
        before = self.systems.get(self.identity, 1)
        reopened = WorkspaceStore(self.path)
        self.assertEqual(reopened.get(self.identity, 1), view)
        self.assertEqual(WorkspaceSystems(reopened).get(self.identity, 1), before)
        self.assertEqual(reopened.get(self.identity, 1)["project"]["systems"], self.project["systems"])

    def test_explicit_interface_cycle_terminates_and_flags_review_without_forcing_execution(self):
        reverse = deepcopy(self.project["interfaces"][0])
        reverse.update(id="frame_to_prop", title="Declared return interface", from_system="frame", to_system="prop",
                       source={"kind": "input", "input_id": "load_budget"}, target_input="thrust", operator=">=")
        self.project["interfaces"].append(reverse)
        view = self.baseline()
        changed = deepcopy(view["project"])
        changed["interfaces"][0]["description"] = "Changed declared interface applicability"
        impact = self.store.preview_change(self.identity, 1, changed)
        self.assertEqual(impact["affected_model_ids"], [])
        self.assertEqual(impact["affected_requirement_ids"], [])
        self.assertEqual(set(impact["affected_interface_ids"]), {"thrust_to_frame", "frame_to_prop"})
        self.assertTrue({"frame", "prop"}.issubset(impact["interface_review_system_ids"]))
        self.assertTrue({"mount", "propulsion"}.issubset(impact["interface_review_model_ids"]))
        self.assertTrue({"mount_stress", "mount_deflection", "fuel_margin", "burn_duration"}
                        .issubset(impact["interface_review_requirement_ids"]))
        self.assertEqual(len(impact["affected_interface_ids"]), len(set(impact["affected_interface_ids"])))
        self.store.save_revision(self.identity, 1, changed)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("Topology review is not physics")):
            after = self.store.run(self.identity, 2)
        self.assertEqual(after["run"]["executed_model_ids"], [])

    def test_removed_interface_remains_in_impact_but_not_active_checks(self):
        view = self.baseline()
        changed = deepcopy(view["project"])
        changed["interfaces"] = [item for item in changed["interfaces"] if item["id"] != "drag_to_frame"]
        projection = self.systems.preview(self.identity, 1, changed)
        self.assertEqual(projection["impact"]["removed_interfaces"], ["drag_to_frame"])
        self.assertIn("drag_to_frame", projection["impact"]["affected_interface_ids"])
        self.assertNotIn("drag_to_frame", self.rows(projection))
        self.assertIn("drag_to_frame", self.rows(self.systems.get(self.identity, 1)))

    def test_scenarios_tests_and_scoped_investigation_accept_architecture_without_rewriting_results(self):
        from sixd.project_investigation import validate_investigation_view
        from sixd.test_evidence import TestEvidence, validate_investigation_context
        from sixd.workspace_scenarios import WorkspaceScenarios
        from sixd.workspace_test_data import WorkspaceTestData

        view = self.baseline()
        scenarios = WorkspaceScenarios(self.store)
        study = scenarios.run(self.identity, 1, view["run"]["run_id"], {
            "schema": "sixd.scenario-spec.v1", "name": "Speed alternatives with hierarchy",
            "source": "Independent constructed comparison", "mode": "sweep", "input_id": "relative_speed", "values": [50, 100]})
        self.assertEqual(study["receipt"]["cases"][1]["review"]["evidence"]["atmospheric_load"]["metrics"]["drag_force"]["value"], 1200)
        tests = WorkspaceTestData(self.store)
        comparison = tests.run(self.identity, 1, view["run"]["run_id"], {
            "schema": "sixd.test-comparison-spec.v1", "name": "Synthetic row with explicit systems",
            "source": "Constructed, not hardware data", "data_kind": "synthetic",
            "test_conditions": "Declared same scalar observable and supplied drag conditions", "conditions_match": "declared_match",
            "filename": "synthetic.csv", "csv_text": "id,req,value,unit,tolerance\r\nforce-a,drag_limit,310,N,15\r\n",
            "mapping": {"measurement_id": "id", "requirement_id": "req", "value": "value", "unit": "unit", "tolerance": "tolerance"}})
        links = TestEvidence(self.store, tests)
        selected = links.investigation_context(self.identity, 1, "drag_limit", comparison["receipt"]["comparison_id"], 2)
        scoped = {**view, "test_evidence": selected}
        self.assertTrue(validate_investigation_context(selected, scoped, "drag_limit"))
        self.assertTrue(validate_investigation_view(scoped, "drag_limit"))
        self.assertEqual(selected["recorded"]["row"]["measurement_requirement"]["status"], "not_met")
        self.assertEqual(selected["recorded"]["row"]["prediction_agreement"]["status"], "within_tolerance")
        self.assertEqual(self.store.get(self.identity, 1)["run"], view["run"])

    def test_historic_scalar_test_remains_readable_beside_separate_downstream_interface_review(self):
        from sixd.project_investigation import validate_investigation_view
        from sixd.test_evidence import TestEvidence, validate_investigation_context
        from sixd.workspace_test_data import WorkspaceTestData

        baseline = self.baseline()
        tests = WorkspaceTestData(self.store)
        receipt = tests.run(self.identity, 1, baseline["run"]["run_id"], {
            "schema": "sixd.test-comparison-spec.v1", "name": "Synthetic mount witness",
            "source": "Constructed, not measured hardware", "data_kind": "synthetic",
            "test_conditions": "Declared same scalar stress observable and beam loading", "conditions_match": "declared_match",
            "filename": "mount.csv", "csv_text": "id,req,value,unit,tolerance\r\nmount-a,mount_stress,210000,Pa,20000\r\n",
            "mapping": {"measurement_id": "id", "requirement_id": "req", "value": "value", "unit": "unit", "tolerance": "tolerance"}})["receipt"]
        original = deepcopy(receipt["row_results"][0])
        changed = deepcopy(baseline["project"])
        changed["interfaces"][0]["description"] = "Revised declaration of load-transfer applicability"
        self.store.save_revision(self.identity, 1, changed)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("Review warning cannot force a solver")):
            current = self.store.run(self.identity, 2)
        self.assertIn("mount_stress", current["system_interfaces"]["impact"]["interface_review_requirement_ids"])
        links = TestEvidence(self.store, tests)
        linked = links.summary(self.identity, 2)["comparisons"][0]["rows"][0]
        self.assertEqual(linked["applicability"]["status"], "same_dependencies")
        self.assertEqual({key: value for key, value in linked.items() if key != "applicability"}, original)
        selected = links.investigation_context(self.identity, 2, "mount_stress", receipt["comparison_id"], 2)
        scoped = {**current, "test_evidence": selected}
        self.assertTrue(validate_investigation_context(selected, scoped, "mount_stress"))
        self.assertTrue(validate_investigation_view(scoped, "mount_stress"))
        self.assertEqual(selected["recorded"]["tested_revision"], 1)
        self.assertEqual(selected["recorded"]["row"], original)

    def test_invalid_architecture_save_is_atomic_and_stale_draft_is_rejected(self):
        view = self.baseline()
        before = self.contents()
        bad = deepcopy(view["project"])
        bad["systems"][0]["parent_id"] = "prop"  # vehicle -> prop -> vehicle is a hierarchy cycle.
        with self.assertRaises(WorkspaceError):
            self.store.save_revision(self.identity, 1, bad)
        self.assertEqual(self.contents(), before)
        self.store.save_revision(self.identity, 1, deepcopy(view["project"]))
        with self.assertRaises(ConflictError):
            self.systems.preview(self.identity, 1, view["project"])


if __name__ == "__main__":
    unittest.main()
