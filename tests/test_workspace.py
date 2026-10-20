"""Connected workspace persistence and evidence applicability, without AI."""
from copy import deepcopy
from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import workspace
from sixd.engineering import STEFAN_BOLTZMANN, evaluate_models
from sixd.lifecycle import verify_review
from sixd.project_examples import example_projects
from sixd.workspace import ConflictError, WorkspaceError, WorkspaceStore


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        # Windows sandbox's package Temp can disallow SQLite journalling.
        directory = ROOT / "work"
        directory.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "workspace.sqlite3"
        self.store = WorkspaceStore(self.path)
        self.identity = self.store.ensure_default()

    def test_default_real_calculation_is_idempotent_and_survives_reopen(self):
        initial = self.store.get(self.identity)
        self.assertEqual(initial["revision"], 1)
        self.assertEqual(len(initial["run"]["review"]["findings"]), 7)
        statuses = [item["status"] for item in initial["run"]["review"]["findings"].values()]
        self.assertEqual(statuses.count("met"), 6)
        self.assertEqual(initial["run"]["review"]["unresolved_requirements"], ["control_tracking"])
        self.assertEqual(initial["run"]["live_model_calls"], 0)
        reopened = WorkspaceStore(self.path)
        self.assertEqual(reopened.ensure_default(), self.identity)
        self.assertEqual(reopened.get(self.identity), initial)
        self.assertEqual(len(reopened.list_projects()), 1)
        self.assertTrue(verify_review(initial["run"]["review"]))

    def test_nonfixture_heat_edit_calculates_actual_value_and_reuses_unaffected_models(self):
        initial = self.store.get(self.identity)
        project = deepcopy(initial["project"])
        project["inputs"]["heat_input"]["value"] = 700
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("Preview must not calculate")):
            impact = self.store.preview_change(self.identity, 1, project)
        self.assertEqual(impact["affected_model_ids"], ["thermal"])
        self.assertEqual(impact["affected_requirement_ids"], ["thermal_limit"])
        saved = self.store.save_revision(self.identity, 1, project)
        self.assertIsNone(saved["run"])
        self.assertTrue(saved["prior_run"]["stale"])
        self.assertEqual(saved["prior_run"]["revision"], 1)
        with patch.object(workspace, "evaluate_models", wraps=evaluate_models) as calculate:
            result = self.store.run(self.identity, 2)
        called_ids = [call.args[0]["models"][0]["id"] for call in calculate.call_args_list]
        self.assertEqual(called_ids, ["thermal"])
        run = result["run"]
        self.assertEqual(run["executed_model_ids"], ["thermal"])
        self.assertEqual(set(run["reused_model_ids"]), {"propulsion", "mount", "atmospheric_load", "control"})
        expected = (700 / (0.8 * STEFAN_BOLTZMANN) + 3 ** 4) ** 0.25
        actual = run["model_results"]["thermal"]["metrics"]["equilibrium_temperature"]["value"]
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-12))
        self.assertEqual(run["review"]["findings"]["thermal_limit"]["status"], "not_met")
        self.assertEqual(run["model_origins"]["propulsion"]["run_id"], initial["run"]["run_id"])
        self.assertEqual(run["model_origins"]["propulsion"]["revision"], 1)
        self.assertEqual(run["model_origins"]["thermal"]["run_id"], run["run_id"])
        self.assertEqual(result["comparison"]["previous_evidence_needs_rechecking"], ["thermal_limit"])
        reopened = WorkspaceStore(self.path)
        self.assertEqual(reopened.get(self.identity)["run"]["review"], run["review"])
        self.assertEqual(reopened.get(self.identity, 1)["project"], initial["project"])
        self.assertEqual(reopened.get(self.identity, 1)["run"], initial["run"])

    def test_limit_only_edit_reuses_metrics_but_reassesses_the_requirement(self):
        initial = self.store.get(self.identity)
        project = deepcopy(initial["project"])
        project["inputs"]["maximum_temperature"]["value"] = 200
        impact = self.store.preview_change(self.identity, 1, project)
        self.assertEqual(impact["affected_model_ids"], [])
        self.assertEqual(impact["affected_requirement_ids"], ["thermal_limit"])
        self.store.save_revision(self.identity, 1, project)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No physics needs recalculation")):
            result = self.store.run(self.identity, 2)
        self.assertEqual(result["run"]["executed_model_ids"], [])
        self.assertEqual(result["run"]["review"]["findings"]["thermal_limit"]["status"], "not_met")
        self.assertEqual(result["run"]["model_results"], initial["run"]["model_results"])

    def test_browser_json_roundtrip_does_not_rerun_unchanged_integral_float_inputs(self):
        initial = self.store.get(self.identity)
        # Match JSON.stringify: integral JSON numbers lose the trailing '.0'.
        project = json.loads(json.dumps(initial["project"]),
                             parse_float=lambda text: int(float(text)) if float(text).is_integer() else float(text))
        self.assertIsInstance(initial["project"]["inputs"]["young_modulus"]["value"], float)
        self.assertIsInstance(project["inputs"]["young_modulus"]["value"], int)
        project["inputs"]["heat_input"]["value"] = 700
        project["inputs"]["heat_input"]["source"] = "User-declared revised heat load"
        impact = self.store.preview_change(self.identity, 1, project)
        self.assertEqual(impact["changed_inputs"], ["heat_input"])
        self.assertEqual(impact["affected_model_ids"], ["thermal"])
        self.store.save_revision(self.identity, 1, project)
        with patch.object(workspace, "evaluate_models", wraps=evaluate_models) as calculate:
            updated = self.store.run(self.identity, 2)
        self.assertEqual([call.args[0]["models"][0]["id"] for call in calculate.call_args_list], ["thermal"])
        self.assertEqual(updated["run"]["executed_model_ids"], ["thermal"])
        self.assertIn("mount", updated["run"]["reused_model_ids"])
        self.assertEqual(updated["run"]["model_origins"]["mount"]["run_id"], initial["run"]["run_id"])

    def test_reuse_number_normalization_preserves_distinct_exact_values(self):
        project = self.store.get(self.identity)["project"]
        model = next(item for item in project["models"] if item["id"] == "mount")
        sources = workspace._sources()
        def key(value):
            candidate = deepcopy(project)
            candidate["inputs"]["young_modulus"]["value"] = value
            return workspace._model_key(candidate, model, sources, workspace.MODEL_VERSIONS)
        self.assertEqual(key(70000000000), key(70000000000.0))
        self.assertNotEqual(key(70000000000.0), key(math.nextafter(70000000000.0, math.inf)))
        # Avoid a float-cast canonicalization that collapses large unequal ints.
        self.assertNotEqual(key(9007199254740992), key(9007199254740993))

    def test_input_source_change_requires_new_evidence_even_for_same_value(self):
        project = self.store.get(self.identity)["project"]
        project["inputs"]["heat_input"]["source"] = "Revised declared thermal loading basis"
        impact = self.store.preview_change(self.identity, 1, project)
        self.assertEqual(impact["affected_model_ids"], ["thermal"])
        self.store.save_revision(self.identity, 1, project)
        result = self.store.run(self.identity, 2)
        self.assertEqual(result["run"]["executed_model_ids"], ["thermal"])

    def test_unrun_intervening_revisions_keep_the_nearest_reviewed_ancestor(self):
        project = self.store.get(self.identity)["project"]
        project["inputs"]["heat_input"]["value"] = 700
        self.store.save_revision(self.identity, 1, project)
        project["inputs"]["maximum_burn_duration"]["value"] = 5000
        self.store.save_revision(self.identity, 2, project)
        pending = self.store.get(self.identity)
        self.assertEqual(pending["prior_run"]["revision"], 1)
        self.assertEqual(set(pending["impact"]["affected_requirement_ids"]), {"thermal_limit", "burn_duration"})
        completed = self.store.run(self.identity, 3)
        self.assertEqual(completed["run"]["executed_model_ids"], ["thermal"])
        self.assertEqual(completed["run"]["review"]["findings"]["burn_duration"]["evidence"]["limit"]["value"], 5000)
        self.assertEqual([item["has_current_run"] for item in self.store.get(self.identity, 1)["revisions"]], [True, False, True])

    def test_repeated_current_revision_run_keeps_prior_design_comparison(self):
        initial = self.store.get(self.identity)
        project = deepcopy(initial["project"])
        project["inputs"]["heat_input"]["value"] = 700
        self.store.save_revision(self.identity, 1, project)
        self.store.run(self.identity, 2)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("All same-revision results reusable")):
            repeated = self.store.run(self.identity, 2)
        self.assertEqual(repeated["run"]["executed_model_ids"], [])
        self.assertEqual(repeated["prior_run"]["revision"], 1)
        self.assertEqual(repeated["comparison"]["from_revision"], "1")
        self.assertEqual(repeated["comparison"]["to_revision"], "2")
        self.assertEqual(repeated["comparison"]["changed_inputs"], ["heat_input"])

    def test_verifier_change_makes_same_revision_receipt_stale_and_disables_reuse(self):
        before = self.store.get(self.identity)
        changed = deepcopy(before["run"]["review"]["verification_sources"])
        changed["engineering.py"] = "a" * 64
        # Simulate a freshly restarted runtime with changed loaded verifier code.
        with patch("sixd.lifecycle._verification_sources", return_value=changed), \
                patch.object(workspace, "_LOADED_VERIFICATION_SOURCES", changed):
            stale = self.store.get(self.identity)
            self.assertIsNone(stale["run"])
            self.assertTrue(stale["prior_run"]["stale"])
            self.assertTrue(stale["impact"]["verification_sources_changed"])
            self.assertEqual(len(stale["impact"]["affected_model_ids"]), 5)
            updated = self.store.run(self.identity, 1)
            self.assertEqual(updated["run"]["reused_model_ids"], [])
            self.assertEqual(len(updated["run"]["executed_model_ids"]), 5)
            self.assertEqual(updated["run"]["review"]["verification_sources"], changed)
        # Returning to old sources can use the earlier current-source receipt,
        # rather than mislabelling the changed-source run as fresh.
        self.assertEqual(self.store.get(self.identity)["run"]["run_id"], before["run"]["run_id"])

    def test_live_source_edit_requires_restart_before_any_new_execution(self):
        before = self.store.get(self.identity)
        changed = deepcopy(before["run"]["review"]["verification_sources"])
        changed["engineering.py"] = "b" * 64
        with patch("sixd.lifecycle._verification_sources", return_value=changed), \
                patch.object(workspace, "evaluate_models", side_effect=AssertionError("Old loaded code must not run")):
            stale = self.store.get(self.identity)
            self.assertIsNone(stale["run"])
            self.assertTrue(stale["prior_run"]["stale"])
            with self.assertRaisesRegex(WorkspaceError, "Restart 6D"):
                self.store.run(self.identity, 1)
        after = self.store.get(self.identity)
        self.assertEqual(after["run"], before["run"])
        self.assertEqual(after["prior_run"], before["prior_run"])

    def test_source_edit_during_run_does_not_save_a_relabelled_receipt(self):
        project = self.store.get(self.identity)["project"]
        project["inputs"]["heat_input"]["value"] = 700
        self.store.save_revision(self.identity, 1, project)
        original_sources = workspace._sources()
        changed_sources = deepcopy(original_sources)
        changed_sources["engineering.py"] = "c" * 64
        # The guard captures loaded code; the review sees an edited file.
        with patch("sixd.lifecycle._verification_sources", side_effect=[original_sources, changed_sources]):
            with self.assertRaisesRegex(WorkspaceError, "changed during the run"):
                self.store.run(self.identity, 2)
        view = self.store.get(self.identity)
        self.assertIsNone(view["run"])
        self.assertEqual(view["prior_run"]["revision"], 1)

    def test_conflicting_and_invalid_saves_leave_existing_revision_untouched(self):
        original = self.store.get(self.identity)
        malformed = deepcopy(original["project"])
        malformed["inputs"]["heat_input"]["value"] = float("nan")
        with self.assertRaises(WorkspaceError):
            self.store.save_revision(self.identity, 1, malformed)
        self.assertEqual(self.store.get(self.identity), original)
        valid = deepcopy(original["project"])
        valid["inputs"]["heat_input"]["value"] = 300
        saved = self.store.save_revision(self.identity, 1, valid)
        for method in (self.store.save_revision, self.store.preview_change):
            with self.assertRaises(ConflictError):
                method(self.identity, 1, valid)
        self.assertEqual(self.store.get(self.identity), saved)
        self.assertEqual(self.store.get(self.identity, 1), {**original, "latest_revision": 2,
                         "revisions": saved["revisions"]})

    def test_adapter_version_change_disables_old_result_reuse(self):
        # Versions are captured in both the reuse key and immutable receipt.
        new_versions = {**workspace.MODEL_VERSIONS, "radiative_equilibrium": "2"}
        with patch.dict(workspace.MODEL_VERSIONS, {"radiative_equilibrium": "2"}), \
                patch.object(workspace, "_LOADED_ADAPTER_VERSIONS", new_versions):
            stale = self.store.get(self.identity)
            self.assertIsNone(stale["run"])
            updated = self.store.run(self.identity, 1)
            self.assertEqual(updated["run"]["executed_model_ids"], ["thermal"])
            self.assertEqual(updated["run"]["model_results"]["thermal"]["model_version"], "2")
            self.assertTrue(verify_review(updated["run"]["review"]))

    def test_requirement_definition_change_reassesses_without_rerunning_physics(self):
        project = self.store.get(self.identity)["project"]
        thermal = next(item for item in project["requirements"] if item["id"] == "thermal_limit")
        thermal["operator"] = ">="
        impact = self.store.preview_change(self.identity, 1, project)
        self.assertEqual(impact["changed_requirements"], ["thermal_limit"])
        self.assertEqual(impact["affected_requirement_ids"], ["thermal_limit"])
        self.store.save_revision(self.identity, 1, project)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No physics changed")):
            updated = self.store.run(self.identity, 2)
        self.assertEqual(updated["run"]["review"]["findings"]["thermal_limit"]["status"], "not_met")

    def test_invalid_adapter_inputs_are_saved_as_design_data_but_never_pass(self):
        project = self.store.get(self.identity)["project"]
        project["inputs"]["emissivity"]["value"] = -1
        self.store.save_revision(self.identity, 1, project)
        result = self.store.run(self.identity, 2)
        self.assertEqual(result["run"]["model_results"]["thermal"]["status"], "invalid_inputs")
        self.assertEqual(result["run"]["model_results"]["thermal"]["metrics"], {})
        self.assertEqual(result["run"]["review"]["findings"]["thermal_limit"]["status"], "not_assessed")

    def test_duplicate_project_ids_and_invented_revisions_fail(self):
        original = self.store.get(self.identity)
        with self.assertRaises(ConflictError):
            self.store.create_project(original["project"])
        for value in (True, 0, -1, "1", 1.5):
            with self.subTest(revision=value), self.assertRaises(WorkspaceError):
                self.store.get(self.identity, value)
        with self.assertRaises(WorkspaceError):
            self.store.run(self.identity, 999)
        with self.assertRaises(WorkspaceError):
            self.store.get("missing-project")
        self.assertEqual(self.store.get(self.identity), original)

    def test_new_import_has_no_claimed_run_and_canonical_revision(self):
        project = example_projects()["baseline"]
        project["project_id"] = "second-project"
        project["revision"] = "External design revision B"
        imported = self.store.create_project(project)
        self.assertIsNone(imported["run"])
        self.assertIsNone(imported["prior_run"])
        self.assertEqual(imported["project"]["revision"], "1")
        self.assertEqual(len(imported["impact"]["affected_model_ids"]), 4)
        self.assertEqual(len(self.store.list_projects()), 2)

    def test_corrupted_review_receipt_is_rejected_on_reopen(self):
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute("SELECT sequence,receipt FROM runs").fetchone()
            receipt = json.loads(row[1])
            receipt["review"]["findings"]["thermal_limit"]["status"] = "met-invented"
            # Even matching the outer checksum cannot bypass review verification.
            connection.execute("UPDATE runs SET receipt=?,digest=? WHERE sequence=?",
                               (workspace._encode(receipt), workspace._digest(receipt), row[0]))
            connection.commit()
        with self.assertRaisesRegex(WorkspaceError, "receipt is inconsistent"):
            WorkspaceStore(self.path).get(self.identity)


if __name__ == "__main__":
    unittest.main()
