"""Invite-protected judge gateway with persistent isolated visitor workspaces.

This is a separate server, not a relaxation of the local server's bind policy.
TLS terminates at an explicitly configured reverse proxy. No forwarded header
is used for authentication, origin checks, client identity or security decisions.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from http.cookies import SimpleCookie, CookieError
from http.server import ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit

from .workspace_server import WorkspaceHandler, WEB, ROOT, FONT_ASSETS, build_status
from .workspace import ConflictError, WorkspaceError


POST_ROUTES = frozenset({
    '/api/projects', '/api/revisions', '/api/impact', '/api/run',
    '/api/simulations', '/api/authoring/preflight', '/api/scenarios',
    '/api/envelopes/preview', '/api/simulation-imports', '/api/simulation-imports/preview',
    '/api/test-data/preview', '/api/test-comparisons', '/api/test-evidence/impact',
    '/api/interfaces/preview', '/api/project-intake/inspect', '/api/project-intake/preview',
    '/api/sources', '/api/source-links', '/api/source-links/confirm',
    '/api/actions', '/api/actions/update', '/api/actions/review',
    '/api/design-comparison', '/api/coverage/save', '/api/investigations',
    '/api/research/search',
})
LOGIN_ASSETS = {'/hosted-login.html': 'text/html; charset=utf-8',
                '/hosted-login.js': 'text/javascript; charset=utf-8',
                '/hosted-login.css': 'text/css; charset=utf-8',
                '/typography.css': 'text/css; charset=utf-8', **FONT_ASSETS}
HOSTED_ASSETS = {'/hosted-mode.js': 'text/javascript; charset=utf-8',
                 '/hosted-mode.css': 'text/css; charset=utf-8'}


@dataclass(frozen=True)
class HostedConfig:
    state_root: Path
    public_origin: str
    access_code: str = field(repr=False)
    allow_loopback_http: bool = False
    open_access: bool = False
    max_sessions: int = 100
    session_ttl_seconds: int = 86400
    get_limit: int = 600
    post_limit: int = 60
    login_limit: int = 60
    max_connections: int = 32
    max_state_bytes: int = 200 * 1024 * 1024

    def __post_init__(self):
        if not isinstance(self.public_origin, str):
            raise ValueError('Configure one exact public origin.')
        origin = urlsplit(self.public_origin)
        loopback = origin.hostname in ('127.0.0.1', 'localhost', '::1')
        try:
            valid_port = origin.port is None or 1 <= origin.port <= 65535
        except ValueError:
            valid_port = False
        if (not origin.hostname or origin.username or origin.password or not valid_port
                or origin.path or origin.query or origin.fragment
                or self.public_origin != origin.scheme + '://' + origin.netloc
                or origin.scheme not in ('http', 'https')
                or (origin.scheme == 'http' and not (self.allow_loopback_http is True and loopback))):
            raise ValueError('Use an exact HTTPS origin, or explicit loopback HTTP for local tests.')
        if (not isinstance(self.access_code, str) or not 32 <= len(self.access_code) <= 256
                or any(not 33 <= ord(c) <= 126 for c in self.access_code)):
            raise ValueError('Configure a private invitation code of 32–256 printable characters.')
        if type(self.allow_loopback_http) is not bool or type(self.open_access) is not bool:
            raise ValueError('The test switches must be boolean.')
        for name, lower, upper in (('max_sessions', 1, 100), ('session_ttl_seconds', 60, 86400),
                ('get_limit', 10, 10000), ('post_limit', 1, 1000), ('login_limit', 1, 100),
                ('max_connections', 4, 128),
                ('max_state_bytes', 1024 * 1024, 1024 * 1024 * 1024)):
            if type(getattr(self, name)) is not int or not lower <= getattr(self, name) <= upper:
                raise ValueError('Hosted resource limits must be bounded integers.')
        state = Path(self.state_root).absolute()
        _unlinked(state)
        resolved = state.resolve()
        for forbidden in (ROOT / '.local', ROOT / 'src', ROOT / 'tests', ROOT / 'design', ROOT / '.git'):
            if resolved == forbidden.resolve() or forbidden.resolve() in resolved.parents:
                raise ValueError('Hosted state must be separate from source and the founder workspace.')
        if resolved == ROOT.resolve():
            raise ValueError('Use a dedicated hosted state directory.')
        object.__setattr__(self, 'state_root', resolved)


def _unlinked(path):
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if part.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Hosted state paths cannot contain linked/reparse components.')


class HostedLimitError(Exception):
    pass


class HostedSessionError(Exception):
    pass


class HostedManager:
    def __init__(self, config, runtime_factory=None, *, clock=None):
        self.config, self.runtime_factory = config, runtime_factory or self._default_runtime
        self.clock = clock or time.time
        self._lock = threading.RLock()
        self._runtimes, self._rates = {}, {}
        self._code_digest = sha256(config.access_code.encode('ascii')).digest()
        self.root = config.state_root
        self.root.mkdir(parents=True, exist_ok=True)
        _unlinked(self.root)
        self.db_path = self.root / 'sessions.sqlite3'
        _unlinked(self.db_path)
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, created REAL NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL)')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _default_runtime(folder, session_id):
        from .workspace_server import WorkspaceRuntime
        return WorkspaceRuntime(folder / 'workspace.sqlite3', ai_local_directory=folder / 'private',
                                allow_environment_key=False)

    def _rate(self, identity, category, limit):
        with self._lock:
            bucket = int(self.clock() // 60)
            key = identity, category
            previous, count = self._rates.get(key, (bucket, 0))
            count = count if previous == bucket else 0
            if count >= limit:
                raise HostedLimitError('The hosted request limit was reached. Try again in one minute.')
            self._rates[key] = bucket, count + 1

    def login(self, code):
        self._rate('global', 'login', self.config.login_limit)
        candidate = code.encode('utf-8') if isinstance(code, str) and len(code) <= 256 else b''
        if not hmac.compare_digest(sha256(candidate).digest(), self._code_digest):
            return None
        with self._lock, self._db() as db:
            # Expired/revoked sessions still count: login/logout cannot renew a
            # finite operator allocation, reset reservations or discard history.
            if db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] >= self.config.max_sessions:
                raise HostedLimitError('The hosted visitor allocation is full. Ask the owner for access.')
            identity, token, now = secrets.token_hex(16), secrets.token_hex(32), self.clock()
            db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',
                (identity, sha256(token.encode('ascii')).hexdigest(), now, now + self.config.session_ttl_seconds, 'provisioning'))
        try:
            self._runtime(identity, seed=True)
        except Exception:
            with self._db() as db:
                db.execute("UPDATE sessions SET state='failed' WHERE id=?", (identity,))
            raise
        with self._db() as db:
            db.execute("UPDATE sessions SET state='active' WHERE id=?", (identity,))
        return token

    def ensure_open_session(self):
        now = self.clock()
        token_file = self.root / 'open_token.txt'
        token = getattr(self, '_public_token', None)
        if not token and token_file.is_file():
            try:
                candidate = token_file.read_text(encoding='ascii').strip()
                if len(candidate) == 64:
                    token = candidate
                    self._public_token = candidate
            except OSError:
                pass
        if token:
            with self._lock, self._db() as db:
                h = sha256(token.encode('ascii')).hexdigest()
                row = db.execute("SELECT id FROM sessions WHERE token_hash=? AND state='active' AND expires>?", (h, now)).fetchone()
                if row is not None:
                    return token
        # Provision a persistent open demo session
        with self._lock, self._db() as db:
            identity, token, now = secrets.token_hex(16), secrets.token_hex(32), self.clock()
            db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',
                (identity, sha256(token.encode('ascii')).hexdigest(), now, now + self.config.session_ttl_seconds, 'provisioning'))
        try:
            self._runtime(identity, seed=True)
        except Exception:
            with self._db() as db:
                db.execute("UPDATE sessions SET state='failed' WHERE id=?", (identity,))
            raise
        with self._db() as db:
            db.execute("UPDATE sessions SET state='active' WHERE id=?", (identity,))
        self._public_token = token
        try:
            token_file.write_text(token, encoding='ascii')
        except OSError:
            pass
        return token

    def session(self, token):
        if not isinstance(token, str) or len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
            return None
        with self._db() as db:
            row = db.execute("SELECT * FROM sessions WHERE token_hash=? AND state='active' AND expires>?",
                (sha256(token.encode('ascii')).hexdigest(), self.clock())).fetchone()
        return dict(row) if row is not None else None

    def _runtime(self, identity, *, seed=False):
        with self._lock:
            if identity in self._runtimes:
                return self._runtimes[identity]
            folder = self.root / 'visitors' / identity
            _unlinked(folder)
            folder.mkdir(parents=True, exist_ok=True)
            runtime = self.runtime_factory(folder, identity)
            seed_id = 'judge-' + identity
            if seed:
                from .project_examples import integrated_rocket_review
                project = integrated_rocket_review()
                project['project_id'] = seed_id
                view = runtime.store.create_project(project)
                runtime.store.run(view['project_id'], view['revision'])
            # The inherited local route otherwise creates its old default
            # example as a GET side effect. Hosted opening selects only this
            # visitor's already calculated reference and never reruns it.
            runtime.store.ensure_default = lambda: seed_id
            self._runtimes[identity] = runtime
            return runtime

    def runtime(self, session):
        with self._lock:
            if not self.active(session):
                raise HostedSessionError()
            return self._runtime(session['id'])

    def active(self, session):
        with self._db() as db:
            return db.execute("SELECT 1 FROM sessions WHERE id=? AND state='active' AND expires>?",
                (session['id'], self.clock())).fetchone() is not None

    def revoke(self, session):
        runtime = self.runtime(session)
        with runtime._post_lock, self._lock, runtime.ai._lock:
            if not self.active(session):
                raise HostedSessionError()
            if runtime.ai._active:
                raise ConflictError('Wait for the active investigation before signing out.')
            with self._db() as db:
                db.execute("UPDATE sessions SET state='revoked' WHERE id=?", (session['id'],))
            self._runtimes.pop(session['id'], None)

    def admit(self, session, method):
        self._rate(session['id'], method, self.config.post_limit if method == 'POST' else self.config.get_limit)
        if method == 'POST':
            folder = self.root / 'visitors' / session['id']
            size = 0
            for path in folder.rglob('*'):
                _unlinked(path)
                if path.is_file():
                    size += path.stat().st_size
            if size >= self.config.max_state_bytes:
                raise HostedLimitError('This visitor workspace reached its storage admission limit. Existing records remain readable.')


class _Facade:
    def __init__(self, runtime, server):
        self.runtime, self.server = runtime, server

    def __getattr__(self, name):
        return getattr(self.runtime, name) if hasattr(self.runtime, name) else getattr(self.server, name)


class HostedHandler(WorkspaceHandler):
    server_version = '6DHosted/1'

    def setup(self):
        self._hosted = self.server
        super().setup()
        self.connection.settimeout(15)

    def _reply(self, status, body, content_type='application/json; charset=utf-8', *, filename=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=True, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        if self._hosted.config.public_origin.startswith('https://'):
            self.send_header('Strict-Transport-Security', 'max-age=31536000')
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
        cookie = getattr(self, '_set_cookie', None)
        if cookie is not None:
            self.send_header('Set-Cookie', cookie)
            self._set_cookie = None
        self.end_headers()
        self.wfile.write(body)

    def _local_request(self):
        config = self._hosted.config
        hosts = self.headers.get_all('Host', [])
        origins = self.headers.get_all('Origin', [])
        parsed = urlsplit(self.path)
        if len(hosts) != 1 or hosts[0] != urlsplit(config.public_origin).netloc or parsed.scheme or parsed.netloc:
            self._error(403, 'Use the configured hosted address.')
            return False
        if (len(origins) > 1 or (origins and origins[0] != config.public_origin)
                or (self.command == 'POST' and len(origins) != 1)):
            self._error(403, 'Use the same-origin hosted interface for this action.')
            return False
        if self.command == 'POST' and (len(self.headers.get_all('Content-Length', [])) != 1
                or self.headers.get_all('Transfer-Encoding')):
            self._error(400, 'Provide one bounded JSON request body.')
            return False
        return True

    def _cookie(self):
        raw = self.headers.get_all('Cookie', [])
        if len(raw) > 1 or (raw and len(raw[0]) > 4096):
            return None
        try:
            cookie = SimpleCookie(raw[0] if raw else '')
            name = self._hosted.cookie_name
            return cookie[name].value if name in cookie else None
        except CookieError:
            return None

    def _set_session(self, token=None):
        name = self._hosted.cookie_name
        secure = self._hosted.config.public_origin.startswith('https://')
        age = self._hosted.config.session_ttl_seconds if token else 0
        self._set_cookie = name + '=' + (token or '') + '; Path=/; HttpOnly; SameSite=Strict; Max-Age=' + str(age) + ('; Secure' if secure else '')

    def _status(self, session):
        c = self._hosted.config
        value = {'hosted': True, 'mode': 'hosted_judge', 'authenticated': session is not None,
                 'open_access': c.open_access,
                 'admin_controls': False, 'external_research_enabled': False, 'metrics_upload_enabled': False,
                 'live_ai_enabled': False, 'inference_available': False,
                 'limits': {'max_sessions': c.max_sessions, 'get_requests_per_minute': c.get_limit,
                    'post_requests_per_minute': c.post_limit, 'max_workspace_bytes': c.max_state_bytes,
                    'session_ttl_seconds': c.session_ttl_seconds}}
        if session is not None:
            value['expires_at'] = datetime.fromtimestamp(session['expires'], timezone.utc).isoformat()
            runtime = self._hosted.manager.runtime(session)
            value['live_ai_enabled'] = runtime.ai.status()['configured'] is True
            value['external_research_enabled'] = runtime.research.status()['key_present'] is True
            spending = getattr(runtime, 'hosted_spending', None)
            if callable(spending):
                limits = spending()
                value['inference_available'] = value['live_ai_enabled'] and all(
                    limits.get(key, 0) > 0 for key in ('total_remaining_usd', 'daily_remaining_usd', 'session_remaining_usd'))
        return value

    def _dispatch(self, method):
        if not self._local_request():
            return
        route, _ = self._query()
        manager = self._hosted.manager
        session = manager.session(self._cookie())
        if session is None and self._hosted.config.open_access:
            token = manager.ensure_open_session()
            if token is not None:
                self._set_session(token)
                session = manager.session(token)
        if method == 'GET' and route == '/health':
            status = build_status()
            self._reply(200, {'service': 'sixd-hosted-judge', 'mode': 'hosted_judge',
                             'build_id': status['build_id'], 'restart_required': status['restart_required']})
            return
        if method == 'GET' and route == '/api/hosted/status':
            if session is not None:
                manager.admit(session, method)
            self._reply(200, self._status(session))
            return
        if method == 'POST' and route == '/api/hosted/login':
            value = self._body()
            if not isinstance(value, dict) or not set(value).issubset({'access_code'}):
                raise WorkspaceError('The request has missing or unsupported fields.')
            if 'access_code' in value:
                if not isinstance(value['access_code'], str) or not 1 <= len(value['access_code']) <= 256:
                    raise WorkspaceError('Enter the private invitation code.')
                candidate_code = value['access_code']
            else:
                candidate_code = self._hosted.config.access_code
            if session is not None:
                # Repeated login cannot allocate another workspace while the
                # current cookie is valid. Reuse it without resetting limits.
                self._reply(200, {'hosted': True, 'authenticated': True})
                return
            token = manager.login(candidate_code)
            if token is None:
                self._error(401, 'The invitation code was not accepted.')
            else:
                self._set_session(token)
                self._reply(200, {'hosted': True, 'authenticated': True})
            return
        if method == 'GET' and route in LOGIN_ASSETS:
            self._reply(200, (WEB / route[1:]).read_bytes(), LOGIN_ASSETS[route])
            return
        if session is None:
            if method == 'GET' and route in ('/', '/index.html'):
                self._reply(200, (WEB / 'hosted-login.html').read_bytes(), LOGIN_ASSETS['/hosted-login.html'])
            else:
                self._error(401, 'Sign in with the private invitation code.')
            return
        if method == 'POST' and route == '/api/hosted/logout':
            # Storage exhaustion must not prevent revoking an authenticated
            # browser. No project data or usage ledger is removed by logout.
            manager._rate(session['id'], 'POST', self._hosted.config.post_limit)
            self._fields(self._body(), set())
            manager.revoke(session)
            self._set_session()
            self._reply(200, {'hosted': True, 'authenticated': False})
            return
        manager.admit(session, method)
        if method == 'POST' and route not in POST_ROUTES:
            self._error(403, 'This administrative or external-service action is unavailable to hosted visitors.')
            return
        if method == 'GET' and route in HOSTED_ASSETS:
            self._reply(200, (WEB / route[1:]).read_bytes(), HOSTED_ASSETS[route])
            return
        runtime = manager.runtime(session)
        owner_paths = ('/api/ai-quality', '/api/model-evaluation', '/api/workflow-evaluation',
                       '/api/evidence-evaluation', '/api/ultra-diagnostic', '/api/ultra-workflow',
                       '/api/observability')
        if method == 'GET' and any(route == path or route.startswith(path + '/') for path in owner_paths):
            self._error(403, 'Owner diagnostics are unavailable in the hosted review workspace.')
            return
        if method == 'GET' and route == '/api/ai/status':
            status = runtime.ai.status()
            budget = status.pop('budget', None) or {}
            status['spend_available'] = budget.get('remaining_usd', 0) > 0
            hosted_limits = budget.get('hosted_limits') or {}
            if hosted_limits:
                status['spend_available'] = status['spend_available'] and all(
                    hosted_limits.get(key, 0) > 0 for key in ('total_remaining_usd', 'daily_remaining_usd', 'session_remaining_usd'))
            status.pop('max_job_reservation_usd', None)
            for option in status.get('available_models', []):
                option.pop('max_job_reservation_usd', None)
            for key in ('key_source', 'key_remembered', 'credential_error', 'environment_key_configured'):
                status.pop(key, None)
            status.update(owner_controls=False, usage_managed=True, remember_supported=False,
                          note='AI connection and usage are managed by the workspace owner.')
            self._reply(200, status)
            return
        if method == 'POST' and route == '/api/investigations' and not runtime.ai.status()['configured']:
            self._error(403, 'Live AI is disabled for this hosted deployment. Saved engineering work remains available.')
            return
        if method == 'POST' and route == '/api/research/search' and not runtime.research.status()['key_present']:
            self._error(403, 'External research is disabled for this hosted deployment. Saved source references remain available.')
            return
        original = self.server
        self.server = _Facade(runtime, self._hosted)
        try:
            if method == 'GET':
                super().do_GET()
            else:
                # A session may end while this request waits behind a write.
                # Logout shares this lock; recheck before any mutation starts.
                with runtime._post_lock:
                    if not manager.active(session):
                        raise HostedSessionError()
                    super().do_POST()
        finally:
            self.server = original

    def _handle(self, method):
        try:
            self._dispatch(method)
        except HostedLimitError as error:
            self._error(429, str(error))
        except HostedSessionError:
            self._set_session()
            self._error(401, 'This hosted session has ended. Sign in again.')
        except ConflictError as error:
            self._error(409, str(error))
        except (WorkspaceError, ValueError, UnicodeError, RecursionError):
            self._error(400, 'The hosted request or local state is invalid. No automatic retry was made.')
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except Exception:
            self._error(503, 'The hosted workspace is temporarily unavailable. No automatic retry was made.')

    def do_GET(self):
        self._handle('GET')

    def do_POST(self):
        self._handle('POST')


class HostedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, config, address, *, runtime_factory=None, clock=None):
        self.config = config
        self.cookie_name = '__Host-sixd_session' if config.public_origin.startswith('https://') else 'sixd_test_session'
        self.manager = HostedManager(config, runtime_factory, clock=clock)
        self._connection_slots = threading.BoundedSemaphore(config.max_connections)
        super().__init__(address, HostedHandler)

    def process_request(self, request, client_address):
        if not self._connection_slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()


def create_hosted_server(config, host='127.0.0.1', port=8770, *, runtime_factory=None, clock=None):
    if host not in ('127.0.0.1', 'localhost', '0.0.0.0'):
        raise ValueError('Use an explicit loopback or private-container proxy bind.')
    if host == '0.0.0.0' and config.allow_loopback_http:
        raise ValueError('Loopback HTTP tests cannot bind a public interface.')
    return HostedHTTPServer(config, (host, port), runtime_factory=runtime_factory, clock=clock)
