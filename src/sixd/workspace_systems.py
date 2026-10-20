"""Read-only, revision-bound system organization and interface projections."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from . import lifecycle, workspace
from .systems import evaluate_interfaces, architecture_impact
from .workspace import WorkspaceError, ConflictError, _digest, _revision


def _sources():
    directory = Path(__file__).resolve().parent
    return {**workspace._sources(), **{name: sha256((directory / name).read_bytes()).hexdigest()
                                      for name in ("systems.py", "workspace_systems.py")}}


def profile_from_view(view, project=None):
    """Project only recorded values; never run adapters or alter a verdict."""
    selected = view["project"] if project is None else project
    draft = project is not None
    current = view["run"]
    review = current["review"] if current and not draft else None
    before = selected
    if draft:
        before = view["project"]
    elif view["prior_run"]:
        before = view["prior_run"]["review"]["project"]
    elif view.get("configuration_base"):
        before = view["configuration_base"]["project"]
    changed_inputs = [key for key in set(before["inputs"]) | set(selected["inputs"])
                      if before["inputs"].get(key) != selected["inputs"].get(key)]
    old_models = {model["id"]: model for model in before["models"]}
    new_models = {model["id"]: model for model in selected["models"]}
    changed_models = [key for key in set(old_models) | set(new_models) if old_models.get(key) != new_models.get(key)]
    profile = {"schema": "sixd.system-interfaces.v1", "project_id": view["project_id"],
               "revision": view["revision"], "project_digest": _digest(selected),
               "context": "draft" if draft else "saved",
               "run_id": current["run_id"] if current else None,
               "review_digest": current["review"]["digest"] if current else None,
               "checks": evaluate_interfaces(selected, review, draft=draft),
               "impact": architecture_impact(before, selected, changed_input_ids=changed_inputs,
                                             changed_model_ids=changed_models),
               "sources": _sources()}
    profile["digest"] = _digest(profile)
    return profile


class WorkspaceSystems:
    def __init__(self, store):
        self.store = store

    def _read(self, project_id, revision, project=None):
        if not isinstance(project_id, str) or not project_id.strip():
            raise WorkspaceError("Select a project for system interfaces.")
        revision = _revision(revision)
        sources = _sources()
        with self.store._connect() as connection:
            connection.execute("BEGIN")
            view = self.store._view(connection, project_id, revision)
            selected = None
            if project is not None:
                if view["latest_revision"] != revision:
                    raise ConflictError("Select the latest saved revision before previewing an architecture draft.")
                try:
                    selected = lifecycle.validate_project(project, allow_empty=True)
                except (ValueError, TypeError, OverflowError) as exc:
                    raise WorkspaceError("Invalid system architecture draft: " + str(exc)) from exc
                if selected["project_id"] != project_id or selected["revision"] not in {str(revision), str(revision + 1)}:
                    raise WorkspaceError("The architecture draft must belong to the selected project and base revision.")
            result = profile_from_view(view, selected)
            if sources != _sources():
                raise ConflictError("Interface verification sources changed during this read. Restart and refresh 6D.")
            return result

    def get(self, project_id, revision):
        return self._read(project_id, revision)

    def preview(self, project_id, base_revision, project):
        return self._read(project_id, base_revision, project)
