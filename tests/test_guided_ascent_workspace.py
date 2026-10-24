"""Guided ascent participates in revision, scope, chain and AI evidence contracts."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import (engineering, lifecycle, guided_ascent, project_authoring,
                 project_investigation, explanation_quality, evidence_roles)
from sixd.project_examples import integrated_rocket_review, powered_flight_review
from sixd.providers import Turn
from sixd.workspace import WorkspaceStore, WorkspaceError
from sixd.workspace_coverage import WorkspaceCoverage
from sixd.workspace_scenarios import WorkspaceScenarios
from sixd.workspace_test_data import WorkspaceTestData
from sixd.test_evidence import TestEvidence


def fixture():
    project = integrated_rocket_review()
    project.update(project_id='constructed-guided-workspace', name='Constructed planar ascent review',
                   description='Declared planar pitch programme with separate scalar load screens; no closed-loop launch GNC.')
    model = next(row for row in project['models'] if row['id'] == 'vertical_flight')
    model.update(type='guided_ascent', description='Prescribed pitch in an inertial plane, not closed-loop guidance.')
    for key, value in dict(pitch_start_time=5, pitch_end_time=25,
                           initial_pitch_angle=0, final_pitch_angle=.6).items():
        project['inputs'][key] = dict(value=value, unit=guided_ascent.PARAMETERS[key],
                                      source='Constructed open-loop steering input, not measured flight data.')
        model['inputs'][key] = key
    project['inputs']['steps']['value'] = 32
    requirement = next(row for row in project['requirements'] if row['id'] == 'upward_acceleration')
    requirement.update(metric='max_sampled_acceleration', title='Maximum sampled inertial acceleration magnitude')
    return project


class GuidedProvider:
    mode = 'offline_transport_fixture'
    model = 'offline-guided-workflow-test'
    def __init__(self):
        self.request_attempts = 0
    def complete(self, messages, tools):
        self.request_attempts += 1
        available = {tool['function']['name']: tool for tool in tools}
        required = json.loads(messages[1]['content'])['required_actions']
        action = next(name for name in ('read_requirement', 'read_model', 'read_changes', 'recheck_model', 'finish')
                      if name in available and (name != 'read_changes' or name in required))
        arguments = {}
        if action == 'finish':
            arguments = dict(evidence_ids=available[action]['function']['parameters']['properties']['evidence_ids']['items']['enum'],
                             summary='The criterion is met within the declared planar ascent model. Verify the pitch-angle convention, steering times, thrust and atmosphere sources. Inspect the retained vector-state grid comparisons and burnout event, then compare with an independent trajectory analysis. The pitch programme is prescribed; closed-loop guidance, navigation, actuator tracking, staging, aeroheating, landing and physical model validity remain unassessed.')
        return Turn({'role': 'assistant', 'content': None, 'tool_calls': [dict(id='guided-'+str(self.request_attempts),
                    type='function', function=dict(name=action, arguments=json.dumps(arguments)))]},
                    dict(prompt_tokens=10, completion_tokens=10))


class GuidedAscentWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.store = WorkspaceStore(Path(cls.temporary.name) / 'workspace.sqlite3')
        cls.project = fixture()
        cls.identity = cls.project['project_id']
        cls.store.create_project(cls.project)
        cls.baseline = cls.store.run(cls.identity, 1)
        draft = deepcopy(cls.baseline['project'])
        draft['inputs']['final_pitch_angle']['value'] = 1.1
        with patch.object(guided_ascent, 'evaluate', side_effect=AssertionError('Preview cannot calculate')):
            cls.impact = cls.store.preview_change(cls.identity, 1, draft)
        cls.saved = cls.store.save_revision(cls.identity, 1, draft)
        cls.revised = cls.store.run(cls.identity, 2)

    def test_saved_artifact_scope_and_unsupported_launch_gnc(self):
        review = self.baseline['run']['review']
        self.assertTrue(lifecycle.verify_review(review))
        artifact = review['evidence']['vertical_flight']['guided_response']
        self.assertEqual(artifact['frame']['id'], 'body_centered_inertial_plane')
        self.assertGreater(self.baseline['run']['model_results']['vertical_flight']['metrics']['burnout_downrange']['value'], 2000)
        self.assertEqual(review['findings']['launch_guidance']['status'], 'not_assessed')
        self.assertFalse(review['launch_authorization'])
        self.assertEqual(self.baseline['run']['live_model_calls'], 0)

    def test_catalog_preflight_and_coverage_describe_bounded_translation(self):
        catalog = next(row for row in project_authoring.catalog()['models'] if row['type'] == 'guided_ascent')
        self.assertEqual({row['name']: row['unit'] for row in catalog['parameters']}, guided_ascent.PARAMETERS)
        with patch.object(guided_ascent, 'evaluate', side_effect=AssertionError('Preflight cannot calculate')):
            self.assertTrue(project_authoring.preflight(self.project)['can_run'])
            coverage = WorkspaceCoverage(self.store).summary(self.identity, 1)
        row = next(row for row in coverage['checks'] if row['requirement_id'] == 'burnout_height')
        self.assertEqual(row['discipline'], 'Flight dynamics')
        self.assertEqual(row['coverage_status'], 'applicability_unknown')

    def test_steering_edit_reruns_transitive_chain_reuses_unaffected_models(self):
        self.assertEqual(set(self.impact['affected_model_ids']), {'vertical_flight', 'atmospheric_load', 'mount'})
        self.assertIsNone(self.saved['run'])
        result = self.revised['run']
        self.assertEqual(set(result['executed_model_ids']), {'vertical_flight', 'atmospheric_load', 'mount'})
        self.assertIn('propulsion', result['reused_model_ids'])
        self.assertIn('thermal', result['reused_model_ids'])
        self.assertEqual(result['model_origins']['thermal']['run_id'], self.baseline['run']['run_id'])
        self.assertEqual(result['review']['findings']['burnout_height']['status'], 'not_met')
        full = lifecycle.review_project(self.revised['project'], engineering.evaluate_models(self.revised['project']))
        self.assertEqual(result['review'], full)
        self.assertEqual(self.store.get(self.identity, 1)['run']['review'], self.baseline['run']['review'])

    def test_history_read_does_not_integrate_or_borrow_current_results(self):
        with patch.object(guided_ascent, 'evaluate', side_effect=AssertionError('History cannot integrate')):
            old = self.store.get(self.identity, 1)
            new = self.store.get(self.identity, 2)
        self.assertEqual(old['run']['review'], self.baseline['run']['review'])
        self.assertEqual(new['run']['review'], self.revised['run']['review'])
        self.assertNotEqual(old['run']['run_id'], new['run']['run_id'])

    def test_failed_vector_grid_agreement_blocks_linked_screen_and_structure(self):
        project = fixture()
        for key, value in dict(steps=8, altitude_numerical_tolerance=1e-12,
                               velocity_numerical_tolerance=1e-12, relative_numerical_tolerance=0).items():
            project['inputs'][key]['value'] = value
        results = engineering.evaluate_models(project)
        self.assertEqual(results['vertical_flight']['status'], 'completed')
        self.assertIsNotNone(engineering.evidence_accuracy_gap(results['vertical_flight']))
        for identity in ('atmospheric_load', 'mount'):
            self.assertEqual(results[identity]['status'], 'not_assessed')
            self.assertEqual(results[identity]['metrics'], {})
        review = lifecycle.review_project(project, results)
        self.assertEqual(review['findings']['burnout_height']['status'], 'not_assessed')
        guidance = explanation_quality.build_guidance(project, review, 'burnout_height')
        self.assertIn('planar', json.dumps(guidance).lower())
        self.assertTrue(lifecycle.verify_review(review))

    def test_numerical_allowance_prevents_near_threshold_pass(self):
        project = deepcopy(self.baseline['project'])
        results = deepcopy(self.baseline['run']['model_results'])
        project['inputs']['minimum_burnout_altitude']['value'] = results['vertical_flight']['metrics']['burnout_altitude']['value']
        review = lifecycle.review_project(project, results)
        self.assertEqual(review['findings']['burnout_height']['status'], 'not_assessed')

    def test_tampered_retained_coordinates_cannot_receive_valid_receipt(self):
        results = deepcopy(self.baseline['run']['model_results'])
        results['vertical_flight']['guided_response']['samples'][-1]['x_m'] += 1
        with self.assertRaises(ValueError):
            lifecycle.review_project(self.baseline['project'], results)

    def test_previous_vertical_manifest_remains_readable_new_guided_requires_solver(self):
        vertical = powered_flight_review()
        results = engineering.evaluate_models(vertical)
        sources = {key: value for key, value in lifecycle._verification_sources().items()
                   if key in lifecycle.POWERED_FLIGHT_VERIFICATION_SOURCE_NAMES}
        with patch.object(lifecycle, '_verification_sources', return_value=sources):
            old = lifecycle.review_project(vertical, results)
        self.assertTrue(lifecycle.verify_review(old))
        with patch.object(lifecycle, '_verification_sources', return_value=sources), self.assertRaises(ValueError):
            lifecycle.review_project(self.baseline['project'], self.baseline['run']['model_results'])

    def test_provider_projection_keeps_frame_witnesses_but_omits_full_grids(self):
        full = dict(recorded_evidence=deepcopy(self.baseline['run']['review']['evidence']['vertical_flight']))
        projected = project_investigation._provider_evidence(full)
        self.assertIn('guided_response', full['recorded_evidence'])
        self.assertNotIn('guided_response', projected['recorded_evidence'])
        summary = projected['recorded_evidence']['guided_summary_projection']
        self.assertEqual(summary['frame']['id'], 'body_centered_inertial_plane')
        self.assertIn('pitch_end', {row['event'] for row in summary['witness_samples']})
        self.assertIn('after_cutoff', {row['event'] for row in summary['witness_samples']})
        self.assertNotIn('refinement', summary)
        self.assertLess(len(json.dumps(projected)), 45000)

    def test_scenario_work_limit_accounts_for_steering_segments(self):
        project = fixture()
        project['inputs']['steps']['value'] = 512
        cases = [dict(name=str(index), changes={'final_pitch_angle': .3 + index*.01}) for index in range(10)]
        with self.assertRaises(WorkspaceError):
            WorkspaceScenarios._budget(project, cases, 'Constructed steering study')

    def test_test_observation_retains_scalar_guided_accuracy_without_trajectory(self):
        tests = WorkspaceTestData(self.store)
        baseline = self.baseline['run']
        predicted = baseline['model_results']['vertical_flight']['metrics']['burnout_altitude']['value']
        record = tests.run(self.identity, 1, baseline['run_id'], {
            'schema': 'sixd.test-comparison-spec.v1', 'name': 'Constructed guided observation',
            'source': 'Synthetic observation, not measured flight data', 'data_kind': 'synthetic',
            'test_conditions': 'Declared same burnout observable; conditions unverified.',
            'conditions_match': 'declared_match', 'filename': 'guided.csv',
            'csv_text': f'id,req,value,unit,tolerance\na,burnout_height,{predicted},m,50\n',
            'mapping': {'measurement_id': 'id', 'requirement_id': 'req', 'value': 'value', 'unit': 'unit', 'tolerance': 'tolerance'}})
        context = TestEvidence(self.store, tests).investigation_context(self.identity, 1, 'burnout_height',
                    record['receipt']['comparison_id'], 2)
        self.assertIn('guided_response', context['recorded']['model'])
        self.assertNotIn('samples', context['recorded']['model']['guided_response'])
        self.assertEqual(record['receipt']['row_results'][0]['prediction_agreement']['status'], 'within_tolerance')

    def test_offline_assistant_uses_guided_scope_roles_and_one_reproducibility_check(self):
        provider = GuidedProvider()
        with patch.object(project_investigation, 'evaluate_models', wraps=engineering.evaluate_models) as calculate:
            result = project_investigation.investigate_project(self.baseline, 'burnout_height', 'Explain the evidence.',
                        provider, investigation_id='offline-guided')
        self.assertEqual(result['state'], 'completed', result)
        self.assertEqual(result['live_model_calls'], 0)
        self.assertEqual(calculate.call_count, 1)
        self.assertTrue(result['evidence']['recheck:vertical_flight']['matches_saved_result'])
        roles = {row['role'] for row in result['evidence_roles']['roles']}
        self.assertIn('position_grid_tolerance', roles)
        self.assertIn('velocity_difference_middle_to_fine', roles)
        self.assertEqual(evidence_roles.evaluate_roles(result)['flags'], [])


if __name__ == '__main__':
    unittest.main()
