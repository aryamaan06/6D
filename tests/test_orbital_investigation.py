"""Orbital investigations preserve exact local evidence with bounded wire context."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import lifecycle, project_investigation as engine
from sixd.engineering import evaluate_models
from sixd.explanation_quality import build_guidance
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore
from test_project_investigation import ScriptProvider


class OrbitalInvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.temporary.cleanup)
        self.store = WorkspaceStore(Path(self.temporary.name) / "test.sqlite3")
        project = example_projects()["orbital_review"]
        self.store.create_project(project)
        self.view = self.store.run(project["project_id"], 1)
        self.requirement = next(r for r in project["requirements"] if r["model_id"] == "orbit")

    def investigate(self, view=None):
        provider = ScriptProvider()
        record = engine.investigate_project(view or self.view, self.requirement["id"],
            "Explain the sampled orbital criterion and what to review next.", provider,
            investigation_id="offline-orbital-investigation")
        return record, provider

    def test_same_adapter_recheck_preserves_full_evidence_and_compacts_only_wire(self):
        original = deepcopy(self.view)
        with patch.object(engine, "evaluate_models", wraps=evaluate_models) as calculator:
            record, provider = self.investigate()
        self.assertEqual(record["state"], "completed")
        self.assertEqual(record["live_model_calls"], 0)
        self.assertEqual(calculator.call_count, 1)
        self.assertEqual([m["id"] for m in calculator.call_args.args[0]["models"]], ["orbit"])
        artifact = original["run"]["model_results"]["orbit"]["simulation"]
        self.assertEqual(record["evidence"]["model:orbit"]["recorded_evidence"]["simulation"], artifact)
        recheck = record["evidence"]["recheck:orbit"]
        self.assertTrue(recheck["matches_saved_result"])
        self.assertEqual(recheck["fresh_result"]["simulation"], artifact)
        self.assertEqual(self.store.get(original["project_id"], 1), original)
        projections = []
        for history in provider.histories:
            for message in history:
                if message["role"] != "tool":
                    continue
                payload = json.loads(message["content"])
                for name in ("recorded_evidence", "fresh_result"):
                    result = payload.get(name, {})
                    if "simulation_summary_projection" in result:
                        self.assertNotIn("simulation", result)
                        self.assertLess(len(message["content"]), 24000)
                        self.assertEqual(payload["run_id"], original["run"]["run_id"])
                        projections.append(result["simulation_summary_projection"])
        self.assertTrue(projections)
        for projection in projections:
            self.assertEqual(projection["artifact_digest"], lifecycle._digest(artifact))
            self.assertEqual(projection["summary"], artifact["summary"])
            self.assertLessEqual(len(projection["witness_samples"]), 5)
            self.assertIn("not this projection", projection["projection_note"])
            for witness in projection["witness_samples"]:
                self.assertEqual({k: v for k, v in witness.items() if k != "sample_index"},
                                 artifact["samples"][witness["sample_index"]])

    def test_guidance_explicitly_limits_sampled_extrema_and_reproducibility(self):
        guidance = build_guidance(self.view["project"], self.view["run"]["review"], self.requirement["id"])
        text = json.dumps(guidance)
        for phrase in ("between samples", "independent reference", "same-adapter", "time window", "perturbations"):
            self.assertIn(phrase, text)
        self.assertEqual(guidance["canonical_assessment"]["criterion"],
            self.view["run"]["review"]["findings"][self.requirement["id"]]["evidence"])

    def test_unreviewed_changed_state_cannot_be_investigated(self):
        project = deepcopy(self.view["project"])
        binding = next(m for m in project["models"] if m["id"] == "orbit")["inputs"]["duration_s"]
        project["inputs"][binding]["value"] *= 0.75
        view = self.store.save_revision(project["project_id"], 1, project)
        provider = ScriptProvider()
        with self.assertRaises(ValueError):
            engine.investigate_project(view, self.requirement["id"], "Explain", provider,
                                      investigation_id="offline-blocked")
        self.assertEqual(provider.request_attempts, 0)

    def test_invalid_orbit_remains_an_evidence_gap_after_recheck(self):
        project = deepcopy(self.view["project"])
        binding = next(m for m in project["models"] if m["id"] == "orbit")["inputs"]["steps"]
        project["inputs"][binding]["value"] = 16
        self.store.save_revision(project["project_id"], 1, project)
        view = self.store.run(project["project_id"], 2)
        record, _ = self.investigate(view)
        self.assertEqual(record["state"], "completed")
        self.assertEqual(record["finding_status"], "not_assessed")
        self.assertTrue(record["evidence"]["recheck:orbit"]["matches_saved_result"])
        self.assertNotIn("simulation", record["evidence"]["recheck:orbit"]["fresh_result"])
        self.assertEqual(record["live_model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
