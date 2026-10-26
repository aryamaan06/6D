"""Explicit, bounded reference search; retrieved text is never engineering proof.

Only a user-entered query is sent to the fixed Tavily search endpoint. Search
attempts and their terminal receipts are separate append-only local records.
"""
from copy import deepcopy
import ipaddress
import json
import math
from pathlib import Path
import re
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

from .workspace import WorkspaceError, ConflictError, _digest, _encode, _now, _revision
from .workspace_sources import _text, _url, _targets
from .credential_store import CredentialError
from .service_credentials import ServiceCredentialStore, credential_error_code, validate_connection, MAX_TAVILY_CREDITS

SCHEMA = 'sixd.research-search.v1'
ENDPOINT = 'https://api.tavily.com/search'
MAX_CREDITS = MAX_TAVILY_CREDITS
MAX_RESPONSE_BYTES = 1024 * 1024
PARAMETERS = {'search_depth': 'basic', 'topic': 'general', 'max_results': 5,
    'include_answer': False, 'include_raw_content': False, 'include_images': False,
    'auto_parameters': False, 'include_usage': True}
LIMITATIONS = [
    'Search results and excerpts are unverified third-party text. Relevance scores are not engineering confidence.',
    'Search sends only your entered query to Tavily. Do not include confidential project data unless you intend to share that query.',
    'Basic search reserves one Tavily credit before sending. Failed or interrupted attempts retain that reservation; no automatic retry occurs.',
    'Local reservations are conservative request accounting, not your Tavily balance or proof of billed usage. This application cannot enforce the provider account billing settings.',
    'Previewing a result does not save a reference, link it, change a finding or establish applicability. Review the source form and then explicitly save and link it.',
    '6D does not fetch result URLs or authenticate their content. Public-looking URLs may change or resolve differently outside the application.',
    'Search receipts and source provenance use unsigned digests for consistency, not proof of truth or authenticated approval.',
]
ERRORS = {
    'provider_auth': ('Tavily rejected the connection.', 'Check the private key and account status before deliberately searching again.'),
    'provider_quota': ('Tavily refused this request because of a service or account limit.', 'Review Tavily usage and limits before deliberately searching again.'),
    'provider_transport': ('The Tavily request could not be completed.', 'Check the connection and retained reservation before deliberately searching again.'),
    'provider_response': ('Tavily returned a response outside the bounded search contract.', 'Review the preserved request identity; no returned text was accepted and no retry was made.'),
}


class _ResearchFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _parse(raw):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def _transport(api_key, body):
    request = Request(ENDPOINT, data=_encode(body).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json',
                 'Accept': 'application/json'}, method='POST')
    try:
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=30) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise _ResearchFailure('provider_response')
        return raw
    except HTTPError as exc:
        code = 'provider_auth' if exc.code in (401, 403) else 'provider_quota' if exc.code in (429, 432, 433) else 'provider_transport'
        exc.close()
        raise _ResearchFailure(code) from None
    except (URLError, OSError, TimeoutError):
        raise _ResearchFailure('provider_transport') from None


def _public_url(value):
    _url(value)
    host = urlsplit(value).hostname.rstrip('.').lower()
    if host in ('localhost', 'localhost.localdomain') or host.endswith(('.localhost', '.local', '.localdomain', '.internal', '.test', '.invalid')):
        raise ValueError('Nonpublic host')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if '.' not in host or re.fullmatch(r'[0-9.]+', host):
            raise ValueError('Nonpublic host')
        encoded = host.encode('idna').decode('ascii')
        if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part) for part in encoded.split('.')):
            raise ValueError('Invalid host')
    else:
        if not address.is_global:
            raise ValueError('Nonpublic address')
    return value


def _contains_secret(value, key):
    if isinstance(value, str):
        if key in value:
            return True
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError, RecursionError):
            return False
        return decoded != value and _contains_secret(decoded, key)
    if isinstance(value, dict):
        return any(_contains_secret(name, key) or _contains_secret(item, key) for name, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret(item, key) for item in value)
    return False


