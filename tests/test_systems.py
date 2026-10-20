"""Declared interfaces are bounded scalar checks, never coupled simulation."""
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
from sixd.engineering import evaluate_models
from sixd.lifecycle import review_project, validate_project
from sixd.systems import architecture_impact, evaluate_interfaces, systems_graph, validate_architecture


def project():
    """Hand arithmetic: drag=.5*1.2*50²*.8*.25=300 N; beam stress=30 kPa."""
    return {
        "schema": "sixd.project.v1", "project_id": "constructed-interface-case",
        "name": "Constructed space-vehicle scalar contracts", "revision": "1",
        "description": "Independent arithmetic fixture, not a vehicle design or flight approval.",
        "lifecycle_stage": "design",
        "inputs": {key: {"value": value, "unit": unit, "source": "Constructed independent test declaration."}
                   for key, value, unit in [
                       ("density", 1.2, "kg/m^3"), ("speed", 50, "m/s"), ("coefficient", .8, "1"),
                       ("area", .25, "m^2"), ("force", 300, "N"), ("length", 1, "m"),
                       ("modulus", 1e9, "Pa"), ("inertia", 1e-4, "m^4"), ("fiber", .01, "m"),
                       ("drag_limit", 305, "N"), ("stress_limit", 35000, "Pa"),
                       ("capacity", 400, "N"), ("declaration", 300, "N"), ("unbound", 17, "kg")]},
        "models": [
            {"id": "aero", "type": "drag_load", "inputs": {"density": "density", "relative_speed": "speed",
                "drag_coefficient": "coefficient", "reference_area": "area"}},
            {"id": "beam", "type": "static_cantilever", "inputs": {"tip_force": "force", "length": "length",
                "young_modulus": "modulus", "second_moment": "inertia", "outer_fiber": "fiber"}},
        ],
        "requirements": [
            {"id": "drag", "title": "Supplied drag limit", "model_id": "aero", "metric": "drag_force",
             "operator": "<=", "limit_input": "drag_limit", "critical": True},
            {"id": "strength", "title": "Supplied bending limit", "model_id": "beam", "metric": "bending_stress",
             "operator": "<=", "limit_input": "stress_limit", "critical": True},
        ],
        "systems": [
            {"id": "vehicle", "title": "Space vehicle", "description": "Declared grouping.", "parent_id": None, "model_ids": []},
            {"id": "flight", "title": "Flight loads", "description": "", "parent_id": "vehicle", "model_ids": ["aero"]},
            {"id": "mount", "title": "Mount", "description": "", "parent_id": "vehicle", "model_ids": ["beam"]},
            {"id": "deployment", "title": "Deployment", "description": "No assigned model.", "parent_id": None, "model_ids": []},
        ],
        "interfaces": [
            {"id": "drag_to_mount", "title": "Declared drag/beam force agreement", "description": "No vector or load-path mapping is verified.",
             "from_system": "flight", "to_system": "mount", "source": {"kind": "model_metric", "model_id": "aero", "metric": "drag_force"},
             "target_input": "force", "quantity": "force magnitude", "unit": "N", "operator": "==", "critical": True},
            {"id": "mount_to_deployment", "title": "Declared deployment load comparison", "description": "Constructed declaration only.",
             "from_system": "mount", "to_system": "deployment", "source": {"kind": "input", "input_id": "declaration"},
             "target_input": "capacity", "quantity": "force magnitude", "unit": "N", "operator": "<=", "critical": False},
        ],
    }


def review(value):
    return review_project(value, evaluate_models(value))


