"""Orbital engineering evidence and revisions, independent of the browser/AI."""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import engineering, lifecycle, orbital_adapter, simulation, workspace
from sixd.engineering import evaluate_models
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore


class OrbitalEngineeringTests(unittest.TestCase):
    def setUp(self):
        self.project = example_projects()["orbital_review"]
        self.results = evaluate_models(self.project)

    def test_actual_template_binds_full_trajectory_and_four_window_criteria(self):
        result = self.results["orbit"]
        self.assertEqual(result["status"], "completed", result["issues"])
        self.assertEqual(set(result["metrics"]), set(orbital_adapter.METRIC_UNITS))
        self.assertEqual(len(result["simulation"]["samples"]), 2049)
        self.assertEqual(result["numerical_accuracy"]["status"], "supported")
        self.assertGreater(max(abs(row["position_m"][2]) for row in result["simulation"]["samples"]), 5e6)
        report = lifecycle.review_project(self.project, self.results)
        self.assertTrue(lifecycle.verify_review(report))
        self.assertEqual(report["review_status"], "supported_requirements_met")
        self.assertFalse(report["launch_authorization"])
        self.assertEqual(len([item for item in report["findings"].values() if item["model_id"] == "orbit"]), 4)
        self.assertIn("between samples", " ".join(result["assumptions"]))
        self.assertIn("phase error", " ".join(result["not_assessed"]))
        evidence = report["evidence"]["orbit"]
        self.assertEqual(evidence["simulation"], result["simulation"])
        self.assertEqual(evidence["verification_sources"]["simulation.py"], simulation.source_fingerprint())
        self.assertEqual(evidence["input_records"]["position_x"], self.project["inputs"]["position_x"])

    def test_arbitrary_input_binding_and_independent_circular_orbit_reference(self):
        # An inclined orbit around a different ideal primary; one quarter-period
        # has a closed form independent of the adapter or numerical integrator.
        project = deepcopy(self.project)
        mu, radius = 8e13, 3e6
        speed = math.sqrt(mu / radius)
        values = {"mu_m3_s2": mu, "exclusion_radius_m": 1e6,
                  "position_x": 0, "position_y": 0, "position_z": radius,
                  "velocity_x": speed, "velocity_y": 0, "velocity_z": 0,
                  "duration_s": math.pi / 2 * math.sqrt(radius ** 3 / mu), "steps": 1024}
        model = project["models"][0]
        for parameter, value in values.items():
            input_id = "customer_" + parameter
            project["inputs"][input_id] = {"value": value, "unit": orbital_adapter.PARAMETERS[parameter], "source": "Declared alternate constructed primary"}
            model["inputs"][parameter] = input_id
        result = evaluate_models(project)["orbit"]
        self.assertEqual(result["status"], "completed")
        final = result["simulation"]["samples"][-1]
        self.assertLess(math.dist(final["position_m"], [radius, 0, 0]) / radius, 2e-6)
        self.assertAlmostEqual(result["metrics"]["final_radius_m"]["value"] / radius, 1, places=5)
        self.assertEqual(result["simulation"]["spec"]["mu_m3_s2"], mu)
        self.assertTrue(lifecycle.verify_review(lifecycle.review_project(project, evaluate_models(project))))

    def test_incomplete_or_invalid_orbital_inputs_abstain_with_no_artifact(self):
        changes = [
            lambda p: p["inputs"]["steps"].update(value=1024.5),
            lambda p: p["inputs"]["steps"].update(value=16),
            lambda p: p["inputs"]["position_x"].update(unit="km"),
            lambda p: p["inputs"]["velocity_y"].update(value=20000),
            lambda p: p["inputs"]["position_x"].update(value=0),
            lambda p: p["models"][0]["inputs"].pop("position_z"),
            lambda p: p["models"][0]["inputs"].update(thrust="heat_input"),
        ]
        for change in changes:
            project = deepcopy(self.project)
            change(project)
            results = evaluate_models(project)
            with self.subTest(change=change):
                self.assertEqual(results["orbit"]["status"], "invalid_inputs")
                self.assertEqual(results["orbit"]["metrics"], {})
                self.assertNotIn("simulation", results["orbit"])
                review = lifecycle.review_project(project, results)
                self.assertTrue(all(item["status"] == "not_assessed" for item in review["findings"].values() if item["model_id"] == "orbit"))
                self.assertEqual(review["findings"]["thermal_limit"]["status"], "met")

    def test_integer_valued_steps_supported_and_numeric_diagnostics_not_assessable(self):
        self.project["inputs"]["steps"]["value"] = 1024.0
        results = evaluate_models(self.project)
        self.assertEqual(results["orbit"]["status"], "completed")
        self.assertIsInstance(results["orbit"]["simulation"]["spec"]["steps"], int)
        extra = deepcopy(self.project["requirements"][0])
        extra.update(id="diagnostic", metric="max_relative_energy_error", limit_input="steps")
        self.project["requirements"].append(extra)
        review = lifecycle.review_project(self.project, results)
        self.assertEqual(review["findings"]["diagnostic"]["status"], "not_assessed")
        self.assertIsNone(review["findings"]["diagnostic"]["evidence"])

    def test_unsupported_frame_thrust_or_hidden_binding_rejected(self):
        for field in ("frame", "thrust", "mass"):
            project = deepcopy(self.project)
            project["models"][0]["inputs"][field] = "steps"
            result = evaluate_models(project)["orbit"]
            self.assertEqual(result["status"], "invalid_inputs")

    def test_artifact_consistency_rejects_mismatched_metrics_state_source_and_summary(self):
        changes = [
            lambda r: r["orbit"]["metrics"]["max_radius_m"].update(value=1),
            lambda r: r["orbit"]["simulation"]["spec"].update(duration_s=1),
            lambda r: r["orbit"]["simulation"].update(source_fingerprint="0" * 64),
            lambda r: r["orbit"]["simulation"]["summary"].update(max_radius_m=1),
            lambda r: r["orbit"]["simulation"]["samples"][2].update(time_s=0),
            lambda r: r["orbit"]["simulation"]["samples"][2].update(radius_m=1),
            lambda r: r["orbit"]["simulation"]["samples"][2]["position_m"].append(0),
            lambda r: r["orbit"]["simulation"]["samples"].pop(),
            lambda r: r["orbit"].pop("simulation"),
            lambda r: r["thermal"].update(simulation=r["orbit"]["simulation"]),
            lambda r: r["orbit"].update(status="invalid_inputs"),
        ]
        for change in changes:
            results = deepcopy(self.results)
            change(results)
            with self.subTest(change=change), self.assertRaises(ValueError):
                lifecycle.review_project(self.project, results)

    def test_history_retains_orbital_evidence_without_running_current_solver_policy(self):
        report = lifecycle.review_project(self.project, self.results)
        saved = json.loads(json.dumps(report))
        with patch.object(simulation, "simulate", side_effect=AssertionError("History cannot rerun physics")), \
                patch.object(simulation, "validate_spec", side_effect=AssertionError("History cannot use current solver policy")), \
                patch.dict(engineering.MODEL_VERSIONS, {"orbital_trajectory": "2"}):
            self.assertTrue(lifecycle.verify_review(saved))
        self.assertEqual(saved, report)

    def test_legacy_three_source_review_remains_readable_and_comparable(self):
        project = example_projects()["baseline"]
        results = evaluate_models(project)
        sources = {key: value for key, value in lifecycle._verification_sources().items() if key in lifecycle.LEGACY_VERIFICATION_SOURCE_NAMES}
        versions = {key: value for key, value in engineering.MODEL_VERSIONS.items() if key != "orbital_trajectory"}
        with patch.object(lifecycle, "_verification_sources", return_value=sources), \
                patch.dict(engineering.MODEL_VERSIONS, versions, clear=True):
            old = lifecycle.review_project(project, results)
        self.assertEqual(set(old["verification_sources"]), {"__init__.py", "engineering.py", "lifecycle.py"})
        self.assertNotIn("orbital_trajectory", old["adapter_versions"])
        retained = deepcopy(old)
        self.assertTrue(lifecycle.verify_review(old))
        current = lifecycle.review_project(project, results)
        comparison = lifecycle.compare_reviews(old, current)
        self.assertEqual(comparison["verification_sources_changed"], ["attitude.py", "chains.py", "orbital_adapter.py", "simulation.py"])
        self.assertEqual(old, retained)
        # Neither a partial new source set nor an orbital artifact without its
        # retained solver source may be accepted as legacy evidence.
        sources["orbital_adapter.py"] = "0" * 64
        with patch.object(lifecycle, "_verification_sources", return_value=sources), self.assertRaises(ValueError):
            lifecycle.review_project(project, results)
        sources.pop("orbital_adapter.py")
        with patch.object(lifecycle, "_verification_sources", return_value=sources), self.assertRaises(ValueError):
            lifecycle.review_project(self.project, self.results)


class OrbitalRevisionTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "work").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(temporary.cleanup)
        self.store = WorkspaceStore(Path(temporary.name) / "workspace.sqlite3")
        self.project = example_projects()["orbital_review"]
        self.identity = self.project["project_id"]
        self.store.create_project(self.project)
        self.first = self.store.run(self.identity, 1)

    def test_limit_change_reuses_exact_trajectory_and_reassesses_current_limit(self):
        project = deepcopy(self.project)
        project["inputs"]["maximum_sampled_radius"]["value"] = 6_990_000
        preview = self.store.preview_change(self.identity, 1, project)
        self.assertEqual(preview["affected_model_ids"], [])
        self.assertEqual(preview["affected_requirement_ids"], ["orbit_max_radius"])
        self.store.save_revision(self.identity, 1, project)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("Limit changes reuse physics")):
            updated = self.store.run(self.identity, 2)
        run = updated["run"]
        self.assertEqual(run["executed_model_ids"], [])
        self.assertEqual(run["model_results"]["orbit"]["simulation"], self.first["run"]["model_results"]["orbit"]["simulation"])
        self.assertEqual(run["model_origins"]["orbit"]["run_id"], self.first["run"]["run_id"])
        self.assertEqual(run["review"]["findings"]["orbit_max_radius"]["status"], "not_met")
        self.assertEqual(self.store.get(self.identity, 1)["run"]["review"]["findings"]["orbit_max_radius"]["status"], "met")

    def test_orbit_state_change_targets_orbit_and_preserves_thermal_origin(self):
        project = deepcopy(self.project)
        project["inputs"]["position_x"]["value"] = 7_050_000
        preview = self.store.preview_change(self.identity, 1, project)
        self.assertEqual(preview["affected_model_ids"], ["orbit"])
        self.assertEqual(set(preview["affected_requirement_ids"]), {"orbit_min_radius", "orbit_max_radius", "orbit_max_speed", "orbit_final_radius"})
        self.store.save_revision(self.identity, 1, project)
        with patch.object(workspace, "evaluate_models", wraps=evaluate_models) as calculated:
            updated = self.store.run(self.identity, 2)
        self.assertEqual([call.args[0]["models"][0]["id"] for call in calculated.call_args_list], ["orbit"])
        self.assertEqual(updated["run"]["reused_model_ids"], ["thermal"])
        self.assertEqual(updated["run"]["model_origins"]["thermal"]["run_id"], self.first["run"]["run_id"])
        self.assertEqual(updated["run"]["model_results"]["orbit"]["simulation"]["samples"][0]["position_m"][0], 7_050_000)

    def test_unrelated_thermal_change_keeps_orbital_samples_and_origin(self):
        project = deepcopy(self.project)
        project["inputs"]["heat_input"]["value"] = 700
        self.assertEqual(self.store.preview_change(self.identity, 1, project)["affected_model_ids"], ["thermal"])
        self.store.save_revision(self.identity, 1, project)
        updated = self.store.run(self.identity, 2)
        self.assertEqual(updated["run"]["executed_model_ids"], ["thermal"])
        self.assertEqual(updated["run"]["reused_model_ids"], ["orbit"])
        self.assertEqual(updated["run"]["model_results"]["orbit"], self.first["run"]["model_results"]["orbit"])
        self.assertEqual(updated["run"]["model_origins"]["orbit"]["revision"], 1)
        self.assertEqual(updated["run"]["review"]["findings"]["thermal_limit"]["status"], "not_met")
        self.assertEqual(updated["graph"]["systems"][0]["title"], "Orbital dynamics")

    def test_invalid_orbit_revision_saves_explicit_gap_without_current_trajectory(self):
        project = deepcopy(self.project)
        project["inputs"]["steps"]["value"] = 16
        self.store.save_revision(self.identity, 1, project)
        updated = self.store.run(self.identity, 2)
        self.assertEqual(updated["run"]["model_results"]["orbit"]["status"], "invalid_inputs")
        self.assertNotIn("simulation", updated["run"]["model_results"]["orbit"])
        self.assertEqual(updated["run"]["review"]["findings"]["orbit_min_radius"]["status"], "not_assessed")
        self.assertIn("simulation", updated["prior_run"]["model_results"]["orbit"])

    def test_added_orbital_source_makes_legacy_run_stale_without_erasing_it(self):
        # Create an old-shaped static receipt under its retained source/version
        # set, then reopen under the new code. This exercises the SQLite path.
        project = example_projects()["baseline"]
        identity = project["project_id"]
        self.store.create_project(project)
        sources = {key: value for key, value in lifecycle._verification_sources().items() if key in lifecycle.LEGACY_VERIFICATION_SOURCE_NAMES}
        versions = {key: value for key, value in engineering.MODEL_VERSIONS.items() if key != "orbital_trajectory"}
        with patch.object(lifecycle, "_verification_sources", return_value=sources), \
                patch.object(workspace, "_LOADED_VERIFICATION_SOURCES", sources), \
                patch.object(workspace, "_LOADED_ADAPTER_VERSIONS", versions), \
                patch.dict(engineering.MODEL_VERSIONS, versions, clear=True):
            old = self.store.run(identity, 1)
        reopened = self.store.get(identity, 1)
        self.assertIsNone(reopened["run"])
        self.assertEqual(reopened["prior_run"]["review"], old["run"]["review"])
        self.assertTrue(reopened["prior_run"]["stale"])
        self.assertTrue(lifecycle.verify_review(reopened["prior_run"]["review"]))
        new = self.store.run(identity, 1)
        self.assertEqual(set(new["run"]["executed_model_ids"]), {"propulsion", "mount", "thermal", "atmospheric_load"})
        self.assertEqual(new["run"]["reused_model_ids"], [])


if __name__ == "__main__":
    unittest.main()
