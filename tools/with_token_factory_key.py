"""Enter a key locally for one CLI invocation; no key file or paid default action."""
from getpass import getpass, GetPassWarning
from pathlib import Path
import os
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    if not sys.stdin.isatty():
        print('Run this helper in your own interactive terminal. Do not put a key in command arguments.')
        return 2
    args = sys.argv[1:] or ['provider-status']
    # This helper supplies a credential, never spending authorization.
    # Existing account/model/license/budget gates still apply to live commands.
    if args[0] not in ('provider-status', 'investigate'):
        print('Use provider-status or investigate with this local helper.')
        return 2
    from sixd.cli import main as sixd_main
    previous = os.environ.pop('NEBIUS_API_KEY', None)
    try:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', GetPassWarning)
                key = getpass('Token Factory key (hidden, local only): ').strip()
        except (EOFError, KeyboardInterrupt, GetPassWarning):
            print('\nSecure key entry unavailable or cancelled. No request was sent.')
            return 2
        if not key or any(ch.isspace() for ch in key):
            print('A single nonempty key is required. No request was sent.')
            return 2
        os.environ['NEBIUS_API_KEY'] = key
        key = None
        return sixd_main(args)
    except KeyboardInterrupt:
        print('\nCommand interrupted. Any previous live request retains its budget reservation.')
        return 2
    finally:
        os.environ.pop('NEBIUS_API_KEY', None)
        if previous is not None:
            os.environ['NEBIUS_API_KEY'] = previous


if __name__ == '__main__':
    raise SystemExit(main())