def _response(raw, key):
    try:
        if isinstance(raw, dict):
            encoded = _encode(raw)
            if len(encoded.encode('utf-8')) > MAX_RESPONSE_BYTES:
                raise ValueError('Too large')
            value = _parse(encoded)
        else:
            if not isinstance(raw, (str, bytes)) or len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError('Invalid body')
            encoded = raw.decode('utf-8') if isinstance(raw, bytes) else raw
            value = _parse(encoded)
        # Never reflect a credential echoed in a response, including an unknown field.
        if key in encoded or _contains_secret(value, key) or not isinstance(value, dict) or not isinstance(value.get('results'), list) or len(value['results']) > 5:
            raise ValueError('Invalid response')
        results = []
        for index, item in enumerate(value['results']):
            if not isinstance(item, dict):
                raise ValueError('Invalid result')
            title = _text(item.get('title'), 'Result title', 200)
            content = _text(item.get('content'), 'Result excerpt', MAX_RESPONSE_BYTES)
            url = _public_url(item.get('url'))
            row = {'index': index, 'title': title, 'url': url, 'content': content[:8000],
                   'content_truncated': len(content) > 8000}
            if item.get('score') is not None:
                score = item['score']
                if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
                    raise ValueError('Invalid relevance score')
                row['score'] = score
            results.append(row)
        request_id = value.get('request_id')
        if request_id is not None:
            _text(request_id, 'Provider request ID', 200)
        usage = value.get('usage')
        if usage is not None:
            if not isinstance(usage, dict) or isinstance(usage.get('credits'), bool) or not isinstance(usage.get('credits'), (int, float)) or not math.isfinite(usage['credits']) or usage['credits'] < 0:
                raise ValueError('Invalid usage')
            usage = {'credits': usage['credits']}
        return results, request_id, usage
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        raise _ResearchFailure('provider_response') from None


def preview_source(receipt, index):
    """Prepare an editable source form from one exact accepted search result."""
    if (not isinstance(receipt, dict) or receipt.get('schema') != SCHEMA or receipt.get('state') != 'completed'
            or receipt.get('digest') != _digest({key: value for key, value in receipt.items() if key != 'digest'})
            or type(index) is not int or not 0 <= index < len(receipt.get('results', []))):
        raise WorkspaceError('Choose an accepted result from an exact saved search receipt.')
    result = receipt['results'][index]
    details = ('Unverified Tavily basic search excerpt, reviewed for manual source intake.\n'
        + 'Search: ' + receipt['search_id'] + ' · result index ' + str(index) + '\n'
        + 'Query: ' + receipt['query'] + '\nRetrieved: ' + receipt['completed_at']
        + '\nOriginal project: ' + receipt['project_id'] + ' · saved revision ' + str(receipt['revision'])
        + '\nOriginal target: ' + receipt['target']['target_id'] + ' · ' + receipt['target']['label']
        + '\nReceipt SHA-256: ' + receipt['digest']
        + '\nProvider request: ' + str(receipt.get('request_id') or 'not supplied')
        + ('\nExcerpt truncated to the source form limit.' if result['content_truncated'] else '')
        + '\nSearch relevance and source authenticity/applicability are not verified. Saving and linking remain explicit separate actions.')
    return {'source_id': None, 'base_version': None, 'title': result['title'], 'url': result['url'],
            'excerpt': result['content'], 'details': details}


