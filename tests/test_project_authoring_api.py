"""HTTP authoring preserves incomplete work without inventing review evidence."""
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import workspace
from sixd.workspace_server import create_server


class ProjectAuthoringAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.server = create_server(port=0, db_path=Path(cls.temporary.name) / "workspace.sqlite3",
            provider_factory=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("No inference during authoring")))
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temporary.cleanup()

    def request(self, path, body=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        connection.request("GET" if body is None else "POST", path,
            body=None if body is None else json.dumps(body), headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        status, value = response.status, json.loads(response.read())
        connection.close()
        return status, value

    def blank(self):
        return {"schema": "sixd.project.v1", "project_id": "authored-" + uuid4().hex,
                "name": "A supplied space engineering project", "revision": "1",
                "description": "Constructed one-condition aerodynamic model; coefficient applicability requires review.",
                "lifecycle_stage": "design", "inputs": {}, "models": [], "requirements": []}

    def configured(self, blank):
        project = deepcopy(blank)
        project["inputs"] = {name: {"value": value, "unit": unit, "source": "Constructed API test input"}
            for name, value, unit in [("rho", 1, "kg/m^3"), ("speed", 10, "m/s"),
                ("cd", 1, "1"), ("area", 2, "m^2"), ("allowable", 150, "N")]}
        project["models"] = [{"id": "load", "type": "drag_load", "inputs": {
            "density": "rho", "relative_speed": "speed", "drag_coefficient": "cd", "reference_area": "area"}}]
        project["requirements"] = [{"id": "load_limit", "title": "Declared drag magnitude limit",
            "model_id": "load", "metric": "drag_force", "operator": "<=", "limit_input": "allowable", "critical": True}]
        return project

    def test_catalog_and_preflight_are_read_only_and_do_not_calculate(self):
        with self.server.store._connect() as connection:
            before = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("Preflight must not calculate")):
            status, catalog = self.request("/api/model-catalog")
            self.assertEqual(status, 200)
            self.assertEqual({m["type"] for m in catalog["models"]},
                {"ideal_propulsion", "static_cantilever", "radiative_equilibrium", "drag_load", "orbital_trajectory", "power_energy_budget", "attitude_control"})
            for model in catalog["models"]:
                self.assertTrue(model["parameters"])
                self.assertTrue(model["metrics"])
                self.assertTrue(all(set(parameter) == {"name", "unit"} for parameter in model["parameters"]))
            status, preflight = self.request("/api/authoring/preflight", {"project": self.blank()})
            self.assertEqual(status, 200)
            self.assertFalse(preflight["can_run"])
            self.assertEqual({issue["code"] for issue in preflight["issues"] if issue["severity"] == "error"},
                             {"empty_models", "empty_requirements"})
        with self.server.store._connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0], before)

    def test_empty_saved_project_reopens_but_cannot_generate_pass_or_export_review(self):
        project = self.blank()
        status, view = self.request("/api/projects", {"project": project})
        self.assertEqual(status, 200, view)
        self.assertIsNone(view["run"])
        self.assertEqual(view["project"], project)
        identity = project["project_id"]
        self.assertEqual(self.request("/api/run", {"project_id": identity, "revision": 1})[0], 400)
        self.assertEqual(self.request("/api/export?project_id=" + identity)[0], 409)
        with self.server.store._connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM runs WHERE project_id=?", (identity,)).fetchone()[0], 0)
        reopened = workspace.WorkspaceStore(self.server.store.db_path).get(identity, 1)
        self.assertEqual(reopened["project"], project)

    def test_custom_authoring_calculate_limit_change_and_history_share_evidence(self):
        blank = self.blank()
        identity = blank["project_id"]
        self.assertEqual(self.request("/api/projects", {"project": blank})[0], 200)
        project = self.configured(blank)
        preflight = self.request("/api/authoring/preflight", {"project": project})[1]
        self.assertTrue(preflight["can_run"], preflight)
        payload = {"project_id": identity, "base_revision": 1, "project": project}
        self.assertEqual(self.request("/api/impact", payload)[1]["impact"]["added_models"], ["load"])
        self.assertEqual(self.request("/api/revisions", payload)[0], 200)
        status, baseline = self.request("/api/run", {"project_id": identity, "revision": 2})
        self.assertEqual(status, 200, baseline)
        self.assertEqual(baseline["run"]["review"]["findings"]["load_limit"]["evidence"]["metric"],
                         {"value": 100, "unit": "N"})
        self.assertEqual(baseline["run"]["review"]["findings"]["load_limit"]["status"], "met")
        project = deepcopy(baseline["project"])
        project["inputs"]["allowable"]["value"] = 50
        self.assertEqual(self.request("/api/revisions", {"project_id": identity, "base_revision": 2, "project": project})[0], 200)
        revised = self.request("/api/run", {"project_id": identity, "revision": 3})[1]
        self.assertEqual(revised["run"]["executed_model_ids"], [])
        self.assertEqual(revised["run"]["reused_model_ids"], ["load"])
        self.assertEqual(revised["run"]["review"]["findings"]["load_limit"]["status"], "not_met")
        self.assertEqual(revised["run"]["model_origins"]["load"]["run_id"], baseline["run"]["run_id"])
        original = self.request("/api/workspace?project_id=" + identity + "&revision=2")[1]
        self.assertEqual(original["run"], baseline["run"])

    def test_dangling_deletion_refused_and_empty_revision_preserves_prior_review(self):
        project = self.configured(self.blank())
        identity = project["project_id"]
        self.request("/api/projects", {"project": project})
        original = self.request("/api/run", {"project_id": identity, "revision": 1})[1]
        invalid = deepcopy(project)
        del invalid["inputs"]["speed"]
        self.assertEqual(self.request("/api/revisions", {"project_id": identity, "base_revision": 1, "project": invalid})[0], 400)
        empty = deepcopy(project)
        empty.update(inputs={}, models=[], requirements=[])
        status, saved = self.request("/api/revisions", {"project_id": identity, "base_revision": 1, "project": empty})
        self.assertEqual(status, 200, saved)
        self.assertIsNone(saved["run"])
        self.assertEqual(saved["prior_run"]["run_id"], original["run"]["run_id"])
        self.assertEqual(self.request("/api/run", {"project_id": identity, "revision": 2})[0], 400)
        self.assertEqual(self.request("/api/workspace?project_id=" + identity + "&revision=1")[1]["run"], original["run"])

    def test_preflight_reports_bad_records_and_exact_body_contract(self):
        for malformed in ({}, {"project": {}, "extra": 1}):
            self.assertEqual(self.request("/api/authoring/preflight", malformed)[0], 400)
        for project in ([], {}, {"schema": "untrusted"}):
            status, result = self.request("/api/authoring/preflight", {"project": project})
            self.assertEqual(status, 200, result)
            self.assertFalse(result["can_run"])
            self.assertTrue(any(issue["code"] == "invalid_project" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
