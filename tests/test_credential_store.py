"""Synthetic credentials in isolated files; never read the founder's key."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.credential_store import CredentialStore, CredentialError, WindowsDPAPI, MAX_FILE_BYTES

KEY = "synthetic-dpapi-test-key-with-no-service-access"


class MemoryProtection:
    """A strict test codec; real Windows behavior has separate roundtrip tests."""
    supported = True
    def protect(self, data):
        return b"fixture-encrypted:" + data[::-1]
    def unprotect(self, data):
        if not data.startswith(b"fixture-encrypted:"):
            raise CredentialError("credential_decryption_failed")
        return data[len(b"fixture-encrypted:"):][::-1]


class CredentialStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "credentials" / "nebius.dpapi"
        self.codec = MemoryProtection()
        self.store = CredentialStore(self.path, protection=self.codec)

    def test_store_roundtrip_has_no_plaintext_and_forget_is_idempotent(self):
        self.assertFalse(self.store.exists())
        self.assertIsNone(self.store.load())
        self.store.save(KEY)
        self.assertTrue(self.store.exists())
        self.assertNotIn(KEY.encode(), self.path.read_bytes())
        self.assertEqual(self.store.load(), KEY)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        self.store.forget(); self.store.forget()
        self.assertFalse(self.store.exists())

    def test_bad_header_empty_or_oversized_ciphertext_is_rejected(self):
        self.path.parent.mkdir()
        for data in (b"", b"not a sixd credential", b"x" * (MAX_FILE_BYTES + 1)):
            self.path.write_bytes(data)
            with self.assertRaises(CredentialError):
                self.store.load()

    def test_changed_ciphertext_or_other_protection_cannot_supply_a_key(self):
        self.store.save(KEY)
        encoded = self.path.read_bytes()
        self.path.write_bytes(encoded[:-3] + b"???")
        with self.assertRaises(CredentialError):
            self.store.load()
        class WrongProtection(MemoryProtection):
            def unprotect(self, data):
                raise CredentialError("credential_decryption_failed")
        with self.assertRaises(CredentialError):
            CredentialStore(self.path, protection=WrongProtection()).load()

    def test_digest_schema_and_duplicate_fields_are_checked_after_decryption(self):
        self.store.save(KEY)
        prefix = self.path.read_bytes().split(b"fixture-encrypted:")[0]
        for decoded in (
            json.dumps({"schema": "wrong", "key": KEY, "key_digest": "x"}).encode(),
            json.dumps({"schema": "sixd.remembered-nebius-key.v1", "key": KEY, "key_digest": "wrong"}).encode(),
            b'{"schema":"sixd.remembered-nebius-key.v1","schema":"x","key":"fake-key"}',
        ):
            self.path.write_bytes(prefix + self.codec.protect(decoded))
            with self.assertRaises(CredentialError):
                self.store.load()

    def test_failed_atomic_replace_preserves_old_ciphertext_and_cleans_temp(self):
        self.store.save(KEY)
        before = self.path.read_bytes()
        with patch("sixd.credential_store.os.replace", side_effect=PermissionError("do not expose credential")):
            with self.assertRaises(CredentialError) as error:
                self.store.save(KEY + "-new")
        self.assertNotIn("do not expose", str(error.exception))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_memory_only_platform_does_not_fall_back_to_plaintext(self):
        class Unsupported(MemoryProtection):
            supported = False
        store = CredentialStore(self.path, protection=Unsupported())
        self.assertFalse(store.supported)
        with self.assertRaises(CredentialError):
            store.save(KEY)
        self.assertFalse(self.path.exists())

    @unittest.skipUnless(os.name == "nt", "Windows current-user DPAPI only")
    def test_real_windows_current_user_dpapi_roundtrip_and_corruption(self):
        store = CredentialStore(self.path)
        self.assertTrue(store.supported)
        store.save(KEY)
        encrypted = self.path.read_bytes()
        self.assertNotIn(KEY.encode(), encrypted)
        self.assertEqual(store.load(), KEY)
        # Flip the protected payload, not the application format header.
        corrupted = bytearray(encrypted)
        corrupted[-10] ^= 0x40
        self.path.write_bytes(corrupted)
        with self.assertRaises(CredentialError):
            store.load()

    @unittest.skipUnless(os.name == "nt", "Windows current-user DPAPI only")
    def test_dpapi_rejects_non_dpapi_bytes_without_raw_os_error(self):
        with self.assertRaises(CredentialError) as error:
            WindowsDPAPI().unprotect(b"this-is-not-a-Windows-protected-blob")
        self.assertEqual(error.exception.code, "credential_decryption_failed")


if __name__ == "__main__":
    unittest.main()
