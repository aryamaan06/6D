"""Authoring contracts, empty drafts and immutable authored-model revisions."""
from copy import deepcopy
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import engineering, lifecycle, orbital_adapter, project_authoring, simulation, workspace
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceError, WorkspaceStore


def blank_project():
    return {"schema": "sixd.project.v1", "project_id": "authored-space-study",
            "name": "Supplied space-system study", "revision": "1",
            "description": "Purpose: screen supplied component choices. Assumptions: declared by the author.",
            "lifecycle_stage": "design", "inputs": {}, "models": [], "requirements": []}


class AuthoringCatalogTests(unittest.TestCase):
    def test_catalog_exposes_maintained_binding_and_metric_contracts_without_calculation(self):
        expected_metrics = {
            "attitude_control": {"final_error":"rad", "final_rate":"rad/s", "max_sampled_error":"rad", "max_sampled_rate":"rad/s", "max_assessed_error":"rad", "max_assessed_rate":"rad/s", "max_sampled_command_torque":"N*m", "max_sampled_applied_torque":"N*m", "sampled_saturation_fraction":"1"},
            "ideal_propulsion": {"propellant_required": "kg", "propellant_available": "kg",
                "propellant_margin": "kg", "mass_flow": "kg/s", "burn_duration": "s"},
            "static_cantilever": {"bending_stress": "Pa", "tip_deflection": "m"},
            "radiative_equilibrium": {"equilibrium_temperature": "K"},
            "drag_load": {"dynamic_pressure": "Pa", "drag_force": "N"},
            "orbital_trajectory": {"min_radius_m": "m", "max_radius_m": "m", "max_speed_m_s": "m/s",
                                   "final_radius_m": "m", "final_speed_m_s": "m/s"},
            "power_energy_budget": {"peak_load_power": "W", "minimum_power_margin": "W", "total_load_energy": "J",
                "total_generated_energy": "J", "battery_energy_required": "J", "battery_energy_margin": "J",
                "minimum_generation_margin": "W", "max_battery_power_required": "W", "minimum_bus_power_margin": "W",
                "minimum_battery_power_margin": "W", "total_duration": "s", "surplus_generation_energy": "J"},
        }
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("No physics")), \
                patch.object(simulation, "simulate", side_effect=AssertionError("No solver")):
            catalog = project_authoring.catalog()
        self.assertEqual(set(catalog), {"schema", "models", "operators", "lifecycle_stages"})
        self.assertEqual(catalog["schema"], "sixd.model-catalog.v1")
        self.assertEqual(catalog["operators"], ["<=", ">=", "=="])
        self.assertEqual(set(catalog["lifecycle_stages"]), lifecycle.STAGES)
        self.assertEqual([item["type"] for item in catalog["models"]], list(engineering.MODEL_PARAMETERS))
        self.assertEqual(len(catalog["models"]), 7)
        for model in catalog["models"]:
            model_type = model["type"]
            self.assertEqual(set(model), {"type", "title", "description", "version", "parameters",
                                          "metrics", "assumptions", "not_assessed", "applicability"} | ({"profile"} if model_type == "power_energy_budget" else set()))
            self.assertEqual(model["applicability"]["physical_applicability"], "not_assessed")
            self.assertTrue(model["applicability"]["references"])
            if model_type == "power_energy_budget":
                self.assertEqual(model["profile"]["mode_limit"], 16)
                self.assertEqual(model["profile"]["roles"]["mode.<index>.<mode_id>.duration"], "s")
            self.assertEqual(model["version"], engineering.MODEL_VERSIONS[model_type])
            self.assertEqual(model["parameters"], [{"name": name, "unit": unit}
                             for name, unit in engineering.MODEL_PARAMETERS[model_type].items()])
            self.assertEqual({item["name"]: item["unit"] for item in model["metrics"]}, expected_metrics[model_type])
            self.assertTrue(all(set(item) == {"name", "unit", "label"} and item["label"] for item in model["metrics"]))
            self.assertEqual(model["assumptions"], engineering._ASSUMPTIONS[model_type])
            self.assertEqual(model["not_assessed"], engineering._NOT_ASSESSED[model_type])
            self.assertTrue(model["title"] and model["description"])
        catalog["models"][0]["parameters"][0]["unit"] = "invented"
        catalog["models"][0]["assumptions"].clear()
        self.assertNotEqual(project_authoring.catalog(), catalog)
        self.assertEqual(engineering.MODEL_PARAMETERS["ideal_propulsion"]["initial_mass"], "kg")


