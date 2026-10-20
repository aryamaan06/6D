"""Actual HTTP intake, local execution, revision conflicts and export boundaries."""
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlencode
from uuid import uuid4
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.workspace_server import create_server, SERVICE, MAX_BODY_BYTES
from sixd import workspace_server
from sixd.project_examples import example_projects


class WorkspaceAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "work").mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.server = create_server(port=0, db_path=Path(cls.temporary.name) / "workspace.sqlite3")
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temporary.cleanup()

    def request(self, path, body=None, *, method=None, headers=None, raw=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = raw if raw is not None else None if body is None else json.dumps(body)
        connection.request(method or ("GET" if data is None else "POST"), path,
                           data, {"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        contents, response_headers, status = response.read(), dict(response.getheaders()), response.status
        connection.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            contents = json.loads(contents)
        return status, contents, response_headers

    def create(self):
        project = deepcopy(example_projects()["baseline"])
        project["project_id"] = "api-" + uuid4().hex
        project["name"] = "An imported design"
        status, view, _ = self.request("/api/projects", {"project": project})
        self.assertEqual(status, 200, view)
        return view

    def test_status_is_local_and_never_advertises_live_inference(self):
        status, value, headers = self.request("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(value["service"], SERVICE)
        self.assertEqual(value["calculation_mode"], "local_deterministic")
        self.assertEqual(value["inference_mode"], "off")
        self.assertRegex(value["build_id"], r"^[a-f0-9]{12}$")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_scenario_roundtrip_export_and_baseline_isolation(self):
        original = self.create()
        identity = original["project_id"]
        baseline = self.request("/api/run", {"project_id": identity, "revision": 1})[1]
        spec = {"schema": "sixd.scenario-spec.v1", "name": "HTTP explicit alternatives",
                "source": "Constructed API acceptance values.", "mode": "sweep",
                "input_id": "relative_speed", "values": [50, 200]}
        status, study, _ = self.request("/api/scenarios", {"project_id": identity, "revision": 1,
            "baseline_run_id": baseline["run"]["run_id"], "spec": spec})
        self.assertEqual(status, 200, study)
        receipt = study["receipt"]
        sid = receipt["study_id"]
        listed = self.request("/api/scenarios?" + urlencode({"project_id": identity, "revision": 1}))[1]
        self.assertEqual(listed["studies"][0]["study_id"], sid)
        self.assertEqual(self.request(f"/api/scenarios/{sid}?revision=1")[1], study)
        status, exported, headers = self.request(f"/api/scenario-export?id={sid}&revision=1")
        self.assertEqual(status, 200)
        self.assertEqual(exported, study)
        self.assertIn("attachment; filename=", headers["Content-Disposition"])
        self.assertEqual(self.request("/api/workspace?" + urlencode({"project_id": identity, "revision": 1}))[1], baseline)
        self.assertEqual(receipt["live_model_calls"], 0)

    def test_scenario_requires_review_and_rejects_cross_origin_and_extra_fields(self):
        original = self.create()
        body = {"project_id": original["project_id"], "revision": 1, "baseline_run_id": "0" * 32,
                "spec": {"schema": "sixd.scenario-spec.v1", "name": "No reviewed baseline",
                         "source": "Constructed test", "mode": "sweep", "input_id": "heat_input", "values": [1, 2]}}
        self.assertEqual(self.request("/api/scenarios", body)[0], 409)
        self.assertEqual(self.request("/api/scenarios", {**body, "extra": True})[0], 400)
        self.assertEqual(self.request("/api/scenarios", body, headers={"Origin": "https://example.org"})[0], 403)
        self.assertEqual(self.request("/api/scenarios/not-an-id")[0], 400)
        for path in ("/scenarios.js", "/scenarios.css"):
            self.assertEqual(self.request(path)[0], 200)

    def test_default_workspace_has_actual_report_and_a_control_evidence_gap(self):
        status, value, _ = self.request("/api/workspace")
        self.assertEqual(status, 200)
        self.assertEqual(value["run"]["review"]["findings"]["control_tracking"]["status"], "not_assessed")
        self.assertFalse(value["run"]["review"]["launch_authorization"])
        self.assertEqual(value["run"]["live_model_calls"], 0)

    def test_edit_impact_save_run_export_and_read_original_revision(self):
        original = self.create()
        identity = original["project_id"]
        project = deepcopy(original["project"])
        initial = self.request("/api/run", {"project_id": identity, "revision": 1})[1]
        project["inputs"]["heat_input"]["value"] = 700
        payload = {"project_id": identity, "base_revision": 1, "project": project}
        status, impact, _ = self.request("/api/impact", payload)
        self.assertEqual(status, 200)
        self.assertEqual(impact["impact"]["affected_model_ids"], ["thermal"])
        saved = self.request("/api/revisions", payload)[1]
        self.assertEqual(saved["revision"], 2)
        self.assertIsNone(saved["run"])
        self.assertEqual(saved["prior_run"]["run_id"], initial["run"]["run_id"])
        query = "?" + urlencode({"project_id": identity, "revision": 2})
        self.assertEqual(self.request("/api/export" + query)[0], 409)
        status, current, _ = self.request("/api/run", {"project_id": identity, "revision": 2})
        self.assertEqual(status, 200, current)
        self.assertEqual(current["run"]["executed_model_ids"], ["thermal"])
        self.assertEqual(current["run"]["review"]["findings"]["thermal_limit"]["status"], "not_met")
        status, exported, headers = self.request("/api/export" + query)
        self.assertEqual(status, 200)
        self.assertEqual(exported["schema"], "sixd.workspace-export.v1")
        self.assertEqual(exported["run"]["review"], current["run"]["review"])
        self.assertIn("attachment; filename=", headers["Content-Disposition"])
        prior = self.request("/api/workspace?" + urlencode({"project_id": identity, "revision": 1}))[1]
        self.assertEqual(prior["run"], initial["run"])
        self.assertEqual(prior["project"]["inputs"]["heat_input"]["value"], 200)

    def test_stale_tab_cannot_overwrite_a_new_revision(self):
        original = self.create()
        payload = {"project_id": original["project_id"], "base_revision": 1, "project": original["project"]}
        self.assertEqual(self.request("/api/revisions", payload)[0], 200)
        self.assertEqual(self.request("/api/revisions", payload)[0], 409)

    def test_import_duplicate_id_does_not_overwrite_project(self):
        original = self.create()
        self.assertEqual(self.request("/api/projects", {"project": original["project"]})[0], 409)

    def test_invalid_project_and_arbitrary_code_are_rejected_atomically(self):
        original = self.create()
        invalid = deepcopy(original["project"])
        invalid["code"] = "arbitrary command"
        payload = {"project_id": original["project_id"], "base_revision": 1, "project": invalid}
        self.assertEqual(self.request("/api/revisions", payload)[0], 400)
        current = self.request("/api/workspace?" + urlencode({"project_id": original["project_id"]}))[1]
        self.assertEqual(current["project"], original["project"])
        self.assertEqual(len(current["revisions"]), 1)

    def test_duplicate_keys_nonfinite_and_unknown_request_fields_are_rejected(self):
        for raw in ('{"project":{},"project":{}}', '{"project":{"value":NaN}}', '[]'):
            with self.subTest(raw=raw):
                self.assertEqual(self.request("/api/projects", raw=raw)[0], 400)
        self.assertEqual(self.request("/api/run", {"project_id": "x", "revision": 1, "provider": "live"})[0], 400)

    def test_origin_host_and_content_type_boundaries(self):
        self.assertEqual(self.request("/api/projects", raw="", headers={"Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request("/api/projects", headers={"Host": "attacker.example"})[0], 403)
        self.assertEqual(self.request("/api/run", raw="", headers={"Content-Type": "text/plain"})[0], 400)
        # Header-only rejection: do not race an invalid shorter body against the
        # server's close when it refuses the advertised over-limit length.
        self.assertEqual(self.request("/api/run", raw="", headers={"Content-Length": str(MAX_BODY_BYTES + 1)})[0], 400)

    def test_revision_types_and_repeated_query_values_are_not_coerced(self):
        for revision in (True, 1.1, 0, -1, "01", "1;anything"):
            with self.subTest(revision=revision):
                self.assertEqual(self.request("/api/run", {"project_id": "x", "revision": revision})[0], 400)
        self.assertEqual(self.request("/api/workspace?project_id=x&project_id=y")[0], 400)

    def test_private_paths_and_unimplemented_actions_are_not_served(self):
        for path in ("/.env", "/.local/workspace.sqlite3", "/src/sixd/workspace.py", "/../AGENTS.md", "/api/investigate"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request("/api/investigate", {"provider": "token-factory"})[0], 404)

    def test_static_app_uses_external_local_assets(self):
        status, html, headers = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"workspace.js", html)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        for path in ("/workspace.js", "/workspace.css", "/lucide.js"):
            self.assertEqual(self.request(path)[0], 200)

    def test_changed_runtime_blocks_mutation_instead_of_claiming_current_code(self):
        original = self.create()
        with patch.object(workspace_server, "_code_fingerprint", return_value="changed"):
            status, value, _ = self.request("/api/status")
            self.assertEqual(status, 200)
            self.assertTrue(value["restart_required"])
            status, value, _ = self.request("/api/run", {"project_id": original["project_id"], "revision": 1})
            self.assertEqual(status, 409)
            self.assertIn("Restart", value["error"])
        current = self.request("/api/workspace?" + urlencode({"project_id": original["project_id"]}))[1]
        self.assertIsNone(current["run"])

    def test_oversized_project_and_deep_json_are_controlled_errors(self):
        project = deepcopy(example_projects()["baseline"])
        project["description"] = "x" * (2 * 1024 * 1024)
        status, value, _ = self.request("/api/projects", {"project": project})
        self.assertEqual(status, 400)
        self.assertIn("two-megabyte", value["error"])
        status, _, _ = self.request("/api/projects", raw='{"project":' + '[' * 1100 + '0' + ']' * 1100 + '}')
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
