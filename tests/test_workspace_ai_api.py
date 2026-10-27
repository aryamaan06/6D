"""End-to-end HTTP investigations through an explicitly offline wire transport."""
from dataclasses import asdict
from contextlib import closing
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.providers import LiveConfig, TokenFactoryProvider
from sixd.project_investigation import ProjectActionAdapter
from sixd.workspace_server import create_server

KEY = "synthetic-http-offline-key-only"


def offline_transport(request):
    payload = json.loads(request.data)
    menu = json.loads(payload["messages"][-1]["content"])
    names = {item["action"] for item in menu["available_actions"]}
    action = next(name for name in ("read_requirement", "read_model", "recheck_model", "finish", "read_changes") if name in names)
    arguments = {"action": action, "evidence_ids": menu["recorded_evidence_ids"] if action == "finish" else [],
                 "summary": "Offline test interpretation: inspect the cited canonical finding, model assumptions and unassessed scope." if action == "finish" else ""}
    return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": None,
            "tool_calls": [{"id": "offline-http-" + action, "type": "function", "function": {
                "name": "select_next_action", "arguments": json.dumps(arguments)}}]}}],
            "usage": {"prompt_tokens": 500, "completion_tokens": 60, "total_tokens": 560}}


def offline_factory(config, ledger, key):
    return TokenFactoryProvider(config, ledger, api_key=key,
                                transport=offline_transport, action_adapter=ProjectActionAdapter())


def write_offline_config(folder):
    config = LiveConfig("https://api.tokenfactory.nebius.com/v1/", "nvidia/offline-nemotron-http-test",
                        "offline-http-test", 5.0, .06, .24, 2048, 45, "native_no_thinking", "forced_action_v1")
    (folder / "token-factory.json").write_text(json.dumps({**asdict(config), "account_verified": True,
        "model_license_reviewed": True, "spend_approved": True}), encoding="utf-8")


class WorkspaceAIAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "work").mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.folder = Path(cls.temp.name)
        write_offline_config(cls.folder)
        cls.server = create_server(port=0, db_path=cls.folder / "workspace.sqlite3", provider_factory=offline_factory)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.port = cls.server.server_port
        cls.identity = cls.server.store.ensure_default()

    @classmethod
    def tearDownClass(cls):
        # HTTP shutdown alone does not join an explicitly started background AI
        # worker. Let its final SQLite write close before removing the fixture,
        # especially on Windows where open files cannot be unlinked.
        deadline = time.monotonic() + 10
        while cls.server.ai._active and time.monotonic() < deadline:
            time.sleep(.01)
        if cls.server.ai._active:
            raise AssertionError("Offline investigation did not become idle before fixture cleanup.")
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temp.cleanup()

    def request(self, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("GET" if body is None else "POST", path, None if body is None else json.dumps(body),
                           {"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        value = json.loads(response.read())
        status = response.status
        connection.close()
        return status, value

    def question(self, requirement="thermal_limit"):
        return {"project_id": self.identity, "revision": 1,
                "requirement_id": requirement, "question": "What supports this finding, and what is not assessed?"}

    def test_conversation_http_rejects_client_history_and_malformed_parent_before_reservation(self):
        before = self.request("/api/ai/status")[1]["budget"]
        for parent in (None, True, 12, "", "g" * 32, "a" * 31, "a" * 33):
            status, _ = self.request("/api/investigations", {**self.question(), "parent_investigation_id": parent})
            self.assertEqual(status, 400)
        for field in ("conversation_context", "messages", "assistant_history"):
            status, _ = self.request("/api/investigations", {**self.question(), field: [{"role": "assistant", "content": "invented"}]})
            self.assertEqual(status, 400)
        self.assertEqual(self.request("/api/ai/status")[1]["budget"], before)

    def await_job(self, identity):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status, value = self.request("/api/investigations/" + identity)
            self.assertEqual(status, 200)
            if value["state"] not in ("queued", "running"):
                return value
            time.sleep(.01)
        self.fail("Offline investigation did not complete")

    def test_connection_is_memory_only_and_does_not_call_or_create_budget(self):
        before = self.request("/api/ai/status")[1]
        status, value = self.request("/api/ai/connect", {"api_key": KEY})
        self.assertEqual(status, 200)
        self.assertTrue(value["key_present"])
        self.assertEqual(value["provider_mode"], "offline_transport_fixture")
        self.assertNotIn(KEY, json.dumps(value))
        self.assertEqual(value["budget"], before["budget"])
        self.assertEqual(self.request("/api/ai/disconnect", {})[0], 200)

    def test_model_comparison_http_status_and_explicit_start_guards(self):
        before = self.request("/api/ai/status")[1]["budget"]
        status, value = self.request("/api/model-evaluation/status")
        self.assertEqual(status, 200)
        self.assertEqual(value["case_count"], 6)
        self.assertEqual(value["active_model"]["name"], "Nano")
        self.assertEqual(self.request("/api/model-evaluation/start", {"allow_spend": False, "allowance_usd": .75})[0], 400)
        self.assertEqual(self.request("/api/model-evaluation/start", {"allow_spend": True, "allowance_usd": .75}, headers={"Origin": "https://untrusted.example"})[0], 403)
        self.assertEqual(self.request("/api/model-evaluation/comparisons/not-an-id")[0], 400)
        self.assertEqual(self.request("/api/ai/status")[1]["budget"], before)

    def test_actual_wire_agent_job_is_scoped_persisted_and_never_claimed_live(self):
        self.request("/api/ai/connect", {"api_key": KEY})
        original = self.server.store.get(self.identity)
        status, queued = self.request("/api/investigations", self.question())
        self.assertEqual(status, 200, queued)
        result = self.await_job(queued["investigation_id"])
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(result["provider_mode"], "offline_transport_fixture")
        self.assertEqual(result["live_model_calls"], 0)
        self.assertEqual(result["request_attempts"], 4)
        self.assertEqual(result["review_digest"], original["run"]["review"]["digest"])
        self.assertEqual(result["finding_status"], "met")
        self.assertEqual(set(result["citations"]), {"requirement:thermal_limit", "model:thermal", "recheck:thermal"})
        self.assertEqual(self.server.store.get(self.identity), original)
        query = urlencode({"project_id": self.identity, "revision": 1, "requirement_id": "thermal_limit"})
        records = self.request("/api/investigations?" + query)[1]["investigations"]
        self.assertIn(result, records)
        self.assertFalse(self.request("/api/ai/status")[1]["live_validated"])
        self.assertNotIn(KEY, json.dumps(records))

    def test_unsupported_control_retains_unassessed_result_and_skips_recheck(self):
        self.request("/api/ai/connect", {"api_key": KEY})
        status, queued = self.request("/api/investigations", self.question("control_tracking"))
        self.assertEqual(status, 200)
        result = self.await_job(queued["investigation_id"])
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(result["finding_status"], "not_assessed")
        self.assertNotIn("recheck_model", [event["action"] for event in result["events"]])

    def test_missing_key_invalid_scope_and_unknown_fields_cannot_start_requests(self):
        self.request("/api/ai/disconnect", {})
        self.assertEqual(self.request("/api/investigations", self.question())[0], 409)
        self.request("/api/ai/connect", {"api_key": KEY})
        self.assertEqual(self.request("/api/investigations", self.question("absent"))[0], 400)
        self.assertEqual(self.request("/api/investigations", {**self.question(), "provider": "arbitrary"})[0], 400)
        self.assertEqual(self.request("/api/ai/connect", {"api_key": KEY, "base_url": "https://example.com"})[0], 400)

    def test_api_key_in_question_is_rejected_before_any_saved_record(self):
        self.request("/api/ai/connect", {"api_key": KEY})
        payload = {**self.question(), "question": "Do not save " + KEY}
        self.assertEqual(self.request("/api/investigations", payload)[0], 400)
        with closing(sqlite3.connect(self.folder / "workspace.sqlite3")) as db:
            self.assertNotIn(KEY, " ".join(row[0] for row in db.execute("SELECT record FROM project_investigations")))

    def test_local_boundary_blocks_cross_origin_connection_without_echo(self):
        # The server rejects these headers before consuming a body.
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("POST", "/api/ai/connect", "", {"Content-Type": "application/json", "Origin": "https://example.com"})
        response = connection.getresponse()
        self.assertEqual(response.status, 403)
        self.assertNotIn(KEY, response.read().decode())
        connection.close()
        self.assertEqual(self.request("/api/investigations/../../.local/token-factory.json")[0], 400)


if __name__ == "__main__":
    unittest.main()