class AuthoringPreflightTests(unittest.TestCase):
    def test_supported_orbital_and_unsupported_projects_never_calculate_or_mutate(self):
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("No physics")), \
                patch.object(orbital_adapter, "evaluate", side_effect=AssertionError("No orbital adapter")), \
                patch.object(simulation, "simulate", side_effect=AssertionError("No solver")):
            for name in ("baseline", "orbital_review", "missing_evidence"):
                project = example_projects()[name]
                before = deepcopy(project)
                result = project_authoring.preflight(project)
                self.assertEqual(result["schema"], "sixd.authoring-preflight.v1")
                self.assertTrue(result["can_run"], result)
                self.assertEqual(result["counts"], {key: len(project[key]) for key in ("inputs", "models", "requirements")})
                self.assertEqual(project, before)
                if name == "missing_evidence":
                    self.assertEqual([item["code"] for item in result["issues"]], ["unsupported_model"])
                    self.assertEqual(result["issues"][0]["severity"], "warning")

    def test_empty_draft_reports_both_missing_collections(self):
        result = project_authoring.preflight(blank_project())
        self.assertFalse(result["can_run"])
        self.assertEqual([item["code"] for item in result["issues"]], ["empty_models", "empty_requirements"])
        self.assertEqual(result["counts"], {"inputs": 0, "models": 0, "requirements": 0})

    def test_binding_metric_and_unit_errors_are_actionable(self):
        project = example_projects()["baseline"]
        del project["models"][0]["inputs"]["initial_mass"]
        project["models"][0]["inputs"]["invented"] = "dry_mass"
        project["inputs"]["thrust"]["unit"] = "kN"
        project["requirements"][0]["metric"] = "unknown_metric"
        project["inputs"]["maximum_temperature"]["unit"] = "C"
        result = project_authoring.preflight(project)
        self.assertFalse(result["can_run"])
        errors = [item for item in result["issues"] if item["severity"] == "error"]
        self.assertEqual({item["code"] for item in errors}, {"missing_parameter", "extra_parameter",
                         "input_unit_mismatch", "unknown_metric", "requirement_unit_mismatch"})
        self.assertTrue(all(item["path"].startswith("project.") and item["message"] for item in errors))
        self.assertIn("project.models[0].inputs.initial_mass", [item["path"] for item in errors])
        self.assertIn("project.requirements[0].metric", [item["path"] for item in errors])

    def test_unused_input_and_model_without_requirement_are_only_warnings(self):
        project = example_projects()["baseline"]
        project["inputs"]["unused"] = {"value": 12, "unit": "m", "source": "Supplied unused dimension"}
        project["requirements"] = [item for item in project["requirements"] if item["model_id"] != "thermal"]
        result = project_authoring.preflight(project)
        self.assertTrue(result["can_run"])
        self.assertEqual({item["code"] for item in result["issues"]}, {"unreferenced_input", "unassessed_model"})
        self.assertTrue(all(item["severity"] == "warning" for item in result["issues"]))

    def test_structural_invalidity_returns_issues_for_missing_metric_and_references(self):
        invalid = [None, [], {}, {**blank_project(), "inputs": []}]
        for field in ("metric", "limit_input", "model_id"):
            project = example_projects()["baseline"]
            if field == "metric":
                del project["requirements"][0][field]
            else:
                project["requirements"][0][field] = "missing"
            invalid.append(project)
        project = blank_project()
        project["inputs"]["bad"] = {"value": float("nan"), "unit": "m", "source": "Supplied"}
        invalid.append(project)
        for project in invalid:
            with self.subTest(project=project):
                result = project_authoring.preflight(project)
                self.assertFalse(result["can_run"])
                self.assertEqual(result["issues"][0]["code"], "invalid_project")
                self.assertEqual(result["issues"][0]["severity"], "error")

    def test_numeric_domain_policy_remains_with_adapter(self):
        project = example_projects()["baseline"]
        project["inputs"]["heat_input"]["value"] = -1
        project["inputs"]["emissivity"]["value"] = 2
        self.assertTrue(project_authoring.preflight(project)["can_run"])
        result = engineering.evaluate_models(project)
        self.assertEqual(result["thermal"]["status"], "invalid_inputs")
        self.assertEqual(result["thermal"]["metrics"], {})


