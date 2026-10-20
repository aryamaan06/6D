"""Comparison isolation, shared allowance, cancellation and historical guidance."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from test_workspace_ai_api import KEY, offline_factory, write_offline_config
from sixd.workspace import WorkspaceStore, ConflictError, WorkspaceError
from sixd.workspace_ai import WorkspaceAI, _digest, _encode
from sixd.workspace_evaluation import WorkspaceEvaluation, BatchBudget, comparison_preflight
from sixd.providers import BudgetLedger, ProviderError


class WorkspaceEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        write_offline_config(self.folder)
        self.store = WorkspaceStore(self.folder / "workspace.sqlite3")
        self.ai = WorkspaceAI(self.store, self.folder, provider_factory=offline_factory)
        self.evaluation = WorkspaceEvaluation(self.ai)

    def await_batch(self, identity):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            value = self.evaluation.get(identity)
            if value["state"] not in {"queued", "running"}:
                return value
            time.sleep(.01)
        self.fail("Offline batch did not complete")

    def test_status_and_connect_send_no_requests_or_create_ledger(self):
        for _ in range(3):
            status = self.evaluation.status()
        self.assertEqual(status["stage"], "comparison_pending")
        self.assertEqual([x["enabled"] for x in status["candidates"]], [True, False, False])
        self.ai.connect(KEY)
        self.assertFalse((self.folder / "budget.sqlite3").exists())
        self.assertNotIn(KEY, json.dumps(self.evaluation.status()))

    def test_capacity_preflight_uses_no_real_transport_or_reservation_ledger(self):
        from sixd.model_evaluation import build_evaluation_plan
        with patch("sixd.providers.TokenFactoryProvider._send", side_effect=AssertionError("No real network")):
            result = comparison_preflight(build_evaluation_plan(temporary_root=self.folder), self.ai._config())
        self.assertTrue(result["fits"])
        self.assertEqual(result["live_calls"], 0)
        self.assertEqual(len(result["cases"]), 18)
        self.assertLess(result["forecast_with_headroom_usd"], 1.50)
        self.assertTrue(all(case["fits_case_cap"] for case in result["cases"]))
        self.assertFalse((self.folder / "budget.sqlite3").exists())

    def test_start_needs_explicit_cap_and_private_connection(self):
        for amount, approve in [(1, True), (1.50, False), (True, True), (float("nan"), True)]:
            with self.assertRaises(WorkspaceError):
                self.evaluation.start(allowance_usd=amount, allow_spend=approve)
        with self.assertRaises(ConflictError):
            self.evaluation.start(allowance_usd=1.50, allow_spend=True)

    def test_shared_session_excludes_jobs_and_connection_change(self):
        self.ai.connect(KEY)
        config, key, epoch = self.ai.begin_comparison("a" * 32)
        self.assertEqual(key, KEY)
        with self.assertRaises(ConflictError):
            self.ai.begin_comparison("b" * 32)
        with self.assertRaises(ConflictError):
            self.ai.connect(KEY)
        self.ai.disconnect()
        with self.assertRaises(ProviderError):
            self.ai.check_comparison_session("a" * 32, epoch)
        self.ai.finish_comparison("b" * 32)
        self.assertEqual(self.ai._active, "a" * 32)
        self.ai.finish_comparison("a" * 32)
        self.assertIsNone(self.ai._active)

    def test_batch_allowance_is_shared_across_candidate_prices_and_retained(self):
        config = self.ai._config()
        ledger = BudgetLedger(self.folder / "budget.sqlite3")
        ledger.reserve(config, .02)
        batch = BatchBudget(ledger, lambda: None, threading.RLock())
        ultra = replace(config, output_usd_per_million_ceiling=3, model="nvidia/ultra")
        batch.reserve(config, .8)
        batch.reserve(ultra, .6)
        with self.assertRaises(ProviderError):
            batch.reserve(ultra, .11)
        self.assertAlmostEqual(self.ai._budget(config)["reserved_usd"], 1.42)
        self.assertEqual(batch.count, 2)

    def test_offline_batch_preserves_config_and_project_records(self):
        identity = self.store.ensure_default()
        view = self.store.run(identity, 1)
        before = (self.folder / "token-factory.json").read_bytes()
        self.ai.connect(KEY)
        created = self.evaluation.start(allowance_usd=1.50, allow_spend=True)
        result = self.await_batch(created["comparison_id"])
        self.assertEqual(result["state"], "completed", result.get("error"))
        self.assertEqual(result["report"]["mode"], "offline_harness_validation")
        self.assertEqual(len(result["report"]["rows"]), 18)
        self.assertEqual(result["report"]["live_calls"], 0)
        self.assertEqual(result["report"]["enabled_models"], [])
        self.assertGreater(result["request_reservations"], 0)
        self.assertLessEqual(result["reserved_usd"], 1.50)
        self.assertEqual(before, (self.folder / "token-factory.json").read_bytes())
        self.assertEqual(view, self.store.get(identity, 1))
        self.assertNotIn(KEY, json.dumps(result))

    def test_restart_preserves_interrupted_job_and_does_not_retry(self):
        record = {"comparison_id": "b" * 32, "state": "running", "rows": [{"state": "completed"}]}
        with self.ai._db() as db:
            db.execute("INSERT INTO model_comparisons VALUES (?,?,?,?,?,?)",
                (record["comparison_id"], "2026-10-16", "running", "old", _encode(record), _digest(record)))
        restarted = WorkspaceEvaluation(self.ai)
        saved = restarted.get(record["comparison_id"])
        self.assertEqual(saved["state"], "interrupted")
        self.assertEqual(saved["rows"], record["rows"])
        self.assertFalse((self.folder / "budget.sqlite3").exists())

    def test_historical_guidance_uses_exact_review_and_never_rewrites_receipt(self):
        identity = self.store.ensure_default()
        view = self.store.run(identity, 1)
        from sixd.project_investigation import investigate_project
        from sixd.workspace_ai import JobBudget
        provider = offline_factory(self.ai._config(), JobBudget(BudgetLedger(self.folder / "budget.sqlite3"), check_session=lambda: None), KEY)
        record = investigate_project(view, "control_tracking", "Explain", provider, investigation_id="c" * 32)
        record.pop("guidance", None)
        record.pop("explanation_quality", None)
        record["summary"] = "This unassessed requirement cannot be satisfied."
        with self.ai._db() as db:
            db.execute("INSERT INTO project_investigations VALUES (?,?,?,?,?,?,?,?,?)",
                       (record["investigation_id"], identity, 1, "control_tracking", record["started_at"], record["state"], self.ai.owner, _encode(record), _digest(record)))
        # Rerun the revision: projection must match captured review, not relabel an AI claim.
        self.store.run(identity, 1)
        projected = self.ai.get(record["investigation_id"])
        self.assertEqual(projected["summary"], record["summary"])
        self.assertEqual(projected["guidance_origin"], "current_app_read_only_projection")
        self.assertEqual(projected["guidance"]["scope"]["review_digest"], record["review_digest"])
        self.assertTrue(projected["explanation_quality"]["review_required"])
        with self.ai._db() as db:
            row = db.execute("SELECT * FROM project_investigations WHERE investigation_id=?", (record["investigation_id"],)).fetchone()
            self.assertEqual(self.ai._read(row), record)


if __name__ == "__main__":
    unittest.main()
