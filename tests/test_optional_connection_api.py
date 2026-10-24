"""Local HTTP + isolated synthetic optional keys; no external service access."""
from copy import deepcopy
from hashlib import sha256
from http.client import HTTPConnection
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from sixd.credential_store import WindowsDPAPI
from sixd.project_examples import example_projects
from sixd.workspace_server import create_server
from test_workspace_ai_api import write_offline_config

BACKUP_SPEC = importlib.util.spec_from_file_location('sixd_optional_backup', ROOT / 'tools' / 'backup_local.py')
backup = importlib.util.module_from_spec(BACKUP_SPEC)
BACKUP_SPEC.loader.exec_module(backup)

TAVILY_KEY = 'tvly-synthetic-remember-http-no-service-access'
LANGSMITH_KEY = 'lsv2-synthetic-remember-http-no-service-access'
NEBIUS_KEY = 'synthetic-prior-nebius-format-no-service-access'
WORKSPACE_ID = '0c678cf0-6414-4356-bb55-188cf9725820'
KEYS = (TAVILY_KEY, LANGSMITH_KEY, NEBIUS_KEY)


class OptionalConnectionAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.private = self.folder / 'private settings'
        self.private.mkdir()
        self.database = self.folder / 'workspace' / 'workspace.sqlite3'
        self.database.parent.mkdir()
        write_offline_config(self.private)
        self.config_bytes = (self.private / 'token-factory.json').read_bytes()
        self.environment = patch.dict(os.environ, {'NEBIUS_API_KEY': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.calls = []
        self.open_server()
        self.addCleanup(self.close_server)
        self.project = deepcopy(example_projects()['baseline'])
        self.identity = self.project['project_id']
        self.server.store.create_project(self.project)

    def open_server(self):
        def no_provider(*args):
            self.calls.append('unexpected-ai-provider')
            raise AssertionError('Connection controls must not request AI.')

        def research_transport(key, body):
            self.calls.append(('explicit-offline-search', deepcopy(body)))
            return {'request_id': 'synthetic-http-request', 'usage': {'credits': 1},
                    'results': []}

        def no_upload(*args):
            self.calls.append('unexpected-upload')
            raise AssertionError('Connection controls must not upload.')

        self.server = create_server(port=0, db_path=self.database,
            ai_local_directory=self.private, provider_factory=no_provider,
            research_transport=research_transport, observability_transport=no_upload)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def close_server(self):
        server = getattr(self, 'server', None)
        if server is not None:
            self.server = None
            server.shutdown()
            server.server_close()
            self.worker.join(timeout=5)
            self.assertFalse(self.worker.is_alive())

    def restart(self):
        before_calls = deepcopy(self.calls)
        self.close_server()
        self.open_server()
        self.assertEqual(self.calls, before_calls)
        self.assertEqual((self.private / 'token-factory.json').read_bytes(), self.config_bytes)

    def request(self, path, body=None, *, origin=None):
        port = self.server.server_port
        headers = {'Content-Type': 'application/json',
                   'Origin': origin or f'http://127.0.0.1:{port}'}
        connection = HTTPConnection('127.0.0.1', port, timeout=10)
        connection.request('GET' if body is None else 'POST', path,
                           None if body is None else json.dumps(body), headers)
        response = connection.getresponse()
        code, raw = response.status, response.read()
        connection.close()
        for key in KEYS:
            self.assertNotIn(key.encode(), raw)
        self.assertNotIn(b'key_digest', raw)
        return code, json.loads(raw)

    def status(self, service):
        path = '/api/research/status' if service == 'research' else '/api/ai-quality/status'
        code, value = self.request(path)
        self.assertEqual(code, 200, value)
        return value if service == 'research' else value['observability']

    def connect(self, service, *, remember=None, **overrides):
        body = ({'api_key': TAVILY_KEY, 'credit_limit': 5} if service == 'research' else
                {'api_key': LANGSMITH_KEY, 'region': 'eu', 'workspace_id': WORKSPACE_ID})
        if remember is not None:
            body['remember'] = remember
        body.update(overrides)
        return self.request(f'/api/{service}/connect', body)

    def ciphertexts(self):
        return {path.name: path.read_bytes() for path in (self.private / 'credentials').glob('*')}

    def assert_private_files(self):
        for path in self.folder.rglob('*'):
            if path.is_file():
                raw = path.read_bytes()
                for key in KEYS:
                    self.assertNotIn(key.encode(), raw, str(path))
        self.assertFalse((self.database.parent / 'credentials').exists())
        self.assertEqual((self.private / 'token-factory.json').read_bytes(), self.config_bytes)

    def test_legacy_connects_are_ephemeral_and_never_send(self):
        for service in ('research', 'observability'):
            code, value = self.connect(service)
            self.assertEqual(code, 200, value)
            self.assertTrue(value['key_present'])
            self.assertFalse(value['key_remembered'])
            self.assertEqual(value['key_source'], 'session')
            self.assertEqual(value['key_storage'], 'server_memory_only')
        self.assertEqual(self.ciphertexts(), {})
        self.restart()
        for service in ('research', 'observability'):
            self.assertFalse(self.status(service)['key_present'])
        self.assertEqual(self.calls, [])
        self.assert_private_files()

    @unittest.skipUnless(os.name == 'nt', 'Windows current-user DPAPI behavior')
    def test_native_remember_restart_retains_metadata_and_search_reservations(self):
        for service in ('research', 'observability'):
            code, value = self.connect(service, remember=True)
            self.assertEqual(code, 200, value)
            self.assertTrue(value['key_remembered'])
            self.assertEqual(value['key_storage'], 'windows_current_user_dpapi')
        self.assertEqual(self.calls, [])
        before = self.ciphertexts()
        self.assertEqual(len(before), 2)
        digest = self.server.sources.summary(self.identity, 1)['digest']
        receipt = self.server.research.search(self.identity, 1, 'requirement:thermal_limit',
            'constructed offline reservation preservation query', digest)
        self.assertEqual(receipt['state'], 'completed')
        self.assertEqual(len(self.calls), 1)
        self.restart()
        research = self.status('research')
        self.assertTrue(research['key_present'])
        self.assertEqual(research['key_source'], 'remembered')
        self.assertEqual(research['credit_limit'], 5)
        self.assertEqual(research['reserved_credits'], 1)
        self.assertEqual(research['remaining_credits'], 4)
        observation = self.status('observability')
        self.assertEqual(observation['region'], 'eu')
        self.assertEqual(observation['workspace_id'], WORKSPACE_ID)
        self.assertTrue(observation['endpoint'].startswith('https://eu.'))
        self.assertEqual(self.ciphertexts(), before)
        self.assertEqual(len(self.calls), 1)
        self.assert_private_files()

    @unittest.skipUnless(os.name == 'nt', 'Windows current-user DPAPI behavior')
    def test_forget_and_disconnect_are_isolated_and_cannot_resurrect(self):
        for service in ('research', 'observability'):
            self.assertEqual(self.connect(service, remember=True)[0], 200)
        code, forgotten = self.request('/api/research/forget', {})
        self.assertEqual(code, 200, forgotten)
        self.assertTrue(forgotten['key_present'])
        self.assertFalse(forgotten['key_remembered'])
        self.assertTrue(self.status('observability')['key_remembered'])
        self.restart()
        self.assertFalse(self.status('research')['key_present'])
        self.assertTrue(self.status('observability')['key_present'])
        code, disconnected = self.request('/api/observability/disconnect', {})
        self.assertEqual(code, 200, disconnected)
        self.assertFalse(disconnected['key_present'])
        self.assertFalse(disconnected['key_remembered'])
        self.restart()
        self.assertFalse(self.status('observability')['key_present'])
        self.assertEqual(self.calls, [])

    @unittest.skipUnless(os.name == 'nt', 'Windows current-user DPAPI behavior')
    def test_explicit_optout_removes_each_services_old_saved_copy(self):
        for service in ('research', 'observability'):
            self.assertEqual(self.connect(service, remember=True)[0], 200)
            code, session = self.connect(service, remember=False)
            self.assertEqual(code, 200, session)
            self.assertTrue(session['key_present'])
            self.assertFalse(session['key_remembered'])
        self.assertEqual(self.ciphertexts(), {})
        self.restart()
        for service in ('research', 'observability'):
            self.assertFalse(self.status(service)['key_present'])
        self.assertEqual(self.calls, [])

    def test_unsupported_remember_is_explicit_and_preserves_session(self):
        for service in ('research', 'observability'):
            self.assertEqual(self.connect(service)[0], 200)
        self.close_server()
        with patch.object(WindowsDPAPI, 'supported', False):
            self.open_server()
            for service in ('research', 'observability'):
                self.assertEqual(self.connect(service)[0], 200)
                self.assertFalse(self.status(service)['remember_supported'])
                code, value = self.connect(service, remember=True, api_key='synthetic-new-session-key')
                self.assertEqual(code, 400, value)
                status = self.status(service)
                self.assertTrue(status['key_present'])
                self.assertFalse(status['key_remembered'])
                self.assertEqual(status['key_source'], 'session')
        self.assertEqual(self.ciphertexts(), {})
        self.assertEqual(self.calls, [])

    def test_strict_body_and_foreign_origin_checks_cover_every_control(self):
        for service in ('research', 'observability'):
            for remember in ('yes', 1, [], {}):
                self.assertEqual(self.connect(service, remember=remember)[0], 400)
            body = ({'api_key': TAVILY_KEY, 'credit_limit': 5} if service == 'research' else
                    {'api_key': LANGSMITH_KEY, 'region': 'eu', 'workspace_id': WORKSPACE_ID})
            self.assertEqual(self.request(f'/api/{service}/connect', {**body, 'remember': None})[0], 400)
            self.assertEqual(self.connect(service, extra=True)[0], 400)
            for action in ('forget', 'disconnect'):
                path = f'/api/{service}/{action}'
                self.assertEqual(self.request(path, {'unexpected': True})[0], 400)
                self.assertEqual(self.request(path, {}, origin='https://example.invalid')[0], 403)
            self.assertEqual(self.request(f'/api/{service}/connect', {}, origin='https://example.invalid')[0], 403)
            self.assertFalse(self.status(service)['key_present'])
        self.assertEqual(self.calls, [])

    def test_active_requests_refuse_connection_mutations(self):
        for service in ('research', 'observability'):
            self.assertEqual(self.connect(service)[0], 200)
            backend = getattr(self.server, service)
            backend._active = 1
            try:
                self.assertEqual(self.connect(service, api_key='synthetic-replacement-key')[0], 409)
                for action in ('forget', 'disconnect'):
                    self.assertEqual(self.request(f'/api/{service}/{action}', {})[0], 409)
                self.assertTrue(self.status(service)['key_present'])
            finally:
                backend._active = 0
        self.assertEqual(self.calls, [])

    @unittest.skipUnless(os.name == 'nt', 'Windows current-user DPAPI behavior')
    def test_previous_nebius_blob_still_restores_with_optional_services(self):
        self.close_server()
        path = self.private / 'credentials' / 'nebius.dpapi'
        # Freeze the pre-E serialized contract independently of CredentialStore.save.
        # New defaults, schema or magic must not cause a previous blob to be lost.
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {'schema': 'sixd.remembered-nebius-key.v1', 'key': NEBIUS_KEY,
                    'key_digest': sha256(NEBIUS_KEY.encode()).hexdigest()}
        protected = WindowsDPAPI._transform(json.dumps(envelope, separators=(',', ':')).encode(),
            decrypt=False, entropy_bytes=b'6D current-user local Nebius credential v1')
        path.write_bytes(b'6D-DPAPI-KEY-v1\n' + protected)
        original = path.read_bytes()
        self.open_server()
        code, nebius = self.request('/api/ai/status')
        self.assertEqual(code, 200, nebius)
        self.assertTrue(nebius['key_present'])
        self.assertEqual(nebius['key_source'], 'remembered')
        for service in ('research', 'observability'):
            self.assertEqual(self.connect(service, remember=True)[0], 200)
        self.restart()
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue(self.request('/api/ai/status')[1]['key_present'])
        self.assertEqual(self.calls, [])
        self.assert_private_files()

    @unittest.skipUnless(os.name == 'nt', 'Windows current-user DPAPI behavior')
    def test_swapped_or_corrupt_saved_services_never_restore_a_key(self):
        for service in ('research', 'observability'):
            self.assertEqual(self.connect(service, remember=True)[0], 200)
        self.close_server()
        tavily = self.private / 'credentials' / 'tavily.dpapi'
        langsmith = self.private / 'credentials' / 'langsmith.dpapi'
        original_tavily, original_langsmith = tavily.read_bytes(), langsmith.read_bytes()
        tavily.write_bytes(original_langsmith)
        langsmith.write_bytes(original_tavily)
        self.open_server()
        for service in ('research', 'observability'):
            status = self.status(service)
            self.assertFalse(status['key_present'])
            self.assertTrue(status['key_remembered'])
            self.assertTrue(status['credential_error'])
        self.close_server()
        tavily.write_bytes(b'invalid remembered blob')
        langsmith.write_bytes(original_langsmith[:-9] + b'corrupted')
        self.open_server()
        for service in ('research', 'observability'):
            self.assertFalse(self.status(service)['key_present'])
            self.assertTrue(self.status(service)['credential_error'])
            self.assertEqual(self.request(f'/api/{service}/forget', {})[0], 200)
        self.assertEqual(self.ciphertexts(), {})
        self.assertEqual(self.calls, [])

    @unittest.skipUnless(os.name == 'nt', 'Windows current-user DPAPI behavior')
    def test_failed_remember_preserves_saved_connection_without_session_fallback(self):
        for service in ('research', 'observability'):
            self.assertEqual(self.connect(service, remember=True)[0], 200)
        original = self.ciphertexts()
        with patch('sixd.service_credentials.os.replace', side_effect=PermissionError(TAVILY_KEY)):
            for service in ('research', 'observability'):
                code, value = self.connect(service, remember=True, api_key='synthetic-replacement-key')
                self.assertEqual(code, 400, value)
                status = self.status(service)
                self.assertTrue(status['key_present'])
                self.assertTrue(status['key_remembered'])
                self.assertEqual(status['key_source'], 'remembered')
                self.assertTrue(status['credential_error'])
        self.assertEqual(self.ciphertexts(), original)
        self.restart()
        self.assertTrue(self.status('research')['key_present'])
        self.assertTrue(self.status('observability')['key_present'])
        self.assertEqual(self.calls, [])
        self.assert_private_files()

    @unittest.skipUnless(os.name == 'nt', 'Windows current-user DPAPI behavior')
    def test_stopped_backup_excludes_both_optional_service_blobs(self):
        for service in ('research', 'observability'):
            self.assertEqual(self.connect(service, remember=True)[0], 200)
        encrypted = self.ciphertexts()
        self.close_server()
        # Exercise the normal co-located backup shape using only isolated files.
        credentials = self.database.parent / 'credentials'
        credentials.mkdir()
        for name, raw in encrypted.items():
            (credentials / name).write_bytes(raw)
        before_database = self.database.read_bytes()
        archive_path = self.folder / 'stopped-backup.zip'
        with patch.object(backup, '_server_running', return_value=False):
            created = backup.create_backup(self.database.parent, archive_path, confirmed_stopped=True)
            restored = backup.restore_backup(archive_path, self.folder / 'restored', confirmed_stopped=True)
        self.assertFalse(created['credentials_included'])
        self.assertFalse(restored['credentials_restored'])
        self.assertEqual(created['provider_calls'], 0)
        with zipfile.ZipFile(archive_path) as archive:
            self.assertEqual(set(archive.namelist()), {'workspace.sqlite3', 'manifest.json'})
            contents = b''.join(archive.read(name) for name in archive.namelist())
            for raw in encrypted.values():
                self.assertNotIn(raw, contents)
        self.assertFalse((self.folder / 'restored' / 'credentials').exists())
        self.assertEqual(self.database.read_bytes(), before_database)
        self.assertEqual(self.ciphertexts(), encrypted)
        self.assertEqual({path.name: path.read_bytes() for path in credentials.iterdir()}, encrypted)
        self.assertEqual((self.private / 'token-factory.json').read_bytes(), self.config_bytes)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
