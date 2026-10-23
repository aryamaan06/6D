"""Current model guidance follows the recorded domain and evidence gap.

These checks exercise saved calculated cases; they do not establish physical
validity or semantic correctness of live model explanations.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sixd.engineering import evaluate_models
from sixd.explanation_quality import build_guidance
from sixd.lifecycle import review_project
from sixd.project_examples import example_projects
from sixd.workspace_ai import WorkspaceAI


def reviewed(project):
    return review_project(project, evaluate_models(project))


class CurrentGuidanceTests(unittest.TestCase):
    def assert_resolved_bases(self, guidance, review):
        for item in guidance["review_actions"] + guidance["missing_information"]:
            for pointer in item["basis"]:
                value = review
                for part in pointer.split("/")[1:]:
                    value = value[part.replace("~1", "/").replace("~0", "~")]
                self.assertIsNotNone(value, pointer)

    def guidance(self, project, requirement):
        review = reviewed(project)
        before = deepcopy(review)
        value = build_guidance(project, review, requirement)
        self.assertEqual(review, before)
        self.assertEqual(value["canonical_assessment"]["status"], review["findings"][requirement]["status"])
        self.assert_resolved_bases(value, review)
        return value, review

    def test_flight_offers_domain_review_without_extending_to_complete_flight(self):
        project = example_projects()["powered_flight_review"]
        value, _ = self.guidance(project, "burnout_height")
        action = next(item for item in value["review_actions"] if item["id"] == "review_model_applicability")
        self.assertIn("burnout", action["action"])
        self.assertIn("mass depletion", action["action"])
        self.assertIn("exponential atmosphere", action["action"])
        self.assertIn("landing and whole-mission performance require separate evidence", action["action"])
        self.assertIn("/evidence/vertical_flight/not_assessed", action["basis"])

    def test_flight_grid_disagreement_points_to_retained_flight_diagnostics(self):
        project = example_projects()["powered_flight_review"]
        for name in ("altitude_numerical_tolerance", "velocity_numerical_tolerance"):
            project["inputs"][name]["value"] = 1e-14
        project["inputs"]["relative_numerical_tolerance"]["value"] = 0
        value, review = self.guidance(project, "burnout_height")
        self.assertEqual(value["canonical_assessment"]["status"], "not_assessed")
        self.assertEqual(review["evidence"]["vertical_flight"]["status"], "completed")
        self.assertFalse(review["evidence"]["vertical_flight"]["flight_response"]["diagnostics"]["grid_agreement_met"])
        action = next(item for item in value["review_actions"] if item["id"] == "resolve_flight_accuracy")
        self.assertIn("/evidence/vertical_flight/flight_response/diagnostics", action["basis"])
        self.assertIn("altitude and velocity", action["action"])
        self.assertIn("absolute and relative", action["action"])
        self.assertIn("Do not loosen tolerances", action["action"])
        self.assertNotIn("resolve_orbital_accuracy", [item["id"] for item in value["review_actions"]])
        self.assertNotIn("position_tolerance_m", str(value))

    def test_flight_near_limit_is_not_a_unit_or_orbit_issue(self):
        project = example_projects()["powered_flight_review"]
        first = reviewed(project)
        self.assertTrue(first["evidence"]["vertical_flight"]["flight_response"]["diagnostics"]["grid_agreement_met"])
        project["inputs"]["maximum_dynamic_pressure"]["value"] = first["evidence"]["vertical_flight"]["metrics"]["max_sampled_dynamic_pressure"]["value"]
        value, _ = self.guidance(project, "dynamic_pressure")
        self.assertEqual(value["canonical_assessment"]["status"], "not_assessed")
        action = next(item for item in value["review_actions"] if item["id"] == "resolve_flight_accuracy")
        self.assertIn("metric allowance overlaps", action["action"])
        self.assertNotIn("resolve_comparison_units", [item["id"] for item in value["review_actions"]])

    def test_attitude_refinement_failure_is_not_presented_as_input_typo(self):
        project = example_projects()["attitude_review"]
        for name in ("angle_numerical_tolerance", "rate_numerical_tolerance"):
            project["inputs"][name]["value"] = 1e-18
        value, review = self.guidance(project, "pointing_window")
        self.assertEqual(review["evidence"]["pointing"]["status"], "invalid_inputs")
        self.assertEqual(review["evidence"]["pointing"]["metrics"], {})
        action = next(item for item in value["review_actions"] if item["id"] == "resolve_attitude_accuracy")
        self.assertIn("/evidence/pointing/issues", action["basis"])
        self.assertIn("angle or angular-rate", action["action"])
        self.assertIn("no completed pointing or rate result", action["action"])
        self.assertNotIn("resolve_invalid_inputs", [item["id"] for item in value["review_actions"]])

    def test_real_attitude_input_error_keeps_input_guidance(self):
        project = example_projects()["attitude_review"]
        project["inputs"]["inertia"]["value"] = -1
        value, _ = self.guidance(project, "pointing_window")
        self.assertIn("resolve_invalid_inputs", [item["id"] for item in value["review_actions"]])
        self.assertNotIn("resolve_attitude_accuracy", [item["id"] for item in value["review_actions"]])

    def test_orbital_accuracy_keeps_existing_id_and_applicable_basis(self):
        project = example_projects()["orbital_review"]
        project["models"][0].pop("accuracy")
        value, _ = self.guidance(project, "orbit_max_radius")
        action = next(item for item in value["review_actions"] if item["id"] == "resolve_orbital_accuracy")
        self.assertEqual(action["title"], "Resolve the orbit's numerical accuracy gap")
        self.assertIn("/evidence/orbit/numerical_accuracy", action["basis"])
        self.assertIn("position/velocity", action["action"])

    def test_historical_read_projection_preserves_recorded_guidance_and_summary(self):
        historical = {"state": "completed", "summary": "Original recorded explanation.",
                      "guidance": {"review_actions": [{"id": "resolve_orbital_accuracy", "title": "Original saved wording"}]},
                      "explanation_quality": {"method": "historical recorded policy"}}
        before = deepcopy(historical)
        manager = WorkspaceAI.__new__(WorkspaceAI)
        # Existing captured guidance needs no new source lookup or calculation.
        projected = manager._projection(historical, None)
        self.assertEqual(projected["guidance_origin"], "recorded")
        self.assertEqual(projected["guidance"], historical["guidance"])
        self.assertEqual(projected["summary"], historical["summary"])
        projected["guidance"]["review_actions"][0]["title"] = "Caller mutation"
        self.assertEqual(historical, before)


if __name__ == "__main__":
    unittest.main()
