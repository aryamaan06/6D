"""Reproducible differential check of targeted versus full project evaluation.

Uses isolated SQLite stores. The full oracle bypasses workspace reuse/impact
selection but intentionally uses the same maintained engineering calculators.
This verifies orchestration equivalence, not independent physical correctness.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from sixd import engineering, lifecycle
from sixd.workspace import WorkspaceError, WorkspaceStore


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True)


def digest(value):
    return sha256(encode(value).encode()).hexdigest()


def differences(expected, actual, path="$", limit=12):
    """Show exact differing paths; preserve both numerical and evidence fields."""
    found = []
    def walk(a, b, p):
        if len(found) >= limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b)):
                if key not in a or key not in b:
                    found.append({"path": p + "." + key, "expected": a.get(key, "<absent>"), "actual": b.get(key, "<absent>")})
                else:
                    walk(a[key], b[key], p + "." + key)
                if len(found) >= limit:
                    break
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                found.append({"path": p + ".length", "expected": len(a), "actual": len(b)})
            for i, (left, right) in enumerate(zip(a, b)):
                walk(left, right, p + f"[{i}]")
                if len(found) >= limit:
                    break
        elif a != b:
            found.append({"path": p, "expected": a, "actual": b})
    walk(expected, actual, path)
    return found


def full_review(saved_snapshot):
    """No WorkspaceStore, reuse-key, or impact helper in this reference path."""
    project = lifecycle.validate_project(deepcopy(saved_snapshot))
    calculated = engineering.evaluate_models(project)
    if set(calculated) != {m["id"] for m in project["models"]}:
        raise AssertionError("Full calculation omitted a model")
    return lifecycle.review_project(project, calculated)


def database_identity(store):
    with store._connect() as connection:
        return {table: connection.execute("SELECT count(*) FROM " + table).fetchone()[0]
                for table in ("projects", "revisions", "runs")}


def check_case(case: dict[str, Any], directory: Path):
    """Return a complete result or raise a descriptive discrepancy."""
    started = time.perf_counter()
    row = {key: deepcopy(case[key]) for key in ("id", "family", "operation", "expected_valid", "detail")}
    row.update(before_digest=digest(case["before"]), after_digest=digest(case["after"]))
    lifecycle.validate_project(case["before"])
    # Classify before invoking the workspace. A generator expectation is not a
    # reason to hide a surprising contract acceptance/rejection.
    try:
        lifecycle.validate_project(case["after"])
        structurally_valid, validation_error = True, None
    except (ValueError, TypeError, OverflowError) as error:
        structurally_valid, validation_error = False, str(error)
    if structurally_valid != case["expected_valid"]:
        raise AssertionError(f"Generator contract expectation disagrees: valid={structurally_valid}; {validation_error}")
    with tempfile.TemporaryDirectory(prefix="case-", dir=directory) as temporary:
        path = Path(temporary) / "workspace.sqlite3"
        store = WorkspaceStore(path)
        initial = store.create_project(case["before"])
        identity = initial["project_id"]
        baseline = store.run(identity, 1)
        baseline_digest = digest(baseline)
        prior = baseline["run"]
        lifecycle.verify_review(prior["review"])
        before_counts = database_identity(store)
        if not structurally_valid:
            failures = {}
            for name, action in (("preview", store.preview_change), ("save", store.save_revision)):
                try:
                    action(identity, 1, deepcopy(case["after"]))
                except WorkspaceError as error:
                    failures[name] = str(error)
                else:
                    raise AssertionError("Workspace accepted structurally invalid " + name)
            if database_identity(store) != before_counts or digest(store.get(identity, 1)) != baseline_digest:
                raise AssertionError("Rejected edit changed saved project records")
            row.update(outcome="rejected_consistently", validation_error=validation_error, workspace_errors=failures,
                       executed_model_ids=[], reused_model_ids=[], model_statuses={}, requirement_statuses={})
        else:
            impact = store.preview_change(identity, 1, deepcopy(case["after"]))
            saved = store.save_revision(identity, 1, deepcopy(case["after"]))
            if saved["run"] is not None:
                raise AssertionError("Saving a revision unexpectedly ran calculations")
            targeted = store.run(identity, 2)
            actual = targeted["run"]
            expected = full_review(targeted["project"])
            delta = differences(expected, actual["review"])
            if delta or encode(expected) != encode(actual["review"]):
                raise AssertionError("Targeted/full engineering reviews differ: " + encode(delta))
            if not lifecycle.verify_review(expected) or not lifecycle.verify_review(actual["review"]):
                raise AssertionError("Review did not verify")
            models = {m["id"] for m in targeted["project"]["models"]}
            executed, reused = actual["executed_model_ids"], actual["reused_model_ids"]
            if len(executed) != len(set(executed)) or len(reused) != len(set(reused)) or set(executed) & set(reused) or set(executed) | set(reused) != models:
                raise AssertionError("Executed/reused model IDs do not partition current models")
            for model_id in executed:
                origin = actual["model_origins"][model_id]
                if origin != {"run_id": actual["run_id"], "revision": 2, "disposition": "executed"}:
                    raise AssertionError("Incorrect executed origin for " + model_id)
            for model_id in reused:
                origin = deepcopy(prior["model_origins"][model_id]); origin["disposition"] = "reused"
                if actual["model_origins"][model_id] != origin or actual["model_results"][model_id] != prior["model_results"][model_id]:
                    raise AssertionError("Reused result/origin changed for " + model_id)
            if digest(store.get(identity, 1)["run"]) != digest(prior) or store.get(identity, 1)["project"] != baseline["project"]:
                raise AssertionError("Historical project or run changed")
            if WorkspaceStore(path).get(identity, 2) != targeted:
                raise AssertionError("Reopened receipt differs from saved current state")
            row.update(outcome="equivalent", review_digest=expected["digest"],
                       executed_model_ids=executed, reused_model_ids=reused,
                       model_statuses={key: result["status"] for key, result in actual["model_results"].items()},
                       requirement_statuses={key: finding["status"] for key, finding in expected["findings"].items()},
                       affected_model_ids=impact["affected_model_ids"])
    row["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    return row


def sources():
    files = sorted((ROOT / "src/sixd").glob("*.py")) + sorted((ROOT / "examples").glob("*.project.json")) + [Path(__file__), ROOT / "tools/recalculation_cases.py", ROOT / "tools/recalculation_histories.py"]
    return {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path.read_bytes()).hexdigest() for path in files}


def run_benchmark(seed=20261019, count=1000, output=None, progress=True):
    from recalculation_cases import build_cases
    if count < 1 or count > 10000:
        raise ValueError("Case count must be between 1 and 10000")
    directory = Path(output or ROOT / "artifacts/recalculation-verification" / f"seed-{seed}-cases-{count}").resolve()
    private_root = (ROOT / ".local").resolve()
    if directory == ROOT or directory == private_root or private_root in directory.parents:
        raise ValueError("Benchmark output cannot be production storage or the repository root")
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source_before = sources()
    outcomes, families, operations, statuses, findings, records, failures = Counter(), Counter(), Counter(), Counter(), Counter(), [], []
    executed_count = reused_count = 0
    ledger = directory / "cases.jsonl"
    with tempfile.TemporaryDirectory(prefix="recalculation-benchmark-", dir=ROOT / "work") as temporary, ledger.open("w", encoding="utf-8") as handle:
        for index, case in enumerate(build_cases(seed=seed, count=count)):
            if index >= count:
                raise ValueError("Generator returned more cases than requested")
            families[case["family"]] += 1; operations[case["operation"]] += 1
            try:
                record = check_case(case, Path(temporary))
            except Exception as error:
                record = {key: deepcopy(case[key]) for key in ("id", "family", "operation", "expected_valid", "detail")}
                record.update(outcome="failed", error_type=type(error).__name__, error=str(error))
                counterexample = directory / ("counterexample-" + str(index).zfill(5) + ".json")
                counterexample.write_text(json.dumps({"case": case, "failure": record}, indent=2, allow_nan=False) + "\n", encoding="utf-8")
                record["counterexample"] = counterexample.name
                failures.append(record)
            outcomes[record["outcome"]] += 1
            statuses.update(record.get("model_statuses", {}).values())
            findings.update(record.get("requirement_statuses", {}).values())
            executed_count += len(record.get("executed_model_ids", [])); reused_count += len(record.get("reused_model_ids", []))
            records.append(record); handle.write(encode(record) + "\n"); handle.flush()
            if progress and ((index + 1) % 50 == 0 or index + 1 == count):
                print(f"Verified {index + 1}/{count}; discrepancies {len(failures)}; elapsed {time.perf_counter()-started:.1f}s", flush=True)
    if len(records) != count:
        raise ValueError("Generator returned fewer cases than requested")
    from recalculation_histories import run_history_checks
    with tempfile.TemporaryDirectory(prefix="recalculation-histories-", dir=ROOT / "work") as temporary:
        histories = run_history_checks(Path(temporary))
    source_after = sources()
    report = {"schema": "sixd.recalculation-verification.v1", "created_at": datetime.now(timezone.utc).isoformat(),
              "seed": seed, "requested_cases": count, "completed_cases": len(records), "passed": not failures and source_before == source_after,
              "outcomes": dict(outcomes), "families": dict(families), "operations": dict(operations),
              "model_statuses": dict(statuses), "requirement_statuses": dict(findings), "histories": histories,
              "executed_model_count": executed_count, "reused_model_count": reused_count,
              "elapsed_seconds": round(time.perf_counter() - started, 3), "failures": failures,
              "python": platform.python_version(), "sources": source_before, "sources_unchanged": source_before == source_after,
              "ledger_sha256": sha256(ledger.read_bytes()).hexdigest(), "paid_model_calls": 0,
              "comparison": "Exact canonical JSON equality of the complete lifecycle review; workspace execution histories checked separately.",
              "limitations": ["Same maintained physics calculators in both paths; no independent physical validation.",
                              "Seeded finite generated edit distribution; not all configurations or histories.",
                              "No AI, hosting, security, user-study or mission-readiness validation."]}
    report["digest"] = digest(report)
    (directory / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261019)
    parser.add_argument("--cases", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    os.environ.pop("NEBIUS_API_KEY", None)
    report = run_benchmark(arguments.seed, arguments.cases, arguments.output)
    print(json.dumps({key: report[key] for key in ("passed", "seed", "completed_cases", "outcomes", "elapsed_seconds", "digest", "paid_model_calls")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
