"""Remaining-balance approvals preserve earlier reservations and protected keys."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools'), str(ROOT / 'tests')]
from sixd.providers import LiveConfig, BudgetLedger, ProviderError
from sixd.service_credentials import ServiceCredentialStore
from test_service_credentials import FixtureProtection
from update_inference_allowance import update_allowance
from update_search_allowance import update_search_allowance


class BalanceAllowanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.local = Path(self.temp.name)

    def test_inference_approved_remaining_is_not_a_reservation_reset(self):
        cfg = LiveConfig('https://api.tokenfactory.nebius.com/v1/', 'nvidia/synthetic-nemotron',
            'synthetic-balance-approval', 29.5, .06, .24)
        (self.local / 'token-factory.json').write_text(json.dumps({**cfg.__dict__,
            'account_verified': True, 'model_license_reviewed': True, 'spend_approved': True}))
        ledger = BudgetLedger(self.local / 'budget.sqlite3')
        ledger.reserve(cfg, 4.80367468)
        with self.assertRaises(ProviderError):
            update_allowance(self.local, 63.06, 'synthetic approval')
        result = update_allowance(self.local, 63.05367468, 'synthetic approval')
        self.assertAlmostEqual(result['cap_usd'] - result['reserved_usd'], 58.25)
        self.assertEqual(result['approval_id'], cfg.approval_id)
        updated = LiveConfig.load(self.local / 'token-factory.json')
        with self.assertRaises(ProviderError):
            ledger.reserve(updated, 58.250001)
        with closing(sqlite3.connect(ledger.path)) as db:
            self.assertEqual(db.execute('SELECT cap,reserved FROM budget').fetchone(), (63.05367468, 4.80367468))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM allowance_changes').fetchone()[0], 1)

    def test_tavily_restores_larger_settings_with_same_key_and_request_history(self):
        store = ServiceCredentialStore(self.local / 'credentials/tavily.dpapi',
            service='tavily', protection=FixtureProtection())
        key = 'synthetic-balance-credential-no-network'
        store.save(key, {'credit_limit': 1})
        path = self.local / 'workspace.sqlite3'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE project_research_versions(search_id TEXT,version INTEGER)')
            db.executemany('INSERT INTO project_research_versions VALUES(?,?)', [('old-request', 1), ('old-request', 2)])
        before = path.read_bytes()
        for invalid in (True, 1, 0, 4126, 4125.0):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                update_search_allowance(self.local, invalid, 'synthetic approval', credential_store=store)
        result = update_search_allowance(self.local, 4125, 'synthetic approval', credential_store=store)
        self.assertEqual(result['remaining_credits'], 4124)
        self.assertEqual(result['reserved_credits'], 1)
        self.assertEqual(store.load(), {'key': key, 'settings': {'credit_limit': 4125}})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(result['search_calls_made'], 0)


if __name__ == '__main__':
    unittest.main()
