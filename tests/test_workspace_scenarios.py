"""Hypothetical cases use real adapters without altering saved designs or runs."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import workspace_scenarios as studies
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError, _digest, _encode


def spec(input_id="heat_input", values=None):
    return {"schema": "sixd.scenario-spec.v1", "name": "Explicit supplied cases",
            "source": "Constructed test assumptions; no measured hardware data.",
            "mode": "sweep", "input_id": input_id, "values": values if values is not None else [100, 200, 700]}


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.path = Path(self.tmp.name) / "workspace.sqlite3"
        self.store = WorkspaceStore(self.path)
        self.service = studies.WorkspaceScenarios(self.store)
        self.project = example_projects()["baseline"]
        self.store.create_project(self.project)
        self.view = self.store.run(self.project["project_id"], 1)
        self.identity = self.project["project_id"]
        self.run_id = self.view["run"]["run_id"]

    def tearDown(self):
        self.tmp.cleanup()

    def run_study(self, value=None):
        return self.service.run(self.identity, 1, self.run_id, spec() if value is None else value)

    def test_thermal_reference_and_baseline_immutable(self):
        before = self.store.get(self.identity)
        result = self.run_study()
        self.assertFalse(result["freshness"]["historical"])
        self.assertEqual(self.store.get(self.identity), before)
        for case, heat in zip(result["receipt"]["cases"], [100, 200, 700]):
            row = next(f for f in case["findings"] if f["requirement_id"] == "thermal_limit")
            expected = (heat / (.8 * 5.670374419e-8) + 3**4)**.25
            self.assertAlmostEqual(row["evidence"]["metric"]["value"], expected)
            self.assertAlmostEqual(row["margin"]["value"], 320 - expected)
            self.assertEqual(row["status"], "met" if expected <= 320 else "not_met")
            self.assertEqual(case["executed_model_ids"], [] if heat == 200 else ["thermal"])
        with self.store._connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM revisions").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM runs").fetchone()[0], 1)

    def test_drag_reference_quadratic_response_and_ge_margin(self):
        result = self.run_study(spec("relative_speed", [0, 50, 200]))["receipt"]
        for case, speed in zip(result["cases"], [0, 50, 200]):
            row = next(f for f in case["findings"] if f["requirement_id"] == "drag_limit")
            self.assertEqual(row["evidence"]["metric"]["value"], .5 * .01 * speed**2)
            fuel = next(f for f in case["findings"] if f["requirement_id"] == "fuel_margin")
            self.assertEqual(fuel["margin"]["value"], fuel["evidence"]["metric"]["value"])

    def test_limits_reuse_calculations_and_compare_each_own_criterion(self):
        result = self.run_study(spec("maximum_temperature", [100, 400]))["receipt"]
        for case, limit in zip(result["cases"], [100, 400]):
            self.assertEqual(case["executed_model_ids"], [])
            row = next(f for f in case["findings"] if f["requirement_id"] == "thermal_limit")
            self.assertEqual(row["metric_change"], 0)
            self.assertEqual(row["evidence"]["limit"]["value"], limit)
            self.assertEqual(row["baseline_evidence"]["limit"]["value"], 320)
            self.assertEqual(row["status"], "not_met" if limit == 100 else "met")

    def test_named_coupled_changes_only_execute_declared_dependencies(self):
        value = {k: v for k, v in spec().items() if k not in {"input_id", "values"}}
        value.update(mode="alternatives", cases=[{"name": "Explicit combined changes", "changes": {"thrust": 400, "heat_input": 700}}])
        case = self.run_study(value)["receipt"]["cases"][0]
        self.assertEqual(set(case["executed_model_ids"]), {"propulsion", "mount", "thermal"})
        self.assertEqual(case["reused_model_ids"], ["atmospheric_load"])
        self.assertEqual(case["changes"]["thrust"]["after"]["unit"], "N")
        self.assertIn("Hypothetical", case["changes"]["thrust"]["after"]["source"])

    def test_invalid_physical_input_is_unassessed_not_vehicle_failure(self):
        case = self.run_study(spec("emissivity", [0, .8]))["receipt"]["cases"][0]
        row = next(f for f in case["findings"] if f["requirement_id"] == "thermal_limit")
        self.assertEqual(row["status"], "not_assessed")
        self.assertIsNone(row["evidence"])
        self.assertIsNone(row["margin"])
        self.assertIn("Resolve", row["next_step"])

    def test_equality_target_zero_margin_and_finite_overflow(self):
        base = {"evidence": {"metric": {"value": 3, "unit": "m"}, "limit": {"value": 3}, "operator": "=="}}
        self.assertEqual(studies.margin(base)["value"], 0)
        base["evidence"]["metric"]["value"] = 1
        self.assertEqual(studies.margin(base)["value"], 2)
        base["evidence"].update(metric={"value": 1e308, "unit": "m"}, limit={"value": -1e308}, operator=">=")
        self.assertIsNone(studies.margin(base)["value"])
        self.assertIsNone(studies._finite_difference(10**400, .1))

    def test_invalid_specs_never_calculate(self):
        variants = [spec(values=[1]), spec(values=[1, 1.0]), spec(values=[True, 2]), spec(values=[float("nan"), 2]),
                    spec(values=list(range(17))), spec("absent"), spec(values=[10**400, 1]), {**spec(), "extra": 1}]
        for value in variants:
            with self.subTest(value=str(value)[:80]), patch.object(studies, "evaluate_models", side_effect=AssertionError("No solver")):
                with self.assertRaises(WorkspaceError):
                    self.run_study(value)

    def test_baseline_required_and_concurrent_lock(self):
        with self.assertRaises(WorkspaceError):
            self.service.run(self.identity, 1, [], spec())
        with self.assertRaises(ConflictError):
            self.service.run(self.identity, 1, "0" * 32, spec())
        self.service._lock.acquire()
        try:
            with self.assertRaises(ConflictError):
                self.run_study()
        finally:
            self.service._lock.release()

    def test_read_export_reopen_do_not_rerun_physics(self):
        result = self.run_study()
        identity = result["receipt"]["study_id"]
        with patch.object(studies, "evaluate_models", side_effect=AssertionError("No solver")):
            reopened = studies.WorkspaceScenarios(WorkspaceStore(self.path))
            self.assertEqual(reopened.get(identity, 1), result)
            self.assertEqual(reopened.list(self.identity, 1)["studies"][0]["study_id"], identity)

    def test_new_revision_and_repeated_baseline_label_history(self):
        result = self.run_study()
        identity = result["receipt"]["study_id"]
        self.store.run(self.identity, 1)
        self.assertTrue(self.service.get(identity, 1)["freshness"]["historical"])
        self.store.save_revision(self.identity, 1, self.project)
        self.assertTrue(self.service.get(identity, 2)["freshness"]["historical"])
        self.assertFalse(self.service.get(identity, 1)["freshness"]["baseline_run_matches"])

    def test_source_changes_label_history_and_block_execution(self):
        result = self.run_study()
        changed = {**studies._sources(), "workspace_scenarios.py": "0" * 64}
        with patch.object(studies, "_sources", return_value=changed):
            self.assertTrue(self.service.get(result["receipt"]["study_id"])["freshness"]["historical"])
            with self.assertRaises(ConflictError):
                self.run_study()

    def test_corrupt_or_rehashed_inconsistent_record_rejected(self):
        result = self.run_study()
        receipt = result["receipt"]
        receipt["cases"][0]["findings"][0]["status"] = "not_met"
        with self.store._connect(write=True) as connection:
            connection.execute("UPDATE scenario_studies SET receipt=?,digest=?", (_encode(receipt), _digest(receipt)))
        with self.assertRaises(WorkspaceError):
            self.service.get(receipt["study_id"])

    def test_orbital_retained_sample_budget_preflights_without_solver(self):
        project = example_projects()["orbital_review"]
        value = spec("duration_s", list(range(1, 17)))
        project["inputs"]["steps"]["value"] = 4096
        with self.assertRaises(WorkspaceError):
            self.service._budget(project, studies._cases(value), value["source"])

    def test_source_change_during_calculation_saves_nothing(self):
        original = studies.evaluate_models
        changed = {**studies._sources(), "workspace_scenarios.py": "0" * 64}
        calls = 0
        def calculate(project):
            nonlocal calls
            calls += 1
            return original(project)
        original_sources = studies._sources()
        with patch.object(studies, "evaluate_models", side_effect=calculate), \
                patch.object(studies, "_sources", side_effect=lambda: original_sources if not calls else changed):
            with self.assertRaises(ConflictError):
                self.run_study()
        self.assertEqual(self.service.list(self.identity, 1)["studies"], [])

    def test_alternative_validation_rejects_ambiguous_or_unbounded_inputs(self):
        base = {k: v for k, v in spec().items() if k not in {"input_id", "values"}}
        for cases in ([], [{"name": "x", "changes": {}}], [{"name": "x", "changes": {"absent": 1}}],
                      [{"name": "x", "changes": {"thrust": True}}],
                      [{"name": "same", "changes": {"thrust": 1}}] * 2,
                      [{"name": "x", "changes": {"thrust": 1}, "extra": 1}]):
            with self.subTest(cases=cases), self.assertRaises(WorkspaceError):
                self.run_study({**base, "mode": "alternatives", "cases": cases})

    def test_orbital_cases_retain_real_samples_and_do_not_change_project_simulations(self):
        project = example_projects()["orbital_review"]
        project["inputs"]["steps"]["value"] = 256
        self.store.create_project(project)
        view = self.store.run(project["project_id"], 1)
        result = self.service.run(project["project_id"], 1, view["run"]["run_id"], spec("duration_s", [100, 200]))
        for case, duration in zip(result["receipt"]["cases"], [100, 200]):
            evidence = case["review"]["evidence"]["orbit"]
            self.assertEqual(evidence["simulation"]["samples"][-1]["time_s"], duration)
            self.assertEqual(len(evidence["simulation"]["samples"]), 257)
            # Analytic circular radius is independent of duration for this supplied reference.
            self.assertLess(abs(evidence["metrics"]["final_radius_m"]["value"] / 7000000 - 1), 1e-5)
            self.assertEqual(case["executed_model_ids"], ["orbit"])
            self.assertEqual(case["reused_model_ids"], ["thermal"])
        self.assertEqual(self.store.get(project["project_id"]), view)


if __name__ == "__main__":
    unittest.main()
