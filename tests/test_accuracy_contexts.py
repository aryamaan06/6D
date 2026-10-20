"""Numerical evidence gaps cannot become passes through ancillary workflows.

The constructed orbit is not a flight design. These tests exercise consumers of
the numerical assessment, not the physical accuracy of the propagator.
"""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import lifecycle, project_investigation, systems, test_evidence
from sixd.engineering import evaluate_models
from sixd.explanation_quality import build_guidance, evaluate_explanation, explanation_acceptance
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore
from sixd.workspace_test_data import WorkspaceTestData


def orbital_project():
    project = example_projects()["orbital_review"]
    next(model for model in project["models"] if model["id"] == "orbit").pop("accuracy", None)
    return project


class AccuracyConsumerTests(unittest.TestCase):
    def test_interface_cannot_use_completed_v2_orbit_without_accuracy(self):
        project = orbital_project()
        project["systems"] = [
            {"id": "orbit_system", "title": "Orbit", "description": "Constructed grouping.",
             "parent_id": None, "model_ids": ["orbit"]},
            {"id": "receiver", "title": "Declared receiving limit", "description": "No coupling.",
             "parent_id": None, "model_ids": []},
        ]
        project["interfaces"] = [{"id": "radius_contract", "title": "Sampled radius contract",
            "description": "Constructed scalar comparison only.", "from_system": "orbit_system", "to_system": "receiver",
            "source": {"kind": "model_metric", "model_id": "orbit", "metric": "max_radius_m"},
            "target_input": "maximum_sampled_radius", "quantity": "Radius", "unit": "m", "operator": "<=", "critical": True}]
        metric = {"value": 7_000_000, "unit": "m"}
        source = {"model_type": "orbital_trajectory", "model_version": "2", "status": "completed",
                  "metrics": {"max_radius_m": metric}, "fingerprint": "retained-source"}
        review = {"digest": "retained-review", "evidence": {"orbit": source}}
        before = deepcopy(project)
        with patch.object(systems, "_current_review", return_value=(review, None)):
            row = systems.evaluate_interfaces(project, review)["rows"][0]
        self.assertEqual(row["status"], "not_assessed")
        self.assertIsNone(row["source_value"])
        self.assertEqual(row["issues"][0]["code"], "accuracy_not_assessed")
        self.assertEqual(project, before)

        # A retained v1 result keeps its historical scalar-only semantics.
        source["model_version"] = "1"
        with patch.object(systems, "_current_review", return_value=(review, None)):
            old_row = systems.evaluate_interfaces(project, review)["rows"][0]
        self.assertEqual(old_row["status"], "met")
        self.assertEqual(old_row["source_value"], metric)

        source.update(model_version="2", numerical_accuracy={"status": "supported", "criteria": {
            "position_tolerance_m": 10, "velocity_tolerance_m_s": 1, "source": "Constructed declared allowances."}})
        project["inputs"]["maximum_sampled_radius"]["value"] = 7_000_005
        with patch.object(systems, "_current_review", return_value=(review, None)):
            near_row = systems.evaluate_interfaces(project, review)["rows"][0]
        self.assertEqual(near_row["status"], "not_assessed")
        self.assertIsNone(near_row["source_value"])
        self.assertEqual(near_row["issues"][0]["code"], "insufficient_accuracy")

    def test_compact_context_preserves_optional_quality_without_changing_legacy_shape(self):
        project = orbital_project()
        requirement = next(item for item in project["requirements"] if item["model_id"] == "orbit")
        source = {"model_version": "1", "status": "completed", "fingerprint": "retained",
                  "metrics": {requirement["metric"]: {"value": 7_000_000, "unit": "m"}},
                  "assumptions": [], "not_assessed": [], "issues": []}
        review = {"evidence": {"orbit": source}, "verification_sources": {}}
        legacy = test_evidence._compact_model(project, requirement, review)
        self.assertNotIn("numerical_accuracy", legacy)
        self.assertNotIn("applicability", legacy)
        source.update(model_version="2", numerical_accuracy={"status": "insufficient_accuracy", "reason": "Constructed refinement gap."},
                      applicability={"physical_validity": "not_established"})
        compact = test_evidence._compact_model(project, requirement, review)
        self.assertEqual(compact["numerical_accuracy"], source["numerical_accuracy"])
        self.assertEqual(compact["applicability"], source["applicability"])
        compact["numerical_accuracy"]["status"] = "tampered"
        self.assertEqual(source["numerical_accuracy"]["status"], "insufficient_accuracy")

    def test_upstream_assistant_projection_keeps_accuracy_gap_and_optional_applicability(self):
        project = orbital_project()
        project["models"].append({"id": "consumer", "type": "static_cantilever", "inputs": {},
                                  "links": {"length": {"model_id": "orbit", "metric": "final_radius_m", "unit": "m",
                                                       "rationale": "Constructed provenance test, not a physical load mapping."}}})
        source = {"model_id": "orbit", "model_type": "orbital_trajectory", "model_version": "2",
                  "status": "completed", "metrics": {"final_radius_m": {"value": 7_000_000, "unit": "m"}},
                  "assumptions": [], "not_assessed": [], "issues": [], "fingerprint": "retained",
                  "model_definition": deepcopy(project["models"][0]),
                  "numerical_accuracy": {"status": "insufficient_accuracy", "reason": "Constructed gap."},
                  "applicability": {"physical_validity": "not_established"}}
        review = {"evidence": {"orbit": source}, "verification_sources": {}}
        payload = project_investigation._upstream_evidence(project, review, "consumer")
        self.assertEqual(payload["models"]["orbit"]["numerical_accuracy"], source["numerical_accuracy"])
        self.assertEqual(payload["models"]["orbit"]["applicability"], source["applicability"])
        projected = project_investigation._provider_evidence({"upstream_evidence": payload})
        self.assertEqual(projected["upstream_evidence"]["models"]["orbit"]["numerical_accuracy"]["status"], "insufficient_accuracy")

    def test_missing_accuracy_guidance_does_not_send_engineer_to_fix_matching_units(self):
        project = orbital_project()
        review = lifecycle.review_project(project, evaluate_models(project))
        requirement = next(item for item in project["requirements"] if item["model_id"] == "orbit")
        guidance = build_guidance(project, review, requirement["id"])
        self.assertEqual(guidance["canonical_assessment"]["status"], "not_assessed")
        actions = {action["id"]: action for action in guidance["review_actions"]}
        self.assertIn("resolve_orbital_accuracy", actions)
        self.assertNotIn("resolve_comparison_units", actions)
        self.assertIn("Do not loosen tolerances", actions["resolve_orbital_accuracy"]["action"])
        self.assertIn("not a guaranteed error bound", actions["resolve_orbital_accuracy"]["action"])

    def test_provider_projection_omits_large_reference_grids_without_altering_full_evidence(self):
        accuracy = {"schema": "sixd.orbit-accuracy.v1", "status": "not_assessed", "criteria": None,
                    "reason": "Constructed evidence gap.", "comparisons": [],
                    "reference_levels": [{"samples": [{"position_m": [1, 2, 3]}] * 100}]}
        payload = {"recorded_evidence": {"numerical_accuracy": accuracy, "status": "completed"}}
        projected = project_investigation._provider_evidence(payload)
        compact = projected["recorded_evidence"]["numerical_accuracy"]
        self.assertNotIn("reference_levels", compact)
        self.assertEqual(compact["reference_levels_projection"]["artifact_digest"], lifecycle._digest(accuracy))
        self.assertEqual(compact["reference_levels_projection"]["omitted_grid_count"], 1)
        self.assertIn("reference_levels", payload["recorded_evidence"]["numerical_accuracy"])

    def test_inaccurate_canonical_finding_cannot_be_explained_as_a_pass(self):
        project = orbital_project()
        review = lifecycle.review_project(project, evaluate_models(project))
        requirement = next(item for item in project["requirements"] if item["model_id"] == "orbit")
        finding = review["findings"][requirement["id"]]
        record = {"canonical_finding": deepcopy(finding), "finding_status": finding["status"],
                  "summary": "The requirement is met. Review the inputs.", "evidence": {}, "citations": []}
        quality = evaluate_explanation(record)
        self.assertIn("canonical_status_contradiction", [flag["code"] for flag in quality["flags"]])
        self.assertFalse(explanation_acceptance(record)["accepted"])

    def test_frozen_test_context_retains_unresolved_accuracy_instead_of_recreating_pass(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
            store = WorkspaceStore(Path(directory) / "workspace.sqlite3")
            project = orbital_project()
            store.create_project(project)
            view = store.run(project["project_id"], 1)
            requirement = next(item for item in project["requirements"] if item["model_id"] == "orbit")
            finding = view["run"]["review"]["findings"][requirement["id"]]
            self.assertEqual(finding["status"], "not_assessed")
            self.assertIsNone(finding["evidence"])
            manager = WorkspaceTestData(store)
            comparison = manager.run(project["project_id"], 1, view["run"]["run_id"], {
                "schema": "sixd.test-comparison-spec.v1", "name": "Constructed orbit observation",
                "source": "Synthetic arithmetic row, not physical data.", "data_kind": "synthetic",
                "test_conditions": "Declared same scalar observable, reference frame and time window.",
                "conditions_match": "declared_match", "filename": "orbit.csv",
                "mapping": {"measurement_id": "id", "requirement_id": "req", "value": "value", "unit": "unit", "tolerance": "tol"},
                "csv_text": "id,req,value,unit,tol\nconstructed," + requirement["id"] + ",7000000,m,10\n",
            })
            helper = test_evidence.TestEvidence(store, manager)
            context = helper.investigation_context(project["project_id"], 1, requirement["id"], comparison["receipt"]["comparison_id"], 2)
            self.assertTrue(test_evidence.validate_investigation_context(context, view, requirement["id"]))
            self.assertEqual(context["recorded"]["finding"]["status"], "not_assessed")
            self.assertIsNone(context["recorded"]["finding"]["evidence"])
            self.assertIn("numerical_accuracy", context["recorded"]["model"])
            self.assertEqual(context["recorded"]["row"]["prediction_agreement"]["status"], "not_assessed")


if __name__ == "__main__":
    unittest.main()
