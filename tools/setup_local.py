"""Prepare a source checkout using installed Python, with no package downloads."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
MINIMUM = (3, 10)
REQUIRED_FILES = (
    "src/sixd/workspace_server.py", "src/sixd/web/workspace.html",
    "design/vendor/lucide.min.js", "tools/open_preview.py",
)


def check_source(root):
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        raise RuntimeError("This checkout is incomplete. Restore the missing project files: " + ", ".join(missing))


def prepare(root=ROOT, *, check_only=False):
    if sys.version_info < MINIMUM:
        raise RuntimeError("Install Python 3.10 or newer, then run Setup-6D.cmd again.")
    root = Path(root).resolve()
    check_source(root)
    environment = root / ".venv"
    target = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if check_only:
        return {"mode": "check_only", "python": sys.executable,
                "python_version": sys.version.split()[0], "root": str(root),
                "environment_present": target.is_file(), "downloads": 0, "provider_calls": 0}
    created = False
    if not environment.exists():
        # Running from src requires no pip or runtime package installation.
        venv.EnvBuilder(with_pip=False).create(environment)
        created = True
    if not target.is_file():
        raise RuntimeError("The existing .venv is incomplete. Rename it, then run Setup-6D.cmd again. No existing environment was removed.")
    try:
        result = subprocess.run([str(target), "-c",
            "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"],
            capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("The project Python environment cannot run. Rename .venv and run Setup-6D.cmd again.") from error
    if result.returncode:
        raise RuntimeError("The project Python environment requires Python 3.10 or newer. Rename .venv and run Setup-6D.cmd again.")
    return {"mode": "source_environment_ready", "python": str(target), "root": str(root),
            "created": created, "downloads": 0, "provider_calls": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check Python and source files without creating anything.")
    args = parser.parse_args(argv)
    result = prepare(check_only=args.check)
    print(json.dumps(result))
    if not args.check:
        print("6D setup is ready. Open Open-6D.cmd to start the local application.")
        print("Calculations use the included source. AI calls require a private connection and an explicit action.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print("6D setup: " + str(error), file=sys.stderr)
        raise SystemExit(1)
