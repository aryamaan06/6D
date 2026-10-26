"""Explicit offline Tavily allowance increase; run only with 6D stopped.

Preserves all search receipts and the remembered key. Makes no search request.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.service_credentials import ServiceCredentialStore, MAX_TAVILY_CREDITS


def update_search_allowance(local, new_cap, authorization, *, credential_store=None):
    if (type(new_cap) is not int or not 1 <= new_cap <= MAX_TAVILY_CREDITS
            or not isinstance(authorization, str) or not 1 <= len(authorization.strip()) <= 500):
        raise ValueError('An explicit authorization and bounded integer allowance are required.')
    local = Path(local)
    credentials = credential_store if credential_store is not None else ServiceCredentialStore(
        local / 'credentials' / 'tavily.dpapi', service='tavily')
    saved = credentials.load()
    if saved is None:
        raise ValueError('A remembered Tavily connection is required; connect privately in Owner settings first.')
    old_cap = saved['settings']['credit_limit']
    with closing(sqlite3.connect((local / 'workspace.sqlite3').resolve().as_uri() + '?mode=ro', uri=True)) as db:
        reserved = db.execute('SELECT COUNT(*) FROM project_research_versions WHERE version=1').fetchone()[0]
    if not new_cap > old_cap or new_cap < reserved or new_cap - reserved > 4124:
        raise ValueError('Retain prior reservations and leave no more than the approved 4124 future credits.')
    credentials.save(saved['key'], {'credit_limit': new_cap})
    restored = credentials.load()
    if restored != {'key': saved['key'], 'settings': {'credit_limit': new_cap}}:
        raise ValueError('The updated protected settings could not be verified.')
    return {'old_cap_credits': old_cap, 'cap_credits': new_cap, 'reserved_credits': reserved,
        'remaining_credits': new_cap - reserved, 'authorization': authorization,
        'key_preserved': True, 'search_calls_made': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cap', type=int, required=True)
    parser.add_argument('--authorization', required=True)
    args = parser.parse_args()
    print(json.dumps(update_search_allowance(ROOT / '.local', args.cap, args.authorization), indent=2))
