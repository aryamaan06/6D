"""HTTP scenario intake, replay/export and local security boundaries."""
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
from sixd import simulation, workspace_server, workspace_simulation
from sixd.project_examples import example_projects
from sixd.workspace_server import create_server


class WorkspaceSimulationAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "work").mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.server = create_server(port=0, db_path=Path(cls.temporary.name) / "workspace.sqlite3",
                                  provider_factory=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("Simulation cannot invoke AI")))
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temporary.cleanup()

    def request(self, path, body=None, *, raw=None, headers=None, method=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = raw if raw is not None else None if body is None else json.dumps(body)
        connection.request(method or ("GET" if data is None else "POST"), path, data,
                           {"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        contents, response_headers, status = response.read(), dict(response.getheaders()), response.status
        connection.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            contents = json.loads(contents)
        return status, contents, response_headers

    def create(self, template="baseline"):
        project = deepcopy(example_projects()[template])
        project["project_id"] = "simulation-api-" + uuid4().hex
        status, view, _ = self.request("/api/projects", {"project": project})
        self.assertEqual(status, 200, view)
        return view

    def run_scenario(self, view, spec=None):
        return self.request("/api/simulations", {"project_id": view["project_id"], "revision": view["revision"],
                                                  "spec": spec or simulation.default_spec()})

    def test_create_replay_export_and_history_are_real_receipts_with_no_ai(self):
        view = self.create()
        query = "?" + urlencode({"project_id": view["project_id"], "revision": 1})
        status, initial, _ = self.request("/api/simulations" + query)
        self.assertEqual(status, 200, initial)
        self.assertEqual(initial["simulations"], [])
        self.assertEqual(initial["default_spec"], simulation.default_spec())
        status, detail, _ = self.run_scenario(view, initial["default_spec"])
        self.assertEqual(status, 200, detail)
        identity = detail["receipt"]["simulation_id"]
        self.assertEqual(detail["receipt"]["live_model_calls"], 0)
        self.assertEqual(self.request("/api/simulations/" + identity)[1], detail)
        status, exported, headers = self.request("/api/simulation-export?" + urlencode({"id": identity}))
        self.assertEqual(status, 200)
        self.assertEqual(exported, detail)
        self.assertIn(identity, headers["Content-Disposition"])
        self.assertEqual(self.request("/api/simulations" + query)[1]["simulations"][0]["simulation_id"], identity)
        after = self.request("/api/workspace" + query)[1]
        self.assertEqual(after, view)
        self.assertEqual(self.request("/api/ai/status")[1]["configured"], False)

    def test_project_template_run_playback_and_export_use_one_canonical_calculation(self):
        status, templates, _ = self.request("/api/templates")
        self.assertEqual(status, 200)
        self.assertIn("orbital_review", {row["id"] for row in templates["templates"]})
        view = self.create("orbital_review")
        query = "?" + urlencode({"project_id": view["project_id"], "revision": 1})
        initial = self.request("/api/simulations" + query)[1]
        self.assertEqual(initial["project_models"][0]["status"], "not_run")
        status, reviewed, _ = self.request("/api/run", {"project_id": view["project_id"], "revision": 1})
        self.assertEqual(status, 200, reviewed)
        with patch.object(simulation, "simulate", side_effect=AssertionError("Replay/export must not recompute")):
            status, listing, _ = self.request("/api/simulations" + query)
            self.assertEqual(status, 200, listing)
            identity = listing["project_models"][0]["simulation_id"]
            self.assertTrue(identity.startswith("p-"))
            status, detail, _ = self.request("/api/simulations/" + identity + "?revision=1")
            self.assertEqual(status, 200, detail)
            self.assertEqual(detail["receipt"]["result"], reviewed["run"]["model_results"]["orbit"]["simulation"])
            self.assertEqual(detail["receipt"]["review_digest"], reviewed["run"]["review"]["digest"])
            self.assertEqual(detail["receipt"]["binding_kind"], "project_model")
            status, exported, headers = self.request("/api/simulation-export?" + urlencode({"id": identity, "revision": 1}))
            self.assertEqual(status, 200, exported)
            self.assertEqual(exported, detail)
            self.assertIn(identity, headers["Content-Disposition"])
        with self.server.store._connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM runs WHERE project_id=?", (view["project_id"],)).fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM simulations WHERE project_id=?", (view["project_id"],)).fetchone()[0], 0)

    def test_project_playback_stays_historical_until_selected_revision_reviewed(self):
        view = self.create("orbital_review")
        status, first, _ = self.request("/api/run", {"project_id": view["project_id"], "revision": 1})
        self.assertEqual(status, 200, first)
        first_id = self.server.simulations.project_identity(first["run"]["run_id"], "orbit")
        project = deepcopy(view["project"])
        project["inputs"]["maximum_final_radius"]["value"] = 6.9e6
        self.assertEqual(self.request("/api/revisions", {"project_id": view["project_id"], "base_revision": 1, "project": project})[0], 200)
        query = "?" + urlencode({"project_id": view["project_id"], "revision": 2})
        listing = self.request("/api/simulations" + query)[1]
        self.assertEqual(listing["project_models"][0]["status"], "historical")
        self.assertIsNone(listing["project_models"][0]["simulation_id"])
        self.assertTrue(self.request("/api/simulations/" + first_id + "?revision=2")[1]["freshness"]["historical"])
        status, second, _ = self.request("/api/run", {"project_id": view["project_id"], "revision": 2})
        self.assertEqual(status, 200, second)
        second_id = self.server.simulations.project_identity(second["run"]["run_id"], "orbit")
        status, compare, _ = self.request("/api/simulation-comparison?" + urlencode({"left_id": first_id, "right_id": second_id}))
        self.assertEqual(status, 200, compare)
        self.assertTrue(compare["compatible"])
        self.assertEqual(compare["right"]["model_origin"]["run_id"], first["run"]["run_id"])
        self.assertEqual(self.request("/api/simulations/" + second_id + "?revision=1")[0], 400)

    def test_history_includes_earlier_revisions_with_explicit_context_and_guarded_comparison(self):
        view = self.create()
        first = self.run_scenario(view)[1]
        new_project = deepcopy(view["project"])
        new_project["inputs"]["heat_input"]["value"] = 710
        status, updated, _ = self.request("/api/revisions", {"project_id": view["project_id"], "base_revision": 1,
                                                             "project": new_project})
        self.assertEqual(status, 200)
        second = self.run_scenario(updated, {**simulation.default_spec(), "name": "Changed time window",
                                             "duration_s": simulation.default_spec()["duration_s"] / 2})[1]
        first_id, second_id = first["receipt"]["simulation_id"], second["receipt"]["simulation_id"]
        historical = self.request("/api/simulations/" + first_id)[1]
        self.assertTrue(historical["freshness"]["historical"])
        self.assertEqual(historical["freshness"]["context_revision"], 2)
        own_context = self.request("/api/simulations/" + first_id + "?revision=1")[1]
        self.assertFalse(own_context["freshness"]["historical"])
        compare_query = "?" + urlencode({"left_id": first_id, "right_id": second_id})
        status, comparison, _ = self.request("/api/simulation-comparison" + compare_query)
        self.assertEqual(status, 200)
        self.assertTrue(comparison["compatible"])
        self.assertTrue(comparison["left"]["historical"])
        self.assertFalse(comparison["same_duration"])
        query = "?" + urlencode({"project_id": view["project_id"], "revision": 2})
        self.assertEqual([s["revision"] for s in self.request("/api/simulations" + query)[1]["simulations"]], [2, 1])

    def test_invalid_simulation_requests_are_controlled_without_receipts(self):
        view = self.create()
        baseline = {"project_id": view["project_id"], "revision": 1, "spec": simulation.default_spec()}
        for payload in ({**baseline, "project_id": []}, {**baseline, "revision": True},
                        {**baseline, "revision": 2}, {**baseline, "spec": None},
                        {**baseline, "spec": {**baseline["spec"], "steps": 4097}},
                        {**baseline, "spec": {**baseline["spec"], "position_m": [1, 0, 0]}},
                        {**baseline, "provider": "live"}, {**baseline, "spec": {**baseline["spec"], "execute": "code"}}):
            with self.subTest(payload=payload):
                status, result, _ = self.request("/api/simulations", payload)
                self.assertEqual(status, 400, result)
        for path in ("/api/simulations?project_id=x&project_id=y&revision=1", "/api/simulations/not-an-id",
                     "/api/simulation-export", "/api/simulation-comparison", "/api/simulations?project_id=x"):
            self.assertEqual(self.request(path)[0], 400)
        self.assertEqual(self.request("/api/simulations", raw='{"project_id":"x","revision":1,"spec":NaN}')[0], 400)
        query = "?" + urlencode({"project_id": view["project_id"], "revision": 1})
        self.assertEqual(self.request("/api/simulations" + query)[1]["simulations"], [])

    def test_local_host_origin_and_runtime_guards_apply_to_simulation(self):
        view = self.create()
        body = {"project_id": view["project_id"], "revision": 1, "spec": simulation.default_spec()}
        # These header guards reject before consuming a request body. Empty
        # POSTs avoid an unread-upload connection reset on Windows.
        self.assertEqual(self.request("/api/simulations", raw="", headers={"Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request("/api/simulations", raw="", headers={"Host": "attacker.example"})[0], 403)
        with patch.object(workspace_server, "_code_fingerprint", return_value="changed"):
            self.assertEqual(self.request("/api/simulations", body)[0], 409)
        detail = self.run_scenario(view)[1]
        sources = {**workspace_simulation._LOADED_SOURCES, "simulation.py": "f" * 64}
        with patch.object(workspace_simulation, "_sources", return_value=sources):
            status, history, _ = self.request("/api/simulations/" + detail["receipt"]["simulation_id"])
            self.assertEqual(status, 200)
            self.assertTrue(history["freshness"]["historical"])
            self.assertEqual(history["receipt"], detail["receipt"])
            self.assertEqual(self.request("/api/simulations", body)[0], 409)

    def test_simulation_assets_are_allowed_but_source_and_private_storage_are_not(self):
        for route in ("/simulation.js", "/simulation.css"):
            # UI assets are supplied by the companion implementation task.
            self.assertIn(ROOT / "src" / "sixd" / "web" / route[1:], workspace_server.BUILD_FILES)
            if (ROOT / "src" / "sixd" / "web" / route[1:]).exists():
                self.assertEqual(self.request(route)[0], 200)
        self.assertIn(ROOT / "src" / "sixd" / "simulation.py", workspace_server.CODE_FILES)
        self.assertIn(ROOT / "src" / "sixd" / "workspace_simulation.py", workspace_server.CODE_FILES)
        for route in ("/workspace_simulation.py", "/simulation.py", "/api/simulations/../workspace.sqlite3"):
            self.assertIn(self.request(route)[0], (400, 404))


if __name__ == "__main__":
    unittest.main()
