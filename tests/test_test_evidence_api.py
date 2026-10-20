"""Local HTTP links preserve original tests without running physics or inference."""
from copy import deepcopy
from hashlib import sha256
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import engineering, workspace
from sixd.project_examples import example_projects
from sixd.providers import LiveConfig, Turn
from sixd.workspace_server import create_server


CSV = ("\ufeffmeasurement_id,requirement_id,value,unit,tolerance,comment\r\n"
       'observed-a,drag_limit,310,N,15,"Constructed, not hardware\r\n=1+1"\r\n'
       "unmapped-b,absent_requirement,300,N,15,Original unmapped row\r\n")


def comparison_spec():
    return {"schema": "sixd.test-comparison-spec.v1", "name": "Frozen synthetic drag observations",
            "source": "Constructed HTTP regression data, not a physical test.", "data_kind": "synthetic",
            "test_conditions": "Drag force at density 1.2 kg/m^3, speed 50 m/s, Cd 0.8 and area 0.25 m^2; same observable and aggregation as the saved model.",
            "conditions_match": "declared_match", "filename": "synthetic-drag.csv", "csv_text": CSV,
            "mapping": {name: name for name in ("measurement_id", "requirement_id", "value", "unit", "tolerance")}}


class TestEvidenceAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "work").mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.provider_calls = []

        def forbidden_provider(*args, **kwargs):
            cls.provider_calls.append((args, kwargs))
            raise AssertionError("Test-evidence HTTP reads must not call a paid provider")

        cls.server = create_server(port=0, db_path=Path(cls.temporary.name) / "workspace.sqlite3",
                                   ai_local_directory=Path(cls.temporary.name), provider_factory=forbidden_provider)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temporary.cleanup()

    def request(self, path, body=None, *, headers=None, server=None):
        connection = HTTPConnection("127.0.0.1", (server or self.server).server_port, timeout=10)
        connection.request("GET" if body is None else "POST", path,
                           None if body is None else json.dumps(body),
                           {"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        status, response_headers, content = response.status, dict(response.getheaders()), response.read()
        connection.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            content = json.loads(content)
        return status, content, response_headers

    def baseline(self, *, run=True):
        project = deepcopy(example_projects()["baseline"])
        project["project_id"] = "test-evidence-http-" + uuid4().hex
        for identity, value in (("density", 1.2), ("relative_speed", 50), ("drag_coefficient", .8),
                                ("reference_area", .25), ("maximum_drag_force", 305)):
            project["inputs"][identity]["value"] = value
        status, view, _ = self.request("/api/projects", {"project": project})
        self.assertEqual(status, 200, view)
        if run:
            status, view, _ = self.request("/api/run", {"project_id": view["project_id"], "revision": 1})
            self.assertEqual(status, 200, view)
            self.assertEqual(view["run"]["model_results"]["atmospheric_load"]["metrics"]["drag_force"]["value"], 300)
        return view

    def save_comparison(self, view):
        status, result, _ = self.request("/api/test-comparisons", {
            "project_id": view["project_id"], "revision": view["revision"],
            "baseline_run_id": view["run"]["run_id"], "spec": comparison_spec()})
        self.assertEqual(status, 200, result)
        return result

    @staticmethod
    def query(view, **extra):
        return "?" + urlencode({"project_id": view["project_id"], "revision": view["revision"], **extra})

    def snapshot(self):
        with self.server.store._connect() as connection:
            tables = [record[0] for record in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            return {table: [tuple(row) for row in connection.execute('SELECT * FROM "' + table + '" ORDER BY rowid')]
                    for table in tables}

    def assert_no_execution(self):
        self.assertEqual(self.provider_calls, [])
        self.assertFalse((Path(self.temporary.name) / "budget.sqlite3").exists())

    def test_saved_summary_keeps_three_distinct_outcomes_and_original_identities(self):
        view = self.baseline()
        receipt = self.save_comparison(view)["receipt"]
        before = self.snapshot()
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("No physics on evidence read")), \
                patch.object(workspace, "evaluate_models", side_effect=AssertionError("No physics on evidence read")):
            status, summary, headers = self.request("/api/test-evidence" + self.query(view))
        self.assertEqual(status, 200, summary)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(summary["context"], "saved")
        self.assertEqual(summary["current_run_id"], view["run"]["run_id"])
        self.assertEqual(summary["current_review_digest"], view["run"]["review"]["digest"])
        item, row = summary["comparisons"][0], summary["comparisons"][0]["rows"][0]
        self.assertEqual(item["comparison_id"], receipt["comparison_id"])
        self.assertEqual(item["baseline_run_id"], receipt["baseline"]["run_id"])
        self.assertEqual(item["baseline_review_digest"], receipt["baseline"]["review"]["digest"])
        self.assertEqual(item["csv_sha256"], sha256(CSV.encode("utf-8")).hexdigest())
        self.assertTrue(item["source_current"])
        self.assertEqual(view["run"]["review"]["findings"]["drag_limit"]["status"], "met")
        self.assertEqual(row["measurement_requirement"]["status"], "not_met")
        self.assertEqual(row["prediction_agreement"]["status"], "within_tolerance")
        self.assertEqual(row["applicability"]["status"], "exact_baseline")
        self.assertEqual(item["rows"][1]["applicability"]["status"], "unmapped")
        self.assertEqual(summary["counts"]["rows"], 2)
        self.assertEqual(summary["counts"]["current"], 1)
        self.assertEqual(summary["counts"]["historical"], 1)
        self.assertEqual(summary["counts"]["unassessed"], 1)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.server.store.get(view["project_id"], 1), view)
        self.assert_no_execution()

    def test_combined_export_contains_exact_csv_original_baseline_and_stable_digest(self):
        view = self.baseline()
        detail = self.save_comparison(view)
        before = self.snapshot()
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("No solver for export")), \
                patch.object(workspace, "evaluate_models", side_effect=AssertionError("No solver for export")):
            status, exported, headers = self.request("/api/engineering-review-export" + self.query(view))
            second = self.request("/api/engineering-review-export" + self.query(view))[1]
        self.assertEqual(status, 200, exported)
        self.assertIn("attachment; filename=", headers["Content-Disposition"])
        self.assertEqual(exported, second)
        self.assertEqual(exported["workspace"], view)
        self.assertEqual(exported["test_evidence"], self.request("/api/test-evidence" + self.query(view))[1])
        self.assertFalse(exported["launch_authorization"])
        self.assertEqual(exported["live_model_calls"], 0)
        original = exported["original_test_sources"][0]
        self.assertEqual(original["csv_text"], CSV)
        self.assertEqual(original["comparison_id"], detail["receipt"]["comparison_id"])
        self.assertEqual(original["baseline_run_id"], view["run"]["run_id"])
        self.assertEqual(original["mapping"], comparison_spec()["mapping"])
        self.assertFalse(original["conditions_declaration_verified"])
        digest = exported.pop("export_digest")
        self.assertEqual(digest, workspace._digest(exported))
        self.assertEqual(self.snapshot(), before)
        self.assert_no_execution()

    def test_draft_dependency_change_marks_review_without_recalculating_original_outcomes(self):
        view = self.baseline()
        receipt = self.save_comparison(view)["receipt"]
        project = deepcopy(view["project"])
        project["inputs"]["relative_speed"]["value"] = 100
        before = self.snapshot()
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("A draft must not run physics")), \
                patch.object(workspace, "evaluate_models", side_effect=AssertionError("A draft must not run physics")):
            status, preview, _ = self.request("/api/test-evidence/impact", {
                "project_id": view["project_id"], "base_revision": 1, "project": project})
        self.assertEqual(status, 200, preview)
        self.assertEqual(preview["context"], "draft")
        self.assertEqual(preview["project_digest"], workspace._digest(project))
        row = preview["comparisons"][0]["rows"][0]
        self.assertEqual(row["applicability"]["status"], "needs_review")
        self.assertIn("relative_speed", row["applicability"]["changed_inputs"])
        original = {key: value for key, value in row.items() if key != "applicability"}
        self.assertEqual(original, receipt["row_results"][0])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.server.store.get(view["project_id"], 1), view)
        self.assert_no_execution()

    def test_unrelated_draft_and_removed_requirement_preserve_historical_records(self):
        view = self.baseline()
        self.save_comparison(view)
        project = deepcopy(view["project"])
        project["inputs"]["heat_input"]["value"] = 700
        payload = {"project_id": view["project_id"], "base_revision": 1, "project": project}
        before = self.snapshot()
        status, unchanged, _ = self.request("/api/test-evidence/impact", payload)
        self.assertEqual(status, 200, unchanged)
        row = unchanged["comparisons"][0]["rows"][0]
        self.assertEqual(row["applicability"]["status"], "same_dependencies")
        self.assertFalse(row["applicability"]["exact_baseline"])
        project["requirements"] = [item for item in project["requirements"] if item["id"] != "drag_limit"]
        status, removed, _ = self.request("/api/test-evidence/impact", payload)
        self.assertEqual(status, 200, removed)
        original = removed["comparisons"][0]["rows"][0]
        self.assertEqual(original["requirement_id"], "drag_limit")
        self.assertEqual(original["applicability"]["status"], "requirement_removed")
        self.assertEqual(original["measurement_requirement"]["status"], "not_met")
        self.assertEqual(self.snapshot(), before)
        self.assert_no_execution()

    def test_saved_revision_keeps_comparison_origin_and_reading_old_revision_is_stable(self):
        view = self.baseline()
        comparison = self.save_comparison(view)["receipt"]
        original_summary = self.request("/api/test-evidence" + self.query(view))[1]
        project = deepcopy(view["project"])
        project["inputs"]["heat_input"]["value"] = 700
        status, later, _ = self.request("/api/revisions", {"project_id": view["project_id"], "base_revision": 1, "project": project})
        self.assertEqual(status, 200, later)
        before = self.snapshot()
        summary = self.request("/api/test-evidence" + self.query(later))[1]
        self.assertIsNone(summary["current_run_id"])
        self.assertEqual(summary["comparisons"][0]["tested_revision"], 1)
        self.assertEqual(summary["comparisons"][0]["baseline_run_id"], comparison["baseline"]["run_id"])
        self.assertEqual(summary["comparisons"][0]["rows"][0]["applicability"]["status"], "same_dependencies")
        self.assertEqual(self.request("/api/test-evidence" + self.query(view))[1], original_summary)
        self.assertEqual(self.snapshot(), before)
        self.assert_no_execution()

    def test_cross_project_and_invalid_draft_revision_are_rejected_atomically(self):
        view, other = self.baseline(), self.baseline()
        self.save_comparison(view)
        before = self.snapshot()
        wrong_project = {"project_id": view["project_id"], "base_revision": 1, "project": other["project"]}
        self.assertEqual(self.request("/api/test-evidence/impact", wrong_project)[0], 400)
        project = deepcopy(view["project"])
        project["revision"] = "3"
        self.assertEqual(self.request("/api/test-evidence/impact", {**wrong_project, "project": project})[0], 400)
        other_summary = self.request("/api/test-evidence" + self.query(other))[1]
        self.assertEqual(other_summary["comparisons"], [])
        self.assertEqual(self.snapshot(), before)
        self.assert_no_execution()

    def test_strict_fields_revision_and_origin_guards_and_assets(self):
        view = self.baseline()
        payload = {"project_id": view["project_id"], "base_revision": 1, "project": view["project"]}
        before = self.snapshot()
        self.assertEqual(self.request("/api/test-evidence/impact", {**payload, "extra": True})[0], 400)
        self.assertEqual(self.request("/api/test-evidence/impact", {"project_id": view["project_id"], "project": view["project"]})[0], 400)
        self.assertEqual(self.request("/api/test-evidence/impact", {**payload, "base_revision": True})[0], 400)
        self.assertEqual(self.request("/api/test-evidence/impact", payload, headers={"Origin": "https://example.org"})[0], 403)
        for route in ("/api/test-evidence", "/api/engineering-review-export"):
            for query in ("", "?project_id=" + view["project_id"], self.query(view, revision="0"),
                          self.query(view) + "&revision=1", self.query(view, revision="999")):
                with self.subTest(route=route, query=query):
                    self.assertEqual(self.request(route + query)[0], 400)
        for route in ("/test-evidence.js", "/test-evidence.css"):
            self.assertEqual(self.request(route)[0], 200)
        self.assertEqual(self.snapshot(), before)
        self.assert_no_execution()

    def test_unreviewed_summary_is_empty_and_never_manufactures_a_run(self):
        view = self.baseline(run=False)
        before = self.snapshot()
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("No automatic review")), \
                patch.object(workspace, "evaluate_models", side_effect=AssertionError("No automatic review")):
            status, summary, _ = self.request("/api/test-evidence" + self.query(view))
        self.assertEqual(status, 200, summary)
        self.assertIsNone(summary["current_run_id"])
        self.assertIsNone(summary["current_review_digest"])
        self.assertEqual(summary["comparisons"], [])
        self.assertEqual(summary["counts"]["rows"], 0)
        self.assertEqual(self.snapshot(), before)
        self.assert_no_execution()

    def test_later_revision_comparison_is_neither_listed_nor_investigable_from_prior_revision(self):
        earlier = self.baseline()
        project = deepcopy(earlier["project"])
        project["inputs"]["relative_speed"]["value"] = 100
        status, saved, _ = self.request("/api/revisions", {"project_id": earlier["project_id"], "base_revision": 1, "project": project})
        self.assertEqual(status, 200, saved)
        status, later, _ = self.request("/api/run", {"project_id": earlier["project_id"], "revision": 2})
        self.assertEqual(status, 200, later)
        receipt = self.save_comparison(later)["receipt"]
        before = self.snapshot()
        self.assertEqual(self.request("/api/test-evidence" + self.query(earlier))[1]["comparisons"], [])
        exported = self.request("/api/engineering-review-export" + self.query(earlier))[1]
        self.assertEqual(exported["original_test_sources"], [])
        with patch.object(self.server.ai, "_config", side_effect=AssertionError("Future test evidence must fail before configuration")) as configure:
            status, failure, _ = self.request("/api/investigations", {
                "project_id": earlier["project_id"], "revision": 1, "requirement_id": "drag_limit", "question": "Explain this row.",
                "test_comparison_id": receipt["comparison_id"], "test_row_number": 2})
            self.assertEqual(status, 400, failure)
            configure.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        self.assert_no_execution()

    def test_invalid_selected_investigations_fail_before_configuration_or_spending(self):
        view, other = self.baseline(), self.baseline()
        receipt = self.save_comparison(view)["receipt"]
        basic = {"project_id": view["project_id"], "revision": 1, "requirement_id": "drag_limit", "question": "Explain this recorded test row."}
        selected = {**basic, "test_comparison_id": receipt["comparison_id"], "test_row_number": 2}
        variants = [{**basic, "test_comparison_id": receipt["comparison_id"]},
                    {**basic, "test_row_number": 2}, {**selected, "extra": True},
                    {**selected, "test_comparison_id": None, "test_row_number": None},
                    {**selected, "test_row_number": True}, {**selected, "test_row_number": "2"},
                    {**selected, "test_row_number": 201}, {**selected, "test_row_number": 3},
                    {**selected, "test_comparison_id": "bad-id"},
                    {**selected, "requirement_id": "thermal_limit"},
                    {**selected, "project_id": other["project_id"]}]
        before = self.snapshot()
        with patch.object(self.server.ai, "_config", side_effect=AssertionError("Invalid selection must fail before provider configuration")) as configure:
            for body in variants:
                with self.subTest(body=body):
                    status, failure, _ = self.request("/api/investigations", body)
                    self.assertEqual(status, 400, failure)
            configure.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        self.assert_no_execution()

    def test_stale_runtime_blocks_new_projection_and_export_without_hiding_original_receipt(self):
        view = self.baseline()
        receipt = self.save_comparison(view)["receipt"]
        before = self.snapshot()
        with patch("sixd.workspace_server._code_fingerprint", return_value="changed-source-fingerprint"):
            for route in ("/api/test-evidence", "/api/engineering-review-export"):
                status, value, _ = self.request(route + self.query(view))
                self.assertEqual(status, 409, value)
                self.assertIn("Restart", value["error"])
            self.assertEqual(self.request("/api/test-comparisons/" + receipt["comparison_id"] + "?revision=1")[0], 200)
        self.assertEqual(self.snapshot(), before)
        self.assert_no_execution()

    def test_offline_http_investigation_completes_with_frozen_selection_and_no_live_calls(self):
        # A second, fully isolated service is the only server in this module
        # with synthetic provider credentials/configuration and a fixture ledger.
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as temporary:
            local = Path(temporary)
            providers = []
            summary = ("The canonical design criterion is met at 300 N against 305 N within this bounded model. "
                       "The measured criterion is not met at 310 N against the recorded 305 N limit. "
                       "The recorded measurement is within tolerance of the saved prediction: the difference is 10 N and tolerance is 15 N. "
                       "Declared test conditions are unverified. Review calibration, observable definition and model assumptions before attributing a cause.")

            class OfflineTransport:
                mode = "offline_transport_fixture"
                model = "nvidia/offline-nemotron-test-evidence-http"

                def __init__(self, config, budget, key):
                    self.config, self.budget, self._key = config, budget, key
                    self.request_attempts, self.histories = 0, []

                def complete(self, messages, tools):
                    self.budget.reserve(self.config, .001)
                    self.request_attempts += 1
                    self.histories.append(deepcopy(messages))
                    available = {item["function"]["name"]: item for item in tools}
                    action = next(name for name in ("read_requirement", "read_model", "recheck_model", "finish") if name in available)
                    arguments = {}
                    if action == "finish":
                        arguments = {"summary": summary, "evidence_ids": available[action]["function"]["parameters"]
                                     ["properties"]["evidence_ids"]["items"]["enum"]}
                    return Turn({"role": "assistant", "content": None, "tool_calls": [{
                        "id": "offline-http-" + str(self.request_attempts), "type": "function",
                        "function": {"name": action, "arguments": json.dumps(arguments)}}]},
                        {"prompt_tokens": 10, "completion_tokens": 10})

            config = LiveConfig("https://api.tokenfactory.nebius.com/v1/", OfflineTransport.model,
                                "isolated-http-test-evidence", 5.0, .06, .24, 2048, 45,
                                "native_no_thinking", "forced_action_v1")
            (local / "token-factory.json").write_text(json.dumps({**config.__dict__, "account_verified": True,
                "model_license_reviewed": True, "spend_approved": True}), encoding="utf-8")

            def factory(selected_config, budget, key):
                provider = OfflineTransport(selected_config, budget, key)
                providers.append(provider)
                return provider

            with patch.dict("os.environ", {"NEBIUS_API_KEY": ""}):
                server = create_server(port=0, db_path=local / "workspace.sqlite3", ai_local_directory=local, provider_factory=factory)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                project = deepcopy(example_projects()["baseline"])
                project["project_id"] = "offline-http-selected-" + uuid4().hex
                for identity, value in (("density", 1.2), ("relative_speed", 50), ("drag_coefficient", .8),
                                       ("reference_area", .25), ("maximum_drag_force", 305)):
                    project["inputs"][identity]["value"] = value
                server.store.create_project(project)
                view = server.store.run(project["project_id"], 1)
                detail = server.test_data.run(view["project_id"], 1, view["run"]["run_id"], comparison_spec())
                selected = detail["receipt"]["comparison_id"]
                expected_bundle = server.test_evidence.investigation_context(view["project_id"], 1, "drag_limit", selected, 2)
                fake_key = "synthetic-private-http-test-evidence-key"
                status, connected, _ = self.request("/api/ai/connect", {"api_key": fake_key}, server=server)
                self.assertEqual(status, 200, connected)
                self.assertFalse(connected["live_validated"])
                status, queued, _ = self.request("/api/investigations", {"project_id": view["project_id"], "revision": 1,
                    "requirement_id": "drag_limit", "question": "Explain the selected observation and next engineering checks.",
                    "test_comparison_id": selected, "test_row_number": 2}, server=server)
                self.assertEqual(status, 200, queued)
                self.assertEqual(queued["test_evidence"], expected_bundle)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    status, completed, _ = self.request("/api/investigations/" + queued["investigation_id"], server=server)
                    self.assertEqual(status, 200, completed)
                    if completed["state"] not in {"queued", "running"} and server.ai._active is None:
                        break
                    threading.Event().wait(.01)
                else:
                    self.fail("The offline selected-test HTTP investigation did not settle")
                self.assertEqual(completed["state"], "completed", completed.get("error"))
                self.assertEqual(completed["provider_mode"], "offline_transport_fixture")
                self.assertEqual(completed["live_model_calls"], 0)
                self.assertEqual(completed["request_attempts"], 4)
                self.assertEqual(completed["test_evidence"], expected_bundle)
                self.assertEqual(completed["evidence"]["requirement:drag_limit"]["selected_test_evidence"], expected_bundle)
                self.assertEqual(completed["canonical_finding"], view["run"]["review"]["findings"]["drag_limit"])
                self.assertEqual(completed["test_evidence"]["recorded"]["row"]["measurement_requirement"]["status"], "not_met")
                self.assertEqual(completed["test_evidence"]["recorded"]["row"]["prediction_agreement"]["status"], "within_tolerance")
                self.assertEqual(completed["test_evidence"]["selection"]["pointer"], "/row_results/0")
                self.assertIn("requirement:drag_limit", completed["citations"])
                self.assertNotIn("unmapped-b", json.dumps(providers[0].histories))
                self.assertNotIn("csv_text", json.dumps(providers[0].histories))
                self.assertNotIn(fake_key, json.dumps(completed))
                self.assertEqual(server.store.get(view["project_id"], 1), view)
                self.assertEqual(server.test_data.get(selected, 1), detail)
                self.assertFalse(completed["launch_authorization"])
                listed = self.request("/api/investigations" + self.query(view, requirement_id="drag_limit"), server=server)[1]
                self.assertEqual(listed["investigations"], [completed])
                # A later CSV must not replace the captured row in old history.
                later_spec = comparison_spec()
                later_spec["csv_text"] = CSV.replace("310,N,15", "999,N,15")
                server.test_data.run(view["project_id"], 1, view["run"]["run_id"], later_spec)
                self.assertEqual(self.request("/api/investigations/" + queued["investigation_id"], server=server)[1], completed)
                self.assertFalse(self.request("/api/ai/status", server=server)[1]["live_validated"])
                for path in local.iterdir():
                    if path.is_file():
                        self.assertNotIn(fake_key.encode(), path.read_bytes(), str(path))
            finally:
                server.shutdown()
                server.server_close()
                worker.join()


if __name__ == "__main__":
    unittest.main()
