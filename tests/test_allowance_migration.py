"""Allowance changes are explicit, bounded, audited and never reset usage."""
from dataclasses import replace
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from sixd.providers import LiveConfig, BudgetLedger, ProviderError, transport_failure
from update_inference_allowance import update_allowance


class AllowanceMigrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(temp.cleanup)
        self.local = Path(temp.name)
        self.config = LiveConfig("https://api.tokenfactory.nebius.com/v1/", "nvidia/offline-nemotron-budget-test",
                                 "unchanged-initial-approval", 5., .06, .24)
        self.ledger = BudgetLedger(self.local / "budget.sqlite3")
        self.ledger.reserve(self.config, .30432376)
        data = {**self.config.__dict__, "account_verified": True, "model_license_reviewed": True, "spend_approved": True}
        (self.local / "token-factory.json").write_text(json.dumps(data), encoding="utf-8")

    def test_explicit_migration_preserves_used_amount_identity_and_audit(self):
        result = update_allowance(self.local, 29.5, "Founder approved existing balance on October 16")
        self.assertEqual(result["reserved_usd"], .30432376)
        self.assertEqual(result["approval_id"], self.config.approval_id)
        changed = LiveConfig.load(self.local / "token-factory.json")
        self.assertEqual(changed, replace(self.config, spend_cap_usd=29.5))
        self.ledger.reserve(changed, .1)
        with closing(sqlite3.connect(self.ledger.path)) as db:
            self.assertAlmostEqual(db.execute("SELECT reserved FROM budget").fetchone()[0], .40432376)
            self.assertEqual(db.execute("SELECT old_cap,new_cap,reserved FROM allowance_changes").fetchone(), (5., 29.5, .30432376))
        with self.assertRaises(ProviderError):
            self.ledger.reserve(self.config, .1)

    def test_invalid_increases_do_not_change_ledger_or_configuration(self):
        before = (self.local / "token-factory.json").read_bytes()
        for cap in (True, 5, 4, 64, float("nan"), float("inf")):
            with self.subTest(cap=cap), self.assertRaises(ProviderError):
                update_allowance(self.local, cap, "explicit test authorization")
        self.assertEqual(before, (self.local / "token-factory.json").read_bytes())
        with closing(sqlite3.connect(self.ledger.path)) as db:
            self.assertEqual(db.execute("SELECT cap,reserved FROM budget").fetchone(), (5., .30432376))

    def test_missing_authorization_and_changed_approval_cannot_migrate(self):
        for config, authorization in ((self.config, ""), (replace(self.config, approval_id="new-id"), "approved")):
            with self.assertRaises(ProviderError):
                self.ledger.increase_cap(config, 29.5, approved_maximum=29.5, authorization=authorization)
        with closing(sqlite3.connect(self.ledger.path)) as db:
            self.assertEqual(db.execute("SELECT cap,reserved FROM budget").fetchone(), (5., .30432376))

    def test_failed_config_replace_cannot_silently_enable_calls_or_reset_usage(self):
        with patch.object(Path, "replace", side_effect=OSError("controlled replacement failure")):
            with self.assertRaises(OSError):
                update_allowance(self.local, 29.5, "approved test migration")
        self.assertEqual(LiveConfig.load(self.local / "token-factory.json").spend_cap_usd, 5.)
        with self.assertRaises(ProviderError) as caught:
            self.ledger.reserve(self.config, .01)
        self.assertEqual(caught.exception.code, "budget_approval_mismatch")
        with closing(sqlite3.connect(self.ledger.path)) as db:
            self.assertEqual(db.execute("SELECT reserved FROM budget").fetchone()[0], .30432376)

    def test_typed_errors_do_not_accept_arbitrary_codes(self):
        self.assertIsNone(ProviderError("private detail", code="synthetic-secret").code)
        self.assertEqual(transport_failure(TimeoutError()).code, "provider_transport_error")
        with self.assertRaises(ProviderError) as caught:
            self.ledger.reserve(self.config, 5.)
        self.assertEqual(caught.exception.code, "cumulative_budget_exhausted")


if __name__ == "__main__":
    unittest.main()
