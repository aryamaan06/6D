"""Append-only orbital scenarios attached to exact saved project revisions.

Standalone scenarios and canonical orbital model evidence share a read-only
playback interface. Reading history verifies saved data and never executes the
numerical kernel. Digests are unsigned local consistency checks, not authenticated
engineering approval.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import threading
from uuid import uuid4

from . import simulation, workspace
from .project_io import _reject_constant, _unique_object
from .workspace import ConflictError, WorkspaceError, _digest, _encode, _now, _revision


RECEIPT_SCHEMA = "sixd.workspace-simulation.v1"
BINDING_NOTE = ("These explicit scenario inputs are attached to this exact saved project revision. "
                "They are not derived from its static component settings or requirement findings.")
DIGEST_NOTE = "Unsigned SHA-256 consistency digest; not a signature or authenticated approval."
PROJECT_BINDING_NOTE = ("This is a derived playback view of the exact trajectory saved in the canonical project model review. "
                        "Its findings use this review's requirements and limits. Reused trajectory evidence retains its original execution origin. "
                        "The view digest does not create a second calculation or an independent approval.")


def _sources():
    return {"simulation.py": sha256(Path(simulation.__file__).read_bytes()).hexdigest(),
            "workspace_simulation.py": sha256(Path(__file__).read_bytes()).hexdigest()}


_LOADED_SOURCES = {**_sources(), "simulation.py": simulation.source_fingerprint()}


class WorkspaceSimulation:
    def __init__(self, store):
        self.store = store
        self._run_lock = threading.Lock()
        with store._connect(write=True) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS simulations (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                simulation_id TEXT NOT NULL UNIQUE, project_id TEXT NOT NULL,
                revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                receipt TEXT NOT NULL, digest TEXT NOT NULL,
                FOREIGN KEY (project_id, revision) REFERENCES revisions(project_id, revision)
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS simulations_project_revision ON simulations(project_id,revision,sequence)")

    @staticmethod
    def _identity(identity):
        if not isinstance(identity, str) or not re.fullmatch(r"(?:[a-f0-9]{32}|p-[a-f0-9]{32}-[a-f0-9]{16})", identity):
            raise WorkspaceError("Invalid simulation ID.")
        return identity

    @staticmethod
    def project_identity(run_id, model_id):
        return "p-" + run_id + "-" + sha256(model_id.encode("utf-8")).hexdigest()[:16]

    def _project_receipt(self, run, model_id):
        """Adapt already verified immutable evidence; never execute a calculator."""
        result = run["model_results"][model_id]
        trajectory = result.get("simulation")
        if (result["model_type"] != "orbital_trajectory" or result["status"] != "completed"
                or not isinstance(trajectory, dict)):
            raise WorkspaceError("This project model has no saved completed trajectory.")
        review = run["review"]
        receipt = {"schema": RECEIPT_SCHEMA,
                "simulation_id": self.project_identity(run["run_id"], model_id),
                "project_id": run["project_id"], "revision": run["revision"], "created_at": run["created_at"],
                "project_snapshot": deepcopy(review["project"]),
                "project_snapshot_digest": _digest(review["project"]),
                "spec": deepcopy(trajectory["spec"]), "sources": deepcopy(review["verification_sources"]),
                "result": deepcopy(trajectory), "binding_note": PROJECT_BINDING_NOTE,
                "execution": "saved_project_model_playback", "live_model_calls": 0,
                "binding_kind": "project_model", "derived_view": True,
                "model_id": model_id, "workspace_run_id": run["run_id"],
                "workspace_run_digest": _digest(run), "review_digest": review["digest"],
                "adapter_versions": deepcopy(review["adapter_versions"]),
                "model_origin": deepcopy(run["model_origins"][model_id]),
                "findings": [deepcopy(finding) for finding in review["findings"].values()
                             if finding["model_id"] == model_id]}
        if "calculation_inputs" in result:
            receipt["calculation_inputs"] = deepcopy(result["calculation_inputs"])
            receipt["binding_note"] += (" Explicit scalar calculation links supplied the recorded roles in calculation_inputs. "
                                        "They do not create a coupled time simulation; source metrics and transfer rationales retain their own scope.")
        if "numerical_accuracy" in result:
            # Playback is a derived compact view. The canonical model result
            # retains both complete reference grids and its validated arithmetic.
            receipt["numerical_accuracy"] = {key: deepcopy(value) for key, value in result["numerical_accuracy"].items()
                                               if key != "reference_levels"}
            receipt["accuracy_evidence_note"] = ("Compact projection of the saved numerical accuracy receipt. "
                                                "Full coarser reference trajectories remain in the canonical project review identified above.")
        if "applicability" in result:
            receipt["applicability"] = deepcopy(result["applicability"])
        return receipt

    def _project_detail(self, run, model_id, selected_revision, current_run_id):
        receipt = self._project_receipt(run, model_id)
        detail = self._detail(receipt, _digest(receipt), workspace._sources(), selected_revision)
        current = self.store._fresh(run)
        selected_run_matches = run["run_id"] == current_run_id
        detail["freshness"].update(source_current=current, selected_run_matches=selected_run_matches,
                                   historical=not current or not selected_run_matches)
        detail["freshness"]["note"] = (
            "Saved canonical trajectory and findings from the current review of this selected revision."
            if current and selected_run_matches else
            "Historical canonical trajectory and findings; these are not a current review of the selected revision.")
        detail["integrity"].update(derived_view=True, canonical_run_digest=receipt["workspace_run_digest"],
                                   canonical_review_digest=receipt["review_digest"],
                                   note=DIGEST_NOTE + " This playback wrapper is derived from a verified saved project run; it is not a separate simulation receipt.")
        return detail

    @staticmethod
    def _current_run_id(runs, revision, store):
        return next((run["run_id"] for run in runs
                     if run["revision"] == revision and store._fresh(run)), None)

    def _project(self, connection, project_id, revision):
        if not isinstance(project_id, str) or not project_id.strip():
            raise WorkspaceError("A project ID is required.")
        _revision(revision)
        row = connection.execute("SELECT * FROM revisions WHERE project_id=? AND revision=?",
                                 (project_id, revision)).fetchone()
        if row is None:
            raise WorkspaceError("The simulation requires an existing saved project revision.")
        return self.store._project(row), row["digest"]

    def _read(self, connection, row):
        """Check frozen identities and binding without rerunning current physics."""
        try:
            receipt = json.loads(row["receipt"], object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            if not isinstance(receipt, dict) or _digest(receipt) != row["digest"]:
                raise ValueError("Stored simulation digest does not match.")
            if (receipt["schema"] != RECEIPT_SCHEMA
                    or receipt["simulation_id"] != row["simulation_id"]
                    or receipt["project_id"] != row["project_id"]
                    or receipt["revision"] != row["revision"]
                    or receipt["created_at"] != row["created_at"]
                    or receipt["execution"] != "local_deterministic_orbit_simulation"
                    or receipt["live_model_calls"] != 0):
                raise ValueError("Stored simulation identity or execution scope is inconsistent.")
            self._identity(receipt["simulation_id"])
            project, project_digest = self._project(connection, receipt["project_id"], receipt["revision"])
            if (receipt["project_snapshot"] != project
                    or receipt["project_snapshot_digest"] != project_digest
                    or _digest(receipt["project_snapshot"]) != project_digest):
                raise ValueError("Stored simulation disagrees with its exact project revision.")
            sources, result, spec = receipt["sources"], receipt["result"], receipt["spec"]
            if (set(sources) != {"simulation.py", "workspace_simulation.py"}
                    or not all(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value)
                               for value in sources.values())
                    or result["source_fingerprint"] != sources["simulation.py"]
                    or result["schema"] != "sixd.orbit-simulation.v1"
                    or result["spec"] != spec
                    or spec["schema"] != "sixd.orbit-scenario.v1"):
                raise ValueError("Stored simulation sources or scenario binding is inconsistent.")
            # This frozen v1 structural contract deliberately does not call the
            # current scenario validator: later validators cannot rewrite history.
            samples = result["samples"]
            method_identity = tuple(result["method"].get(key) for key in ("name", "version", "order"))
            if method_identity not in {("velocity_verlet", "1", 2), ("rk4", "2", 4)} or type(result["method"]["order"]) is not int:
                raise ValueError("Unsupported retained orbital method.")
            maximum_steps = 16384 if method_identity[0] == "rk4" else 4096
            if (type(spec["steps"]) is not int or not 16 <= spec["steps"] <= maximum_steps
                    or not isinstance(samples, list) or len(samples) != spec["steps"] + 1
                    or result["summary"]["sample_count"] != len(samples)
                    or samples[0]["time_s"] != 0 or samples[-1]["time_s"] != spec["duration_s"]
                    or samples[0]["position_m"] != spec["position_m"]
                    or samples[0]["velocity_m_s"] != spec["velocity_m_s"]
                    or result["method"]["steps"] != spec["steps"]):
                raise ValueError("Stored simulation samples disagree with their scenario.")
            previous_time = -1.0
            for sample in samples:
                if (sample["time_s"] <= previous_time
                        or len(sample["position_m"]) != 3 or len(sample["velocity_m_s"]) != 3):
                    raise ValueError("Stored simulation sample sequence is inconsistent.")
                previous_time = sample["time_s"]
            return receipt
        except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
            raise WorkspaceError("Stored simulation receipt is inconsistent: " + str(exc)) from exc

    @staticmethod
    def _summary(receipt, digest, current_sources, selected_revision):
        current = receipt["sources"] == current_sources
        matches = receipt["revision"] == selected_revision
        return {"simulation_id": receipt["simulation_id"], "project_id": receipt["project_id"],
                "revision": receipt["revision"], "created_at": receipt["created_at"],
                "spec": deepcopy(receipt["spec"]), "sources": deepcopy(receipt["sources"]),
                "result_summary": deepcopy(receipt["result"]["summary"]), "receipt_digest": digest,
                "source_current": current, "selected_revision_matches": matches,
                "context_revision": selected_revision, "historical": not current or not matches,
                "binding_kind": receipt.get("binding_kind", "standalone"),
                **{key: deepcopy(receipt[key]) for key in ("model_id", "workspace_run_id", "review_digest", "model_origin",
                                                         "numerical_accuracy", "accuracy_evidence_note", "applicability")
                   if key in receipt}}

    @classmethod
    def _detail_summary(cls, detail):
        summary = cls._summary(detail["receipt"], detail["receipt_digest"], detail["current_sources"],
                               detail["freshness"]["context_revision"])
        summary.update({key: value for key, value in detail["freshness"].items() if key != "note"})
        return summary

    @staticmethod
    def _detail(receipt, digest, current_sources, selected_revision):
        current = receipt["sources"] == current_sources
        matches = receipt["revision"] == selected_revision
        note = ("Saved samples from the recorded source version; source changes do not alter this historical receipt."
                if not current else "Recorded simulation sources match the current application sources.")
        if not matches:
            note += " This receipt is attached to a different project revision from the displayed context."
        return {"receipt": receipt, "receipt_digest": digest,
                "integrity": {"digest_valid": True, "project_binding_valid": True,
                              "unsigned": True, "note": DIGEST_NOTE},
                "freshness": {"source_current": current, "selected_revision_matches": matches,
                              "context_revision": selected_revision,
                              "historical": not current or not matches, "note": note},
                "current_sources": current_sources}

    def list(self, project_id, revision):
        with self.store._connect() as connection:
            project, _ = self._project(connection, project_id, revision)
            rows = connection.execute("SELECT * FROM simulations WHERE project_id=? AND revision<=? ORDER BY sequence DESC",
                                      (project_id, revision)).fetchall()
            sources = _sources()
            summaries = [self._summary(self._read(connection, row), row["digest"], sources, revision)
                         for row in rows]
            runs = self.store._runs(connection, project_id, revision)
            current_id = self._current_run_id(runs, revision, self.store)
            current = next((run for run in runs if run["run_id"] == current_id), None)
            for run in runs:
                for model_id, result in run["model_results"].items():
                    if result.get("simulation") is not None:
                        summaries.append(self._detail_summary(self._project_detail(run, model_id, revision, current_id)))
            summaries.sort(key=lambda row: (row["revision"], row["created_at"], row["simulation_id"]), reverse=True)
            project_models = []
            for model in project["models"]:
                if model["type"] != "orbital_trajectory":
                    continue
                result = current["model_results"].get(model["id"]) if current else None
                identity = (self.project_identity(current_id, model["id"])
                            if result and result.get("simulation") is not None else None)
                historical = any(row.get("model_id") == model["id"] for row in summaries)
                status = "current" if identity else "not_assessed" if current else "historical" if historical else "not_run"
                project_models.append({"model_id": model["id"], "name": model.get("description") or model["id"],
                                       "status": status, "simulation_id": identity,
                                       "requirement_ids": [item["id"] for item in project["requirements"]
                                                           if item["model_id"] == model["id"]]})
        return {"project_id": project_id, "revision": revision, "default_spec": simulation.default_spec(),
                "simulations": summaries, "current_sources": sources, "binding_note": BINDING_NOTE,
                "project_models": project_models,
                "comparison_note": "Compare two saved scenarios through the compatibility check before overlaying results."}

    def get(self, identity, selected_revision=None):
        self._identity(identity)
        with self.store._connect() as connection:
            if identity.startswith("p-"):
                run_id = identity.split("-")[1]
                row = connection.execute("SELECT project_id, revision FROM runs WHERE run_id=?", (run_id,)).fetchone()
                if row is None:
                    raise WorkspaceError("Simulation not found.")
                latest = connection.execute("SELECT MAX(revision) FROM revisions WHERE project_id=?", (row["project_id"],)).fetchone()[0]
                context_revision = latest if selected_revision is None else selected_revision
                self._project(connection, row["project_id"], context_revision)
                if row["revision"] > context_revision:
                    raise WorkspaceError("This trajectory belongs to a later revision than the selected context.")
                runs = self.store._runs(connection, row["project_id"], context_revision)
                run = next(item for item in runs if item["run_id"] == run_id)
                matches = [model_id for model_id in run["model_results"]
                           if self.project_identity(run_id, model_id) == identity]
                if len(matches) != 1:
                    raise WorkspaceError("Simulation not found or model identity is ambiguous.")
                return self._project_detail(run, matches[0], context_revision,
                                            self._current_run_id(runs, context_revision, self.store))
            row = connection.execute("SELECT * FROM simulations WHERE simulation_id=?", (identity,)).fetchone()
            if row is None:
                raise WorkspaceError("Simulation not found.")
            receipt = self._read(connection, row)
            latest = connection.execute("SELECT MAX(revision) FROM revisions WHERE project_id=?",
                                        (receipt["project_id"],)).fetchone()[0]
            context_revision = latest if selected_revision is None else selected_revision
            self._project(connection, receipt["project_id"], context_revision)
        return self._detail(receipt, row["digest"], _sources(), context_revision)

    def run(self, project_id, revision, spec):
        # One bounded local calculation at a time; repeated concurrent requests
        # do not create an unbounded compute queue or call a provider.
        if not self._run_lock.acquire(blocking=False):
            raise ConflictError("A local simulation is already running. Wait for it to finish before starting another.")
        try:
            if _sources() != _LOADED_SOURCES:
                raise ConflictError("Simulation code changed after this application started. Restart 6D before running a scenario; historical receipts remain readable.")
            normalized = simulation.validate_spec(spec)
            with self.store._connect() as connection:
                project, project_digest = self._project(connection, project_id, revision)
            result = simulation.simulate(normalized)
            if (result["spec"] != normalized or result["source_fingerprint"] != _LOADED_SOURCES["simulation.py"]):
                raise WorkspaceError("Simulation output does not match the declared scenario or loaded kernel.")
            identity, stamp = uuid4().hex, _now()
            receipt = {"schema": RECEIPT_SCHEMA, "simulation_id": identity,
                       "project_id": project_id, "revision": revision, "created_at": stamp,
                       "project_snapshot": project, "project_snapshot_digest": project_digest,
                       "spec": normalized, "sources": deepcopy(_LOADED_SOURCES), "result": result,
                       "binding_note": BINDING_NOTE, "execution": "local_deterministic_orbit_simulation",
                       "live_model_calls": 0}
            digest = _digest(receipt)
            with self.store._connect(write=True) as connection:
                # Recheck both bindings after the computation and before commit.
                latest_project, latest_digest = self._project(connection, project_id, revision)
                if latest_project != project or latest_digest != project_digest:
                    raise WorkspaceError("Project snapshot changed during simulation; no receipt was saved.")
                if _sources() != _LOADED_SOURCES:
                    raise ConflictError("Simulation sources changed during execution; no receipt was saved. Restart 6D.")
                row = {"simulation_id": identity, "project_id": project_id, "revision": revision,
                       "created_at": stamp, "receipt": _encode(receipt), "digest": digest}
                self._read(connection, row)
                connection.execute("INSERT INTO simulations (simulation_id,project_id,revision,created_at,receipt,digest) VALUES (?,?,?,?,?,?)",
                                   (identity, project_id, revision, stamp, row["receipt"], digest))
            return self.get(identity, revision)
        finally:
            self._run_lock.release()

    def compare(self, left_id, right_id):
        left, right = self.get(left_id), self.get(right_id)
        a, b = left["receipt"], right["receipt"]
        reasons = []
        if left_id == right_id:
            reasons.append("Choose two distinct saved scenarios.")
        if a["project_id"] != b["project_id"]:
            reasons.append("The scenarios belong to different projects.")
        for field, label in (("schema", "Scenario schema"), ("mu_m3_s2", "Gravitational parameter"),
                             ("frame", "Reference frame"), ("exclusion_radius_m", "Exclusion radius")):
            if a["spec"].get(field) != b["spec"].get(field):
                reasons.append(label + " differs.")
        for field in ("name", "version", "order", "force_model"):
            if a["result"]["method"].get(field) != b["result"]["method"].get(field):
                reasons.append("Numerical method or force model differs (" + field + ").")
        if a["result"]["units"] != b["result"]["units"]:
            reasons.append("Result units differ.")
        # The immutable numerical kernel is the common source between standalone
        # scenarios and project-model views. Wrapper/other adapter changes do not
        # change saved orbital physics. Each full source map remains disclosed.
        if (a["result"].get("source_fingerprint") != b["result"].get("source_fingerprint")
                or a["sources"].get("simulation.py") != b["sources"].get("simulation.py")):
            reasons.append("Recorded simulation kernel sources differ.")
        changed = sorted(field for field in set(a["spec"]) | set(b["spec"])
                         if a["spec"].get(field) != b["spec"].get(field))
        same_window = a["spec"]["duration_s"] == b["spec"]["duration_s"]
        return {"schema": "sixd.simulation-comparison.v1", "compatible": not reasons, "reasons": reasons,
                "changed_spec_fields": changed,
                "left": self._detail_summary(left),
                "right": self._detail_summary(right),
                "shared_time_domain_s": [0, min(a["spec"]["duration_s"], b["spec"]["duration_s"])] if not reasons else None,
                "same_duration": same_window,
                "same_initial_state": all(a["spec"][key] == b["spec"][key] for key in ("position_m", "velocity_m_s")),
                "note": ("Each scenario retains its own inputs, time steps, samples and numerical diagnostics. "
                         "These comparisons do not change project requirement findings."
                         + (" Durations differ; full-run extrema cover different time intervals." if not same_window else ""))}
