"""Independent references and abstention cases for the v1 bus energy budget."""

import copy
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sixd.engineering import evaluate_models, power_parameters, verify_power_artifact


def values_for_modes(modes=None, *, energy=400, battery=20, bus=100):
    """All values are explicitly constructed, not actual spacecraft evidence."""
    if modes is None:
        modes = [
            ("idle", 10, 60, [("sensor", 10, 2), ("cpu", 20, 1)]),
            ("transmit", 5, 40, [("radio", 30, 2), ("cpu", 20, 1)]),
        ]
    values = {"usable_battery_energy": energy, "max_battery_power": battery, "bus_power_limit": bus}
    for index, (mode_id, duration, generation, loads) in enumerate(modes, 1):
        prefix = f"mode.{index}.{mode_id}."
        values[prefix + "duration"] = duration
        values[prefix + "generation"] = generation
        for load_id, power, count in loads:
            values[prefix + f"load.{load_id}.power"] = power
            values[prefix + f"load.{load_id}.count"] = count
    return values


def power_project(values=None):
    if values is None:
        values = values_for_modes()
    units = power_parameters(values)
    # Separate IDs prove parameter names are roles, not project input IDs.
    bindings = {role: f"input_{index}" for index, role in enumerate(values)}
    return {
        "inputs": {bindings[role]: {"value": value, "unit": units[role],
                                     "source": "Constructed independent reference"}
                   for role, value in values.items()},
        "models": [{"id": "power", "type": "power_energy_budget", "inputs": bindings}],
    }


def set_value(project, role, value):
    project["inputs"][project["models"][0]["inputs"][role]]["value"] = value


