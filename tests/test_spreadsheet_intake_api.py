"""A supplied spreadsheet becomes a project only after explicit confirmation."""
from base64 import b64encode
from contextlib import closing
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


def source(name, text):
    return {'filename': name, 'content_base64': b64encode(text.encode()).decode()}


def supplied(project_id='spreadsheet-supplied'):
    return {
        'project': {'project_id': project_id, 'name': 'Supplied atmospheric load',
                    'description': 'Constructed intake acceptance case, no hardware claim.', 'lifecycle_stage': 'design'},
        'files': [
            source('inputs.csv', 'Name,Amount,SI,Origin\nrho,1,kg/m^3,Constructed\nv,10,m/s,Constructed\ncd,1,1,Constructed\na,2,m^2,Constructed\nmax,150,N,Declared criterion\n'),
            source('bindings.csv', 'Model,Kind,Role,Input\nload,drag_load,density,rho\nload,drag_load,relative_speed,v\nload,drag_load,drag_coefficient,cd\nload,drag_load,reference_area,a\n'),
            source('requirements.csv', 'ID,Title,Model,Metric,Operator,Limit,Critical\ndrag,Declared drag limit,load,drag_force,<=,max,true\n')],
        'tables': {
            'inputs': {'file_index': 0, 'sheet': 'CSV', 'mapping': dict(zip(['id', 'value', 'unit', 'source'], ['Name', 'Amount', 'SI', 'Origin']))},
            'bindings': {'file_index': 1, 'sheet': 'CSV', 'mapping': dict(zip(['model_id', 'model_type', 'parameter', 'input_id'], ['Model', 'Kind', 'Role', 'Input']))},
            'requirements': {'file_index': 2, 'sheet': 'CSV', 'mapping': dict(zip(['id', 'title', 'model_id', 'metric', 'operator', 'limit_input', 'critical'], ['ID', 'Title', 'Model', 'Metric', 'Operator', 'Limit', 'Critical']))}}
    }


class SpreadsheetIntakeAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.server = create_server(port=0, db_path=Path(self.temp.name) / 'workspace.sqlite3',
            provider_factory=lambda *a, **kw: (_ for _ in ()).throw(AssertionError('Intake cannot call an AI provider')))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.temp.cleanup()

    def request(self, route, body=None, *, origin=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        conn.request('GET' if body is None else 'POST', route,
                     None if body is None else json.dumps(body), headers)
        response = conn.getresponse()
        status, raw = response.status, response.read()
        is_json = 'application/json' in response.getheader('Content-Type', '')
        conn.close()
        return status, json.loads(raw) if is_json else raw

    def counts(self):
        with self.server.store._connect() as db:
            return {name: db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0]
                    for name in ('projects', 'revisions', 'runs')}

    def test_preview_then_confirm_then_calculate_without_provider(self):
        payload = supplied()
        before = self.counts()
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('Preview must not calculate')):
            code, doc = self.request('/api/project-intake/inspect', payload['files'][0])
            self.assertEqual(code, 200, doc)
            self.assertEqual(doc['sheets'][0]['headers'], ['Name', 'Amount', 'SI', 'Origin'])
            code, preview = self.request('/api/project-intake/preview', payload)
            self.assertEqual(code, 200, preview)
            self.assertTrue(preview['valid'], preview)
            self.assertEqual(self.counts(), before)
            code, created = self.request('/api/projects', {'project': preview['project']})
            self.assertEqual(code, 200, created)
            self.assertIsNone(created['run'])
            self.assertIn(doc['sha256'], created['project']['description'])
        code, calculated = self.request('/api/run', {'project_id': payload['project']['project_id'], 'revision': 1})
        self.assertEqual(code, 200, calculated)
        finding = calculated['run']['review']['findings']['drag']
        self.assertEqual(finding['status'], 'met')
        self.assertEqual(finding['evidence']['metric']['value'], 100)
        self.assertEqual(finding['evidence']['limit']['value'], 150)
        self.assertEqual(self.counts()['runs'], before['runs'] + 1)

    def test_invalid_unit_can_be_corrected_and_preview_does_not_save(self):
        payload = supplied()
        before = self.counts()
        payload['files'][0] = source('inputs.csv', 'Name,Amount,SI,Origin\nrho,1,kg/m^3,Constructed\nv,10,km/s,Constructed\ncd,1,1,Constructed\na,2,m^2,Constructed\nmax,150,N,Declared criterion\n')
        code, bad = self.request('/api/project-intake/preview', payload)
        self.assertEqual(code, 200, bad)
        self.assertFalse(bad['valid'])
        self.assertTrue(bad['issues'])
        self.assertEqual(self.counts(), before)
        code, good = self.request('/api/project-intake/preview', supplied())
        self.assertEqual(code, 200, good)
        self.assertTrue(good['valid'], good)
        self.assertEqual(self.counts(), before)

    def test_duplicate_confirmation_cannot_replace_existing_project(self):
        code, preview = self.request('/api/project-intake/preview', supplied())
        self.assertTrue(preview['valid'], preview)
        code, first = self.request('/api/projects', {'project': preview['project']})
        self.assertEqual(code, 200, first)
        different = dict(preview['project'], name='Attempted replacement')
        code, duplicate = self.request('/api/projects', {'project': different})
        self.assertEqual(code, 409, duplicate)
        code, saved = self.request('/api/workspace?project_id=spreadsheet-supplied')
        self.assertEqual(saved['project'], first['project'])

    def test_inspect_rejects_legacy_formats_and_foreign_origin(self):
        code, error = self.request('/api/project-intake/inspect', source('macros.xlsm', 'not a workbook'))
        self.assertEqual(code, 400, error)
        code, error = self.request('/api/project-intake/inspect', supplied()['files'][0], origin='https://example.invalid')
        self.assertEqual(code, 403, error)

    def test_assets_are_available_without_any_connection(self):
        for route in ('/spreadsheet-intake.js', '/spreadsheet-intake.css'):
            code, content = self.request(route)
            self.assertEqual(code, 200)
            self.assertTrue(content)
        code, workbook = self.request('/api/project-intake/example-workbook')
        self.assertEqual(code, 200)
        self.assertEqual(workbook, (ROOT / 'examples/project-intake/constructed-drag.xlsx').read_bytes())


if __name__ == '__main__':
    unittest.main()
