"""User workflow closure never changes the canonical engineering result."""
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
from sixd.project_examples import example_projects
from sixd.workspace_server import create_server


class WorkspaceActionsAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.server = create_server(port=0, db_path=Path(self.temp.name) / 'workspace.sqlite3',
            provider_factory=lambda *a, **kw: (_ for _ in ()).throw(AssertionError('Actions cannot call a provider')))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.project = deepcopy(example_projects()['baseline'])
        thermal = next(r for r in self.project['requirements'] if r['id'] == 'thermal_limit')
        self.limit_id = thermal['limit_input']
        self.project['inputs'][self.limit_id]['value'] = 250
        self.identity = self.project['project_id']
        self.server.store.create_project(self.project)
        self.initial = self.server.store.run(self.identity, 1)
        self.assertEqual(self.initial['run']['review']['findings']['thermal_limit']['status'], 'not_met')

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.temp.cleanup()

    def request(self, path, body=None, origin=None):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=20)
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        connection.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), headers)
        response = connection.getresponse()
        code, raw = response.status, response.read()
        result = json.loads(raw) if 'application/json' in response.getheader('Content-Type', '') else raw
        connection.close()
        return code, result

    def profile(self, revision=1):
        code, value = self.request('/api/actions?project_id=' + self.identity + '&revision=' + str(revision))
        self.assertEqual(code, 200, value)
        return value

    def create(self):
        current = self.profile()
        origin = next(o for o in current['origins'] if o['target_id'] == 'finding:thermal_limit')
        spec = {**origin['suggested'], 'origin_id': origin['target_id'], 'note': 'User-declared follow-up for this constructed finding.'}
        code, result = self.request('/api/actions', {'project_id': self.identity, 'revision': 1,
            'expected_digest': current['digest'], 'spec': spec})
        self.assertEqual(code, 200, result)
        return result

    def update(self, state, *, closure='', supports=None, revision=1):
        current = self.profile(revision)
        action = current['actions'][0]
        spec = {key: action[key] for key in ('title', 'next_check', 'missing_evidence', 'completion_criteria', 'note')}
        spec.update(status=state, closure_note=closure, support_ids=action['support_ids'] if supports is None else supports)
        return self.request('/api/actions/update', {'project_id': self.identity, 'revision': revision,
            'action_id': action['action_id'], 'base_version': action['version'], 'expected_digest': current['digest'], 'spec': spec})

    def close(self, supports=None):
        self.assertEqual(self.update('in_progress')[0], 200)
        self.assertEqual(self.update('ready_for_review')[0], 200)
        code, result = self.update('closed', closure='Recorded the bounded analysis and its unresolved physical limits.',
            supports=['finding:thermal_limit'] if supports is None else supports)
        self.assertEqual(code, 200, result)
        return result

    def test_full_workflow_and_export_keep_unmet_finding_unchanged(self):
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('Action operations must not calculate')):
            self.create()
            closed = self.close()
            self.assertEqual(closed['actions'][0]['status'], 'closed')
            self.assertEqual(closed['actions'][0]['review_status'], 'current')
            self.assertEqual(len(closed['actions'][0]['history']), 4)
            code, exported = self.request('/api/engineering-review-export?project_id=' + self.identity + '&revision=1')
            self.assertEqual(code, 200, exported)
            self.assertEqual(exported['engineering_actions']['actions'][0]['status'], 'closed')
            self.assertEqual(exported['workspace']['run']['review'], self.initial['run']['review'])
            self.assertEqual(exported['workspace']['run']['review']['findings']['thermal_limit']['status'], 'not_met')
            digest = exported.pop('export_digest')
            self.assertEqual(digest, workspace._digest(exported))
            self.assertEqual(exported['engineering_actions']['run_id'], exported['workspace']['run']['run_id'])
        self.assertEqual(self.server.store.get(self.identity, 1)['run'], self.initial['run'])

    def test_closure_requires_ordered_states_note_and_support(self):
        self.create()
        self.assertEqual(self.update('closed', closure='Attempted shortcut', supports=['finding:thermal_limit'])[0], 409)
        self.assertEqual(self.update('in_progress')[0], 200)
        self.assertEqual(self.update('ready_for_review')[0], 200)
        self.assertEqual(self.update('closed', supports=['finding:thermal_limit'])[0], 400)
        self.assertEqual(self.update('closed', closure='Missing supporting records', supports=[])[0], 400)
        self.assertEqual(self.profile()['actions'][0]['status'], 'ready_for_review')

    def test_source_support_stays_pinned_and_explicit_review_reopens(self):
        source = {'source_id': None, 'base_version': None, 'title': 'Constructed support', 'url': 'https://example.org/review',
                  'excerpt': 'Version one, user supplied.', 'details': 'No authenticity claim.'}
        code, library = self.request('/api/sources', {'project_id': self.identity, 'revision': 1, 'source': source})
        self.assertEqual(code, 200, library)
        source_id = library['sources'][0]['source_id']
        self.create()
        self.close(['source:' + source_id])
        source.update(source_id=source_id, base_version=1, excerpt='Version two, not silently adopted.')
        self.assertEqual(self.request('/api/sources', {'project_id': self.identity, 'revision': 1, 'source': source})[0], 200)
        changed = self.profile()
        self.assertEqual(changed['actions'][0]['status'], 'closed')
        self.assertEqual(changed['actions'][0]['review_status'], 'needs_review')
        self.assertEqual(changed['actions'][0]['supports'][0]['snapshot']['version'], 1)
        self.assertEqual(self.update('closed', closure='Attempt to silently replace same support', supports=['source:' + source_id])[0], 409)
        action = changed['actions'][0]
        code, reviewed = self.request('/api/actions/review', {'project_id': self.identity, 'revision': 1,
            'action_id': action['action_id'], 'base_version': action['version'], 'expected_digest': changed['digest']})
        self.assertEqual(code, 200, reviewed)
        self.assertEqual(reviewed['actions'][0]['status'], 'in_progress')
        self.assertEqual(reviewed['actions'][0]['supports'], [])
        self.assertEqual(reviewed['actions'][0]['closure_note'], '')
        self.assertTrue(any(item['status'] == 'closed' for item in reviewed['actions'][0]['history']))

    def test_changed_revision_flags_context_and_old_revision_writes_are_refused(self):
        self.create()
        self.close()
        revised = deepcopy(self.project)
        revised['inputs'][self.limit_id]['value'] = 240
        self.server.store.save_revision(self.identity, 1, revised)
        self.server.store.run(self.identity, 2)
        updated = self.profile(2)
        self.assertEqual(updated['actions'][0]['status'], 'closed')
        self.assertEqual(updated['actions'][0]['review_status'], 'needs_review')
        self.assertEqual(self.profile(1)['actions'][0]['review_status'], 'current')
        self.assertEqual(self.update('in_progress', revision=1)[0], 409)
        self.assertEqual(self.server.store.get(self.identity, 1)['run'], self.initial['run'])

    def test_stale_and_null_digest_and_foreign_origin_are_rejected(self):
        profile = self.profile()
        origin = next(o for o in profile['origins'] if o['target_id'] == 'finding:thermal_limit')
        spec = {**origin['suggested'], 'origin_id': origin['target_id'], 'note': ''}
        body = {'project_id': self.identity, 'revision': 1, 'expected_digest': None, 'spec': spec}
        self.assertEqual(self.request('/api/actions', body)[0], 400)
        body['expected_digest'] = profile['digest']
        self.assertEqual(self.request('/api/actions', body, 'https://example.invalid')[0], 403)
        self.create()
        self.assertEqual(self.request('/api/actions', body)[0], 409)
        self.assertEqual(len(self.profile()['actions']), 1)

    def test_queue_assets_and_reopened_store_preserve_action_history(self):
        self.create()
        for route in ('/action-queue.js', '/action-queue.css'):
            code, content = self.request(route)
            self.assertEqual(code, 200)
            self.assertTrue(content)
        from sixd.workspace_sources import WorkspaceSources
        from sixd.workspace_actions import WorkspaceActions
        reopened = workspace.WorkspaceStore(self.server.store.db_path)
        queue = WorkspaceActions(reopened, WorkspaceSources(reopened))
        self.assertEqual(queue.summary(self.identity, 1)['digest'], self.profile()['digest'])


if __name__ == '__main__':
    unittest.main()
