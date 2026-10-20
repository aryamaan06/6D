"""Offline recovery checks with isolated SQLite stores and synthetic settings."""
from pathlib import Path
from contextlib import closing
import importlib.util
import json
import shutil
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sixd_backup_local", ROOT / "tools/backup_local.py")
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


class LocalBackupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="local-backup-test-", dir=ROOT / "work")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.local = self.root / "source local"
        self.local.mkdir()
        self.archive = self.root / "snapshot.zip"
        with closing(sqlite3.connect(self.local / "workspace.sqlite3")) as db, db:
            db.execute("CREATE TABLE history (id INTEGER PRIMARY KEY, receipt TEXT)")
            db.executemany("INSERT INTO history VALUES (?,?)", [(1, "original"), (2, "changed")])
        with closing(sqlite3.connect(self.local / "budget.sqlite3")) as db, db:
            db.execute("CREATE TABLE budget (id TEXT PRIMARY KEY,cap REAL,reserved REAL)")
            db.execute("INSERT INTO budget VALUES ('synthetic-approval',29.5,2.30350988)")
            db.execute("CREATE TABLE allowance_changes (value TEXT)")
            db.execute("INSERT INTO allowance_changes VALUES ('preserved prior migration')")
        (self.local / "token-factory.json").write_text(json.dumps({
            "approval_id": "synthetic-approval", "spend_cap_usd": 29.5,
            "base_url": "https://api.tokenfactory.nebius.com/v1/", "model": "nvidia/offline-nemotron",
            "spend_approved": True}), encoding="utf-8")
        (self.local / "project-assistant-model.json").write_text(json.dumps({
            "comparison_id": "0" * 32, "candidate_id": "super"}), encoding="utf-8")
        self.probe = patch.object(backup, "_server_running", return_value=False)
        self.probe.start()
        self.addCleanup(self.probe.stop)

    def create(self):
        return backup.create_backup(self.local, self.archive, confirmed_stopped=True)

    def restore(self, archive=None, destination=None):
        return backup.restore_backup(archive or self.archive, destination or self.root / "restored local", confirmed_stopped=True)

    def mutate(self, transform):
        target = self.root / "modified.zip"
        with zipfile.ZipFile(self.archive) as archive:
            contents = {info.filename: archive.read(info) for info in archive.infolist()}
        transform(contents)
        with zipfile.ZipFile(target, "w") as archive:
            for name, data in contents.items():
                archive.writestr(name, data)
        return target

    def test_complete_bundle_restores_exact_history_settings_selection_and_ledger(self):
        before = {p.name: p.read_bytes() for p in self.local.iterdir() if p.is_file()}
        result = self.create()
        self.assertEqual(result["provider_calls"], 0)
        restored = Path(self.restore()["restored_to"])
        with closing(sqlite3.connect(restored / "workspace.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT * FROM history ORDER BY id").fetchall(), [(1, "original"), (2, "changed")])
        with closing(sqlite3.connect(restored / "budget.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT * FROM budget").fetchall(), [("synthetic-approval", 29.5, 2.30350988)])
            self.assertEqual(db.execute("SELECT * FROM allowance_changes").fetchall(), [("preserved prior migration",)])
        for name in ("token-factory.json", "project-assistant-model.json"):
            self.assertEqual((restored / name).read_bytes(), before[name])
        self.assertEqual({p.name: p.read_bytes() for p in self.local.iterdir() if p.is_file()}, before)

    def test_sqlite_backup_includes_committed_wal_not_only_main_database_file(self):
        connection = sqlite3.connect(self.local / "workspace.sqlite3")
        self.addCleanup(connection.close)
        self.assertEqual(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("INSERT INTO history VALUES (3,'committed in WAL')")
        connection.commit()
        self.assertTrue((self.local / "workspace.sqlite3-wal").is_file())
        self.create()
        restored = Path(self.restore()["restored_to"])
        with closing(sqlite3.connect(restored / "workspace.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT receipt FROM history WHERE id=3").fetchone(), ("committed in WAL",))

    def test_credentials_env_logs_caches_and_nonallowlisted_data_are_excluded(self):
        (self.local / "credentials").mkdir()
        (self.local / "credentials/nebius.dpapi").write_bytes(b"synthetic encrypted bytes")
        for name in (".env", "key.txt", "workspace-server.log", "cache.json"):
            (self.local / name).write_text("synthetic-private-marker", encoding="utf-8")
        self.create()
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(set(archive.namelist()), set(backup.ALLOWLIST) | {"manifest.json"})
            self.assertNotIn(b"synthetic-private-marker", b"".join(archive.read(n) for n in archive.namelist()))
        restored = Path(self.restore()["restored_to"])
        self.assertFalse((restored / "credentials").exists())
        self.assertFalse((restored / ".env").exists())

    def test_workspace_only_unconfigured_snapshot_is_supported(self):
        for name in backup.ALLOWLIST[1:]:
            (self.local / name).unlink()
        self.create()
        self.assertEqual(self.restore()["files"], ["workspace.sqlite3"])

    def test_missing_ledger_or_settings_refuses_without_reset(self):
        for name in ("budget.sqlite3", "token-factory.json"):
            contents = (self.local / name).read_bytes()
            (self.local / name).unlink()
            with self.assertRaises(backup.BackupError):
                self.create()
            self.assertFalse(self.archive.exists())
            (self.local / name).write_bytes(contents)

    def test_mismatched_budget_config_cannot_be_backed_up(self):
        with closing(sqlite3.connect(self.local / "budget.sqlite3")) as db, db:
            db.execute("UPDATE budget SET cap=5")
        with self.assertRaises(backup.BackupError):
            self.create()
        self.assertFalse(self.archive.exists())

    def test_configuration_cannot_smuggle_plaintext_credential_fields(self):
        path = self.local / "token-factory.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["api_key"] = "synthetic-secret-not-a-provider-key"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(backup.BackupError):
            self.create()
        self.assertFalse(self.archive.exists())

    def test_confirmation_and_stopped_port_are_required_for_backup_and_restore(self):
        with self.assertRaises(backup.BackupError):
            backup.create_backup(self.local, self.archive)
        self.create()
        with self.assertRaises(backup.BackupError):
            backup.restore_backup(self.archive, self.root / "new local")
        with patch.object(backup, "_server_running", return_value=True):
            with self.assertRaises(backup.BackupError):
                self.restore()
        self.assertFalse((self.root / "restored local").exists())

    def test_existing_archive_and_restore_directory_are_never_overwritten(self):
        self.create()
        original_archive = self.archive.read_bytes()
        with self.assertRaises(backup.BackupError):
            self.create()
        self.assertEqual(self.archive.read_bytes(), original_archive)
        target = self.root / "existing local"
        target.mkdir()
        (target / "budget.sqlite3").write_bytes(b"existing independent ledger")
        with self.assertRaises(backup.BackupError):
            self.restore(destination=target)
        self.assertEqual((target / "budget.sqlite3").read_bytes(), b"existing independent ledger")

    def test_corrupt_zip_or_wrong_file_digest_restores_nothing(self):
        self.archive.write_bytes(b"not a ZIP")
        with self.assertRaises(backup.BackupError):
            self.restore()
        self.archive.unlink()
        self.create()
        changed = self.mutate(lambda files: files.__setitem__("workspace.sqlite3", b"tampered"))
        with self.assertRaises(backup.BackupError):
            self.restore(changed)
        self.assertFalse((self.root / "restored local").exists())

    def test_concurrent_archive_creation_is_not_removed_by_failure_cleanup(self):
        original_open = Path.open
        target = self.archive
        def concurrent_open(path, mode="r", *args, **kwargs):
            if path == target and mode == "xb":
                with original_open(path, "wb") as stream:
                    stream.write(b"other process archive")
            return original_open(path, mode, *args, **kwargs)
        with patch.object(Path, "open", concurrent_open):
            with self.assertRaises(FileExistsError):
                self.create()
        self.assertEqual(self.archive.read_bytes(), b"other process archive")

    def test_extra_traversal_absolute_and_credential_paths_are_rejected(self):
        self.create()
        for name in ("../escape.txt", "/absolute.txt", "C:/escape.txt", "credentials/nebius.dpapi", ".env"):
            with self.subTest(name=name):
                changed = self.mutate(lambda files: files.__setitem__(name, b"untrusted"))
                with self.assertRaises(backup.BackupError):
                    self.restore(changed)
                self.assertFalse((self.root / "escape.txt").exists())
                changed.unlink()

    def test_duplicate_entries_and_symlinks_are_rejected(self):
        self.create()
        duplicate = self.root / "duplicate.zip"
        shutil.copyfile(self.archive, duplicate)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate, "a") as archive:
                archive.writestr("workspace.sqlite3", b"duplicate")
        with self.assertRaises(backup.BackupError):
            self.restore(duplicate)
        symbolic = self.root / "symbolic.zip"
        with zipfile.ZipFile(self.archive) as old, zipfile.ZipFile(symbolic, "w") as new:
            for info in old.infolist():
                if info.filename == "workspace.sqlite3":
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                new.writestr(info, old.read(info))
        with self.assertRaises(backup.BackupError):
            self.restore(symbolic)

    def test_archive_size_limits_apply_before_extraction(self):
        self.create()
        with patch.object(backup, "MAX_FILE_BYTES", 10):
            with self.assertRaises(backup.BackupError):
                self.restore()
        self.assertFalse((self.root / "restored local").exists())

    def test_manifest_duplicate_json_fields_and_missing_file_are_rejected(self):
        self.create()
        changed = self.mutate(lambda files: files.__setitem__("manifest.json", b'{"schema":"sixd.local-backup.v1","schema":"sixd.local-backup.v1"}'))
        with self.assertRaises(backup.BackupError):
            self.restore(changed)
        changed.unlink()
        changed = self.mutate(lambda files: files.pop("budget.sqlite3"))
        with self.assertRaises(backup.BackupError):
            self.restore(changed)

    def test_invalid_database_does_not_leave_an_archive_or_destination(self):
        (self.local / "workspace.sqlite3").write_bytes(b"not a database")
        with self.assertRaises(backup.BackupError):
            self.create()
        self.assertFalse(self.archive.exists())

    def test_stalled_snapshot_aborts_without_creating_an_archive(self):
        with patch.object(backup.time, "monotonic", side_effect=[0, 16]):
            with self.assertRaises(backup.BackupError):
                self.create()
        self.assertFalse(self.archive.exists())


if __name__ == "__main__":
    unittest.main()
