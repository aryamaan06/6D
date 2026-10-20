"""Scalar chain workflows against independently calculated drag/beam values."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import chains, engineering, lifecycle, project_investigation, test_evidence
from sixd.project_examples import example_projects
from sixd.providers import Turn
from sixd.workspace import WorkspaceStore, WorkspaceError, _digest, _encode
from sixd.workspace_scenarios import WorkspaceScenarios
from sixd.workspace_simulation import WorkspaceSimulation
from sixd.workspace_test_data import WorkspaceTestData


class OfflineChainProvider:
    mode = "offline_transport_fixture"
    model = "offline-chain-evidence-test"

    def __init__(self):
        self.request_attempts = 0
        self.histories = []

    def complete(self, messages, tools):
        self.request_attempts += 1
        self.histories.append(deepcopy(messages))
        available = {tool["function"]["name"]: tool for tool in tools}
        required = json.loads(messages[1]["content"])["required_actions"]
        action = next(name for name in ("read_requirement", "read_model", "read_changes", "recheck_model", "finish")
                      if name in available and (name != "read_changes" or name in required))
        args = {}
        if action == "finish":
            args = {"evidence_ids": available[action]["function"]["parameters"]["properties"]["evidence_ids"]["items"]["enum"],
                    "summary": "The calculated beam criterion is met within the declared static model. Review the explicit aerodynamic force transfer, its direction and load location, beam geometry and material sources. Obtain independent load-case and structural evidence. The source drag criterion remains violated; physical compatibility and full vehicle performance are unassessed."}
        return Turn({"role": "assistant", "content": None, "tool_calls": [
            {"id": "offline-chain-" + str(self.request_attempts), "type": "function",
             "function": {"name": action, "arguments": json.dumps(args)}}]},
            {"prompt_tokens": 10, "completion_tokens": 10})


class ChainIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(temporary.cleanup)
        self.store = WorkspaceStore(Path(temporary.name) / "workspace.sqlite3")
        self.project = example_projects()["chain_review"]
        self.identity = self.project["project_id"]
        self.store.create_project(self.project)
        self.view = self.store.run(self.identity, 1)

    def compare(self):
        service = WorkspaceTestData(self.store)
        result = service.run(self.identity, 1, self.view["run"]["run_id"], {
            "schema": "sixd.test-comparison-spec.v1", "name": "Constructed beam scalar observation",
            "source": "Independently calculated synthetic scalar, not a hardware test", "data_kind": "synthetic",
            "test_conditions": "Declared same static cantilever and applied point-load observable; unverified conditions.",
            "conditions_match": "declared_match", "filename": "beam.csv",
            "csv_text": "id,req,value,unit,tolerance\na,mount_stress,410000,Pa,20000\n",
            "mapping": {"measurement_id": "id", "requirement_id": "req", "value": "value", "unit": "unit", "tolerance": "tolerance"}})
        return service, result

    def test_hypothetical_cases_propagate_values_and_gaps_without_canonical_change(self):
        # .5 * .4 * 10^2 * .5 * 2 = 20 N, then F*2*.01/1e-6 = 400000 Pa.
        self.assertEqual(self.view["run"]["model_results"]["aero"]["metrics"]["drag_force"]["value"], 20)
        self.assertAlmostEqual(self.view["run"]["model_results"]["beam"]["metrics"]["bending_stress"]["value"], 400000)
        service = WorkspaceScenarios(self.store)
        saved = service.run(self.identity, 1, self.view["run"]["run_id"], {
            "schema": "sixd.scenario-spec.v1", "name": "Explicit flow alternatives",
            "source": "Constructed applicability cases", "mode": "alternatives", "cases": [
                {"name": "Same", "changes": {"relative_speed": 10}},
                {"name": "Higher speed", "changes": {"relative_speed": 20}},
                {"name": "Invalid density", "changes": {"density": -1}}]})
        same, faster, invalid = saved["receipt"]["cases"]
        self.assertEqual(same["executed_model_ids"], [])
        self.assertEqual(set(same["reused_model_ids"]), {"aero", "beam", "thermal"})
        self.assertEqual(faster["executed_model_ids"], ["aero", "beam"])
        self.assertEqual(faster["reused_model_ids"], ["thermal"])
        self.assertAlmostEqual(faster["review"]["evidence"]["beam"]["metrics"]["bending_stress"]["value"], 1600000)
        self.assertEqual(faster["review"]["findings"]["mount_stress"]["status"], "not_met")
        self.assertEqual(invalid["review"]["evidence"]["aero"]["status"], "invalid_inputs")
        self.assertEqual(invalid["review"]["evidence"]["beam"]["status"], "not_assessed")
        self.assertEqual(invalid["review"]["findings"]["mount_stress"]["status"], "not_assessed")
        with patch("sixd.engineering.evaluate_model", side_effect=AssertionError("History must not calculate")):
            self.assertEqual(service.get(saved["receipt"]["study_id"]), saved)
            self.assertEqual(self.store.get(self.identity), self.view)

    def test_scenario_receipt_cannot_relabel_transitive_execution_as_reuse(self):
        service = WorkspaceScenarios(self.store)
        detail = service.run(self.identity, 1, self.view["run"]["run_id"], {
            "schema": "sixd.scenario-spec.v1", "name": "Changed flow", "source": "Synthetic",
            "mode": "sweep", "input_id": "relative_speed", "values": [10, 20]})
        receipt = detail["receipt"]
        case = receipt["cases"][1]
        case["executed_model_ids"].remove("beam")
        case["reused_model_ids"].append("beam")
        case["reused_model_origins"]["beam"] = deepcopy(receipt["baseline"]["model_origins"]["beam"])
        with self.store._connect(write=True) as connection:
            connection.execute("UPDATE scenario_studies SET receipt=?,digest=?", (_encode(receipt), _digest(receipt)))
        with self.assertRaises(WorkspaceError):
            service.get(receipt["study_id"])

    def test_linked_numerical_work_allocation_is_bounded_before_execution(self):
        project = example_projects()["orbital_review"]
        orbit = next(model for model in project["models"] if model["id"] == "orbit")
        del orbit["inputs"]["steps"]
        orbit["links"] = {"steps": {"model_id": "placeholder", "metric": "scalar", "unit": "1", "rationale": "Budget-only fixture"}}
        cases = [{"name": str(index), "changes": {"duration_s": index + 1}} for index in range(8)]
        with patch("sixd.engineering.evaluate_models", side_effect=AssertionError("Budget preflight must not calculate")):
            with self.assertRaisesRegex(WorkspaceError, "retained orbital/control samples"):
                WorkspaceScenarios._budget(project, cases, "Synthetic work-bound inputs")
        control = example_projects()["attitude_review"]
        control["inputs"]["steps"]["value"] = 2048
        cases = [{"name": str(index), "changes": {"duration": index + 1}} for index in range(8)]
        with self.assertRaisesRegex(WorkspaceError, "retained orbital/control samples"):
            WorkspaceScenarios._budget(control, cases, "Synthetic work-bound inputs")

    def test_test_applicability_tracks_upstream_assumptions_without_changing_observation(self):
        tests, comparison = self.compare()
        links = test_evidence.TestEvidence(self.store, tests)
        original = comparison["receipt"]["row_results"][0]
        changes = [
            lambda p: p["inputs"]["density"].update(source="Updated density-source assessment"),
            lambda p: next(model for model in p["models"] if model["id"] == "aero").update(description="Updated flow applicability"),
            lambda p: next(model for model in p["models"] if model["id"] == "beam")["links"]["tip_force"].update(rationale="Revised explicit tip-load justification"),
        ]
        for change in changes:
            project = deepcopy(self.project)
            change(project)
            with patch("sixd.engineering.evaluate_models", side_effect=AssertionError("Test linkage must not calculate")):
                row = links.summary(self.identity, 1, project)["comparisons"][0]["rows"][0]
            self.assertEqual(row["applicability"]["status"], "needs_review")
            self.assertEqual({key: value for key, value in row.items() if key != "applicability"}, original)
        self.assertEqual(self.store.get(self.identity), self.view)

    def test_test_context_retains_transitive_bindings_and_rejects_rehashed_mutation(self):
        tests, comparison = self.compare()
        links = test_evidence.TestEvidence(self.store, tests)
        with patch("sixd.engineering.evaluate_model", side_effect=AssertionError("Context must not calculate")):
            context = links.investigation_context(self.identity, 1, "mount_stress", comparison["receipt"]["comparison_id"], 2)
            self.assertTrue(test_evidence.validate_investigation_context(context, self.view, "mount_stress"))
        self.assertEqual(set(context["recorded"]["model"]["calculation_dependencies"]["models"]), {"aero", "beam"})
        self.assertIn("density", context["recorded"]["model"]["input_records"])
        self.assertNotIn("heat_input", context["recorded"]["model"]["input_records"])
        context["recorded"]["model"]["calculation_dependencies"]["models"]["aero"]["description"] = "Tampered source model"
        context["context_digest"] = _digest({key: value for key, value in context.items() if key != "context_digest"})
        with self.assertRaisesRegex(WorkspaceError, "dependency binding"):
            test_evidence.validate_investigation_context(context, self.view, "mount_stress")

    def test_same_numeric_prediction_after_upstream_revision_needs_test_review(self):
        tests, comparison = self.compare()
        links = test_evidence.TestEvidence(self.store, tests)
        project = deepcopy(self.project)
        next(model for model in project["models"] if model["id"] == "aero")["description"] = "New atmosphere applicability assessment"
        self.store.save_revision(self.identity, 1, project)
        current = self.store.run(self.identity, 2)
        self.assertEqual(current["run"]["model_results"]["beam"]["metrics"], self.view["run"]["model_results"]["beam"]["metrics"])
        row = links.summary(self.identity, 2)["comparisons"][0]["rows"][0]
        self.assertEqual(row["applicability"]["status"], "needs_review")
        self.assertEqual(row["prediction_agreement"], comparison["receipt"]["row_results"][0]["prediction_agreement"])
        context = links.investigation_context(self.identity, 2, "mount_stress", comparison["receipt"]["comparison_id"], 2)
        self.assertTrue(test_evidence.validate_investigation_context(context, current, "mount_stress"))

    def test_offline_assistant_rechecks_the_chain_and_exposes_its_boundaries(self):
        provider = OfflineChainProvider()
        with patch.object(project_investigation, "evaluate_models", wraps=engineering.evaluate_models) as calculate:
            receipt = project_investigation.investigate_project(self.view, "mount_stress", "Explain this linked finding.",
                provider, investigation_id="offline-chain")
        self.assertEqual(receipt["state"], "completed", receipt)
        self.assertEqual(receipt["live_model_calls"], 0)
        self.assertEqual(calculate.call_count, 1)
        self.assertEqual([model["id"] for model in calculate.call_args.args[0]["models"]], ["aero", "beam"])
        recheck = receipt["evidence"]["recheck:beam"]
        self.assertEqual(recheck["executed_model_ids"], ["aero", "beam"])
        self.assertEqual(recheck["matches_saved_results"], {"aero": True, "beam": True})
        self.assertEqual(receipt["evidence"]["model:beam"]["upstream_evidence"]["model_ids"], ["aero"])
        projected = project_investigation._provider_evidence(receipt["evidence"]["model:beam"])
        self.assertNotIn("calculation_inputs", projected["recorded_evidence"])
        self.assertEqual(projected["recorded_evidence"]["calculation_inputs_summary_projection"]["values"]["tip_force"], {"value": 20.0, "unit": "N"})
        self.assertTrue(any(action["id"] == "review_calculation_transfers" for action in receipt["guidance"]["review_actions"]))
        self.assertEqual(self.store.get(self.identity), self.view)

    def test_assistant_detects_an_upstream_recheck_mismatch_even_if_target_is_unchanged(self):
        def changed(project):
            result = engineering.evaluate_models(project)
            result["aero"]["metrics"]["drag_force"]["value"] += 1
            return result
        with patch.object(project_investigation, "evaluate_models", side_effect=changed):
            receipt = project_investigation.investigate_project(self.view, "mount_stress", "Explain this linked finding.",
                OfflineChainProvider(), investigation_id="offline-chain-mismatch")
        self.assertEqual(receipt["state"], "failed")
        self.assertEqual(receipt["error_code"], "recheck_mismatch")
        self.assertEqual(receipt["evidence"]["recheck:beam"]["matches_saved_results"], {"aero": False, "beam": True})

    def test_scoped_change_evidence_retains_upstream_model_assumption_changes(self):
        old = self.view["run"]["review"]
        project = deepcopy(self.project)
        next(model for model in project["models"] if model["id"] == "aero")["description"] = "Revised source assumption"
        new = lifecycle.review_project(project, engineering.evaluate_models(project))
        changes = project_investigation._scoped_changes(old, new, "mount_stress", "beam")
        self.assertIn("aero", changes["changed_models"])
        self.assertEqual(changes["scope"]["upstream_model_ids"], ["aero"])
        self.assertEqual(set(changes["after"]["model_definitions"]), {"aero", "beam"})

    def test_provider_projection_bounds_upstream_records_and_retains_digest(self):
        records = {"source-" + str(index): {"model_id": "source-" + str(index), "description": "supplied"} for index in range(20)}
        upstream = {"schema": "sixd.investigation-upstream-evidence.v1", "model_ids": list(records), "models": records}
        projected = project_investigation._provider_evidence({"upstream_evidence": upstream})["upstream_evidence"]
        self.assertEqual(len(projected["models"]), 12)
        self.assertEqual(projected["projection"]["omitted_model_count"], 8)
        self.assertEqual(projected["projection"]["captured_digest"], _digest(upstream))
        self.assertEqual(len(upstream["models"]), 20)

    def test_project_playback_retains_explicit_resolved_scalar_roles_without_recalculation(self):
        project = example_projects()["orbital_review"]
        base = example_projects()["baseline"]
        propulsion = deepcopy(next(model for model in base["models"] if model["id"] == "propulsion"))
        project["inputs"].update({identity: deepcopy(base["inputs"][identity]) for identity in propulsion["inputs"].values()})
        project["inputs"]["steps"]["value"] = 512
        project["models"].append(propulsion)
        orbit = next(model for model in project["models"] if model["id"] == "orbit")
        del orbit["inputs"]["duration_s"]
        orbit["links"] = {"duration_s": {"model_id": "propulsion", "metric": "burn_duration", "unit": "s",
            "rationale": "Use the ideal burn duration only as an explicitly chosen coast observation window. No thrust is applied to the orbit."}}
        self.store.create_project(project)
        view = self.store.run(project["project_id"], 1)
        self.assertEqual(view["run"]["model_results"]["orbit"]["status"], "completed")
        service = WorkspaceSimulation(self.store)
        identity = service.project_identity(view["run"]["run_id"], "orbit")
        with patch("sixd.engineering.evaluate_model", side_effect=AssertionError("Playback must not calculate")):
            playback = service.get(identity)
        receipt = playback["receipt"]
        self.assertEqual(receipt["calculation_inputs"], view["run"]["model_results"]["orbit"]["calculation_inputs"])
        self.assertEqual(receipt["spec"]["duration_s"], view["run"]["model_results"]["propulsion"]["metrics"]["burn_duration"]["value"])
        self.assertIn("do not create a coupled time simulation", receipt["binding_note"])


if __name__ == "__main__":
    unittest.main()