class ArchitectureValidationTests(unittest.TestCase):
    def test_optional_fields_do_not_modify_legacy_or_caller(self):
        current = project()
        original = deepcopy(current)
        self.assertIsNone(validate_architecture(current))
        self.assertEqual(current, original)
        legacy = deepcopy(current)
        del legacy["systems"]
        del legacy["interfaces"]
        saved = deepcopy(legacy)
        self.assertIsNone(validate_architecture(legacy))
        self.assertEqual(legacy, saved)
        self.assertEqual(systems_graph(legacy), [])
        self.assertEqual(evaluate_interfaces(legacy)["counts"], {"met": 0, "not_met": 0, "not_assessed": 0, "total": 0})

    def test_graph_has_explicit_tree_and_subtree_model_requirement_ownership(self):
        current = project()
        rows = {row["id"]: row for row in systems_graph(current)}
        root = rows["subsystem:vehicle"]
        self.assertEqual(root["model_ids"], ["aero", "beam"])
        self.assertEqual(root["requirement_ids"], ["drag", "strength"])
        self.assertEqual(root["own_model_ids"], [])
        self.assertIsNone(root["parent_id"])
        self.assertEqual(rows["subsystem:flight"]["parent_id"], "subsystem:vehicle")
        self.assertEqual(rows["subsystem:flight"]["own_model_ids"], ["aero"])
        self.assertEqual(rows["subsystem:deployment"]["model_ids"], [])
        self.assertTrue(all(row["declared"] for row in rows.values()))
        rows["subsystem:flight"]["own_model_ids"].append("tamper")
        self.assertEqual(current["systems"][1]["model_ids"], ["aero"])

    def test_model_metric_may_belong_to_source_descendant(self):
        current = project()
        current["interfaces"][0]["from_system"] = "vehicle"
        validate_architecture(current)
        current["interfaces"][0]["from_system"] = "deployment"
        with self.assertRaisesRegex(ValueError, "source model must belong"):
            validate_architecture(current)

    def test_unassigned_models_and_explicit_input_associations_are_allowed(self):
        current = project()
        current["interfaces"] = current["interfaces"][1:]
        current["systems"][1]["model_ids"] = []
        current["interfaces"][0]["from_system"] = "flight"
        validate_architecture(current)
        self.assertEqual(systems_graph(current)[1]["model_ids"], [])

    def test_strict_fields_collection_types_and_references(self):
        mutations = [
            lambda p: p.update(systems=None), lambda p: p.update(interfaces={}),
            lambda p: p["systems"][0].update(extra=True),
            lambda p: p["systems"][0].pop("description"),
            lambda p: p["systems"][1].update(parent_id="missing"),
            lambda p: p["systems"][1].update(parent_id=3),
            lambda p: p["systems"][1].update(model_ids="aero"),
            lambda p: p["systems"][1].update(model_ids=["missing"]),
            lambda p: p["systems"][1].update(title=" "),
            lambda p: p["systems"].append(deepcopy(p["systems"][1])),
            lambda p: p["systems"][2]["model_ids"].append("aero"),
            lambda p: p["systems"][1]["model_ids"].append("aero"),
            lambda p: p["interfaces"][0].update(extra=True),
            lambda p: p["interfaces"][0].pop("quantity"),
            lambda p: p["interfaces"][0].update(to_system="flight"),
            lambda p: p["interfaces"][0].update(to_system="missing"),
            lambda p: p["interfaces"][0].update(target_input="missing"),
            lambda p: p["interfaces"][0].update(operator="<"),
            lambda p: p["interfaces"][0].update(critical=1),
            lambda p: p["interfaces"][0].update(unit=""),
            lambda p: p["interfaces"][0].update(source={"kind": "guess"}),
            lambda p: p["interfaces"][0].update(source={"kind": "input", "input_id": "missing"}),
            lambda p: p["interfaces"][0].update(source={"kind": "input", "input_id": "force", "model_id": "aero"}),
            lambda p: p["interfaces"][0]["source"].update(model_id="missing"),
            lambda p: p["interfaces"][0]["source"].update(metric=""),
            lambda p: p["interfaces"].append(deepcopy(p["interfaces"][0])),
        ]
        for mutate in mutations:
            current = project()
            mutate(current)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                validate_architecture(current)

    def test_parent_cycles_rejected_and_dangling_ancestor_is_value_error(self):
        for system_id, parent in (("vehicle", "vehicle"), ("vehicle", "flight"), ("vehicle", "missing")):
            current = project()
            # Child-first order exercises dangling ancestry before parent record.
            current["systems"] = current["systems"][1:] + current["systems"][:1]
            next(row for row in current["systems"] if row["id"] == system_id)["parent_id"] = parent
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                validate_architecture(current)

    def test_limits_bound_architecture_without_disallowing_interface_cycles(self):
        current = project()
        current["systems"] += [{"id": f"extra-{i}", "title": "Empty", "description": "", "parent_id": None, "model_ids": []}
                               for i in range(60)]
        validate_architecture(current)
        current["systems"].append({"id": "overflow", "title": "Extra", "description": "", "parent_id": None, "model_ids": []})
        with self.assertRaisesRegex(ValueError, "64"):
            validate_architecture(current)
        current = project()
        current["interfaces"] = [dict(deepcopy(current["interfaces"][1]), id=f"contract-{i}") for i in range(128)]
        validate_architecture(current)
        current["interfaces"].append(dict(deepcopy(current["interfaces"][0]), id="overflow"))
        with self.assertRaisesRegex(ValueError, "128"):
            validate_architecture(current)
        current = project()
        current["interfaces"][1]["to_system"] = "flight"
        validate_architecture(current)


