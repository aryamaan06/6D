"""Source annotations remain supplemental through real HTTP and report export."""
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


class WorkspaceSourcesAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.server = create_server(port=0, db_path=Path(self.temp.name) / 'workspace.sqlite3',
            provider_factory=lambda *a, **kw: (_ for _ in ()).throw(AssertionError('Library cannot call a provider')))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.project = deepcopy(example_projects()['baseline'])
        self.identity = self.project['project_id']
        self.server.store.create_project(self.project)
        self.initial = self.server.store.run(self.identity, 1)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.temp.cleanup()

    def request(self, path, body=None, origin=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        conn.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), headers)
        res = conn.getresponse()
        code, raw = res.status, res.read()
        value = json.loads(raw) if 'application/json' in res.getheader('Content-Type', '') else raw
        conn.close()
        return code, value

    def source(self):
        return {'source_id': None, 'base_version': None, 'title': 'User-supplied thermal note',
                'url': 'https://example.org/thermal-note', 'excerpt': 'Constructed reference excerpt, not a validated source.',
                'details': 'Local HTTP acceptance fixture.'}

    def add(self):
        status, profile = self.request('/api/sources', {'project_id': self.identity, 'revision': 1, 'source': self.source()})
        self.assertEqual(status, 200, profile)
        return profile['sources'][0]

    def link(self, source, target='requirement:thermal_limit', revision=1):
        profile = self.request('/api/sources?project_id=' + self.identity + '&revision=' + str(revision))[1]
        return self.request('/api/source-links', {'project_id': self.identity, 'revision': revision,
            'expected_digest': profile['digest'],
            'spec': {'source_id': source['source_id'], 'source_version': source['version'],
                     'target_id': target, 'note': 'User-declared relevance, not verification.'}})

    def test_three_target_kinds_export_atomically_without_changing_original_review(self):
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('Source operations must not calculate')):
            source = self.add()
            for target in ('requirement:thermal_limit', 'assumption:thermal:0', 'finding:thermal_limit'):
                status, profile = self.link(source, target)
                self.assertEqual(status, 200, profile)
            status, exported = self.request('/api/engineering-review-export?project_id=' + self.identity + '&revision=1')
            self.assertEqual(status, 200, exported)
            self.assertEqual(len(exported['project_sources']['links']), 3)
            self.assertEqual(exported['workspace']['run']['review'], self.initial['run']['review'])
            self.assertEqual(exported['project_sources']['run_id'], exported['workspace']['run']['run_id'])
            enclosing = exported.pop('export_digest')
            self.assertEqual(enclosing, workspace._digest(exported))
            library = exported['project_sources']
            self.assertEqual(library['digest'], workspace._digest({k: v for k, v in library.items() if k != 'digest'}))
            self.assertFalse(exported['launch_authorization'])
            self.assertEqual(exported['live_model_calls'], 0)
        self.assertEqual(self.server.store.get(self.identity, 1)['run'], self.initial['run'])

    def test_new_source_version_keeps_old_export_and_link_until_explicit_review(self):
        source = self.add()
        status, before = self.link(source)
        self.assertEqual(status, 200, before)
        link = before['links'][0]
        old_export = self.request('/api/engineering-review-export?project_id=' + self.identity + '&revision=1')[1]
        updated = self.source()
        updated.update(source_id=source['source_id'], base_version=1, excerpt='Changed user-supplied passage.')
        status, profile = self.request('/api/sources', {'project_id': self.identity, 'revision': 1, 'source': updated})
        self.assertEqual(status, 200, profile)
        self.assertEqual(profile['links'][0]['status'], 'needs_review')
        self.assertEqual(profile['links'][0]['source']['excerpt'], source['excerpt'])
        self.assertEqual(old_export['project_sources']['links'][0]['source']['excerpt'], source['excerpt'])
        status, confirmed = self.request('/api/source-links/confirm', {'project_id': self.identity, 'revision': 1,
            'link_id': link['link_id'], 'base_version': 1, 'expected_digest': profile['digest']})
        self.assertEqual(status, 200, confirmed)
        self.assertEqual(confirmed['links'][0]['source_version'], 2)
        self.assertEqual(confirmed['links'][0]['version'], 2)
        self.assertEqual(len(confirmed['links'][0]['history']), 2)
        self.assertEqual(self.server.store.get(self.identity, 1)['run'], self.initial['run'])

    def test_requirement_change_flags_link_and_historical_write_is_refused(self):
        source = self.add()
        self.assertEqual(self.link(source)[0], 200)
        revised = deepcopy(self.project)
        limit_id = next(r['limit_input'] for r in revised['requirements'] if r['id'] == 'thermal_limit')
        revised['inputs'][limit_id]['value'] -= 1
        self.server.store.save_revision(self.identity, 1, revised)
        status, profile = self.request('/api/sources?project_id=' + self.identity + '&revision=2')
        self.assertEqual(status, 200, profile)
        self.assertEqual(profile['links'][0]['status'], 'needs_review')
        status, original = self.request('/api/sources?project_id=' + self.identity + '&revision=1')
        self.assertEqual(original['links'][0]['status'], 'linked')
        status, refused = self.request('/api/sources', {'project_id': self.identity, 'revision': 1, 'source': self.source()})
        self.assertEqual(status, 409, refused)

    def test_unsafe_url_foreign_origin_and_bad_target_are_refused(self):
        bad = self.source()
        bad['url'] = 'javascript:alert(1)'
        self.assertEqual(self.request('/api/sources', {'project_id': self.identity, 'revision': 1, 'source': bad})[0], 400)
        self.assertEqual(self.request('/api/sources', {'project_id': self.identity, 'revision': 1, 'source': self.source()}, 'https://example.invalid')[0], 403)
        source = self.add()
        self.assertEqual(self.link(source, 'finding:invented')[0], 409)
        self.assertEqual(self.request('/api/sources?project_id=' + self.identity + '&revision=1')[1]['links'], [])

    def test_assets_load_and_append_only_tables_survive_reopen(self):
        self.add()
        reopened = workspace.WorkspaceStore(self.server.store.db_path)
        from sixd.workspace_sources import WorkspaceSources
        self.assertEqual(len(WorkspaceSources(reopened).summary(self.identity, 1)['sources']), 1)
        for route in ('/source-library.js', '/source-library.css'):
            status, content = self.request(route)
            self.assertEqual(status, 200)
            self.assertTrue(content)

    def test_stale_review_context_and_null_digest_cannot_confirm_unseen_source(self):
        source = self.add()
        status, reviewed = self.link(source)
        self.assertEqual(status, 200)
        link = reviewed['links'][0]
        updated = self.source()
        updated.update(source_id=source['source_id'], base_version=1, excerpt='An unseen replacement source version.')
        self.assertEqual(self.request('/api/sources', {'project_id': self.identity, 'revision': 1, 'source': updated})[0], 200)
        confirmation = {'project_id': self.identity, 'revision': 1, 'link_id': link['link_id'],
                        'base_version': 1, 'expected_digest': reviewed['digest']}
        self.assertEqual(self.request('/api/source-links/confirm', confirmation)[0], 409)
        confirmation['expected_digest'] = None
        self.assertEqual(self.request('/api/source-links/confirm', confirmation)[0], 400)
        kept = self.request('/api/sources?project_id=' + self.identity + '&revision=1')[1]
        self.assertEqual(kept['links'][0]['source_version'], 1)
        self.assertEqual(kept['links'][0]['version'], 1)


if __name__ == '__main__':
    unittest.main()
