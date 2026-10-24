"""Requirement evidence must remain tied to its exact declared configuration."""
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.lifecycle import compare_reviews, review_project, validate_project, verify_review


def project():
    # Constructed analytical examples, not flight-qualified vehicle data.
    return {
        "schema": "sixd.project.v1", "project_id": "constructed-space-models",
        "name": "Constructed requirement review", "revision": "A", "description": "Unit-test inputs only.",
        "lifecycle_stage": "design",
        "inputs": {
            "force": {"value": 12, "unit": "N", "source": "constructed reference"},
            "length": {"value": 2, "unit": "m", "source": "constructed reference"},
            "modulus": {"value": 6, "unit": "Pa", "source": "constructed reference"},
            "inertia": {"value": 4, "unit": "m^4", "source": "constructed reference"},
            "fiber": {"value": 3, "unit": "m", "source": "constructed reference"},
            "stress_limit": {"value": 20, "unit": "Pa", "source": "declared test requirement"},
            "density": {"value": 1, "unit": "kg/m^3", "source": "constructed reference"},
            "speed": {"value": 4, "unit": "m/s", "source": "constructed reference"},
            "coefficient": {"value": 1, "unit": "1", "source": "supplied test coefficient"},
            "area": {"value": 2, "unit": "m^2", "source": "constructed reference"},
            "drag_limit": {"value": 20, "unit": "N", "source": "declared test requirement"},
            "unbound": {"value": 1, "unit": "kg", "source": "not used by any model"},
        },
        "models": [
            {"id": "mount", "type": "static_cantilever", "inputs": {
                "tip_force": "force", "length": "length", "young_modulus": "modulus",
                "second_moment": "inertia", "outer_fiber": "fiber"}},
            {"id": "atmosphere", "type": "drag_load", "inputs": {
                "density": "density", "relative_speed": "speed", "drag_coefficient": "coefficient",
                "reference_area": "area"}},
        ],
        "requirements": [
            {"id": "strength", "title": "Declared mount stress limit", "model_id": "mount",
             "metric": "bending_stress", "operator": "<=", "limit_input": "stress_limit", "critical": True},
            {"id": "drag", "title": "Declared aerodynamic load limit", "model_id": "atmosphere",
             "metric": "drag_force", "operator": "<=", "limit_input": "drag_limit", "critical": True},
        ],
    }


def recorded_results():
    # Hand-computed F*L*c/I = 18 Pa and 0.5*rho*V^2*Cd*A = 16 N.
    return {
        "mount": {"model_id": "mount", "model_type": "static_cantilever", "model_version": "1",
                  "status": "completed", "metrics": {"bending_stress": {"value": 18, "unit": "Pa"}},
                  "assumptions": ["Static cantilever reference only."],
                  "not_assessed": ["Buckling and fatigue."], "issues": []},
        "atmosphere": {"model_id": "atmosphere", "model_type": "drag_load", "model_version": "1",
                       "status": "completed", "metrics": {"drag_force": {"value": 16, "unit": "N"}},
                       "assumptions": ["Supplied coefficient applies to this scenario."],
                       "not_assessed": ["Coefficient applicability is not independently verified."], "issues": []},
    }


