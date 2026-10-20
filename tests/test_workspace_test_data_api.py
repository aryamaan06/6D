"""Real local HTTP intake and comparison without solver or paid execution."""
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
from sixd.workspace_server import create_server
from sixd.project_examples import example_projects
from sixd import engineering, workspace

MAPPING = {key: key for key in ("measurement_id", "requirement_id", "value", "unit", "tolerance")}
CSV = 'measurement_id,requirement_id,value,unit,tolerance,comment\nA,drag_limit,310,N,15,"Quoted, source\n=1+1"\n'


def spec(csv_text=CSV):
    return {"schema": "sixd.test-comparison-spec.v1", "name": "Supplied scalar observations",
            "source": "Constructed HTTP acceptance data, no physical test.", "data_kind": "synthetic",
            "test_conditions": "Static drag force at density 1.2 kg/m^3, speed 50 m/s, Cd 0.8, area 0.25 m^2; same scalar definition as the saved model.",
            "conditions_match": "declared_match", "filename": "observations.csv",
            "csv_text": csv_text, "mapping": deepcopy(MAPPING)}


class TestDataAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        def forbidden(*args, **kwargs):
            raise AssertionError("No paid provider in test-data HTTP acceptance")
        cls.server = create_server(port=0, db_path=Path(cls.tmp.name)/"workspace.sqlite3",
                                   ai_local_directory=Path(cls.tmp.name), provider_factory=forbidden)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.worker.join(); cls.tmp.cleanup()

    def request(self, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        connection.request("GET" if body is None else "POST", path,
                           None if body is None else json.dumps(body),
                           {"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        status, response_headers, raw = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, json.loads(raw) if response_headers.get("Content-Type", "").startswith("application/json") else raw, response_headers

    def baseline(self, run=True):
        project = example_projects()["baseline"]
        project["project_id"] = "test-data-http-" + uuid4().hex
        for identity, value in (("density", 1.2), ("relative_speed", 50), ("drag_coefficient", .8), ("reference_area", .25), ("maximum_drag_force", 305)):
            project["inputs"][identity]["value"] = value
        self.assertEqual(self.request("/api/projects", {"project": project})[0], 200)
        if run:
            status, view, _ = self.request("/api/run", {"project_id": project["project_id"], "revision": 1})
            self.assertEqual(status, 200, view)
            self.assertEqual(view["run"]["model_results"]["atmospheric_load"]["metrics"]["drag_force"]["value"], 300)
        else:
            view = self.server.store.get(project["project_id"], 1)
        return view

    def save(self, view, value=None):
        return self.request("/api/test-comparisons", {"project_id": view["project_id"], "revision": 1,
            "baseline_run_id": view["run"]["run_id"], "spec": spec() if value is None else value})

    def test_preview_preserves_quoted_multiline_and_formula_text_without_storing(self):
        with self.server.store._connect() as connection:
            count = connection.execute("SELECT count(*) FROM test_comparisons").fetchone()[0]
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("No solver")), \
                patch.object(workspace, "evaluate_models", side_effect=AssertionError("No solver")):
            status, result, _ = self.request("/api/test-data/preview", {"filename": "test.csv", "csv_text": CSV, "mapping": MAPPING})
        self.assertEqual(status, 200, result)
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["raw_preview"][0]["comment"], "Quoted, source\n=1+1")
        self.assertEqual(result["rows"][0]["value"], 310)
        with self.server.store._connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM test_comparisons").fetchone()[0], count)

    def test_separate_findings_and_roundtrip_export_preserve_baseline(self):
        view = self.baseline()
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("No solver")), \
                patch.object(workspace, "evaluate_models", side_effect=AssertionError("No solver")):
            status, result, _ = self.save(view)
            self.assertEqual(status, 200, result)
            receipt = result["receipt"]
            row = receipt["row_results"][0]
            self.assertEqual(row["measurement_requirement"]["status"], "not_met")
            self.assertEqual(row["prediction_agreement"]["status"], "within_tolerance")
            self.assertEqual(row["prediction_agreement"]["signed_difference"], 10)
            self.assertEqual(row["prediction_agreement"]["absolute_difference"], 10)
            self.assertEqual(receipt["spec"]["csv_text"], CSV)
            identity = receipt["comparison_id"]
            self.assertEqual(self.request(f"/api/test-comparisons/{identity}?revision=1")[1], result)
            status, exported, headers = self.request(f"/api/test-comparison-export?id={identity}&revision=1")
            self.assertEqual(status, 200)
            self.assertEqual(exported, result)
            self.assertIn("attachment; filename=", headers["Content-Disposition"])
            listing = self.request("/api/test-comparisons?" + urlencode({"project_id": view["project_id"], "revision": 1}))[1]
            self.assertEqual(listing["comparisons"][0]["comparison_id"], identity)
            self.assertEqual(self.server.store.get(view["project_id"], 1), view)
            self.assertEqual(receipt["live_model_calls"], 0)

    def test_unknown_conditions_and_bad_units_remain_unassessed(self):
        view = self.baseline()
        for value in ({**spec(), "conditions_match": "unknown"}, {**spec(), "test_conditions": ""},
                      spec(CSV.replace(",310,N,15,", ",310,mN,15,"))):
            with self.subTest(value=value["conditions_match"]):
                status, result, _ = self.save(view, value)
                self.assertEqual(status, 200, result)
                row = result["receipt"]["row_results"][0]
                self.assertEqual(row["measurement_requirement"]["status"], "not_assessed")
                self.assertEqual(row["prediction_agreement"]["status"], "not_assessed")

    def test_missing_tolerance_blocks_only_agreement(self):
        view = self.baseline()
        status, result, _ = self.save(view, spec(CSV.replace(",310,N,15,", ",310,N,,")))
        self.assertEqual(status, 200, result)
        row = result["receipt"]["row_results"][0]
        self.assertEqual(row["measurement_requirement"]["status"], "not_met")
        self.assertEqual(row["prediction_agreement"]["status"], "not_assessed")

    def test_import_guards_and_static_assets(self):
        body = {"filename": "x.csv", "csv_text": CSV, "mapping": MAPPING}
        self.assertEqual(self.request("/api/test-data/preview", {**body, "extra": True})[0], 400)
        self.assertEqual(self.request("/api/test-data/preview", body, {"Origin": "https://example.org"})[0], 403)
        self.assertEqual(self.request("/api/test-data/preview", {**body, "csv_text": "x,x\n1,2"})[0], 400)
        self.assertEqual(self.request("/api/test-comparisons/no-id")[0], 400)
        unreviewed = self.baseline(run=False)
        self.assertEqual(self.request("/api/test-comparisons", {"project_id": unreviewed["project_id"],
            "revision": 1, "baseline_run_id": "0"*32, "spec": spec()})[0], 409)
        for path in ("/test-data.js", "/test-data.css"):
            self.assertEqual(self.request(path)[0], 200)


if __name__ == "__main__":
    unittest.main()