class WorkspaceResearch:
    def __init__(self, store, sources, transport=None, *, credential_store=None, local_directory=None):
        if sources.store is not store:
            raise WorkspaceError('Research and source library must share a workspace.')
        self.store, self.sources = store, sources
        self._key, self._credit_limit = None, None
        self._active = 0
        self._transport = transport or _transport
        self._lock = threading.RLock()
        local = Path(local_directory) if local_directory is not None else self.store.db_path.parent
        self._credential_store = (credential_store if credential_store is not None else
            ServiceCredentialStore(local / 'credentials' / 'tavily.dpapi', service='tavily'))
        self._remembered, self._key_source, self._credential_error = False, None, None
        with store._connect(write=True) as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS project_research_versions (
                search_id TEXT NOT NULL, version INTEGER NOT NULL,
                project_id TEXT NOT NULL REFERENCES projects(project_id), revision INTEGER NOT NULL,
                created_at TEXT NOT NULL, snapshot TEXT NOT NULL, digest TEXT NOT NULL,
                PRIMARY KEY(search_id,version),
                FOREIGN KEY(project_id,revision) REFERENCES revisions(project_id,revision))''')
        try:
            self._remembered = self._credential_store.exists()
            if self._remembered:
                restored = self._credential_store.load()
                if not isinstance(restored, dict) or set(restored) != {'key', 'settings'}:
                    raise CredentialError('credential_data_invalid')
                settings = validate_connection('tavily', restored['key'], restored['settings'])
                with self.store._connect() as connection:
                    if settings['credit_limit'] < self._reserved(connection):
                        raise CredentialError('credential_data_invalid')
                self._key, self._credit_limit = restored['key'], settings['credit_limit']
                self._key_source = 'remembered'
        except CredentialError as error:
            self._credential_error = credential_error_code(error)

    def _reserved(self, connection):
        return connection.execute('SELECT COUNT(*) FROM project_research_versions WHERE version=1').fetchone()[0]

    def _usage_review_required(self, connection):
        identities = connection.execute('SELECT DISTINCT search_id FROM project_research_versions WHERE version=2').fetchall()
        for row in identities:
            receipt = self._load(connection.execute('SELECT * FROM project_research_versions WHERE search_id=? ORDER BY version', (row['search_id'],)).fetchall())
            usage = receipt.get('reported_usage')
            if usage is not None:
                try:
                    credits = usage['credits']
                    if isinstance(credits, bool) or not isinstance(credits, (int, float)) or not math.isfinite(credits) or credits < 0:
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    raise WorkspaceError('Saved provider usage is inconsistent. Research remains blocked for review.') from None
                if credits > receipt['reserved_credits']:
                    return True
        return False

    def status(self):
        with self._lock, self.store._connect() as connection:
            reserved = self._reserved(connection)
            review_required = self._usage_review_required(connection)
            return {'schema': 'sixd.research-status.v1', 'provider': 'tavily', 'key_present': self._key is not None,
                'credit_limit': self._credit_limit, 'reserved_credits': reserved,
                'remaining_credits': max(0, self._credit_limit - reserved) if self._credit_limit is not None else 0,
                'maximum_credit_limit': MAX_CREDITS, 'request_credit_bound': 1, 'max_results': 5,
                'active_requests': self._active,
                'usage_review_required': review_required,
                'can_search': self._key is not None and self._credit_limit is not None and reserved < self._credit_limit and not review_required,
                'remember_supported': self._credential_store.supported,
                'key_remembered': self._remembered, 'key_source': self._key_source,
                'credential_error': self._credential_error,
                'key_storage': 'windows_current_user_dpapi' if self._key_source == 'remembered' else 'server_memory_only',
                'limitations': list(LIMITATIONS)}

    def connect(self, api_key, credit_limit, remember=False):
        if (not isinstance(api_key, str) or not 8 <= len(api_key) <= 2048
                or any(ord(ch) < 33 or ord(ch) > 126 for ch in api_key)):
            raise WorkspaceError('Enter a nonempty Tavily key privately, without whitespace.')
        if type(credit_limit) is not int or not 1 <= credit_limit <= MAX_CREDITS:
            raise WorkspaceError('Choose a positive integer Tavily allowance within the approved cumulative limit.')
        if type(remember) is not bool:
            raise WorkspaceError('Remember on this device must be true or false.')
        with self._lock, self.store._connect() as connection:
            if self._active:
                raise ConflictError('Wait for the current explicit search before changing its connection.')
            if credit_limit < self._reserved(connection):
                raise WorkspaceError('The absolute allowance cannot be below retained request reservations.')
            try:
                if remember:
                    self._credential_store.save(api_key, {'credit_limit': credit_limit})
                else:
                    self._credential_store.forget()
            except CredentialError as error:
                self._credential_error = credential_error_code(error)
                raise WorkspaceError('The private connection was not changed because local credential storage could not be updated. Review the storage status.') from None
            self._key, self._credit_limit = api_key, credit_limit
            self._remembered, self._key_source, self._credential_error = remember, 'remembered' if remember else 'session', None
        return self.status()

    def disconnect(self):
        with self._lock:
            if self._active:
                raise ConflictError('Wait for the current explicit search before disconnecting its connection.')
            self._forget_connection()
            self._key, self._credit_limit = None, None
            self._key_source = None
        return self.status()

    def _forget_connection(self):
        try:
            self._credential_store.forget()
        except CredentialError as error:
            self._credential_error = credential_error_code(error)
            raise WorkspaceError('The remembered copy could not be removed. The current private connection was not changed.') from None
        self._remembered, self._credential_error = False, None
        if self._key_source == 'remembered':
            self._key_source = 'session'

    def forget_key(self):
        """Remove the saved copy while keeping the current session and allowance."""
        with self._lock:
            if self._active:
                raise ConflictError('Wait for the current explicit search before changing its remembered connection.')
            self._forget_connection()
        return self.status()

    @staticmethod
    def _insert(connection, record):
        value = {**deepcopy(record), 'digest': _digest(record)}
        connection.execute('INSERT INTO project_research_versions VALUES (?,?,?,?,?,?,?)',
            (value['search_id'], value['version'], value['project_id'], value['revision'], value['created_at'], _encode(value), value['digest']))
        return value

    @staticmethod
    def _load(rows):
        records = []
        try:
            if not 1 <= len(rows) <= 2:
                raise ValueError
            for row in rows:
                value = _parse(row['snapshot'])
                if (value.get('schema') != SCHEMA or value.get('digest') != row['digest']
                        or value['digest'] != _digest({k: v for k, v in value.items() if k != 'digest'})
                        or any(value[key] != row[key] for key in ('search_id', 'version', 'project_id', 'revision', 'created_at'))
                        or value['reserved_credits'] != 1 or value['request'] != PARAMETERS
                        or value['version'] != len(records) + 1
                        or value['state'] not in ({'pending'} if value['version'] == 1 else {'completed', 'failed'})):
                    raise ValueError
                if records:
                    changing = {'version', 'state', 'completed_at', 'request_id', 'reported_usage', 'usage_warning', 'results', 'error', 'digest'}
                    if {k: v for k, v in records[0].items() if k not in changing} != {k: v for k, v in value.items() if k not in changing}:
                        raise ValueError
                records.append(value)
            return records[-1]
        except (ValueError, TypeError, KeyError):
            raise WorkspaceError('A saved research receipt is inconsistent. No record was replaced.') from None

    def _get(self, connection, search_id, project_id, revision):
        _text(search_id, 'Search ID', 64)
        rows = connection.execute('''SELECT * FROM project_research_versions
            WHERE search_id=? AND project_id=? AND revision<=? ORDER BY version''',
            (search_id, project_id, revision)).fetchall()
        if not rows:
            raise WorkspaceError('The search is unavailable in this project revision.')
        return self._load(rows)

    def list(self, project_id, revision):
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            view = self.sources._view(connection, project_id, revision)
            profile = self.sources.summary_in_snapshot(connection, view)
            ids = connection.execute('''SELECT search_id FROM project_research_versions
                WHERE project_id=? AND revision<=? AND version=1 ORDER BY rowid DESC LIMIT 100''',
                (project_id, revision)).fetchall()
            receipts = [self._get(connection, row['search_id'], project_id, revision) for row in ids]
            searches = [{key: deepcopy(item[key]) for key in ('search_id', 'revision', 'created_at', 'state', 'query', 'target', 'reserved_credits', 'digest')}
                        | {'result_count': len(item['results'])} for item in receipts]
            review_required = self._usage_review_required(connection)
            result = {'schema': 'sixd.project-research.v1', 'project_id': project_id, 'revision': view['revision'],
                'can_search': view['revision'] == view['latest_revision'] and not review_required,
                'usage_review_required': review_required, 'library_digest': profile['digest'],
                'targets': profile['targets'], 'searches': searches, 'limitations': list(LIMITATIONS)}
            return {**result, 'digest': _digest(result)}

    def get(self, search_id, project_id, revision):
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            self.sources._view(connection, project_id, revision)
            return self._get(connection, search_id, project_id, revision)

    def search(self, project_id, revision, target_id, query, expected_digest):
        _text(query, 'Search query', 1000)
        _text(target_id, 'Research target', 8192)
        if not isinstance(expected_digest, str) or re.fullmatch('[a-f0-9]{64}', expected_digest) is None:
            raise WorkspaceError('Supply the exact displayed source-library digest before searching.')
        revision = _revision(revision)
        with self._lock:
            if self._key is None or self._credit_limit is None:
                raise WorkspaceError('Connect a Tavily key privately before explicitly searching.')
            key = self._key
            if key in query:
                raise WorkspaceError('The query contains the connected credential. Remove it before searching.')
            with self.store._connect(write=True) as connection:
                view = self.sources._view(connection, project_id, revision, write=True)
                profile = self.sources.summary_in_snapshot(connection, view)
                if profile['digest'] != expected_digest:
                    raise ConflictError('The source library or finding changed. Refresh and review it before searching.')
                targets = _targets(view)
                if target_id not in targets:
                    raise ConflictError('The selected engineering target is unavailable. Refresh before searching.')
                if self._usage_review_required(connection):
                    raise WorkspaceError('Reported Tavily usage exceeded the local basic-request reservation. Research is blocked for provider/account review; reconnecting does not clear this record.')
                if self._reserved(connection) >= min(self._credit_limit, MAX_CREDITS):
                    raise WorkspaceError('The local Tavily allowance is exhausted. Retained reservations are not reset by reconnecting.')
                target, context = targets[target_id]
                request = {'schema': SCHEMA, 'search_id': uuid4().hex, 'version': 1, 'project_id': project_id,
                    'revision': revision, 'created_at': _now(), 'completed_at': None, 'state': 'pending',
                    'query': query, 'target': deepcopy(target), 'context_digest': _digest(context),
                    'project_digest': profile['project_digest'], 'library_digest': profile['digest'], 'run_id': profile['run_id'],
                    'request': deepcopy(PARAMETERS), 'reserved_credits': 1, 'provider': 'tavily',
                    'request_id': None, 'reported_usage': None, 'usage_warning': None, 'results': [], 'error': None,
                    'limitations': list(LIMITATIONS)}
                self._insert(connection, request)
            self._active += 1
        try:
            return self._finish(request, key)
        finally:
            with self._lock:
                self._active -= 1

    def _finish(self, request, key):
        terminal = {**deepcopy(request), 'version': 2, 'completed_at': _now()}
        try:
            raw = self._transport(key, {'query': request['query'], **deepcopy(PARAMETERS)})
            results, request_id, usage = _response(raw, key)
            terminal.update(state='completed', results=results, request_id=request_id, reported_usage=usage)
            if usage and usage['credits'] > request['reserved_credits']:
                terminal['usage_warning'] = ('Tavily reported usage above the local basic-request reservation. '
                    'The retained reservation count is not a provider billing ceiling; review provider usage and account settings before another search.')
        except _ResearchFailure as exc:
            message, next_step = ERRORS[exc.code]
            terminal.update(state='failed', error={'code': exc.code, 'message': message, 'next_step': next_step})
        except Exception:
            message, next_step = ERRORS['provider_transport']
            terminal.update(state='failed', error={'code': 'provider_transport', 'message': message, 'next_step': next_step})
        terminal['completed_at'] = _now()
        with self.store._connect(write=True) as connection:
            return self._insert(connection, terminal)

    @staticmethod
    def preview_source(receipt, index):
        return preview_source(receipt, index)
