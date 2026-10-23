"""HTTP comparisons inspect retained evidence without creating new findings."""
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import workspace
from sixd.workspace_server import create_server


def project(identity='comparison-http'):
    return {'schema': 'sixd.project.v1', 'project_id': identity, 'revision': '1', 'name': 'Constructed comparison',
        'description': 'Synthetic one-condition drag values, not measured hardware.', 'lifecycle_stage': 'design',
        'inputs': {key: {'value': value, 'unit': unit, 'source': 'Constructed supplied input'} for key, value, unit in
            [('density', 1, 'kg/m^3'), ('speed', 10, 'm/s'), ('cd', 1, '1'), ('area', 2, 'm^2'),
             ('maximum', 150, 'N'), ('minimum', 50, 'N'), ('target', 100, 'N')]},
        'models': [{'id': 'load', 'type': 'drag_load', 'inputs': {'density': 'density', 'relative_speed': 'speed',
                    'drag_coefficient': 'cd', 'reference_area': 'area'}}],
        'requirements': [{'id': key, 'title': title, 'model_id': 'load', 'metric': 'drag_force',
            'operator': operator, 'limit_input': limit, 'critical': True} for key, title, operator, limit in
            [('upper', 'Maximum supplied force', '<=', 'maximum'), ('lower', 'Minimum supplied force', '>=', 'minimum'),
             ('equal', 'Exact supplied force target', '==', 'target')]]}


class WorkspaceComparisonAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.server = create_server(port=0, db_path=Path(self.temp.name) / 'workspace.sqlite3',
            provider_factory=lambda *a, **kw: (_ for _ in ()).throw(AssertionError('Comparison cannot call a provider')))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.project = project()
        self.identity = self.project['project_id']
        self.server.store.create_project(self.project)
        self.a = self.server.store.run(self.identity, 1)
        changed = deepcopy(self.project)
        changed['inputs']['speed']['value'] = 8
        self.server.store.save_revision(self.identity, 1, changed)
        self.b = self.server.store.run(self.identity, 2)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.temp.cleanup()

    def request(self, path, body=None, origin=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=20)
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        conn.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), headers)
        response = conn.getresponse()
        code, raw = response.status, response.read()
        value = json.loads(raw) if 'application/json' in response.getheader('Content-Type', '') else raw
        conn.close()
        return code, value

    def select(self, view):
        return {'kind': 'run', 'run_id': view['run']['run_id']}

    def compare(self, a=None, b=None, revision=2):
        return self.request('/api/design-comparison', {'project_id': self.identity, 'revision': revision,
            'left': self.select(self.a) if a is None else a, 'right': self.select(self.b) if b is None else b})

    def rows(self):
        with self.server.store._connect() as db:
            return {table: db.execute('SELECT * FROM ' + table + ' ORDER BY rowid').fetchall()
                for table, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}

    def test_catalog_and_operator_margins_are_read_only_and_source_bound(self):
        before = self.rows()
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('Comparison must not calculate')):
            code, catalog = self.request('/api/design-comparison/catalog?project_id=' + self.identity + '&revision=2')
            self.assertEqual(code, 200, catalog)
            self.assertEqual(len(catalog['options']), 2)
            code, result = self.compare()
            self.assertEqual(code, 200, result)
        rows = {r['requirement_id']: r for r in result['requirements']}
        self.assertEqual(rows['upper']['trend'], 'improved')
        self.assertEqual(rows['lower']['trend'], 'worsened')
        self.assertEqual(rows['equal']['trend'], 'worsened')
        self.assertEqual(rows['upper']['metric_delta']['value'], -36)
        self.assertEqual(rows['upper']['margin_delta']['value'], 36)
        self.assertEqual(rows['lower']['margin_delta']['value'], -36)
        self.assertEqual(rows['equal']['right']['margin']['value'], 36)
        self.assertEqual(rows['equal']['right']['finding']['status'], 'not_met')
        self.assertEqual(result['left']['review_digest'], self.a['run']['review']['digest'])
        self.assertEqual(result['right']['review_digest'], self.b['run']['review']['digest'])
        self.assertEqual(result['digest'], workspace._digest({key: val for key, val in result.items() if key != 'digest'}))
        self.assertEqual(self.rows(), before)

    def test_relaxed_criterion_does_not_become_design_improvement(self):
        relaxed = deepcopy(self.b['project'])
        relaxed['inputs']['maximum']['value'] = 200
        self.server.store.save_revision(self.identity, 2, relaxed)
        c = self.server.store.run(self.identity, 3)
        before = self.rows()
        code, result = self.compare(self.select(self.b), self.select(c), revision=3)
        self.assertEqual(code, 200, result)
        row = next(r for r in result['requirements'] if r['requirement_id'] == 'upper')
        self.assertEqual(row['trend'], 'criterion_changed')
        self.assertEqual(row['left']['metric']['value'], row['right']['metric']['value'])
        self.assertEqual(self.rows(), before)

    def test_scenarios_are_hypothetical_and_different_baselines_are_flagged(self):
        study = self.server.scenarios.run(self.identity, 2, self.b['run']['run_id'], {
            'schema': 'sixd.scenario-spec.v1', 'name': 'Constructed variants', 'source': 'Supplied synthetic input cases',
            'mode': 'alternatives', 'cases': [{'name': 'Slower', 'changes': {'speed': 6}}, {'name': 'Faster', 'changes': {'speed': 12}}]})
        study_id = study['receipt']['study_id']
        left = {'kind': 'scenario', 'study_id': study_id, 'case_index': 0}
        right = {'kind': 'scenario', 'study_id': study_id, 'case_index': 1}
        before = self.rows()
        code, result = self.compare(left, right)
        self.assertEqual(code, 200, result)
        self.assertTrue(result['left']['hypothetical'])
        self.assertEqual(result['compatibility']['status'], 'compatible')
        code, incompatible = self.compare(self.select(self.a), right)
        self.assertEqual(code, 200, incompatible)
        self.assertEqual(incompatible['compatibility']['status'], 'incompatible')
        self.assertFalse(any(row['trend'] == 'improved' for row in incompatible['requirements']))
        self.assertEqual(self.rows(), before)

    def test_cross_project_future_identical_and_bad_fields_are_rejected(self):
        foreign = project('foreign-comparison')
        self.server.store.create_project(foreign)
        foreign_view = self.server.store.run(foreign['project_id'], 1)
        for left, right, revision in [(self.select(self.a), self.select(foreign_view), 2),
            (self.select(self.a), self.select(self.b), 1), (self.select(self.a), self.select(self.a), 2)]:
            code, result = self.compare(left, right, revision)
            self.assertIn(code, (400, 404, 409), result)
            self.assertNotIn('requirements', result)
        code, value = self.request('/api/design-comparison', {'project_id': self.identity, 'revision': 2,
            'left': self.select(self.a), 'right': self.select(self.b)}, 'https://example.invalid')
        self.assertEqual(code, 403, value)

    def test_incompatible_units_and_missing_evidence_remain_unassessed(self):
        altered = deepcopy(self.b['project'])
        altered['inputs']['maximum']['unit'] = 'kg'
        self.server.store.save_revision(self.identity, 2, altered)
        c = self.server.store.run(self.identity, 3)
        code, result = self.compare(self.select(self.b), self.select(c), revision=3)
        self.assertEqual(code, 200, result)
        row = next(r for r in result['requirements'] if r['requirement_id'] == 'upper')
        self.assertEqual(row['right']['finding']['status'], 'not_assessed')
        self.assertFalse(row['comparability']['comparable'])
        self.assertEqual(row['trend'], 'not_comparable')

    def test_assets_and_stale_runtime_guard(self):
        for route in ('/design-comparison.js', '/design-comparison.css'):
            code, body = self.request(route)
            self.assertEqual(code, 200)
            self.assertTrue(body)
        with patch('sixd.workspace_server._code_fingerprint', return_value='modified'):
            self.assertEqual(self.request('/api/design-comparison/catalog?project_id=' + self.identity + '&revision=2')[0], 409)
            self.assertEqual(self.compare()[0], 409)

    def test_exact_integer_text_survives_the_wire(self):
        changed = deepcopy(self.b['project'])
        changed['inputs']['serial_number'] = {'value': 9007199254740993, 'unit': '1',
            'source': 'Constructed original integer'}
        changed['inputs']['cd']['value'] = 9007199254740993
        self.server.store.save_revision(self.identity, 2, changed)
        c = self.server.store.run(self.identity, 3)
        code, result = self.compare(self.select(self.b), self.select(c), revision=3)
        self.assertEqual(code, 200, result)
        row = next(item for item in result['inputs'] if item['id'] == 'serial_number')
        self.assertEqual(row['right']['value'], 9007199254740993)
        self.assertEqual(row['right']['display_value'], '9007199254740993')
        finding = next(item for item in result['requirements'] if item['requirement_id'] == 'upper')
        self.assertIn('9007199254740993', finding['right']['context_display'])
        self.assertIn('9007199254740993', result['models_display'])

    def test_malformed_selectors_never_trigger_an_execution(self):
        before = self.rows()
        invalid = [None, {}, {'kind': 'latest'}, {'kind': 'run', 'run_id': self.a['run']['run_id'], 'extra': True},
            {'kind': 'scenario', 'study_id': 'missing', 'case_index': True},
            {'kind': 'scenario', 'study_id': 'missing', 'case_index': -1}]
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('No comparison calculation')):
            for selection in invalid:
                # Deliberately bypass helper's None-as-default convenience.
                code, result = self.request('/api/design-comparison', {'project_id': self.identity,
                    'revision': 2, 'left': selection, 'right': self.select(self.b)})
                self.assertIn(code, (400, 404), result)
        self.assertEqual(self.rows(), before)


if __name__ == '__main__':
    unittest.main()
