"""Power budgets remain immutable, scoped evidence in the existing workspace.

The two-mode witness is independently calculated: cruise draws 50 W from the
battery for 100 s; downlink has a 50 W generation surplus for 50 s. Surplus is
reported but never credited as battery recharge. No hardware data or paid AI.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import engineering, lifecycle, project_authoring, project_investigation, workspace
from sixd.project_examples import example_projects
from sixd.providers import Turn
from sixd.test_evidence import TestEvidence, validate_investigation_context
from sixd.workspace import WorkspaceError, WorkspaceStore, _digest, _encode
from sixd.workspace_scenarios import WorkspaceScenarios
from sixd.workspace_systems import WorkspaceSystems
from sixd.workspace_test_data import WorkspaceTestData


def power_project(identity="independent-power-workspace"):
    """A separate reference fixture; never derive expectations from the adapter."""
    project = deepcopy(example_projects()["baseline"])
    project["project_id"] = identity
    project["name"] = "Constructed sequential spacecraft power budget"
    project["inputs"].update({
        key: {"value": value, "unit": unit, "source": "Independent constructed power reference; no hardware data."}
        for key, value, unit in (
            ("usable_energy", 6000, "J"), ("battery_power", 60, "W"), ("bus_limit", 100, "W"),
            ("cruise_duration", 100, "s"), ("cruise_generation", 20, "W"),
            ("avionics_power", 10, "W"), ("one_unit", 1, "1"),
            ("payload_power", 30, "W"), ("payload_count", 2, "1"),
            ("downlink_duration", 50, "s"), ("downlink_generation", 100, "W"),
            ("radio_power", 40, "W"), ("minimum_power_margin", 0, "W"),
            ("minimum_energy_margin", 0, "J"), ("peak_demand_limit", 85, "W"),
        )})
    project["models"].append({"id": "power", "type": "power_energy_budget", "inputs": {
        "usable_battery_energy": "usable_energy", "max_battery_power": "battery_power", "bus_power_limit": "bus_limit",
        "mode.1.cruise.duration": "cruise_duration", "mode.1.cruise.generation": "cruise_generation",
        "mode.1.cruise.load.avionics.power": "avionics_power", "mode.1.cruise.load.avionics.count": "one_unit",
        "mode.1.cruise.load.payload.power": "payload_power", "mode.1.cruise.load.payload.count": "payload_count",
        "mode.2.downlink.duration": "downlink_duration", "mode.2.downlink.generation": "downlink_generation",
        "mode.2.downlink.load.radio.power": "radio_power", "mode.2.downlink.load.radio.count": "one_unit",
        "mode.2.downlink.load.avionics.power": "avionics_power", "mode.2.downlink.load.avionics.count": "one_unit",
    }})
    for requirement_id, title, metric, operator, limit in (
        ("power_capacity", "Declared bus and battery power capacity", "minimum_power_margin", ">=", "minimum_power_margin"),
        ("energy_capacity", "Declared usable energy capacity", "battery_energy_margin", ">=", "minimum_energy_margin"),
        ("peak_demand", "Declared equipment peak demand", "peak_load_power", "<=", "peak_demand_limit"),
    ):
        project["requirements"].append({"id": requirement_id, "title": title, "model_id": "power",
            "metric": metric, "operator": operator, "limit_input": limit, "critical": True})
    return project


class OfflinePowerProvider:
    mode = "offline_transport_fixture"
    model = "offline-power-reproducibility-reference"

    def __init__(self):
        self.request_attempts, self.histories = 0, []

    def complete(self, messages, tools):
        self.request_attempts += 1
        self.histories.append(deepcopy(messages))
        available = {item["function"]["name"]: item for item in tools}
        required = json.loads(messages[1]["content"])["required_actions"]
        action = next(name for name in ("read_requirement", "read_model", "read_changes", "recheck_model", "finish")
                      if name in available and (name != "read_changes" or name in required))
        arguments = {}
        if action == "finish":
            arguments = {"evidence_ids": available[action]["function"]["parameters"]["properties"]["evidence_ids"]["items"]["enum"],
                "summary": "The calculated criterion is met within the supplied sequential-mode budget. "
                "Review equipment demand, simultaneous operating modes, generation and usable battery energy against their sources. "
                "Confirm losses and reserve allocation separately; charging, transients and hardware validity remain unassessed."}
        return Turn({"role": "assistant", "content": None, "tool_calls": [{"id": "offline-power-" + str(self.request_attempts),
            "type": "function", "function": {"name": action, "arguments": json.dumps(arguments)}}]},
            {"prompt_tokens": 10, "completion_tokens": 10})


class PowerWorkspaceTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "work").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "power.sqlite3"
        self.store = WorkspaceStore(self.path)
        self.project = power_project()
        self.identity = self.project["project_id"]

    def baseline(self):
        self.store.create_project(self.project)
        return self.store.run(self.identity, 1)

    def contents(self):
        with self.store._connect() as connection:
            names = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name: [tuple(row) for row in connection.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
                    for name in names}

    def test_independent_budget_metrics_and_modes_are_saved_and_reopened_unchanged(self):
        view = self.baseline()
        result = view["run"]["model_results"]["power"]
        expected = {
            "peak_load_power": (70, "W"), "minimum_power_margin": (10, "W"),
            "total_load_energy": (9500, "J"), "total_generated_energy": (7000, "J"),
            "battery_energy_required": (5000, "J"), "battery_energy_margin": (1000, "J"),
            "minimum_generation_margin": (-50, "W"), "max_battery_power_required": (50, "W"),
            "minimum_bus_power_margin": (30, "W"), "minimum_battery_power_margin": (10, "W"),
            "total_duration": (150, "s"), "surplus_generation_energy": (2500, "J"),
        }
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["metrics"], {name: {"value": value, "unit": unit} for name, (value, unit) in expected.items()})
        self.assertEqual(len(result["power_budget"]["modes"]), 2)
        self.assertEqual(view["run"]["review"]["evidence"]["power"]["power_budget"], result["power_budget"])
        self.assertTrue(lifecycle.verify_review(view["run"]["review"]))
        self.assertTrue(all(view["run"]["review"]["findings"][key]["status"] == "met"
                            for key in ("power_capacity", "energy_capacity", "peak_demand")))
        before = self.contents()
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("Opening evidence must not calculate")):
            self.assertEqual(WorkspaceStore(self.path).get(self.identity), view)
        self.assertEqual(self.contents(), before)
        self.assertEqual(view["run"]["live_model_calls"], 0)
        self.assertFalse(view["run"]["review"]["launch_authorization"])

    def test_duration_edit_targets_power_and_preserves_original_run_and_other_origins(self):
        original = self.baseline()
        original_bytes = _encode(original["run"])
        changed = deepcopy(original["project"])
        changed["inputs"]["cruise_duration"]["value"] = 200
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("Draft preview is not a calculation")):
            preview = self.store.preview_change(self.identity, 1, changed)
        self.assertEqual(preview["affected_model_ids"], ["power"])
        self.assertEqual(set(preview["affected_requirement_ids"]), {"power_capacity", "energy_capacity", "peak_demand"})
        saved = self.store.save_revision(self.identity, 1, changed)
        self.assertIsNone(saved["run"])
        with patch.object(workspace, "evaluate_models", wraps=engineering.evaluate_models) as calculate:
            current = self.store.run(self.identity, 2)
        self.assertEqual([call.args[0]["models"][0]["id"] for call in calculate.call_args_list], ["power"])
        self.assertEqual(current["run"]["model_results"]["power"]["metrics"]["battery_energy_required"], {"value": 10000, "unit": "J"})
        self.assertEqual(current["run"]["review"]["findings"]["energy_capacity"]["status"], "not_met")
        self.assertEqual(current["run"]["review"]["findings"]["power_capacity"]["status"], "met")
        for model_id in ("thermal", "mount", "propulsion", "atmospheric_load"):
            self.assertIn(model_id, current["run"]["reused_model_ids"])
            self.assertEqual(current["run"]["model_origins"][model_id]["run_id"], original["run"]["run_id"])
        self.assertEqual(_encode(self.store.get(self.identity, 1)["run"]), original_bytes)

    def test_power_capacity_failure_is_separate_from_available_energy(self):
        self.project["inputs"]["battery_power"]["value"] = 40
        view = self.baseline()
        result = view["run"]["model_results"]["power"]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["metrics"]["minimum_power_margin"], {"value": -10, "unit": "W"})
        self.assertEqual(result["metrics"]["battery_energy_margin"], {"value": 1000, "unit": "J"})
        self.assertEqual(view["run"]["review"]["findings"]["power_capacity"]["status"], "not_met")
        self.assertEqual(view["run"]["review"]["findings"]["energy_capacity"]["status"], "met")

    def test_limit_only_revision_reassesses_without_rerunning_budget(self):
        original = self.baseline()
        changed = deepcopy(original["project"])
        changed["inputs"]["minimum_energy_margin"]["value"] = 1500
        self.assertEqual(self.store.preview_change(self.identity, 1, changed)["affected_model_ids"], [])
        self.store.save_revision(self.identity, 1, changed)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No model dependency changed")):
            current = self.store.run(self.identity, 2)
        self.assertEqual(current["run"]["executed_model_ids"], [])
        self.assertEqual(current["run"]["model_results"]["power"], original["run"]["model_results"]["power"])
        self.assertEqual(current["run"]["review"]["findings"]["energy_capacity"]["status"], "not_met")

    def test_malformed_mode_and_wrong_units_are_unassessed_not_power_failure(self):
        for failure in ("missing_duration", "wrong_unit", "fractional_count", "negative_generation"):
            with self.subTest(failure=failure):
                project = deepcopy(self.project)
                project["project_id"] += "-" + failure
                if failure == "missing_duration":
                    del project["models"][-1]["inputs"]["mode.1.cruise.duration"]
                elif failure == "wrong_unit":
                    project["inputs"]["usable_energy"]["unit"] = "Wh"
                elif failure == "fractional_count":
                    project["inputs"]["payload_count"]["value"] = 1.5
                else:
                    project["inputs"]["cruise_generation"]["value"] = -1
                self.store.create_project(project)
                current = self.store.run(project["project_id"], 1)
                result = current["run"]["model_results"]["power"]
                self.assertEqual(result["status"], "invalid_inputs", result)
                self.assertEqual(result["metrics"], {})
                self.assertNotIn("power_budget", result)
                self.assertTrue(all(current["run"]["review"]["findings"][key]["status"] == "not_assessed"
                                    for key in ("power_capacity", "energy_capacity", "peak_demand")))
                self.assertEqual(current["run"]["model_results"]["thermal"]["status"], "completed")

    def test_wrong_requirement_unit_is_a_comparison_gap_not_a_failed_budget(self):
        self.project["inputs"]["minimum_energy_margin"]["unit"] = "W"
        view = self.baseline()
        self.assertEqual(view["run"]["model_results"]["power"]["status"], "completed")
        self.assertEqual(view["run"]["review"]["findings"]["energy_capacity"]["status"], "not_assessed")
        self.assertEqual(view["run"]["review"]["findings"]["power_capacity"]["status"], "met")

    def test_corrupt_or_absent_artifact_cannot_be_reviewed_as_completed(self):
        good = engineering.evaluate_models(self.project)
        self.assertEqual(good["power"]["status"], "completed")
        for failure in ("absent", "empty_modes", "wrong_schema", "extra_field", "wrong_metric"):
            with self.subTest(failure=failure):
                bad = deepcopy(good)
                if failure == "absent":
                    del bad["power"]["power_budget"]
                elif failure == "empty_modes":
                    bad["power"]["power_budget"]["modes"] = []
                elif failure == "wrong_schema":
                    bad["power"]["power_budget"]["schema"] = "unverified"
                elif failure == "extra_field":
                    bad["power"]["power_budget"]["launch_authorization"] = True
                else:
                    bad["power"]["metrics"]["battery_energy_required"]["value"] = 2500
                with self.assertRaises(ValueError):
                    lifecycle.review_project(self.project, bad)

    def test_invalid_model_cannot_smuggle_a_completed_artifact(self):
        good = engineering.evaluate_models(self.project)
        for status in ("invalid_inputs", "not_assessed"):
            bad = deepcopy(good)
            bad["power"].update(status=status, metrics={})
            with self.subTest(status=status), self.assertRaises(ValueError):
                lifecycle.review_project(self.project, bad)

    def test_rehashed_stored_artifact_corruption_is_rejected_on_read(self):
        current = self.baseline()
        run = deepcopy(current["run"])
        # Recompute the storage digest: integrity must include semantic artifact
        # validation and agreement with immutable review evidence, not hash only.
        run["model_results"]["power"]["power_budget"]["modes"] = []
        with self.store._connect(write=True) as connection:
            connection.execute("UPDATE runs SET receipt=?,digest=? WHERE run_id=?",
                (_encode(run), _digest(run), run["run_id"]))
        with self.assertRaises(WorkspaceError):
            self.store.get(self.identity)

    def test_rehashing_review_envelope_cannot_hide_changed_mode_arithmetic(self):
        current = self.baseline()
        review = deepcopy(current["run"]["review"])
        evidence = review["evidence"]["power"]
        evidence["power_budget"]["modes"][0]["battery_energy_required_j"] = 2500
        evidence["fingerprint"] = _digest({key: value for key, value in evidence.items() if key != "fingerprint"})
        review["digest"] = _digest({key: value for key, value in review.items() if key != "digest"})
        with self.assertRaises(ValueError):
            lifecycle.verify_review(review)

    def test_nonfinite_boolean_and_string_inputs_cannot_overwrite_a_saved_revision(self):
        original = self.baseline()
        before = self.contents()
        for value in (True, "100", float("nan"), float("inf")):
            with self.subTest(value=repr(value)):
                invalid = deepcopy(original["project"])
                invalid["inputs"]["cruise_duration"]["value"] = value
                with self.assertRaises(WorkspaceError):
                    self.store.save_revision(self.identity, 1, invalid)
                self.assertEqual(self.contents(), before)

    def test_recorded_input_source_change_reruns_only_power_without_inventing_physical_change(self):
        original = self.baseline()
        changed = deepcopy(original["project"])
        changed["inputs"]["cruise_generation"]["source"] = "Revised declaration; same supplied bus-level generation value."
        impact = self.store.preview_change(self.identity, 1, changed)
        self.assertEqual(impact["affected_model_ids"], ["power"])
        self.store.save_revision(self.identity, 1, changed)
        current = self.store.run(self.identity, 2)
        self.assertEqual(current["run"]["executed_model_ids"], ["power"])
        self.assertEqual(current["run"]["model_results"]["power"], original["run"]["model_results"]["power"])
        self.assertNotEqual(current["run"]["review"]["evidence"]["power"]["fingerprint"],
                            original["run"]["review"]["evidence"]["power"]["fingerprint"])

    def test_legacy_component_review_remains_readable_without_any_power_artifact(self):
        legacy = deepcopy(example_projects()["baseline"])
        self.store.create_project(legacy)
        original = self.store.run(legacy["project_id"], 1)
        before = _encode(original["run"])
        self.assertTrue(all("power_budget" not in row for row in original["run"]["review"]["evidence"].values()))
        self.assertTrue(lifecycle.verify_review(original["run"]["review"]))
        self.assertEqual(_encode(WorkspaceStore(self.path).get(legacy["project_id"])["run"]), before)
        # A genuinely earlier adapter-version manifest did not mention power.
        # Its absent unused adapter cannot invalidate existing component proof.
        old_review = deepcopy(original["run"]["review"])
        del old_review["adapter_versions"]["power_energy_budget"]
        old_review["digest"] = _digest({key: value for key, value in old_review.items() if key != "digest"})
        self.assertTrue(lifecycle.verify_review(old_review))

    def test_power_model_metric_can_feed_an_explicit_interface_without_coupling(self):
        self.project["systems"] = [
            {"id": "electrical", "title": "Electrical budget", "description": "Supplied bus budget", "parent_id": None, "model_ids": ["power"]},
            {"id": "payload", "title": "Equipment allowance", "description": "Declared interface allowance", "parent_id": None, "model_ids": []},
        ]
        self.project["interfaces"] = [{"id": "electrical_peak", "title": "Declared peak bus demand",
            "description": "Capacity check only; no values are copied into another model.", "from_system": "electrical", "to_system": "payload",
            "source": {"kind": "model_metric", "model_id": "power", "metric": "peak_load_power"}, "target_input": "peak_demand_limit",
            "quantity": "Bus power", "unit": "W", "operator": "<=", "critical": True}]
        current = self.baseline()
        row = current["system_interfaces"]["checks"]["rows"][0]
        self.assertEqual(row["status"], "met")
        self.assertEqual(row["source_value"], {"value": 70, "unit": "W"})
        before = self.contents()
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("A read is not execution")):
            self.assertEqual(WorkspaceSystems(self.store).get(self.identity, 1), current["system_interfaces"])
        self.assertEqual(self.contents(), before)

    def test_duration_scenarios_preserve_baseline_and_show_energy_shortfall_only(self):
        current = self.baseline()
        service = WorkspaceScenarios(self.store)
        result = service.run(self.identity, 1, current["run"]["run_id"], {
            "schema": "sixd.scenario-spec.v1", "name": "Declared cruise duration alternatives",
            "source": "Synthetic operating schedule; no mission prediction.", "mode": "sweep",
            "input_id": "cruise_duration", "values": [100, 200]})
        short, long = result["receipt"]["cases"]
        self.assertEqual(short["executed_model_ids"], [])
        self.assertEqual(long["executed_model_ids"], ["power"])
        rows = {row["requirement_id"]: row for row in long["findings"]}
        self.assertEqual(rows["energy_capacity"]["status"], "not_met")
        self.assertEqual(rows["energy_capacity"]["evidence"]["metric"], {"value": -4000, "unit": "J"})
        self.assertEqual(rows["power_capacity"]["status"], "met")
        self.assertEqual(self.store.get(self.identity), current)
        study_id = result["receipt"]["study_id"]
        self.assertEqual(service.get(study_id, 1), result)

    def test_scalar_test_observation_compares_energy_and_preserves_separate_outcomes(self):
        current = self.baseline()
        tests = WorkspaceTestData(self.store)
        saved = tests.run(self.identity, 1, current["run"]["run_id"], {
            "schema": "sixd.test-comparison-spec.v1", "name": "Constructed energy-margin reading",
            "source": "Synthetic arithmetic observation; not measured hardware.", "data_kind": "synthetic",
            "test_conditions": "Declared same usable-energy margin observable and schedule; unverified.", "conditions_match": "declared_match",
            "filename": "energy.csv", "csv_text": "id,req,value,unit,tolerance\r\nenergy-a,energy_capacity,-100,J,1200\r\n",
            "mapping": {"measurement_id": "id", "requirement_id": "req", "value": "value", "unit": "unit", "tolerance": "tolerance"}})
        receipt = saved["receipt"]
        row = receipt["row_results"][0]
        self.assertEqual(row["measurement_requirement"]["status"], "not_met")
        self.assertEqual(row["prediction_agreement"]["status"], "within_tolerance")
        self.assertEqual(current["run"]["review"]["findings"]["energy_capacity"]["status"], "met")
        links = TestEvidence(self.store, tests)
        context = links.investigation_context(self.identity, 1, "energy_capacity", receipt["comparison_id"], 2)
        scoped = {**current, "test_evidence": context}
        self.assertTrue(validate_investigation_context(context, scoped, "energy_capacity"))
        self.assertTrue(project_investigation.validate_investigation_view(scoped, "energy_capacity"))
        self.assertEqual(links.review_export(self.identity, 1)["workspace"]["run"], current["run"])

    def test_scoped_offline_assistant_reads_saved_budget_and_rechecks_only_power(self):
        current = self.baseline()
        provider = OfflinePowerProvider()
        before = self.contents()
        with patch.object(project_investigation, "evaluate_models", wraps=engineering.evaluate_models) as calculate:
            receipt = project_investigation.investigate_project(current, "energy_capacity", "Explain the saved energy budget.",
                provider, investigation_id="offline-power-reference")
        self.assertEqual(receipt["state"], "completed", receipt)
        self.assertEqual(receipt["live_model_calls"], 0)
        self.assertEqual(receipt["finding_status"], "met")
        self.assertEqual(calculate.call_count, 1)
        self.assertEqual([model["id"] for model in calculate.call_args.args[0]["models"]], ["power"])
        self.assertTrue(receipt["evidence"]["recheck:power"]["matches_saved_result"])
        self.assertEqual(receipt["evidence"]["model:power"]["recorded_evidence"]["power_budget"],
                         current["run"]["review"]["evidence"]["power"]["power_budget"])
        self.assertEqual(self.contents(), before)


if __name__ == "__main__":
    unittest.main()
