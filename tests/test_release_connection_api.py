"""Real local HTTP + synthetic Windows-encrypted key; no provider requests."""
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
from sixd.workspace_server import create_server
from test_workspace_ai_api import write_offline_config

KEY = "synthetic-release-http-key-only"


class ReleaseConnectionAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.folder = Path(self.temp.name)
        write_offline_config(self.folder)
        self.environment = patch.dict(os.environ, {"NEBIUS_API_KEY": ""})
        self.environment.start()
        self.calls = []
        self.open_server()

    def open_server(self):
        def no_provider(*args):
            self.calls.append(True)
            raise AssertionError("Connection controls may not instantiate a provider.")
        self.server = create_server(port=0, db_path=self.folder / "workspace.sqlite3", provider_factory=no_provider)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=5)
        self.assertFalse(self.worker.is_alive())

    def tearDown(self):
        self.stop_server()
        self.environment.stop()
        self.assertEqual(self.calls, [])
        self.temp.cleanup()

    def request(self, path, body=None, *, origin=None):
        port = self.server.server_port
        headers = {"Content-Type": "application/json", "Origin": origin or f"http://127.0.0.1:{port}"}
        connection = HTTPConnection("127.0.0.1", port, timeout=10)
        connection.request("GET" if body is None else "POST", path,
                           None if body is None else json.dumps(body), headers)
        response = connection.getresponse()
        code, raw = response.status, response.read()
        connection.close()
        self.assertNotIn(KEY.encode(), raw)
        return code, json.loads(raw)

    @unittest.skipUnless(os.name == "nt", "Windows current-user DPAPI behavior")
    def test_remember_restart_forget_keeps_session_but_not_next_restart(self):
        code, connected = self.request("/api/ai/connect", {"api_key": KEY, "remember": True})
        self.assertEqual(code, 200)
        self.assertTrue(connected["key_remembered"])
        self.assertTrue(connected["key_present"])
        saved = self.folder / "credentials" / "nebius.dpapi"
        self.assertNotIn(KEY.encode(), saved.read_bytes())
        before_budget = connected["budget"]
        self.stop_server()
        self.open_server()
        code, restored = self.request("/api/ai/status")
        self.assertEqual(code, 200)
        self.assertTrue(restored["key_present"])
        self.assertEqual(restored["key_source"], "remembered")
        self.assertEqual(restored["budget"], before_budget)
        code, forgotten = self.request("/api/ai/forget", {})
        self.assertEqual(code, 200)
        self.assertTrue(forgotten["key_present"])
        self.assertFalse(forgotten["key_remembered"])
        self.assertFalse(saved.exists())
        self.stop_server()
        self.open_server()
        self.assertFalse(self.request("/api/ai/status")[1]["key_present"])

    @unittest.skipUnless(os.name == "nt", "Windows current-user DPAPI behavior")
    def test_disconnect_removes_remembered_copy_and_cannot_resurrect_on_restart(self):
        self.assertEqual(self.request("/api/ai/connect", {"api_key": KEY, "remember": True})[0], 200)
        code, value = self.request("/api/ai/disconnect", {})
        self.assertEqual(code, 200)
        self.assertFalse(value["key_present"])
        self.assertFalse(value["key_remembered"])
        self.stop_server()
        self.open_server()
        self.assertFalse(self.request("/api/ai/status")[1]["key_present"])

    def test_legacy_connection_and_strict_optional_fields(self):
        code, value = self.request("/api/ai/connect", {"api_key": KEY})
        self.assertEqual(code, 200)
        self.assertTrue(value["key_present"])
        self.assertFalse(value["key_remembered"])
        for body in ({"api_key": KEY, "remember": "yes"}, {"api_key": KEY, "remember": True, "extra": True}):
            self.assertEqual(self.request("/api/ai/connect", body)[0], 400)
        self.assertEqual(self.request("/api/ai/forget", {"unexpected": True})[0], 400)

    def test_foreign_origin_cannot_forget_or_stop(self):
        for path in ("/api/ai/forget", "/api/shutdown"):
            self.assertEqual(self.request(path, {}, origin="https://example.invalid")[0], 403)
        self.assertFalse(self.server._stopping)

    def test_shutdown_refuses_active_job_then_stops_without_code_currentness(self):
        self.server.ai._active = "synthetic-active-job"
        self.assertEqual(self.request("/api/shutdown", {})[0], 409)
        self.assertFalse(self.server._stopping)
        self.server.ai._active = None
        with patch("sixd.workspace_server._code_fingerprint", return_value="changed-source"):
            self.assertEqual(self.request("/api/shutdown", {})[0], 200)
        self.worker.join(timeout=5)
        self.assertFalse(self.worker.is_alive())
        self.assertTrue(self.server._stopping)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