class InterfaceEvaluationTests(unittest.TestCase):
    def test_independent_scalar_reference_and_no_physics_or_mutation(self):
        current = project()
        recorded = review(current)
        original, original_review = deepcopy(current), deepcopy(recorded)
        with patch("sixd.engineering.evaluate_models", side_effect=AssertionError("No adapter execution allowed")):
            result = evaluate_interfaces(current, recorded)
        self.assertEqual(result["schema"], "sixd.interface-checks.v1")
        self.assertEqual(result["counts"], {"met": 2, "not_met": 0, "not_assessed": 0, "total": 2})
        first, second = result["rows"]
        self.assertEqual(first["source_value"], {"value": 300, "unit": "N"})
        self.assertEqual(first["target_value"]["value"], 300)
        self.assertEqual(first["source_origin"]["review_digest"], recorded["digest"])
        self.assertEqual(first["dependency_input_ids"], ["area", "coefficient", "density", "force", "speed"])
        self.assertEqual(second["source_origin"]["kind"], "declared_input")
        self.assertIn("declaration", second["reason"].lower() + str(result["limitations"]))
        self.assertEqual(current, original)
        self.assertEqual(recorded, original_review)

    def test_declared_inputs_can_compare_without_review_model_metric_cannot(self):
        current = project()
        result = evaluate_interfaces(current)
        self.assertEqual(result["rows"][0]["status"], "not_assessed")
        self.assertEqual(result["rows"][0]["issues"][0]["code"], "review_unavailable")
        self.assertEqual(result["rows"][1]["status"], "met")
        self.assertIn("Declared source value", result["rows"][1]["reason"])

    def test_strict_boundaries_operators_and_negative_values(self):
        for operator, source_value, target_value, expected in [
            ("<=", 300, 300, "met"), ("<=", 300.000001, 300, "not_met"),
            (">=", 300, 300, "met"), (">=", 299.999999, 300, "not_met"),
            ("==", 300, 300, "met"), ("==", 300.000001, 300, "not_met"),
            ("<=", -10, -9, "met"), (">=", -10, -9, "not_met"),
        ]:
            current = project()
            current["inputs"]["declaration"]["value"] = source_value
            current["inputs"]["capacity"]["value"] = target_value
            current["interfaces"][1]["operator"] = operator
            with self.subTest(operator=operator, value=source_value):
                self.assertEqual(evaluate_interfaces(current)["rows"][1]["status"], expected)

    def test_exact_units_prevent_implicit_conversions_even_when_numbers_equal(self):
        for changed in ("source", "target", "contract"):
            current = project()
            if changed == "source":
                current["inputs"]["declaration"]["unit"] = "mN"
            elif changed == "target":
                current["inputs"]["capacity"]["unit"] = "mN"
            else:
                current["interfaces"][1]["unit"] = "mN"
            with self.subTest(changed=changed):
                row = evaluate_interfaces(current)["rows"][1]
                self.assertEqual(row["status"], "not_assessed")
                self.assertIn("unit_mismatch", [issue["code"] for issue in row["issues"]])

    def test_drafts_never_issue_numeric_verdict_or_read_historical_model_metric(self):
        current = project()
        recorded = review(current)
        current["inputs"]["force"]["value"] = 999
        current["inputs"]["capacity"]["unit"] = "mN"
        rows = evaluate_interfaces(current, recorded, draft=True)["rows"]
        self.assertTrue(all(row["status"] == "not_assessed" for row in rows))
        self.assertIsNone(rows[0]["source_value"])
        self.assertEqual(rows[1]["source_value"]["value"], 300)
        self.assertIn("unit_mismatch", [issue["code"] for issue in rows[1]["issues"]])
        with self.assertRaises(ValueError):
            evaluate_interfaces(current, draft=1)

    def test_invalid_numeric_values_are_gaps_never_comparisons(self):
        for key in ("declaration", "capacity"):
            for value in (True, math.inf, math.nan, "300", 10**1000):
                current = project()
                current["inputs"][key]["value"] = value
                with self.subTest(key=key, value=str(value)[:10]):
                    self.assertEqual(evaluate_interfaces(current)["rows"][1]["status"], "not_assessed")

    def test_stale_wrong_revision_wrong_identity_corrupt_and_historical_sources_are_gaps(self):
        current = project()
        recorded = review(current)
        variants = []
        changed = deepcopy(current)
        changed["revision"] = "2"
        variants.append((changed, recorded))
        changed = deepcopy(current)
        changed["project_id"] = "another-project"
        variants.append((changed, recorded))
        changed = deepcopy(current)
        changed["inputs"]["speed"]["value"] = 51
        variants.append((changed, recorded))
        bad = deepcopy(recorded)
        bad["evidence"]["aero"]["metrics"]["drag_force"]["value"] = 0
        variants.append((current, bad))
        variants.append((current, {"schema": "garbage"}))
        for value, evidence in variants:
            with self.subTest(project=value["project_id"], revision=value["revision"]):
                row = evaluate_interfaces(value, evidence)["rows"][0]
                self.assertEqual(row["status"], "not_assessed")
                self.assertIsNone(row["source_value"])
        from sixd.lifecycle import _verification_sources
        with patch("sixd.lifecycle._verification_sources", return_value={key: "0"*64 for key in _verification_sources()}):
            row = evaluate_interfaces(current, recorded)["rows"][0]
            self.assertEqual(row["status"], "not_assessed")
            self.assertIn("historical", row["reason"])

    def test_missing_metric_unassessed_source_and_unsupported_model_stay_gaps(self):
        current = project()
        current["interfaces"][0]["source"]["metric"] = "nonexistent_metric"
        recorded = review(current)
        self.assertEqual(evaluate_interfaces(current, recorded)["rows"][0]["issues"][0]["code"], "metric_unavailable")
        current = project()
        recorded = review_project(current, {})
        self.assertEqual(evaluate_interfaces(current, recorded)["rows"][0]["issues"][0]["code"], "model_unassessed")
        current["models"][0]["type"] = "unsupported_custom_solver"
        recorded = review(current)
        row = evaluate_interfaces(current, recorded)["rows"][0]
        self.assertEqual(row["status"], "not_assessed")
        self.assertIsNone(row["source_value"])

    def test_interface_failure_does_not_modify_passing_requirement_review(self):
        current = project()
        current["inputs"]["force"]["value"] = 301
        recorded = review(current)
        self.assertEqual(recorded["review_status"], "supported_requirements_met")
        result = evaluate_interfaces(current, recorded)
        self.assertEqual(result["rows"][0]["status"], "not_met")
        self.assertEqual(recorded["review_status"], "supported_requirements_met")
        self.assertIs(recorded["launch_authorization"], False)


