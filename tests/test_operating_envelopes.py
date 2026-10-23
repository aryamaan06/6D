"""Bounded Cartesian studies: independent arithmetic and frozen evidence checks."""
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


def spec(*axes):
    return {"schema": "sixd.envelope-spec.v1", "name": "Constructed sampled conditions",
            "source": "Synthetic test ranges; no hardware validation.", "mode": "grid",
            "axes": [{"input_id": identity, "minimum": low, "maximum": high, "points": points}
                     for identity, low, high, points in (axes or (("relative_speed", 0, 200, 3),))]}


class EnvelopeTests(unittest.TestCase):
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

    def test_preview_cartesian_order_exact_endpoints_and_no_solver(self):
        value = spec(("relative_speed", 0, 200, 3), ("heat_input", 100, 700, 2))
        with patch.object(studies, "evaluate_models", side_effect=AssertionError("No solver")), \
                patch.object(studies, "evaluate_model", side_effect=AssertionError("No solver")):
            preview = self.service.preview_envelope(self.identity, 1, self.run_id, value)
        self.assertEqual(preview["case_count"], 6)
        self.assertEqual([case["changes"] for case in preview["cases"]],
                         [{"relative_speed": speed, "heat_input": heat} for speed in (0, 100, 200) for heat in (100, 700)])
        self.assertEqual(preview["axes"][0], {"input_id": "relative_speed", "unit": "m/s", "values": [0, 100, 200]})
        self.assertEqual(self.service.list(self.identity, 1)["studies"], [])

    def test_static_reference_counts_and_worst_margin_are_hand_computed(self):
        before = self.store.get(self.identity)
        result = self.run_study()
        receipt = result["receipt"]
        self.assertEqual(receipt["schema"], studies.ENVELOPE_SCHEMA)
        limit = self.project["inputs"][next(r["limit_input"] for r in self.project["requirements"] if r["id"] == "drag_limit")]["value"]
        rows = [next(r for r in case["findings"] if r["requirement_id"] == "drag_limit") for case in receipt["cases"]]
        expected = [.5 * .01 * speed**2 for speed in (0, 100, 200)]
        self.assertEqual([r["evidence"]["metric"]["value"] for r in rows], expected)
        summary = next(r for r in receipt["envelope_summary"] if r["requirement_id"] == "drag_limit")
        self.assertEqual(summary["counts"], {"met": sum(v <= limit for v in expected), "not_met": sum(v > limit for v in expected), "not_assessed": 0})
        self.assertEqual(summary["worst_observed"], {"value": limit - expected[-1], "unit": "N", "kind": "signed_margin", "case_indices": [2]})
        self.assertEqual(self.store.get(self.identity), before)
        with self.store._connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM revisions").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM runs").fetchone()[0], 1)

    def test_equal_worst_cases_keep_all_ties_and_units_separate(self):
        receipt = self.run_study(spec(("relative_speed", -100, 100, 3)))["receipt"]
        row = next(r for r in receipt["envelope_summary"] if r["requirement_id"] == "drag_limit")
        # Negative speed is outside the maintained drag model; do not infer
        # symmetry or discard the unsupported case when selecting a maximum.
        self.assertEqual(row["unresolved_cases"], [0])
        thermal = next(r for r in receipt["envelope_summary"] if r["requirement_id"] == "thermal_limit")
        self.assertEqual(thermal["worst_observed"]["case_indices"], [0, 1, 2])
        self.assertEqual(thermal["unit"], "K")
        self.assertEqual(row["unit"], "N")

    def test_equal_target_summary_uses_largest_absolute_difference(self):
        project = deepcopy(self.project)
        requirement = next(r for r in project["requirements"] if r["id"] == "drag_limit")
        requirement["operator"] = "=="
        cases = []
        for index, value in enumerate((0, 4, 4)):
            cases.append({"index": index, "findings": [{"requirement_id": r["id"], "status": "met" if value == 0 else "not_met",
                "margin": {"value": value, "unit": project["inputs"][r["limit_input"]]["unit"],
                           "kind": "absolute_difference" if r["operator"] == "==" else "signed_margin"}}
                for r in project["requirements"]]})
        row = next(r for r in studies.envelope_findings_summary(cases, project) if r["requirement_id"] == "drag_limit")
        self.assertEqual(row["worst_observed"]["value"], 4)
        self.assertEqual(row["worst_observed"]["case_indices"], [1, 2])
        self.assertEqual(row["status"], "sampled_violation")

    def test_unresolved_physical_cases_never_disappear(self):
        receipt = self.run_study(spec(("emissivity", 0, 1, 3)))["receipt"]
        row = next(r for r in receipt["envelope_summary"] if r["requirement_id"] == "thermal_limit")
        self.assertEqual(row["counts"]["not_assessed"], 1)
        self.assertEqual(row["unresolved_cases"], [0])
        self.assertNotEqual(row["status"], "all_sampled_met")
        case = receipt["cases"][0]
        finding = next(r for r in case["findings"] if r["requirement_id"] == "thermal_limit")
        self.assertTrue(finding["reason"])
        self.assertIsNone(finding["margin"])

    def test_margin_overflow_cannot_produce_all_sampled_met(self):
        project = {"requirements": [{"id": "r", "title": "Overflow", "operator": ">=", "limit_input": "limit"}],
                   "inputs": {"limit": {"value": -1e308, "unit": "N"}}}
        overflow = studies.margin({"evidence": {"metric": {"value": 1e308, "unit": "N"}, "limit": {"value": -1e308}, "operator": ">="}})
        row = studies.envelope_findings_summary([{"index": 0, "findings": [{"requirement_id": "r", "status": "met", "margin": overflow}]}], project)[0]
        self.assertEqual(row["counts"]["met"], 1)
        self.assertEqual(row["unresolved_cases"], [0])
        self.assertEqual(row["status"], "unresolved")
        self.assertIsNone(row["worst_observed"])

    def test_fixed_criterion_and_noop_or_resolution_axes_rejected(self):
        eligible = {row["input_id"] for row in self.service.list(self.identity, 1)["eligible_inputs"]}
        self.assertNotIn("maximum_temperature", eligible)
        project = deepcopy(self.project)
        project["models"][0]["inputs"]["ignored_unused_role"] = "maximum_temperature"
        self.assertNotIn("maximum_temperature", {row["input_id"] for row in studies.eligible_inputs(project)})
        for identity in ("maximum_temperature", "not_a_parameter"):
            with self.assertRaises(WorkspaceError):
                self.run_study(spec((identity, 1, 2, 2)))
        for example in ("orbital_review", "attitude_review", "powered_flight"):
            if example not in example_projects():
                continue
            eligible = {row["input_id"] for row in studies.eligible_inputs(example_projects()[example])}
            self.assertNotIn("steps", eligible)
            self.assertFalse(any("numerical_tolerance" in identity for identity in eligible))
            self.assertNotIn("assessment_start", eligible)

    def test_shared_criterion_id_excluded_even_when_model_bound(self):
        project = deepcopy(self.project)
        project["requirements"][0]["limit_input"] = "thrust"
        self.assertNotIn("thrust", {row["input_id"] for row in studies.eligible_inputs(project)})

    def test_invalid_grid_shapes_values_and_case_limits_before_solver(self):
        invalid = [spec(("relative_speed", 1, 1, 2)), spec(("relative_speed", 2, 1, 2)),
                   spec(("relative_speed", 0, 1, True)), spec(("relative_speed", 0, 1, 2.0)),
                   spec(("relative_speed", 0, 1, 10)), spec(("relative_speed", False, 1, 2)),
                   spec(("relative_speed", 0, float("inf"), 2)), spec(("relative_speed", 0, 10**400, 2)),
                   spec(("relative_speed", 2**53, 2**53 + 2, 2)), spec(("relative_speed", 0, float(2**53), 2)),
                   spec(("relative_speed", 1, 1.0000000000000002, 3)),
                   spec(("relative_speed", 0, 1, 5), ("heat_input", 0, 1, 4)),
                   spec(("relative_speed", 0, 1, 2), ("relative_speed", 2, 3, 2)),
                   {**spec(), "axes": []}, {**spec(), "unknown": 1}]
        for value in invalid:
            with self.subTest(spec=str(value)[:100]), patch.object(studies, "evaluate_models", side_effect=AssertionError("No solver")):
                with self.assertRaises(WorkspaceError):
                    self.run_study(value)

    def test_large_opposite_signed_grid_retains_exact_endpoints(self):
        normalized, axes = studies._grid(spec(("relative_speed", -1e15, 1e15, 3)), self.project)
        self.assertEqual(axes[0]["values"], [-1e15, 0, 1e15])
        self.assertEqual(len(studies._cases(normalized)), 3)

    def test_shared_numerical_criterion_id_is_globally_frozen(self):
        project = example_projects()["baseline"]
        project["models"].append({"id": "controller", "type": "attitude_control", "inputs": {"steps": "thrust", "angle_numerical_tolerance": "relative_speed"}})
        eligible = {row["input_id"] for row in studies.eligible_inputs(project)}
        self.assertNotIn("thrust", eligible)
        self.assertNotIn("relative_speed", eligible)

    def test_history_snapshot_and_reopen_never_run_solvers(self):
        result = self.run_study()
        identity = result["receipt"]["study_id"]
        with patch.object(studies, "evaluate_models", side_effect=AssertionError("No solver")), \
                patch.object(studies, "evaluate_model", side_effect=AssertionError("No solver")):
            reopened = studies.WorkspaceScenarios(WorkspaceStore(self.path))
            self.assertEqual(reopened.get(identity, 1), result)
            snapshot = reopened.envelope_summary(self.identity, 1)
            self.assertEqual(snapshot["studies"], [result])
            self.assertEqual(snapshot["omitted_count"], 0)
            self.assertFalse(snapshot["history_truncated"])
            frozen = dict(snapshot)
            digest = frozen.pop("digest")
            self.assertEqual(_digest(frozen), digest)

    def test_rehashed_summary_or_axes_tampering_is_rejected(self):
        original = self.run_study()["receipt"]
        for mutate in (lambda receipt: receipt["envelope_summary"][0].update(status="fabricated"),
                       lambda receipt: receipt["axes"][0]["values"].__setitem__(0, 999)):
            receipt = deepcopy(original)
            mutate(receipt)
            with self.store._connect(write=True) as connection:
                connection.execute("UPDATE scenario_studies SET receipt=?,digest=?", (_encode(receipt), _digest(receipt)))
            with self.assertRaises(WorkspaceError):
                self.service.get(original["study_id"])

    def test_latest_revision_and_current_baseline_required(self):
        self.store.save_revision(self.identity, 1, self.project)
        with self.assertRaises(ConflictError):
            self.run_study()
        with self.assertRaises(ConflictError):
            self.service.preview_envelope(self.identity, 1, self.run_id, spec())
        with self.assertRaises(ConflictError):
            self.service.run(self.identity, 2, self.run_id, spec())

    def test_revision_changed_during_calculation_cannot_commit(self):
        original = studies.evaluate_models
        changed = False
        def calculate(project):
            nonlocal changed
            if not changed:
                self.store.save_revision(self.identity, 1, self.project)
                changed = True
            return original(project)
        with patch.object(studies, "evaluate_models", side_effect=calculate), self.assertRaises(ConflictError):
            self.run_study()
        self.assertEqual(self.service.list(self.identity, 2)["studies"], [])

    def test_baseline_rerun_during_calculation_cannot_commit(self):
        original = studies.evaluate_models
        changed = False
        def calculate(project):
            nonlocal changed
            if not changed:
                self.store.run(self.identity, 1)
                changed = True
            return original(project)
        with patch.object(studies, "evaluate_models", side_effect=calculate), self.assertRaises(ConflictError):
            self.run_study()
        self.assertEqual(self.service.list(self.identity, 1)["studies"], [])

    def test_snapshot_history_bound_and_historical_labels(self):
        original = self.run_study()["receipt"]
        with self.store._connect(write=True) as connection:
            for index in range(20):
                receipt = deepcopy(original)
                receipt["study_id"] = format(index, "032x")
                connection.execute("INSERT INTO scenario_studies (study_id,project_id,revision,created_at,receipt,digest) VALUES (?,?,?,?,?,?)",
                    (receipt["study_id"], self.identity, 1, receipt["created_at"], _encode(receipt), _digest(receipt)))
        self.store.save_revision(self.identity, 1, self.project)
        with patch.object(studies, "evaluate_models", side_effect=AssertionError("No solver")):
            snapshot = self.service.envelope_summary(self.identity, 2)
        self.assertEqual(len(snapshot["studies"]), 20)
        self.assertEqual(snapshot["omitted_count"], 1)
        self.assertTrue(snapshot["history_truncated"])
        self.assertTrue(all(row["freshness"]["historical"] for row in snapshot["studies"]))

    def test_budget_blocks_preview_and_execution_without_solver(self):
        project = example_projects()["orbital_review"]
        self.store.create_project(project)
        view = self.store.run(project["project_id"], 1)
        value = spec(("duration_s", 100, 200, 9))
        with patch.object(studies, "MAX_SAMPLES", 1), patch.object(studies, "evaluate_models", side_effect=AssertionError("No solver")):
            with self.assertRaises(WorkspaceError):
                self.service.preview_envelope(project["project_id"], 1, view["run"]["run_id"], value)
            with self.assertRaises(WorkspaceError):
                self.service.run(project["project_id"], 1, view["run"]["run_id"], value)

    def test_legacy_scenario_scope_is_retained_and_absent_from_envelope_exports(self):
        value = {"schema": "sixd.scenario-spec.v1", "name": "Legacy", "source": "Constructed assumptions", "mode": "sweep", "input_id": "maximum_temperature", "values": [100, 400]}
        result = self.run_study(value)
        self.assertEqual(result["receipt"]["schema"], studies.SCHEMA)
        self.assertEqual(result["receipt"]["limitations"], studies.LIMITATIONS)
        self.assertNotIn("envelope_summary", result["receipt"])
        self.assertEqual(self.service.get(result["receipt"]["study_id"]), result)
        self.assertEqual(self.service.envelope_summary(self.identity, 1)["studies"], [])

    def test_export_size_omits_whole_receipts_with_explicit_count(self):
        self.run_study()
        with patch.object(studies, "MAX_RECEIPT_BYTES", 2048):
            snapshot = self.service.envelope_summary(self.identity, 1)
        self.assertEqual(snapshot["studies"], [])
        self.assertEqual(snapshot["omitted_count"], 1)
        self.assertTrue(snapshot["history_truncated"])


if __name__ == "__main__":
    unittest.main()
