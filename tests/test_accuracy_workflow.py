"""Accuracy deficiencies cannot become passing engineering evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import engineering, lifecycle, simulation
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore
from sixd.project_authoring import preflight, catalog


class AccuracyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.project = example_projects()['orbital_review']

    def review(self, project=None):
        project = project or self.project
        return lifecycle.review_project(project, engineering.evaluate_models(project))

    def test_missing_criteria_preserves_diagnostic_trajectory_but_no_comparison_pass(self):
        self.project['models'][0].pop('accuracy')
        report = self.review()
        self.assertTrue(lifecycle.verify_review(report))
        self.assertEqual(report['evidence']['orbit']['status'], 'completed')
        self.assertTrue(report['evidence']['orbit']['simulation']['samples'])
        self.assertEqual(report['review_status'], 'incomplete')
        for finding in report['findings'].values():
            if finding['model_id'] == 'orbit':
                self.assertEqual(finding['assessment_status'], 'accuracy_not_assessed')
                self.assertEqual(finding['status'], 'not_assessed')
                self.assertIsNone(finding['evidence'])
        self.assertEqual(report['findings']['thermal_limit']['status'], 'met')
        self.assertIn('orbital_accuracy_missing', {issue['code'] for issue in preflight(self.project)['issues']})

    def test_supported_grid_and_clear_criterion_failure_stay_distinct(self):
        self.project['inputs']['maximum_sampled_radius']['value'] = 6_900_000
        report = self.review()
        self.assertEqual(report['evidence']['orbit']['numerical_accuracy']['status'], 'supported')
        self.assertEqual(report['findings']['orbit_max_radius']['status'], 'not_met')
        self.assertEqual(report['findings']['orbit_min_radius']['status'], 'met')

    def test_tight_tolerances_block_all_orbital_criteria(self):
        self.project['models'][0]['accuracy']['position_tolerance_m'] = 1e-8
        report = self.review()
        self.assertEqual(report['evidence']['orbit']['numerical_accuracy']['status'], 'insufficient_accuracy')
        self.assertEqual(report['findings']['orbit_max_radius']['assessment_status'], 'insufficient_accuracy')
        self.assertIsNone(report['findings']['orbit_max_radius']['evidence'])

    def test_near_limit_and_exact_equality_do_not_receive_a_pass(self):
        results = engineering.evaluate_models(self.project)
        metric = results['orbit']['metrics']['max_radius_m']['value']
        self.project['inputs']['maximum_sampled_radius']['value'] = metric + 100
        report = lifecycle.review_project(self.project, results)
        self.assertEqual(report['findings']['orbit_max_radius']['assessment_status'], 'insufficient_accuracy')
        self.project['inputs']['maximum_sampled_radius']['value'] = metric
        next(r for r in self.project['requirements'] if r['id'] == 'orbit_max_radius')['operator'] = '=='
        report = lifecycle.review_project(self.project, results)
        self.assertEqual(report['findings']['orbit_max_radius']['status'], 'not_assessed')

    def test_allowance_boundaries_handle_inclusive_pass_and_ambiguous_failure(self):
        result = {'model_type': 'orbital_trajectory', 'model_version': '2', 'numerical_accuracy': {
            'status': 'supported', 'criteria': {'position_tolerance_m': 2, 'velocity_tolerance_m_s': .1}}}
        for operator, value, limit, unresolved in [('<=', 8, 10, False), ('<=', 12, 10, True),
                                                   ('>=', 12, 10, False), ('>=', 8, 10, True)]:
            with self.subTest(operator=operator, value=value):
                gap = engineering.requirement_accuracy_gap(result, {'operator': operator}, {'value': value, 'unit': 'm'}, {'value': limit})
                self.assertEqual(gap is not None, unresolved)

    def test_criteria_must_be_explicit_finite_positive_and_orbital_only(self):
        for bad in [None, {}, {'position_tolerance_m': True, 'velocity_tolerance_m_s': 1, 'source': 'test'},
                    {'position_tolerance_m': 1, 'velocity_tolerance_m_s': 0, 'source': 'test'},
                    {'position_tolerance_m': float('nan'), 'velocity_tolerance_m_s': 1, 'source': 'test'}]:
            project = deepcopy(self.project)
            project['models'][0]['accuracy'] = bad
            with self.subTest(criteria=bad), self.assertRaises(ValueError):
                lifecycle.validate_project(project)
        self.project['models'][1]['accuracy'] = self.project['models'][0]['accuracy']
        with self.assertRaises(ValueError):
            lifecycle.validate_project(self.project)

    def test_v2_cannot_omit_receipt_and_reference_context_cannot_claim_physical_validation(self):
        results = engineering.evaluate_models(self.project)
        omitted = deepcopy(results)
        omitted['orbit'].pop('numerical_accuracy')
        with self.assertRaisesRegex(ValueError, 'accuracy receipt'):
            lifecycle.review_project(self.project, omitted)
        results['thermal']['applicability']['physical_applicability'] = 'validated'
        with self.assertRaisesRegex(ValueError, 'physical applicability'):
            lifecycle.review_project(self.project, results)
        self.assertEqual(len(catalog()['models']), 8)

    def test_legacy_v1_history_is_not_rewritten_or_rerun(self):
        self.project['models'][0].pop('accuracy')
        results = engineering.evaluate_models(self.project)
        from sixd import orbital_adapter
        params = engineering._bind_inputs(self.project, self.project['models'][0])
        metrics, artifact = orbital_adapter.evaluate(params, method='velocity_verlet')
        results['orbit']['metrics'] = metrics
        results['orbit']['simulation'] = artifact
        results['orbit']['model_version'] = '1'
        results['orbit'].pop('numerical_accuracy')
        with patch.dict(engineering.MODEL_VERSIONS, {'orbital_trajectory': '1'}):
            old = lifecycle.review_project(self.project, results)
        preserved = deepcopy(old)
        self.assertEqual(old['findings']['orbit_max_radius']['status'], 'met')
        with patch.object(simulation, 'simulate', side_effect=AssertionError('History cannot rerun')):
            self.assertTrue(lifecycle.verify_review(old))
        self.assertEqual(old, preserved)

    def test_deficient_orbit_cannot_feed_a_calculation_chain(self):
        self.project['models'][0].pop('accuracy')
        for key, value, unit in [('rho', 1, 'kg/m^3'), ('cd', 1, '1'), ('area', 1, 'm^2')]:
            self.project['inputs'][key] = {'value': value, 'unit': unit, 'source': 'Constructed chain test'}
        self.project['models'].append({'id': 'drag', 'type': 'drag_load',
            'inputs': {'density': 'rho', 'drag_coefficient': 'cd', 'reference_area': 'area'},
            'links': {'relative_speed': {'model_id': 'orbit', 'metric': 'final_speed_m_s', 'unit': 'm/s',
                        'rationale': 'Constructed scalar transfer to exercise the accuracy guard, not an atmospheric flight claim.'}}})
        results = engineering.evaluate_models(self.project)
        self.assertEqual(results['drag']['status'], 'not_assessed')
        self.assertEqual(results['drag']['metrics'], {})
        self.assertTrue(lifecycle.verify_review(lifecycle.review_project(self.project, results)))

    def test_criteria_edit_targets_orbit_reuses_thermal_and_equals_full_recompute(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as directory:
            store = WorkspaceStore(Path(directory) / 'workspace.sqlite3')
            identity = self.project['project_id']
            store.create_project(self.project)
            first = store.run(identity, 1)['run']
            changed = deepcopy(self.project)
            changed['models'][0]['accuracy']['position_tolerance_m'] = 1e-8
            preview = store.preview_change(identity, 1, changed)
            self.assertIn('orbit', preview['affected_model_ids'])
            store.save_revision(identity, 1, changed)
            second = store.run(identity, 2)['run']
            self.assertEqual(second['executed_model_ids'], ['orbit'])
            self.assertEqual(second['reused_model_ids'], ['thermal'])
            self.assertEqual(second['review'], self.review(second['review']['project']))
            self.assertEqual(store.get(identity, 1)['run']['review'], first['review'])


if __name__ == '__main__':
    unittest.main()
