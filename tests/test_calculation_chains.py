"""Independent scalar chains, retained provenance and transitive reuse."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import chains, engineering, lifecycle, project_authoring, workspace
from sixd.project_examples import example_projects


def fixture():
    inputs = {}
    def add(name, value, unit):
        inputs[name] = {"value": value, "unit": unit, "source": "Constructed analytical example, not flight data."}
        return name
    aero = {"id": "aero", "type": "drag_load", "inputs": {
        "density": add("rho", .4, "kg/m^3"), "relative_speed": add("speed", 10, "m/s"),
        "drag_coefficient": add("cd", .5, "1"), "reference_area": add("area", 2, "m^2")}}
    beam = {"id": "beam", "type": "static_cantilever", "inputs": {
        "length": add("length", 2, "m"), "young_modulus": add("E", 2e11, "Pa"),
        "second_moment": add("I", 1e-6, "m^4"), "outer_fiber": add("c", .01, "m")},
        "links": {"tip_force": {"model_id": "aero", "metric": "drag_force", "unit": "N",
            "rationale": "Declared rigid load transfer maps the supplied drag magnitude to this transverse cantilever tip load; applicability requires separate validation."}}}
    thermal = {"id": "thermal", "type": "radiative_equilibrium", "inputs": {
        "heat_input": add("heat", 10, "W"), "area": add("radiator", 1, "m^2"),
        "emissivity": add("epsilon", .8, "1"), "background_temperature": add("background", 3, "K")}}
    requirements = []
    for identity, model, metric, threshold, unit in (
        ("drag_limit", "aero", "drag_force", 10, "N"),
        ("stress_limit", "beam", "bending_stress", 1e6, "Pa"),
        ("deflection_limit", "beam", "tip_deflection", .001, "m"),
        ("thermal_limit", "thermal", "equilibrium_temperature", 500, "K")):
        requirements.append({"id": identity, "title": identity, "model_id": model, "metric": metric,
            "operator": "<=", "limit_input": add(identity, threshold, unit), "critical": True})
    return {"schema": lifecycle.PROJECT_SCHEMA, "project_id": "chain-test", "revision": "1", "name": "Constructed chain",
        "description": "An analytical load assignment and independent thermal branch.", "lifecycle_stage": "design",
        "inputs": inputs, "models": [beam, thermal, aero], "requirements": requirements}


class CalculationChainTests(unittest.TestCase):
    def setUp(self):
        self.project = fixture()

    def test_reverse_order_chain_matches_analytical_force_stress_deflection(self):
        original = deepcopy(self.project)
        result = engineering.evaluate_models(self.project)
        self.assertEqual(list(result), ["thermal", "aero", "beam"])
        self.assertEqual(result["aero"]["metrics"]["drag_force"], {"value": 20., "unit": "N"})
        self.assertAlmostEqual(result["beam"]["metrics"]["bending_stress"]["value"], 400000.)
        self.assertAlmostEqual(result["beam"]["metrics"]["tip_deflection"]["value"], 1 / 3750)
        review = lifecycle.review_project(self.project, result)
        self.assertEqual(review["findings"]["drag_limit"]["status"], "not_met")
        self.assertEqual(review["findings"]["stress_limit"]["status"], "met")
        self.assertEqual(self.project, original)
        self.assertTrue(lifecycle.verify_review(review))
        self.assertTrue(project_authoring.preflight(self.project)["can_run"])

    def test_multihop_saves_all_ancestors_and_independent_deepcopy(self):
        beam2 = deepcopy(self.project["models"][0]); beam2["id"] = "beam2"
        del beam2["inputs"]["length"]
        beam2["links"]["length"] = {"model_id": "beam", "metric": "tip_deflection", "unit": "m",
            "rationale": "Constructed transfer fixture uses the first deflection as a second beam length; not a validated physical design."}
        self.project["models"].insert(0, beam2)
        results = engineering.evaluate_models(self.project)
        provenance = results["beam2"]["calculation_inputs"]
        self.assertEqual(set(provenance["ancestors"]), {"aero", "beam"})
        self.assertEqual(provenance["values"]["length"]["value"], 1 / 3750)
        self.assertAlmostEqual(results["beam2"]["metrics"]["bending_stress"]["value"], 20 * (1 / 3750) * .01 / 1e-6)
        self.assertEqual(provenance["ancestors"]["beam"]["result_digest"], chains.digest(results["beam"]))
        review = lifecycle.review_project(self.project, results)
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("History must not solve")), patch.dict(engineering._CALCULATORS, {key: lambda _: (_ for _ in ()).throw(AssertionError("History must not solve")) for key in engineering._CALCULATORS}):
            self.assertTrue(lifecycle.verify_review(review))

    def test_invalid_upstream_propagates_gap_and_never_uses_old_or_zero_value(self):
        self.project["inputs"]["rho"]["value"] = -1
        result = engineering.evaluate_models(self.project)
        self.assertEqual(result["aero"]["status"], "invalid_inputs")
        self.assertEqual(result["beam"]["status"], "not_assessed")
        self.assertEqual(result["beam"]["metrics"], {})
        self.assertNotIn("tip_force", result["beam"]["calculation_inputs"]["values"])
        self.assertEqual(result["beam"]["calculation_inputs"]["links"]["tip_force"]["status"], "invalid_inputs")
        self.assertEqual(result["thermal"]["status"], "completed")
        review = lifecycle.review_project(self.project, result)
        self.assertEqual(review["findings"]["stress_limit"]["status"], "not_assessed")
        result["beam"]["status"] = "completed"
        with self.assertRaises(ValueError):
            lifecycle.review_project(self.project, result)

    def test_structural_contract_errors_rejected_before_execution(self):
        mutations = {
            "dangling": lambda p: p["models"][0]["links"]["tip_force"].update(model_id="missing"),
            "metric": lambda p: p["models"][0]["links"]["tip_force"].update(metric="unknown"),
            "unit": lambda p: p["models"][0]["links"]["tip_force"].update(unit="kN"),
            "rationale": lambda p: p["models"][0]["links"]["tip_force"].update(rationale=" "),
            "both": lambda p: p["models"][0]["inputs"].update(tip_force="drag_limit"),
            "role": lambda p: p["models"][0]["links"].update(unknown=p["models"][0]["links"].pop("tip_force")),
            "unsupported_source": lambda p: p["models"][2].update(type="unavailable_model"),
            "extra_field": lambda p: p["models"][0]["links"]["tip_force"].update(scale=1),
            "bad_container": lambda p: p["models"][0].update(links=[]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                p = deepcopy(self.project); mutate(p)
                with self.assertRaises(ValueError): lifecycle.validate_project(p)
                self.assertFalse(project_authoring.preflight(p)["can_run"])

    def test_cycle_and_resource_bounds(self):
        p = deepcopy(self.project)
        p["models"][0]["inputs"].pop("young_modulus")
        p["models"][0]["links"]["young_modulus"] = {"model_id": "beam", "metric": "bending_stress", "unit": "Pa", "rationale": "Cycle fixture"}
        with self.assertRaisesRegex(ValueError, "cycle"):
            lifecycle.validate_project(p)
        p = deepcopy(self.project)
        for i in range(126):
            item = deepcopy(p["models"][1]); item["id"] = f"extra{i}"; p["models"].append(item)
        with self.assertRaisesRegex(ValueError, "at most 128"):
            lifecycle.validate_project(p)

    def test_deep_chain_limit_is_iterative_and_rejects_excess_depth(self):
        p = deepcopy(self.project)
        base = deepcopy(p["models"][0]); last = "beam"
        for index in range(63):
            model = deepcopy(base); model["id"] = f"deep{index}"
            model["inputs"].pop("length")
            model["links"]["length"] = {"model_id": last, "metric": "tip_deflection", "unit": "m", "rationale": "Constructed chain depth test"}
            p["models"].insert(0, model); last = model["id"]
        with self.assertRaisesRegex(ValueError, "depth exceeds 64"):
            lifecycle.validate_project(p)

    def test_fanout_and_downstream_domain_failure_stay_independent(self):
        p = deepcopy(self.project)
        branch = deepcopy(p["models"][0]); branch["id"] = "second_beam"
        branch["inputs"]["second_moment"] = "invalid_section"
        p["inputs"]["invalid_section"] = {"value": 0, "unit": "m^4", "source": "Constructed invalid section"}
        p["models"].insert(0, branch)
        result = engineering.evaluate_models(p)
        self.assertEqual(result["aero"]["status"], "completed")
        self.assertEqual(result["beam"]["status"], "completed")
        self.assertEqual(result["second_beam"]["status"], "invalid_inputs")
        self.assertEqual(result["second_beam"]["metrics"], {})
        self.assertEqual(result["second_beam"]["calculation_inputs"]["values"]["tip_force"]["value"], 20.)
        self.assertTrue(lifecycle.verify_review(lifecycle.review_project(p, result)))

    def test_linked_attitude_artifact_verifies_without_reintegrating(self):
        p = example_projects()["attitude_review"]
        source = next(item for item in p["models"] if item["type"] == "attitude_control")
        target = deepcopy(source); target["id"] = "second_axis"
        target["inputs"].pop("initial_angle")
        target["links"] = {"initial_angle": {"model_id": source["id"], "metric": "final_error", "unit": "rad",
            "rationale": "Constructed second independent calculation starts from the first calculation's final error magnitude; no continuous coupled dynamics are implied."}}
        p["models"].insert(0, target)
        results = engineering.evaluate_models(p)
        self.assertEqual(results["second_axis"]["status"], "completed")
        review = lifecycle.review_project(p, results)
        with patch.object(engineering.attitude, "evaluate", side_effect=AssertionError("History must not integrate")):
            self.assertTrue(lifecycle.verify_review(review))

    def test_linked_orbital_artifact_verifies_without_reintegrating(self):
        p = example_projects()["orbital_review"]
        source = next(item for item in p["models"] if item["type"] == "orbital_trajectory")
        target = deepcopy(source); target["id"] = "second_orbit"
        target["inputs"].pop("position_x")
        target["links"] = {"position_x": {"model_id": source["id"], "metric": "final_radius_m", "unit": "m",
            "rationale": "Constructed new independent initial x position takes the first radius magnitude; this is not propagation continuity or a frame conversion."}}
        p["models"].insert(0, target)
        results = engineering.evaluate_models(p)
        self.assertEqual(results["second_orbit"]["status"], "completed")
        review = lifecycle.review_project(p, results)
        with patch.object(engineering.orbital_adapter, "evaluate", side_effect=AssertionError("History must not integrate")):
            self.assertTrue(lifecycle.verify_review(review))

    def test_source_and_transitive_provenance_tamper_rejected_after_rehash(self):
        good = engineering.evaluate_models(self.project)
        mutations = (
            lambda r: r["beam"]["calculation_inputs"]["values"]["tip_force"].update(value=30),
            lambda r: r["beam"]["calculation_inputs"]["links"]["tip_force"].update(source_result_digest="0"*64),
            lambda r: r["beam"]["calculation_inputs"]["ancestors"]["aero"]["input_records"]["rho"].update(source="changed"),
            lambda r: r["beam"]["calculation_inputs"].update(dependency_fingerprint="f"*64),
            lambda r: r["beam"].pop("calculation_inputs"),
        )
        for mutate in mutations:
            r = deepcopy(good); mutate(r)
            with self.assertRaises(ValueError): lifecycle.review_project(self.project, r)
        review = lifecycle.review_project(self.project, good)
        review["evidence"]["beam"]["calculation_inputs"]["links"]["tip_force"]["rationale"] = "Altered rationale"
        body = {key: value for key, value in review.items() if key != "digest"}
        review["digest"] = lifecycle._digest(body)
        with self.assertRaises(ValueError): lifecycle.verify_review(review)

    def test_absent_or_wrong_metric_source_is_explicitly_unavailable(self):
        model = self.project["models"][0]
        for sources in ({}, {"aero": {"status": "completed", "metrics": {}}}):
            result = engineering.evaluate_model(self.project, model, sources)
            self.assertEqual(result["status"], "not_assessed")
            self.assertEqual(result["metrics"], {})

    def test_dynamic_power_role_can_supply_thermal_input(self):
        power = deepcopy(example_projects()["power_budget"])
        pmodel = next(item for item in power["models"] if item["type"] == "power_energy_budget")
        thermal = next(item for item in power["models"] if item["type"] == "radiative_equilibrium")
        thermal["inputs"].pop("heat_input")
        thermal["links"] = {"heat_input": {"model_id": pmodel["id"], "metric": "peak_load_power", "unit": "W", "rationale": "Declared example assumes this electrical load is rejected entirely as steady heat at the radiator."}}
        result = engineering.evaluate_models(power)
        self.assertEqual(result[thermal["id"]]["status"], "completed")
        self.assertTrue(lifecycle.verify_review(lifecycle.review_project(power, result)))
        # A dynamic duration role consumes a compatible independently calculated burn duration.
        prop = deepcopy(example_projects()["baseline"])
        propulsion = next(item for item in prop["models"] if item["type"] == "ideal_propulsion")
        power["inputs"].update(prop["inputs"])
        power["models"].append(propulsion)
        duration = next(role for role in pmodel["inputs"] if role.endswith(".duration"))
        pmodel["inputs"].pop(duration)
        pmodel["links"] = {duration: {"model_id": propulsion["id"], "metric": "burn_duration", "unit": "s", "rationale": "This constructed operating mode lasts the independently calculated ideal burn duration."}}
        self.assertTrue(project_authoring.preflight(power)["can_run"])
        result = engineering.evaluate_models(power)
        self.assertEqual(result[pmodel["id"]]["status"], "completed")
        self.assertTrue(lifecycle.verify_review(lifecycle.review_project(power, result)))

    def test_legacy_six_source_reviews_preserve_exact_bytes(self):
        p = example_projects()["attitude_review"]
        sources = {name: value for name, value in lifecycle._verification_sources().items() if name != "chains.py"}
        with patch.object(lifecycle, "_verification_sources", return_value=sources):
            review = lifecycle.review_project(p, engineering.evaluate_models(p))
        saved = json.dumps(review, sort_keys=True)
        self.assertTrue(lifecycle.verify_review(review))
        self.assertEqual(json.dumps(review, sort_keys=True), saved)
        self.assertNotIn("calculation_inputs", review["evidence"]["pointing"])
        with patch.object(lifecycle, "_verification_sources", return_value=sources), self.assertRaises(ValueError):
            lifecycle.review_project(self.project, engineering.evaluate_models(self.project))


class ChainWorkspaceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=ROOT / "work"); self.addCleanup(tmp.cleanup)
        self.store = workspace.WorkspaceStore(Path(tmp.name) / "workspace.sqlite3")
        self.project = fixture(); self.identity = self.project["project_id"]
        self.store.create_project(self.project)
        self.first = self.store.run(self.identity, 1)

    def change(self, mutations):
        p = deepcopy(self.first["project"])
        for key, value in mutations.items(): p["inputs"][key]["value"] = value
        impact = self.store.preview_change(self.identity, 1, p)
        self.store.save_revision(self.identity, 1, p)
        return self.store.run(self.identity, 2), impact

    def test_upstream_change_reruns_downstream_and_preserves_independent_origin(self):
        updated, impact = self.change({"speed": 20})
        self.assertEqual(impact["affected_model_ids"], ["aero", "beam"])
        self.assertEqual(updated["run"]["executed_model_ids"], ["aero", "beam"])
        self.assertEqual(updated["run"]["reused_model_ids"], ["thermal"])
        self.assertEqual(updated["run"]["model_origins"]["thermal"]["run_id"], self.first["run"]["run_id"])
        self.assertEqual(updated["run"]["review"]["findings"]["stress_limit"]["status"], "not_met")
        self.assertEqual(self.store.get(self.identity, 1)["run"], self.first["run"])

    def test_same_numeric_source_output_changed_configuration_invalidates_downstream(self):
        updated, _ = self.change({"rho": .1, "speed": 20})
        before = self.first["run"]; after = updated["run"]
        self.assertEqual(before["model_results"]["aero"]["metrics"], after["model_results"]["aero"]["metrics"])
        self.assertEqual(after["executed_model_ids"], ["aero", "beam"])
        self.assertNotEqual(before["review"]["findings"]["stress_limit"]["dependency_fingerprint"], after["review"]["findings"]["stress_limit"]["dependency_fingerprint"])
        self.assertIn("stress_limit", updated["comparison"]["previous_evidence_needs_rechecking"])

    def test_source_record_only_change_rechecks_and_history_reads_never_execute(self):
        p = deepcopy(self.first["project"]); p["inputs"]["rho"]["source"] = "Replaced atmospheric dataset"
        self.store.save_revision(self.identity, 1, p)
        updated = self.store.run(self.identity, 2)
        self.assertEqual(updated["run"]["executed_model_ids"], ["aero", "beam"])
        with patch.object(engineering, "evaluate_model", side_effect=AssertionError("History must not calculate")), patch.object(workspace, "evaluate_model", side_effect=AssertionError("History must not calculate")):
            self.assertEqual(self.store.get(self.identity), updated)

    def test_requirement_limit_only_reuses_entire_chain(self):
        updated, impact = self.change({"stress_limit": 1})
        self.assertEqual(impact["affected_model_ids"], [])
        self.assertEqual(updated["run"]["executed_model_ids"], [])
        self.assertEqual(updated["run"]["model_results"], self.first["run"]["model_results"])
        self.assertEqual(updated["run"]["review"]["findings"]["stress_limit"]["status"], "not_met")

    def test_unavailable_revision_never_reuses_previously_passed_downstream(self):
        updated, _ = self.change({"rho": -1})
        self.assertEqual(updated["run"]["model_results"]["beam"]["metrics"], {})
        self.assertEqual(updated["run"]["review"]["findings"]["stress_limit"]["status"], "not_assessed")
        self.assertEqual(updated["run"]["executed_model_ids"], ["aero", "beam"])


if __name__ == "__main__":
    unittest.main()
