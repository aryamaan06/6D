"""Reviewed model wiring, using isolated synthetic proof fixtures only.

No fixture in this module is actual model-performance evidence. Positive-path
records deliberately relabel offline receipts solely to test the host's gate
wiring. They exist only in temporary databases, never the founder's data.
"""
from contextlib import closing
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from test_model_evaluation import EvidenceFixture
from test_workspace_ai_api import offline_factory
from sixd import model_evaluation as evaluation
from sixd.providers import BudgetLedger, LiveConfig, ProviderError
from sixd.workspace import WorkspaceStore
from sixd.workspace_ai import WorkspaceAI, _digest, _encode
from sixd.workspace_evaluation import WorkspaceEvaluation


KEY = "synthetic-selection-test-key-no-network"
COMPARISON = "a" * 32


class WorkspaceModelSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "work").mkdir(exist_ok=True)
        cls.scratch = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.plan = evaluation.build_evaluation_plan(temporary_root=cls.scratch.name)
        cls.offline_report = evaluation.run_offline_comparison(
            cls.plan, lambda candidate, _case: EvidenceFixture(candidate))
        # Synthetic gate fixture only: these labels are fabricated, not live
        # inference results or grounds to select a production model.
        cls.synthetic_report = deepcopy(cls.offline_report)
        cls.synthetic_report["mode"] = "live_comparison"
        for row in cls.synthetic_report["rows"]:
            row.update(provider_mode="live_token_factory", live_model_calls=5,
                       actual_provider_model=row["proposed_model"], request_reservations=5,
                       reserved_usd=.01)
        cls.seal_report(cls.synthetic_report)
        ids = [case["id"] for case in cls.plan["cases"]]
        cls.synthetic_review = {
            "schema": "sixd.model-manual-review.v2",
            "report_digest": cls.synthetic_report["report_digest"],
            "plan_digest": cls.plan["plan_digest"], "candidate_id": "super",
            "reviewer": "SYNTHETIC HOST-WIRING TEST ONLY",
            "reviewed_at": "2026-10-16T00:00:00Z", "reviewed_case_ids": ids,
            "no_critical_unsupported_claims": True,
            "paired_benefit": {"baseline_candidate_id": "nano", "demonstrated": True,
                               "case_ids": [ids[0]],
                               "rationale": "Fabricated test assertion; no actual performance claim."},
            "baseline_case_reviews": [{
                "case_id": ids[0], "outcome": "completed",
                "receipt_digest": evaluation._digest(cls.synthetic_report["rows"][0]["receipt"]),
                "comparison_supports_benefit": True, "notes": "Synthetic paired judgment only."}],
            "case_reviews": [{"case_id": identity, "canonical_status_correct": True,
                              "claims_supported": True, "next_steps_useful": True,
                              "revision_change_explained": True,
                              "notes": "Synthetic test judgment, not a real review."} for identity in ids],
        }

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    @staticmethod
    def seal_report(report):
        report["report_digest"] = evaluation._digest(
            {key: value for key, value in report.items() if key != "report_digest"})

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.temporary.cleanup)
        self.local = Path(self.temporary.name)
        nano = evaluation.CANDIDATES[0]
        self.base = LiveConfig("https://api.tokenfactory.nebius.com/v1/", nano["model"],
            "synthetic-existing-allowance", 29.5, .06, .24, 2048, 45,
            "native_no_thinking", "forced_action_v1")
        self.config_path = self.local / "token-factory.json"
        self.config_path.write_text(json.dumps({**asdict(self.base), "account_verified": True,
            "model_license_reviewed": True, "spend_approved": True}), encoding="utf-8")
        self.config_bytes = self.config_path.read_bytes()
        BudgetLedger(self.local / "budget.sqlite3").reserve(self.base, .30432376)
        self.providers = []

        def factory(config, ledger, key):
            self.providers.append((config, ledger.max_reservation_usd))
            return offline_factory(config, ledger, key)

        environment = patch.dict("os.environ", {"NEBIUS_API_KEY": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.store = WorkspaceStore(self.local / "workspace.sqlite3")
        self.project_id = self.store.ensure_default()
        self.ai = WorkspaceAI(self.store, self.local, provider_factory=factory)
        WorkspaceEvaluation(self.ai)
        # Other workers may edit application files during isolated async tests.
        # Source-change rejection has its own independent regression cases.
        source_guard = patch.object(self.ai, "_sources", return_value=self.ai._runtime)
        source_guard.start()
        self.addCleanup(source_guard.stop)

    def write_selection(self, **changes):
        value = {"comparison_id": COMPARISON, "candidate_id": "super", **changes}
        (self.local / "project-assistant-model.json").write_text(json.dumps(value), encoding="utf-8")

    def proof(self):
        return {"schema": "sixd.workspace-comparison.v1", "comparison_id": COMPARISON,
                "state": "completed", "plan": deepcopy(self.plan),
                "report": deepcopy(self.synthetic_report),
                "model_reviews": {"super": deepcopy(self.synthetic_review)}}

    def save_proof(self, record, *, digest=None, row_state=None):
        with self.ai._db() as db:
            db.execute("INSERT OR REPLACE INTO model_comparisons VALUES (?,?,?,?,?,?)",
                (COMPARISON, "2026-10-16T00:00:00Z", row_state or record["state"], "synthetic-owner",
                 _encode(record), digest or _digest(record)))

    def assert_fail_closed(self):
        with self.assertRaises(ProviderError) as caught:
            self.ai._config()
        self.assertEqual(caught.exception.code, "configuration_error")
        self.assertIn("no fallback", str(caught.exception))
        self.assertFalse(self.ai.status()["configured"])
        self.assertEqual(self.providers, [])
        self.assertEqual(self.config_path.read_bytes(), self.config_bytes)

    def test_no_selection_preserves_baseline_and_existing_reservations(self):
        selected = self.ai._config()
        self.assertEqual(selected, self.base)
        self.assertEqual(self.ai._job_ceiling(selected), .10)
        self.assertEqual(self.ai._budget(selected)["reserved_usd"], .30432376)
        self.assertEqual(self.providers, [])

    def test_historical_selection_survives_source_updates_without_admitting_stale_investigations(self):
        self.write_selection()
        self.save_proof(self.proof())
        with patch('sixd.project_investigation._runtime_matches', return_value=False):
            selected = self.ai._config()
            self.assertEqual(selected.model, evaluation.CANDIDATES[1]['model'])
            with self.assertRaises(ValueError):
                evaluation.validate_evaluation_plan(self.plan)
        self.assertEqual(self.config_path.read_bytes(), self.config_bytes)
        self.assertEqual(self.providers, [])
        self.assertEqual(self.config_path.read_bytes(), self.config_bytes)

    def test_missing_or_malformed_selection_proof_blocks_without_fallback(self):
        self.write_selection()
        self.assert_fail_closed()
        self.save_proof(self.proof())
        for choice in ({"candidate_id": "nano"}, {"candidate_id": "unknown"},
                       {"comparison_id": "invalid"}, {"unexpected": True}):
            with self.subTest(choice=choice):
                self.write_selection(**choice)
                self.assert_fail_closed()
        (self.local / "project-assistant-model.json").write_text("not-json", encoding="utf-8")
        self.assert_fail_closed()

    def test_digest_tampering_and_missing_or_negative_manual_review_are_rejected(self):
        self.write_selection()
        record = self.proof()
        self.save_proof(record, digest="tampered")
        self.assert_fail_closed()
        for mutation in ("missing_review", "bad_review", "tampered_report", "tampered_plan"):
            record = self.proof()
            if mutation == "missing_review":
                record["model_reviews"] = {}
            elif mutation == "bad_review":
                record["model_reviews"]["super"]["case_reviews"][0]["claims_supported"] = False
            elif mutation == "tampered_report":
                record["report"]["rows"][6]["receipt"]["summary"] = "Changed without resealing report."
            else:
                record["plan"]["cases"][0]["question"] = "Changed without resealing plan."
            with self.subTest(mutation=mutation):
                self.save_proof(record)
                self.assert_fail_closed()

    def test_actual_offline_report_cannot_qualify_even_with_a_synthetic_review(self):
        self.write_selection()
        record = self.proof()
        record["report"] = deepcopy(self.offline_report)
        record["model_reviews"]["super"]["report_digest"] = record["report"]["report_digest"]
        self.save_proof(record)
        self.assert_fail_closed()

    def test_malformed_proof_shapes_and_state_mismatch_fail_with_controlled_error(self):
        self.write_selection()
        for field, value in (("report", None), ("report", []), ("model_reviews", []),
                             ("state", "interrupted")):
            record = self.proof()
            record[field] = value
            with self.subTest(field=field, shape=type(value).__name__):
                self.save_proof(record, row_state="completed")
                self.assert_fail_closed()

    def test_synthetic_qualifying_proof_selects_super_without_mutating_global_config(self):
        self.write_selection()
        record = self.proof()
        # Exercise the actual gate, not a mocked eligibility result. This is
        # still a fabricated positive fixture, never live quality evidence.
        self.assertTrue(evaluation.candidate_selection_gate(record["report"], "super",
            plan=record["plan"], manual_review=record["model_reviews"]["super"])["eligible"])
        self.save_proof(record)
        selected = self.ai._config()
        self.assertEqual(selected.model, evaluation.CANDIDATES[1]["model"])
        self.assertEqual(selected.input_usd_per_million_ceiling, .30)
        self.assertEqual(selected.output_usd_per_million_ceiling, .90)
        self.assertEqual(selected.approval_id, self.base.approval_id)
        self.assertEqual(selected.spend_cap_usd, self.base.spend_cap_usd)
        self.assertEqual(self.ai._job_ceiling(selected), .20)
        self.assertEqual(self.ai._budget(selected)["reserved_usd"], .30432376)
        status = self.ai.status()
        self.assertEqual(status["model"], selected.model)
        self.assertEqual(status["max_job_reservation_usd"], .20)
        self.assertFalse(status["live_validated"])
        self.assertEqual(status["budget"]["cap_usd"], self.base.spend_cap_usd)
        self.assertEqual(self.config_path.read_bytes(), self.config_bytes)
        self.assertEqual(LiveConfig.load(self.config_path), self.base)
        self.assertEqual(self.providers, [])

    def test_invalidated_selected_review_blocks_new_job_without_implicit_nano_fallback(self):
        self.write_selection()
        self.save_proof(self.proof())
        self.ai.connect(KEY)
        record = self.proof()
        record["model_reviews"]["super"]["no_critical_unsupported_claims"] = False
        self.save_proof(record)
        with self.assertRaises(ProviderError):
            self.ai.start(self.project_id, 1, "thermal_limit", "Explain this saved requirement.")
        self.assertEqual(self.providers, [])
        self.assertIsNone(self.ai._active)
        self.assertFalse(self.ai.status()["configured"])
        self.assertEqual(self.config_path.read_bytes(), self.config_bytes)
        with self.ai._db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM project_investigations").fetchone()[0], 0)

    def test_explicit_offline_job_uses_selected_model_price_and_case_ceiling(self):
        self.write_selection()
        self.save_proof(self.proof())
        connected = self.ai.connect(KEY)
        self.assertEqual(connected["max_job_reservation_usd"], .20)
        self.assertEqual(self.providers, [])
        queued = self.ai.start(self.project_id, 1, "thermal_limit", "Explain this saved requirement.")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            receipt = self.ai.get(queued["investigation_id"])
            if receipt["state"] not in {"queued", "running"} and self.ai._active is None:
                break
            time.sleep(.01)
        else:
            self.fail("Isolated offline investigation did not complete.")
        self.assertEqual(receipt["state"], "completed", receipt.get("error"))
        self.assertEqual(receipt["provider_mode"], "offline_transport_fixture")
        self.assertEqual(receipt["live_model_calls"], 0)
        self.assertEqual(receipt["model"], evaluation.CANDIDATES[1]["model"])
        self.assertEqual(len(self.providers), 1)
        config, ceiling = self.providers[0]
        self.assertEqual(ceiling, .20)
        self.assertEqual(config.input_usd_per_million_ceiling, .30)
        self.assertEqual(config.output_usd_per_million_ceiling, .90)
        self.assertLessEqual(receipt["reserved_usd"], .20)
        with closing(sqlite3.connect(self.local / "budget.sqlite3")) as db:
            row = db.execute("SELECT id,cap,reserved FROM budget").fetchone()
        self.assertEqual(row[:2], (self.base.approval_id, self.base.spend_cap_usd))
        self.assertAlmostEqual(row[2], .30432376 + receipt["reserved_usd"])
        self.assertEqual(self.config_path.read_bytes(), self.config_bytes)
        self.assertNotIn(KEY, json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
