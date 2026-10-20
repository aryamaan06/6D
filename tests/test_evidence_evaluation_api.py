"""HTTP authorization boundaries for the evidence-link comparison.

The one actual preparation runs local synthetic transports only. These tests
never connect a private key, send inference traffic or touch the founder ledger.
"""
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.workspace_server import create_server
from test_workspace_ai_api import write_offline_config


class EvidenceEvaluationAPITests(unittest.TestCase):
    def setUp(self):
        (ROOT / "work").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        write_offline_config(self.folder)
        self.factory = Mock(side_effect=AssertionError("HTTP boundary tests cannot construct a paid provider."))
        with patch.dict("os.environ", {"NEBIUS_API_KEY": ""}):
            self.server = create_server(port=0, db_path=self.folder / "workspace.sqlite3", provider_factory=self.factory)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close)
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()

    def request(self, path, body=None, *, origin=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=180)
        try:
            headers = {"Content-Type": "application/json"}
            if origin is not None:
                headers["Origin"] = origin
            connection.request("GET" if body is None else "POST", path,
                               body=None if body is None else json.dumps(body), headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def assert_no_spending_or_worker(self):
        self.factory.assert_not_called()
        self.assertIsNone(self.server.ai._active)
        self.assertIsNone(getattr(self.server.ai, "_comparison", (None,))[0])
        self.assertIsNone(self.server.evidence_evaluation.status()["latest"])
        self.assertFalse((self.folder / "budget.sqlite3").exists())
        self.assertFalse((self.folder / "project-assistant-model.json").exists())

    def test_status_reads_require_no_private_connection_and_do_not_prepare_or_spend(self):
        with patch.object(self.server.evidence_evaluation, "prepare", side_effect=AssertionError("No preparation from GET")):
            status, result = self.request("/api/evidence-evaluation/status")
        self.assertEqual(status, 200)
        self.assertEqual(result["batch_cap_usd"], 2.0)
        self.assertEqual(result["planned_tasks"], 9)
        self.assertEqual(result["case_count"], 3)
        self.assertEqual(result["explanation_policy"], "application_roles_v1")
        self.assertFalse(result["automatic_model_selection"])
        self.assertIsNone(result["latest"])
        self.assert_no_spending_or_worker()

    def test_prepare_exact_empty_body_runs_real_nine_path_forecast_without_a_key(self):
        status, prepared = self.request("/api/evidence-evaluation/prepare", {}, origin=self.origin)
        self.assertEqual(status, 200, prepared)
        self.assertEqual(prepared["state"], "prepared_offline")
        self.assertEqual(prepared["live_calls"], 0)
        self.assertFalse(prepared["active_model_changed"])
        self.assertEqual([case["id"] for case in prepared["plan"]["cases"]],
                         ["orbit-met", "limit-only-change", "unsupported-control"])
        forecast = prepared["capacity_preflight"]
        self.assertEqual(forecast["mode"], "offline_forecast")
        self.assertEqual(forecast["live_calls"], 0)
        self.assertEqual(len(forecast["cases"]), 9)
        self.assertTrue(forecast["fits"], forecast)
        self.assertEqual({row["candidate_id"] for row in forecast["cases"]}, {"nano", "super", "ultra"})
        self.assertLessEqual(forecast["forecast_with_headroom_usd"], 2)
        self.assertTrue(all(row["fits_case_cap"] for row in forecast["cases"]))
        self.assert_no_spending_or_worker()

    def test_missing_extra_false_cap_and_cross_origin_posts_stop_before_preparation(self):
        with patch.object(self.server.evidence_evaluation, "prepare", side_effect=AssertionError("Invalid request cannot prepare")) as prepare:
            invalid_bodies = ({}, {"allow_spend": True}, {"allowance_usd": 2},
                {"allow_spend": True, "allowance_usd": 2, "extra": True},
                {"allow_spend": False, "allowance_usd": 2},
                {"allow_spend": True, "allowance_usd": 1.99},
                {"allow_spend": True, "allowance_usd": True})
            for body in invalid_bodies:
                with self.subTest(body=body):
                    self.assertEqual(self.request("/api/evidence-evaluation/start", body, origin=self.origin)[0], 400)
            self.assertEqual(self.request("/api/evidence-evaluation/prepare", {"allow_spend": True}, origin=self.origin)[0], 400)
            for path, body in (("/api/evidence-evaluation/prepare", {}),
                               ("/api/evidence-evaluation/start", {"allow_spend": True, "allowance_usd": 2})):
                self.assertEqual(self.request(path, body, origin="https://untrusted.example")[0], 403)
            prepare.assert_not_called()
        self.assert_no_spending_or_worker()

    def test_explicit_start_still_needs_private_connection_and_run_ids_are_bounded(self):
        # The expensive preparation is exercised above. This test isolates the
        # subsequent private-session gate without generating another plan.
        with patch.object(self.server.evidence_evaluation, "prepare", return_value={"capacity_preflight": {"fits": True}}) as prepare:
            status, result = self.request("/api/evidence-evaluation/start",
                {"allow_spend": True, "allowance_usd": 2}, origin=self.origin)
            self.assertEqual(status, 409, result)
            prepare.assert_called_once_with()
        for identity in ("not-an-id", "../private", "0" * 32):
            with self.subTest(identity=identity):
                self.assertIn(self.request("/api/evidence-evaluation/runs/" + identity)[0], (400, 404))
        self.assert_no_spending_or_worker()


if __name__ == "__main__":
    unittest.main()
