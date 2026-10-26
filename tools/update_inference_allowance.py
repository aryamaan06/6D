"""Apply an explicit local allowance increase, retaining prior reservations.

This operator tool makes no provider request. Inference/HTTP handlers never
invoke it. A failed config replacement leaves a visible ledger/config mismatch
which blocks inference until the operator repairs it; it cannot reset usage.
"""
import argparse
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.providers import BudgetLedger, LiveConfig, ProviderError
from sixd.workspace_ai import MAX_APPROVED_ALLOWANCE_USD


def update_allowance(local, new_cap, authorization):
    local = Path(local)
    path = local / "token-factory.json"
    config = LiveConfig.load(path)
    if type(new_cap) not in (int, float) or not math.isfinite(new_cap) or not config.spend_cap_usd < new_cap <= MAX_APPROVED_ALLOWANCE_USD:
        raise ProviderError("Choose an increase within the explicitly approved cumulative cap.", code="configuration_error")
    with closing(sqlite3.connect((local / 'budget.sqlite3').resolve().as_uri() + '?mode=ro', uri=True)) as db:
        rows = db.execute('SELECT id,cap,reserved FROM budget').fetchall()
    if len(rows) != 1 or new_cap - rows[0][2] > 58.25 + 1e-12:
        raise ProviderError("The increase must leave at most the approved USD58.25 available; prior reservations must remain.", code="configuration_error")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["spend_cap_usd"] = new_cap
    staged = local / "token-factory.allowance-staged.json"
    # Stage and validate before touching the ledger. No credentials are added.
    with staged.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")
    LiveConfig.load(staged)
    try:
        result = BudgetLedger(local / "budget.sqlite3").increase_cap(config, new_cap,
            approved_maximum=MAX_APPROVED_ALLOWANCE_USD, authorization=authorization)
    except Exception:
        staged.unlink()
        raise
    staged.replace(path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cap", type=float, required=True)
    parser.add_argument("--authorization", required=True)
    args = parser.parse_args()
    print(json.dumps(update_allowance(ROOT / ".local", args.cap, args.authorization), indent=2))
