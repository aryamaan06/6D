"""Local, append-only project revisions and deterministic execution receipts.

The SQLite file is application-owned storage. Imports supply strict project
records, never model results or executable code. Reuse is allowed only for an
identical model, its complete input records, adapter version and verifier source
hashes. Requirement limits are always evaluated against the selected revision.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3
from uuid import uuid4

from . import lifecycle
from .engineering import MODEL_VERSIONS, evaluate_models, evaluate_model
from . import chains
from .project_examples import example_projects


class WorkspaceError(ValueError):
    """Invalid project, missing workspace record or inconsistent stored data."""


class ConflictError(WorkspaceError):
    """The project changed after the editing session's base revision."""


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return sha256(_encode(value).encode("utf-8")).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _sources():
    return lifecycle._verification_sources()


# This process keeps imported calculators in memory. Hashing files immediately
# before execution alone could falsely attribute old loaded code to new files.
# Require a restart after verifier edits rather than silently relabelling it.
_LOADED_VERIFICATION_SOURCES = _sources()
_LOADED_ADAPTER_VERSIONS = deepcopy(MODEL_VERSIONS)


def _require_current_runtime():
    sources = _sources()
    if (sources != _LOADED_VERIFICATION_SOURCES
            or MODEL_VERSIONS != _LOADED_ADAPTER_VERSIONS):
        raise WorkspaceError("Verification code changed after this application started. "
                             "Restart 6D before running checks; historical evidence remains available.")
    return sources


def _revision(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise WorkspaceError("Revision must be a positive integer.")
    return value


def _snapshot(project, revision):
    # Validate the incoming record before canonicalizing its revision metadata.
    try:
        result = lifecycle.validate_project(project, allow_empty=True)
        result["revision"] = str(revision)
        return lifecycle.validate_project(result, allow_empty=True)
    except (ValueError, TypeError, OverflowError) as exc:
        raise WorkspaceError(str(exc)) from exc


def _model_key(project, model, sources, versions):
    if model.get("links"):
        configuration = chains.dependency_configuration(project, model["id"])
        return _digest({"calculation_dependencies": configuration,
                        "adapter_versions": {item["type"]: versions.get(item["type"]) for item in configuration["models"].values()},
                        "verification_sources": sources})
    inputs = {}
    for key in sorted(set(model["inputs"].values())):
        record = deepcopy(project["inputs"][key])
        # A browser JSON roundtrip serializes integral floats as integers.
        # Use exact rational values for reuse only: 70e9 and 70000000000 are
        # the same input, while unequal representable numbers stay unequal.
        # Project/review evidence retains its original serialization and digest.
        numerator, denominator = record["value"].as_integer_ratio()
        negative_zero = record["value"] == 0 and math.copysign(1, record["value"]) < 0
        record["value"] = {"numerator": numerator, "denominator": denominator}
        # IEEE signed zero compares equal numerically but can be retained by a
        # maintained adapter and its exact receipt serialization. Preserve its
        # sign for reuse without changing ordinary integer/float equivalence.
        if negative_zero:
            record["value"]["negative_zero"] = True
        inputs[key] = record
    return _digest({
        "model": model,
        "inputs": inputs,
        "adapter_version": versions.get(model["type"]), "verification_sources": sources,
    })


def _changes(old, new):
    return (sorted(key for key in old.keys() & new.keys() if old[key] != new[key]),
            sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys()))


