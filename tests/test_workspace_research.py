"""Research is explicit, scoped, credit-bounded and separate from engineering."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import workspace_research as research
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError, _encode
from sixd.workspace_sources import WorkspaceSources


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.store = WorkspaceStore(Path(self.temp.name) / 'workspace.sqlite3')
        self.project = deepcopy(example_projects()['baseline'])
        self.identity = self.project['project_id']
        self.store.create_project(self.project)
        self.sources = WorkspaceSources(self.store)
        self.calls = []
        self.response = {'request_id': 'constructed-request', 'usage': {'credits': 1}, 'results': [{
            'title': 'Supplied spacecraft reference', 'url': 'https://www.nasa.gov/example/reference',
            'content': 'A constructed excerpt, not a verified engineering reference.', 'score': .8}]}
        self.service = research.WorkspaceResearch(self.store, self.sources, self.transport)
        self.key = 'tvly-constructed-private-key'

    def tearDown(self):
        self.temp.cleanup()

    def transport(self, key, body):
        self.calls.append((key, deepcopy(body)))
        return deepcopy(self.response)

    def search(self, **overrides):
        value = {'project_id': self.identity, 'revision': 1, 'target_id': 'requirement:thermal_limit',
            'query': 'spacecraft steady radiative equilibrium model assumptions',
            'expected_digest': self.sources.summary(self.identity, 1)['digest']}
        value.update(overrides)
        return self.service.search(**value)

    def canonical(self):
        with self.store._connect() as db:
            return {table: [tuple(row) for row in db.execute('SELECT * FROM ' + table + ' ORDER BY rowid')]
                for table in ('projects', 'revisions', 'runs', 'project_source_versions', 'project_source_link_versions')}

    def connect(self, limit=5):
        return self.service.connect(self.key, limit)

    def test_status_connect_list_disconnect_are_offline_and_key_never_exposed(self):
        before = self.canonical()
        self.assertFalse(self.service.status()['key_present'])
        status = self.connect()
        self.assertTrue(status['key_present'])
        self.assertNotIn(self.key, _encode(status))
        listing = self.service.list(self.identity, 1)
        self.assertEqual(listing['searches'], [])
        self.assertIn('requirement:thermal_limit', [target['target_id'] for target in listing['targets']])
        self.assertFalse(self.service.disconnect()['key_present'])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.canonical(), before)

    def test_one_explicit_search_freezes_scope_and_only_sends_entered_query(self):
        self.connect()
        before = self.canonical()
        receipt = self.search()
        self.assertEqual(receipt['state'], 'completed')
        self.assertEqual(receipt['version'], 2)
        self.assertEqual(receipt['target']['target_id'], 'requirement:thermal_limit')
        self.assertEqual(receipt['results'][0]['index'], 0)
        self.assertEqual(self.calls, [(self.key, {'query': receipt['query'], **research.PARAMETERS})])
        self.assertEqual(receipt['reported_usage'], {'credits': 1})
        self.assertNotIn(self.key, _encode(receipt))
        self.assertEqual(self.service.get(receipt['search_id'], self.identity, 1), receipt)
        self.assertEqual(self.service.list(self.identity, 1)['searches'][0]['result_count'], 1)
        self.assertEqual(self.service.status()['reserved_credits'], 1)
        self.assertEqual(self.canonical(), before)

    def test_stale_target_and_library_preflight_do_not_reserve_or_call(self):
        self.connect()
        for values in ({'expected_digest': '0' * 64}, {'expected_digest': None},
                {'target_id': 'requirement:missing'}, {'revision': 2}, {'query': self.key}):
            with self.assertRaises(WorkspaceError):
                self.search(**values)
        self.assertEqual(self.service.status()['reserved_credits'], 0)
        self.assertEqual(self.calls, [])

    def test_reservation_survives_failure_reconnect_and_restart(self):
        self.connect(1)
        self.service._transport = lambda *args: (_ for _ in ()).throw(RuntimeError('secret ' + self.key))
        receipt = self.search()
        self.assertEqual(receipt['state'], 'failed')
        self.assertEqual(receipt['error']['code'], 'provider_transport')
        self.assertNotIn(self.key, _encode(receipt))
        self.service.disconnect()
        self.connect(1)
        with self.assertRaises(WorkspaceError):
            self.search()
        fresh = research.WorkspaceResearch(self.store, self.sources, self.transport)
        self.assertEqual(fresh.status()['reserved_credits'], 1)
        self.assertFalse(fresh.status()['key_present'])
        fresh.connect(self.key, 1)
        with self.assertRaises(WorkspaceError):
            fresh.search(self.identity, 1, 'requirement:thermal_limit', 'explicit query', self.sources.summary(self.identity, 1)['digest'])
        self.assertEqual(self.calls, [])

    def test_absolute_allowance_is_not_incremented_by_reconnect(self):
        self.connect(2)
        self.search()
        self.connect(2)
        self.search()
        self.assertEqual(self.service.status()['remaining_credits'], 0)
        with self.assertRaises(WorkspaceError):
            self.search()
        with self.assertRaises(WorkspaceError):
            self.connect(1)
        for invalid in (0, research.MAX_CREDITS + 1, True, 2.0, '5'):
            with self.assertRaises(WorkspaceError):
                self.connect(invalid)

    def test_invalid_provider_responses_are_controlled_and_never_imported(self):
        self.connect(20)
        valid = deepcopy(self.response)
        variants = [b'{"results":[],"results":[]}', b'{"results":NaN}', b'invalid JSON',
            b'x' * (research.MAX_RESPONSE_BYTES + 1), {'results': None}, {'results': [valid['results'][0]] * 6},
            {'results': [{'title': 'Missing content', 'url': 'https://nasa.gov'}]},
            {**valid, 'usage': {'credits': float('inf')}},
            {**valid, 'private': self.key},
            json.dumps({**valid, 'private': self.key}).replace('tvly', '\\u0074vly').encode()]
        before = self.canonical()
        for raw in variants:
            self.service._transport = lambda *args, raw=raw: raw
            receipt = self.search()
            self.assertEqual(receipt['state'], 'failed')
            self.assertEqual(receipt['error']['code'], 'provider_response')
            self.assertEqual(receipt['results'], [])
            self.assertNotIn(self.key, _encode(receipt))
        self.assertEqual(self.service.status()['reserved_credits'], len(variants))
        self.assertEqual(self.canonical(), before)

    def test_private_and_unsafe_result_urls_are_rejected_without_fetching(self):
        self.connect(20)
        for url in ('javascript:alert(1)', 'http://127.0.0.1/private', 'http://[::1]/',
                'https://user:pass@example.org', 'http://10.0.0.1', 'http://localhost.localdomain',
                'http://host.local', 'https://127.1/', 'https://internal', 'https://bad\\host.org'):
            self.response['results'][0]['url'] = url
            receipt = self.search()
            self.assertEqual(receipt['state'], 'failed', url)
            self.assertEqual(receipt['results'], [])
        self.assertEqual(len(self.calls), 10)

    def test_preview_is_pure_and_carries_exact_search_provenance(self):
        self.connect()
        self.response['results'][0]['content'] = 'A' * 8010
        receipt = self.search()
        before = self.canonical()
        form = self.service.preview_source(receipt, 0)
        self.assertEqual(form['source_id'], None)
        self.assertEqual(len(form['excerpt']), 8000)
        self.assertIn(receipt['digest'], form['details'])
        self.assertIn(receipt['query'], form['details'])
        self.assertIn('truncated', form['details'])
        self.assertEqual(self.canonical(), before)
        for index in (True, -1, 1):
            with self.assertRaises(WorkspaceError):
                self.service.preview_source(receipt, index)
        corrupt = deepcopy(receipt)
        corrupt['results'][0]['title'] = 'Replaced'
        with self.assertRaises(WorkspaceError):
            self.service.preview_source(corrupt, 0)

    def test_historical_read_scopes_and_current_write_guards(self):
        self.connect()
        receipt = self.search()
        changed = deepcopy(self.project)
        changed['inputs']['heat_input']['value'] += 1
        self.store.save_revision(self.identity, 1, changed)
        self.assertEqual(self.service.get(receipt['search_id'], self.identity, 2), receipt)
        self.assertFalse(self.service.list(self.identity, 1)['can_search'])
        with self.assertRaises(ConflictError):
            self.search()
        other = deepcopy(self.project)
        other['project_id'] = 'other-research-project'
        self.store.create_project(other)
        with self.assertRaises(WorkspaceError):
            self.service.get(receipt['search_id'], other['project_id'], 1)
        profile = self.sources.summary(self.identity, 2)
        newer = self.service.search(self.identity, 2, 'requirement:thermal_limit', 'Second explicit search', profile['digest'])
        with self.assertRaises(WorkspaceError):
            self.service.get(newer['search_id'], self.identity, 1)
        self.assertEqual(len(self.calls), 2)

    def test_corrupt_saved_receipt_and_rehashed_request_mutation_are_refused(self):
        self.connect()
        receipt = self.search()
        with self.store._connect(write=True) as db:
            row = db.execute('SELECT snapshot FROM project_research_versions WHERE search_id=? AND version=2', (receipt['search_id'],)).fetchone()
            stored = json.loads(row[0]);stored['query'] = 'Changed later'
            from sixd.workspace import _digest
            stored['digest'] = _digest({k: v for k, v in stored.items() if k != 'digest'})
            db.execute('UPDATE project_research_versions SET snapshot=?,digest=? WHERE search_id=? AND version=2', (_encode(stored), stored['digest'], receipt['search_id']))
        with self.assertRaises(WorkspaceError):
            self.service.get(receipt['search_id'], self.identity, 1)

    def test_transport_has_fixed_destination_no_redirect_and_no_retry(self):
        class Response(BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
        class Opener:
            def __init__(self): self.calls = []
            def open(inner, request, timeout):
                inner.calls.append((request, timeout))
                return Response(b'{"results":[]}')
        opener = Opener()
        with patch.object(research, 'build_opener', return_value=opener) as factory:
            self.assertEqual(research._transport(self.key, {'query': 'user entered'}), b'{"results":[]}')
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, 'https://api.tavily.com/search')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(timeout, 30)
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(factory.call_args.args[0].proxies, {})
        self.assertIsNone(factory.call_args.args[1].redirect_request(None, None, 302, '', {}, 'http://localhost/private'))
        for status, code in ((401, 'provider_auth'), (403, 'provider_auth'), (429, 'provider_quota'), (432, 'provider_quota'), (433, 'provider_quota'), (302, 'provider_transport'), (500, 'provider_transport')):
            with patch.object(research, 'build_opener') as factory:
                factory.return_value.open.side_effect = HTTPError(research.ENDPOINT, status, self.key, {}, BytesIO(b'private'))
                with self.assertRaises(research._ResearchFailure) as caught:
                    research._transport(self.key, {'query': 'explicit'})
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(factory.return_value.open.call_count, 1)

    def test_transport_limit_and_network_error_do_not_leak_details(self):
        class Response(BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
        for payload in (b'x' * (research.MAX_RESPONSE_BYTES + 1),):
            with patch.object(research, 'build_opener') as factory:
                factory.return_value.open.return_value = Response(payload)
                with self.assertRaises(research._ResearchFailure) as caught:
                    research._transport(self.key, {})
                self.assertEqual(caught.exception.code, 'provider_response')
        with patch.object(research, 'build_opener') as factory:
            factory.return_value.open.side_effect = URLError(self.key)
            with self.assertRaises(research._ResearchFailure) as caught:
                research._transport(self.key, {})
            self.assertNotIn(self.key, str(caught.exception))

    def test_pending_search_does_not_block_status_or_reset_reservation(self):
        self.connect(1)
        started, finish = threading.Event(), threading.Event()
        results, statuses = [], []
        def slow(key, body):
            started.set()
            finish.wait(3)
            return self.response
        self.service._transport = slow
        worker = threading.Thread(target=lambda: results.append(self.search()))
        worker.start()
        try:
            self.assertTrue(started.wait(2))
            reader = threading.Thread(target=lambda: statuses.append(self.service.status()))
            reader.start();reader.join(1)
            self.assertFalse(reader.is_alive(), 'Status must not wait for provider network I/O')
            self.assertEqual(statuses[0]['active_requests'], 1)
            self.assertEqual(statuses[0]['reserved_credits'], 1)
            with self.assertRaises(ConflictError):
                self.service.disconnect()
        finally:
            finish.set();worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0]['state'], 'completed')
        self.service.disconnect()
        self.assertFalse(self.service.status()['key_present'])
        self.assertEqual(self.service.status()['active_requests'], 0)

    def test_interrupted_attempt_stays_pending_and_reserved(self):
        self.connect(1)
        self.service._transport = lambda *args: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.search()
        self.assertEqual(self.service.status()['reserved_credits'], 1)
        self.assertEqual(self.service.status()['active_requests'], 0)
        listing = self.service.list(self.identity, 1)
        self.assertEqual(listing['searches'][0]['state'], 'pending')
        with self.assertRaises(WorkspaceError):
            self.search()

    def test_json_escaped_credentials_are_rejected_in_decoded_strings_and_keys(self):
        for key in ('tvly-quote-"private', 'tvly-backslash-\\private'):
            self.key = key
            self.connect(20)
            for location in ('content', 'unknown_field', 'object_key', 'json_excerpt', 'nested_json_excerpt'):
                payload = deepcopy(self.response)
                if location == 'content':
                    payload['results'][0]['content'] = 'Accidental echoed secret: ' + key
                elif location == 'unknown_field':
                    payload['unrecognized'] = {'nested': [key]}
                elif location == 'json_excerpt':
                    payload['results'][0]['content'] = json.dumps({'token': key})
                elif location == 'nested_json_excerpt':
                    payload['results'][0]['content'] = json.dumps(json.dumps({'token': key}))
                else:
                    payload[key] = 'Unexpected provider key'
                raw = json.dumps(payload).encode('utf-8')
                self.assertNotIn(key, raw.decode('utf-8'))
                self.service._transport = lambda *args, raw=raw: raw
                receipt = self.search()
                self.assertEqual(receipt['state'], 'failed')
                self.assertEqual(receipt['error']['code'], 'provider_response')
                self.assertEqual(receipt['results'], [])
                self.assertFalse(research._contains_secret(receipt, key))

    def test_unexpected_provider_usage_is_preserved_with_billing_warning(self):
        self.connect()
        self.response['usage']['credits'] = 2
        receipt = self.search()
        self.assertEqual(receipt['state'], 'completed')
        self.assertEqual(receipt['reported_usage']['credits'], 2)
        self.assertEqual(receipt['reserved_credits'], 1)
        self.assertIn('not a provider billing ceiling', receipt['usage_warning'])
        self.assertEqual(self.service.get(receipt['search_id'], self.identity, 1)['usage_warning'], receipt['usage_warning'])
        self.assertTrue(self.service.status()['usage_review_required'])
        self.assertFalse(self.service.status()['can_search'])
        self.assertFalse(self.service.list(self.identity, 1)['can_search'])
        self.connect(20)
        with self.assertRaisesRegex(WorkspaceError, 'blocked'):
            self.search()
        self.assertEqual(len(self.calls), 1)
        restarted = research.WorkspaceResearch(self.store, self.sources, self.transport)
        restarted.connect(self.key, 20)
        self.assertTrue(restarted.status()['usage_review_required'])
        with self.assertRaisesRegex(WorkspaceError, 'blocked'):
            restarted.search(self.identity, 1, 'requirement:thermal_limit', 'Another query', self.sources.summary(self.identity, 1)['digest'])
        self.assertEqual(len(self.calls), 1)


if __name__ == '__main__':
    unittest.main()
