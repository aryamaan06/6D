"""Constructed rocket-review arithmetic, coverage and retained change evidence.

These tests check the declared screening workflow. They do not establish the
physical applicability of the inputs, a complete vehicle or launch readiness.
"""
from collections import Counter
from copy import deepcopy
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import engineering, lifecycle, powered_flight, project_authoring, workspace
from sixd.project_examples import example_projects, integrated_rocket_review


class RocketReferenceExampleTests(unittest.TestCase):
    def setUp(self):
        self.project = integrated_rocket_review()

    def test_schema_organizes_five_supported_models_and_keeps_launch_gnc_gap(self):
        project = lifecycle.validate_project(self.project)
        self.assertTrue(project_authoring.preflight(project)["can_run"])
        self.assertEqual(example_projects()["rocket_review"], project)
        self.assertEqual({model["type"] for model in project["models"]}, {
            "ideal_propulsion", "powered_flight", "drag_load", "static_cantilever",
            "radiative_equilibrium", "unsupported_launch_gnc"})
        self.assertEqual(len(project["requirements"]), 10)
        owners = [identity for system in project["systems"] for identity in system["model_ids"]]
        self.assertCountEqual(owners, [model["id"] for model in project["models"]])
        self.assertEqual(len(set(owners)), len(owners))
        self.assertTrue(all(system["parent_id"] == "rocket" for system in project["systems"][1:]))
        results = engineering.evaluate_models(project)
        review = lifecycle.review_project(project, results)
        self.assertEqual(Counter(item["status"] for item in review["findings"].values()),
                         {"met": 9, "not_assessed": 1})
        self.assertEqual(results["launch_gnc"]["status"], "not_assessed")
        self.assertEqual(results["launch_gnc"]["metrics"], {})
        self.assertEqual(review["findings"]["launch_guidance"]["status"], "not_assessed")
        self.assertFalse(review["launch_authorization"])
        self.assertTrue(lifecycle.verify_review(review))

    def test_ideal_budget_and_full_flight_burn_are_distinct_analytic_quantities(self):
        results = engineering.evaluate_models(self.project)
        # NASA ideal rocket equation: mf = m0*exp(-delta_v/(Isp*g0)).
        # Evaluate directly here rather than calling the maintained calculator.
        exhaust_speed = 250 * 9.80665
        required = 1000 * (1 - math.exp(-500 / exhaust_speed))
        mass_flow = 20000 / exhaust_speed
        ideal = results["propulsion"]["metrics"]
        flight = results["vertical_flight"]["metrics"]
        self.assertAlmostEqual(ideal["propellant_required"]["value"], required, places=10)
        self.assertAlmostEqual(ideal["propellant_margin"]["value"], 300 - required, places=10)
        self.assertAlmostEqual(ideal["burn_duration"]["value"], required / mass_flow, places=10)
        self.assertAlmostEqual(flight["burn_duration"]["value"], 300 / mass_flow, places=10)
        self.assertEqual(flight["propellant_consumed"], {"value": 300., "unit": "kg"})
        self.assertLess(ideal["burn_duration"]["value"], flight["burn_duration"]["value"])
        self.assertEqual(self.project["inputs"]["maximum_burn_duration"]["unit"], "s")

    def test_explicit_speed_drag_and_transverse_beam_chain_matches_equations(self):
        results = engineering.evaluate_models(self.project)
        flight = results["vertical_flight"]
        speed = max(abs(sample["velocity_m_s"]) for sample in flight["flight_response"]["samples"])
        # NASA drag equation for the separately declared reference-density case.
        expected_pressure = 1.225 * speed**2 / 2
        expected_drag = expected_pressure * .4 * .8
        drag = results["atmospheric_load"]
        self.assertAlmostEqual(drag["metrics"]["dynamic_pressure"]["value"], expected_pressure, places=8)
        self.assertAlmostEqual(drag["metrics"]["drag_force"]["value"], expected_drag, places=8)
        # The screening condition is deliberately not actual flight maximum q.
        self.assertGreater(expected_pressure, flight["metrics"]["max_sampled_dynamic_pressure"]["value"])
        self.assertGreater(expected_drag, flight["metrics"]["max_sampled_drag"]["value"])
        self.assertEqual(drag["calculation_inputs"]["values"]["relative_speed"],
                         {"value": speed, "unit": "m/s"})
        # MIT Euler-Bernoulli equations; rectangular section about declared axis.
        section_moment = .3 * .1**3 / 12
        expected_stress = expected_drag * 2 * .05 / section_moment
        expected_deflection = expected_drag * 2**3 / (3 * 70e9 * section_moment)
        beam = results["mount"]
        self.assertAlmostEqual(self.project["inputs"]["second_moment"]["value"], section_moment, places=16)
        self.assertAlmostEqual(beam["metrics"]["bending_stress"]["value"], expected_stress, delta=1e-6)
        self.assertAlmostEqual(beam["metrics"]["tip_deflection"]["value"], expected_deflection, places=12)
        self.assertEqual(beam["calculation_inputs"]["values"]["tip_force"], drag["metrics"]["drag_force"])
        self.assertEqual(set(beam["calculation_inputs"]["ancestors"]),
                         {"vertical_flight", "atmospheric_load"})

    def test_independent_radiator_matches_stefan_boltzmann_balance(self):
        results = engineering.evaluate_models(self.project)
        # NIST sigma and the supplied steady grey-surface black-background case.
        expected = (200 / (.8 * 5.670374419e-8 * 1) + 3**4)**.25
        self.assertAlmostEqual(results["thermal"]["metrics"]["equilibrium_temperature"]["value"],
                               expected, places=10)
        thermal = next(model for model in self.project["models"] if model["id"] == "thermal")
        self.assertNotIn("links", thermal)
        self.assertNotIn("thrust", thermal["inputs"].values())

    def test_flight_numerical_gap_blocks_both_linked_calculations(self):
        for name, value in {"steps": 8, "altitude_numerical_tolerance": 1e-12,
                            "velocity_numerical_tolerance": 1e-12,
                            "relative_numerical_tolerance": 0}.items():
            self.project["inputs"][name]["value"] = value
        results = engineering.evaluate_models(self.project)
        self.assertEqual(results["vertical_flight"]["status"], "completed")
        self.assertFalse(results["vertical_flight"]["flight_response"]["diagnostics"]["grid_agreement_met"])
        self.assertEqual(results["atmospheric_load"]["calculation_inputs"]["links"]["relative_speed"]["status"],
                         "insufficient_accuracy")
        for identity in ("atmospheric_load", "mount", "launch_gnc"):
            self.assertEqual(results[identity]["status"], "not_assessed")
            self.assertEqual(results[identity]["metrics"], {})
        self.assertEqual(results["thermal"]["status"], "completed")
        review = lifecycle.review_project(self.project, results)
        self.assertEqual(Counter(item["status"] for item in review["findings"].values()),
                         {"met": 3, "not_assessed": 7})
        self.assertTrue(lifecycle.verify_review(review))

    def test_stored_baseline_flawed_and_corrected_revision_reuse_and_receipts(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
            store = workspace.WorkspaceStore(Path(directory) / "workspace.sqlite3")
            identity = self.project["project_id"]
            store.create_project(self.project)
            baseline = store.run(identity, 1)
            self.assertEqual(Counter(item["status"] for item in baseline["run"]["review"]["findings"].values()),
                             {"met": 9, "not_assessed": 1})
            previous = baseline
            for revision, thrust, expected in (
                (2, 11000, {"met": 8, "not_met": 1, "not_assessed": 1}),
                (3, 20000, {"met": 9, "not_assessed": 1}),
            ):
                with self.subTest(revision=revision):
                    project = deepcopy(previous["project"])
                    project["inputs"]["thrust"]["value"] = thrust
                    with patch.object(powered_flight, "evaluate", side_effect=AssertionError("Preview must not calculate")):
                        impact = store.preview_change(identity, revision - 1, project)
                    affected = {"propulsion", "vertical_flight", "atmospheric_load", "mount"}
                    self.assertEqual(set(impact["affected_model_ids"]), affected)
                    store.save_revision(identity, revision - 1, project)
                    with patch.object(workspace, "evaluate_model", wraps=engineering.evaluate_model) as linked, \
                         patch.object(workspace, "evaluate_models", wraps=engineering.evaluate_models) as direct:
                        current = store.run(identity, revision)
                    self.assertEqual(linked.call_count + direct.call_count, 4)
                    calculated = {call.args[1]["id"] for call in linked.call_args_list}
                    calculated.update(model["id"] for call in direct.call_args_list for model in call.args[0]["models"])
                    self.assertEqual(calculated, affected)
                    run = current["run"]
                    self.assertEqual(set(run["executed_model_ids"]), affected)
                    self.assertEqual(set(run["reused_model_ids"]), {"thermal", "launch_gnc"})
                    self.assertEqual(run["model_origins"]["thermal"]["run_id"], baseline["run"]["run_id"])
                    self.assertEqual(run["model_results"]["thermal"], baseline["run"]["model_results"]["thermal"])
                    self.assertEqual(run["model_results"]["launch_gnc"]["metrics"], {})
                    self.assertEqual(run["review"]["findings"]["launch_guidance"]["status"], "not_assessed")
                    self.assertEqual(Counter(item["status"] for item in run["review"]["findings"].values()), expected)
                    full_review = lifecycle.review_project(current["project"], engineering.evaluate_models(current["project"]))
                    self.assertEqual(run["review"], full_review)
                    self.assertEqual(run["live_model_calls"], 0)
                    self.assertTrue(lifecycle.verify_review(run["review"]))
                    self.assertEqual(store.get(identity, revision - 1)["run"], previous["run"])
                    if revision == 2:
                        self.assertEqual(run["review"]["findings"]["burnout_height"]["status"], "not_met")
                        self.assertLess(run["model_results"]["vertical_flight"]["metrics"]["burnout_altitude"]["value"], 5000)
                        self.assertGreater(run["model_results"]["vertical_flight"]["metrics"]["final_altitude"]["value"], 5000)
                        self.assertLess(run["model_results"]["mount"]["metrics"]["bending_stress"]["value"],
                                        baseline["run"]["model_results"]["mount"]["metrics"]["bending_stress"]["value"])
                    previous = current
            self.assertEqual(previous["run"]["model_results"]["vertical_flight"]["metrics"],
                             baseline["run"]["model_results"]["vertical_flight"]["metrics"])
            with patch.object(powered_flight, "evaluate", side_effect=AssertionError("History must not calculate")):
                self.assertEqual(store.get(identity, 1)["run"], baseline["run"])
                self.assertEqual(store.get(identity, 3)["run"], previous["run"])


if __name__ == "__main__":
    unittest.main()
