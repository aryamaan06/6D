"""Synthetic isolated optional-service secrets; fake and real crypto are separate."""
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.credential_store import CredentialError, CredentialStore, MAX_FILE_BYTES
from sixd.service_credentials import ServiceCredentialStore, _MAGIC, _SCHEMA, _encode

KEY = 'synthetic-optional-service-key-no-account-access'
TAVILY = {'credit_limit': 7}
LANGSMITH = {'region': 'eu', 'workspace_id': '0c678cf0-6414-4356-bb55-188cf9725820'}


class FixtureProtection:
    """Reversible fixture only; this is deliberately not a security implementation."""
    supported = True

    def protect(self, data):
        return b'fixture-protected:' + data[::-1]

    def unprotect(self, data):
        if not data.startswith(b'fixture-protected:'):
            raise CredentialError('credential_decryption_failed')
        return data[len(b'fixture-protected:'):][::-1]


class UnsupportedProtection(FixtureProtection):
    supported = False


class ServiceCredentialFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'credentials'
        self.codec = FixtureProtection()
        self.tavily = self.store('tavily')
        self.langsmith = self.store('langsmith')

    def store(self, service, protection=None):
        return ServiceCredentialStore(self.directory / (service + '.dpapi'), service=service,
            protection=protection if protection is not None else self.codec)

    def encoded(self, service='tavily', key=KEY, settings=None, **overrides):
        value = {'schema': _SCHEMA, 'service': service, 'key': key,
            'settings': settings if settings is not None else TAVILY}
        value.update(overrides)
        return _MAGIC + self.codec.protect(_encode({**value, 'digest': sha256(_encode(value)).hexdigest()}))

    def test_roundtrip_settings_and_only_ciphertext_files(self):
        for store, settings in ((self.tavily, TAVILY), (self.langsmith, LANGSMITH)):
            self.assertIsNone(store.load())
            self.assertFalse(store.exists())
            store.save(KEY, settings)
            self.assertEqual(store.load(), {'key': KEY, 'settings': settings})
            encoded = store.path.read_bytes()
            for private in (KEY.encode(), b'credit_limit', b'workspace_id', b'0c678cf0'):
                self.assertNotIn(private, encoded)
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()), ['langsmith.dpapi', 'tavily.dpapi'])
        self.tavily.forget()
        self.tavily.forget()
        self.assertFalse(self.tavily.exists())
        self.assertEqual(self.langsmith.load()['settings'], LANGSMITH)

    def test_cross_service_and_nebius_blobs_are_rejected_even_with_shared_fixture_codec(self):
        self.tavily.save(KEY, TAVILY)
        self.langsmith.path.write_bytes(self.tavily.path.read_bytes())
        with self.assertRaises(CredentialError):
            self.langsmith.load()
        nebius = CredentialStore(self.directory / 'nebius.dpapi', protection=self.codec)
        nebius.save(KEY)
        self.tavily.path.write_bytes(nebius.path.read_bytes())
        with self.assertRaises(CredentialError):
            self.tavily.load()
        self.assertEqual(nebius.load(), KEY)

    def test_strict_schema_settings_and_key_validation_after_decryption(self):
        self.directory.mkdir()
        invalid = [self.encoded(schema='wrong'), self.encoded(service='langsmith'),
            self.encoded(settings={'credit_limit': True}), self.encoded(settings={'credit_limit': 0}),
            self.encoded(settings={'credit_limit': 21}), self.encoded(settings={'credit_limit': 3, 'other': 1}),
            self.encoded(key='short'), self.encoded(key=KEY + ' '),
            _MAGIC + self.codec.protect(b'{"schema":"x","schema":"x"}'),
            _MAGIC + self.codec.protect(b'{"key":NaN}'),
            self.encoded().replace(b'fixture-protected:', b'wrong:')]
        for encoded in invalid:
            with self.subTest(encoded_length=len(encoded)):
                self.tavily.path.write_bytes(encoded)
                with self.assertRaises(CredentialError):
                    self.tavily.load()
        for settings in ({'region': 'other', 'workspace_id': None}, {'region': 'us'},
                {'region': 'us', 'workspace_id': 'invalid'}, {'region': 'us', 'workspace_id': 42}):
            self.langsmith.path.write_bytes(self.encoded(service='langsmith', settings=settings))
            with self.assertRaises(CredentialError):
                self.langsmith.load()

    def test_digest_and_envelope_extra_fields_cannot_be_accepted(self):
        self.tavily.save(KEY, TAVILY)
        envelope = json.loads(self.codec.unprotect(self.tavily.path.read_bytes()[len(_MAGIC):]))
        for change in ({'digest': '0' * 64}, {'settings': {'credit_limit': 20}}, {'unknown': 'ignored?'}):
            self.tavily.path.write_bytes(_MAGIC + self.codec.protect(_encode({**envelope, **change})))
            with self.assertRaises(CredentialError):
                self.tavily.load()

    def test_header_ciphertext_and_plaintext_size_are_bounded(self):
        self.directory.mkdir()
        for encoded in (b'', _MAGIC, b'plain ' + KEY.encode(), b'x' * (MAX_FILE_BYTES + 1),
                _MAGIC + self.codec.protect(b'x' * (MAX_FILE_BYTES + 1))):
            self.tavily.path.write_bytes(encoded)
            with self.assertRaises(CredentialError):
                self.tavily.load()
        for bad in (b'', 'plaintext', b'x' * MAX_FILE_BYTES):
            with patch.object(self.codec, 'protect', return_value=bad):
                with self.assertRaises(CredentialError):
                    self.tavily.save(KEY, TAVILY)
        with patch.object(self.codec, 'unprotect', return_value=b'x' * (MAX_FILE_BYTES + 1)):
            self.tavily.path.write_bytes(_MAGIC + b'small-ciphertext')
            with self.assertRaises(CredentialError):
                self.tavily.load()

    def test_atomic_replace_failure_preserves_prior_copy_and_temps_contain_only_ciphertext(self):
        self.tavily.save(KEY, TAVILY)
        before = self.tavily.path.read_bytes()
        observed = []
        def blocked(source, destination):
            observed.append(Path(source).read_bytes())
            self.assertEqual(Path(destination), self.tavily.path)
            raise PermissionError(KEY)
        with patch('sixd.service_credentials.os.replace', side_effect=blocked):
            with self.assertRaises(CredentialError) as error:
                self.tavily.save(KEY + '-new', {'credit_limit': 9})
        self.assertTrue(observed)
        self.assertNotIn(KEY.encode(), observed[0])
        self.assertNotIn(KEY, str(error.exception))
        self.assertEqual(self.tavily.path.read_bytes(), before)
        self.assertEqual(list(self.directory.iterdir()), [self.tavily.path])

    def test_unsupported_never_falls_back_and_forget_can_remove_prior_copy(self):
        self.tavily.save(KEY, TAVILY)
        unsupported = self.store('tavily', UnsupportedProtection())
        self.assertFalse(unsupported.supported)
        for action in (lambda: unsupported.save(KEY, TAVILY), unsupported.load):
            with self.assertRaises(CredentialError) as error:
                action()
            self.assertEqual(error.exception.code, 'credential_storage_unsupported')
        unsupported.forget()
        self.assertFalse(unsupported.exists())
        self.assertFalse(any(self.directory.iterdir()))

    def test_unexpected_crypto_errors_and_error_codes_are_sanitized(self):
        for exception in (RuntimeError(KEY), CredentialError(KEY)):
            with patch.object(self.codec, 'protect', side_effect=exception):
                with self.assertRaises(CredentialError) as error:
                    self.tavily.save(KEY, TAVILY)
            self.assertEqual(error.exception.code, 'credential_storage_unavailable')
            self.assertNotIn(KEY, str(error.exception))
        self.assertFalse(self.directory.exists())

    def test_linked_ancestor_guard_runs_without_windows_symlink_privilege(self):
        self.directory.mkdir()
        original_lstat = Path.lstat
        def linked(path, *args, **kwargs):
            if path == self.directory:
                return SimpleNamespace(st_mode=stat.S_IFLNK,
                    st_file_attributes=getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0))
            return original_lstat(path, *args, **kwargs)
        with patch.object(Path, 'lstat', linked):
            for action in (self.tavily.exists, self.tavily.load, self.tavily.forget,
                    lambda: self.tavily.save(KEY, TAVILY)):
                with self.assertRaises(CredentialError) as error:
                    action()
                self.assertEqual(error.exception.code, 'credential_path_invalid')
        self.assertFalse(any(self.directory.iterdir()))

    def test_directory_and_symlink_paths_fail_closed(self):
        self.tavily.path.mkdir(parents=True)
        with self.assertRaises(CredentialError):
            self.tavily.save(KEY, TAVILY)
        self.tavily.path.rmdir()
        target = Path(self.temp.name) / 'elsewhere'
        target.mkdir()
        junction = self.directory / 'linked'
        try:
            junction.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest('Creating symlinks needs local Windows privilege.')
        store = ServiceCredentialStore(junction / 'key.dpapi', service='tavily', protection=self.codec)
        for action in (store.exists, store.load, store.forget, lambda: store.save(KEY, TAVILY)):
            with self.assertRaises(CredentialError) as error:
                action()
            self.assertEqual(error.exception.code, 'credential_path_invalid')
        self.assertFalse(any(target.iterdir()))


