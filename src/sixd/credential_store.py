"""Optional current-Windows-user DPAPI storage for one local provider key.

No plaintext credential is written, logged or returned by this storage surface.
DPAPI protects data for the current Windows account, not against software already
running as that account. Other platforms keep memory-only connections.
"""
import ctypes
from ctypes import wintypes
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile


MAX_FILE_BYTES = 65536
_MAGIC = b"6D-DPAPI-KEY-v1\n"
_SCHEMA = "sixd.remembered-nebius-key.v1"
_ENTROPY = b"6D current-user local Nebius credential v1"


class CredentialError(Exception):
    """A controlled failure; raw OS/crypto exception text is never public."""
    def __init__(self, code):
        self.code = code
        super().__init__("The remembered API key could not be accessed safely.")


def valid_key(value):
    return (isinstance(value, str) and 16 <= len(value) <= 8192
            and not any(ch.isspace() or ord(ch) < 32 for ch in value))


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


class WindowsDPAPI:
    supported = os.name == "nt"

    @staticmethod
    def _transform(data, *, decrypt):
        if os.name != "nt":
            raise CredentialError("credential_storage_unsupported")
        if not isinstance(data, bytes) or not 0 < len(data) <= MAX_FILE_BYTES:
            raise CredentialError("credential_data_invalid")
        try:
            crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            protect = crypt32.CryptProtectData
            protect.argtypes = [ctypes.POINTER(_DataBlob), wintypes.LPCWSTR,
                ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
                wintypes.DWORD, ctypes.POINTER(_DataBlob)]
            protect.restype = wintypes.BOOL
            unprotect = crypt32.CryptUnprotectData
            unprotect.argtypes = [ctypes.POINTER(_DataBlob), ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
                wintypes.DWORD, ctypes.POINTER(_DataBlob)]
            unprotect.restype = wintypes.BOOL
            free = kernel32.LocalFree
            free.argtypes = [ctypes.c_void_p]
            free.restype = ctypes.c_void_p
            source_buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
            entropy_buffer = (ctypes.c_ubyte * len(_ENTROPY)).from_buffer_copy(_ENTROPY)
            source = _DataBlob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
            entropy = _DataBlob(len(_ENTROPY), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_ubyte)))
            output, description = _DataBlob(), ctypes.c_void_p()
            try:
                if decrypt:
                    success = unprotect(ctypes.byref(source), ctypes.byref(description),
                        ctypes.byref(entropy), None, None, 0x01, ctypes.byref(output))
                else:
                    # No CRYPTPROTECT_LOCAL_MACHINE: the Windows user is the scope.
                    success = protect(ctypes.byref(source), "6D local provider key",
                        ctypes.byref(entropy), None, None, 0x01, ctypes.byref(output))
                if not success or not output.pbData or not 0 < output.cbData <= MAX_FILE_BYTES:
                    raise CredentialError("credential_decryption_failed" if decrypt else "credential_encryption_failed")
                return ctypes.string_at(output.pbData, output.cbData)
            finally:
                if output.pbData:
                    # Clear the allocated cleartext on decrypt before releasing it.
                    if decrypt and output.cbData <= MAX_FILE_BYTES:
                        ctypes.memset(output.pbData, 0, output.cbData)
                    free(ctypes.cast(output.pbData, ctypes.c_void_p))
                if description.value:
                    free(description)
                ctypes.memset(source_buffer, 0, len(source_buffer))
        except CredentialError:
            raise
        except (AttributeError, OSError, TypeError, ValueError, OverflowError):
            raise CredentialError("credential_decryption_failed" if decrypt else "credential_encryption_failed") from None

    def protect(self, data):
        return self._transform(data, decrypt=False)

    def unprotect(self, data):
        return self._transform(data, decrypt=True)


class CredentialStore:
    def __init__(self, path, *, protection=None):
        self.path = Path(path)
        self.protection = protection if protection is not None else WindowsDPAPI()

    @property
    def supported(self):
        return bool(self.protection.supported)

    def _check_path(self):
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise CredentialError("credential_path_invalid")

    def exists(self):
        try:
            self._check_path()
            return self.path.is_file()
        except (OSError, ValueError):
            raise CredentialError("credential_storage_unavailable") from None

    def save(self, key):
        if not self.supported:
            raise CredentialError("credential_storage_unsupported")
        if not valid_key(key):
            raise CredentialError("credential_data_invalid")
        try:
            envelope = {"schema": _SCHEMA, "key": key,
                        "key_digest": sha256(key.encode("utf-8")).hexdigest()}
            plaintext = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            encrypted = self.protection.protect(plaintext)
            if not isinstance(encrypted, bytes) or not 0 < len(encrypted) <= MAX_FILE_BYTES - len(_MAGIC):
                raise CredentialError("credential_encryption_failed")
            self._check_path()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._check_path()
            temporary_path = None
            try:
                # The temporary file contains ciphertext only.
                with tempfile.NamedTemporaryFile(prefix=".sixd-key-", dir=self.path.parent, delete=False) as stream:
                    temporary_path = Path(stream.name)
                    stream.write(_MAGIC + encrypted)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_path, self.path)
                temporary_path = None
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
        except CredentialError:
            raise
        except (OSError, UnicodeError, TypeError, ValueError):
            raise CredentialError("credential_storage_unavailable") from None

    def load(self):
        if not self.supported:
            raise CredentialError("credential_storage_unsupported")
        try:
            self._check_path()
            with self.path.open("rb") as stream:
                encoded = stream.read(MAX_FILE_BYTES + 1)
            if len(encoded) > MAX_FILE_BYTES or not encoded.startswith(_MAGIC):
                raise CredentialError("credential_data_invalid")
            plaintext = self.protection.unprotect(encoded[len(_MAGIC):])
            if not isinstance(plaintext, bytes) or len(plaintext) > MAX_FILE_BYTES:
                raise CredentialError("credential_data_invalid")
            def unique(pairs):
                value = {}
                for name, item in pairs:
                    if name in value:
                        raise ValueError("Duplicate field.")
                    value[name] = item
                return value
            envelope = json.loads(plaintext.decode("utf-8"), object_pairs_hook=unique)
            if (not isinstance(envelope, dict) or set(envelope) != {"schema", "key", "key_digest"}
                    or envelope["schema"] != _SCHEMA or not valid_key(envelope["key"])
                    or envelope["key_digest"] != sha256(envelope["key"].encode("utf-8")).hexdigest()):
                raise CredentialError("credential_data_invalid")
            return envelope["key"]
        except FileNotFoundError:
            return None
        except CredentialError:
            raise
        except (OSError, UnicodeError, TypeError, ValueError):
            raise CredentialError("credential_storage_unavailable") from None

    def forget(self):
        try:
            self._check_path()
            self.path.unlink(missing_ok=True)
        except CredentialError:
            raise
        except (OSError, ValueError):
            raise CredentialError("credential_storage_unavailable") from None
