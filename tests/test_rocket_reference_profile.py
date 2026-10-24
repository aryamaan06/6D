from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import engineering, powered_flight
from sixd.project_examples import integrated_rocket_review
from sixd.rocket_reference import profile_from_view, SUPPORTED_IDS
from sixd.workspace import WorkspaceStore


class RocketReferenceProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.store = WorkspaceStore(Path(cls.temp.name) / "workspace.sqlite3")
        cls.project = integrated_rocket_review()
        identity = cls.project["project_id"]
        cls.unrun = cls.store.create_project(cls.project)
        cls.baseline = cls.store.run(identity, 1)
        reduced = deepcopy(cls.baseline["project"])
        reduced["inputs"]["thrust"]["value"] = 11000
        cls.store.save_revision(identity, 1, reduced)
        cls.reduced = cls.store.run(identity, 2)
        corrected = deepcopy(cls.reduced["project"])
        corrected["inputs"]["thrust"]["value"] = 20000
        cls.store.save_revision(identity, 2, corrected)
        cls.corrected = cls.store.run(identity, 3)

    def test_stages_use_saved_configuration_and_current_record(self):
        for view, stage, next_thrust in ((self.baseline,"baseline",11000),
                                       (self.reduced,"reduced",20000),
                                       (self.corrected,"corrected",None)):
            with self.subTest(stage=stage):
                result = profile_from_view(view)
                self.assertTrue(result["recognized"])
                self.assertEqual(result["stage"], stage)
                self.assertEqual(result["next_thrust"], next_thrust)
                self.assertEqual(result["can_stage"], next_thrust is not None)
                self.assertEqual(result["run_id"], view["run"]["run_id"])
                self.assertEqual(result["project_id"], view["project_id"])
                self.assertEqual(result["revision"], view["revision"])

    def test_execution_and_reuse_are_actual_receipt_projections(self):
        for view in (self.baseline,self.reduced,self.corrected):
            result = profile_from_view(view)
            for key in ("executed_model_ids","reused_model_ids"):
                self.assertEqual(result[key], [x for x in view["run"][key] if x in SUPPORTED_IDS])
            self.assertNotIn("launch_gnc", result["model_origins"])
        result = profile_from_view(self.reduced)
        self.assertEqual(set(result["executed_model_ids"]), set(SUPPORTED_IDS) - {"thermal"})
        self.assertEqual(result["reused_model_ids"], ["thermal"])
        self.assertEqual(result["model_origins"]["thermal"]["run_id"], self.baseline["run"]["run_id"])
        result["model_origins"]["thermal"]["revision"] = 999
        self.assertEqual(self.reduced["run"]["model_origins"]["thermal"]["revision"], 1)

    def test_template_import_metadata_and_browser_number_roundtrip_are_recognized(self):
        project = json.loads(json.dumps(self.project))
        project.update(project_id="my-imported-reference", name="My named reference", revision="29")
        for record in project["inputs"].values():
            if float(record["value"]).is_integer():
                record["value"] = int(record["value"])
        view = dict(project_id=project["project_id"],revision=29,latest_revision=29,
                    project=project,run=None,prior_run=None)
        result = profile_from_view(view)
        self.assertTrue(result["recognized"])
        self.assertFalse(result["can_stage"])

    def test_any_nonrecipe_engineering_edit_disables_guided_changes(self):
        def changed_source(p): p["inputs"]["thrust"]["source"] = "A new supplied source"
        def changed_unit(p): p["inputs"]["thrust"]["unit"] = "kN"
        def changed_limit(p): p["inputs"]["minimum_burnout_altitude"]["value"] = 4000
        def changed_thrust(p): p["inputs"]["thrust"]["value"] = 13000
        def changed_model(p): p["models"][0]["description"] = "A new model assumption"
        def changed_link(p):
            next(x for x in p["models"] if x["id"] == "atmospheric_load")["links"]["relative_speed"]["rationale"] = "A different screening assumption"
        def changed_system(p): p["systems"][0]["description"] = "A different scope"
        for edit in (changed_source,changed_unit,changed_limit,changed_thrust,changed_model,changed_link,changed_system):
            with self.subTest(edit=edit.__name__):
                view = deepcopy(self.baseline)
                edit(view["project"])
                result = profile_from_view(view)
                self.assertFalse(result["recognized"])
                self.assertFalse(result["can_stage"])
                self.assertIsNone(result["next_thrust"])

    def test_historical_revision_and_unrun_or_stale_results_cannot_stage(self):
        historical = self.store.get(self.project["project_id"], 1)
        self.assertEqual(historical["latest_revision"], 3)
        cases = [self.unrun,historical]
        stale = deepcopy(self.baseline)
        stale["run"]["stale"] = True
        cases.append(stale)
        old_sources = deepcopy(self.baseline)
        old_sources["run"]["review"]["verification_sources"]["engineering.py"] = "0" * 64
        cases.append(old_sources)
        wrong_run = deepcopy(self.baseline)
        wrong_run["run"]["revision"] = 2
        cases.append(wrong_run)
        wrong_project = deepcopy(self.baseline)
        wrong_project["run"]["review"]["project"]["name"] = "Different configuration context"
        cases.append(wrong_project)
        for view in cases:
            with self.subTest(reason=profile_from_view(view)["reason"]):
                self.assertFalse(profile_from_view(view)["can_stage"])

    def test_restored_label_requires_recorded_reduced_case_under_same_verifier(self):
        without_prior = deepcopy(self.corrected)
        without_prior["prior_run"] = None
        self.assertEqual(profile_from_view(without_prior)["stage"], "baseline")
        changed_prior = deepcopy(self.corrected)
        changed_prior["prior_run"]["review"]["verification_sources"]["engineering.py"] = "0" * 64
        self.assertEqual(profile_from_view(changed_prior)["stage"], "baseline")
        different_project = deepcopy(self.corrected)
        different_project["prior_run"]["project_id"] = "unrelated-reference"
        self.assertEqual(profile_from_view(different_project)["stage"], "baseline")

    def test_projection_never_calculates_or_mutates_the_view(self):
        view = deepcopy(self.corrected)
        before = deepcopy(view)
        with patch.object(engineering, "evaluate_models", side_effect=AssertionError("No calculation")), \
             patch.object(powered_flight, "evaluate", side_effect=AssertionError("No calculation")), \
             patch.object(self.store, "save_revision", side_effect=AssertionError("No write")), \
             patch.object(self.store, "run", side_effect=AssertionError("No calculation")):
            result = profile_from_view(view)
        self.assertEqual(view, before)
        self.assertTrue(result["recognized"])
        self.assertTrue(any("not simultaneous" in line for line in result["scope"]))
        self.assertTrue(any("unassessed" in line for line in result["scope"]))


if __name__ == "__main__":
    unittest.main()