@unittest.skipUnless(os.name == 'nt', 'Real current-Windows-user DPAPI only')
class ServiceCredentialWindowsTests(unittest.TestCase):
    def test_actual_windows_roundtrip_service_entropy_and_legacy_nebius_compatibility(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as directory:
            directory = Path(directory)
            tavily = ServiceCredentialStore(directory / 'tavily.dpapi', service='tavily')
            langsmith = ServiceCredentialStore(directory / 'langsmith.dpapi', service='langsmith')
            nebius = CredentialStore(directory / 'nebius.dpapi')
            for store, settings in ((tavily, TAVILY), (langsmith, LANGSMITH)):
                store.save(KEY, settings)
                self.assertNotIn(KEY.encode(), store.path.read_bytes())
                self.assertEqual(store.load(), {'key': KEY, 'settings': settings})
            nebius.save(KEY)
            self.assertEqual(nebius.load(), KEY)
            original = tavily.path.read_bytes()
            langsmith.path.write_bytes(original)
            with self.assertRaises(CredentialError) as error:
                langsmith.load()
            self.assertEqual(error.exception.code, 'credential_decryption_failed')
            corrupt = bytearray(original)
            corrupt[-10] ^= 0x20
            tavily.path.write_bytes(corrupt)
            with self.assertRaises(CredentialError):
                tavily.load()
            self.assertEqual(nebius.load(), KEY)


if __name__ == '__main__':
    unittest.main()
