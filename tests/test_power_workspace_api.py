"""Actual loopback HTTP contracts for the bounded power/energy capability.

All projects, stores and providers are isolated fixtures. These requests never
access founder data, an API credential or any external inference endpoint.
"""
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
sys.path.insert(0, str(ROOT / "tests"))
from sixd import engineering, workspace_server
from sixd.workspace_server import create_server
from test_power_workspace import power_project


class PowerWorkspaceAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "work").mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.server = create_server(port=0, db_path=Path(cls.temporary.name) / "power-api.sqlite3",
                                   provider_factory=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("No paid inference")))
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temporary.cleanup()

    def request(self, path, body=None, *, headers=None, raw=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=15)
        connection.request("GET" if body is None else "POST", path,
                           raw if raw is not None else None if body is None else json.dumps(body),
                           {"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        value, status, response_headers = response.read(), response.status, dict(response.getheaders())
        connection.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            value = json.loads(value)
        return status, value, response_headers

    def create(self):
        project = power_project("power-api-" + uuid4().hex)
        status, view, _ = self.request("/api/projects", {"project": project})
        self.assertEqual(status, 200, view)
        return view

    def run_workspace(self, view):
        status, current, _ = self.request("/api/run", {"project_id": view["project_id"], "revision": view["revision"]})
        self.assertEqual(status, 200, current)
        return current

    def test_catalog_exposes_dynamic_mode_contract_and_exact_power_energy_units(self):
        status, catalog, _ = self.request("/api/model-catalog")
        self.assertEqual(status, 200, catalog)
        matches = [row for row in catalog["models"] if row["type"] == "power_energy_budget"]
        self.assertEqual(len(matches), 1)
        power = matches[0]
        self.assertEqual(power["version"], engineering.MODEL_VERSIONS["power_energy_budget"])
        metrics = {row["name"]: row["unit"] for row in power["metrics"]}
        self.assertEqual(metrics["peak_load_power"], "W")
        self.assertEqual(metrics["battery_energy_required"], "J")
        self.assertEqual(metrics["minimum_power_margin"], "W")
        self.assertEqual(metrics["battery_energy_margin"], "J")
        self.assertEqual(metrics["total_duration"], "s")
        self.assertEqual(len(metrics), 12)
        self.assertTrue(power["assumptions"])
        self.assertTrue(any("charg" in line.lower() for line in power["not_assessed"]))
        # Dynamic roles must be discoverable; global capacity fields alone are
        # not a sufficient authoring contract for a sequential operating mode.
        encoded = json.dumps(power).lower()
        self.assertIn("mode", encoded)
        self.assertIn("count", encoded)
        self.assertIn("generation", encoded)

    def test_catalog_preflight_and_templates_are_read_only_and_never_run_physics(self):
        project = power_project("power-preflight-" + uuid4().hex)
        original = deepcopy(project)
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("Catalog must not calculate")):
            self.assertEqual(self.request("/api/model-catalog")[0], 200)
            status, result, _ = self.request("/api/authoring/preflight", {"project": project})
            self.assertEqual(status, 200, result)
            self.assertTrue(result["can_run"], result)
            status, templates, _ = self.request("/api/templates")
            self.assertEqual(status, 200)
        self.assertEqual(project, original)
        self.assertTrue(any(any(model["type"] == "power_energy_budget" for model in template["project"]["models"])
                            for template in templates["templates"]), templates)

    def test_power_mode_binding_errors_are_actionable_before_execution(self):
        for failure in ("missing_generation", "wrong_energy_unit", "unknown_metric", "unknown_role"):
            with self.subTest(failure=failure):
                project = power_project()
                if failure == "missing_generation":
                    del project["models"][-1]["inputs"]["mode.2.downlink.generation"]
                elif failure == "wrong_energy_unit":
                    project["inputs"]["usable_energy"]["unit"] = "Wh"
                elif failure == "unknown_metric":
                    project["requirements"][-1]["metric"] = "battery_state_of_charge"
                else:
                    project["models"][-1]["inputs"]["mode.1.cruise.launch_authorization"] = "one_unit"
                status, result, _ = self.request("/api/authoring/preflight", {"project": project})
                self.assertEqual(status, 200, result)
                self.assertFalse(result["can_run"], result)
                self.assertTrue(any(issue["severity"] == "error" and issue["path"].startswith("project.")
                                    for issue in result["issues"]))

    def test_run_export_preserves_budget_artifact_sources_and_separate_findings(self):
        current = self.run_workspace(self.create())
        query = "?" + urlencode({"project_id": current["project_id"], "revision": 1})
        status, exported, headers = self.request("/api/export" + query)
        self.assertEqual(status, 200, exported)
        self.assertIn("attachment; filename=", headers["Content-Disposition"])
        self.assertEqual(exported["run"], current["run"])
        power = exported["run"]["model_results"]["power"]
        self.assertEqual(power["metrics"]["battery_energy_required"], {"value": 5000, "unit": "J"})
        self.assertEqual(len(power["power_budget"]["modes"]), 2)
        self.assertEqual(power["power_budget"]["limits"], {
            "usable_battery_energy_j": 6000, "max_battery_power_w": 60, "bus_power_limit_w": 100})
        evidence = exported["run"]["review"]["evidence"]["power"]
        self.assertEqual(evidence["power_budget"], power["power_budget"])
        self.assertEqual(evidence["input_records"]["payload_count"]["value"], 2)
        self.assertEqual(evidence["verification_sources"], exported["run"]["review"]["verification_sources"])
        self.assertEqual(exported["run"]["live_model_calls"], 0)
        self.assertFalse(exported["run"]["review"]["launch_authorization"])

    def test_edit_duration_save_targeted_run_and_historic_http_read(self):
        original = self.run_workspace(self.create())
        changed = deepcopy(original["project"])
        changed["inputs"]["cruise_duration"]["value"] = 200
        payload = {"project_id": original["project_id"], "base_revision": 1, "project": changed}
        status, preview, _ = self.request("/api/impact", payload)
        self.assertEqual(status, 200, preview)
        self.assertEqual(preview["impact"]["affected_model_ids"], ["power"])
        status, saved, _ = self.request("/api/revisions", payload)
        self.assertEqual(status, 200, saved)
        self.assertIsNone(saved["run"])
        self.assertEqual(self.request("/api/export?" + urlencode({"project_id": original["project_id"], "revision": 2}))[0], 409)
        current = self.run_workspace(saved)
        self.assertEqual(current["run"]["executed_model_ids"], ["power"])
        self.assertEqual(current["run"]["review"]["findings"]["energy_capacity"]["status"], "not_met")
        self.assertEqual(current["run"]["review"]["findings"]["power_capacity"]["status"], "met")
        historical = self.request("/api/workspace?" + urlencode({"project_id": original["project_id"], "revision": 1}))[1]
        self.assertEqual(historical["run"], original["run"])

    def test_failed_budget_comparison_is_returned_as_engineering_result_not_http_error(self):
        created = self.create()
        changed = deepcopy(created["project"])
        changed["inputs"]["battery_power"]["value"] = 40
        status, saved, _ = self.request("/api/revisions", {"project_id": created["project_id"], "base_revision": 1, "project": changed})
        self.assertEqual(status, 200)
        current = self.run_workspace(saved)
        self.assertEqual(current["run"]["model_results"]["power"]["status"], "completed")
        self.assertEqual(current["run"]["review"]["findings"]["power_capacity"]["status"], "not_met")
        self.assertEqual(current["run"]["review"]["findings"]["energy_capacity"]["status"], "met")

    def test_new_capability_keeps_origin_and_runtime_mutation_guards(self):
        original = self.create()
        body = {"project_id": original["project_id"], "revision": 1}
        # This rejection occurs before reading a body. Send an empty payload so
        # Windows cannot race the server's deliberate close with unread bytes.
        self.assertEqual(self.request("/api/run", body, raw="", headers={"Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request("/api/run", {**body, "inference": True})[0], 400)
        with patch.object(workspace_server, "_code_fingerprint", return_value="changed-runtime"):
            status, result, _ = self.request("/api/run", body)
            self.assertEqual(status, 409, result)
            self.assertIn("Restart", result["error"])
        self.assertIsNone(self.request("/api/workspace?" + urlencode({"project_id": original["project_id"], "revision": 1}))[1]["run"])


if __name__ == "__main__":
    unittest.main()
