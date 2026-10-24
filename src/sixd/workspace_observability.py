"""Explicit LangSmith export of allowlisted qualification metrics only.

No tracing SDK, ambient tracing, project text or raw AI responses are used.
API contract checked against https://docs.langchain.com/langsmith/trace-with-api.
The receipt records API acceptance, never successful semantic evaluation.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import threading
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import UUID, uuid4

from .model_evaluation import CANDIDATES
from .workspace import ConflictError, WorkspaceError, _digest, _encode, _now
from .credential_store import CredentialError
from .service_credentials import ServiceCredentialStore, credential_error_code, validate_connection

SCHEMA = 'sixd.observability-export.v1'
PREVIEW_SCHEMA = 'sixd.observability-preview.v1'
ENDPOINTS = {'us': 'https://api.smith.langchain.com/runs',
             'eu': 'https://eu.api.smith.langchain.com/runs'}
CASE_IDS = ('source-context', 'flight-scope', 'limit-only-change', 'unsupported-control')
TERMINAL = {'completed', 'stopped', 'failed', 'interrupted'}
ROW_STATES = {'completed', 'failed', 'not_run'}
EXPORT_STATES = {'pending', 'accepted_by_api', 'failed', 'unknown', 'interrupted'}
MAX_EXPORTS = 20
MAX_PAYLOAD_BYTES = 16384
MAX_RESPONSE_BYTES = 65536
_SHA = re.compile(r'^[0-9a-f]{64}$')
_IDENTITY = re.compile(r'^[0-9a-f]{32}$')
LIMITATIONS = [
    'Upload is explicit and optional. Only the previewed allowlisted hashes and bounded qualification metrics leave this computer.',
    'Project inputs, engineering values, source text, prompts, explanations and credentials are excluded.',
    'One upload attempt is retained per qualification, including failed, ambiguous or interrupted attempts; no automatic retry occurs.',
    'API acceptance does not establish that LangSmith displayed, scored or independently verified the run.',
    'Workflow gates are automated development checks, not human engineering review or model accuracy certification.',
]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _transport(endpoint, headers, body):
    """One POST, without proxy inheritance, redirects or any retry."""
    request = Request(endpoint, data=_encode(body).encode('utf-8'),
                      headers=headers, method='POST')
    try:
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=20) as response:
            status = response.status
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        # Response content is deliberately neither parsed nor reflected.
        return {'status': status, 'oversized': len(raw) > MAX_RESPONSE_BYTES}
    except HTTPError as error:
        status = error.code
        error.close()
        return {'status': status}
    except (URLError, OSError, TimeoutError):
        return {'status': None}


def _identity(value, label='Qualification'):
    if not isinstance(value, str) or not _IDENTITY.fullmatch(value):
        raise WorkspaceError(label + ' identity must be a saved hexadecimal identifier.')
    return value


def _hash(value):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise WorkspaceError('Qualification hashes are missing or invalid.')
    return value


def _number(value, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise WorkspaceError('Qualification metrics are outside the bounded export contract.')
    return value


def _count(value, maximum=10000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise WorkspaceError('Qualification counts are outside the bounded export contract.')
    return value


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise WorkspaceError('Qualification timestamps are invalid.')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds')
    except (ValueError, OverflowError):
        raise WorkspaceError('Qualification timestamps must include an explicit timezone.') from None


def _contains_secret(value, secrets):
    """Also inspect JSON strings containing nested/escaped serialized JSON."""
    if isinstance(value, str):
        if any(key and key in value for key in secrets):
            return True
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError, RecursionError):
            return False
        return decoded != value and _contains_secret(decoded, secrets)
    if isinstance(value, dict):
        return any(_contains_secret(k, secrets) or _contains_secret(v, secrets) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(v, secrets) for v in value)
    return False


def _payload(record):
    """Reconstruct each exported field. No free text is copied from receipts."""
    if (not isinstance(record, dict) or record.get('schema') != 'sixd.ai-qualification.v1'
            or record.get('state') not in TERMINAL):
        raise WorkspaceError('Choose a completed, stopped or failed saved qualification.')
    identity = _identity(record.get('qualification_id'))
    model = record.get('model')
    if model not in {candidate['model'] for candidate in CANDIDATES}:
        raise WorkspaceError('Qualification model is not a verified application candidate.')
    source_hashes = record.get('agent_sources')
    if not isinstance(source_hashes, dict) or not 1 <= len(source_hashes) <= 64:
        raise WorkspaceError('Qualification source hashes are missing or excessive.')
    # Filenames, source labels and URLs never leave the local qualification.
    source_hashes = sorted(_hash(value) for value in source_hashes.values())
    report = record.get('report')
    if (not isinstance(report, dict) or report.get('mode') not in {'live_comparison', 'offline_harness_validation'}
            or not isinstance(report.get('rows'), list) or not 1 <= len(report['rows']) <= len(CASE_IDS)):
        raise WorkspaceError('Qualification rows are outside the bounded export contract.')
    rows, seen = [], set()
    for source in report['rows']:
        if not isinstance(source, dict) or source.get('case_id') not in CASE_IDS or source['case_id'] in seen or source.get('state') not in ROW_STATES:
            raise WorkspaceError('Qualification contains unknown or duplicate cases.')
        score = source.get('score')
        if source['state'] != 'completed' and score is None:
            score = {'workflow_gate_pass': None}
        if not isinstance(score, dict) or (type(score.get('workflow_gate_pass')) is not bool and not (source['state'] != 'completed' and score.get('workflow_gate_pass') is None)):
            raise WorkspaceError('Qualification workflow gate must be explicit.')
        seen.add(source['case_id'])
        rows.append({'case_id': source['case_id'], 'state': source['state'],
                     'elapsed_seconds': None if source['state'] != 'completed' and source.get('elapsed_seconds') is None else _number(source.get('elapsed_seconds'), 86400),
                     'reserved_usd': None if source['state'] != 'completed' and source.get('reserved_usd') is None else _number(source.get('reserved_usd'), 29.50),
                     'request_reservations': None if source['state'] != 'completed' and source.get('request_reservations') is None else _count(source.get('request_reservations')),
                     'live_model_calls': None if source['state'] != 'completed' and source.get('live_model_calls') is None else _count(source.get('live_model_calls')),
                     'workflow_gate_pass': score['workflow_gate_pass']})
    start, end = _timestamp(record.get('created_at')), _timestamp(record.get('completed_at'))
    if end < start:
        raise WorkspaceError('Qualification completion predates its start.')
    return {'id': str(UUID(identity)), 'name': '6D qualification', 'run_type': 'chain',
            'session_name': '6D qualification', 'start_time': start, 'end_time': end,
            'inputs': {'qualification_id': identity, 'report_digest': _hash(report.get('report_digest')),
                       'model': model, 'agent_source_hashes': source_hashes},
            'outputs': {'qualification_state': record['state'], 'mode': report['mode'], 'cases': rows,
                        'reserved_usd': _number(record.get('reserved_usd'), 29.50),
                        'request_reservations': _count(record.get('request_reservations')),
                        'live_model_calls': (sum(row['live_model_calls'] for row in rows)
                                             if all(row['live_model_calls'] is not None for row in rows) else None)}}


class WorkspaceObservability:
    def __init__(self, ai, qualification, *, transport=None, credential_store=None, local_directory=None):
        self.ai, self.qualification, self.store = ai, qualification, ai.store
        self._key, self._region, self._workspace_id = None, 'us', None
        self._transport = transport or _transport
        self._lock = threading.RLock()
        self._active = 0
        local = Path(local_directory) if local_directory is not None else self.store.db_path.parent
        self._credential_store = (credential_store if credential_store is not None else
            ServiceCredentialStore(local / 'credentials' / 'langsmith.dpapi', service='langsmith'))
        self._remembered, self._key_source, self._credential_error = False, None, None
        with self.store._connect(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS project_observability_versions (
                export_id TEXT NOT NULL, version INTEGER NOT NULL,
                qualification_id TEXT NOT NULL, created_at TEXT NOT NULL,
                snapshot TEXT NOT NULL, digest TEXT NOT NULL,
                PRIMARY KEY(export_id,version), UNIQUE(qualification_id,version))''')
            pending = db.execute('SELECT export_id FROM project_observability_versions GROUP BY export_id HAVING MAX(version)=1').fetchall()
            for item in pending:
                first = self._read(db, item['export_id'])
                self._insert(db, {**{k: v for k, v in first.items() if k != 'digest'},
                    'version': 2, 'state': 'interrupted', 'completed_at': _now(),
                    'error_code': 'server_restarted', 'previous_digest': first['digest']})
        try:
            self._remembered = self._credential_store.exists()
            if self._remembered:
                restored = self._credential_store.load()
                if not isinstance(restored, dict) or set(restored) != {'key', 'settings'}:
                    raise CredentialError('credential_data_invalid')
                settings = validate_connection('langsmith', restored['key'], restored['settings'])
                self._key, self._region, self._workspace_id = restored['key'], settings['region'], settings['workspace_id']
                self._key_source = 'remembered'
        except CredentialError as error:
            self._credential_error = credential_error_code(error)

    @staticmethod
    def _insert(db, value):
        record = {**deepcopy(value), 'digest': _digest(value)}
        db.execute('INSERT INTO project_observability_versions VALUES (?,?,?,?,?,?)',
            (record['export_id'], record['version'], record['qualification_id'], record['created_at'], _encode(record), record['digest']))
        return record

    @staticmethod
    def _read(db, export_id):
        rows = db.execute('SELECT * FROM project_observability_versions WHERE export_id=? ORDER BY version', (export_id,)).fetchall()
        if not rows:
            raise WorkspaceError('Saved observability export not found.')
        try:
            if len(rows) not in (1, 2):
                raise ValueError
            prior = None
            for index, row in enumerate(rows, 1):
                value = json.loads(row['snapshot'])
                if (value.get('schema') != SCHEMA or value.get('version') != index
                        or value.get('state') not in (EXPORT_STATES - {'pending'} if index == 2 else {'pending'})
                        or any(value.get(k) != row[k] for k in ('export_id', 'version', 'qualification_id', 'created_at', 'digest'))
                        or _digest({k: v for k, v in value.items() if k != 'digest'}) != value['digest']
                        or (prior and value.get('previous_digest') != prior['digest'])):
                    raise ValueError
                if prior and any(value.get(k) != prior.get(k) for k in ('payload', 'preview_digest', 'region', 'workspace_id')):
                    raise ValueError
                prior = value
            return value
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
            raise WorkspaceError('Saved observability export is inconsistent.') from None

    def status(self):
        with self._lock, self.store._connect() as db:
            attempts = db.execute('SELECT COUNT(*) FROM project_observability_versions WHERE version=1').fetchone()[0]
            return {'schema': 'sixd.observability-status.v1', 'provider': 'langsmith',
                    'key_present': self._key is not None,
                    'remember_supported': self._credential_store.supported,
                    'key_remembered': self._remembered, 'key_source': self._key_source,
                    'credential_error': self._credential_error,
                    'key_storage': 'windows_current_user_dpapi' if self._key_source == 'remembered' else 'server_memory_only',
                    'region': self._region, 'workspace_id': self._workspace_id,
                    'endpoint': ENDPOINTS[self._region], 'attempts': attempts, 'maximum_attempts': MAX_EXPORTS,
                    'active_requests': self._active, 'can_export': self._key is not None and attempts < MAX_EXPORTS and not self._active,
                    'limitations': list(LIMITATIONS)}

    def connect(self, api_key, region='us', workspace_id=None, remember=False):
        if not isinstance(api_key, str) or not 8 <= len(api_key) <= 2048 or any(not 33 <= ord(ch) <= 126 for ch in api_key):
            raise WorkspaceError('Enter the LangSmith key privately without whitespace.')
        if not isinstance(region, str) or region not in ENDPOINTS:
            raise WorkspaceError('Choose the US or EU LangSmith region.')
        if type(remember) is not bool:
            raise WorkspaceError('Remember on this device must be true or false.')
        if workspace_id is not None:
            try:
                if not isinstance(workspace_id, str) or str(UUID(workspace_id)) != workspace_id.lower():
                    raise ValueError
                workspace_id = str(UUID(workspace_id))
            except (ValueError, AttributeError, TypeError):
                raise WorkspaceError('Optional LangSmith workspace identity must be a UUID.') from None
            if api_key in workspace_id:
                raise WorkspaceError('A private credential cannot be public connection metadata.')
        with self._lock:
            if self._active:
                raise ConflictError('Wait for the current explicit upload before changing its connection.')
            try:
                if remember:
                    self._credential_store.save(api_key, {'region': region, 'workspace_id': workspace_id})
                else:
                    self._credential_store.forget()
            except CredentialError as error:
                self._credential_error = credential_error_code(error)
                raise WorkspaceError('The private connection was not changed because local credential storage could not be updated. Review the storage status.') from None
            self._key, self._region, self._workspace_id = api_key, region, workspace_id
            self._remembered, self._key_source, self._credential_error = remember, 'remembered' if remember else 'session', None
        return self.status()

    def disconnect(self):
        with self._lock:
            if self._active:
                raise ConflictError('Wait for the current explicit upload before disconnecting its connection.')
            self._forget_connection()
            self._key = None
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
        """Remove the saved copy while keeping the current session and settings."""
        with self._lock:
            if self._active:
                raise ConflictError('Wait for the current explicit upload before changing its remembered connection.')
            self._forget_connection()
        return self.status()

    def preview(self, qualification_id):
        identity = _identity(qualification_id)
        record = self.qualification.get(identity)
        if record.get('qualification_id') != identity:
            raise WorkspaceError('Saved qualification identity does not match.')
        payload = _payload(record)
        with self._lock:
            value = {'schema': PREVIEW_SCHEMA, 'qualification_id': identity,
                     'endpoint': ENDPOINTS[self._region], 'region': self._region,
                     'workspace_id': self._workspace_id, 'payload': payload}
            if len(_encode(payload).encode('utf-8')) > MAX_PAYLOAD_BYTES:
                raise WorkspaceError('Qualification metrics exceed the bounded upload size.')
            if _contains_secret(value, (self._key, getattr(self.ai, '_key', None))):
                raise WorkspaceError('A private credential matched the upload preview. Nothing was sent.')
            return {**value, 'preview_digest': _digest(value)}

    def export(self, qualification_id, preview_digest, allow_upload=True):
        if allow_upload is not True:
            raise WorkspaceError('Explicit permission is required for this metrics upload.')
        if not isinstance(preview_digest, str) or not _SHA.fullmatch(preview_digest):
            raise WorkspaceError('Review the sanitized upload preview first.')
        with self._lock:
            if self._key is None:
                raise WorkspaceError('Connect LangSmith privately before explicitly uploading metrics.')
            if self._active:
                raise ConflictError('A metrics upload is already running.')
            preview = self.preview(qualification_id)
            if preview['preview_digest'] != preview_digest:
                raise ConflictError('The sanitized preview changed. Review it again before uploading.')
            key, region, tenant = self._key, self._region, self._workspace_id
            with self.store._connect(write=True) as db:
                if db.execute('SELECT 1 FROM project_observability_versions WHERE qualification_id=?', (qualification_id,)).fetchone():
                    raise ConflictError('This qualification already has a retained upload attempt; it cannot be sent again.')
                count = db.execute('SELECT COUNT(*) FROM project_observability_versions WHERE version=1').fetchone()[0]
                if count >= MAX_EXPORTS:
                    raise WorkspaceError('The lifetime local metrics upload limit has been reached.')
                first = self._insert(db, {'schema': SCHEMA, 'export_id': uuid4().hex, 'version': 1,
                    'qualification_id': qualification_id, 'created_at': _now(), 'state': 'pending',
                    'preview_digest': preview_digest, 'payload': preview['payload'], 'region': region,
                    'workspace_id': tenant})
            self._active += 1
        headers = {'x-api-key': key, 'Content-Type': 'application/json', 'Accept': 'application/json'}
        if tenant:
            headers['x-tenant-id'] = tenant
        state, code = 'unknown', 'transport_ambiguous'
        try:
            response = self._transport(ENDPOINTS[region], headers, deepcopy(preview['payload']))
            status = response.get('status') if isinstance(response, dict) else None
            if type(status) is int and 200 <= status <= 299:
                state, code = 'accepted_by_api', None
            elif type(status) is int and 300 <= status <= 499:
                state, code = 'failed', 'api_rejected'
            # A server error, lost response or malformed reply cannot establish non-delivery.
        except Exception:
            pass  # Raw provider exceptions can contain credentials; never persist or reflect them.
        finally:
            with self._lock:
                self._active -= 1
        with self.store._connect(write=True) as db:
            latest = self._read(db, first['export_id'])
            if latest['version'] == 2:
                return latest
            return self._insert(db, {**{k: v for k, v in first.items() if k != 'digest'},
                'version': 2, 'state': state, 'completed_at': _now(), 'error_code': code,
                'previous_digest': first['digest']})

    def get(self, export_id):
        with self.store._connect() as db:
            return self._read(db, _identity(export_id, 'Export'))

    def list(self):
        with self.store._connect() as db:
            db.execute('BEGIN')
            identities = db.execute('SELECT export_id FROM project_observability_versions WHERE version=1 ORDER BY created_at DESC').fetchall()
            return {'schema': 'sixd.observability-history.v1',
                    'exports': [self._read(db, row['export_id']) for row in identities]}
