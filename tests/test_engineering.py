import copy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.engineering import MODEL_PARAMETERS, MODEL_VERSIONS, evaluate_models


def project_for(model_type, values):
    """Explicit constructed inputs; these are not actual spacecraft data."""
    return {
        "inputs": {name: {"value": value, "unit": MODEL_PARAMETERS[model_type][name],
                          "source": "Constructed independent reference case"}
                   for name, value in values.items()},
        "models": [{"id": "candidate", "type": model_type,
                    "inputs": {name: name for name in values}}],
    }


PROPULSION = {"initial_mass": 1000, "dry_mass": 400,
              "delta_v": 9.80665 * 100 * math.log(2), "specific_impulse": 100,
              "thrust": 980.665}
BEAM = {"tip_force": 100, "length": 2, "young_modulus": 200e9,
        "second_moment": 1e-6, "outer_fiber": 0.01}
THERMAL = {"heat_input": 459.300327939, "area": 2, "emissivity": 0.5,
           "background_temperature": 0}
DRAG = {"density": 1.2, "relative_speed": 10, "drag_coefficient": 0.5,
        "reference_area": 2}


class EngineeringTests(unittest.TestCase):
    def result(self, model_type, values):
        result = evaluate_models(project_for(model_type, values))["candidate"]
        self.assertEqual(result["status"], "completed", result["issues"])
        return result

    def test_propulsion_half_mass_hand_worked_reference(self):
        # A velocity increment ve*ln(2) halves mass; with 1 kg/s flow the
        # 500 kg theoretical burn lasts 500 seconds and leaves 100 kg reserve.
        metrics = self.result("ideal_propulsion", PROPULSION)["metrics"]
        for name, expected in {"propellant_required": 500, "propellant_available": 600,
                               "propellant_margin": 100, "mass_flow": 1,
                               "burn_duration": 500}.items():
            self.assertAlmostEqual(metrics[name]["value"], expected, places=10)

    def test_propulsion_insufficient_fuel_is_a_valid_negative_margin(self):
        values = dict(PROPULSION, dry_mass=700)
        result = self.result("ideal_propulsion", values)
        self.assertAlmostEqual(result["metrics"]["propellant_margin"]["value"], -200)
        self.assertEqual(result["issues"], [])

    def test_propulsion_large_mass_long_burn_does_not_report_false_zero_margin(self):
        values = dict(PROPULSION, initial_mass=1e20, dry_mass=1,
                      specific_impulse=300, delta_v=100 * 9.80665 * 300)
        metrics = self.result("ideal_propulsion", values)["metrics"]
        # The ideal final mass is 1e20/e^100, approximately 3.72e-24 kg.
        # Subtracting rounded propellant numbers loses the 1 kg dry mass.
        self.assertEqual(metrics["propellant_required"]["value"], 1e20)
        self.assertEqual(metrics["propellant_available"]["value"], 1e20)
        self.assertAlmostEqual(metrics["propellant_margin"]["value"], -1)
        self.assertFalse(metrics["propellant_margin"]["value"] >= 0)

    def test_propulsion_large_mass_preserves_a_positive_small_reserve(self):
        values = dict(PROPULSION, initial_mass=1e20, dry_mass=1,
                      specific_impulse=300, delta_v=40 * 9.80665 * 300)
        metrics = self.result("ideal_propulsion", values)["metrics"]
        # Independent high-precision reference: exp(-40)=4.248354255291589e-18.
        self.assertAlmostEqual(metrics["propellant_margin"]["value"], 423.8354255291589, places=9)

    def test_propulsion_tiny_burn_without_propellant_has_negative_margin(self):
        values = dict(PROPULSION, initial_mass=1000, dry_mass=1000,
                      specific_impulse=300, delta_v=1e-14)
        metrics = self.result("ideal_propulsion", values)["metrics"]
        # Even below the initial mass's floating-point spacing, a positive
        # required burn cannot pass a nonnegative fuel-margin requirement.
        self.assertLess(metrics["propellant_margin"]["value"], 0)
        self.assertEqual(metrics["propellant_margin"]["value"], -metrics["propellant_required"]["value"])

    def test_propulsion_large_initial_mass_prevents_premature_exponential_underflow(self):
        values = dict(PROPULSION, initial_mass=1e308, dry_mass=1e-100,
                      specific_impulse=300, delta_v=800 * 9.80665 * 300,
                      thrust=1e308)
        metrics = self.result("ideal_propulsion", values)["metrics"]
        # exp(-800) alone underflows, but multiplying by 1e308 mathematically
        # leaves representable mass. Check the independently rearranged log.
        self.assertGreater(metrics["propellant_margin"]["value"], 0)
        self.assertAlmostEqual(math.log10(metrics["propellant_margin"]["value"]),
                               308 - 800 / math.log(10), places=10)

    def test_propulsion_unrepresentable_final_mass_abstains(self):
        values = dict(PROPULSION, specific_impulse=300,
                      delta_v=1000 * 9.80665 * 300)
        result = evaluate_models(project_for("ideal_propulsion", values))["candidate"]
        self.assertEqual(result["status"], "invalid_inputs")
        self.assertEqual(result["metrics"], {})
        self.assertTrue(any("Remaining final mass" in issue for issue in result["issues"]))

    def test_propulsion_zero_and_tiny_burns(self):
        zero = self.result("ideal_propulsion", dict(PROPULSION, delta_v=0))["metrics"]
        self.assertEqual(zero["propellant_required"]["value"], 0)
        self.assertEqual(zero["burn_duration"]["value"], 0)
        tiny = self.result("ideal_propulsion", dict(PROPULSION, delta_v=1e-12))["metrics"]
        # Independently use first-order mass loss dm/m = dv/ve for a tiny burn.
        self.assertAlmostEqual(tiny["propellant_required"]["value"] / (1e-12 / 0.980665), 1, places=12)

    def test_propulsion_thrust_changes_time_but_not_required_propellant(self):
        original = self.result("ideal_propulsion", PROPULSION)["metrics"]
        doubled = self.result("ideal_propulsion", dict(PROPULSION, thrust=1961.33))["metrics"]
        self.assertEqual(doubled["propellant_required"], original["propellant_required"])
        self.assertAlmostEqual(doubled["burn_duration"]["value"], 250)

    def test_cantilever_hand_worked_stress_and_tip_deflection(self):
        # Clamp moment 200 Nm, section modulus I/c=0.0001 m^3 => 2 MPa.
        # Flexural rigidity 200000 Nm^2; integrated curvature gives 1/750 m.
        metrics = self.result("static_cantilever", BEAM)["metrics"]
        self.assertAlmostEqual(metrics["bending_stress"]["value"], 2e6)
        self.assertAlmostEqual(metrics["tip_deflection"]["value"], 1 / 750)

    def test_cantilever_length_and_modulus_scaling(self):
        original = self.result("static_cantilever", BEAM)["metrics"]
        longer = self.result("static_cantilever", dict(BEAM, length=4))["metrics"]
        stiffer = self.result("static_cantilever", dict(BEAM, young_modulus=400e9))["metrics"]
        self.assertAlmostEqual(longer["bending_stress"]["value"] / original["bending_stress"]["value"], 2)
        self.assertAlmostEqual(longer["tip_deflection"]["value"] / original["tip_deflection"]["value"], 8)
        self.assertEqual(stiffer["bending_stress"], original["bending_stress"])
        self.assertAlmostEqual(stiffer["tip_deflection"]["value"] / original["tip_deflection"]["value"], 0.5)

    def test_thermal_known_radiant_exitance_and_scaling(self):
        # Rounded NIST sigma gives 459.300327939 W/m^2 blackbody exitance
        # at 300 K. epsilon*area=1 m^2, so the required heat input is 459.3 W.
        result = self.result("radiative_equilibrium", THERMAL)
        self.assertAlmostEqual(result["metrics"]["equilibrium_temperature"]["value"], 300, places=9)
        hotter = self.result("radiative_equilibrium", dict(THERMAL, heat_input=16 * THERMAL["heat_input"]))
        self.assertAlmostEqual(hotter["metrics"]["equilibrium_temperature"]["value"], 600, places=9)
        self.assertTrue(any("Transient" in item for item in result["not_assessed"]))
        self.assertTrue(any("Aerothermodynamic" in item for item in result["not_assessed"]))

    def test_thermal_background_and_zero_heat(self):
        at_background = self.result("radiative_equilibrium", dict(THERMAL, heat_input=0, background_temperature=300))
        self.assertEqual(at_background["metrics"]["equilibrium_temperature"]["value"], 300)
        combined = self.result("radiative_equilibrium", dict(THERMAL, background_temperature=300))
        self.assertAlmostEqual(combined["metrics"]["equilibrium_temperature"]["value"] / 300, 2 ** 0.25)

    def test_thermal_finite_answer_does_not_overflow_background_fourth_power(self):
        result = self.result("radiative_equilibrium", dict(THERMAL, background_temperature=1e100))
        self.assertEqual(result["metrics"]["equilibrium_temperature"]["value"], 1e100)

    def test_thermal_extreme_power_ratio_remains_finite_when_fourth_root_is_finite(self):
        values = dict(THERMAL, heat_input=1e308, emissivity=1e-308, area=1e-308)
        result = self.result("radiative_equilibrium", values)
        temperature = result["metrics"]["equilibrium_temperature"]["value"]
        # Independently check the energy balance in log space; Q/(eps*A*sigma)
        # itself exceeds float range, but its fourth root is representable.
        self.assertAlmostEqual(4 * math.log10(temperature), 924 - math.log10(5.670374419e-8), places=10)
        json.dumps(result, allow_nan=False)

    def test_drag_hand_worked_and_speed_squared_scaling(self):
        # 0.5*1.2*10^2 = 60 Pa; Cd*A=1 m^2 => 60 N.
        result = self.result("drag_load", DRAG)
        self.assertEqual(result["metrics"]["dynamic_pressure"], {"value": 60.0, "unit": "Pa"})
        self.assertEqual(result["metrics"]["drag_force"], {"value": 60.0, "unit": "N"})
        fast = self.result("drag_load", dict(DRAG, relative_speed=20))
        self.assertEqual(fast["metrics"]["drag_force"]["value"], 240)
        self.assertTrue(any("not independently verified" in note for note in result["not_assessed"]))

    def test_drag_coefficient_area_convention_equivalence(self):
        original = self.result("drag_load", DRAG)["metrics"]
        equivalent = self.result("drag_load", dict(DRAG, drag_coefficient=0.25, reference_area=4))["metrics"]
        self.assertEqual(original, equivalent)

    def test_zero_loads_have_zero_outputs_without_inventing_applicability(self):
        beam = self.result("static_cantilever", dict(BEAM, tip_force=0))
        self.assertTrue(all(item["value"] == 0 for item in beam["metrics"].values()))
        drag = self.result("drag_load", dict(DRAG, density=0))
        self.assertTrue(all(item["value"] == 0 for item in drag["metrics"].values()))
        self.assertTrue(drag["not_assessed"])

    def test_physical_input_ranges_are_checked(self):
        cases = [("ideal_propulsion", PROPULSION, "dry_mass", 1001),
                 ("ideal_propulsion", PROPULSION, "delta_v", -1),
                 ("ideal_propulsion", PROPULSION, "thrust", 0),
                 ("static_cantilever", BEAM, "tip_force", -1),
                 ("static_cantilever", BEAM, "second_moment", 0),
                 ("radiative_equilibrium", THERMAL, "emissivity", 1.1),
                 ("radiative_equilibrium", THERMAL, "heat_input", -1),
                 ("radiative_equilibrium", THERMAL, "background_temperature", -1),
                 ("drag_load", DRAG, "density", -1),
                 ("drag_load", DRAG, "relative_speed", -1),
                 ("drag_load", DRAG, "reference_area", 0)]
        for kind, values, parameter, invalid in cases:
            with self.subTest(kind=kind, parameter=parameter):
                result = evaluate_models(project_for(kind, dict(values, **{parameter: invalid})))["candidate"]
                self.assertEqual(result["status"], "invalid_inputs")
                self.assertEqual(result["metrics"], {})
                self.assertTrue(result["issues"])

    def test_wrong_units_missing_extra_and_unknown_bindings_abstain(self):
        project = project_for("drag_load", DRAG)
        variants = []
        wrong_unit = copy.deepcopy(project); wrong_unit["inputs"]["relative_speed"]["unit"] = "km/s"; variants.append(wrong_unit)
        missing = copy.deepcopy(project); del missing["models"][0]["inputs"]["density"]; variants.append(missing)
        extra = copy.deepcopy(project); extra["models"][0]["inputs"]["lift_coefficient"] = "drag_coefficient"; variants.append(extra)
        unknown = copy.deepcopy(project); unknown["models"][0]["inputs"]["density"] = "missing"; variants.append(unknown)
        no_source = copy.deepcopy(project); no_source["inputs"]["density"]["source"] = " "; variants.append(no_source)
        for candidate in variants:
            with self.subTest(candidate=candidate):
                result = evaluate_models(candidate)["candidate"]
                self.assertEqual(result["status"], "invalid_inputs")
                self.assertEqual(result["metrics"], {})

    def test_boolean_nonfinite_and_non_numeric_values_are_rejected(self):
        for value in (True, False, math.nan, math.inf, -math.inf, "1.2", None, 10 ** 1000):
            with self.subTest(value=str(value)[:20]):
                result = evaluate_models(project_for("drag_load", dict(DRAG, density=value)))["candidate"]
                self.assertEqual(result["status"], "invalid_inputs")
                json.dumps(result, allow_nan=False)

    def test_numerical_overflow_and_underflow_abstain_without_partial_metrics(self):
        cases = [("drag_load", dict(DRAG, relative_speed=1e308)),
                 ("static_cantilever", dict(BEAM, length=1e308)),
                 ("ideal_propulsion", dict(PROPULSION, specific_impulse=1e308)),
                 ("drag_load", dict(DRAG, density=1e-320, relative_speed=1e-320))]
        for kind, values in cases:
            with self.subTest(kind=kind):
                result = evaluate_models(project_for(kind, values))["candidate"]
                self.assertEqual(result["status"], "invalid_inputs")
                self.assertEqual(result["metrics"], {})
                json.dumps(result, allow_nan=False)

    def test_unsupported_model_is_visible_and_has_no_metrics_or_version(self):
        project = {"inputs": {}, "models": [{"id": "gnc", "type": "full_gnc", "inputs": {}}]}
        result = evaluate_models(project)["gnc"]
        self.assertEqual(result["status"], "not_assessed")
        self.assertIsNone(result["model_version"])
        self.assertEqual(result["metrics"], {})
        self.assertTrue(result["not_assessed"])

    def test_invalid_model_does_not_suppress_valid_models_or_mutate_input(self):
        project = project_for("drag_load", DRAG)
        project["models"].append({"id": "invalid", "type": "static_cantilever", "inputs": {}})
        before = copy.deepcopy(project)
        results = evaluate_models(project)
        self.assertEqual(project, before)
        self.assertEqual(results["candidate"]["status"], "completed")
        self.assertEqual(results["invalid"]["status"], "invalid_inputs")
        self.assertEqual(set(results["candidate"]), {"model_id", "model_type", "model_version", "status",
                                                     "metrics", "assumptions", "not_assessed", "issues", "applicability"})
        self.assertEqual(results["candidate"]["applicability"]["physical_applicability"], "not_assessed")
        self.assertEqual(MODEL_VERSIONS["orbital_trajectory"], "2")
        self.assertTrue(all(version == "1" for kind, version in MODEL_VERSIONS.items() if kind != "orbital_trajectory"))

    def test_duplicate_ids_and_invalid_top_level_do_not_silently_overwrite(self):
        project = project_for("drag_load", DRAG)
        project["models"].append(copy.deepcopy(project["models"][0]))
        with self.assertRaises(ValueError):
            evaluate_models(project)
        for invalid in (None, {}, {"inputs": [], "models": []}):
            with self.assertRaises(ValueError):
                evaluate_models(invalid)


if __name__ == "__main__":
    unittest.main()
