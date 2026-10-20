"""Bounded multi-revision probes for targeted/full recalculation equivalence.

Each history uses an isolated SQLite database.  The full path deliberately
uses the maintained calculators, but does not use workspace reuse or impact
selection.  This checks orchestration and retained evidence, not physics.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sixd import engineering, lifecycle
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _records(store):
    with store._connect() as connection:
        return {table: [dict(row) for row in connection.execute("SELECT * FROM " + table)]
                for table in ("projects", "revisions", "runs")}


def _preserved(store, before):
    after = _records(store)
    for table, rows in before.items():
        for row in rows:
            if row not in after[table]:
                raise AssertionError("Historical " + table + " row changed or disappeared")


def _check(view, *, executed, reused):
    """Compare exact evidence serialization, including fingerprints and signs."""
    project = lifecycle.validate_project(deepcopy(view["project"]))
    fresh = lifecycle.review_project(project, engineering.evaluate_models(project))
    receipt = view["run"]
    if _encode(receipt["review"]) != _encode(fresh):
        raise AssertionError("Targeted/full reviews differ at revision " + str(view["revision"]))
    lifecycle.verify_review(receipt["review"])
    if set(receipt["executed_model_ids"]) != set(executed):
        raise AssertionError("Unexpected executed model set: " + repr(receipt["executed_model_ids"]))
    if set(receipt["reused_model_ids"]) != set(reused):
        raise AssertionError("Unexpected reused model set: " + repr(receipt["reused_model_ids"]))
    if set(executed) & set(reused) or set(executed) | set(reused) != {m["id"] for m in project["models"]}:
        raise AssertionError("Execution and reuse do not partition current models")
    if receipt["live_model_calls"] != 0:
        raise AssertionError("History probe unexpectedly reports a live model call")
    return {"revision": view["revision"], "review_digest": fresh["digest"],
            "executed_model_ids": receipt["executed_model_ids"],
            "reused_model_ids": receipt["reused_model_ids"]}


def _save_run(store, project, base_revision, old_rows):
    identity = project["project_id"]
    saved = store.save_revision(identity, base_revision, project)
    if saved["run"] is not None:
        raise AssertionError("Saving a revision unexpectedly ran a calculation")
    _preserved(store, old_rows)
    view = store.run(identity, base_revision + 1)
    _preserved(store, old_rows)
    return view


def _repeated(store, initial):
    models = {m["id"] for m in initial["project"]["models"]}
    checks = [_check(initial, executed=models, reused=[])]
    before = _records(store)
    repeated = store.run(initial["project_id"], 1)
    checks.append(_check(repeated, executed=[], reused=models))
    _preserved(store, before)
    if repeated["run"]["run_id"] == initial["run"]["run_id"]:
        raise AssertionError("A repeated run did not get a distinct execution identity")
    for identity in models:
        origin = deepcopy(initial["run"]["model_origins"][identity])
        origin["disposition"] = "reused"
        if repeated["run"]["model_origins"][identity] != origin:
            raise AssertionError("Repeated execution lost its original calculation identity")
    return checks


def _revert(store, initial):
    models = {m["id"] for m in initial["project"]["models"]}
    checks = [_check(initial, executed=models, reused=[])]
    changed = deepcopy(initial["project"])
    changed["inputs"]["heat_input"]["value"] = 700
    second = _save_run(store, changed, 1, _records(store))
    checks.append(_check(second, executed=["thermal"], reused=models - {"thermal"}))
    reverted = deepcopy(initial["project"])
    third = _save_run(store, reverted, 2, _records(store))
    checks.append(_check(third, executed=["thermal"], reused=models - {"thermal"}))
    if third["run"]["model_results"]["thermal"] != initial["run"]["model_results"]["thermal"]:
        raise AssertionError("Reverting the supplied thermal inputs changed its computed result")
    if third["run"]["model_origins"]["thermal"]["revision"] != 3:
        raise AssertionError("Reverted result was misattributed to an older execution")
    return checks


def _unrun(store, initial):
    models = {m["id"] for m in initial["project"]["models"]}
    checks = [_check(initial, executed=models, reused=[])]
    changed = deepcopy(initial["project"])
    changed["inputs"]["heat_input"]["value"] = 700
    before = _records(store)
    pending = store.save_revision(initial["project_id"], 1, changed)
    if pending["run"] is not None or pending["prior_run"]["revision"] != 1:
        raise AssertionError("Unrun revision did not retain the reviewed ancestor")
    changed = deepcopy(pending["project"])
    changed["inputs"]["maximum_burn_duration"]["value"] = 1
    third = _save_run(store, changed, 2, before)
    checks.append(_check(third, executed=["thermal"], reused=models - {"thermal"}))
    if third["run"]["review"]["findings"]["burn_duration"]["status"] != "not_met":
        raise AssertionError("Reused propulsion result was not reassessed against the new limit")
    if store.get(initial["project_id"], 2)["run"] is not None:
        raise AssertionError("Later calculation fabricated a run for the skipped revision")
    return checks


def _rewire(store, initial):
    """A -> B -> A load source, then a stale former source and invalid source."""
    checks = [_check(initial, executed=["aero", "beam", "thermal"], reused=[])]
    project = deepcopy(initial["project"])
    source = deepcopy(next(m for m in project["models"] if m["id"] == "aero"))
    source["id"] = "alternate_aero"
    project["inputs"]["alternate_speed"] = {"value": 20, "unit": "m/s", "source": "Constructed alternate condition"}
    source["inputs"]["relative_speed"] = "alternate_speed"
    project["models"].append(source)
    beam = next(m for m in project["models"] if m["id"] == "beam")
    beam["links"]["tip_force"]["model_id"] = source["id"]
    beam["links"]["tip_force"]["rationale"] = "Constructed history remaps the declared transverse tip load to the alternate drag condition."
    second = _save_run(store, project, 1, _records(store))
    checks.append(_check(second, executed=["alternate_aero", "beam"], reused=["aero", "thermal"]))
    if second["run"]["model_results"]["beam"]["calculation_inputs"]["values"]["tip_force"]["value"] != 80:
        raise AssertionError("Rewired beam did not consume the alternate source")
    project = deepcopy(second["project"])
    beam = next(m for m in project["models"] if m["id"] == "beam")
    beam["links"] = deepcopy(next(m for m in initial["project"]["models"] if m["id"] == "beam")["links"])
    third = _save_run(store, project, 2, _records(store))
    checks.append(_check(third, executed=["beam"], reused=["aero", "alternate_aero", "thermal"]))
    project = deepcopy(third["project"])
    project["inputs"]["alternate_speed"]["value"] = 30
    fourth = _save_run(store, project, 3, _records(store))
    checks.append(_check(fourth, executed=["alternate_aero"], reused=["aero", "beam", "thermal"]))
    if fourth["run"]["model_origins"]["beam"]["revision"] != 3:
        raise AssertionError("Editing a former source lost the beam's valid retained origin")
    project = deepcopy(fourth["project"])
    project["inputs"]["relative_speed"]["value"] = -1
    fifth = _save_run(store, project, 4, _records(store))
    checks.append(_check(fifth, executed=["aero", "beam"], reused=["alternate_aero", "thermal"]))
    result = fifth["run"]["model_results"]["beam"]
    if result["status"] != "not_assessed" or result["metrics"]:
        raise AssertionError("An invalid replacement source left a stale beam verdict")
    return checks


HISTORIES = {
    "repeated_same_revision": ("baseline", _repeated),
    "revert_after_reviewed_edit": ("baseline", _revert),
    "unrun_intervening_revision": ("baseline", _unrun),
    "chain_rewiring_multistep": ("chain_review", _rewire),
}


def check_history(name: str, directory: Path) -> dict:
    """Run one named history or raise on any discrepancy; retain no founder data."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    fixture_name, operation = HISTORIES[name]
    with tempfile.TemporaryDirectory(prefix="history-" + name + "-", dir=directory) as temporary:
        path = Path(temporary) / "workspace.sqlite3"
        store = WorkspaceStore(path)
        project = example_projects()[fixture_name]
        store.create_project(project)
        initial = store.run(project["project_id"], 1)
        baseline = _records(store)
        checks = operation(store, initial)
        _preserved(store, baseline)
        view = store.get(project["project_id"])
        if WorkspaceStore(path).get(project["project_id"]) != view:
            raise AssertionError("Reopening the workspace changed its retained evidence")
    return {"id": name, "family": "multi_revision_history", "status": "passed",
            "outcome": "equivalent", "compared_runs": len(checks),
            "history_preserved": True, "run_checks": checks}


def run_history_checks(directory: Path) -> list[dict]:
    return [check_history(name, directory) for name in HISTORIES]
