"""Start or open the connected 6D workspace at its stable local address.

The filename is retained for existing Windows shortcuts. Starting or opening
the workspace makes no provider call; investigations require an explicit start.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.workspace_server import HOST, PORT, SERVICE, SERVER_VERSION, WORKSPACE_ID, RUNTIME_ID, serve

ADDRESS = f"http://{HOST}:{PORT}/"


def health():
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(ADDRESS + "health", timeout=1) as response:
            value = json.loads(response.read(4096))
        if (isinstance(value, dict) and value.get("service") == SERVICE
                and value.get("workspace") == WORKSPACE_ID
                and value.get("server_version") == SERVER_VERSION
                and value.get("runtime_id") == RUNTIME_ID
                and not value.get("restart_required")):
            return value
    except (OSError, URLError, ValueError):
        pass
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="Run the local workspace server in the foreground.")
    parser.add_argument("--no-browser", action="store_true", help="Start/check 6D without opening a browser.")
    args = parser.parse_args()
    if args.serve:
        serve()
        return 0
    ready = health()
    if not ready:
        options = {"cwd": str(ROOT), "stdin": subprocess.DEVNULL,
                   "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            options["start_new_session"] = True
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--serve"], **options)
        for _ in range(60):
            ready = health()
            if ready:
                break
            if child.poll() is not None:
                raise RuntimeError(f"6D could not start at {ADDRESS} Another application or an older 6D server may occupy this address.")
            time.sleep(0.1)
        else:
            raise RuntimeError(f"6D did not become ready at {ADDRESS}")
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
