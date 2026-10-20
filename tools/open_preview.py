"""Start or open the connected 6D workspace at its stable local address.

The filename is retained for existing Windows shortcuts. Starting or opening
the workspace makes no provider call; investigations require an explicit start.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
if sys.version_info < (3, 10):
    print("6D needs Python 3.10 or newer. Run Setup-6D.cmd after installing Python.", file=sys.stderr)
    raise SystemExit(1)
sys.path.insert(0, str(ROOT / "src"))
from sixd.workspace_server import HOST, PORT, SERVICE, SERVER_VERSION, WORKSPACE_ID, RUNTIME_ID, serve

ADDRESS = f"http://{HOST}:{PORT}/"


def inspect_address():
    """Identify this checkout without treating another service as safe to stop."""
    try:
        opener = build_opener(ProxyHandler({}))
        # Windows loopback refusal can take longer than one second even when
        # no process is listening. A shorter timeout misclassifies a free port
        # as an unresponsive foreign service and prevents first startup.
        with opener.open(ADDRESS + "health", timeout=5) as response:
            value = json.loads(response.read(4096))
        if (isinstance(value, dict) and value.get("service") == SERVICE
                and value.get("workspace") == WORKSPACE_ID
                and value.get("server_version") == SERVER_VERSION):
            ready = value.get("runtime_id") == RUNTIME_ID and not value.get("restart_required")
            return ("ready" if ready else "stale"), value
        return "foreign", None
    except HTTPError:
        return "foreign", None
    except (TimeoutError, socket.timeout):
        return "unresponsive", None
    except URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            return "unresponsive", None
        return "closed", None
    except ValueError:
        return "foreign", None
    except OSError:
        return "closed", None


def health():
    state, value = inspect_address()
    return value if state == "ready" else None


def stop_workspace():
    state, _ = inspect_address()
    if state == "closed":
        print("6D is already stopped.")
        return 0
    if state not in {"ready", "stale"}:
        raise RuntimeError("This address is occupied by another application or checkout. No process was stopped.")
    opener = build_opener(ProxyHandler({}))
    request = Request(ADDRESS + "api/shutdown", data=b"{}",
                      headers={"Origin": ADDRESS.rstrip("/"), "Content-Type": "application/json"})
    try:
        with opener.open(request, timeout=5) as response:
            result = json.loads(response.read(4096))
    except HTTPError as error:
        if error.code == 409:
            raise RuntimeError("6D has an active job. Wait for it to finish, then run Stop-6D.cmd again.") from None
        raise RuntimeError("This 6D build cannot stop through the guarded endpoint. No process was killed; close its own server or restart Windows.") from None
    if result != {"stopping": True}:
        raise RuntimeError("6D did not confirm shutdown. No operating-system process was killed.")
    for _ in range(60):
        if inspect_address()[0] == "closed":
            print("6D stopped. Saved projects and evidence remain on disk.")
            return 0
        time.sleep(0.1)
    raise RuntimeError("6D accepted shutdown but the address is still occupied. Check the server before backing up.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="Run the local workspace server in the foreground.")
    parser.add_argument("--no-browser", action="store_true", help="Start/check 6D without opening a browser.")
    parser.add_argument("--check", action="store_true", help="Check this Python and checkout without opening or starting the server.")
    parser.add_argument("--stop", action="store_true", help="Stop only this checkout's server through its guarded local endpoint.")
    args = parser.parse_args(argv)
    if args.check:
        print(json.dumps({"mode": "startup_check", "python": sys.executable,
                          "python_version": sys.version.split()[0], "root": str(ROOT),
                          "address": ADDRESS, "provider_calls": 0}))
        return 0
    if args.stop:
        return stop_workspace()
    if args.serve:
        serve()
        return 0
    state, ready = inspect_address()
    if state == "stale":
        raise RuntimeError("An older 6D process from this checkout is still running. Run Stop-6D.cmd, then Open-6D.cmd. No process was stopped automatically.")
    if state != "ready" and state != "closed":
        raise RuntimeError("The local address is occupied or not responding. Close the other application or 6D checkout before starting this one. No process was stopped.")
    if state == "closed":
        log_path = ROOT / ".local" / "startup.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        options = {"cwd": str(ROOT), "stdin": subprocess.DEVNULL}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            options["start_new_session"] = True
        with log_path.open("ab") as log:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--serve"],
                                     stdout=log, stderr=log, **options)
        for _ in range(100):
            ready = health()
            if ready:
                break
            if child.poll() is not None:
                raise RuntimeError(f"6D could not start at {ADDRESS} Inspect {log_path}. No other process was stopped.")
            time.sleep(0.1)
        else:
            raise RuntimeError(f"6D did not become ready at {ADDRESS} Inspect {log_path} before trying again.")
    print(f"6D workspace ready: {ADDRESS}")
    print(f"Build: {ready['build_id']} | Calculations: local | AI investigations: on explicit request after private connection")
    if not args.no_browser:
        webbrowser.open(ADDRESS, new=2)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"6D: {error}", file=sys.stderr)
        raise SystemExit(1)
