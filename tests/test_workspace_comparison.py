"""Stored evidence comparisons use explicit criteria and retain provenance."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import workspace, workspace_scenarios, workspace_comparison
from sixd.workspace import WorkspaceStore, WorkspaceError, _digest, _encode
from sixd.workspace_comparison import WorkspaceComparison, _difference


def project(identity='comparison-unit'):
    return {'schema': 'sixd.project.v1', 'project_id': identity, 'revision': '1',
        'name': 'Constructed force comparison', 'description': 'Supplied single-condition drag reference, not a flight vehicle.',
        'lifecycle_stage': 'design', 'inputs': {key: {'value': value, 'unit': unit, 'source': 'Constructed input'}
            for key, value, unit in [('density', 1, 'kg/m^3'), ('speed', 10, 'm/s'), ('cd', 1, '1'),
                ('area', 2, 'm^2'), ('maximum', 150, 'N'), ('minimum', 50, 'N'), ('target', 100, 'N')]},
        'models': [{'id': 'load', 'type': 'drag_load', 'inputs': {'density': 'density', 'relative_speed': 'speed',
            'drag_coefficient': 'cd', 'reference_area': 'area'}}],
        'requirements': [{'id': key, 'title': key + ' supplied force', 'model_id': 'load', 'metric': 'drag_force',
            'operator': op, 'limit_input': limit, 'critical': True} for key, op, limit in
            [('upper', '<=', 'maximum'), ('lower', '>=', 'minimum'), ('equal', '==', 'target')]]}


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.store = WorkspaceStore(Path(self.tmp.name) / 'workspace.sqlite3')
        self.scenarios = workspace_scenarios.WorkspaceScenarios(self.store)
        self.service = WorkspaceComparison(self.store, self.scenarios)
        self.project = project()
        self.pid = self.project['project_id']
        self.store.create_project(self.project)
        self.a = self.store.run(self.pid, 1)
        changed = deepcopy(self.project)
        changed['inputs']['speed']['value'] = 8
        self.store.save_revision(self.pid, 1, changed)
        self.b = self.store.run(self.pid, 2)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def select(view):
        return {'kind': 'run', 'run_id': view['run']['run_id']}

    def compare(self, left=None, right=None, revision=2):
        return self.service.compare(self.pid, revision, self.select(self.a) if left is None else left,
                                    self.select(self.b) if right is None else right)

    def save(self, change):
        value = deepcopy(self.b['project'])
        change(value)
        self.store.save_revision(self.pid, 2, value)
        return self.store.run(self.pid, 3)

    def rows(self):
        with self.store._connect() as db:
            return {table: [tuple(row) for row in db.execute('SELECT * FROM ' + table + ' ORDER BY rowid')]
                for table, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}

    @staticmethod
    def requirement(result, identity='upper'):
        return next(row for row in result['requirements'] if row['requirement_id'] == identity)

    def study(self, baseline=None, revision=2):
        value = {'schema': 'sixd.scenario-spec.v1', 'name': 'Supplied alternatives', 'source': 'Constructed test cases',
            'mode': 'sweep', 'input_id': 'speed', 'values': [6, 12]}
        result = self.scenarios.run(self.pid, revision, (baseline or self.b)['run']['run_id'], value)
        return [{'kind': 'scenario', 'study_id': result['receipt']['study_id'], 'case_index': i} for i in range(2)]

    def test_hand_solved_all_operator_margins_and_canonical_statuses(self):
        result = self.compare()
        # F = rho * v^2 * Cd * A / 2 = v^2 N. These values are hand arithmetic.
        expectations = [('upper', 50, 86, 'improved'), ('lower', 50, 14, 'worsened'),
                        ('equal', 0, 36, 'worsened')]
        for identity, before, after, trend in expectations:
            row = self.requirement(result, identity)
            self.assertEqual(row['left']['metric']['value'], 100)
            self.assertEqual(row['right']['metric']['value'], 64)
            self.assertEqual(row['left']['margin']['value'], before)
            self.assertEqual(row['right']['margin']['value'], after)
            self.assertEqual(row['trend'], trend)
            self.assertTrue(row['comparability']['comparable'])
            self.assertEqual(row['metric_delta']['value'], -36)
        self.assertEqual(self.requirement(result, 'lower')['right']['finding']['status'], 'met')
        self.assertEqual(self.requirement(result, 'equal')['right']['finding']['status'], 'not_met')
        self.assertTrue(result['summary']['no_overall_ranking'])
        self.assertEqual(result['summary']['counts']['improved'], 1)

    def test_limit_relaxation_is_criterion_change_not_hardware_improvement(self):
        c = self.save(lambda p: p['inputs']['maximum'].update(value=200))
        row = self.requirement(self.compare(self.select(self.b), self.select(c), 3))
        self.assertEqual(row['trend'], 'criterion_changed')
        self.assertEqual(row['metric_delta']['value'], 0)
        self.assertEqual(row['left']['margin']['value'], 86)
        self.assertEqual(row['right']['margin']['value'], 136)
        self.assertFalse(row['comparability']['criterion_unchanged'])
        self.assertIn('different declared limits', row['notes'][0])

    def test_operator_metric_model_and_binding_changes_prevent_numeric_trends(self):
        variants = [lambda p: p['requirements'][0].update(operator='>='),
            lambda p: p['requirements'][0].update(metric='dynamic_pressure'),
            lambda p: p['models'][0].update(description='A changed modelling assumption'),
            lambda p: (p['inputs'].update(speed_alias=deepcopy(p['inputs']['speed'])),
                       p['models'][0]['inputs'].update(relative_speed='speed_alias'))]
        for change in variants:
            with self.subTest(change=change):
                # Separate saved project/revision sets keep each transition independent.
                value = deepcopy(self.b['project'])
                change(value)
                # Pure row comparison intentionally exercises metadata gates; the real changed-model
                # run below proves these gates also apply after ordinary persistence/verification.
                side_a, side_b = self._sides()
                side_b['project'] = value
                if value['requirements'][0]['metric'] == 'dynamic_pressure':
                    side_b['review']['findings']['upper']['status'] = 'not_assessed'
                    side_b['review']['findings']['upper']['evidence'] = None
                row = next(r for r in self.service._requirements(side_a, side_b, False) if r['requirement_id'] == 'upper')
                self.assertEqual(row['trend'], 'not_comparable')
                self.assertIsNone(row['metric_delta'])
        c = self.save(lambda p: p['models'][0].update(description='Changed declared boundary assumption'))
        self.assertEqual(self.requirement(self.compare(self.select(self.b), self.select(c), 3))['trend'], 'not_comparable')

    def _sides(self):
        result = self.compare()
        return deepcopy(result['left']), deepcopy(result['right'])

    def test_unassessed_wrong_limit_unit_preserves_raw_diagnostic_without_margin(self):
        c = self.save(lambda p: p['inputs']['maximum'].update(unit='kg'))
        row = self.requirement(self.compare(self.select(self.b), self.select(c), 3))
        self.assertEqual(row['right']['finding']['status'], 'not_assessed')
        self.assertFalse(row['right']['metric_assessed'])
        self.assertEqual(row['right']['metric']['value'], 64)
        self.assertIn('Diagnostic', row['right']['metric']['note'])
        self.assertEqual(row['right']['limit']['unit'], 'kg')
        self.assertIsNone(row['right']['margin'])
        self.assertEqual(row['trend'], 'not_comparable')
        self.assertIsNone(row['margin_delta'])

    def test_failed_model_evidence_does_not_turn_into_improvement(self):
        c = self.save(lambda p: p['inputs']['density'].update(value=-1))
        row = self.requirement(self.compare(self.select(self.b), self.select(c), 3))
        self.assertEqual(row['right']['finding']['status'], 'not_assessed')
        self.assertEqual(row['trend'], 'not_comparable')
        self.assertIsNone(row['right']['metric'])

    def test_added_removed_requirements_and_inputs_have_no_improvement_claim(self):
        def change(p):
            p['requirements'] = [r for r in p['requirements'] if r['id'] != 'equal']
            p['requirements'].append({**p['requirements'][0], 'id': 'new_upper'})
            p['inputs'].pop('target')
            p['inputs']['unused'] = {'value': 7, 'unit': 'kg', 'source': 'New supplied input'}
        c = self.save(change)
        result = self.compare(self.select(self.b), self.select(c), 3)
        self.assertEqual(self.requirement(result, 'equal')['trend'], 'removed')
        self.assertEqual(self.requirement(result, 'new_upper')['trend'], 'added')
        inputs = {r['id']: r for r in result['inputs']}
        self.assertEqual(inputs['target']['change'], 'removed')
        self.assertEqual(inputs['unused']['change'], 'added')
        self.assertIsNone(inputs['unused']['value_delta'])

    def test_same_baseline_scenarios_and_exact_baseline_run_are_compatible(self):
        left, right = self.study()
        result = self.compare(left, right)
        self.assertEqual(result['compatibility']['status'], 'compatible')
        self.assertTrue(result['left']['hypothetical'])
        self.assertEqual(result['left']['project_revision'], 2)
        self.assertEqual(result['left']['baseline_run_id'], self.b['run']['run_id'])
        self.assertEqual(self.requirement(result)['metric_delta']['value'], 108)
        self.assertEqual(self.compare(self.select(self.b), right)['compatibility']['status'], 'compatible')

    def test_different_scenario_baselines_suppress_trends_without_hiding_values(self):
        left, right = self.study()
        other_run = self.store.run(self.pid, 2)
        other_case = self.study(other_run)[0]
        for a, b in [(left, other_case), (self.select(other_run), right), (self.select(self.a), left)]:
            with self.subTest(a=a, b=b):
                result = self.compare(a, b)
                self.assertEqual(result['compatibility']['status'], 'incompatible')
                row = self.requirement(result)
                self.assertIsNotNone(row['left']['metric'])
                self.assertIsNotNone(row['right']['metric'])
                self.assertEqual(row['trend'], 'not_comparable')
                self.assertIsNone(row['metric_delta'])

    def test_historical_revision_is_not_historical_implementation(self):
        self.assertEqual(self.compare()['compatibility']['status'], 'compatible')
        sources = {**workspace._sources(), 'changed-maintained-code': '0' * 64}
        with patch.object(workspace, '_sources', return_value=sources):
            result = self.compare()
        self.assertEqual(result['compatibility']['status'], 'limited')
        self.assertFalse(result['left']['freshness']['current_implementation'])
        self.assertEqual(self.requirement(result)['left']['metric']['value'], 100)
        self.assertEqual(self.requirement(result)['trend'], 'not_comparable')

    def test_versions_and_verification_sources_are_individual_comparability_gates(self):
        left, right = self._sides()
        for field, value in [('model_version', 'historical'), ('verification_sources', {'old': '0' * 64})]:
            changed = deepcopy(right)
            changed['review']['evidence']['load'][field] = value
            row = self.service._requirements(left, changed, False)[0]
            self.assertFalse(row['comparability']['comparable'])
            self.assertEqual(row['trend'], 'not_comparable')

    def test_read_only_no_solver_retrieval_or_budget_changes_and_single_snapshot(self):
        selections = self.study()
        before = self.rows()
        original = self.store._connect
        traced = []
        @contextmanager
        def observe(*args, **kwargs):
            with original(*args, **kwargs) as connection:
                connection.set_trace_callback(traced.append)
                yield connection
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('No calculation')), \
             patch.object(workspace_scenarios, 'evaluate_models', side_effect=AssertionError('No scenario calculation')), \
             patch.object(self.store, '_connect', side_effect=observe):
            catalog = self.service.catalog(self.pid, 2)
            result = self.compare(*selections)
        self.assertEqual(sum(sql == 'BEGIN' for sql in traced), 2)
        self.assertFalse(any(sql.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP')) for sql in traced))
        self.assertEqual(before, self.rows())
        self.assertEqual(result['live_model_calls'], 0)
        self.assertEqual(len(catalog['options']), 4)
        self.assertEqual(result['digest'], _digest({k: v for k, v in result.items() if k != 'digest'}))

    def test_catalog_contains_old_runs_and_unreviewed_revisions_and_frozen_ids(self):
        before = self.service.catalog(self.pid, 2)
        selections = [r['selection'] for r in before['options']]
        self.store.save_revision(self.pid, 2, self.b['project'])
        newer = self.store.run(self.pid, 2)
        catalog = self.service.catalog(self.pid, 3)
        self.assertEqual(catalog['unreviewed_revisions'][0]['revision'], 3)
        self.assertIn(self.select(self.a), [r['selection'] for r in catalog['options']])
        self.assertEqual(self.compare(*reversed(selections))['right']['run_id'], self.b['run']['run_id'])
        self.assertNotEqual(newer['run']['run_id'], self.b['run']['run_id'])
        self.assertEqual(len(self.service.catalog(self.pid, 1)['options']), 1)

    def test_exact_integer_display_and_finite_only_differences(self):
        exact = 9007199254740993
        c = self.save(lambda p: p['inputs']['maximum'].update(value=exact))
        result = self.compare(self.select(self.b), self.select(c), 3)
        row = self.requirement(result)
        self.assertEqual(row['right']['limit']['display_value'], str(exact))
        self.assertEqual(next(r for r in result['inputs'] if r['id'] == 'maximum')['right']['display_value'], str(exact))
        encoded = json.loads(_encode(result))
        self.assertEqual(self.requirement(encoded)['right']['limit']['display_value'], str(exact))
        self.assertIsNone(_difference(1e308, -1e308, 'N'))
        self.assertIsNone(_difference(10**400, 0, 'N'))
        self.assertEqual(_difference(exact, 1, 'N')['display_value'], str(exact - 1))

    def test_input_unit_change_never_converts(self):
        left, right = self._sides()
        right['project']['inputs']['speed']['unit'] = 'km/s'
        row = next(r for r in self.service._inputs(left, right) if r['id'] == 'speed')
        self.assertEqual(row['change'], 'unit_changed')
        self.assertIsNone(row['value_delta'])

    def test_finite_overflow_retains_raw_values_and_disables_trend(self):
        left, right = self._sides()
        for side, value in [(left, -1e308), (right, 1e308)]:
            side['review']['findings']['upper']['evidence']['metric']['value'] = value
            side['review']['findings']['upper']['evidence']['limit']['value'] = 0
        row = self.service._requirements(left, right, False)[0]
        self.assertEqual(row['trend'], 'not_comparable')
        self.assertIsNone(row['metric_delta'])
        self.assertIsNone(row['margin_delta'])
        self.assertEqual(row['right']['metric']['value'], 1e308)

    def test_cross_project_future_and_malformed_selectors_are_rejected(self):
        other = project('other-comparison')
        self.store.create_project(other)
        foreign = self.store.run(other['project_id'], 1)
        future_study = self.study()[0]
        for left, right, revision in [(self.select(self.a), self.select(foreign), 2),
            (self.select(self.a), self.select(self.b), 1), (self.select(self.a), future_study, 1),
            (self.select(self.a), self.select(self.a), 2),
            ({'kind': 'run', 'run_id': self.a['run']['run_id'], 'revision': 1}, self.select(self.b), 2),
            ({'kind': 'scenario', 'study_id': future_study['study_id'], 'case_index': True}, self.select(self.b), 2),
            ({'kind': 'scenario', 'study_id': future_study['study_id'], 'case_index': 16}, self.select(self.b), 2),
            ({'kind': 'run', 'run_id': 'absent'}, self.select(self.b), 2)]:
            with self.subTest(left=left, revision=revision), self.assertRaises(WorkspaceError):
                self.compare(left, right, revision)

    def test_corrupt_or_consistently_rehashed_inconsistent_run_rejected(self):
        with self.store._connect(write=True) as connection:
            receipt = deepcopy(self.a['run'])
            receipt['review']['findings']['upper']['status'] = 'not_met'
            receipt['review']['digest'] = _digest({k: v for k, v in receipt['review'].items() if k != 'digest'})
            connection.execute('UPDATE runs SET receipt=?,digest=? WHERE run_id=?',
                (_encode(receipt), _digest(receipt), receipt['run_id']))
        with self.assertRaises(WorkspaceError):
            self.compare()

    def test_corrupt_scenario_receipt_rejected(self):
        left, right = self.study()
        with self.store._connect(write=True) as connection:
            connection.execute('UPDATE scenario_studies SET digest=? WHERE study_id=?', ('0' * 64, left['study_id']))
        with self.assertRaises(WorkspaceError):
            self.compare(left, right)

    def test_catalog_bounds_runs_and_studies_but_keeps_exact_selectors(self):
        latest = self.store.run(self.pid, 2)
        for _ in range(3):
            self.study(latest)
        self.assertEqual(workspace_comparison.MAX_RUNS, 100)
        self.assertEqual(workspace_comparison.MAX_STUDIES, 20)
        with patch.object(workspace_comparison, 'MAX_RUNS', 2), patch.object(workspace_comparison, 'MAX_STUDIES', 2):
            catalog = self.service.catalog(self.pid, 2)
        self.assertTrue(catalog['history_truncated'])
        self.assertEqual(len([v for v in catalog['options'] if v['kind'] == 'run']), 2)
        self.assertEqual(len([v for v in catalog['options'] if v['kind'] == 'scenario']), 4)
        self.assertTrue(all(set(v['selection']) in ({'kind', 'run_id'}, {'kind', 'study_id', 'case_index'})
                            for v in catalog['options']))

    def test_historical_selection_does_not_inspect_or_leak_corrupt_future_runs(self):
        alternate = self.store.run(self.pid, 1)
        with self.store._connect(write=True) as db:
            db.execute('UPDATE runs SET digest=? WHERE run_id=?', ('0' * 64, self.b['run']['run_id']))
        self.assertEqual(len(self.service.catalog(self.pid, 1)['options']), 2)
        result = self.compare(self.select(self.a), self.select(alternate), 1)
        self.assertEqual(result['revision'], 1)
        self.assertTrue(all(r['trend'] == 'unchanged' for r in result['requirements']))

    def test_scalar_chain_definition_changes_are_not_confused_with_input_alternatives(self):
        p = project('comparison-scalar-chain')
        p['inputs'].update({key: {'value': value, 'unit': unit, 'source': 'Constructed chain boundary'} for key, value, unit in
            [('length', 1, 'm'), ('modulus', 1e9, 'Pa'), ('moment', 1e-4, 'm^4'), ('fiber', .1, 'm'),
             ('stress_limit', 200000, 'Pa'), ('alternate_cd', .5, '1')]})
        p['models'].append({'id': 'beam', 'type': 'static_cantilever', 'inputs': {'length': 'length',
            'young_modulus': 'modulus', 'second_moment': 'moment', 'outer_fiber': 'fiber'},
            'links': {'tip_force': {'model_id': 'load', 'metric': 'drag_force', 'unit': 'N',
                'rationale': 'Constructed scalar tip load, physical applicability unassessed.'}}})
        p['requirements'] = [{'id': 'stress', 'title': 'Supplied stress boundary', 'model_id': 'beam',
            'metric': 'bending_stress', 'operator': '<=', 'limit_input': 'stress_limit', 'critical': True}]
        pid = p['project_id']
        self.store.create_project(p)
        a = self.store.run(pid, 1)
        p['inputs']['speed']['value'] = 8
        self.store.save_revision(pid, 1, p)
        b = self.store.run(pid, 2)
        p['models'][0]['inputs']['drag_coefficient'] = 'alternate_cd'
        self.store.save_revision(pid, 2, p)
        c = self.store.run(pid, 3)
        # sigma = F*L*c/I: 100000 -> 64000 Pa, then a changed upstream coefficient binding.
        row = self.service.compare(pid, 3, self.select(a), self.select(b))['requirements'][0]
        self.assertEqual(row['trend'], 'improved')
        self.assertEqual(row['metric_delta']['value'], -36000)
        changed = self.service.compare(pid, 3, self.select(b), self.select(c))['requirements'][0]
        self.assertEqual(changed['trend'], 'not_comparable')
        self.assertIn('upstream model context', ' '.join(changed['comparability']['reasons']))
        self.assertEqual(changed['left']['model_context']['definition'], changed['right']['model_context']['definition'])

    def test_cross_project_scenario_id_cannot_be_used(self):
        other = project('comparison-other-scenario')
        self.store.create_project(other)
        run = self.store.run(other['project_id'], 1)
        study = self.scenarios.run(other['project_id'], 1, run['run']['run_id'], {
            'schema': 'sixd.scenario-spec.v1', 'name': 'Foreign scenario', 'source': 'Constructed input',
            'mode': 'sweep', 'input_id': 'speed', 'values': [6, 12]})
        selection = {'kind': 'scenario', 'study_id': study['receipt']['study_id'], 'case_index': 0}
        with self.assertRaises(WorkspaceError):
            self.compare(self.select(self.a), selection)


if __name__ == '__main__':
    unittest.main()
