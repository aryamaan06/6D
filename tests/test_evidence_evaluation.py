"""Nine bounded offline paths are harness evidence, never live model approval."""
from copy import deepcopy
from dataclasses import asdict
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
sys.path.insert(0, str(ROOT / "tests"))
from sixd import evidence_evaluation as evaluation
from sixd.model_evaluation import _digest
from sixd.providers import LiveConfig, ProviderError, TokenFactoryProvider
from sixd.project_investigation import ProjectActionAdapter
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError
from sixd.workspace_ai import WorkspaceAI, _encode
from sixd.workspace_evaluation import BatchBudget
from sixd.workspace_evidence_evaluation import EvidenceEvaluation, comparison_preflight
from sixd.workspace_workflow_evaluation import WorkflowEvaluation
from test_model_evaluation import EvidenceFixture

KEY = "synthetic-evidence-evaluation-key-only"


def offline_transport(request):
    wire = json.loads(request.data)
    menu = json.loads(wire["messages"][-1]["content"])
    names = {item["action"] for item in menu["available_actions"]}
    action = next(name for name in ("read_requirement", "read_model", "read_changes", "recheck_model", "finish") if name in names)
    args = {"action": action, "evidence_ids": menu["recorded_evidence_ids"] if action == "finish" else [],
        "summary": "Inspect the recorded canonical finding and scoped assumptions. Obtain the applicable independent analysis; unassessed evidence remains unresolved." if action == "finish" else ""}
    return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": None,
        "tool_calls": [{"id": "offline-evidence-" + action, "type": "function", "function": {
            "name": "select_next_action", "arguments": json.dumps(args)}}]}}],
        "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25}}


def offline_factory(config, ledger, key):
    return TokenFactoryProvider(config, ledger, api_key=key, transport=offline_transport,
        action_adapter=ProjectActionAdapter())


def write_config(folder):
    config = LiveConfig("https://api.tokenfactory.nebius.com/v1/", "nvidia/offline-nemotron-evidence-test",
        "offline-evidence-tests", 5.0, .06, .24, 2048, 45, "native_no_thinking", "forced_action_v1")
    path = folder / "token-factory.json"
    path.write_text(json.dumps({**asdict(config), "account_verified": True,
        "model_license_reviewed": True, "spend_approved": True}), encoding="utf-8")
    return config


class EvidenceEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "work").mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.plan = evaluation.build_plan(temporary_root=cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_preparation_is_fixed_bounded_and_not_paid_authorization(self):
        self.assertEqual(tuple(case["id"] for case in self.plan["cases"]), evaluation.CASE_IDS)
        self.assertEqual(len(self.plan["cases"]) * len(self.plan["candidates"]), 9)
        self.assertEqual(self.plan["explanation_policy"], "application_roles_v1")
        self.assertTrue(evaluation.validate_plan(self.plan))
        self.assertEqual([c["per_case_cap_usd"] for c in self.plan["candidates"]], [.10, .20, .35])
        self.assertEqual(self.plan["budget_policy"]["batch_cap_usd"], 2)
        self.assertEqual(self.plan["budget_policy"]["max_request_reservations"], 54)
        self.assertFalse(self.plan["budget_policy"]["live_requests_enabled_by_plan"])
        self.assertFalse(self.plan["active_model_changed"])

    def test_every_candidate_receives_identical_locked_evidence_without_semantic_claim(self):
        seen = {}
        def factory(candidate, case):
            seen.setdefault(case["id"], []).append((case["case_digest"], _digest(case["view"])))
            return EvidenceFixture(candidate)
        report = evaluation.run_comparison(self.plan, factory)
        self.assertEqual(len(report["rows"]), 9)
        self.assertTrue(all(len(set(rows)) == 1 and len(rows) == 3 for rows in seen.values()))
        self.assertTrue(all(row["state"] == "completed" for row in report["rows"]),
            [(row["case_id"], (row.get("receipt") or {}).get("error")) for row in report["rows"] if row["state"] != "completed"])
        self.assertTrue(all(row["fact_policy_recorded"] for row in report["rows"]))
        self.assertTrue(all(row["fact_contract_accepted"] for row in report["rows"]))
        self.assertEqual(report["mode"], "offline_harness_validation")
        self.assertEqual(report["live_calls"], 0)
        self.assertFalse(report["independent_human_review"])
        card = evaluation.scorecard(report)
        self.assertFalse(card["semantic_accuracy_established"])
        self.assertTrue(all(row["semantic_review"] == "pending_independent_human_review" for row in card["candidates"]))
        self.assertTrue(all(row["fact_contract_passes"] == 3 for row in card["candidates"]))
        # Generic fixture prose observes the policy but demonstrates no use of
        # numerical references; the separate count must make that visible.
        self.assertTrue(all(row["linked_explanations"] == 0 for row in card["candidates"]))

    def test_failed_candidate_stops_and_keeps_remaining_cases_untested(self):
        invoked = []
        def factory(candidate, case):
            invoked.append((candidate["id"], case["id"]))
            return EvidenceFixture(candidate, fail=candidate["id"] == "ultra")
        report = evaluation.run_comparison(self.plan, factory)
        rows = [row for row in report["rows"] if row["candidate_id"] == "ultra"]
        self.assertEqual([row["state"] for row in rows], ["failed", "not_run", "not_run"])
        self.assertEqual(sum(identity == "ultra" for identity, _ in invoked), 1)
        self.assertFalse(report["active_model_changed"])
        self.assertEqual(evaluation.scorecard(report)["candidates"][-1]["untested"], 2)

    def test_corrupt_or_cross_revision_snapshot_is_rejected_before_provider(self):
        changed = deepcopy(self.plan)
        changed["cases"][1]["view"]["revision"] = 1
        with self.assertRaises(ValueError):
            evaluation.run_comparison(changed, lambda *_: self.fail("No provider creation"))
        with self.assertRaises(ValueError):
            evaluation.scorecard({"schema": evaluation.REPORT_SCHEMA, "report_digest": "bad"})
        with patch("sixd.project_investigation._runtime_matches", return_value=False):
            with self.assertRaises(ValueError):
                evaluation.validate_plan(self.plan)
            self.assertTrue(evaluation.validate_plan(self.plan, require_current_sources=False))

    def test_capacity_forecast_is_offline_and_within_all_enforced_limits(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
            folder = Path(directory)
            result = comparison_preflight(self.plan, write_config(folder))
            self.assertFalse((folder / "budget.sqlite3").exists())
        self.assertTrue(result["fits"], result)
        self.assertEqual(result["live_calls"], 0)
        self.assertEqual(len(result["cases"]), 9)
        self.assertLessEqual(result["request_reservations"], 54)
        self.assertLessEqual(result["forecast_with_headroom_usd"], 2)
        self.assertTrue(all(row["requests"] <= 6 and row["fits_case_cap"] for row in result["cases"]))

    def test_shared_batch_budget_rejects_extra_reservation_before_shared_ledger(self):
        class Shared:
            def __init__(self): self.amounts = []
            def reserve(self, config, amount): self.amounts.append(amount)
        shared = Shared()
        budget = BatchBudget(shared, lambda: None, threading.RLock(), cap_usd=2, max_requests=54)
        budget.reserve(None, 1.99)
        with self.assertRaises(ProviderError): budget.reserve(None, .02)
        self.assertEqual(shared.amounts, [1.99])
        budget.count = 54
        with self.assertRaises(ProviderError): budget.reserve(None, .001)
        self.assertEqual(shared.amounts, [1.99])


class EvidenceEvaluationServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.plan = evaluation.build_plan(temporary_root=cls.temp.name)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        write_config(self.folder)
        self.store = WorkspaceStore(self.folder / "workspace.sqlite3")
        self.ai = WorkspaceAI(self.store, self.folder, provider_factory=offline_factory)
        self.service = EvidenceEvaluation(self.ai)
        self.old = WorkflowEvaluation(self.ai)

    def prepared(self):
        return {"plan": deepcopy(self.plan), "capacity_preflight": {"fits": True, "live_calls": 0}}

    def test_invalid_authorization_and_status_do_not_prepare_or_spend(self):
        self.assertIsNone(self.service.status()["latest"])
        with patch.object(self.service, "prepare", side_effect=AssertionError("No preparation")):
            for amount, allow in [(3, True), (2, False), (True, True), (float("nan"), True)]:
                with self.assertRaises(WorkspaceError): self.service.start(allowance_usd=amount, allow_spend=allow)
        self.assertFalse((self.folder / "budget.sqlite3").exists())

    def test_failed_capacity_or_missing_private_connection_cannot_start(self):
        prepared = self.prepared(); prepared["capacity_preflight"]["fits"] = False
        with patch.object(self.service, "prepare", return_value=prepared):
            with self.assertRaises(ConflictError): self.service.start(allowance_usd=2, allow_spend=True)
        with patch.object(self.service, "prepare", return_value=self.prepared()):
            with self.assertRaises(ConflictError): self.service.start(allowance_usd=2, allow_spend=True)
        self.assertIsNone(self.service.status()["latest"])
        self.assertFalse((self.folder / "budget.sqlite3").exists())

    def test_explicit_offline_batch_preserves_old_history_settings_and_user_projects(self):
        self.ai.connect(KEY)
        before_config = (self.folder / "token-factory.json").read_bytes()
        before_projects = self.store.list_projects()
        # Run the injected offline worker to completion before temporary DB
        # teardown. Thread scheduling is covered by the existing host tests;
        # this test exercises the complete new service/ledger path without a
        # wall-clock timeout that could delete its DB while a fixture runs.
        class InlineWorker:
            def __init__(self, *, target, args, daemon):
                self.target, self.args = target, args
            def start(self): self.target(*self.args)
        with patch.object(self.service, "prepare", return_value=self.prepared()), \
                patch("sixd.workspace_evidence_evaluation.threading.Thread", InlineWorker):
            started = self.service.start(allowance_usd=2, allow_spend=True)
        record = self.service.get(started["comparison_id"])
        self.assertEqual(record["state"], "completed", record)
        self.assertEqual(len(record["report"]["rows"]), 9)
        self.assertEqual(record["report"]["live_calls"], 0)
        self.assertEqual(self.store.list_projects(), before_projects)
        self.assertEqual((self.folder / "token-factory.json").read_bytes(), before_config)
        self.assertIsNone(self.old.status()["latest"])
        self.assertLessEqual(record["reserved_usd"], 2)
        self.assertLessEqual(record["request_reservations"], 54)
        self.assertNotIn(KEY, json.dumps(record))
        self.assertFalse((self.folder / "project-assistant-model.json").exists())
        self.assertIsNone(self.ai._active)
        self.assertFalse(self.service.status()["scorecard"]["active_model_changed"])

    def test_restart_preserves_partial_record_and_does_not_resume(self):
        identity = "e" * 32
        record = {"comparison_id": identity, "state": "running", "created_at": "2026-10-20",
            "report": None, "reserved_usd": .1, "request_reservations": 3}
        with self.ai._db() as db:
            db.execute("INSERT INTO evidence_evaluations VALUES (?,?,?,?,?,?)",
                (identity, "2026-10-20", "running", "old-owner", _encode(record), _digest(record)))
        restarted = EvidenceEvaluation(self.ai)
        saved = restarted.get(identity)
        self.assertEqual(saved["state"], "interrupted")
        self.assertEqual(saved["reserved_usd"], .1)
        self.assertIsNone(self.old.status()["latest"])
        self.assertIsNone(self.ai._active)


if __name__ == "__main__": unittest.main()
