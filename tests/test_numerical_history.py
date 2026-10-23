from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import simulation,orbital_adapter as orbit,engineering,lifecycle
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore
from sixd.workspace_simulation import WorkspaceSimulation


class NumericalHistoryTests(unittest.TestCase):
    def test_legacy_v2_retains_its_method_policy_and_findings_without_integration(self):
        project=example_projects()['orbital_review']
        results=engineering.evaluate_models(project)
        model=project['models'][0];params=engineering._bind_inputs(project,model)
        metrics,a,q=orbit.evaluate_with_accuracy(params,model['accuracy'],method='velocity_verlet')
        results['orbit'].update(model_version='2',metrics=metrics,simulation=a,numerical_accuracy=q)
        with patch.dict(engineering.MODEL_VERSIONS,{'orbital_trajectory':'2'}):
            report=lifecycle.review_project(project,results)
        before=deepcopy(report)
        with patch.object(simulation,'simulate',side_effect=AssertionError('History cannot integrate')):
            self.assertTrue(lifecycle.verify_review(report))
        self.assertEqual(report,before)
        self.assertEqual(q['method']['expected_order'],2)

    def test_non_power_of_two_grid_pins_final_time_and_validates(self):
        from test_orbital_accuracy import parameters
        p=parameters(duration_s=444.4504652492591,steps=513)
        metrics,a=orbit.evaluate(p)
        self.assertEqual(a['samples'][-1]['time_s'],p['duration_s'])
        self.assertTrue(orbit.validate_artifact(a,metrics,p,simulation.source_fingerprint()))

    def test_large_standalone_history_reopens_without_current_solver(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            store=WorkspaceStore(Path(folder)/'test.sqlite3')
            view=store.create_project(example_projects()['orbital_review'])
            viewer=WorkspaceSimulation(store)
            spec=simulation.default_spec();spec.update(steps=16384,duration_s=spec['duration_s']*8)
            detail=viewer.run(view['project_id'],1,spec)
            identity=detail['receipt']['simulation_id']
            with patch.object(simulation,'simulate',side_effect=AssertionError('No integration')):
                self.assertEqual(viewer.get(identity)['receipt'],detail['receipt'])


if __name__=='__main__':unittest.main()
