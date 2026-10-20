"""Local API contracts for explicit subsystem architecture and interface review."""
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from sixd import engineering, workspace, workspace_server
from sixd.workspace_server import create_server
from test_workspace_systems import system_project


class WorkspaceSystemsAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "work").mkdir(exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.calls = []

        def forbidden_provider(*args, **kwargs):
            cls.calls.append((args, kwargs))
            raise AssertionError("Architecture reads must not use a paid provider")

        cls.server = create_server(port=0, db_path=Path(cls.tmp.name) / "workspace.sqlite3",
                                   ai_local_directory=Path(cls.tmp.name), provider_factory=forbidden_provider)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.tmp.cleanup()

    def request(self, route, body=None, *, headers=None, raw=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        data = raw if raw is not None else None if body is None else json.dumps(body)
        connection.request("GET" if data is None else "POST", route, data,
                           {"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        status, response_headers, value = response.status, dict(response.getheaders()), response.read()
        connection.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            value = json.loads(value)
        return status, value, response_headers

    def baseline(self, *, run=True):
        project = system_project()
        project["project_id"] = "systems-http-" + uuid4().hex
        status, view, _ = self.request("/api/projects", {"project": project})
        self.assertEqual(status, 200, view)
        if run:
            status, view, _ = self.request("/api/run", {"project_id": project["project_id"], "revision": 1})
            self.assertEqual(status, 200, view)
        return view

    @staticmethod
    def query(view, **extra):
        return "?" + urlencode({"project_id": view["project_id"], "revision": view["revision"], **extra})

    def contents(self):
        with self.server.store._connect() as db:
            names = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name: [tuple(row) for row in db.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
                    for name in names}

    def assert_no_paid_calls(self):
        self.assertEqual(self.calls, [])
        self.assertFalse((Path(self.tmp.name) / "budget.sqlite3").exists())

    def test_saved_projection_binds_exact_current_configuration_and_has_local_headers(self):
        view = self.baseline()
        before = self.contents()
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No physics for GET")), \
                patch.object(engineering, "evaluate_models", side_effect=AssertionError("No physics for GET")):
            status, result, headers = self.request("/api/interfaces" + self.query(view))
        self.assertEqual(status, 200, result)
        self.assertEqual(result, view["system_interfaces"])
        self.assertEqual(result["context"], "saved")
        self.assertEqual(result["run_id"], view["run"]["run_id"])
        self.assertEqual(result["review_digest"], view["run"]["review"]["digest"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(self.contents(), before)
        self.assert_no_paid_calls()

    def test_preview_is_read_only_draft_with_no_passing_numeric_contracts(self):
        view = self.baseline()
        project = deepcopy(view["project"])
        project["inputs"]["load_budget"]["value"] = 100
        before = self.contents()
        payload = {"project_id": view["project_id"], "base_revision": 1, "project": project}
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No draft solver")):
            status, result, _ = self.request("/api/interfaces/preview", payload)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["context"], "draft")
        self.assertEqual(result["project_digest"], workspace._digest(project))
        self.assertTrue(all(row["status"] == "not_assessed" for row in result["checks"]["rows"]))
        self.assertEqual(self.contents(), before)
        self.assertEqual(self.server.store.get(view["project_id"], 1), view)
        self.assert_no_paid_calls()

    def test_save_and_run_include_separate_interface_projection_in_both_export_formats(self):
        view = self.baseline()
        project = deepcopy(view["project"])
        project["interfaces"][0]["operator"] = ">="
        status, saved, _ = self.request("/api/revisions", {
            "project_id": view["project_id"], "base_revision": 1, "project": project})
        self.assertEqual(status, 200, saved)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("Architecture-only reuse")):
            status, updated, _ = self.request("/api/run", {"project_id": view["project_id"], "revision": 2})
        self.assertEqual(status, 200, updated)
        self.assertEqual(updated["run"]["executed_model_ids"], [])
        self.assertEqual(updated["run"]["model_results"], view["run"]["model_results"])
        status, exported, headers = self.request("/api/export" + self.query(updated))
        self.assertEqual(status, 200, exported)
        self.assertEqual(exported["system_interfaces"], updated["system_interfaces"])
        self.assertIn("attachment; filename=", headers["Content-Disposition"])
        self.assertNotIn("system_interfaces", exported["run"]["review"])
        status, combined, headers = self.request("/api/engineering-review-export" + self.query(updated))
        self.assertEqual(status, 200, combined)
        self.assertEqual(combined["workspace"]["system_interfaces"], updated["system_interfaces"])
        self.assertFalse(combined["launch_authorization"])
        self.assertEqual(combined["live_model_calls"], 0)
        self.assertIn("attachment; filename=", headers["Content-Disposition"])
        self.assertEqual(self.request("/api/workspace" + self.query(view))[1]["run"], view["run"])
        self.assert_no_paid_calls()

    def test_unreviewed_metric_projection_never_manufactures_a_run(self):
        view = self.baseline(run=False)
        before = self.contents()
        status, result, _ = self.request("/api/interfaces" + self.query(view))
        self.assertEqual(status, 200, result)
        self.assertIsNone(result["run_id"])
        self.assertEqual(next(row for row in result["checks"]["rows"]
                              if row["id"] == "drag_to_frame")["status"], "not_assessed")
        self.assertEqual(self.contents(), before)
        self.assert_no_paid_calls()

    def test_strict_query_body_origin_host_and_revision_guards(self):
        view = self.baseline()
        payload = {"project_id": view["project_id"], "base_revision": 1, "project": view["project"]}
        before = self.contents()
        for query in ("", "?project_id=" + view["project_id"], self.query(view, revision=0),
                      self.query(view) + "&revision=1", self.query(view, revision=999),
                      self.query(view) + "&project_id=other"):
            with self.subTest(query=query):
                self.assertEqual(self.request("/api/interfaces" + query)[0], 400)
        for body in ({**payload, "unexpected": True}, {k: v for k, v in payload.items() if k != "project"},
                     {**payload, "base_revision": True}, {**payload, "base_revision": 1.5}):
            with self.subTest(body_keys=list(body)):
                self.assertEqual(self.request("/api/interfaces/preview", body)[0], 400)
        # The Origin guard rejects before reading a body. Keep this POST empty
        # so Windows cannot reset a connection with unread uploaded bytes.
        self.assertEqual(self.request("/api/interfaces/preview", raw="", headers={"Origin": "https://example.org"})[0], 403)
        self.assertEqual(self.request("/api/interfaces" + self.query(view), headers={"Host": "attacker.example"})[0], 403)
        self.assertEqual(self.request("/api/interfaces/preview", payload, headers={"Content-Type": "text/plain"})[0], 400)
        self.assertEqual(self.request("/api/interfaces/preview", raw='{"project_id":"a","project_id":"b"}')[0], 400)
        self.assertEqual(self.contents(), before)
        self.assert_no_paid_calls()

    def test_cross_project_and_stale_draft_are_rejected_without_writing(self):
        view, other = self.baseline(), self.baseline()
        before = self.contents()
        wrong = {"project_id": view["project_id"], "base_revision": 1, "project": other["project"]}
        self.assertEqual(self.request("/api/interfaces/preview", wrong)[0], 400)
        self.assertEqual(self.contents(), before)
        payload = {**wrong, "project": view["project"]}
        self.assertEqual(self.request("/api/revisions", payload)[0], 200)
        before = self.contents()
        self.assertEqual(self.request("/api/interfaces/preview", payload)[0], 409)
        self.assertEqual(self.contents(), before)
        self.assert_no_paid_calls()

    def test_live_code_change_refuses_preview_until_restart(self):
        view = self.baseline()
        before = self.contents()
        with patch.object(workspace_server, "_code_fingerprint", return_value="changed"):
            status, response, _ = self.request("/api/interfaces/preview", {
                "project_id": view["project_id"], "base_revision": 1, "project": view["project"]})
            for route in ("/api/interfaces", "/api/workspace", "/api/export", "/api/engineering-review-export"):
                with self.subTest(route=route):
                    get_status, get_response, _ = self.request(route + self.query(view))
                    self.assertEqual(get_status, 409, get_response)
                    self.assertIn("Restart", get_response["error"])
        self.assertEqual(status, 409, response)
        self.assertIn("Restart", response["error"])
        self.assertEqual(self.contents(), before)
        self.assert_no_paid_calls()


if __name__ == "__main__":
    unittest.main()