class ArchitectureImpactTests(unittest.TestCase):
    def test_no_change_and_unbound_input_do_not_create_artificial_coupling(self):
        before = project()
        after = deepcopy(before)
        result = architecture_impact(before, after)
        self.assertEqual(result["affected_interface_ids"], [])
        self.assertEqual(result["interface_review_model_ids"], [])
        self.assertEqual(result["interface_review_requirement_ids"], [])
        self.assertEqual(result["reasons"], [])
        after["inputs"]["unbound"]["value"] = 22
        self.assertEqual(architecture_impact(before, after)["affected_interface_ids"], [])

    def test_changed_upstream_model_input_reaches_declared_downstream_edges(self):
        before = project()
        after = deepcopy(before)
        after["inputs"]["speed"]["value"] = 51
        result = architecture_impact(before, after)
        self.assertEqual(result["affected_interface_ids"], ["drag_to_mount", "mount_to_deployment"])
        self.assertIn("beam", result["interface_review_model_ids"])
        self.assertIn("strength", result["interface_review_requirement_ids"])
        self.assertIn("deployment", result["interface_review_system_ids"])
        self.assertIn("interface_input_changed", {row["code"] for row in result["reasons"]})
        # No input is assigned a newly predicted drag value.
        self.assertEqual(after["inputs"]["force"]["value"], 300)

    def test_ancestor_declared_source_catches_changed_descendant_model(self):
        before = project()
        before["interfaces"][0]["from_system"] = "vehicle"
        after = deepcopy(before)
        after["models"][0]["description"] = "Reviewed model definition changed."
        result = architecture_impact(before, after)
        self.assertIn("drag_to_mount", result["affected_interface_ids"])
        self.assertIn("mount_to_deployment", result["affected_interface_ids"])

    def test_receiving_parent_propagates_child_outgoing_interface(self):
        # A(flight) -> B(mount), C(child) belongs to B, C -> D(deployment).
        # A changed load must not stop at B while merely highlighting C's model.
        before = project()
        before["systems"][2]["model_ids"] = []
        before["systems"].append({"id": "child", "title": "Contained mount", "description": "",
                                  "parent_id": "mount", "model_ids": ["beam"]})
        before["interfaces"][1]["from_system"] = "child"
        after = deepcopy(before)
        after["inputs"]["speed"]["value"] = 51
        result = architecture_impact(before, after)
        self.assertEqual(result["affected_interface_ids"], ["drag_to_mount", "mount_to_deployment"])
        self.assertIn("child", result["interface_review_system_ids"])
        self.assertIn("deployment", result["interface_review_system_ids"])
        self.assertIn("beam", result["interface_review_model_ids"])
        self.assertIn("strength", result["interface_review_requirement_ids"])
        self.assertTrue(any(row["code"] == "descendant_system_review" and row["system_id"] == "child"
                            for row in result["reasons"]))
        self.assertEqual(after["inputs"]["force"]["value"], 300)

    def test_affected_child_also_propagates_parent_exposed_output(self):
        before = project()
        before["systems"][2]["model_ids"] = []
        before["systems"].append({"id": "child", "title": "Contained mount", "description": "",
                                  "parent_id": "mount", "model_ids": ["beam"]})
        after = deepcopy(before)
        # Change model metadata, not any contract input: the only route to the
        # deployment interface is the owning child's parent-exposed contract.
        after["models"][1]["description"] = "Changed contained model definition."
        result = architecture_impact(before, after)
        self.assertEqual(result["affected_interface_ids"], ["mount_to_deployment"])
        self.assertIn("deployment", result["interface_review_system_ids"])

    def test_old_new_hierarchy_union_cycle_is_finite(self):
        before = project()
        before["systems"].append({"id": "child", "title": "Contained mount", "description": "",
                                  "parent_id": "mount", "model_ids": []})
        before["interfaces"][1]["from_system"] = "child"
        after = deepcopy(before)
        # Both individual trees are acyclic; their conservative edge union has
        # mount <-> child. The propagation must still visit each ID only once.
        after["systems"][2]["parent_id"] = "child"
        after["systems"][-1]["parent_id"] = "vehicle"
        result = architecture_impact(before, after)
        self.assertIn("mount_to_deployment", result["affected_interface_ids"])
        self.assertIn("deployment", result["interface_review_system_ids"])
        self.assertLess(len(result["reasons"]), 40)
        self.assertEqual(result, architecture_impact(before, after))

    def test_removed_edge_retains_old_downstream_review_route(self):
        before = project()
        after = deepcopy(before)
        after["interfaces"] = after["interfaces"][1:]
        result = architecture_impact(before, after)
        self.assertEqual(result["removed_interfaces"], ["drag_to_mount"])
        self.assertEqual(result["affected_interface_ids"], ["drag_to_mount", "mount_to_deployment"])
        self.assertIn("strength", result["interface_review_requirement_ids"])

    def test_added_changed_removed_systems_and_contracts_are_explicit(self):
        before = project()
        after = deepcopy(before)
        after["systems"][1]["title"] = "Updated flight loads"
        after["systems"].append({"id": "new", "title": "New system", "description": "", "parent_id": None, "model_ids": []})
        after["systems"] = [row for row in after["systems"] if row["id"] != "deployment"]
        after["interfaces"][1]["to_system"] = "new"
        after["interfaces"].append(dict(deepcopy(after["interfaces"][1]), id="new-edge", to_system="flight"))
        original_before, original_after = deepcopy(before), deepcopy(after)
        result = architecture_impact(before, after)
        self.assertEqual(result["added_systems"], ["new"])
        self.assertEqual(result["removed_systems"], ["deployment"])
        self.assertEqual(result["changed_systems"], ["flight"])
        self.assertEqual(result["changed_interfaces"], ["mount_to_deployment"])
        self.assertEqual(result["added_interfaces"], ["new-edge"])
        self.assertIn("deployment", result["interface_review_system_ids"])
        self.assertIn("new", result["interface_review_system_ids"])
        self.assertEqual(before, original_before)
        self.assertEqual(after, original_after)

    def test_cycle_traversal_is_finite_and_deterministic(self):
        before = project()
        before["interfaces"][1]["to_system"] = "flight"
        after = deepcopy(before)
        after["inputs"]["speed"]["value"] = 51
        first = architecture_impact(before, after)
        self.assertEqual(first, architecture_impact(before, after))
        self.assertEqual(first["affected_interface_ids"], ["drag_to_mount", "mount_to_deployment"])
        self.assertLess(len(first["reasons"]), 30)

    def test_removed_model_ids_and_old_receiving_models_remain_reviewable(self):
        before = project()
        after = deepcopy(before)
        after["models"] = [row for row in after["models"] if row["id"] != "beam"]
        after["requirements"] = [row for row in after["requirements"] if row["model_id"] != "beam"]
        after["systems"][2]["model_ids"] = []
        result = architecture_impact(before, after)
        self.assertIn("beam", result["interface_review_model_ids"])
        self.assertIn("strength", result["interface_review_requirement_ids"])
        self.assertIn("mount_to_deployment", result["affected_interface_ids"])

    def test_current_source_change_flags_contracts_without_execution(self):
        current = project()
        with patch("sixd.engineering.evaluate_models", side_effect=AssertionError("No solver")):
            result = architecture_impact(current, current, sources_changed=True)
        self.assertEqual(result["affected_interface_ids"], ["drag_to_mount", "mount_to_deployment"])
        self.assertIn("verification_sources_changed", {row["code"] for row in result["reasons"]})


if __name__ == "__main__":
    unittest.main()
