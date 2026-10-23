"""No-network checks for explicit, sanitized and non-retriable metrics exports."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import workspace_observability as observation
from sixd.model_evaluation import CANDIDATES
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError, _digest, _encode


def qualification_record(identity=None):
    rows = [{'case_id': case_id, 'state': 'completed', 'elapsed_seconds': index + .25,
             'reserved_usd': .01, 'request_reservations': 2, 'live_model_calls': 2,
             'score': {'workflow_gate_pass': True, 'summary': 'PRIVATE explanation text'},
             'receipt': {'state': 'completed', 'summary': 'PRIVATE rocket mass=12345 and prompt'}}
            for index, case_id in enumerate(observation.CASE_IDS)]
    report = {'mode': 'live_comparison', 'rows': rows, 'private': 'PRIVATE field'}
    report['report_digest'] = _digest(report)
    return {'schema': 'sixd.ai-qualification.v1', 'qualification_id': identity or uuid4().hex,
            'state': 'completed', 'created_at': '2026-10-24T05:00:00+00:00',
            'completed_at': '2026-10-24T05:01:00+00:00', 'model': CANDIDATES[1]['model'],
            'agent_sources': {'PRIVATE source filename': 'a' * 64},
            'report': report, 'reserved_usd': .04, 'request_reservations': 8, 'live_model_calls': 8}


class QualificationFixture:
    def __init__(self):
        self.record = qualification_record()

    def get(self, identity):
        if identity != self.record['qualification_id']:
            raise WorkspaceError('Qualification not found.')
        return deepcopy(self.record)

    def status(self):
        return {'state': self.record['state']}


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.store = WorkspaceStore(Path(self.temp.name) / 'workspace.sqlite3')
        self.ai = SimpleNamespace(store=self.store, _key='NEBIUS-private-test-key')
        self.qualification = QualificationFixture()
        self.calls = []
        self.response = {'status': 202}
        self.key = 'LANGSMITH-private-test-key'
        self.service = observation.WorkspaceObservability(self.ai, self.qualification, transport=self.transport)

    def tearDown(self):
        self.temp.cleanup()

    def transport(self, endpoint, headers, body):
        self.calls.append((endpoint, deepcopy(headers), deepcopy(body)))
        return deepcopy(self.response)

    def preview(self):
        return self.service.preview(self.qualification.record['qualification_id'])

    def export(self, **kwargs):
        value = self.preview()
        return self.service.export(value['qualification_id'], value['preview_digest'], **kwargs)

    def connect(self, **kwargs):
        return self.service.connect(self.key, **kwargs)

    def test_setup_read_preview_disconnect_never_send_and_do_not_expose_keys(self):
        self.assertFalse(self.service.status()['key_present'])
        initial = self.preview()
        self.assertEqual(initial, self.preview())
        status = self.connect(region='eu', workspace_id='0c678cf0-6414-4356-bb55-188cf9725820')
        self.assertTrue(status['key_present'])
        self.assertEqual(status['endpoint'], observation.ENDPOINTS['eu'])
        self.assertEqual(self.service.list()['exports'], [])
        self.assertFalse(self.service.disconnect()['key_present'])
        self.assertEqual(self.calls, [])
        for value in (initial, status, self.preview()):
            self.assertNotIn(self.key, _encode(value))
            self.assertNotIn(self.ai._key, _encode(value))

    def test_explicit_export_uses_only_allowlisted_metrics_one_request_and_retained_receipt(self):
        self.connect(region='eu', workspace_id='0c678cf0-6414-4356-bb55-188cf9725820')
        preview = self.preview()
        rendered = _encode(preview)
        self.assertNotIn('PRIVATE', rendered)
        self.assertNotIn('12345', rendered)
        self.assertNotIn('receipt', rendered)
        receipt = self.export()
        self.assertEqual(receipt['state'], 'accepted_by_api')
        self.assertEqual(receipt['version'], 2)
        self.assertEqual(len(self.calls), 1)
        endpoint, headers, body = self.calls[0]
        self.assertEqual(endpoint, observation.ENDPOINTS['eu'])
        self.assertEqual(headers['x-api-key'], self.key)
        self.assertEqual(headers['x-tenant-id'], '0c678cf0-6414-4356-bb55-188cf9725820')
        self.assertEqual(body, preview['payload'])
        self.assertEqual(body['outputs']['cases'][0]['elapsed_seconds'], .25)
        self.assertEqual(body['inputs']['agent_source_hashes'], ['a' * 64])
        self.assertEqual(self.service.get(receipt['export_id']), receipt)
        self.assertEqual(self.service.list()['exports'], [receipt])
        self.assertNotIn(self.key, _encode(receipt))
        with self.assertRaises(ConflictError):
            self.export()
        self.assertEqual(len(self.calls), 1)

    def test_payload_drops_free_text_even_when_containing_both_credentials(self):
        row = self.qualification.record['report']['rows'][0]
        row['receipt']['summary'] = self.key + self.ai._key
        row['score']['summary'] = json.dumps({'nested': json.dumps({'key': self.key})})
        self.qualification.record['agent_sources'] = {self.key: 'b' * 64}
        self.qualification.record['question'] = self.ai._key
        self.connect()
        payload = self.export()['payload']
        self.assertNotIn(self.key, _encode(payload))
        self.assertNotIn(self.ai._key, _encode(payload))
        self.assertEqual(len(self.calls), 1)

    def test_actual_allowlisted_credential_match_blocks_before_reservation(self):
        self.service.connect('a' * 64)
        with self.assertRaises(WorkspaceError):
            self.preview()
        self.assertEqual(self.service.status()['attempts'], 0)
        self.assertEqual(self.calls, [])
        for value in ({'x': json.dumps({'deep': json.dumps({'key': self.key})})},
                      json.dumps({'nested': self.key}).replace('L', '\\u004c')):
            self.assertTrue(observation._contains_secret(value, (self.key,)))

    def test_not_run_observations_are_unknown_not_fabricated_zeroes(self):
        row = self.qualification.record['report']['rows'][3]
        for key in ('elapsed_seconds', 'reserved_usd', 'request_reservations', 'live_model_calls', 'score'):
            row.pop(key)
        row['state'] = 'not_run'
        value = self.preview()['payload']['outputs']['cases'][3]
        for name in ('elapsed_seconds', 'reserved_usd', 'request_reservations', 'live_model_calls', 'workflow_gate_pass'):
            self.assertIsNone(value[name])

    def test_malformed_or_injected_context_never_reaches_transport(self):
        self.connect()
        original = deepcopy(self.qualification.record)
        variants = [
            {'model': 'attacker-model'}, {'schema': 'other'}, {'state': 'running'},
            {'qualification_id': 'bad'}, {'created_at': 'yesterday'},
            {'completed_at': '2026-10-23T01:00:00Z'}, {'agent_sources': {'x': 'not-a-hash'}},
            {'reserved_usd': float('nan')}, {'request_reservations': True},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                self.qualification.record = {**deepcopy(original), **changes}
                with self.assertRaises(WorkspaceError):
                    self.preview()
        for field, value in (('case_id', 'arbitrary-private-case'), ('state', 'made-up'),
                             ('elapsed_seconds', float('inf')), ('reserved_usd', -.1),
                             ('live_model_calls', True), ('request_reservations', 10001),
                             ('score', {'workflow_gate_pass': 'yes'})):
            self.qualification.record = deepcopy(original)
            self.qualification.record['report']['rows'][0][field] = value
            with self.subTest(field=field), self.assertRaises(WorkspaceError):
                self.preview()
        self.qualification.record = deepcopy(original)
        self.qualification.record['report']['rows'][1] = deepcopy(self.qualification.record['report']['rows'][0])
        with self.assertRaises(WorkspaceError):
            self.preview()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.service.status()['attempts'], 0)

    def test_bad_connection_and_unreviewed_or_stale_preview_do_not_reserve(self):
        for fields in ({'api_key': ''}, {'api_key': 'bad key value'}, {'api_key': self.key, 'region': 'https://other.test'},
                       {'api_key': self.key, 'region': []}, {'api_key': self.key, 'workspace_id': 'wrong'}):
            with self.subTest(fields=fields), self.assertRaises(WorkspaceError):
                self.service.connect(**fields)
        value = self.preview()
        with self.assertRaises(WorkspaceError):
            self.export()
        self.connect()
        for digest in ('0' * 64, None, ''):
            with self.assertRaises(WorkspaceError):
                self.service.export(value['qualification_id'], digest)
        self.connect(region='eu')
        with self.assertRaises(ConflictError):
            self.service.export(value['qualification_id'], value['preview_digest'])
        with self.assertRaises(WorkspaceError):
            self.export(allow_upload=False)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.service.status()['attempts'], 0)

    def test_http_rejection_and_ambiguous_failure_are_retained_without_retry(self):
        self.connect()
        for response, expected in (({'status': 401}, 'failed'), ({'status': 302}, 'failed'),
                                   ({'status': 500}, 'unknown'), ({'status': None}, 'unknown'),
                                   ({'status': True}, 'unknown')):
            self.qualification.record = qualification_record()
            self.response = response
            receipt = self.export()
            self.assertEqual(receipt['state'], expected)
            with self.assertRaises(ConflictError):
                self.export()
        before = len(self.calls)
        self.qualification.record = qualification_record()
        def broken(*args):
            raise RuntimeError('PRIVATE ' + self.key)
        self.service._transport = broken
        receipt = self.export()
        self.assertEqual(receipt['state'], 'unknown')
        self.assertNotIn(self.key, _encode(receipt))
        self.assertNotIn('PRIVATE', _encode(receipt))
        self.assertEqual(len(self.calls), before)
        self.assertEqual(self.service.status()['attempts'], 6)
        fresh = observation.WorkspaceObservability(self.ai, self.qualification, transport=self.transport)
        fresh.connect(self.key)
        preview = fresh.preview(self.qualification.record['qualification_id'])
        with self.assertRaises(ConflictError):
            fresh.export(preview['qualification_id'], preview['preview_digest'])

    def test_reservation_is_committed_before_transport_and_restart_is_interrupted(self):
        self.connect()
        def restart(endpoint, headers, body):
            with self.store._connect() as db:
                row = db.execute('SELECT snapshot FROM project_observability_versions WHERE version=1').fetchone()
                pending = json.loads(row['snapshot'])
                self.assertEqual(pending['state'], 'pending')
                self.assertNotIn(self.key, row['snapshot'])
            fresh = observation.WorkspaceObservability(self.ai, self.qualification, transport=self.transport)
            self.assertFalse(fresh.status()['key_present'])
            self.assertEqual(fresh.list()['exports'][0]['state'], 'interrupted')
            return {'status': 201}
        self.service._transport = restart
        result = self.export()
        self.assertEqual(result['state'], 'interrupted')
        self.assertEqual(result['error_code'], 'server_restarted')
        self.assertEqual(self.service.status()['attempts'], 1)

    def test_concurrent_send_has_single_retained_attempt_and_connection_is_frozen(self):
        started, finish = threading.Event(), threading.Event()
        self.connect()
        def blocked(*args):
            started.set()
            self.assertTrue(finish.wait(5))
            return {'status': 201}
        self.service._transport = blocked
        results = []
        thread = threading.Thread(target=lambda: results.append(self.export()))
        thread.start()
        try:
            self.assertTrue(started.wait(5))
            self.assertEqual(self.service.status()['active_requests'], 1)
            with self.assertRaises(ConflictError):
                self.export()
            with self.assertRaises(ConflictError):
                self.connect(region='eu')
        finally:
            finish.set()
            thread.join(6)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]['state'], 'accepted_by_api')
        self.assertEqual(self.service.status()['attempts'], 1)

    def test_lifetime_limit_tampering_and_disconnect_preserve_history(self):
        self.connect()
        with patch.object(observation, 'MAX_EXPORTS', 2):
            self.export()
            self.qualification.record = qualification_record()
            self.export()
            self.qualification.record = qualification_record()
            with self.assertRaises(WorkspaceError):
                self.export()
            self.assertFalse(self.service.status()['can_export'])
        history = self.service.list()
        self.service.disconnect()
        self.assertEqual(self.service.list(), history)
        with self.store._connect(write=True) as db:
            db.execute("UPDATE project_observability_versions SET digest=? WHERE version=2", ('0' * 64,))
        with self.assertRaises(WorkspaceError):
            self.service.list()

    def test_transport_uses_fixed_request_one_post_no_proxy_no_redirect_and_bounded_read(self):
        class Response:
            status = 201
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit):
                self.limit = limit
                return b'ok'
        response = Response()
        opener = SimpleNamespace(open=lambda request, timeout: response)
        with patch.object(observation, 'build_opener', return_value=opener) as build:
            result = observation._transport(observation.ENDPOINTS['us'], {'x-api-key': self.key}, {'safe': True})
        self.assertEqual(result['status'], 201)
        self.assertEqual(response.limit, observation.MAX_RESPONSE_BYTES + 1)
        handlers = build.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], observation._NoRedirect)
        self.assertIsNone(handlers[1].redirect_request(None, None, None, None, None, None))
        for exception in (URLError(self.key), HTTPError(observation.ENDPOINTS['us'], 403, self.key, {}, BytesIO())):
            opener = SimpleNamespace(open=lambda *args, **kwargs: (_ for _ in ()).throw(exception))
            with patch.object(observation, 'build_opener', return_value=opener):
                value = observation._transport(observation.ENDPOINTS['us'], {'x-api-key': self.key}, {})
            self.assertNotIn(self.key, _encode(value))


if __name__ == '__main__':
    unittest.main()
