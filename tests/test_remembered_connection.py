"""Remember/restore tests using synthetic keys and no provider calls."""
from dataclasses import asdict
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
from sixd.credential_store import CredentialStore, CredentialError
from sixd.workspace_ai import WorkspaceAI
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError
from sixd.providers import LiveConfig, BudgetLedger
from test_credential_store import MemoryProtection

KEY = "synthetic-remembered-key-with-no-service-access"
OTHER_KEY = "synthetic-other-session-key-with-no-service-access"


class RememberedConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.store = WorkspaceStore(self.folder / "workspace.sqlite3")
        self.store.ensure_default()
        self.config = LiveConfig("https://api.tokenfactory.nebius.com/v1/", "nvidia/offline-nemotron-remembered-test",
            "remembered-offline-approval", 5, .06, .24, 2048, 45, "native_no_thinking", "forced_action_v1")
        config_path = self.folder / "token-factory.json"
        config_path.write_text(json.dumps({**asdict(self.config), "account_verified": True,
            "model_license_reviewed": True, "spend_approved": True}), encoding="utf-8")
        BudgetLedger(self.folder / "budget.sqlite3").reserve(self.config, .25)
        self.budget_bytes = (self.folder / "budget.sqlite3").read_bytes()
        self.config_bytes = config_path.read_bytes()
        self.saved = CredentialStore(self.folder / "credentials" / "nebius.dpapi", protection=MemoryProtection())
        env = patch.dict(os.environ, {"NEBIUS_API_KEY": ""})
        env.start(); self.addCleanup(env.stop)
        self.provider_calls = []
        self.ai = self.make_ai()

    def factory(self, *args):
        self.provider_calls.append(True)
        raise AssertionError("Connection/restore must never request a provider.")

    def make_ai(self):
        return WorkspaceAI(self.store, self.folder, provider_factory=self.factory, credential_store=self.saved)

    def assert_private_and_preserved(self, *values):
        text = json.dumps(values)
        self.assertNotIn(KEY, text)
        self.assertNotIn(OTHER_KEY, text)
        for path in self.folder.rglob("*"):
            if path.is_file():
                self.assertNotIn(KEY.encode(), path.read_bytes(), str(path))
        self.assertEqual((self.folder / "token-factory.json").read_bytes(), self.config_bytes)
        self.assertEqual((self.folder / "budget.sqlite3").read_bytes(), self.budget_bytes)
        self.assertEqual(self.provider_calls, [])

    def test_opt_in_remembers_restores_without_requests_or_budget_change(self):
        status = self.ai.connect(KEY, remember=True)
        self.assertTrue(status["key_remembered"])
        self.assertEqual(status["key_source"], "remembered")
        reopened = self.make_ai()
        restored = reopened.status()
        self.assertTrue(restored["key_present"])
        self.assertEqual(restored["key_source"], "remembered")
        self.assertEqual(restored["budget"]["reserved_usd"], .25)
        self.assert_private_and_preserved(status, restored)

    def test_default_connection_is_ephemeral_and_explicit_optout_removes_saved(self):
        self.ai.connect(KEY)
        self.assertFalse(self.saved.exists())
        self.assertFalse(self.make_ai().status()["key_present"])
        self.ai.connect(KEY, remember=True)
        result = self.ai.connect(OTHER_KEY, remember=False)
        self.assertFalse(self.saved.exists())
        self.assertEqual(result["key_source"], "session")
        self.assertFalse(self.make_ai().status()["key_present"])
        self.assert_private_and_preserved(result)

    def test_forget_retains_live_session_but_disconnect_removes_saved_and_session(self):
        self.ai.connect(KEY, remember=True)
        forgotten = self.ai.forget_key()
        self.assertTrue(forgotten["key_present"])
        self.assertFalse(forgotten["key_remembered"])
        self.assertEqual(forgotten["key_source"], "session")
        self.assertFalse(self.make_ai().status()["key_present"])
        self.ai.connect(KEY, remember=True)
        disconnected = self.ai.disconnect()
        self.assertFalse(disconnected["key_present"])
        self.assertFalse(disconnected["key_remembered"])
        self.assertFalse(self.make_ai().status()["key_present"])
        self.assert_private_and_preserved(forgotten, disconnected)

    def test_corrupt_or_unreadable_remembered_storage_is_nonfatal_and_private(self):
        self.ai.connect(KEY, remember=True)
        self.saved.path.write_bytes(b"not a saved key")
        status = self.make_ai().status()
        self.assertFalse(status["key_present"])
        self.assertTrue(status["key_remembered"])
        self.assertEqual(status["credential_error"], "credential_data_invalid")
        self.assert_private_and_preserved(status)

    def test_environment_precedence_and_restart_semantics_are_explicit(self):
        self.ai.connect(KEY, remember=True)
        with patch.dict(os.environ, {"NEBIUS_API_KEY": OTHER_KEY}):
            ai = self.make_ai()
            status = ai.status()
            self.assertEqual(status["key_source"], "environment")
            self.assertTrue(status["environment_key_configured"])
            self.assertIn("launch environment", status["note"])
            ai.disconnect()
            self.assertFalse(self.saved.exists())
            self.assertEqual(self.make_ai().status()["key_source"], "environment")
        self.assert_private_and_preserved(status)

    def test_invalid_boolean_and_failed_save_leave_existing_connection_unchanged(self):
        self.ai.connect(KEY)
        for value in (1, 0, "true", None, []):
            with self.subTest(value=value), self.assertRaises(WorkspaceError):
                self.ai.connect(OTHER_KEY, remember=value)
        epoch = self.ai._epoch
        with patch.object(self.saved, "save", side_effect=CredentialError("credential_storage_unavailable")):
            with self.assertRaises(WorkspaceError):
                self.ai.connect(OTHER_KEY, remember=True)
        self.assertEqual(self.ai._epoch, epoch)
        self.assertEqual(self.ai._key, KEY)
        self.assertFalse(self.saved.exists())
        self.assert_private_and_preserved(self.ai.status())

    def test_connection_and_forget_cannot_race_active_job_disconnect_cancels_epoch(self):
        self.ai.connect(KEY, remember=True)
        self.ai._active = "synthetic-active-job"
        with self.assertRaises(ConflictError):
            self.ai.connect(OTHER_KEY, remember=True)
        with self.assertRaises(ConflictError):
            self.ai.forget_key()
        epoch = self.ai._epoch
        status = self.ai.disconnect()
        self.assertEqual(self.ai._epoch, epoch + 1)
        self.assertFalse(status["key_present"])
        self.assertFalse(self.saved.exists())


if __name__ == "__main__":
    unittest.main()