class PowerBudgetTests(unittest.TestCase):
    def completed(self, project=None):
        project = power_project() if project is None else project
        before = copy.deepcopy(project)
        result = evaluate_models(project)["power"]
        self.assertEqual(project, before)
        self.assertEqual(result["status"], "completed", result["issues"])
        self.assertEqual(result["model_version"], "1")
        self.assertEqual(result["issues"], [])
        self.assertTrue(verify_power_artifact(result["power_budget"], result["metrics"], project, project["models"][0]))
        return result

    def invalid(self, project):
        result = evaluate_models(project)["power"]
        self.assertEqual(result["status"], "invalid_inputs", result)
        self.assertEqual(result["metrics"], {})
        self.assertNotIn("power_budget", result)
        self.assertNotIn("simulation", result)
        self.assertTrue(result["issues"])
        return result

    def test_two_mode_independent_hand_reference(self):
        # Idle: 40 W equipment and 60 W generation for 10 s. Transmit:
        # 80 W equipment and 40 W generation for 5 s. Both total energies
        # equal 800 J, yet 200 J battery energy is still needed in transmit.
        result = self.completed()
        values = {name: record["value"] for name, record in result["metrics"].items()}
        self.assertEqual(values, {
            "peak_load_power": 80, "minimum_power_margin": -20,
            "total_load_energy": 800, "total_generated_energy": 800,
            "battery_energy_required": 200, "battery_energy_margin": 200,
            "minimum_generation_margin": -40, "max_battery_power_required": 40,
            "minimum_bus_power_margin": 20, "minimum_battery_power_margin": -20,
            "total_duration": 15, "surplus_generation_energy": 200,
        })
        energy_names = {"total_load_energy", "total_generated_energy", "battery_energy_required",
                        "battery_energy_margin", "surplus_generation_energy"}
        for name, metric in result["metrics"].items():
            self.assertEqual(metric["unit"], "J" if name in energy_names else "s" if name == "total_duration" else "W")
        self.assertNotIn("simulation", result)

    def test_mode_artifact_retains_sequence_and_equipment(self):
        artifact = self.completed()["power_budget"]
        self.assertEqual(artifact["schema"], "sixd.power-energy-budget.v1")
        self.assertEqual(artifact["limits"], {"usable_battery_energy_j": 400,
                                              "max_battery_power_w": 20, "bus_power_limit_w": 100})
        first, second = artifact["modes"]
        self.assertEqual((first["index"], first["id"], first["start_s"], first["end_s"]), (1, "idle", 0, 10))
        self.assertEqual((second["index"], second["id"], second["start_s"], second["end_s"]), (2, "transmit", 10, 15))
        self.assertEqual(first["loads"], [{"id": "cpu", "power_w": 20, "count": 1, "load_power_w": 20},
                                          {"id": "sensor", "power_w": 10, "count": 2, "load_power_w": 20}])
        self.assertEqual(first["power_margin_w"], 40)
        self.assertEqual(first["battery_power_margin_w"], 20)
        self.assertEqual(first["surplus_energy_j"], 200)
        self.assertEqual([row["remaining_energy_budget_j"] for row in artifact["modes"]], [400, 200])
        self.assertTrue(any("not battery state of charge" in item for item in artifact["assumptions"]))
        self.assertTrue(any("no charging" in item for item in artifact["assumptions"]))
        self.assertTrue(any("Inrush" in item for item in artifact["not_assessed"]))

    def test_power_failure_and_energy_sufficiency_are_separate(self):
        metrics = self.completed()["metrics"]
        self.assertLess(metrics["minimum_power_margin"]["value"], 0)
        self.assertGreater(metrics["battery_energy_margin"]["value"], 0)

    def test_energy_failure_and_power_sufficiency_are_separate(self):
        result = self.completed(power_project(values_for_modes(energy=100, battery=50)))
        self.assertEqual(result["metrics"]["minimum_power_margin"]["value"], 10)
        self.assertEqual(result["metrics"]["battery_energy_margin"]["value"], -100)
        self.assertEqual(result["power_budget"]["modes"][-1]["remaining_energy_budget_j"], -100)
        self.assertNotIn("state_of_charge", json.dumps(result))

    def test_bus_failure_is_independent_of_generation_and_battery(self):
        result = self.completed(power_project(values_for_modes(energy=1000, battery=1000, bus=79)))
        self.assertEqual(result["metrics"]["minimum_bus_power_margin"]["value"], -1)
        self.assertEqual(result["metrics"]["minimum_power_margin"]["value"], -1)
        self.assertGreater(result["metrics"]["minimum_battery_power_margin"]["value"], 0)

    def test_later_surplus_cannot_pay_an_earlier_deficit(self):
        modes = [("dark", 10, 0, [("payload", 60, 1)]),
                 ("bright", 10, 100, [("payload", 0, 1)])]
        result = self.completed(power_project(values_for_modes(modes, energy=100, battery=100, bus=100)))
        self.assertEqual(result["metrics"]["total_generated_energy"]["value"], 1000)
        self.assertEqual(result["metrics"]["total_load_energy"]["value"], 600)
        self.assertEqual(result["metrics"]["battery_energy_required"]["value"], 600)
        self.assertEqual(result["metrics"]["battery_energy_margin"]["value"], -500)
        self.assertEqual([row["remaining_energy_budget_j"] for row in result["power_budget"]["modes"]], [-500, -500])

    def test_prior_surplus_receives_no_recharge_credit_either(self):
        modes = [("bright", 10, 100, [("payload", 0, 1)]),
                 ("dark", 10, 0, [("payload", 60, 1)])]
        result = self.completed(power_project(values_for_modes(modes, energy=100, battery=100, bus=100)))
        self.assertEqual(result["metrics"]["battery_energy_margin"]["value"], -500)
        self.assertEqual(result["power_budget"]["modes"][0]["remaining_energy_budget_j"], 100)

    def test_exact_zero_margin_boundaries(self):
        modes = [("run", 10, 40, [("payload", 80, 1)])]
        result = self.completed(power_project(values_for_modes(modes, energy=400, battery=40, bus=80)))
        for name in ("minimum_power_margin", "minimum_bus_power_margin", "minimum_battery_power_margin", "battery_energy_margin"):
            self.assertEqual(result["metrics"][name]["value"], 0)

    def test_zero_loads_counts_and_capacities_are_meaningful(self):
        modes = [("off", 1, 0, [("payload", 100, 0), ("control", 0, 1)])]
        result = self.completed(power_project(values_for_modes(modes, energy=0, battery=0, bus=0)))
        self.assertEqual(result["metrics"]["total_duration"]["value"], 1)
        self.assertTrue(all(record["value"] == 0 for key, record in result["metrics"].items() if key != "total_duration"))

    def test_count_scales_all_equipment_simultaneously(self):
        modes = [("run", 2, 0, [("payload", 7, 3), ("control", 11, 2)])]
        result = self.completed(power_project(values_for_modes(modes, energy=100, battery=100, bus=100)))
        self.assertEqual(result["metrics"]["peak_load_power"]["value"], 43)
        self.assertEqual(result["metrics"]["total_load_energy"]["value"], 86)

    def test_layout_order_comes_from_indices_not_object_order(self):
        project = power_project()
        shuffled = copy.deepcopy(project)
        shuffled["models"][0]["inputs"] = dict(reversed(list(shuffled["models"][0]["inputs"].items())))
        self.assertEqual(self.completed(project), self.completed(shuffled))

    def test_huge_plus_tiny_load_does_not_report_false_zero_margin(self):
        modes = [("run", 1, 0, [("large", 1e20, 1), ("tiny", 1, 1)])]
        result = self.completed(power_project(values_for_modes(modes, energy=1e20, battery=1e20, bus=1e20)))
        for name in ("minimum_power_margin", "minimum_bus_power_margin", "minimum_battery_power_margin", "battery_energy_margin"):
            self.assertEqual(result["metrics"][name]["value"], -1)

    def test_supplied_integer_difference_is_not_rounded_before_budgeting(self):
        modes = [("run", 1, 0, [("payload", 10 ** 20 + 1, 1)])]
        result = self.completed(power_project(values_for_modes(modes, energy=10 ** 20, battery=10 ** 20, bus=10 ** 20)))
        self.assertEqual(result["metrics"]["battery_energy_margin"]["value"], -1)
        self.assertEqual(result["metrics"]["minimum_power_margin"]["value"], -1)

    def test_surplus_cancellation_retains_small_positive_generation(self):
        modes = [("run", 1, 10 ** 20 + 1, [("payload", 10 ** 20, 1)])]
        result = self.completed(power_project(values_for_modes(modes, energy=0, battery=0, bus=10 ** 20)))
        self.assertEqual(result["metrics"]["minimum_generation_margin"]["value"], 1)
        self.assertEqual(result["metrics"]["surplus_generation_energy"]["value"], 1)
        self.assertEqual(result["metrics"]["battery_energy_required"]["value"], 0)

    def test_fractional_counts_and_negative_values_abstain(self):
        for role, value in [("mode.1.idle.load.cpu.count", 0.5), ("mode.1.idle.load.cpu.count", -1),
                            ("mode.1.idle.load.cpu.count", 1000001), ("mode.1.idle.load.cpu.power", -1),
                            ("mode.1.idle.generation", -1), ("usable_battery_energy", -1),
                            ("max_battery_power", -1), ("bus_power_limit", -1),
                            ("mode.1.idle.duration", 0), ("mode.1.idle.duration", -1)]:
            with self.subTest(role=role, value=value):
                project = power_project()
                set_value(project, role, value)
                self.invalid(project)

    def test_integral_float_count_and_maximum_bound_are_supported(self):
        modes = [("run", 1, 0, [("payload", 1, 1000000.0)])]
        result = self.completed(power_project(values_for_modes(modes, energy=1e6, battery=1e6, bus=1e6)))
        self.assertEqual(result["power_budget"]["modes"][0]["loads"][0]["count"], 1000000)
        self.assertIs(type(result["power_budget"]["modes"][0]["loads"][0]["count"]), int)

    def test_nonfinite_boolean_and_string_values_abstain(self):
        for value in (True, False, "20", None, math.inf, -math.inf, math.nan, 10 ** 400):
            for role in ("usable_battery_energy", "mode.1.idle.load.cpu.power", "mode.1.idle.load.cpu.count"):
                with self.subTest(value=repr(value)[:25], role=role):
                    project = power_project()
                    set_value(project, role, value)
                    self.invalid(project)

    def test_exact_units_and_source_are_required(self):
        for role, unit in [("usable_battery_energy", "Wh"), ("max_battery_power", "kW"),
                           ("mode.1.idle.duration", "min"), ("mode.1.idle.load.cpu.count", "count")]:
            with self.subTest(role=role):
                project = power_project()
                project["inputs"][project["models"][0]["inputs"][role]]["unit"] = unit
                self.invalid(project)
        project = power_project()
        project["inputs"][project["models"][0]["inputs"]["bus_power_limit"]]["source"] = " "
        self.invalid(project)

    def test_missing_reference_and_extra_record_fields_abstain(self):
        project = power_project()
        del project["inputs"][project["models"][0]["inputs"]["bus_power_limit"]]
        self.invalid(project)
        project = power_project()
        project["inputs"][project["models"][0]["inputs"]["bus_power_limit"]]["uncertainty"] = 1
        self.invalid(project)

    def test_invalid_dynamic_role_layouts_abstain(self):
        def mutate(transform):
            project = power_project()
            project["models"][0]["inputs"] = transform(project["models"][0]["inputs"])
            return project
        cases = [
            lambda b: {k: v for k, v in b.items() if k != "usable_battery_energy"},
            lambda b: {k: v for k, v in b.items() if not k.startswith("mode.")},
            lambda b: {k: v for k, v in b.items() if k != "mode.1.idle.generation"},
            lambda b: {k: v for k, v in b.items() if k != "mode.1.idle.load.cpu.count"},
            lambda b: {k: v for k, v in b.items() if not k.startswith("mode.1.idle.load.")},
            lambda b: {k.replace("mode.2.", "mode.3."): v for k, v in b.items()},
            lambda b: {k.replace("mode.1.", "mode.01."): v for k, v in b.items()},
            lambda b: {k.replace("mode.1.", "mode.0."): v for k, v in b.items()},
            lambda b: {k.replace("mode.2.transmit.", "mode.2.idle."): v for k, v in b.items()},
            lambda b: dict(b, **{"mode.1.other.generation": "input_0"}),
            lambda b: dict(b, **{"mode.1.idle.duty_cycle": "input_0"}),
            lambda b: dict(b, **{"mode.1.idle.load.cpu.voltage": "input_0"}),
            lambda b: {k.replace(".idle.", ".constructor."): v for k, v in b.items()},
            lambda b: {k.replace(".load.cpu.", ".load.prototype."): v for k, v in b.items()},
            lambda b: {k.replace(".idle.", ".__proto__."): v for k, v in b.items()},
            lambda b: {k.replace(".idle.", ".bad id."): v for k, v in b.items()},
        ]
        for index, transform in enumerate(cases):
            with self.subTest(index=index):
                self.invalid(mutate(transform))

    def test_parameter_contract_rejects_non_object_and_non_string_keys(self):
        for bindings in (None, [], "", {False: "input"}):
            with self.subTest(bindings=bindings), self.assertRaises(ValueError):
                power_parameters(bindings)

    def test_maximum_modes_and_load_rows_are_supported_and_bounded(self):
        modes = [(f"phase{i}", 1, 0, [(f"item{j}", 1, 1) for j in range(8)]) for i in range(16)]
        result = self.completed(power_project(values_for_modes(modes, energy=128, battery=8, bus=8)))
        self.assertEqual(len(result["power_budget"]["modes"]), 16)
        self.assertEqual(result["metrics"]["battery_energy_required"]["value"], 128)
        too_many = values_for_modes(modes + [("extra", 1, 0, [("item", 1, 1)])])
        with self.assertRaisesRegex(ValueError, "16"):
            power_parameters(too_many)
        modes[0][3].append(("extra", 1, 1))
        with self.assertRaisesRegex(ValueError, "128"):
            power_parameters(values_for_modes(modes))

    def test_overflow_and_underflow_produce_no_partial_artifact(self):
        modes_to_reject = [
            [("run", 1e308, 0, [("payload", 1e308, 1)])],
            [("run", 1, 0, [("payload", 1e308, 1000000)])],
            [("run", 5e-324, 0, [("payload", 5e-324, 1)])],
            [("run", 5e-324, 5e-324, [("payload", 0, 1)])],
        ]
        for modes in modes_to_reject:
            with self.subTest(modes=modes):
                self.invalid(power_project(values_for_modes(modes)))

    def test_collapsed_timeline_is_not_displayed_as_a_zero_duration_mode(self):
        modes = [("long", 1e20, 0, [("off", 0, 0)]), ("short", 1, 0, [("off", 0, 0)])]
        result = self.invalid(power_project(values_for_modes(modes)))
        self.assertIn("timeline", result["issues"][0])

    def test_result_roundtrips_and_verifies_without_running_adapters(self):
        project = power_project()
        result = json.loads(json.dumps(self.completed(project), allow_nan=False))
        with patch("sixd.engineering.evaluate_models", side_effect=AssertionError("No model execution during verification")):
            self.assertTrue(verify_power_artifact(result["power_budget"], result["metrics"], project, project["models"][0]))

    def test_artifact_verifier_catches_rehashed_corruption(self):
        project = power_project()
        result = self.completed(project)
        for field, value in [("load_power_w", 1), ("generation_power_w", 1),
                             ("remaining_energy_budget_j", 10000), ("battery_power_required_w", 0),
                             ("start_s", 5), ("index", True), ("id", "other")]:
            with self.subTest(field=field):
                changed = copy.deepcopy(result["power_budget"])
                changed["modes"][1][field] = value
                with self.assertRaises(ValueError):
                    verify_power_artifact(changed, result["metrics"], project, project["models"][0])
        changes = []
        artifact = copy.deepcopy(result["power_budget"])
        artifact["modes"][0]["loads"][0]["count"] = True
        changes.append(artifact)
        artifact = copy.deepcopy(result["power_budget"])
        artifact["modes"].reverse()
        changes.append(artifact)
        artifact = copy.deepcopy(result["power_budget"])
        artifact["limits"]["max_battery_power_w"] = 100
        changes.append(artifact)
        artifact = copy.deepcopy(result["power_budget"])
        artifact["assumptions"] = ["Battery charging is simulated."]
        changes.append(artifact)
        artifact = copy.deepcopy(result["power_budget"])
        artifact["not_assessed"] = []
        changes.append(artifact)
        artifact = copy.deepcopy(result["power_budget"])
        artifact["modes"][0]["load_power_w"] = math.nan
        changes.append(artifact)
        for index, artifact in enumerate(changes):
            with self.subTest(index=index), self.assertRaises(ValueError):
                verify_power_artifact(artifact, result["metrics"], project, project["models"][0])

    def test_metrics_and_bound_input_corruption_are_rejected(self):
        project = power_project()
        result = self.completed(project)
        for metric, value in [("battery_energy_margin", 0), ("minimum_power_margin", False),
                              ("total_duration", 99)]:
            metrics = copy.deepcopy(result["metrics"])
            metrics[metric]["value"] = value
            with self.subTest(metric=metric), self.assertRaises(ValueError):
                verify_power_artifact(result["power_budget"], metrics, project, project["models"][0])
        changed_project = copy.deepcopy(project)
        set_value(changed_project, "mode.2.transmit.duration", 6)
        with self.assertRaises(ValueError):
            verify_power_artifact(result["power_budget"], result["metrics"], changed_project, changed_project["models"][0])
        with self.assertRaises(ValueError):
            verify_power_artifact(result["power_budget"], result["metrics"], project, {"type": "drag_load"})

    def test_invalid_power_model_does_not_suppress_another_supported_model(self):
        project = power_project()
        set_value(project, "usable_battery_energy", -1)
        project["inputs"].update({
            "rho": {"value": 1.2, "unit": "kg/m^3", "source": "Constructed"},
            "speed": {"value": 50, "unit": "m/s", "source": "Constructed"},
            "cd": {"value": 0.8, "unit": "1", "source": "Constructed"},
            "area": {"value": 0.25, "unit": "m^2", "source": "Constructed"},
        })
        project["models"].append({"id": "drag", "type": "drag_load", "inputs": {
            "density": "rho", "relative_speed": "speed", "drag_coefficient": "cd", "reference_area": "area"}})
        result = evaluate_models(project)
        self.assertEqual(result["power"]["status"], "invalid_inputs")
        self.assertEqual(result["drag"]["status"], "completed")
        self.assertEqual(result["drag"]["metrics"]["drag_force"]["value"], 300)


if __name__ == "__main__":
    unittest.main()
