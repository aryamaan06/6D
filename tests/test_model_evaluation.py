"""Constructed comparison packs preserve evidence and never enable from fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import model_evaluation as evaluation
from sixd.explanation_quality import evaluate_explanation
from sixd.providers import ProviderError, Turn


class EvidenceFixture:
    mode = "offline_evidence_fixture"

    def __init__(self, candidate, *, fail=False, omit_changes=False):
        self.model = "fixture-for-" + candidate["id"]
        self.request_attempts = 0
        self.fail, self.omit_changes = fail, omit_changes
        self.config = SimpleNamespace(**candidate["settings"])
        self.histories = []

    def complete(self, messages, tools):
        self.histories.append(deepcopy({"messages": messages, "tools": tools}))
        self.request_attempts += 1
        if self.fail:
            raise RuntimeError("Private remote error is not evidence.")
        names = [tool["function"]["name"] for tool in tools]
        priority = ["read_requirement", "read_model", "recheck_model", "finish"]
        if not self.omit_changes:
            priority.insert(0, "read_changes")
        action = next(name for name in priority if name in names)
        arguments = {}
        if action == "finish":
            finish = next(tool for tool in tools if tool["function"]["name"] == action)
            ids = finish["function"]["parameters"]["properties"]["evidence_ids"]["items"]["enum"]
            payloads = [json.loads(row["content"]) for row in messages if row["role"] == "tool"]
            requirement = next(item for item in payloads if item["kind"] == "requirement")
            status = requirement["finding"]["status"]
            arguments = {"evidence_ids": ids, "summary": (
                "The recorded requirement is " + status + ". Review the supplied units, assumptions "
                "and missing model evidence before choosing the next engineering check. "
                "This bounded calculation does not establish mission readiness.")}
        return Turn({"role": "assistant", "content": None, "tool_calls": [{
            "id": "fixture-" + str(self.request_attempts), "type": "function",
            "function": {"name": action, "arguments": json.dumps(arguments)},
        }]}, {"prompt_tokens": 13, "completion_tokens": 7, "total_tokens": 20})


class ModelEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scratch = ROOT / "work"
        scratch.mkdir(exist_ok=True)
        cls.directory = tempfile.TemporaryDirectory(dir=scratch)
        cls.plan = evaluation.build_evaluation_plan(temporary_root=cls.directory.name)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_fixed_pack_has_known_independent_results_and_held_out_case(self):
        self.assertTrue(evaluation.validate_evaluation_plan(self.plan))
        self.assertEqual(self.plan["schema"], "sixd.model-evaluation-plan.v2")
        self.assertEqual(len(self.plan["cases"]), 6)
        self.assertEqual({case["expected"]["status"] for case in self.plan["cases"]},
                         {"met", "not_met", "not_assessed"})
        held_out = next(case for case in self.plan["cases"] if case["held_out_variation"])
        self.assertEqual(held_out["id"], "held-out-drag")
        self.assertAlmostEqual(held_out["expected"]["reference_metric"]["value"], 286.0344459, places=6)
        hot = next(case for case in self.plan["cases"] if case["id"] == "thermal-exceeded")
        expected_temperature = (700 / (0.8 * 5.670374419e-8) + 3 ** 4) ** 0.25
        self.assertAlmostEqual(hot["expected"]["reference_metric"]["value"], expected_temperature, places=10)
        self.assertGreater(expected_temperature, 320)

    def test_prospective_resource_policy_gives_priced_models_headroom_without_authorizing_spend(self):
        policy = self.plan["budget_policy"]
        self.assertEqual(policy["future_batch_maximum_usd"], 1.50)
        self.assertEqual(policy["max_request_reservations"], 90)
        self.assertEqual(policy["per_case_max_requests"], 6)
        self.assertTrue(policy["existing_ledger_required"])
        self.assertTrue(policy["preflight_against_remaining_allowance_required"])
        self.assertFalse(policy["reset_ledger"])
        self.assertFalse(policy["live_requests_enabled_by_plan"])
        self.assertEqual({c["id"]: c["per_case_cap_usd"] for c in self.plan["candidates"]},
                         {"nano": .10, "super": .20, "ultra": .35})
        for case in self.plan["cases"]:
            self.assertEqual(case["expected"]["requires_changes"], case["view"].get("prior_run") is not None)
            self.assertEqual(case["evaluation_policy"], evaluation.CASE_POLICY)

    def test_limit_only_case_preserves_physics_but_changes_criterion(self):
        case = next(case for case in self.plan["cases"] if case["id"] == "limit-only-change")
        old, new = case["view"]["prior_run"]["review"], case["view"]["run"]["review"]
        self.assertEqual(old["findings"]["thermal_limit"]["status"], "met")
        self.assertEqual(new["findings"]["thermal_limit"]["status"], "not_met")
        self.assertEqual(old["evidence"]["thermal"]["metrics"], new["evidence"]["thermal"]["metrics"])
        self.assertEqual(case["view"]["run"]["executed_model_ids"], [])
        self.assertIn("thermal", case["view"]["run"]["reused_model_ids"])

    def test_same_evidence_questions_tools_settings_reach_every_candidate(self):
        seen = {}

        def factory(candidate, case):
            provider = EvidenceFixture(candidate)
            seen[(candidate["id"], case["id"])] = (deepcopy(candidate), deepcopy(case), provider)
            return provider

        original = deepcopy(self.plan)
        report = evaluation.run_offline_comparison(self.plan, factory, quality_evaluator=evaluate_explanation)
        self.assertEqual(len(report["rows"]), 18)
        self.assertEqual(self.plan, original)
        for case in self.plan["cases"]:
            nano = seen[("nano", case["id"])]
            for name in ("super", "ultra"):
                other = seen[(name, case["id"])]
                self.assertEqual(nano[0]["settings"], other[0]["settings"])
                self.assertEqual(nano[1], other[1])
                self.assertEqual(nano[2].histories, other[2].histories)
        self.assertTrue(all(row["score"]["workflow_gate_pass"] for row in report["rows"]))
        self.assertTrue(all(row["score"]["quality_checks"]["semantic_accuracy_established"] is False
                            for row in report["rows"]))
        self.assertEqual(report["live_calls"], 0)
        self.assertEqual(report["enabled_models"], [])
        self.assertIsNone(report["winner"])
        self.assertFalse(report["active_model_changed"])
        self.assertTrue(all(row["billed_cost_usd"] is None for row in report["rows"]))

    def test_fixture_gates_do_not_claim_prose_is_semantically_correct(self):
        report = evaluation.run_offline_comparison(self.plan, lambda candidate, case: EvidenceFixture(candidate))
        score = report["rows"][0]["score"]
        self.assertEqual(score["citation_identifier_precision"], 1.0)
        self.assertEqual(score["prose_status_correctness"], "manual_review_required")
        self.assertEqual(score["unsupported_claims"], "manual_review_required")
        self.assertEqual(score["next_steps_usefulness"], "manual_review_required")
        for candidate in ("nano", "super", "ultra"):
            self.assertFalse(evaluation.candidate_selection_gate(report, candidate, manual_review={"pass": True})["eligible"])

    def test_offline_runner_rejects_live_provider_before_request(self):
        provider = EvidenceFixture({"id": "nano", "settings": evaluation.SETTINGS})
        provider.mode = "live_token_factory"
        with self.assertRaisesRegex(ValueError, "offline providers"):
            evaluation.run_offline_comparison(self.plan, lambda candidate, case: provider)
        self.assertEqual(provider.request_attempts, 0)

    def test_mismatched_live_model_or_settings_cannot_send(self):
        candidate = {**evaluation.CANDIDATES[0], "settings": evaluation.SETTINGS}
        for mutation in ("model", "settings"):
            provider = EvidenceFixture(candidate)
            provider.mode = "live_token_factory"
            provider.model = candidate["model"] if mutation == "settings" else "wrong-model"
            if mutation == "settings":
                provider.config.max_output_tokens = 8192
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                evaluation.run_comparison(self.plan, lambda candidate, case: provider, mode="live")
            self.assertEqual(provider.request_attempts, 0)

    def test_failed_candidate_stops_without_retry_or_fallback(self):
        attempts = []

        def factory(candidate, case):
            attempts.append((candidate["id"], case["id"]))
            return EvidenceFixture(candidate, fail=candidate["id"] == "super")

        report = evaluation.run_offline_comparison(self.plan, factory)
        super_rows = [row for row in report["rows"] if row["candidate_id"] == "super"]
        self.assertEqual([row["state"] for row in super_rows], ["failed"] + ["not_run"] * 5)
        self.assertEqual(len([row for row in attempts if row[0] == "super"]), 1)
        self.assertEqual(len(attempts), 13)
        self.assertNotIn("Private remote error", json.dumps(report))

    def test_factory_failure_is_sanitized_and_candidate_rest_skipped(self):
        def factory(candidate, case):
            raise RuntimeError("secret-key-and-arbitrary-response")

        report = evaluation.run_offline_comparison(self.plan, factory)
        self.assertEqual(sum(row["state"] == "failed" for row in report["rows"]), 3)
        self.assertNotIn("secret-key", json.dumps(report))
        self.assertEqual(report["live_calls"], 0)

    def test_factory_controlled_failure_code_is_retained_without_private_text(self):
        def factory(candidate, case):
            raise ProviderError("private-key-or-provider-text", code="case_budget_exhausted")

        report = evaluation.run_offline_comparison(self.plan, factory)
        attempted = [row for row in report["rows"] if row["state"] == "failed"]
        self.assertEqual(len(attempted), 3)
        self.assertTrue(all(row["error_code"] == "case_budget_exhausted" for row in attempted))
        self.assertNotIn("private-key", json.dumps(report))

    def test_callback_can_stop_entire_batch_after_recording_one_case(self):
        rows = []

        def callback(row):
            rows.append(row)
            return False

        report = evaluation.run_offline_comparison(self.plan,
            lambda candidate, case: EvidenceFixture(candidate), on_case=callback)
        self.assertEqual(len(rows), 1)
        self.assertEqual(report["rows"][0]["state"], "completed")
        self.assertTrue(all(row["state"] == "not_run" for row in report["rows"][1:]))

    def test_only_real_prior_revision_requires_a_change_read(self):
        report = evaluation.run_offline_comparison(self.plan,
            lambda candidate, case: EvidenceFixture(candidate, omit_changes=True))
        attempted = [row for row in report["rows"] if row["state"] != "not_run"]
        for row in attempted:
            if row["case_id"] == "limit-only-change":
                self.assertFalse(row["score"]["workflow_gate_pass"])
                self.assertFalse(row["score"]["checks"]["changes_read"])
            else:
                self.assertEqual(row["state"], "completed")
                self.assertTrue(row["score"]["workflow_gate_pass"])

    def test_v1_case_retains_original_first_revision_scoring(self):
        report = evaluation.run_offline_comparison(self.plan,
            lambda candidate, case: EvidenceFixture(candidate, omit_changes=True))
        row = report["rows"][0]
        old_case = deepcopy(self.plan["cases"][0])
        old_case.pop("evaluation_policy")
        old_case["expected"]["requires_changes"] = True
        old_score = evaluation.score_receipt(old_case, row["receipt"])
        self.assertFalse(old_score["checks"]["changes_read"])
        self.assertFalse(old_score["workflow_gate_pass"])
        self.assertNotIn("relevant_changes_cited", old_score["checks"])
        self.assertTrue(row["score"]["workflow_gate_pass"])

    def test_actual_revision_comparison_must_match_and_be_cited(self):
        report = evaluation.run_offline_comparison(self.plan, lambda candidate, case: EvidenceFixture(candidate))
        case = next(case for case in self.plan["cases"] if case["id"] == "limit-only-change")
        receipt = deepcopy(next(row["receipt"] for row in report["rows"] if row["case_id"] == case["id"]))
        self.assertTrue(evaluation.score_receipt(case, receipt)["workflow_gate_pass"])
        self.assertEqual(evaluation.score_receipt(case, receipt)["revision_change_explained"], "manual_review_required")
        receipt["citations"].remove("changes")
        self.assertFalse(evaluation.score_receipt(case, receipt)["checks"]["relevant_changes_cited"])
        receipt["citations"].append("changes")
        receipt["evidence"]["changes"]["comparison"]["changed_inputs"] = ["heat_input"]
        self.assertFalse(evaluation.score_receipt(case, receipt)["checks"]["scoped_changes_correct"])

    def test_mutated_case_rejected_before_provider_constructed(self):
        changed = deepcopy(self.plan)
        changed["cases"][0]["view"]["project"]["inputs"]["heat_input"]["value"] = 999
        factories = []
        with self.assertRaises(ValueError):
            evaluation.run_offline_comparison(changed, lambda *args: factories.append(args))
        self.assertEqual(factories, [])

    def test_artifacts_append_only_and_ui_summary_no_receipts(self):
        summary = evaluation.evaluation_summary(self.plan)
        self.assertNotIn("view", summary["cases"][0])
        self.assertFalse(summary["budget_policy"]["live_requests_enabled_by_plan"])
        self.assertEqual(summary["metadata"]["observed_at"], "2026-10-15")
        destination = Path(self.directory.name) / "prepared-plan.json"
        evaluation.write_evaluation_artifact(destination, self.plan)
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), self.plan)
        with self.assertRaises(FileExistsError):
            evaluation.write_evaluation_artifact(destination, self.plan)
        with self.assertRaises(ValueError):
            evaluation.write_evaluation_artifact(Path(self.directory.name) / "wrong.json", {"api_key": "no"})

    def test_accepted_usage_is_recorded_without_claiming_billed_cost(self):
        report = evaluation.run_offline_comparison(self.plan, lambda candidate, case: EvidenceFixture(candidate))
        row = report["rows"][0]
        self.assertEqual(row["receipt"]["accepted_responses"], 5)
        self.assertEqual(row["usage"], {"prompt_tokens": 65, "completion_tokens": 35, "total_tokens": 100})
        self.assertEqual(row["usage_coverage"], "accepted_responses_only")
        self.assertEqual(len(row["request_digests"]), 5)
        self.assertIsNone(row["reserved_usd"])
        self.assertIsNone(row["billed_cost_usd"])

    def test_manual_gate_requires_complete_paired_live_provenance_and_bound_review(self):
        # Fabricated live-labelled fixture records test gate logic only. They are
        # never persisted or represented as actual model-performance evidence.
        report = evaluation.run_offline_comparison(self.plan, lambda c, case: EvidenceFixture(c))
        report["mode"] = "live_comparison"
        for row in report["rows"]:
            row.update(provider_mode="live_token_factory", live_model_calls=5,
                       actual_provider_model=row["proposed_model"], request_reservations=5, reserved_usd=.01)
        def seal(value):
            value["report_digest"] = evaluation._digest({k: v for k, v in value.items() if k != "report_digest"})
        seal(report)
        ids = [c["id"] for c in self.plan["cases"]]
        baseline = report["rows"][0]
        review = {"schema": "sixd.model-manual-review.v2", "report_digest": report["report_digest"],
                  "plan_digest": self.plan["plan_digest"], "candidate_id": "super", "reviewer": "test fixture",
                  "reviewed_at": "2026-10-16T00:00:00Z", "reviewed_case_ids": ids,
                  "no_critical_unsupported_claims": True,
                  "paired_benefit": {"baseline_candidate_id": "nano", "demonstrated": True,
                                     "case_ids": [ids[0]], "rationale": "Synthetic gate-test assertion only."},
                  "baseline_case_reviews": [{"case_id": ids[0], "outcome": "completed",
                    "receipt_digest": evaluation._digest(baseline["receipt"]),
                    "comparison_supports_benefit": True, "notes": "Synthetic paired baseline judgment."}],
                  "case_reviews": [{"case_id": i, "canonical_status_correct": True, "claims_supported": True,
                                    "next_steps_useful": True, "revision_change_explained": True,
                                    "notes": "Synthetic gate-test judgment."} for i in ids]}
        self.assertFalse(evaluation.candidate_selection_gate(report, "super", plan=self.plan)["eligible"])
        self.assertTrue(evaluation.candidate_selection_gate(report, "super", plan=self.plan, manual_review=review)["eligible"])
        self.assertFalse(evaluation.candidate_selection_gate(report, "super", plan=self.plan, manual_review=review)["enable"])
        for mutation in ("missing_case", "offline", "bad_digest", "wrong_model", "bad_review", "no_benefit", "old_report_schema",
                         "revision_unexplained", "baseline_digest", "baseline_review_missing"):
            changed, judgment = deepcopy(report), deepcopy(review)
            if mutation == "missing_case": changed["rows"].pop()
            elif mutation == "offline": changed["mode"] = "offline_harness_validation"
            elif mutation == "bad_digest": changed["rows"][0]["case_digest"] = "bad"
            elif mutation == "wrong_model": changed["rows"][6]["actual_provider_model"] = "wrong"
            elif mutation == "old_report_schema": changed["schema"] = evaluation.LEGACY_REPORT_SCHEMA
            elif mutation == "bad_review": judgment["case_reviews"][0]["claims_supported"] = False
            elif mutation == "revision_unexplained": judgment["case_reviews"][4]["revision_change_explained"] = False
            elif mutation == "baseline_digest": judgment["baseline_case_reviews"][0]["receipt_digest"] = "bad"
            elif mutation == "baseline_review_missing": judgment["baseline_case_reviews"] = []
            else: judgment["paired_benefit"]["demonstrated"] = False
            seal(changed)
            judgment["report_digest"] = changed["report_digest"]
            with self.subTest(mutation=mutation):
                self.assertFalse(evaluation.candidate_selection_gate(changed, "super", plan=self.plan, manual_review=judgment)["eligible"])

        # A fully passing candidate can be useful precisely because the baseline
        # failed the same case. Require the observed failure receipt and explicit
        # attribution, rather than requiring the failing baseline to pass first.
        failed_report, failed_review = deepcopy(report), deepcopy(review)
        baseline = failed_report["rows"][0]
        baseline["state"] = baseline["receipt"]["state"] = "failed"
        baseline["receipt"].update(error_code="invalid_action_response", error="Controlled fixture protocol failure.")
        baseline["score"] = evaluation.score_receipt(self.plan["cases"][0], baseline["receipt"])
        failed_review["baseline_case_reviews"][0].update(
            outcome="failed", failure_reviewed=True, failure_attribution="model_protocol",
            receipt_digest=evaluation._digest(baseline["receipt"]))
        # Later Nano cases may be unattempted after the failure; none is used as
        # evidence for the documented paired benefit on this attempted case.
        for row in failed_report["rows"][1:6]:
            row.update(state="not_run", receipt=None, score=None, live_model_calls=0,
                       request_reservations=0, reserved_usd=0)
        seal(failed_report)
        failed_review["report_digest"] = failed_report["report_digest"]
        self.assertTrue(evaluation.candidate_selection_gate(failed_report, "super", plan=self.plan,
                                                          manual_review=failed_review)["eligible"])
        for failure in ("case_spending_limit", "transport_error", "request_timeout", "case_budget_exhausted",
                        "batch_budget_exhausted", "cumulative_budget_exhausted", "provider_transport_error",
                        "recheck_mismatch", "configuration_error"):
            budget_report, budget_review = deepcopy(failed_report), deepcopy(failed_review)
            receipt = budget_report["rows"][0]["receipt"]
            receipt["error_code"] = failure
            budget_review["baseline_case_reviews"][0]["receipt_digest"] = evaluation._digest(receipt)
            seal(budget_report)
            budget_review["report_digest"] = budget_report["report_digest"]
            with self.subTest(nonquality_failure=failure):
                self.assertFalse(evaluation.candidate_selection_gate(budget_report, "super", plan=self.plan,
                                                                    manual_review=budget_review)["eligible"])


if __name__ == "__main__":
    unittest.main()
