"""Optional current-user DPAPI storage for bounded optional-service connections.

Service identity and validated connection settings are encrypted with the key.
No credential or connection setting is written as plaintext, including temp files.
Nebius keeps its existing v1 format and DPAPI entropy unchanged.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tempfile
from uuid import UUID

from .credential_store import CredentialError, MAX_FILE_BYTES, WindowsDPAPI


_SCHEMA = 'sixd.remembered-service-key.v1'
_MAGIC = b'6D-DPAPI-SERVICE-v1\n'
SERVICES = frozenset(('tavily', 'langsmith'))
# October 26 approval: 4,124 future credits plus one retained prior reservation.
MAX_TAVILY_CREDITS = 4125
_ERROR_CODES = frozenset(('credential_storage_unsupported', 'credential_data_invalid',
    'credential_encryption_failed', 'credential_decryption_failed',
    'credential_storage_unavailable', 'credential_path_invalid'))


def credential_error_code(error):
    """Only fixed application codes may enter public status."""
    return error.code if getattr(error, 'code', None) in _ERROR_CODES else 'credential_storage_unavailable'


def validate_connection(service, key, settings):
    """Validate decrypted data again before a service can become connected."""
    if (service not in SERVICES or not isinstance(key, str) or not 8 <= len(key) <= 2048
            or any(not 33 <= ord(ch) <= 126 for ch in key) or not isinstance(settings, dict)):
        raise CredentialError('credential_data_invalid')
    if service == 'tavily':
        if (set(settings) != {'credit_limit'} or type(settings['credit_limit']) is not int
                or not 1 <= settings['credit_limit'] <= MAX_TAVILY_CREDITS):
            raise CredentialError('credential_data_invalid')
        return {'credit_limit': settings['credit_limit']}
    if set(settings) != {'region', 'workspace_id'} or settings['region'] not in ('us', 'eu'):
        raise CredentialError('credential_data_invalid')
    workspace_id = settings['workspace_id']
    if workspace_id is not None:
        try:
            if (not isinstance(workspace_id, str) or len(workspace_id) != 36
                    or str(UUID(workspace_id)) != workspace_id.lower() or key in workspace_id):
                raise ValueError
            workspace_id = str(UUID(workspace_id))
        except (ValueError, AttributeError, TypeError):
            raise CredentialError('credential_data_invalid') from None
    return {'region': settings['region'], 'workspace_id': workspace_id}


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


class _ServiceDPAPI(WindowsDPAPI):
    def __init__(self, service):
        self._entropy = ('6D current-user local optional-service credential v1: ' + service).encode('ascii')

    def protect(self, data):
        return self._transform(data, decrypt=False, entropy_bytes=self._entropy)

    def unprotect(self, data):
        return self._transform(data, decrypt=True, entropy_bytes=self._entropy)


class ServiceCredentialStore:
    def __init__(self, path, *, service, protection=None):
        if service not in SERVICES:
            raise CredentialError('credential_data_invalid')
        self.path, self.service = Path(path), service
        self.protection = protection if protection is not None else _ServiceDPAPI(service)

    @property
    def supported(self):
        return bool(self.protection.supported)

    def _check_path(self):
        # Reject symlinks and Windows junction/reparse ancestors before file IO.
        for path in (self.path, *self.path.parents):
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if (stat.S_ISLNK(info.st_mode)
                    or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
                raise CredentialError('credential_path_invalid')
        if self.path.exists() and not self.path.is_file():
            raise CredentialError('credential_path_invalid')

    def exists(self):
        try:
            self._check_path()
            return self.path.is_file()
        except CredentialError:
            raise
        except Exception:
            raise CredentialError('credential_storage_unavailable') from None

    def save(self, key, settings):
        if not self.supported:
            raise CredentialError('credential_storage_unsupported')
        try:
            settings = validate_connection(self.service, key, settings)
            value = {'schema': _SCHEMA, 'service': self.service, 'key': key, 'settings': settings}
            envelope = {**value, 'digest': sha256(_encode(value)).hexdigest()}
            encrypted = self.protection.protect(_encode(envelope))
            if not isinstance(encrypted, bytes) or not 0 < len(encrypted) <= MAX_FILE_BYTES - len(_MAGIC):
                raise CredentialError('credential_encryption_failed')
            self._check_path()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._check_path()
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(prefix='.sixd-service-key-', dir=self.path.parent, delete=False) as stream:
                    temporary_path = Path(stream.name)
                    stream.write(_MAGIC + encrypted)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._check_path()
                os.replace(temporary_path, self.path)
                temporary_path = None
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
        except CredentialError as error:
            raise CredentialError(credential_error_code(error)) from None
        except Exception:
            raise CredentialError('credential_storage_unavailable') from None

    def load(self):
        if not self.supported:
            raise CredentialError('credential_storage_unsupported')
        try:
            self._check_path()
            with self.path.open('rb') as stream:
                encoded = stream.read(MAX_FILE_BYTES + 1)
            if len(encoded) > MAX_FILE_BYTES or not encoded.startswith(_MAGIC) or len(encoded) <= len(_MAGIC):
                raise CredentialError('credential_data_invalid')
            plaintext = self.protection.unprotect(encoded[len(_MAGIC):])
            if not isinstance(plaintext, bytes) or not 0 < len(plaintext) <= MAX_FILE_BYTES:
                raise CredentialError('credential_data_invalid')
            def unique(pairs):
                value = {}
                for name, item in pairs:
                    if name in value:
                        raise ValueError
                    value[name] = item
                return value
            envelope = json.loads(plaintext.decode('utf-8'), object_pairs_hook=unique,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
            if (not isinstance(envelope, dict) or set(envelope) != {'schema', 'service', 'key', 'settings', 'digest'}
                    or envelope['schema'] != _SCHEMA or envelope['service'] != self.service
                    or envelope['digest'] != sha256(_encode({k: v for k, v in envelope.items() if k != 'digest'})).hexdigest()):
                raise CredentialError('credential_data_invalid')
            settings = validate_connection(self.service, envelope['key'], envelope['settings'])
            return {'key': envelope['key'], 'settings': settings}
        except FileNotFoundError:
            return None
        except CredentialError as error:
            raise CredentialError(credential_error_code(error)) from None
        except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
            raise CredentialError('credential_data_invalid') from None
        except Exception:
            raise CredentialError('credential_storage_unavailable') from None

    def forget(self):
        try:
            self._check_path()
            self.path.unlink(missing_ok=True)
        except CredentialError:
            raise
        except Exception:
            raise CredentialError('credential_storage_unavailable') from None
