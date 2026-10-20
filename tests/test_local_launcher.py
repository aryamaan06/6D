"""Offline installation and guarded startup checks in isolated source copies."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


setup = module("sixd_setup_local_test", "setup_local.py")
launcher = module("sixd_open_preview_test", "open_preview.py")


class Reply:
    def __init__(self, value):
        self.value = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _):
        return self.value


class LocalSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="launcher unit ", dir=ROOT / "work")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in setup.REQUIRED_FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture", encoding="utf-8")

    def test_check_only_checks_source_without_creating_data_or_environment(self):
        result = setup.prepare(self.root, check_only=True)
        self.assertEqual(result["downloads"], 0)
        self.assertEqual(result["provider_calls"], 0)
        self.assertFalse((self.root / ".venv").exists())
        self.assertFalse((self.root / ".local").exists())

    def test_unsupported_python_rejected_before_environment_creation(self):
        with patch.object(setup.sys, "version_info", (3, 9)):
            with self.assertRaisesRegex(RuntimeError, "3.10"):
                setup.prepare(self.root)
        self.assertFalse((self.root / ".venv").exists())

    def test_incomplete_checkout_rejected_without_partial_install(self):
        (self.root / setup.REQUIRED_FILES[0]).unlink()
        with self.assertRaisesRegex(RuntimeError, "checkout is incomplete"):
            setup.prepare(self.root)
        self.assertFalse((self.root / ".venv").exists())

    def test_existing_environment_is_not_removed_or_reinstalled(self):
        target = self.root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        target.parent.mkdir(parents=True)
        target.write_bytes(b"preserved environment placeholder")
        with patch.object(setup.venv, "EnvBuilder") as builder, patch.object(setup.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
            result = setup.prepare(self.root)
        self.assertFalse(result["created"])
        builder.assert_not_called()
        self.assertEqual(target.read_bytes(), b"preserved environment placeholder")

    def test_partial_environment_is_preserved_and_reports_recovery(self):
        environment = self.root / ".venv"
        environment.mkdir()
        (environment / "keep.txt").write_text("preserved")
        with self.assertRaisesRegex(RuntimeError, "existing .venv is incomplete"):
            setup.prepare(self.root)
        self.assertEqual((environment / "keep.txt").read_text(), "preserved")


class GuardedStartupTests(unittest.TestCase):
    def health(self, **changes):
        result = {"service": launcher.SERVICE, "server_version": launcher.SERVER_VERSION,
                  "workspace": launcher.WORKSPACE_ID, "runtime_id": launcher.RUNTIME_ID,
                  "restart_required": False, "build_id": "offline-check"}
        result.update(changes)
        return result

    def test_only_matching_checkout_runtime_is_ready(self):
        cases = [(self.health(), "ready"), (self.health(workspace="another-checkout"), "foreign"),
                 (self.health(service="other-service"), "foreign"),
                 (self.health(runtime_id="earlier-runtime"), "stale"),
                 (self.health(restart_required=True), "stale")]
        for value, expected in cases:
            with self.subTest(state=expected):
                with patch.object(launcher, "build_opener", return_value=SimpleNamespace(open=lambda *a, **k: Reply(value))):
                    self.assertEqual(launcher.inspect_address()[0], expected)

    def test_actual_free_loopback_port_is_closed_not_a_foreign_timeout(self):
        # Reserve then release a local ephemeral port. This never probes or
        # starts the founder's fixed-address server.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        with patch.object(launcher, "ADDRESS", f"http://127.0.0.1:{port}/"):
            self.assertEqual(launcher.inspect_address(), ("closed", None))

    def test_check_mode_never_probes_starts_or_opens_browser(self):
        with patch.object(launcher, "inspect_address") as probe, patch.object(launcher.subprocess, "Popen") as process, patch.object(launcher.webbrowser, "open") as browser:
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(launcher.main(["--check"]), 0)
        self.assertEqual(json.loads(output.getvalue())["provider_calls"], 0)
        probe.assert_not_called(); process.assert_not_called(); browser.assert_not_called()

    def test_ready_server_reused_without_another_process_or_browser(self):
        with patch.object(launcher, "inspect_address", return_value=("ready", self.health())), patch.object(launcher.subprocess, "Popen") as process, patch.object(launcher.webbrowser, "open") as browser:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.main(["--no-browser"]), 0)
        process.assert_not_called(); browser.assert_not_called()

    def test_foreign_and_stale_server_are_not_replaced_or_killed(self):
        for state in ("foreign", "stale", "unresponsive"):
            with self.subTest(state=state), patch.object(launcher, "inspect_address", return_value=(state, None)), patch.object(launcher.subprocess, "Popen") as process:
                with self.assertRaises(RuntimeError):
                    launcher.main(["--no-browser"])
                process.assert_not_called()

    def test_child_failure_is_logged_locally_with_no_browser(self):
        with tempfile.TemporaryDirectory(prefix="launcher failure ", dir=ROOT / "work") as temporary:
            folder = Path(temporary)
            with patch.object(launcher, "ROOT", folder), patch.object(launcher, "inspect_address", return_value=("closed", None)), patch.object(launcher.subprocess, "Popen", return_value=SimpleNamespace(poll=lambda: 1)) as process, patch.object(launcher.webbrowser, "open") as browser:
                with self.assertRaisesRegex(RuntimeError, "startup.log"):
                    launcher.main(["--no-browser"])
            self.assertTrue((folder / ".local/startup.log").is_file())
            self.assertEqual(process.call_args.kwargs["stdout"].name, str(folder / ".local/startup.log"))
            self.assertIs(process.call_args.kwargs["stdout"], process.call_args.kwargs["stderr"])
            browser.assert_not_called()

    def test_stop_foreign_server_does_not_send_shutdown(self):
        with patch.object(launcher, "inspect_address", return_value=("foreign", None)), patch.object(launcher, "build_opener") as opener:
            with self.assertRaisesRegex(RuntimeError, "No process was stopped"):
                launcher.stop_workspace()
        opener.assert_not_called()

    def test_stop_active_job_gives_actionable_message_without_killing_process(self):
        error = HTTPError(launcher.ADDRESS, 409, "conflict", {}, None)
        with patch.object(launcher, "inspect_address", return_value=("ready", self.health())), patch.object(launcher, "build_opener", return_value=SimpleNamespace(open=lambda *a, **k: (_ for _ in ()).throw(error))):
            with self.assertRaisesRegex(RuntimeError, "active job"):
                launcher.stop_workspace()

    def test_stop_own_stale_server_uses_same_origin_guard_and_waits_for_close(self):
        sent = []
        def respond(request, **_):
            sent.append(request)
            return Reply({"stopping": True})
        with patch.object(launcher, "inspect_address", side_effect=[("stale", self.health()), ("closed", None)]), patch.object(launcher, "build_opener", return_value=SimpleNamespace(open=respond)):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.stop_workspace(), 0)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].get_method(), "POST")
        self.assertEqual(sent[0].get_header("Origin"), launcher.ADDRESS.rstrip("/"))
        self.assertEqual(sent[0].data, b"{}")


@unittest.skipUnless(os.name == "nt", "Native Windows launcher checks.")
class NativeLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="portable launch with spaces ", dir=ROOT / "work")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        for folder in ("src", "design"):
            shutil.copytree(ROOT / folder, cls.root / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (cls.root / "tools").mkdir()
        for name in ("run_python.cmd", "open_preview.py", "setup_local.py"):
            shutil.copyfile(ROOT / "tools" / name, cls.root / "tools" / name)
        for name in ("Open-6D.cmd", "Setup-6D.cmd", "Stop-6D.cmd"):
            shutil.copyfile(ROOT / name, cls.root / name)
        candidates = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python").glob("Python3*/python.exe"), reverse=True)
        if "codex" not in str(Path(sys.executable)).casefold():
            candidates.insert(0, Path(sys.executable))
        cls.installed = next((p for p in candidates if "codex" not in str(p).casefold()), None)
        if cls.installed is None:
            raise unittest.SkipTest("No independent installed Python was found for native verification.")

    def command(self, name, *args, override=True):
        environment = os.environ.copy()
        environment.pop("NEBIUS_API_KEY", None)
        environment.pop("SIXD_PYTHON", None)
        if override:
            environment["SIXD_PYTHON"] = str(self.installed)
        result = subprocess.run([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(self.root / name), *args],
                                env=environment, cwd=self.root, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(next(line for line in result.stdout.splitlines() if line.startswith("{")))

    def test_explicit_installed_python_is_honored_in_space_path_without_server(self):
        result = self.command("Open-6D.cmd", "--check")
        self.assertEqual(Path(result["python"]).resolve(), self.installed.resolve())
        self.assertEqual(Path(result["root"]), self.root)
        self.assertFalse((self.root / ".local").exists())

    def test_installed_fallback_works_without_override_or_project_environment(self):
        result = self.command("Open-6D.cmd", "--check", override=False)
        self.assertNotIn("codex", result["python"].casefold())
        self.assertEqual(result["provider_calls"], 0)
        self.assertFalse((self.root / ".venv").exists())
        self.assertFalse((self.root / ".local").exists())

    def test_setup_creates_offline_environment_once_and_launcher_prefers_it(self):
        result = self.command("Setup-6D.cmd")
        self.assertEqual(result["mode"], "source_environment_ready")
        self.assertEqual(result["downloads"], 0)
        again = self.command("Setup-6D.cmd")
        self.assertFalse(again["created"])
        opened = self.command("Open-6D.cmd", "--check", override=False)
        self.assertEqual(Path(opened["python"]).resolve(), (self.root / ".venv/Scripts/python.exe").resolve())
        self.assertFalse((self.root / ".local").exists())


if __name__ == "__main__":
    unittest.main()
