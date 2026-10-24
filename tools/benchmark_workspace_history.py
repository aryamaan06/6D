"""Measure constructed orbital histories in isolated before/after subprocesses.

Run ``python tools/benchmark_workspace_history.py`` for both phases, or preserve
the immutable before phase with ``--phase before`` and later run ``--phase after``.
Before-only staging and partial checkpoints stay in ignored artifacts; the public
output is written only after a complete paired comparison.
No application databases, credentials, providers or network services are used.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import platform
import sqlite3
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
BASELINE = "c76d0b6b109a2567201573b21bea4cf2be9922fa"
SCHEMA = "sixd.workspace-history-performance.v1"


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return sha256(encode(value)).hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")


def summary(samples):
    values = [sample["seconds"] for sample in samples]
    return {"samples": samples, "sample_count": len(samples),
            "median_seconds": statistics.median(values),
            "minimum_seconds": min(values), "maximum_seconds": max(values),
            "total_seconds": sum(values),
            "verify_review_calls": sum(s["verify_review_calls"] for s in samples),
            "receipt_decode_calls": sum(s["receipt_decode_calls"] for s in samples)}


def source_manifest(source):
    return {str(p.relative_to(source)).replace("\\", "/"): sha256(p.read_bytes()).hexdigest()
            for p in sorted((source / "src").rglob("*.py"))}


def snapshot_baseline(destination):
    # Git supplies the immutable source tree, never an import of active code.
    archive = subprocess.check_output(["git", "archive", BASELINE, "src"], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as files:
        for member in files.getmembers():
            relative = Path(member.name)
            if relative.is_absolute() or ".." in relative.parts or member.issym() or member.islnk():
                raise ValueError("Unexpected archived source path")
            if member.isfile():
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(files.extractfile(member).read())
    manifest = source_manifest(destination)
    return {"kind": "immutable_git_archive", "commit": BASELINE,
            "raw_source_manifest_digest": digest(manifest),
            "executed_source_manifest_digest": digest(manifest),
            "raw_workspace_sha256": manifest["src/sixd/workspace.py"],
            "executed_workspace_sha256": manifest["src/sixd/workspace.py"],
            "crlf_normalized_files": [], "source_file_count": len(manifest)}


def snapshot_candidate(source, destination):
    before = source_manifest(source)
    normalized = []
    for relative in before:
        data = (source / relative).read_bytes()
        clean = data.replace(b"\r\n", b"\n")
        if clean != data:
            normalized.append(relative)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(clean)
    if source_manifest(source) != before:
        raise RuntimeError("Candidate sources changed while being copied; rerun after edits finish")
    executed = source_manifest(destination)
    return {"kind": "copied_candidate_source", "raw_source_manifest_digest": digest(before),
            "executed_source_manifest_digest": digest(executed),
            "raw_workspace_sha256": before["src/sixd/workspace.py"],
            "executed_workspace_sha256": executed["src/sixd/workspace.py"],
            "crlf_normalized_files": normalized, "source_file_count": len(before),
            "raw_source_hashes": before,
            "normalization": "CRLF -> LF in isolated candidate copy only; active source is untouched"}


def worker(args):
    # This process imports exactly one source tree. Both phases use this runner.
    sys.path.insert(0, str(args.source_root / "src"))
    from sixd import lifecycle, workspace
    from sixd.project_examples import example_projects

    loaded = Path(workspace.__file__).resolve()
    if args.source_root.resolve() not in loaded.parents:
        raise RuntimeError("Worker imported a different workspace source tree")
    source_before = source_manifest(args.source_root)
    verification_sources = lifecycle._verification_sources()
    counters = {"verify_review": 0, "receipt_decode": 0}
    original_verify = lifecycle.verify_review
    original_receipt = workspace.WorkspaceStore._receipt

    def counted_verify(*values, **options):
        counters["verify_review"] += 1
        return original_verify(*values, **options)

    def counted_receipt(*values, **options):
        counters["receipt_decode"] += 1
        return original_receipt(*values, **options)

    lifecycle.verify_review = counted_verify
    workspace.WorkspaceStore._receipt = counted_receipt
    # Fixed identity/time removes nondeterminism from complete view comparisons.
    # No model, validation, review, caching or storage logic is replaced.
    identity = 0

    def next_uuid():
        nonlocal identity
        identity += 1
        return uuid.UUID(int=identity)

    workspace.uuid4 = next_uuid
    workspace._now = lambda: "2026-10-24T00:00:00.000000+00:00"
    records = []

    def measure(operation, action):
        verify_before, receipts_before = counters["verify_review"], counters["receipt_decode"]
        start = time.perf_counter()
        view = action()
        elapsed = time.perf_counter() - start
        # Serialization and digest calculation are deliberately outside timing.
        payload = encode(view)
        run = view.get("run")
        sample = {"operation": operation, "revision": view["revision"],
                  "seconds": elapsed, "verify_review_calls": counters["verify_review"] - verify_before,
                  "receipt_decode_calls": counters["receipt_decode"] - receipts_before,
                  "compact_json_payload_bytes": len(payload),
                  "canonical_view_sha256": sha256(payload).hexdigest(),
                  "review_digest": run["review"]["digest"] if run else None,
                  "evidence_fingerprints": {k: v["fingerprint"] for k, v in run["review"]["evidence"].items()} if run else {},
                  "executed_model_ids": run["executed_model_ids"] if run else [],
                  "reused_model_ids": run["reused_model_ids"] if run else []}
        records.append(sample)
        return view, sample

    with tempfile.TemporaryDirectory(prefix="constructed-history-", dir=args.work_directory) as temporary:
        db_path = Path(temporary) / "history.sqlite3"
        store = workspace.WorkspaceStore(db_path)
        project = deepcopy(example_projects()["orbital_review"])
        project["inputs"]["steps"]["value"] = args.steps
        project["name"] = "Constructed orbital history performance probe"
        project_id = project["project_id"]
        fixture_digest = digest(project)
        view, created = measure("create", lambda: store.create_project(project))
        checkpoints = []
        run_samples, save_samples = [], []
        for revision in range(1, max(args.counts) + 1):
            if revision > 1:
                changed = deepcopy(view["project"])
                # Vary only independent thermal input: orbit state/grid stay fixed.
                changed["inputs"]["heat_input"]["value"] = 500 + 10 * (revision - 1)
                view, sample = measure("save", lambda: store.save_revision(project_id, revision - 1, changed))
                save_samples.append(sample)
            view, sample = measure("run", lambda: store.run(project_id, revision))
            run_samples.append(sample)
            if revision not in args.counts:
                continue
            warm, cold = [], []
            for _ in range(args.warm_reads):
                current, sample = measure("warm_get", lambda: store.get(project_id))
                warm.append(sample)
                if current != view:
                    raise AssertionError("Warm read changed the returned view")
            for _ in range(args.cold_reads):
                current, sample = measure("new_store_get", lambda: workspace.WorkspaceStore(db_path).get(project_id))
                cold.append(sample)
                if current != view:
                    raise AssertionError("New-store read changed the returned view")
            # Validate every retained record with the original verifier, outside
            # measured reads. This is an internal consistency check, not physics.
            with closing(sqlite3.connect(db_path)) as connection:
                rows = connection.execute("SELECT receipt FROM runs ORDER BY sequence").fetchall()
                revision_count = connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
            for (receipt,) in rows:
                original_verify(json.loads(receipt)["review"])
            checkpoints.append({"revision_count": revision_count, "run_count": len(rows),
                                "warm_get": summary(warm), "new_store_get": summary(cold),
                                "save": summary(save_samples), "run": summary(run_samples),
                                "latest_save": save_samples[-1], "latest_run": run_samples[-1],
                                "all_stored_reviews_verified": True,
                                "database_file_bytes": db_path.stat().st_size})
            # Preserve every complete checkpoint outside the disposable source/
            # database tree. A later cleanup error cannot discard measurements.
            if args.checkpoint_output:
                write_json(args.checkpoint_output,
                           {"schema": SCHEMA + ".checkpoints", "status": "partial",
                            "label": args.label, "started_at": args.started_at,
                            "steps": args.steps, "warm_reads": args.warm_reads,
                            "cold_reads": args.cold_reads, "fixture_sha256": fixture_digest,
                            "executed_source_manifest_digest": digest(source_before),
                            "checkpoints": checkpoints})
            print(f"{args.label}: {revision} revisions/runs measured", file=sys.stderr, flush=True)
        if source_manifest(args.source_root) != source_before:
            raise RuntimeError("Worker sources changed during measurement")
    return {"label": args.label, "started_at": args.started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "fixture_sha256": fixture_digest, "verification_sources": verification_sources,
            "executed_source_manifest_digest": digest(source_before),
            "sources_unchanged_during_measurement": True, "create": created,
            "checkpoints": checkpoints,
            "operation_sequence_sha256": digest([{k: v for k, v in row.items()
                                                       if k not in {"seconds", "verify_review_calls", "receipt_decode_calls"}}
                                                    for row in records]),
            "environment": {"python": sys.version, "python_implementation": platform.python_implementation(),
                            "platform": platform.platform(), "machine": platform.machine(),
                            "processor": platform.processor(), "logical_cpu_count": os.cpu_count(),
                            "sqlite_version": sqlite3.sqlite_version,
                            "perf_counter_resolution_seconds": time.get_clock_info("perf_counter").resolution},
            "paid_model_calls": 0, "network_calls": 0, "application_database_access": False}


def compare(before, after):
    same_sources = before["verification_sources"] == after["verification_sources"]
    rows = []
    for old, new in zip(before["checkpoints"], after["checkpoints"], strict=True):
        if old["revision_count"] != new["revision_count"]:
            raise ValueError("History checkpoints differ")
        row = {"revision_count": old["revision_count"], "operations": {}}
        for operation in ("warm_get", "new_store_get", "save", "run"):
            left, right = old[operation], new[operation]
            row["operations"][operation] = {
                "before_median_seconds": left["median_seconds"], "after_median_seconds": right["median_seconds"],
                "measured_speedup_ratio": left["median_seconds"] / right["median_seconds"],
                "before_verify_review_calls": left["verify_review_calls"],
                "after_verify_review_calls": right["verify_review_calls"],
                "before_receipt_decode_calls": left["receipt_decode_calls"],
                "after_receipt_decode_calls": right["receipt_decode_calls"],
                "canonical_returned_views_equal": [s["canonical_view_sha256"] for s in left["samples"]]
                                                  == [s["canonical_view_sha256"] for s in right["samples"]],
                "before_compact_json_payload_bytes": left["samples"][-1]["compact_json_payload_bytes"],
                "after_compact_json_payload_bytes": right["samples"][-1]["compact_json_payload_bytes"]}
        rows.append(row)
    exact = before["operation_sequence_sha256"] == after["operation_sequence_sha256"]
    structural = (all(new["warm_get"]["verify_review_calls"] <= old["warm_get"]["verify_review_calls"]
                      and new["new_store_get"]["verify_review_calls"] <= old["new_store_get"]["verify_review_calls"]
                      for old, new in zip(before["checkpoints"], after["checkpoints"], strict=True))
                  and after["checkpoints"][-1]["warm_get"]["verify_review_calls"]
                  < before["checkpoints"][-1]["warm_get"]["verify_review_calls"])
    return {"executed_verification_source_hashes_equal": same_sources,
            "raw_verification_source_hashes_equal": before["source_provenance"].get("raw_verification_sources", before["verification_sources"])
                                                   == after["source_provenance"].get("raw_verification_sources", after["verification_sources"]),
            "fixture_sha256_equal": before["fixture_sha256"] == after["fixture_sha256"],
            "complete_canonical_operation_sequence_equal": exact,
            "comparison_applicable": same_sources and before["fixture_sha256"] == after["fixture_sha256"],
            "structural_read_verification_reduction_passed": structural,
            "timing_threshold_assertions": False, "checkpoints": rows,
            "passed": same_sources and exact and structural}


def launch(args, label, destination):
    snapshot = destination / "source"
    snapshot.mkdir(parents=True)
    provenance = snapshot_baseline(snapshot) if label == "before" else snapshot_candidate(args.source_root, snapshot)
    output = destination / "worker.json"
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--label", label,
               "--source-root", str(snapshot), "--work-directory", str(destination),
               "--counts", ",".join(map(str, args.counts)), "--steps", str(args.steps),
               "--warm-reads", str(args.warm_reads), "--cold-reads", str(args.cold_reads),
               "--checkpoint-output", str(ROOT / "artifacts/workspace-history-benchmark" / (label + "-checkpoints.json")),
               "--output", str(output)]
    subprocess.run(command, check=True, cwd=destination)
    result = json.loads(output.read_text(encoding="utf-8"))
    if result["executed_source_manifest_digest"] != provenance["executed_source_manifest_digest"]:
        raise AssertionError("Executed source does not match snapshot provenance")
    raw_sources = provenance.pop("raw_source_hashes", None)
    provenance["raw_verification_sources"] = ({name: raw_sources["src/sixd/" + name]
                                               for name in result["verification_sources"]}
                                              if raw_sources is not None else result["verification_sources"])
    result["source_provenance"] = provenance
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "after", "both"), default="both")
    parser.add_argument("--source-root", type=Path, default=ROOT,
                        help="Candidate project root; copied to an isolated LF-normalized source snapshot")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/HISTORY_PERFORMANCE_RESULTS.json")
    parser.add_argument("--counts", default="2,7,13")
    parser.add_argument("--steps", type=int, default=512)
    parser.add_argument("--warm-reads", type=int, default=2)
    parser.add_argument("--cold-reads", type=int, default=2)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--label", default="worker", help=argparse.SUPPRESS)
    parser.add_argument("--work-directory", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--checkpoint-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.counts = sorted(set(int(value) for value in args.counts.split(",")))
    if not args.counts or args.counts[0] < 2 or args.steps < 1 or min(args.warm_reads, args.cold_reads) < 2:
        parser.error("Use histories >=2 revisions, positive steps, and at least two reads per mode")
    args.started_at = datetime.now(timezone.utc).isoformat()
    if args.worker:
        write_json(args.output, worker(args))
        return 0
    work_root = ROOT / "artifacts/workspace-history-benchmark"
    work_root.mkdir(parents=True, exist_ok=True)
    preserved_before = work_root / "preserved-before.json"
    settings = {"counts": args.counts, "steps": args.steps, "warm_reads": args.warm_reads, "cold_reads": args.cold_reads,
                "history": "One growing isolated SQLite history; one run per revision; independent heat input = 500 + 10*(revision-1) after revision 1",
                "baseline_commit": BASELINE}
    if args.phase == "after":
        report = json.loads(preserved_before.read_text(encoding="utf-8"))
        if report.get("schema") != SCHEMA or report["settings"] != settings:
            raise ValueError("Preserved before report uses different benchmark settings")
    else:
        report = {"schema": SCHEMA, "settings": settings,
                  "reproduction": ["tools/run_python.cmd tools/benchmark_workspace_history.py --phase before",
                                   "tools/run_python.cmd tools/benchmark_workspace_history.py --phase after",
                                   "Or run both consecutively: tools/run_python.cmd tools/benchmark_workspace_history.py"],
                  "method": {"timed_scope": "Public store method only; new-store mode includes constructor; excludes JSON serialization, digest collection and explicit post-checkpoint verification",
                             "warm_read": "Same WorkspaceStore instance already used to build this history",
                             "new_store_read": "New WorkspaceStore instance for every read in same child process; OS/filesystem caches not flushed",
                             "save_run_summary": "Cumulative one sample per revision up to each checkpoint; latest_save/latest_run are also retained",
                             "identity_control": "Same fixed _now() and sequential UUID(int=n) in both subprocesses; no other workspace/model logic replaced",
                             "source_control": "Immutable git-archive baseline with matching kernels; current copied source with CRLF normalized to LF; active source never swapped",
                             "payload": "Complete public returned view as sorted compact ensure_ascii JSON UTF-8 bytes; transport/gzip costs excluded",
                             "verification_counts": "Instrument lifecycle.verify_review and WorkspaceStore._receipt equally in both source subprocesses",
                             "run_order": "Before phase precedes after; no process import crossover; same Python executable; no CPU affinity or load control"},
                  "limitations": ["Finite constructed local history and this machine only; elapsed timing is descriptive and has no pass threshold.",
                                  "New-store reads are cold for application object caches only; they are not cold-process or cold-disk measurements.",
                                  "Review verification checks internal evidence consistency; it does not recompute or prove orbital physics.",
                                  "The retained orbital grid is fixed by settings.steps; no mission accuracy, hardware or production scale claim follows.",
                                  "Database/payload size and serialization costs remain visible and can grow; paid model, network and multi-user server latency are excluded.",
                                  "Fixed clock/UUID and instrumentation add the same small overhead to each phase; other offline tests may run on this shared machine, which is not dedicated idle hardware.",
                                  "This fixed 512-step default is a bounded scaling probe; it does not reproduce another reviewer's unknown orbital resolution or wall-clock timings."]}
    # Keep disposable constructed data in the repository's ignored artifact
    # directory; some managed Windows runtimes cannot create nested system-temp
    # directories. TemporaryDirectory removes only its own new child directory.
    with tempfile.TemporaryDirectory(prefix="sixd-history-benchmark-", dir=work_root) as temporary:
        root = Path(temporary)
        if args.phase in ("before", "both"):
            report["before"] = launch(args, "before", root / "before")
            report["before_preservation_sha256"] = digest(report["before"])
            write_json(preserved_before, report)
        if args.phase in ("after", "both"):
            if digest(report["before"]) != report["before_preservation_sha256"]:
                raise ValueError("Preserved before results were modified")
            report["after"] = launch(args, "after", root / "after")
            report["comparison"] = compare(report["before"], report["after"])
            report["before_preserved_unchanged"] = digest(report["before"]) == report["before_preservation_sha256"]
            write_json(args.output, report)
    print(json.dumps({"output": str(preserved_before if args.phase == "before" else args.output), "phase": args.phase,
                      "comparison_passed": report.get("comparison", {}).get("passed")}))
    return 0 if "comparison" not in report or report["comparison"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