def rehash(review):
    body = {key: value for key, value in review.items() if key != "digest"}
    review["digest"] = sha256(json.dumps(body, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=True, allow_nan=False).encode()).hexdigest()


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.project = project()
        self.results = recorded_results()
        self.review = review_project(self.project, self.results)

    def test_fresh_engineering_results_support_only_declared_requirements(self):
        from sixd.engineering import evaluate_models
        review = review_project(self.project, evaluate_models(self.project))
        self.assertEqual(review["review_status"], "supported_requirements_met")
        self.assertEqual(review["findings"]["strength"]["evidence"]["metric"]["value"], 18)
        self.assertEqual(review["findings"]["drag"]["evidence"]["metric"]["value"], 16)
        self.assertIs(review["launch_authorization"], False)
        self.assertTrue(review["exclusions"])

    def test_snapshots_are_independent_of_mutated_caller_objects(self):
        snapshot = validate_project(self.project)
        self.project["inputs"]["force"]["value"] = 999
        self.results["mount"]["metrics"]["bending_stress"]["value"] = 999
        self.assertEqual(snapshot["inputs"]["force"]["value"], 12)
        self.assertEqual(self.review["project"]["inputs"]["force"]["value"], 12)
        self.assertEqual(self.review["evidence"]["mount"]["metrics"]["bending_stress"]["value"], 18)
        self.assertTrue(verify_review(self.review))

    def test_strict_project_records_reject_unknown_fields_at_every_level(self):
        for path in ((), ("inputs", "force"), ("models", 0), ("requirements", 0)):
            malformed = deepcopy(self.project)
            target = malformed
            for key in path:
                target = target[key]
            target["surprise"] = "not allowed"
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_project(malformed)

    def test_nonfinite_boolean_and_non_json_numbers_are_rejected(self):
        for value in (True, False, math.nan, math.inf, -math.inf, "12", 10**1000):
            malformed = deepcopy(self.project)
            malformed["inputs"]["force"]["value"] = value
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                validate_project(malformed)

    def test_missing_references_and_duplicate_ids_are_rejected(self):
        mutations = [
            lambda p: p["models"][0]["inputs"].update(tip_force="missing"),
            lambda p: p["requirements"][0].update(model_id="missing"),
            lambda p: p["requirements"][0].update(limit_input="missing"),
            lambda p: p["models"].append(deepcopy(p["models"][0])),
            lambda p: p["requirements"].append(deepcopy(p["requirements"][0])),
            lambda p: p.update(models=[]),
            lambda p: p.update(requirements=[]),
            lambda p: p["models"][0].update(inputs=[]),
            lambda p: p["requirements"][0].update(critical=1),
            lambda p: p["requirements"][0].update(operator="approximately"),
        ]
        for mutation in mutations:
            malformed = deepcopy(self.project)
            mutation(malformed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_project(malformed)

    def test_required_strings_and_schemas_are_not_inferred(self):
        for key, value in (("description", " "), ("name", None), ("schema", "unknown"),
                           ("lifecycle_stage", "flight_certified")):
            malformed = deepcopy(self.project)
            malformed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_project(malformed)

    def test_missing_result_is_incomplete_even_when_other_requirement_passes(self):
        results = deepcopy(self.results)
        del results["mount"]
        review = review_project(self.project, results)
        self.assertEqual(review["review_status"], "incomplete")
        self.assertEqual(review["unresolved_requirements"], ["strength"])
        self.assertEqual(review["findings"]["drag"]["status"], "met")

    def test_failure_remains_visible_when_another_critical_requirement_is_unknown(self):
        self.project["inputs"]["drag_limit"]["value"] = 10
        del self.results["mount"]
        review = review_project(self.project, self.results)
        self.assertEqual(review["review_status"], "incomplete")
        self.assertEqual(review["failed_requirements"], ["drag"])
        self.assertEqual(review["findings"]["drag"]["status"], "not_met")
        self.assertEqual(review["unresolved_requirements"], ["strength"])
        self.assertIs(review["launch_authorization"], False)

    def test_unknown_noncritical_requirement_still_makes_review_incomplete(self):
        self.project["requirements"][0]["critical"] = False
        del self.results["mount"]
        self.assertEqual(review_project(self.project, self.results)["review_status"], "incomplete")

    def test_failure_without_unknowns_is_requirements_not_met(self):
        self.project["inputs"]["stress_limit"]["value"] = 17
        review = review_project(self.project, self.results)
        self.assertEqual(review["review_status"], "requirements_not_met")
        self.assertEqual(review["failed_requirements"], ["strength"])
        self.assertEqual(review["unresolved_requirements"], [])

    def test_unsupported_type_cannot_pass_through_attached_completed_metrics(self):
        self.project["models"][0]["type"] = "whole_rocket_magic"
        self.results["mount"].update(model_type="whole_rocket_magic", model_version=None)
        review = review_project(self.project, self.results)
        self.assertEqual(review["findings"]["strength"]["status"], "not_assessed")
        self.assertEqual(review["evidence"]["mount"]["metrics"], {})
        self.assertEqual(review["review_status"], "incomplete")
        self.assertTrue(verify_review(review))

    def test_status_cannot_be_overridden_by_numeric_metric(self):
        for status in ("invalid_inputs", "not_assessed"):
            results = deepcopy(self.results)
            results["mount"]["status"] = status
            with self.subTest(status=status):
                review = review_project(self.project, results)
                self.assertEqual(review["findings"]["strength"]["status"], "not_assessed")
                self.assertIsNone(review["findings"]["strength"]["evidence"])

    def test_missing_metric_and_unit_mismatch_abstain(self):
        for change in ("missing", "different unit"):
            results = deepcopy(self.results)
            if change == "missing":
                results["mount"]["metrics"] = {}
            else:
                results["mount"]["metrics"]["bending_stress"]["unit"] = "MPa"
            with self.subTest(change=change):
                self.assertEqual(review_project(self.project, results)["findings"]["strength"]["status"], "not_assessed")

    def test_malformed_result_identity_version_and_shape_are_rejected(self):
        mutations = [
            lambda r: r["mount"].update(model_id="atmosphere"),
            lambda r: r["mount"].update(model_type="drag_load"),
            lambda r: r["mount"].update(model_version="old"),
            lambda r: r["mount"].update(status="safe_to_launch"),
            lambda r: r["mount"].update(extra="unsupported"),
            lambda r: r["mount"].update(assumptions="not a list"),
            lambda r: r["mount"].update(issues=[1]),
            lambda r: r.update(unregistered=deepcopy(r["mount"])),
        ]
        for mutation in mutations:
            malformed = deepcopy(self.results)
            mutation(malformed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                review_project(self.project, malformed)

    def test_metrics_reject_nonfinite_boolean_or_extra_fields(self):
        for value in (True, False, math.nan, math.inf, "18"):
            malformed = deepcopy(self.results)
            malformed["mount"]["metrics"]["bending_stress"]["value"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                review_project(self.project, malformed)
        self.results["mount"]["metrics"]["bending_stress"]["verdict"] = "met"
        with self.assertRaises(ValueError):
            review_project(self.project, self.results)

    def test_all_operators_apply_exact_declared_comparison(self):
        for operator, limit, expected in (("<=", 18, "met"), (">=", 18, "met"),
                                          ("==", 18, "met"), ("==", 18.000001, "not_met"),
                                          (">=", 19, "not_met")):
            self.project["requirements"][0]["operator"] = operator
            self.project["inputs"]["stress_limit"]["value"] = limit
            with self.subTest(operator=operator, limit=limit):
                self.assertEqual(review_project(self.project, self.results)["findings"]["strength"]["status"], expected)

    def test_bound_value_unit_source_and_limit_changes_invalidate_only_dependencies(self):
        for input_id, key, value in (("force", "value", 13), ("force", "unit", "kN"),
                                     ("force", "source", "different measured version"),
                                     ("stress_limit", "value", 17), ("stress_limit", "unit", "MPa"),
                                     ("stress_limit", "source", "revised requirement source")):
            revised = deepcopy(self.project)
            revised["revision"] = "B"
            revised["inputs"][input_id][key] = value
            new = review_project(revised, self.results)
            comparison = compare_reviews(self.review, new)
            with self.subTest(input_id=input_id, key=key):
                self.assertEqual(comparison["previous_evidence_needs_rechecking"], ["strength"])
                self.assertEqual(comparison["unchanged_evidence_applicability"], ["drag"])
                self.assertEqual(comparison["changed_inputs"], [input_id])

    def test_unbound_input_and_revision_metadata_do_not_infer_physical_impact(self):
        revised = deepcopy(self.project)
        revised["revision"] = "B"
        revised["lifecycle_stage"] = "physical_test"
        revised["inputs"]["unbound"]["value"] = 900
        new = review_project(revised, self.results)
        comparison = compare_reviews(self.review, new)
        self.assertEqual(comparison["previous_evidence_needs_rechecking"], [])
        self.assertEqual(comparison["unchanged_evidence_applicability"], ["drag", "strength"])
        self.assertIs(new["launch_authorization"], False)

    def test_rebinding_and_requirement_changes_invalidate_old_evidence(self):
        revised = deepcopy(self.project)
        revised["inputs"]["other_force"] = deepcopy(revised["inputs"]["force"])
        revised["models"][0]["inputs"]["tip_force"] = "other_force"
        comparison = compare_reviews(self.review, review_project(revised, self.results))
        self.assertEqual(comparison["changed_models"], ["mount"])
        self.assertEqual(comparison["previous_evidence_needs_rechecking"], ["strength"])
        revised = deepcopy(self.project)
        revised["requirements"][0]["critical"] = False
        comparison = compare_reviews(self.review, review_project(revised, self.results))
        self.assertEqual(comparison["changed_requirements"], ["strength"])
        self.assertEqual(comparison["previous_evidence_needs_rechecking"], ["strength"])

    def test_model_upgrade_invalidates_applicability_but_old_review_still_verifies(self):
        from sixd.engineering import MODEL_VERSIONS
        results = deepcopy(self.results)
        results["mount"]["model_version"] = "2"
        with patch.dict(MODEL_VERSIONS, {"static_cantilever": "2"}):
            self.assertTrue(verify_review(self.review))
            new = review_project(self.project, results)
        self.assertTrue(verify_review(new))
        comparison = compare_reviews(self.review, new)
        self.assertEqual(comparison["changed_model_versions"], ["mount"])
        self.assertEqual(comparison["previous_evidence_needs_rechecking"], ["strength"])

    def test_recorded_sources_are_actual_code_hashes_and_bound_to_receipts(self):
        sources = self.review["verification_sources"]
        self.assertEqual(set(sources), {"engineering.py", "lifecycle.py", "__init__.py", "orbital_adapter.py", "simulation.py", "attitude.py", "chains.py", "powered_flight.py", "guided_ascent.py", "staged_ascent.py"})
        for name, fingerprint in sources.items():
            actual = sha256((ROOT / "src" / "sixd" / name).read_bytes()).hexdigest()
            self.assertEqual(fingerprint, actual)
        for evidence in self.review["evidence"].values():
            self.assertEqual(evidence["verification_sources"], sources)

    def test_changed_code_hash_invalidates_previous_evidence_without_version_bump(self):
        recorded_sources = deepcopy(self.review["verification_sources"])
        recorded_sources["engineering.py"] = "f" * 64
        with patch("sixd.lifecycle._verification_sources", return_value=recorded_sources):
            new = review_project(self.project, self.results)
            self.assertTrue(verify_review(self.review))
        self.assertTrue(verify_review(new))
        self.assertEqual(new["adapter_versions"], self.review["adapter_versions"])
        comparison = compare_reviews(self.review, new)
        self.assertEqual(comparison["verification_sources_changed"], ["engineering.py"])
        self.assertEqual(comparison["previous_evidence_needs_rechecking"], ["drag", "strength"])
        self.assertEqual(comparison["unchanged_evidence_applicability"], [])
        self.assertEqual(comparison["changed_model_versions"], [])
        for key in self.review["findings"]:
            self.assertNotEqual(self.review["findings"][key]["dependency_fingerprint"],
                                new["findings"][key]["dependency_fingerprint"])

    def test_malformed_recorded_code_hashes_are_rejected_even_with_recomputed_digest(self):
        for value in ("not-a-hash", "F" * 64, "a" * 63, 1, None):
            malformed = deepcopy(self.review)
            malformed["verification_sources"]["engineering.py"] = value
            rehash(malformed)
            with self.subTest(value=value), self.assertRaises(ValueError):
                verify_review(malformed)
        malformed = deepcopy(self.review)
        del malformed["verification_sources"]["__init__.py"]
        rehash(malformed)
        with self.assertRaises(ValueError):
            verify_review(malformed)

    def test_added_removed_requirements_and_models_are_explicit(self):
        revised = deepcopy(self.project)
        revised["requirements"] = [revised["requirements"][1]]
        revised["models"] = [revised["models"][1]]
        revised["requirements"][0]["id"] = "new_drag_requirement"
        comparison = compare_reviews(self.review, review_project(revised, {"atmosphere": self.results["atmosphere"]}))
        self.assertEqual(comparison["removed_models"], ["mount"])
        self.assertEqual(comparison["removed_requirements"], ["drag", "strength"])
        self.assertEqual(comparison["added_requirements"], ["new_drag_requirement"])
        self.assertEqual(comparison["unchanged_evidence_applicability"], [])

    def test_unassessed_old_requirements_are_not_listed_as_applicable_evidence(self):
        old = review_project(self.project, {})
        comparison = compare_reviews(old, self.review)
        self.assertEqual(comparison["unchanged_evidence_applicability"], [])
        self.assertEqual(comparison["unchanged_unassessed_requirements"], ["drag", "strength"])

    def test_comparison_rejects_different_projects_and_preserves_snapshots(self):
        old_copy = deepcopy(self.review)
        compare_reviews(self.review, self.review)
        self.assertEqual(self.review, old_copy)
        other = deepcopy(self.project)
        other["project_id"] = "another_project"
        with self.assertRaises(ValueError):
            compare_reviews(self.review, review_project(other, self.results))

    def test_json_round_trip_preserves_verification(self):
        restored = json.loads(json.dumps(self.review, allow_nan=False))
        self.assertTrue(verify_review(restored))
        self.assertEqual(restored["digest"], self.review["digest"])

    def test_tampering_is_detected_even_if_only_outer_digest_is_recomputed(self):
        mutations = [
            lambda r: r["project"]["inputs"]["force"].update(value=99),
            lambda r: r["findings"]["strength"].update(status="not_met"),
            lambda r: r["findings"]["strength"].update(dependency_fingerprint="invented"),
            lambda r: r["evidence"]["mount"]["input_records"]["force"].update(source="another source"),
            lambda r: r["evidence"]["mount"]["metrics"]["bending_stress"].update(value=99),
            lambda r: r["verification_sources"].update({"engineering.py": "f" * 64}),
            lambda r: r.update(review_status="safe_to_launch"),
            lambda r: r.update(launch_authorization=True),
        ]
        for mutation in mutations:
            altered = deepcopy(self.review)
            mutation(altered)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verify_review(altered)
            rehash(altered)
            with self.subTest(rehashed=mutation), self.assertRaises(ValueError):
                verify_review(altered)

    def test_result_versions_must_be_strings_or_none_for_unsupported_type(self):
        for version in (1, True, None):
            results = deepcopy(self.results)
            results["mount"]["model_version"] = version
            with self.subTest(version=version), self.assertRaises(ValueError):
                review_project(self.project, results)


if __name__ == "__main__":
    unittest.main()