def _impact(before, after, *, sources_changed=False, changed_adapter_types=()):
    old_models = {item["id"]: item for item in before["models"]}
    new_models = {item["id"]: item for item in after["models"]}
    old_requirements = {item["id"]: item for item in before["requirements"]}
    new_requirements = {item["id"]: item for item in after["requirements"]}
    changed_inputs, added_inputs, removed_inputs = _changes(before["inputs"], after["inputs"])
    changed_models, added_models, removed_models = _changes(old_models, new_models)
    changed_requirements, added_requirements, removed_requirements = _changes(old_requirements, new_requirements)
    touched_inputs = set(changed_inputs + added_inputs + removed_inputs)
    affected_models = set(changed_models + added_models)
    for model_id, model in new_models.items():
        if (sources_changed or model["type"] in changed_adapter_types
                or touched_inputs.intersection(model["inputs"].values())):
            affected_models.add(model_id)
    for model in chains.ordered_models(after):
        if any(link["model_id"] in affected_models for link in model.get("links", {}).values()):
            affected_models.add(model["id"])
    affected_requirements = set(changed_requirements + added_requirements)
    for requirement in after["requirements"]:
        if requirement["model_id"] in affected_models or requirement["limit_input"] in touched_inputs:
            affected_requirements.add(requirement["id"])
    result = {
        "changed_inputs": changed_inputs, "added_inputs": added_inputs, "removed_inputs": removed_inputs,
        "changed_models": changed_models, "added_models": added_models, "removed_models": removed_models,
        "changed_requirements": changed_requirements, "added_requirements": added_requirements,
        "removed_requirements": removed_requirements,
        "affected_model_ids": sorted(affected_models),
        "affected_requirement_ids": sorted(affected_requirements),
        "verification_sources_changed": sources_changed,
        "changed_adapter_types": sorted(changed_adapter_types),
        "exclusions": ["Impact follows explicit bindings only; physical coupling is not inferred.",
                       "An affected requirement needs review; this preview does not predict its outcome."],
    }
    if any(key in project for project in (before, after) for key in ("systems", "interfaces")):
        from .systems import architecture_impact
        result.update(architecture_impact(before, after, changed_input_ids=touched_inputs,
                                          changed_model_ids=changed_models + added_models + removed_models,
                                          sources_changed=sources_changed or bool(changed_adapter_types)))
    return result


def _graph(project):
    titles = {"ideal_propulsion": "Propulsion", "static_cantilever": "Structures",
              "powered_flight": "Powered vertical flight",
              "attitude_control": "Guidance and control · single-axis pointing",
              "power_energy_budget": "Electrical power",
              "radiative_equilibrium": "Thermal", "drag_load": "Atmospheric loads",
              "orbital_trajectory": "Orbital dynamics",
              "unsupported_closed_loop_gnc": "Guidance and control"}
    from .systems import systems_graph
    declared = systems_graph(project) if "systems" in project else []
    assigned = {model_id for item in declared for model_id in item["own_model_ids"]}
    systems = {}
    links = []
    for model in project["models"]:
        system = None
        if model["id"] not in assigned:
            system = systems.setdefault(model["type"], {
                "id": "system:" + model["type"], "title": ("Unassigned · " if declared else "") + titles.get(model["type"], model["type"]),
                "model_ids": [], "requirement_ids": [],
            })
            system["model_ids"].append(model["id"])
        for input_id in sorted(set(model["inputs"].values())):
            links.append({"source": "input:" + input_id, "target": "model:" + model["id"], "type": "input"})
        for role, link in model.get("links", {}).items():
            links.append({"source": "model:" + link["model_id"], "target": "model:" + model["id"],
                          "type": "calculation", "role": role, **deepcopy(link)})
        for requirement in project["requirements"]:
            if requirement["model_id"] == model["id"]:
                if system is not None:
                    system["requirement_ids"].append(requirement["id"])
                links.extend([
                    {"source": "model:" + model["id"], "target": "requirement:" + requirement["id"], "type": "evidence"},
                    {"source": "input:" + requirement["limit_input"], "target": "requirement:" + requirement["id"], "type": "limit"},
                ])
    result = {"systems": declared + list(systems.values()), "links": links}
    if "systems" in project or "interfaces" in project:
        result["system_links"] = [{"source": "subsystem:" + item["from_system"],
                                    "target": "subsystem:" + item["to_system"], "type": "interface",
                                    "interface_id": item["id"], "title": item["title"]}
                                   for item in project.get("interfaces", [])]
    return result


