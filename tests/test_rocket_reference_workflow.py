"""Actual HTTP reference journey; no provider can supply the engineering result."""
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
from sixd import powered_flight, lifecycle
from sixd.workspace import _digest
from sixd.workspace_server import create_server


class RocketReferenceWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        def forbidden(*args, **kwargs):
            raise AssertionError('The reference journey must not call an external provider.')
        cls.server = create_server(port=0, db_path=Path(cls.temporary.name) / 'workspace.sqlite3',
                                   provider_factory=forbidden, research_transport=forbidden,
                                   observability_transport=forbidden)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temporary.cleanup()

    def request(self, path, body=None, expected=200):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=60)
        connection.request('GET' if body is None else 'POST', path,
                           None if body is None else json.dumps(body), {'Content-Type': 'application/json'})
        response = connection.getresponse()
        data = json.loads(response.read())
        connection.close()
        self.assertEqual(response.status, expected, data)
        return data

    def test_complete_reference_journey_preserves_context_and_receipts(self):
        before = self.server.store.list_projects()
        templates = self.request('/api/templates')['templates']
        project = next(item['project'] for item in templates if item['id'] == 'rocket_review')
        self.assertEqual(self.server.store.list_projects(), before)
        project['project_id'], project['name'] = 'api-rocket-journey', 'Renamed reference'
        view = self.request('/api/projects', {'project': project})
        identity = view['project_id']
        def summary(revision):
            return self.request(f'/api/review-workspace?project_id={identity}&revision={revision}')
        unrun = summary(1)
        self.assertEqual(unrun['counts']['not_run'], 10)
        self.assertFalse(unrun['rocket_reference']['can_stage'])
        baseline = self.request('/api/run', dict(project_id=identity, revision=1))
        with patch.object(powered_flight, 'evaluate', side_effect=AssertionError('Reading must not calculate')):
            data = summary(1)
        self.assertEqual(data['counts'], dict(met=9, not_met=0, not_assessed=1, not_run=0))
        self.assertEqual(data['rocket_reference']['run_id'], baseline['run']['run_id'])
        self.assertTrue(data['rocket_reference']['can_stage'])
        self.assertEqual(data.pop('digest'), _digest(data))

        reduced = deepcopy(baseline['project'])
        reduced['inputs']['thrust']['value'] = 11000
        draft = dict(project_id=identity, base_revision=1, project=reduced)
        impact = self.request('/api/impact', draft)['impact']
        self.assertEqual(set(impact['affected_model_ids']),
                         {'propulsion', 'vertical_flight', 'atmospheric_load', 'mount'})
        self.assertEqual(self.server.store.get(identity, 1), baseline)
        self.request('/api/revisions', draft)
        self.assertFalse(summary(1)['rocket_reference']['can_stage'])
        self.assertEqual(summary(2)['counts']['not_run'], 10)
        failed = self.request('/api/run', dict(project_id=identity, revision=2))
        data = summary(2)
        self.assertEqual(data['counts'], dict(met=8, not_met=1, not_assessed=1, not_run=0))
        self.assertEqual(data['rocket_reference']['reused_model_ids'], ['thermal'])
        self.assertEqual(failed['run']['review']['findings']['burnout_height']['status'], 'not_met')
        self.assertEqual(self.request('/api/impact', draft, expected=409)['error'],
                         'The project has a newer revision. Reload before previewing this draft.')

        corrected = deepcopy(failed['project'])
        corrected['inputs']['thrust']['value'] = data['rocket_reference']['next_thrust']
        self.request('/api/revisions', dict(project_id=identity, base_revision=2, project=corrected))
        final = self.request('/api/run', dict(project_id=identity, revision=3))
        data = summary(3)
        self.assertEqual(data['counts'], dict(met=9, not_met=0, not_assessed=1, not_run=0))
        self.assertEqual(data['rocket_reference']['stage'], 'corrected')
        self.assertFalse(data['rocket_reference']['can_stage'])
        export = self.request(f'/api/engineering-review-export?project_id={identity}&revision=3')
        self.assertEqual(export['workspace']['run']['review'], final['run']['review'])
        self.assertTrue(lifecycle.verify_review(export['workspace']['run']['review']))
        self.assertFalse(final['run']['review']['launch_authorization'])
        self.assertEqual(self.server.store.get(identity, 1)['run']['review'], baseline['run']['review'])
        self.assertEqual(self.server.store.get(identity, 2)['run']['review'], failed['run']['review'])
        for saved in (baseline, failed, final):
            self.assertEqual(saved['run']['live_model_calls'], 0)


if __name__ == '__main__':
    unittest.main()