class AuthoredWorkspaceTests(unittest.TestCase):
    def setUp(self):
        directory = ROOT / "work"
        directory.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "authored.sqlite3"
        self.store = WorkspaceStore(self.path)

    def test_blank_revision_persists_but_cannot_produce_a_review_or_receipt(self):
        blank = blank_project()
        saved = self.store.create_project(blank)
        self.assertEqual(saved["project"], blank)
        self.assertIsNone(saved["run"])
        self.assertEqual(saved["graph"], {"systems": [], "links": []})
        reopened = WorkspaceStore(self.path)
        self.assertEqual(reopened.get(blank["project_id"]), saved)
        revised = deepcopy(blank)
        revised["description"] += " Additional supplied purpose and assumptions."
        saved = reopened.save_revision(blank["project_id"], 1, revised)
        self.assertEqual(saved["revision"], 2)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No calculation")), \
                patch.object(lifecycle, "review_project", side_effect=AssertionError("No review")):
            for revision in (1, 2):
                with self.assertRaisesRegex(WorkspaceError, "one model and one requirement"):
                    reopened.run(blank["project_id"], revision)
        with closing(sqlite3.connect(str(self.path))) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 0)
        with self.assertRaises(ValueError):
            lifecycle.validate_project(blank)
        with self.assertRaises(ValueError):
            lifecycle.review_project(blank, {})
        forged = lifecycle._assemble(blank, {}, engineering.MODEL_VERSIONS, lifecycle._verification_sources())
        self.assertEqual(forged["review_status"], "supported_requirements_met")
        with self.assertRaises(ValueError):
            lifecycle.verify_review(forged)

    def test_empty_collections_do_not_relax_record_or_reference_validation(self):
        project = blank_project()
        project["inputs"]["bad"] = {"value": True, "unit": "m", "source": "Supplied"}
        with self.assertRaises(ValueError):
            lifecycle.validate_project(project, allow_empty=True)
        project = blank_project()
        project["models"] = [{"id": "user-model", "type": "unknown", "inputs": {"x": "absent"}}]
        with self.assertRaisesRegex(WorkspaceError, "missing input"):
            self.store.create_project(project)
        project = example_projects()["baseline"]
        project["models"] = []
        with self.assertRaisesRegex(WorkspaceError, "missing model"):
            self.store.create_project(project)

    def test_model_only_revision_cannot_run_or_save_a_receipt(self):
        project = example_projects()["baseline"]
        project["requirements"] = []
        self.store.create_project(project)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No calculation")):
            with self.assertRaises(WorkspaceError):
                self.store.run(project["project_id"], 1)
        self.assertIsNone(self.store.get(project["project_id"])["run"])

    def test_unreviewed_revisions_compare_additions_and_removals_with_previous_saved_configuration(self):
        blank = blank_project()
        identity = blank["project_id"]
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("Saving must not calculate")):
            initial = self.store.create_project(blank)
            self.assertIsNone(initial["configuration_base"])
            project = example_projects()["baseline"]
            project["project_id"] = identity
            second = self.store.save_revision(identity, 1, project)
            self.assertIsNone(second["run"])
            self.assertIsNone(second["prior_run"])
            self.assertEqual(second["configuration_base"], {"revision": 1, "project": blank})
            self.assertEqual(second["impact"]["added_inputs"], sorted(project["inputs"]))
            self.assertEqual(second["impact"]["added_models"], sorted(item["id"] for item in project["models"]))
            self.assertEqual(second["impact"]["added_requirements"], sorted(item["id"] for item in project["requirements"]))

            project["models"] = [item for item in project["models"] if item["id"] != "thermal"]
            project["requirements"] = [item for item in project["requirements"] if item["model_id"] != "thermal"]
            removed_inputs = ["heat_input", "radiator_area", "emissivity", "background_temperature", "maximum_temperature"]
            for input_id in removed_inputs:
                del project["inputs"][input_id]
            third = self.store.save_revision(identity, 2, project)
            self.assertEqual(third["configuration_base"], {"revision": 2, "project": second["project"]})
            self.assertEqual(third["impact"]["removed_inputs"], sorted(removed_inputs))
            self.assertEqual(third["impact"]["removed_models"], ["thermal"])
            self.assertEqual(third["impact"]["removed_requirements"], ["thermal_limit"])
            self.assertEqual(third["impact"]["added_models"], [])
            self.assertEqual(third["impact"]["affected_model_ids"], [item["id"] for item in project["models"]])
            self.assertEqual(third["impact"]["affected_requirement_ids"], [item["id"] for item in project["requirements"]])
            self.assertIsNone(third["run"])
            self.assertIsNone(third["comparison"])
            self.assertEqual(self.store.get(identity, 2)["configuration_base"], second["configuration_base"])

    def test_add_remap_remove_models_preserves_reuse_and_historical_revisions(self):
        blank = blank_project()
        identity = blank["project_id"]
        self.store.create_project(blank)
        source = example_projects()["baseline"]
        thermal = deepcopy(next(item for item in source["models"] if item["id"] == "thermal"))
        drag = deepcopy(next(item for item in source["models"] if item["id"] == "atmospheric_load"))
        project = deepcopy(blank)

        def add_model(model):
            project["models"].append(model)
            requirements = [deepcopy(item) for item in source["requirements"] if item["model_id"] == model["id"]]
            project["requirements"].extend(requirements)
            ids = set(model["inputs"].values()) | {item["limit_input"] for item in requirements}
            project["inputs"].update({key: deepcopy(source["inputs"][key]) for key in ids})

        add_model(thermal)
        self.store.save_revision(identity, 1, project)
        first = self.store.run(identity, 2)
        add_model(drag)
        self.store.save_revision(identity, 2, project)
        second = self.store.run(identity, 3)
        self.assertIsNone(second["configuration_base"])
        self.assertEqual(second["run"]["executed_model_ids"], ["atmospheric_load"])
        self.assertEqual(second["run"]["reused_model_ids"], ["thermal"])
        self.assertEqual(second["run"]["model_origins"]["thermal"]["run_id"], first["run"]["run_id"])

        project["inputs"]["replacement_heat"] = deepcopy(project["inputs"]["heat_input"])
        project["models"][0]["inputs"]["heat_input"] = "replacement_heat"
        del project["inputs"]["heat_input"]
        preview = self.store.preview_change(identity, 3, project)
        self.assertEqual(preview["affected_model_ids"], ["thermal"])
        self.store.save_revision(identity, 3, project)
        third = self.store.run(identity, 4)
        self.assertEqual(third["run"]["executed_model_ids"], ["thermal"])
        self.assertEqual(third["run"]["reused_model_ids"], ["atmospheric_load"])

        project["models"] = [drag]
        project["requirements"] = [item for item in project["requirements"] if item["model_id"] == drag["id"]]
        used = set(drag["inputs"].values()) | {item["limit_input"] for item in project["requirements"]}
        project["inputs"] = {key: value for key, value in project["inputs"].items() if key in used}
        self.store.save_revision(identity, 4, project)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("Unchanged drag is reusable")):
            fourth = self.store.run(identity, 5)
        self.assertEqual(fourth["run"]["executed_model_ids"], [])
        self.assertEqual(fourth["run"]["reused_model_ids"], ["atmospheric_load"])
        self.assertEqual(fourth["comparison"]["removed_models"], ["thermal"])
        self.assertEqual(fourth["comparison"]["removed_requirements"], ["thermal_limit"])
        reopened = WorkspaceStore(self.path)
        self.assertEqual(reopened.get(identity, 1)["project"], blank)
        for revision, earlier in ((2, first), (3, second), (4, third)):
            self.assertEqual(reopened.get(identity, revision)["project"], earlier["project"])
            self.assertEqual(reopened.get(identity, revision)["run"], earlier["run"])
        self.assertTrue(lifecycle.verify_review(fourth["run"]["review"]))


if __name__ == "__main__":
    unittest.main()