class WorkspaceStore:
    """Open a local database; each public operation uses its own connection."""

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                    snapshot TEXT NOT NULL, digest TEXT NOT NULL,
                    PRIMARY KEY (project_id, revision)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL UNIQUE, project_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                    receipt TEXT NOT NULL, digest TEXT NOT NULL,
                    FOREIGN KEY (project_id, revision) REFERENCES revisions(project_id, revision)
                );
            """)

    @contextmanager
    def _connect(self, *, write=False):
        connection = sqlite3.connect(str(self.db_path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _rows(self, connection, project_id):
        rows = connection.execute("SELECT * FROM revisions WHERE project_id=? ORDER BY revision", (project_id,)).fetchall()
        if not rows:
            raise WorkspaceError("Project not found.")
        return rows

    def _project(self, row):
        try:
            project = json.loads(row["snapshot"])
            if _digest(project) != row["digest"]:
                raise ValueError("Stored project digest does not match.")
            project = lifecycle.validate_project(project, allow_empty=True)
            if project["project_id"] != row["project_id"] or project["revision"] != str(row["revision"]):
                raise ValueError("Stored project identity does not match its revision.")
            return project
        except (ValueError, TypeError, KeyError) as exc:
            raise WorkspaceError("Stored project revision is inconsistent: " + str(exc)) from exc

    def _receipt(self, row):
        try:
            receipt = json.loads(row["receipt"])
            if _digest(receipt) != row["digest"]:
                raise ValueError("Stored run digest does not match.")
            lifecycle.verify_review(receipt["review"])
            if (receipt["run_id"] != row["run_id"] or receipt["revision"] != row["revision"]
                    or receipt["project_id"] != row["project_id"]
                    or receipt["review"]["revision"] != str(row["revision"])
                    or receipt["review"]["project_id"] != row["project_id"]):
                raise ValueError("Stored run identity does not match its review.")
            model_ids = set(receipt["review"]["evidence"])
            executed = receipt["executed_model_ids"]
            reused = receipt["reused_model_ids"]
            if (set(receipt["model_results"]) != model_ids or set(receipt["model_origins"]) != model_ids
                    or len(executed) != len(set(executed)) or len(reused) != len(set(reused))
                    or set(executed) & set(reused) or set(executed) | set(reused) != model_ids):
                raise ValueError("Stored execution scope does not match its models.")
            for model_id, result in receipt["model_results"].items():
                evidence = receipt["review"]["evidence"][model_id]
                expected_result = {key: value for key, value in evidence.items()
                                   if key not in {"model_definition", "input_records", "verification_sources", "fingerprint"}}
                if expected_result != result:
                    raise ValueError("Stored model results disagree with review evidence.")
                origin = receipt["model_origins"][model_id]
                if (origin["disposition"] != ("executed" if model_id in executed else "reused")
                        or not isinstance(origin["run_id"], str) or not origin["run_id"]
                        or _revision(origin["revision"]) > receipt["revision"]
                        or (model_id in executed and (origin["run_id"] != receipt["run_id"]
                                                     or origin["revision"] != receipt["revision"]))):
                    raise ValueError("Stored model execution origin is inconsistent.")
            return receipt
        except (ValueError, TypeError, KeyError) as exc:
            raise WorkspaceError("Stored execution receipt is inconsistent: " + str(exc)) from exc

    def _runs(self, connection, project_id, revision):
        rows = connection.execute("SELECT * FROM runs WHERE project_id=? AND revision<=? ORDER BY revision DESC, sequence DESC",
                                  (project_id, revision)).fetchall()
        receipts = [self._receipt(row) for row in rows]
        snapshots = {}
        for receipt in receipts:
            number = receipt["revision"]
            if number not in snapshots:
                row = connection.execute("SELECT * FROM revisions WHERE project_id=? AND revision=?",
                                         (project_id, number)).fetchone()
                if row is None:
                    raise WorkspaceError("Stored execution receipt has no matching project revision.")
                snapshots[number] = self._project(row)
            if receipt["review"]["project"] != snapshots[number]:
                raise WorkspaceError("Stored execution receipt disagrees with its project revision.")
        return receipts

    @staticmethod
    def _fresh(receipt):
        return (receipt["review"]["verification_sources"] == _sources()
                and receipt["review"]["adapter_versions"] == MODEL_VERSIONS)

    @staticmethod
    def _applicability_changes(receipt):
        if not receipt:
            return {"sources_changed": False, "changed_adapter_types": []}
        versions = receipt["review"]["adapter_versions"]
        changed = sorted(key for key in set(versions) | set(MODEL_VERSIONS)
                         if versions.get(key) != MODEL_VERSIONS.get(key))
        return {"sources_changed": receipt["review"]["verification_sources"] != _sources(),
                "changed_adapter_types": changed}

    def _view(self, connection, project_id, revision=None):
        rows = self._rows(connection, project_id)
        latest = rows[-1]["revision"]
        selected = latest if revision is None else _revision(revision)
        row = next((item for item in rows if item["revision"] == selected), None)
        if row is None:
            raise WorkspaceError("Project revision not found.")
        project = self._project(row)
        all_receipts = self._runs(connection, project_id, latest)
        receipts = [item for item in all_receipts if item["revision"] <= selected]
        current = next((item for item in receipts if item["revision"] == selected and self._fresh(item)), None)
        # A repeated run of the same revision must not erase its comparison
        # against the preceding reviewed design. Reuse itself can still choose
        # the newest receipt, independently, in run().
        previous = (next((item for item in receipts if item["revision"] < selected), None)
                    if current else next(iter(receipts), None))
        if current and previous is None:
            previous = next((item for item in receipts if item is not current and not self._fresh(item)), None)
        reference = current or previous
        prior = deepcopy(previous)
        if prior:
            prior["stale"] = prior["revision"] != selected or not self._fresh(prior)
            prior["stale_reasons"] = ([] if prior["revision"] == selected else ["Different project revision."])
            if not self._fresh(prior):
                prior["stale_reasons"].append("Verification sources or adapter versions changed.")
        if current:
            current = deepcopy(current)
            current.update(stale=False, stale_reasons=[])
        configuration_base = None
        before = project
        if reference:
            before = reference["review"]["project"]
        else:
            earlier = next((item for item in reversed(rows) if item["revision"] < selected), None)
            if earlier is not None:
                before = self._project(earlier)
                configuration_base = {"revision": earlier["revision"], "project": before}
        impact = _impact(before, project,
                         **self._applicability_changes(reference))
        if not reference:
            impact["affected_model_ids"] = [item["id"] for item in project["models"]]
            impact["affected_requirement_ids"] = [item["id"] for item in project["requirements"]]
        revision_views = []
        for item in rows:
            candidate_runs = [run for run in all_receipts if run["revision"] == item["revision"]]
            revision_views.append({"revision": item["revision"], "created_at": item["created_at"],
                                   "has_current_run": any(self._fresh(run) for run in candidate_runs)})
        comparison = lifecycle.compare_reviews(prior["review"], current["review"]) if prior and current else None
        view = {"schema": "sixd.workspace.v1", "project_id": project_id,
                "revision": selected, "latest_revision": latest, "project": project,
                "revisions": revision_views, "run": current, "prior_run": prior,
                "configuration_base": configuration_base,
                "impact": impact, "comparison": comparison, "graph": _graph(project)}
        if "systems" in project or "interfaces" in project:
            from .workspace_systems import profile_from_view
            view["system_interfaces"] = profile_from_view(view)
        return view

    def list_projects(self):
        with self._connect() as connection:
            projects = [dict(row) for row in connection.execute("""
                SELECT p.project_id, p.created_at, MAX(r.revision) AS revision
                FROM projects p JOIN revisions r ON p.project_id=r.project_id
                GROUP BY p.project_id ORDER BY p.created_at, p.project_id
            """)]
            for item in projects:
                row = connection.execute("SELECT * FROM revisions WHERE project_id=? AND revision=?",
                                         (item["project_id"], item["revision"])).fetchone()
                item["name"] = self._project(row)["name"]
            return projects

    def create_project(self, project):
        snapshot = _snapshot(project, 1)
        identity = snapshot["project_id"]
        with self._connect(write=True) as connection:
            if connection.execute("SELECT 1 FROM projects WHERE project_id=?", (identity,)).fetchone():
                raise ConflictError("A project with this ID already exists. Import with a new project ID.")
            stamp = _now()
            connection.execute("INSERT INTO projects VALUES (?,?)", (identity, stamp))
            connection.execute("INSERT INTO revisions VALUES (?,?,?,?,?)", (identity, 1, stamp, _encode(snapshot), _digest(snapshot)))
            return self._view(connection, identity)

    def ensure_default(self):
        project = example_projects()["baseline"]
        unsupported = example_projects()["missing_evidence"]
        project["inputs"]["maximum_tracking_error"] = unsupported["inputs"]["maximum_tracking_error"]
        project["models"].append(unsupported["models"][-1])
        project["requirements"].append(unsupported["requirements"][-1])
        identity = project["project_id"]
        with self._connect() as connection:
            exists = connection.execute("SELECT 1 FROM projects WHERE project_id=?", (identity,)).fetchone()
        created = False
        if not exists:
            try:
                self.create_project(project)
                created = True
            except ConflictError:
                pass  # Another local request initialized the same example.
        # Only initialize a brand-new demo. Opening an existing workspace after
        # a verifier update must preserve its stale evidence and require an
        # explicit Run checks action, rather than silently appending a run.
        if created and self.get(identity, 1)["run"] is None:
            self.run(identity, 1)
        return identity

    def get(self, project_id, revision=None):
        with self._connect() as connection:
            return self._view(connection, project_id, revision)

    def save_revision(self, project_id, base_revision, project):
        base_revision = _revision(base_revision)
        snapshot = _snapshot(project, base_revision + 1)
        if snapshot["project_id"] != project_id:
            raise WorkspaceError("A revision cannot change project identity.")
        with self._connect(write=True) as connection:
            rows = self._rows(connection, project_id)
            if rows[-1]["revision"] != base_revision:
                raise ConflictError("The project has a newer revision. Reload before saving this draft.")
            connection.execute("INSERT INTO revisions VALUES (?,?,?,?,?)", (
                project_id, base_revision + 1, _now(), _encode(snapshot), _digest(snapshot)))
            return self._view(connection, project_id)

    def preview_change(self, project_id, base_revision, project):
        base_revision = _revision(base_revision)
        snapshot = _snapshot(project, base_revision + 1)
        if snapshot["project_id"] != project_id:
            raise WorkspaceError("A draft cannot change project identity.")
        with self._connect() as connection:
            view = self._view(connection, project_id)
            if view["revision"] != base_revision:
                raise ConflictError("The project has a newer revision. Reload before previewing this draft.")
            receipt = view["run"] or view["prior_run"]
            impact = _impact(receipt["review"]["project"] if receipt else view["project"], snapshot,
                             **self._applicability_changes(receipt))
            impact.update(base_revision=base_revision, preview_revision=base_revision + 1,
                          comparison_revision=receipt["revision"] if receipt else base_revision)
            return impact

    def run(self, project_id, revision):
        revision = _revision(revision)
        sources = _require_current_runtime()
        with self._connect(write=True) as connection:
            rows = self._rows(connection, project_id)
            row = next((item for item in rows if item["revision"] == revision), None)
            if row is None:
                raise WorkspaceError("Project revision not found.")
            project = self._project(row)
            if not project["models"] or not project["requirements"]:
                raise WorkspaceError("Add at least one model and one requirement before running checks.")
            prior = next(iter(self._runs(connection, project_id, revision)), None)
            prior_models = {item["id"]: item for item in prior["review"]["project"]["models"]} if prior else {}
            results, reused, executed, origins = {}, [], [], {}
            run_id = uuid4().hex
            for model in chains.ordered_models(project):
                model_id = model["id"]
                unchanged = (prior and model_id in prior_models
                    and _model_key(project, model, sources, MODEL_VERSIONS)
                    == _model_key(prior["review"]["project"], prior_models[model_id],
                                  prior["review"]["verification_sources"], prior["review"]["adapter_versions"]))
                if unchanged:
                    results[model_id] = deepcopy(prior["model_results"][model_id])
                    reused.append(model_id)
                    origin = deepcopy(prior["model_origins"][model_id])
                    origin["disposition"] = "reused"
                    origins[model_id] = origin
                else:
                    if model.get("links"):
                        results[model_id] = evaluate_model(project, model, results)
                    else:
                        partial = deepcopy(project)
                        partial["models"] = [model]
                        results.update(evaluate_models(partial))
                    executed.append(model_id)
                    origins[model_id] = {"run_id": run_id, "revision": revision, "disposition": "executed"}
            review = lifecycle.review_project(project, results)
            # Preserve the lifecycle normalization of unsupported results too.
            # The receipt's plain result map must exactly match its review.
            results = {identity: {key: deepcopy(value) for key, value in evidence.items()
                                  if key not in {"model_definition", "input_records", "verification_sources", "fingerprint"}}
                       for identity, evidence in review["evidence"].items()}
            # Refuse a receipt if verifier files changed during this transaction.
            if review["verification_sources"] != sources:
                raise WorkspaceError("Verification sources changed during the run; no receipt was saved.")
            stamp = _now()
            receipt = {"schema": "sixd.workspace-run.v1", "run_id": run_id,
                       "project_id": project_id, "revision": revision, "created_at": stamp,
                       "review": review, "model_results": results,
                       "executed_model_ids": executed, "reused_model_ids": reused,
                       "model_origins": origins, "live_model_calls": 0,
                       "execution": "local_maintained_deterministic_adapters"}
            connection.execute("INSERT INTO runs (run_id,project_id,revision,created_at,receipt,digest) VALUES (?,?,?,?,?,?)",
                               (run_id, project_id, revision, stamp, _encode(receipt), _digest(receipt)))
            return self._view(connection, project_id, revision)
