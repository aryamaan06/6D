"""Offline native HTTP checks for invitation hosting and visitor boundaries."""
from contextlib import closing
from dataclasses import replace
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import sqlite3
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.hosted_server import HostedConfig, HostedManager, HostedLimitError, create_hosted_server

CODE = 'synthetic-hosted-invitation-code-for-tests-only'
ORIGIN = 'https://judge.example.test'


class HostedConfigTests(unittest.TestCase):
    def test_https_exact_origin_and_bounded_secrets_and_limits(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as folder:
            for origin in ['http://judge.example.test', 'https://judge.example.test/',
                    'https://user:pass@judge.example.test', 'https://judge.example.test?q=x',
                    'https://judge.example.test:bad']:
                with self.subTest(origin=origin), self.assertRaises(ValueError):
                    HostedConfig(Path(folder), origin, CODE)
            for changes in [{'access_code': 'short'}, {'max_sessions': True}, {'post_limit': 0},
                    {'session_ttl_seconds': 999999}, {'max_state_bytes': 1}]:
                with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                    HostedConfig(Path(folder), ORIGIN, CODE).__class__(**{
                        **{'state_root': Path(folder), 'public_origin': ORIGIN, 'access_code': CODE}, **changes})
            config = HostedConfig(Path(folder), 'http://127.0.0.1:8770', CODE, allow_loopback_http=True)
            self.assertNotIn(CODE, repr(config))
            with self.assertRaises(ValueError):
                create_hosted_server(config, host='0.0.0.0', port=0)

    def test_founder_and_source_state_locations_are_rejected(self):
        for folder in [ROOT, ROOT / '.local', ROOT / '.local' / 'hosted', ROOT / 'src' / 'hosted',
                ROOT / 'tests' / 'hosted', ROOT / 'design' / 'hosted', ROOT / '.git' / 'hosted']:
            with self.subTest(path=folder), self.assertRaises(ValueError):
                HostedConfig(folder, ORIGIN, CODE)


class HostedHTTPTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.folder = Path(self.temp.name)
        self.now = [1700000000.0]
        self.config = HostedConfig(self.folder, ORIGIN, CODE, max_sessions=4,
            session_ttl_seconds=60, get_limit=500, post_limit=100, login_limit=100)
        self.environment = patch.dict(os.environ, {'NEBIUS_API_KEY': 'synthetic-environment-key-must-not-restore'})
        self.environment.start()
        self.start()

    def start(self):
        self.server = create_hosted_server(self.config, port=0, clock=lambda: self.now[0])
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.worker.join(timeout=5)

    def tearDown(self):
        self.stop(); self.environment.stop(); self.temp.cleanup()

    def request(self, path, body=None, *, cookie=None, origin=ORIGIN, host='judge.example.test', raw=None):
        method = 'POST' if body is not None or raw is not None else 'GET'
        headers = {'Host': host}
        if method == 'POST':
            headers['Content-Type'] = 'application/json'
            if origin is not None:
                headers['Origin'] = origin
        if cookie:
            headers['Cookie'] = cookie
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=20)
        encoded = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        try:
            conn.request(method, path, body=encoded, headers=headers)
            response = conn.getresponse(); data = response.read(); result_headers = dict(response.getheaders())
            value = json.loads(data) if result_headers.get('Content-Type', '').startswith('application/json') else data
            self.assertNotIn(CODE.encode(), data)
            self.assertNotIn(b'synthetic-environment-key-must-not-restore', data)
            return response.status, value, result_headers
        finally:
            conn.close()

    def login(self):
        code, value, headers = self.request('/api/hosted/login', {'access_code': CODE})
        self.assertEqual(code, 200, value)
        self.assertEqual(value, {'hosted': True, 'authenticated': True})
        return headers['Set-Cookie'].split(';', 1)[0]

    def test_unauthenticated_api_and_shell_do_not_reveal_workspace(self):
        code, value, _ = self.request('/api/projects')
        self.assertEqual(code, 401)
        self.assertNotIn('projects', value)
        code, value, _ = self.request('/api/hosted/status')
        self.assertEqual(code, 200); self.assertFalse(value['authenticated']); self.assertTrue(value['hosted'])
        code, value, _ = self.request('/health')
        self.assertEqual(code, 200); self.assertNotIn('workspace', value)
        with closing(sqlite3.connect(self.server.manager.db_path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 0)

    def test_login_seeds_only_one_calculated_rocket_and_cookie_is_private(self):
        cookie = self.login()
        self.assertTrue(cookie.startswith('__Host-sixd_session='))
        code, view, headers = self.request('/api/workspace', cookie=cookie)
        self.assertEqual(code, 200); self.assertIsNotNone(view['run'])
        self.assertTrue(view['project_id'].startswith('judge-'))
        self.assertEqual(len(view['project']['models']), 6)  # five calculations plus explicit GNC gap
        self.assertEqual(headers['Cache-Control'], 'no-store')
        code, projects, _ = self.request('/api/projects', cookie=cookie)
        self.assertEqual(len(projects['projects']), 1)
        code, status, _ = self.request('/api/hosted/status', cookie=cookie)
        self.assertFalse(status['live_ai_enabled']); self.assertIn('expires_at', status)
        self.assertEqual(self.request('/api/ai/status', cookie=cookie)[1]['key_present'], False)
        row = next(iter(self.server.manager._runtimes.values()))
        self.assertEqual(row.ai._key, None)

    def test_https_cookie_flags_and_no_raw_token_in_session_database(self):
        code, value, headers = self.request('/api/hosted/login', {'access_code': CODE})
        cookie = headers['Set-Cookie']
        for flag in ['; Secure', '; HttpOnly', '; SameSite=Strict', '; Path=/', '; Max-Age=60']:
            self.assertIn(flag, cookie)
        token = cookie.split(';')[0].split('=', 1)[1]
        with closing(sqlite3.connect(self.server.manager.db_path)) as db:
            rows = db.execute('SELECT * FROM sessions').fetchall()
        self.assertNotIn(token, repr(rows)); self.assertNotIn(CODE, repr(rows))

    def test_two_visitors_cannot_read_or_change_each_others_projects(self):
        a, b = self.login(), self.login()
        view_a = self.request('/api/workspace', cookie=a)[1]
        view_b = self.request('/api/workspace', cookie=b)[1]
        self.assertNotEqual(view_a['project_id'], view_b['project_id'])
        code, _, _ = self.request('/api/workspace?project_id=' + view_a['project_id'], cookie=b)
        self.assertEqual(code, 400)
        code, _, _ = self.request('/api/run', {'project_id': view_a['project_id'], 'revision': 1}, cookie=b)
        self.assertEqual(code, 400)
        self.assertEqual(self.request('/api/workspace', cookie=a)[1]['run'], view_a['run'])

    def test_allowed_revision_run_is_isolated_and_persists_after_restart(self):
        cookie = self.login(); before = self.request('/api/workspace', cookie=cookie)[1]
        project = before['project']; project['inputs']['thrust']['value'] = 11000
        code, revised, _ = self.request('/api/revisions',
            {'project_id': before['project_id'], 'base_revision': 1, 'project': project}, cookie=cookie)
        self.assertEqual(code, 200, revised)
        code, run, _ = self.request('/api/run', {'project_id': before['project_id'], 'revision': 2}, cookie=cookie)
        self.assertEqual(code, 200, run)
        with closing(sqlite3.connect(self.server.manager.db_path)) as db:
            session_rows = db.execute('SELECT * FROM sessions').fetchall()
        self.stop(); self.start()
        code, reopened, _ = self.request('/api/workspace', cookie=cookie)
        self.assertEqual(code, 200); self.assertEqual(reopened['revision'], 2)
        self.assertEqual(reopened['run'], run['run'])
        with closing(sqlite3.connect(self.server.manager.db_path)) as db:
            self.assertEqual(db.execute('SELECT * FROM sessions').fetchall(), session_rows)
        self.assertEqual(len(self.request('/api/projects', cookie=cookie)[1]['projects']), 1)

    def test_admin_external_service_and_evaluation_posts_are_forbidden(self):
        cookie = self.login()
        forbidden = ['/api/shutdown', '/api/ai/connect', '/api/ai/disconnect', '/api/ai/forget',
            '/api/research/connect', '/api/research/forget', '/api/research/disconnect', '/api/research/search',
            '/api/observability/connect', '/api/observability/export', '/api/observability/forget',
            '/api/model-evaluation/start', '/api/workflow-evaluation/start', '/api/ai-quality/start',
            '/api/evidence-evaluation/prepare', '/api/ultra-diagnostic/start', '/unknown']
        for route in forbidden:
            with self.subTest(route=route):
                self.assertEqual(self.request(route, {}, cookie=cookie)[0], 403)
        self.assertEqual(self.request('/api/investigations', {}, cookie=cookie)[0], 403)

    def test_origin_host_and_duplicate_headers_cannot_bypass_gateway(self):
        cookie = self.login()
        for origin in [None, 'http://judge.example.test', 'https://evil.example']:
            with self.subTest(origin=origin):
                self.assertEqual(self.request('/api/run', {}, cookie=cookie, origin=origin)[0], 403)
        self.assertEqual(self.request('/api/projects', cookie=cookie, host='evil.example')[0], 403)
        self.assertEqual(self.request('https://evil.example/api/projects', cookie=cookie)[0], 403)
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            conn.putrequest('GET', '/api/projects', skip_host=True)
            conn.putheader('Host', 'judge.example.test');conn.putheader('Host', 'evil.example')
            conn.putheader('Cookie', cookie);conn.endheaders()
            response=conn.getresponse();self.assertEqual(response.status,403);response.read()
        finally:conn.close()

    def test_login_strict_json_and_forged_cookies(self):
        for body in [{'access_code': CODE, 'extra': 1}, {'access_code': 4}, {'access_code': ''}]:
            self.assertEqual(self.request('/api/hosted/login', body)[0], 400)
        self.assertEqual(self.request('/api/hosted/login', {'access_code': 'wrong-code'})[0], 401)
        self.assertEqual(self.request('/api/hosted/login', raw=b'{"access_code":"one","access_code":"two"}')[0], 400)
        self.assertEqual(self.request('/api/projects', cookie='__Host-sixd_session=' + 'a' * 64)[0], 401)
        self.assertEqual(self.request('/api/projects', cookie='__Host-sixd_session=../../.local')[0], 401)

    def test_logout_revokes_cookie_and_does_not_reset_allocation(self):
        cookie = self.login(); self.assertEqual(self.request('/api/hosted/logout', {}, cookie=cookie)[0], 200)
        self.assertEqual(self.request('/api/projects', cookie=cookie)[0], 401)
        self.stop(); self.start()
        self.assertEqual(self.request('/api/projects', cookie=cookie)[0], 401)
        with closing(sqlite3.connect(self.server.manager.db_path)) as db:
            self.assertEqual(db.execute('SELECT state FROM sessions').fetchone()[0], 'revoked')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 1)

    def test_logout_refuses_active_ai_and_repeated_login_reuses_session(self):
        cookie = self.login(); runtime = next(iter(self.server.manager._runtimes.values()))
        runtime.ai._active = 'synthetic-active-job'
        self.assertEqual(self.request('/api/hosted/logout', {}, cookie=cookie)[0], 409)
        self.assertEqual(self.request('/api/projects', cookie=cookie)[0], 200)
        runtime.ai._active = None
        self.assertEqual(self.request('/api/hosted/login', {'access_code': CODE}, cookie=cookie)[0], 200)
        with closing(sqlite3.connect(self.server.manager.db_path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 1)

    def test_expiry_and_maximum_sessions_survive_restart(self):
        self.stop(); self.config = replace(self.config, max_sessions=1); self.start()
        cookie = self.login(); self.now[0] += 61
        self.assertEqual(self.request('/api/projects', cookie=cookie)[0], 401)
        self.stop(); self.start()
        self.assertEqual(self.request('/api/hosted/login', {'access_code': CODE})[0], 429)

    def test_request_and_login_throttles_reject_without_allocating(self):
        cookie = self.login(); session = self.server.manager.session(cookie.split('=',1)[1])
        for _ in range(self.config.get_limit):self.server.manager.admit(session, 'GET')
        self.assertEqual(self.request('/api/projects', cookie=cookie)[0],429)
        self.now[0]+=60
        self.assertEqual(self.request('/api/projects', cookie=cookie)[0],401)  # fixed expiry, not sliding
        for _ in range(self.config.login_limit):
            self.server.manager._rate('global','login',self.config.login_limit)
        self.assertEqual(self.request('/api/hosted/login',{'access_code':CODE})[0],429)

    def test_storage_admission_blocks_writes_but_keeps_existing_records_readable(self):
        cookie = self.login(); runtime = next(iter(self.server.manager._runtimes.values()))
        path=runtime.store.db_path.parent/'synthetic-storage-bound.dat'
        with path.open('wb') as stream:stream.truncate(self.config.max_state_bytes)
        self.assertEqual(self.request('/api/run', {}, cookie=cookie)[0],429)
        self.assertEqual(self.request('/api/workspace',cookie=cookie)[0],200)
        self.assertEqual(self.request('/api/hosted/logout',{},cookie=cookie)[0],200)

    def test_waiting_mutation_rechecks_revocation_and_expiry_before_running(self):
        for end_session in ('revoke', 'expire'):
            with self.subTest(end_session=end_session):
                cookie = self.login()
                before = self.request('/api/workspace', cookie=cookie)[1]
                manager = self.server.manager
                session = manager.session(cookie.split('=', 1)[1])
                runtime = manager.runtime(session)
                original_runtime = manager.runtime
                arrived, result = threading.Event(), []

                def reached(value):
                    found = original_runtime(value)
                    arrived.set()
                    return found

                def mutate():
                    result.append(self.request('/api/run',
                        {'project_id': before['project_id'], 'revision': 1}, cookie=cookie)[0])

                with patch.object(manager, 'runtime', side_effect=reached):
                    with runtime._post_lock:
                        worker = threading.Thread(target=mutate)
                        worker.start()
                        self.assertTrue(arrived.wait(5))
                        if end_session == 'revoke':
                            manager.revoke(session)
                        else:
                            self.now[0] += 61
                    worker.join(10)
                self.assertFalse(worker.is_alive())
                self.assertEqual(result, [401])
                self.assertEqual(runtime.store.get(before['project_id'])['run'], before['run'])
                if end_session == 'revoke':
                    self.assertNotIn(session['id'], manager._runtimes)

    def test_unexpected_runtime_error_returns_controlled_json_without_details(self):
        cookie=self.login(); runtime=next(iter(self.server.manager._runtimes.values()))
        with patch.object(runtime.store,'list_projects',side_effect=RuntimeError('synthetic-private-internal-detail')):
            code,value,_=self.request('/api/projects',cookie=cookie)
        self.assertEqual(code,503);self.assertNotIn('synthetic-private-internal-detail',json.dumps(value))

    def test_connection_threads_are_bounded_even_before_authentication(self):
        self.stop();self.config=replace(self.config,max_connections=4);self.start()
        connections=[]
        try:
            for _ in range(4):
                connection=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=5)
                connection.sendall(b'GET / HTTP/1.1\r\n');connections.append(connection)
            deadline=time.monotonic()+3
            while self.server._connection_slots._value and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(self.server._connection_slots._value,0)
            with socket.create_connection(('127.0.0.1',self.server.server_port),timeout=5) as rejected:
                self.assertTrue(rejected.recv(4096).startswith(b'HTTP/1.0 503'))
        finally:
            for connection in connections:connection.close()


if __name__=='__main__':unittest.main()
