"""Selected recorded test evidence stays scoped, frozen and distinct from design.

All providers and keys here are isolated synthetic fixtures; no network or
founder configuration is accessed. The drag reference is hand-calculated.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import project_investigation as engine
from sixd.explanation_quality import evaluate_explanation, explanation_acceptance
from sixd.project_examples import example_projects
from sixd.providers import LiveConfig, Turn
from sixd.test_evidence import TestEvidence
from sixd.workspace import WorkspaceError, WorkspaceStore, _digest
from sixd.workspace_ai import WorkspaceAI
from sixd.workspace_test_data import WorkspaceTestData

MAPPING = {"measurement_id": "id", "requirement_id": "req", "value": "reading", "unit": "units", "tolerance": "tol"}
GOOD = ("The canonical design criterion is met within this bounded model. "
        "The measured criterion is not met against its recorded limit. "
        "The recorded measurement is within tolerance of the saved prediction. "
        "Declared test conditions are unverified. Review calibration, observable definition and model assumptions before attributing a cause.")


class OfflineProvider:
    mode = "offline_transport_fixture"
    model = "nvidia/offline-nemotron-test-evidence-provider"

    def __init__(self, summary=GOOD, *, config=None, budget=None, key=None, entered=None, release=None):
        self.summary, self.config, self.budget, self._key = summary, config, budget, key
        self.entered, self.release = entered, release
        self.request_attempts, self.histories = 0, []

    def complete(self, messages, tools):
        if not self.request_attempts and self.entered:
            self.entered.set()
            if not self.release.wait(5):
                raise AssertionError("Offline test synchronization timed out.")
        if self.budget:
            self.budget.reserve(self.config, .001)
        self.request_attempts += 1
        self.histories.append(deepcopy(messages))
        available = {item["function"]["name"]: item for item in tools}
        required = json.loads(messages[1]["content"])["required_actions"]
        action = next(name for name in ("read_requirement", "read_model", "read_changes", "recheck_model", "finish")
                      if name in available and (name != "read_changes" or name in required))
        args = {}
        if action == "finish":
            # Positive transport fixtures now speak the real numerical-reference
            # contract. Deliberately invented quantities in negative tests stay
            # literal and must still be rejected by both relevant guards.
            catalog = next(json.loads(item["content"])["evidence_facts"] for item in reversed(messages)
                           if item.get("role") == "tool" and "evidence_facts" in json.loads(item["content"]))
            labels = {"design_metric": "Requirement comparison · metric", "design_limit": "Declared limit · limit",
                      "measurement": "Original test row · measurement_requirement · metric",
                      "test_limit": "Original test row · measurement_requirement · limit",
                      "difference": "Original test row · prediction_agreement · absolute_difference",
                      "tolerance": "Original test row · prediction_agreement · tolerance"}
            summary = self.summary
            for name, label in labels.items():
                marker = "{{" + name + "}}"
                if marker in summary:
                    fact = next(fact for fact in catalog["facts"] if fact["label"] == label)
                    summary = summary.replace(marker, "[[fact:" + fact["id"] + "]]")
            args = {"summary": summary, "evidence_ids": available[action]["function"]["parameters"]["properties"]["evidence_ids"]["items"]["enum"]}
        return Turn({"role": "assistant", "content": None, "tool_calls": [{"id": "offline-test-" + str(self.request_attempts),
            "type": "function", "function": {"name": action, "arguments": json.dumps(args)}}]},
            {"prompt_tokens": 10, "completion_tokens": 10})


class TestEvidenceInvestigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.tmp.cleanup)
        self.local = Path(self.tmp.name)
        self.store = WorkspaceStore(self.local / "workspace.sqlite3")
        self.project = example_projects()["baseline"]
        for key, value in {"density": 1.2, "relative_speed": 50, "drag_coefficient": .8,
                           "reference_area": .25, "maximum_drag_force": 305}.items():
            self.project["inputs"][key]["value"] = value
        self.store.create_project(self.project)
        self.identity = self.project["project_id"]
        self.view = self.store.run(self.identity, 1)
        self.tests = WorkspaceTestData(self.store)
        self.links = TestEvidence(self.store, self.tests)
        self.comparison = self.compare()
        self.config = LiveConfig("https://api.tokenfactory.nebius.com/v1/", OfflineProvider.model,
            "isolated-test-evidence-approval", 5.0, .06, .24, 2048, 45, "native_no_thinking", "forced_action_v1")
        (self.local / "token-factory.json").write_text(json.dumps({**self.config.__dict__, "account_verified": True,
            "model_license_reviewed": True, "spend_approved": True}), encoding="utf-8")

    def compare(self, csv_text=None, **changes):
        spec = {"schema": "sixd.test-comparison-spec.v1", "name": "Synthetic selected-row comparison",
                "source": "Constructed arithmetic only", "data_kind": "synthetic", "test_conditions": "Same scalar drag observable and declared baseline conditions.",
                "conditions_match": "declared_match", "filename": "selected.csv", "mapping": deepcopy(MAPPING),
                "csv_text": csv_text or "id,req,reading,units,tol\nselected,drag_limit,310,N,15\nPRIVATE-OTHER-ROW,thermal_limit,290,K,3\n"}
        spec.update(changes)
        return self.tests.run(self.identity, 1, self.view["run"]["run_id"], spec)

    def selected(self, view=None, comparison=None):
        view = deepcopy(view or self.view)
        comparison = comparison or self.comparison
        view["test_evidence"] = self.links.investigation_context(self.identity, view["revision"], "drag_limit", comparison["receipt"]["comparison_id"], 2)
        return view

    def investigate(self, *, view=None, summary=GOOD):
        provider = OfflineProvider(summary)
        receipt = engine.investigate_project(self.selected() if view is None else view, "drag_limit",
            "Explain this recorded test discrepancy.", provider, investigation_id="offline-selected-test")
        return receipt, provider

    def wait(self, manager, identity):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            record = manager.get(identity)
            if record["state"] not in {"queued", "running"} and manager._active is None:
                return record
            threading.Event().wait(.01)
        self.fail("Offline investigation did not settle.")

    def manager(self, **options):
        providers = []
        def factory(config, budget, key):
            provider = OfflineProvider(config=config, budget=budget, key=key, **options)
            providers.append(provider)
            return provider
        with patch.dict("os.environ", {"NEBIUS_API_KEY": ""}):
            manager = WorkspaceAI(self.store, self.local, provider_factory=factory)
        # Root/parallel integration edits must not impersonate a source change.
        guard = patch.object(manager, "_sources", return_value=manager._runtime)
        guard.start()
        self.addCleanup(guard.stop)
        manager.connect("synthetic-private-test-evidence-key")
        return manager, providers

    def test_read_requirement_embeds_one_exact_row_without_extra_action_or_calculation(self):
        before = deepcopy(self.view)
        with patch.object(engine, "evaluate_models", wraps=engine.evaluate_models) as calculate:
            receipt, provider = self.investigate()
        self.assertEqual(receipt["state"], "completed")
        self.assertEqual(receipt["accepted_responses"], 4)
        self.assertEqual(receipt["live_model_calls"], 0)
        self.assertEqual(calculate.call_count, 1)  # Existing reproducibility action only.
        self.assertEqual([m["id"] for m in calculate.call_args.args[0]["models"]], ["atmospheric_load"])
        self.assertEqual(receipt["canonical_finding"]["status"], "met")
        bundle = receipt["test_evidence"]
        self.assertEqual(bundle["recorded"]["row"]["measurement_requirement"]["status"], "not_met")
        self.assertEqual(bundle["recorded"]["row"]["prediction_agreement"]["status"], "within_tolerance")
        self.assertEqual(bundle["selection"]["pointer"], "/row_results/0")
        self.assertEqual(receipt["evidence"]["requirement:drag_limit"]["selected_test_evidence"], bundle)
        self.assertEqual(set(receipt["citations"]), {"requirement:drag_limit", "model:atmospheric_load", "recheck:atmospheric_load"})
        self.assertNotIn("PRIVATE-OTHER-ROW", json.dumps(receipt))
        self.assertNotIn("PRIVATE-OTHER-ROW", json.dumps(provider.histories))
        self.assertNotIn("csv_text", json.dumps(provider.histories))
        self.assertEqual(self.store.get(self.identity, 1), before)
        self.assertFalse(receipt["launch_authorization"])

    def test_clear_measured_pass_and_current_design_failure_remain_separate(self):
        comparison = self.compare("id,req,reading,units,tol\nlow,drag_limit,250,N,1\n")
        changed = deepcopy(self.project)
        changed["inputs"]["maximum_drag_force"]["value"] = 200
        self.store.save_revision(self.identity, 1, changed)
        view = self.store.run(self.identity, 2)
        selected = self.selected(view, comparison)
        receipt, _ = self.investigate(view=selected, summary=(
            "The canonical design criterion is not met against the current limit. "
            "The measured criterion is met against its recorded limit. "
            "The recorded measurement is outside tolerance of the original prediction. Declared test conditions are unverified. "
            "Review calibration and the changed criterion; the historical comparison does not establish current applicability."))
        self.assertEqual(receipt["state"], "completed")
        self.assertEqual(receipt["test_evidence"]["applicability"]["status"], "needs_review")
        self.assertEqual(receipt["test_evidence"]["recorded"]["row"]["measurement_requirement"]["limit"]["value"], 305)
        self.assertEqual(receipt["canonical_finding"]["evidence"]["limit"]["value"], 200)
        self.assertEqual(receipt["accepted_responses"], 5)

    def test_unverified_or_unknown_conditions_remain_a_gap(self):
        comparison = self.compare(conditions_match="unknown")
        receipt, _ = self.investigate(view=self.selected(comparison=comparison), summary=(
            "The canonical design criterion is met only within its bounded scope. The measurement criterion is not assessed. "
            "Prediction agreement is not assessed because conditions are unknown. Declared test conditions are unverified. "
            "Obtain the same observable, test conditions and calibration record before comparing outcomes."))
        self.assertEqual(receipt["state"], "completed")
        self.assertEqual(receipt["test_evidence"]["recorded"]["row"]["measurement_requirement"]["status"], "not_assessed")

    def test_wrong_selected_binding_is_rejected_before_provider(self):
        selected = self.selected()
        for mutate in (lambda b: b.update(project_id="other"), lambda b: b.update(revision=2),
                       lambda b: b["current"].update(run_id="0" * 32),
                       lambda b: b["selection"].update(row_number=True),
                       lambda b: b["recorded"]["row"].update(requirement_id="thermal_limit")):
            invalid = deepcopy(selected)
            mutate(invalid["test_evidence"])
            invalid["test_evidence"]["context_digest"] = _digest({k: v for k, v in invalid["test_evidence"].items() if k != "context_digest"})
            provider = OfflineProvider()
            with self.assertRaises(ValueError):
                engine.investigate_project(invalid, "drag_limit", "Explain.", provider, investigation_id="invalid-context")
            self.assertEqual(provider.request_attempts, 0)

    def test_read_evidence_must_contain_exact_selected_bundle(self):
        receipt, _ = self.investigate()
        receipt["evidence"]["requirement:drag_limit"]["selected_test_evidence"]["selection"]["comparison_id"] = "0" * 32
        self.assertIn("test_evidence_binding_mismatch", explanation_acceptance(receipt)["blocked_codes"])

    def test_cited_context_does_not_equate_boolean_and_numeric_records(self):
        receipt, _ = self.investigate()
        selected = receipt["evidence"]["requirement:drag_limit"]["selected_test_evidence"]
        selected["recorded"]["conditions_declaration_verified"] = 0
        self.assertIn("test_evidence_binding_mismatch", explanation_acceptance(receipt)["blocked_codes"])

    def test_invented_measurement_quantities_and_validation_claims_are_rejected(self):
        for extra, expected in ((" The measurement is 999 N.", "test_evidence_unmatched_quantity"),
                (" This test validates the model.", "test_evidence_validation_claim"),
                (" The hardware is validated.", "test_evidence_validation_claim"),
                (" The discrepancy proves a defect.", "test_evidence_validation_claim"),
                (" This test overrides the canonical finding.", "test_evidence_validation_claim"),
                (" The measured criterion is met, and ready for launch.", "readiness_or_guarantee_claim")):
            with self.subTest(extra=extra):
                receipt, _ = self.investigate(summary=GOOD + extra)
                self.assertEqual(receipt["state"], "failed")
                self.assertEqual(receipt["error_code"], "explanation_rejected")
                self.assertIn(expected, receipt["explanation_acceptance"]["blocked_codes"])

    def test_clear_measured_or_agreement_contradictions_are_rejected(self):
        for summary in (GOOD + " The measured criterion is met.", GOOD + " The measurement is outside tolerance.",
                        GOOD + " Prediction agreement is outside tolerance.", GOOD + " Recorded agreement is not assessed."):
            receipt, _ = self.investigate(summary=summary)
            self.assertEqual(receipt["state"], "failed")
            self.assertIn("test_evidence_status_contradiction", receipt["explanation_acceptance"]["blocked_codes"])

    def test_negated_claims_and_review_questions_do_not_require_fixed_wording(self):
        for extra in (" This test does not validate the model.", " The hardware is not validated.",
                      " The discrepancy does not prove a defect.",
                      " Check whether the recorded measurement is outside tolerance.",
                      " Determine whether prediction agreement is outside tolerance."):
            with self.subTest(extra=extra):
                receipt, _ = self.investigate(summary=GOOD + extra)
                self.assertEqual(receipt["state"], "completed")
                self.assertTrue(receipt["explanation_acceptance"]["accepted"])

    def test_ambiguous_attribution_gets_review_flag_without_forced_wording(self):
        receipt, _ = self.investigate(summary=GOOD + " The design and measurement have different criterion outcomes.")
        self.assertEqual(receipt["state"], "completed")
        quality = evaluate_explanation(receipt)
        self.assertTrue(quality["review_required"])
        self.assertIn("test_evidence_ambiguous_attribution", [f["code"] for f in quality["flags"]])
        self.assertFalse(quality["semantic_accuracy_established"])

    def test_absent_selection_preserves_old_receipt_shape(self):
        receipt, _ = self.investigate(view=deepcopy(self.view), summary="The recorded criterion is met only within model scope. Review its assumptions.")
        self.assertEqual(receipt["state"], "completed")
        self.assertNotIn("test_evidence", receipt)
        self.assertNotIn("selected_test_evidence", receipt["evidence"]["requirement:drag_limit"])

    def test_manager_rejects_invalid_selection_before_job_or_request(self):
        manager, providers = self.manager()
        cid = self.comparison["receipt"]["comparison_id"]
        for selection in ({"test_comparison_id": cid}, {"test_row_number": 2},
                {"test_comparison_id": cid, "test_row_number": True},
                {"test_comparison_id": "0" * 32, "test_row_number": 2},
                {"test_comparison_id": cid, "test_row_number": 3}):
            with self.subTest(selection=selection), self.assertRaises(WorkspaceError):
                manager.start(self.identity, 1, "drag_limit", "Explain.", **selection)
        self.assertEqual(providers, [])
        self.assertFalse((self.local / "budget.sqlite3").exists())
        with self.store._connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM project_investigations").fetchone()[0], 0)

    def test_manager_freezes_selection_and_history_does_not_pull_current_test_data(self):
        manager, providers = self.manager()
        cid = self.comparison["receipt"]["comparison_id"]
        entered, release = threading.Event(), threading.Event()
        run = manager._run
        def delayed_worker(*args):
            entered.set()
            if not release.wait(5):
                raise AssertionError("Offline worker synchronization timed out.")
            run(*args)
        with patch.object(manager, "_run", side_effect=delayed_worker):
            queued = manager.start(self.identity, 1, "drag_limit", "Explain the recorded comparison.", test_comparison_id=cid, test_row_number=2)
            self.assertTrue(entered.wait(5))
            frozen = deepcopy(queued["test_evidence"])
            queued["test_evidence"]["recorded"]["row"]["measurement_id"] = "client-mutated"
            release.set()
        completed = self.wait(manager, queued["investigation_id"])
        self.assertEqual(completed["state"], "completed")
        self.assertEqual(completed["test_evidence"], frozen)
        self.compare("id,req,reading,units,tol\nnewer,drag_limit,500,N,2\n")
        with patch.object(self.links, "investigation_context", side_effect=AssertionError("No new projection in history")), \
                patch("sixd.test_evidence.TestEvidence.investigation_context", side_effect=AssertionError("No new context in history")):
            historical = manager.get(completed["investigation_id"])
            listed = manager.list(self.identity, 1, "drag_limit")
        self.assertEqual(historical["test_evidence"], frozen)
        self.assertEqual(listed[0]["test_evidence"], frozen)
        self.assertEqual(providers[0].request_attempts, 4)
        self.assertAlmostEqual(completed["reserved_usd"], .004)

