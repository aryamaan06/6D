"""Back up stopped 6D data and restore only into a new local-data directory.

SQLite snapshots include committed WAL records. This does not snapshot source
code or remembered credentials. Stop every process using the source directory
before backup; never use a backup to reset the shared spending ledger.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import socket
import sqlite3
import stat
import sys
import tempfile
import time
import zipfile


SCHEMA = "sixd.local-backup.v1"
ALLOWLIST = ("workspace.sqlite3", "budget.sqlite3", "token-factory.json", "project-assistant-model.json")
CONFIG_FIELDS = {
    "token-factory.json": {"base_url", "model", "approval_id", "spend_cap_usd",
        "input_usd_per_million_ceiling", "output_usd_per_million_ceiling", "max_output_tokens",
        "request_timeout_seconds", "inference_profile", "selection_protocol", "account_verified",
        "model_license_reviewed", "spend_approved"},
    "project-assistant-model.json": {"comparison_id", "candidate_id"},
}
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
ROOT = Path(__file__).resolve().parents[1]


class BackupError(ValueError):
    """Controlled backup error without file contents or credential values."""


def _json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BackupError("Duplicate JSON fields are not accepted.")
            result[key] = value
        return result
    def nonfinite(_):
        raise BackupError("Nonfinite JSON values are not accepted.")
    try:
        return json.loads(data, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, UnicodeError, TypeError):
        raise BackupError("Backup JSON is invalid.") from None


def _server_running():
    try:
        with socket.create_connection(("127.0.0.1", 8768), timeout=.3):
            return True
    except OSError:
        return False


def _require_stopped(confirmed_stopped):
    if confirmed_stopped is not True:
        raise BackupError("Stop 6D and other processes using these databases, then pass --confirmed-stopped.")
    if _server_running():
        raise BackupError("Port 8768 is still in use. Stop 6D before backing up or restoring; no process was stopped automatically.")


def _regular(path, limit=MAX_FILE_BYTES):
    # Explicit filenames do not follow symbolic links/reparse points.
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    if (path.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            or (hasattr(path, "is_junction") and path.is_junction())):
        raise BackupError("Linked backup files or directories are not accepted.")
    if not path.is_file():
        raise BackupError("A required local data file is unavailable.")
    if path.stat().st_size > limit:
        raise BackupError("A local file exceeds the supported backup size.")


def _validate_config(name, data):
    value = _json(data)
    if not isinstance(value, dict) or set(value) - CONFIG_FIELDS[name]:
        raise BackupError("A local configuration contains unsupported fields; credentials must not be placed in configuration files.")
    # Unknown/nested fields are disallowed rather than silently dropping data.
    if any(isinstance(item, (dict, list)) for item in value.values()):
        raise BackupError("Nested configuration values are not supported in backups.")
    if name == "token-factory.json":
        if not {"approval_id", "spend_cap_usd"}.issubset(value):
            raise BackupError("Provider allowance configuration is incomplete.")
        if (not isinstance(value["approval_id"], str) or not value["approval_id"]
                or type(value["spend_cap_usd"]) not in (int, float)
                or not math.isfinite(value["spend_cap_usd"]) or value["spend_cap_usd"] <= 0):
            raise BackupError("Provider allowance configuration is invalid.")
    elif set(value) != CONFIG_FIELDS[name]:
        raise BackupError("The project model selection is incomplete.")
    return value


def _snapshot(source, destination):
    _regular(source)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as reader:
            with closing(sqlite3.connect(destination)) as writer:
                started = time.monotonic()
                def progress(status, remaining, total):
                    if time.monotonic() - started > 15:
                        raise BackupError("A database snapshot did not finish promptly; confirm all database users are stopped.")
                reader.backup(writer, pages=256, progress=progress, sleep=.05)
                if writer.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise BackupError("A database snapshot failed its integrity check.")
    except sqlite3.Error:
        raise BackupError("A database could not be safely snapshotted.") from None
    _regular(destination)


def _validate_bundle(folder, names):
    if "workspace.sqlite3" not in names:
        raise BackupError("A backup must contain the project database.")
    if ("budget.sqlite3" in names) != ("token-factory.json" in names):
        raise BackupError("Provider settings and the spending ledger must be backed up and restored together.")
    if "project-assistant-model.json" in names and "token-factory.json" not in names:
        raise BackupError("A model selection requires its provider configuration and ledger.")
    configs = {name: _validate_config(name, (folder / name).read_bytes())
               for name in names if name in CONFIG_FIELDS}
    for name in (n for n in names if n.endswith(".sqlite3")):
        try:
            with closing(sqlite3.connect((folder / name).resolve().as_uri() + "?mode=ro", uri=True)) as db:
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise BackupError("A backup database failed its integrity check.")
                if name == "budget.sqlite3":
                    rows = db.execute("SELECT id,cap,reserved FROM budget").fetchall()
                    cfg = configs["token-factory.json"]
                    if (len(rows) != 1 or rows[0][0] != cfg["approval_id"]
                            or rows[0][1] != cfg["spend_cap_usd"]
                            or type(rows[0][1]) not in (int, float) or not math.isfinite(rows[0][1])
                            or type(rows[0][2]) not in (int, float) or not math.isfinite(rows[0][2])
                            or not 0 <= rows[0][2] <= rows[0][1]):
                        raise BackupError("The allowance configuration and preserved ledger do not agree.")
        except sqlite3.Error:
            raise BackupError("A backup database is invalid or its ledger is unavailable.") from None


def create_backup(source, output, *, confirmed_stopped=False):
    _require_stopped(confirmed_stopped)
    source, output = Path(source), Path(output).absolute()
    if (not source.is_dir() or source.is_symlink()
            or getattr(source.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            or (hasattr(source, "is_junction") and source.is_junction())):
        raise BackupError("Choose the existing .local directory as the backup source.")
    source = source.resolve()
    if output.exists() or output.is_symlink():
        raise BackupError("The output archive already exists; choose a new filename.")
    if not output.parent.is_dir():
        raise BackupError("Create the backup destination folder first.")
    names = [name for name in ALLOWLIST if (source / name).exists() or (source / name).is_symlink()]
    if "workspace.sqlite3" not in names:
        raise BackupError("The project database is missing.")
    with tempfile.TemporaryDirectory(prefix=".sixd-backup-", dir=output.parent) as temporary:
        folder = Path(temporary)
        for name in names:
            path = source / name
            _regular(path)
            if name.endswith(".sqlite3"):
                _snapshot(path, folder / name)
            else:
                _validate_config(name, path.read_bytes())
                shutil.copyfile(path, folder / name)
        _validate_bundle(folder, names)
        entries = [{"path": name, "bytes": (folder / name).stat().st_size,
                    "sha256": sha256((folder / name).read_bytes()).hexdigest()} for name in names]
        if sum(entry["bytes"] for entry in entries) > MAX_TOTAL_BYTES:
            raise BackupError("The backup exceeds the supported total size.")
        manifest = {"schema": SCHEMA, "created_at": datetime.now(timezone.utc).isoformat(),
                    "files": entries, "credentials_included": False,
                    "consistency": "Stopped-app SQLite snapshots; all database users must have been stopped.",
                    "ledger_policy": "Restore the complete bundle; never reset or split the spending ledger."}
        # Exclusive creation is outside the cleanup block: if another process
        # creates the chosen path first, its file must never be deleted.
        stream = output.open("xb")
        try:
            with stream, zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, indent=2, allow_nan=False))
                for name in names:
                    archive.write(folder / name, name)
        except Exception:
            if output.exists():
                output.unlink()
            raise
    return {"archive": str(output), "files": names, "credentials_included": False,
            "provider_calls": 0}


def restore_backup(archive_path, destination, *, confirmed_stopped=False):
    _require_stopped(confirmed_stopped)
    archive_path, destination = Path(archive_path), Path(destination).absolute()
    _regular(archive_path, MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES + 16384)
    if destination.exists() or destination.is_symlink():
        raise BackupError("Restore requires a new directory; existing .local data is never overwritten.")
    if not destination.parent.is_dir():
        raise BackupError("Create the new checkout folder before restoring its .local data.")
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if (len(names) != len(set(names)) or "manifest.json" not in names
                    or set(names) - set(ALLOWLIST) - {"manifest.json"}
                    or len(names) > len(ALLOWLIST) + 1):
                raise BackupError("The archive contains unsupported, duplicate or unsafe paths.")
            for info in infos:
                if (info.is_dir() or stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1
                        or info.file_size > (MAX_MANIFEST_BYTES if info.filename == "manifest.json" else MAX_FILE_BYTES)
                        or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise BackupError("The archive has unsupported entries or exceeds size limits.")
            if sum(info.file_size for info in infos) > MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES:
                raise BackupError("The archive exceeds the supported total size.")
            manifest = _json(archive.read("manifest.json"))
            if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA
                    or manifest.get("credentials_included") is not False
                    or not isinstance(manifest.get("files"), list)
                    or len(manifest["files"]) != len(names) - 1):
                raise BackupError("The backup manifest is invalid.")
            expected = {}
            for entry in manifest["files"]:
                if (not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}
                        or entry["path"] not in ALLOWLIST or entry["path"] in expected
                        or type(entry["bytes"]) is not int or not 0 <= entry["bytes"] <= MAX_FILE_BYTES
                        or not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64):
                    raise BackupError("The backup manifest file list is invalid.")
                expected[entry["path"]] = entry
            if set(expected) != set(names) - {"manifest.json"}:
                raise BackupError("The archive and manifest do not match.")
            with tempfile.TemporaryDirectory(prefix=".sixd-restore-", dir=destination.parent) as temporary:
                folder = Path(temporary)
                for name, entry in expected.items():
                    info = archive.getinfo(name)
                    if info.file_size != entry["bytes"]:
                        raise BackupError("An archived file size does not match the manifest.")
                    digest, count = sha256(), 0
                    with archive.open(info) as reader, (folder / name).open("xb") as writer:
                        while chunk := reader.read(1024 * 1024):
                            count += len(chunk)
                            if count > entry["bytes"]:
                                raise BackupError("An archived file exceeded its declared size.")
                            digest.update(chunk)
                            writer.write(chunk)
                    if count != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                        raise BackupError("An archived file failed its digest check.")
                _validate_bundle(folder, set(expected))
                # rename() refuses an existing destination on Windows; recheck
                # explicitly on all platforms before the final directory move.
                if destination.exists() or destination.is_symlink():
                    raise BackupError("The restore destination appeared; no existing data was replaced.")
                folder.rename(destination)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, EOFError, OSError):
        raise BackupError("The backup archive could not be safely read or restored.") from None
    return {"restored_to": str(destination), "files": sorted(expected),
            "credentials_restored": False, "provider_calls": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="Create a private stopped-app local-data archive.")
    backup.add_argument("--source", type=Path, default=ROOT / ".local")
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--confirmed-stopped", action="store_true")
    restore = commands.add_parser("restore", help="Restore into a new .local directory only.")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--to", type=Path, required=True)
    restore.add_argument("--confirmed-stopped", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = (create_backup(args.source, args.output, confirmed_stopped=args.confirmed_stopped)
                  if args.command == "backup" else
                  restore_backup(args.archive, args.to, confirmed_stopped=args.confirmed_stopped))
    except (BackupError, OSError, sqlite3.Error):
        # BackupError contains controlled text, ordinary I/O exceptions may
        # include private source paths, database contents or key names.
        error = sys.exc_info()[1]
        print("6D backup: " + (str(error) if isinstance(error, BackupError) else "Local files could not be accessed safely."), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
