"""Optional research and source-aware investigations through isolated HTTP."""
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from sixd import workspace
from sixd.workspace_server import create_server
from sixd.workspace_research import WorkspaceResearch, PARAMETERS
from test_workspace_ai_api import offline_factory, write_offline_config, KEY as AI_KEY

KEY = 'synthetic-tavily-test-key-not-real'


class SourceResearchAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.folder = Path(self.temp.name)
        write_offline_config(self.folder)
        self.calls = []
        self.transport_error = False
        self.server = create_server(port=0, db_path=self.folder / 'workspace.sqlite3',
            provider_factory=offline_factory, research_transport=self.transport)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.pid = self.server.store.ensure_default()
        self.original = self.server.store.get(self.pid, 1)['run']

    def tearDown(self):
        deadline = time.monotonic() + 10
        while self.server.ai._active and time.monotonic() < deadline:
            threading.Event().wait(.01)
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.temp.cleanup()

    def transport(self, key, body):
        self.assertEqual(key, KEY)
        self.calls.append(deepcopy(body))
        if self.transport_error:
            raise RuntimeError('Provider exception must be hidden: ' + KEY)
        return json.dumps({'request_id': 'constructed-search-response', 'usage': {'credits': 1},
            'results': [{'title': 'Constructed thermal reference <manual>', 'url': 'https://example.org/thermal-reference',
                'content': 'Steady balance omits transient heat storage; this is a synthetic reference.', 'score': .8}]}).encode()

    def request(self, path, body=None, origin=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=20)
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        conn.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), headers)
        res = conn.getresponse()
        status, raw = res.status, res.read()
        value = json.loads(raw) if 'application/json' in res.getheader('Content-Type', '') else raw
        conn.close()
        return status, value

    def query(self, revision=1):
        return '?project_id=' + self.pid + '&revision=' + str(revision)

    def search_body(self):
        profile = self.request('/api/research' + self.query())[1]
        return {'project_id': self.pid, 'revision': 1, 'target_id': 'requirement:thermal_limit',
            'query': 'steady radiative thermal equilibrium assumptions', 'expected_digest': profile['library_digest']}

    def connect(self, limit=5):
        code, value = self.request('/api/research/connect', {'api_key': KEY, 'credit_limit': limit})
        self.assertEqual(code, 200, value)
        self.assertNotIn(KEY, json.dumps(value))
        return value

    def test_connection_and_navigation_never_search_or_change_numerical_evidence(self):
        before = self.request('/api/ai/status')[1]['budget']
        self.assertFalse(self.request('/api/research/status')[1]['key_present'])
        self.connect()
        for route in ('/source-research.js', '/source-research.css', '/api/research' + self.query()):
            self.assertEqual(self.request(route)[0], 200)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.request('/api/ai/status')[1]['budget'], before)
        self.assertEqual(self.server.store.get(self.pid, 1)['run'], self.original)
        self.assertEqual(self.request('/api/research/disconnect', {})[0], 200)

    def test_search_preview_and_explicit_save_link_are_separate(self):
        self.connect()
        body = self.search_body()
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('Research must not calculate')):
            code, receipt = self.request('/api/research/search', body)
            self.assertEqual(code, 200, receipt)
            self.assertEqual(receipt['state'], 'completed')
            self.assertEqual(self.calls, [{'query': body['query'], **PARAMETERS}])
            code, preview = self.request('/api/research/' + receipt['search_id'] + '/preview' + self.query() + '&result_index=0')
            self.assertEqual(code, 200, preview)
            self.assertEqual(preview['receipt_digest'], receipt['digest'])
            self.assertIn(receipt['search_id'], preview['source']['details'])
            self.assertEqual(self.request('/api/sources' + self.query())[1]['sources'], [])
            code, profile = self.request('/api/sources', {'project_id': self.pid, 'revision': 1, 'source': preview['source']})
            self.assertEqual(code, 200, profile)
            self.assertEqual(profile['links'], [])
            source = profile['sources'][0]
            code, linked = self.request('/api/source-links', {'project_id': self.pid, 'revision': 1,
                'expected_digest': profile['digest'], 'spec': {'source_id': source['source_id'], 'source_version': 1,
                'target_id': body['target_id'], 'note': 'User-reviewed reference relevance only.'}})
            self.assertEqual(code, 200, linked)
            self.assertEqual(len(linked['links']), 1)
        self.assertEqual(self.server.store.get(self.pid, 1)['run'], self.original)
        self.assertNotIn(KEY, json.dumps([receipt, preview, linked]))

    def test_stale_historical_and_unavailable_scope_refused_before_reservation(self):
        self.connect()
        body = self.search_body()
        self.server.sources.save_source(self.pid, 1, {'source_id': None, 'base_version': None,
            'title': 'Changed source context', 'url': 'https://example.org/change', 'excerpt': 'Supplied change.', 'details': ''})
        self.assertEqual(self.request('/api/research/search', body)[0], 409)
        body = self.search_body()
        body['target_id'] = 'requirement:missing'
        self.assertIn(self.request('/api/research/search', body)[0], (400, 409))
        self.server.store.save_revision(self.pid, 1, self.server.store.get(self.pid, 1)['project'])
        self.assertEqual(self.request('/api/research/search', self.search_body())[0], 409)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.request('/api/research/status')[1]['reserved_credits'], 0)

    def test_failed_reservation_and_reconnect_do_not_retry_or_reset(self):
        self.connect(limit=1)
        self.transport_error = True
        code, failed = self.request('/api/research/search', self.search_body())
        self.assertEqual(code, 200, failed)
        self.assertEqual(failed['state'], 'failed')
        self.assertNotIn(KEY, json.dumps(failed))
        self.assertEqual(len(self.calls), 1)
        self.request('/api/research/disconnect', {})
        status = self.connect(limit=1)
        self.assertEqual(status['reserved_credits'], 1)
        self.assertEqual(status['remaining_credits'], 0)
        self.assertEqual(self.request('/api/research/search', self.search_body())[0], 400)
        self.assertEqual(len(self.calls), 1)
        restored = WorkspaceResearch(self.server.store, self.server.sources, transport=self.transport)
        self.assertFalse(restored.status()['key_present'])
        self.assertEqual(restored.status()['reserved_credits'], 1)

    def test_origin_fields_runtime_guards_and_key_in_query(self):
        self.connect()
        body = self.search_body()
        self.assertEqual(self.request('/api/research/search', body, 'https://example.invalid')[0], 403)
        self.assertEqual(self.request('/api/research/connect', {'api_key': KEY, 'credit_limit': True})[0], 400)
        self.assertEqual(self.request('/api/research/search', {**body, 'unexpected': True})[0], 400)
        self.assertEqual(self.request('/api/research/search', {**body, 'query': KEY})[0], 400)
        with patch('sixd.workspace_server._code_fingerprint', return_value='stale'):
            self.assertEqual(self.request('/api/research' + self.query())[0], 409)
            self.assertEqual(self.request('/api/research/search', body)[0], 409)
        self.assertEqual(self.calls, [])

    def test_new_assistant_captures_saved_link_without_web_search(self):
        profile = self.server.sources.save_source(self.pid, 1, {'source_id': None, 'base_version': None,
            'title': 'Supplied offline reference', 'url': 'https://example.org/reference',
            'excerpt': 'Steady balance omits transient heat storage.', 'details': 'Constructed, unverified reference.'})
        source = profile['sources'][0]
        self.server.sources.link_source(self.pid, 1, {'source_id': source['source_id'], 'source_version': 1,
            'target_id': 'requirement:thermal_limit', 'note': 'Declared relevance only.'})
        self.assertEqual(self.request('/api/ai/connect', {'api_key': AI_KEY})[0], 200)
        code, queued = self.request('/api/investigations', {'project_id': self.pid, 'revision': 1,
            'requirement_id': 'thermal_limit', 'question': 'Explain the saved finding and relevant reference limitations.'})
        self.assertEqual(code, 200, queued)
        self.assertEqual(queued['project_sources']['links'][0]['source']['excerpt'], source['excerpt'])
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            code, record = self.request('/api/investigations/' + queued['investigation_id'])
            if record['state'] not in ('queued', 'running'):
                break
            threading.Event().wait(.01)
        self.assertEqual(record['state'], 'completed', record)
        self.assertEqual(record['project_sources'], queued['project_sources'])
        self.assertEqual(record['live_model_calls'], 0)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.server.store.get(self.pid, 1)['run'], self.original)


if __name__ == '__main__':
    unittest.main()
