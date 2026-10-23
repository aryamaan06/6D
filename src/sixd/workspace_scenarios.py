"""Bounded hypothetical studies of immutable reviewed project configurations.

Studies never insert project revisions or canonical runs. Numerical evidence uses
the maintained adapters; reads verify frozen records without rerunning physics.
"""
from copy import deepcopy
from hashlib import sha256
import json
from itertools import product
import math
from pathlib import Path
import re
import threading
from uuid import uuid4

from . import chains, lifecycle, workspace
from .engineering import MODEL_VERSIONS, evaluate_model, evaluate_models
from .project_io import _reject_constant, _unique_object
from .workspace import ConflictError, WorkspaceError, _digest, _encode, _now, _revision

SCHEMA = "sixd.scenario-study.v1"
ENVELOPE_SCHEMA = "sixd.envelope-study.v1"
MAX_CASES, MAX_MODELS, MAX_SAMPLES = 16, 64, 32768
MAX_RECEIPT_BYTES = 32 * 1024 * 1024
LIMITATIONS = [
    "Hypothetical results belong to this study, not a new saved project revision or approval.",
    "Only explicitly supplied cases are calculated; no interpolation, operating envelope or optimum is established.",
    "Comparisons do not quantify uncertainty, probabilities or independent physical validation.",
    "Each metric retains its own unit and criterion; margins in different units are not ranked against each other.",
    "Orbital extrema concern stored samples and the declared duration, not continuous-time safety bounds.",
    "Record digests are unsigned consistency checks, not authenticated approval or proof of truth.",
]
ENVELOPE_LIMITATIONS = [
    "Hypothetical sampled results belong to this study, not a saved project revision or approval.",
    "Only the displayed Cartesian sample combinations are calculated; conditions between samples and outside the declared ranges remain unassessed.",
    "Worst observed means worst among retained cases only; no continuous operating envelope, optimization, probability or physical validation is established.",
    "Requirement criteria remain fixed; each margin retains its own unit and is never ranked against margins in different units.",
    "Failed or numerically unresolved calculations remain unassessed and do not establish a vehicle failure or a satisfied criterion.",
    "Orbital and flight extrema concern stored samples and the declared duration, not continuous-time safety bounds.",
    "Record digests are unsigned consistency checks, not authenticated approval or proof of truth.",
]


def eligible_inputs(project):
    """Direct maintained parameter bindings, with fixed criteria and resolution."""
    fixed = {row["limit_input"] for row in project["requirements"]}
    frozen_roles = {"steps", "assessment_start"}
    fixed.update(identity for model in project["models"] for role, identity in model["inputs"].items()
                 if role in frozen_roles or "numerical_tolerance" in role)
    rows = {}
    for model in project["models"]:
        try:
            expected = chains.parameter_units(model)
        except (KeyError, ValueError, TypeError):
            continue
        for role, identity in model["inputs"].items():
            if role == "steps" or role not in expected or role in model.get("links", {}) or identity in fixed:
                continue
            record = project["inputs"].get(identity)
            if not record or record["unit"] != expected[role]:
                continue
            row = rows.setdefault(identity, {"input_id": identity, "unit": record["unit"],
                "value": record["value"], "model_ids": [], "roles": []})
            if model["id"] not in row["model_ids"]:
                row["model_ids"].append(model["id"])
            row["roles"].append({"model_id": model["id"], "role": role})
    return list(rows.values())


def _grid(spec, project):
    if not isinstance(spec, dict) or set(spec) != {"schema", "name", "source", "mode", "axes"} or spec.get("schema") != "sixd.envelope-spec.v1" or spec.get("mode") != "grid":
        raise WorkspaceError("Supply exactly the sixd.envelope-spec.v1 grid fields.")
    normalized = {"schema": spec["schema"], "mode": "grid", "name": _text(spec["name"], "Study name", 120),
                  "source": _text(spec["source"], "Envelope assumptions/source", 1200), "axes": []}
    axes = spec["axes"]
    if not isinstance(axes, list) or not 1 <= len(axes) <= 3:
        raise WorkspaceError("A sampled envelope requires between one and three axes.")
    allowed, found, expanded, count = {row["input_id"]: row for row in eligible_inputs(project)}, set(), [], 1
    for axis in axes:
        if not isinstance(axis, dict) or set(axis) != {"input_id", "minimum", "maximum", "points"}:
            raise WorkspaceError("Each axis requires input_id, minimum, maximum and points.")
        identity, points = axis["input_id"], axis["points"]
        if not isinstance(identity, str) or identity not in allowed or identity in found:
            raise WorkspaceError("Axes must be distinct eligible directly bound parameters; criteria and numerical resolution stay fixed.")
        found.add(identity)
        if isinstance(points, bool) or not isinstance(points, int) or not 2 <= points <= 9:
            raise WorkspaceError("Each axis requires an integer between two and nine points.")
        low, high = _grid_number(axis["minimum"]), _grid_number(axis["maximum"])
        if not low < high:
            raise WorkspaceError("Each axis minimum must be strictly smaller than its maximum.")
        count *= points
        if count > MAX_CASES:
            raise WorkspaceError(f"Cartesian combinations exceed the {MAX_CASES}-case limit.")
        # Convex interpolation avoids overflow in high-low; endpoints retain
        # exactly the supplied JSON numbers. Interior values must stay distinct.
        values = [low] + [_grid_number((1 - i / (points - 1)) * low + (i / (points - 1)) * high)
                          for i in range(1, points - 1)] + [high]
        if any(a >= b for a, b in zip(values, values[1:])):
            raise WorkspaceError("Generated axis values collapse at this numerical precision; widen the range or reduce points.")
        normalized["axes"].append({"input_id": identity, "minimum": low, "maximum": high, "points": points})
        expanded.append({"input_id": identity, "unit": allowed[identity]["unit"], "values": values})
    return normalized, expanded


def _grid_number(value):
    value = _number(value)
    if float(value).is_integer() and abs(value) > 2**53 - 1:
        raise WorkspaceError("Grid integer values must stay within the exact browser-safe numeric range (absolute value at most 9007199254740991).")
    return value


def envelope_findings_summary(cases, project):
    """Summarize frozen findings only: no solver, interpolation or unit mixing."""
    result = []
    for requirement in project["requirements"]:
        identity = requirement["id"]
        rows = [(case["index"], next(row for row in case["findings"] if row["requirement_id"] == identity)) for case in cases]
        counts = {status: sum(row["status"] == status for _, row in rows) for status in ("met", "not_met", "not_assessed")}
        unit = project["inputs"][requirement["limit_input"]]["unit"]
        operator = requirement["operator"]
        candidates, unresolved = [], []
        for index, row in rows:
            value = row.get("margin")
            expected_kind = "absolute_difference" if operator == "==" else "signed_margin"
            if row["status"] == "not_assessed" or not value or value["value"] is None or value["unit"] != unit or value["kind"] != expected_kind:
                unresolved.append(index)
            else:
                candidates.append((index, value["value"]))
        worst = None
        if candidates:
            value = (max if operator == "==" else min)(value for _, value in candidates)
            worst = {"value": value, "unit": unit, "kind": "absolute_difference" if operator == "==" else "signed_margin",
                     "case_indices": [index for index, candidate in candidates if candidate == value]}
        status = "sampled_violation" if counts["not_met"] else "unresolved" if unresolved or not rows else "all_sampled_met"
        result.append({"requirement_id": identity, "title": requirement["title"], "unit": unit, "operator": operator,
                       "counts": counts, "worst_observed": worst, "unresolved_cases": unresolved, "status": status,
                       "note": "Observed sampled cases only. Unresolved cases and unsampled conditions prevent a continuous-envelope conclusion."})
    return result


def _sources():
    return {**workspace._sources(), "workspace_scenarios.py": sha256(Path(__file__).read_bytes()).hexdigest()}


_LOADED_SOURCES = _sources()


def _text(value, label, maximum):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise WorkspaceError(f"{label} requires nonempty text up to {maximum} characters.")
    return value.strip()


def _number(value):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise WorkspaceError("Scenario values must be finite JSON numbers; units come from the baseline.")
    return value


def validate_spec(spec, project):
    if isinstance(spec, dict) and spec.get("schema") == "sixd.envelope-spec.v1":
        return _grid(spec, project)[0]
    if not isinstance(spec, dict) or spec.get("schema") != "sixd.scenario-spec.v1":
        raise WorkspaceError("Supply a sixd.scenario-spec.v1 scenario specification.")
    common = {"schema", "name", "source", "mode"}
    mode = spec.get("mode")
    expected = common | ({"input_id", "values"} if mode == "sweep" else {"cases"})
    if set(spec) != expected or mode not in {"sweep", "alternatives"}:
        raise WorkspaceError("Scenario mode has missing or unsupported fields.")
    normalized = {key: spec[key] for key in common}
    normalized["name"] = _text(spec["name"], "Study name", 120)
    normalized["source"] = _text(spec["source"], "Scenario assumptions/source", 1200)
    if mode == "sweep":
        identity = spec["input_id"]
        if not isinstance(identity, str) or identity not in project["inputs"]:
            raise WorkspaceError("Choose an existing baseline input for the sweep.")
        values = spec["values"]
        if not isinstance(values, list) or not 2 <= len(values) <= MAX_CASES:
            raise WorkspaceError(f"Supply between two and {MAX_CASES} explicit sweep values.")
        values = [_number(value) for value in values]
        if len(set(values)) != len(values):
            raise WorkspaceError("Sweep values must be distinct.")
        normalized.update(input_id=identity, values=values)
    else:
        cases = spec["cases"]
        if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
            raise WorkspaceError(f"Supply between one and {MAX_CASES} named alternatives.")
        names, normalized_cases = set(), []
        for case in cases:
            if not isinstance(case, dict) or set(case) != {"name", "changes"}:
                raise WorkspaceError("Each alternative requires exactly name and changes.")
            name = _text(case["name"], "Case name", 120)
            if name in names:
                raise WorkspaceError("Alternative names must be distinct.")
            names.add(name)
            changes = case["changes"]
            if not isinstance(changes, dict) or not 1 <= len(changes) <= 8:
                raise WorkspaceError("Each alternative changes between one and eight supplied inputs.")
            if any(not isinstance(key, str) or key not in project["inputs"] for key in changes):
                raise WorkspaceError("An alternative refers to an input absent from the baseline.")
            normalized_cases.append({"name": name, "changes": {key: _number(value) for key, value in changes.items()}})
        normalized["cases"] = normalized_cases
    return deepcopy(normalized)


def _cases(spec):
    if spec["mode"] == "grid":
        axes = []
        for axis in spec["axes"]:
            low, high, count = axis["minimum"], axis["maximum"], axis["points"]
            axes.append([low] + [(1 - i / (count - 1)) * low + (i / (count - 1)) * high
                                 for i in range(1, count - 1)] + [high])
        return [{"name": "Sample " + str(index + 1),
                 "changes": {axis["input_id"]: value for axis, value in zip(spec["axes"], values)}}
                for index, values in enumerate(product(*axes))]
    if spec["mode"] == "sweep":
        return [{"name": f"{spec['input_id']} = {value}", "changes": {spec["input_id"]: value}}
                for value in spec["values"]]
    return deepcopy(spec["cases"])


def _variant(project, case, source):
    variant, changes = deepcopy(project), {}
    for identity, value in case["changes"].items():
        before = deepcopy(project["inputs"][identity])
        if before["value"] != value:
            variant["inputs"][identity] = {"value": value, "unit": before["unit"],
                "source": "Hypothetical scenario assumption: " + source + "; baseline source: " + before["source"]}
        changes[identity] = {"before": before, "after": deepcopy(variant["inputs"][identity]),
                             "value_changed": before["value"] != value}
    return variant, changes


def _finite_difference(a, b):
    try:
        value = a - b
        return value if math.isfinite(value) else None
    except OverflowError:
        return None


def margin(finding):
    evidence = finding.get("evidence")
    if not evidence:
        return None
    value, limit, operator = evidence["metric"]["value"], evidence["limit"]["value"], evidence["operator"]
    delta = _finite_difference(limit, value) if operator == "<=" else _finite_difference(value, limit)
    exact = operator == "=="
    return {"kind": "absolute_difference" if exact else "signed_margin",
            "value": abs(delta) if exact and delta is not None else delta,
            "unit": evidence["metric"]["unit"],
            "definition": ("Absolute difference from the exact target; zero alone meets ==. No tolerance inferred." if exact else
                           "Limit minus result; nonnegative meets <=." if operator == "<=" else
                           "Result minus limit; nonnegative meets >=."),
            "note": "Difference exceeds finite numeric range; use the recorded comparison." if delta is None else ""}


def _findings(baseline, review):
    rows = []
    for requirement in review["project"]["requirements"]:
        identity = requirement["id"]
        before, after = baseline["findings"][identity], review["findings"][identity]
        a, b = after["evidence"], before["evidence"]
        comparable = bool(a and b and a["metric"]["unit"] == b["metric"]["unit"])
        status = after["status"]
        next_step = ("Review the calculated criterion violation, its assumptions and input sources; evaluate a justified revision or higher-fidelity analysis." if status == "not_met" else
                     "Resolve the recorded input, metric or unsupported-model issue before concluding whether this criterion is satisfied." if status == "not_assessed" else
                     "Confirm model applicability and input provenance before relying on this calculated pass; inspect excluded effects separately.")
        rows.append({"requirement_id": identity, "title": requirement["title"], "model_id": requirement["model_id"],
                     "metric": requirement["metric"], "status": status, "baseline_status": before["status"],
                     "status_changed": status != before["status"], "evidence": deepcopy(a), "baseline_evidence": deepcopy(b),
                     "metric_change": _finite_difference(a["metric"]["value"], b["metric"]["value"]) if comparable else None,
                     "margin": margin(after), "baseline_margin": margin(before), "reason": after["reason"],
                     "next_step": next_step, "assumptions": deepcopy(after["assumptions"]),
                     "not_assessed": deepcopy(after["not_assessed"])})
    return rows


def _counts(findings):
    return {status: sum(row["status"] == status for row in findings) for status in ("met", "not_met", "not_assessed")}


class WorkspaceScenarios:
    def __init__(self, store):
        self.store, self._lock = store, threading.Lock()
        with store._connect(write=True) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS scenario_studies (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, study_id TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                receipt TEXT NOT NULL, digest TEXT NOT NULL,
                FOREIGN KEY(project_id,revision) REFERENCES revisions(project_id,revision))""")
            connection.execute("CREATE INDEX IF NOT EXISTS studies_project_revision ON scenario_studies(project_id,revision,sequence)")

    def _baseline(self, connection, run_id):
        row = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise WorkspaceError("The study baseline run is missing.")
        run = self.store._receipt(row)
        snapshot = connection.execute("SELECT * FROM revisions WHERE project_id=? AND revision=?",
                                      (run["project_id"], run["revision"])).fetchone()
        if snapshot is None or self.store._project(snapshot) != run["review"]["project"]:
            raise WorkspaceError("The baseline run does not match its saved revision.")
        return run

    def preview_envelope(self, project_id, revision, baseline_run_id, spec):
        _revision(revision)
        with self.store._connect() as connection:
            connection.execute("BEGIN")
            view = self.store._view(connection, project_id, revision)
            if revision != view["latest_revision"] or not view["run"] or view["run"]["run_id"] != baseline_run_id:
                raise ConflictError("Preview requires the latest saved revision and its current baseline run.")
            normalized, axes = _grid(spec, view["project"])
            cases = _cases(normalized)
            self._budget(view["project"], cases, normalized["source"])
            return {"project_id": project_id, "revision": revision, "baseline_run_id": baseline_run_id,
                    "spec": normalized, "axes": axes, "cases": cases, "case_count": len(cases),
                    "limits": self._limits(), "limitations": deepcopy(ENVELOPE_LIMITATIONS)}

    @staticmethod
    def _limits():
        return {"max_cases": MAX_CASES, "max_axes": 3, "min_points_per_axis": 2, "max_points_per_axis": 9,
                "max_overrides_per_case": 8, "max_models": MAX_MODELS,
                "max_orbital_samples": MAX_SAMPLES, "history_limit": 20, "max_snapshot_bytes": MAX_RECEIPT_BYTES}

    @staticmethod
    def _budget(project, cases, source):
        if len(project["models"]) > MAX_MODELS:
            raise WorkspaceError(f"Studies support at most {MAX_MODELS} models per project.")
        total = 0
        for variant in [project] + [_variant(project, case, source)[0] for case in cases]:
            for model in variant["models"]:
                if model["type"] not in {"orbital_trajectory", "attitude_control", "powered_flight"}:
                    continue
                record = variant["inputs"].get(model["inputs"].get("steps"))
                minimum, maximum, multiplier = ((8, 512, 14) if model["type"] == "powered_flight" else (16, 16384, 2) if model["type"] == "orbital_trajectory" else (32, 2048, 2))
                # Work allocation can itself be linked. Bound the retained
                # samples before executing its upstream calculation; never
                # treat an uncomputed step count as zero work.
                steps = maximum if "steps" in model.get("links", {}) else record["value"] if record else 0
                if isinstance(steps, (int, float)) and minimum <= steps <= maximum and float(steps).is_integer():
                    total += multiplier * int(steps) + (6 if model["type"] == "powered_flight" else 1)
        if total > MAX_SAMPLES:
            raise WorkspaceError(f"This study exceeds {MAX_SAMPLES} retained orbital/control/flight samples. Use fewer cases or a suitable smaller grid.")

    def run(self, project_id, revision, baseline_run_id, spec):
        _revision(revision)
        if not isinstance(baseline_run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", baseline_run_id):
            raise WorkspaceError("Choose a saved baseline run ID.")
        if not self._lock.acquire(blocking=False):
            raise ConflictError("A scenario study is already running. Wait for it to finish.")
        try:
            sources = workspace._require_current_runtime()
            if _sources() != _LOADED_SOURCES:
                raise ConflictError("Scenario code changed; restart 6D before running a study.")
            view = self.store.get(project_id, revision)
            grid = isinstance(spec, dict) and spec.get("schema") == "sixd.envelope-spec.v1"
            if grid and revision != view["latest_revision"]:
                raise ConflictError("Sampled envelopes require the latest saved revision.")
            current = view["run"]
            if not current or current["run_id"] != baseline_run_id:
                raise ConflictError("Run checks for this saved revision and select its current baseline before starting a study.")
            with self.store._connect() as connection:
                baseline = self._baseline(connection, baseline_run_id)
            project = baseline["review"]["project"]
            spec = validate_spec(spec, project)
            cases = _cases(spec)
            self._budget(project, cases, spec["source"])
            computed = []
            for index, case in enumerate(cases):
                variant, changes = _variant(project, case, spec["source"])
                results, executed, reused = {}, [], []
                for model in chains.ordered_models(variant):
                    identity = model["id"]
                    original = next(m for m in project["models"] if m["id"] == identity)
                    if workspace._model_key(variant, model, sources, MODEL_VERSIONS) == workspace._model_key(project, original, sources, MODEL_VERSIONS):
                        results[identity] = deepcopy(baseline["model_results"][identity])
                        reused.append(identity)
                    else:
                        if model.get("links"):
                            results[identity] = evaluate_model(variant, model, results)
                        else:
                            scoped = chains.ancestor_project(variant, identity)
                            results[identity] = evaluate_models(scoped)[identity]
                        executed.append(identity)
                review = lifecycle.review_project(variant, results)
                findings = _findings(baseline["review"], review)
                computed.append({"index": index, "name": case["name"], "changes": changes,
                                 "context": "hypothetical_scenario_not_project_revision", "review": review,
                                 "executed_model_ids": executed, "reused_model_ids": reused,
                                 "reused_model_origins": {key: deepcopy(baseline["model_origins"][key]) for key in reused},
                                 "findings": findings, "counts": _counts(findings)})
            if _sources() != _LOADED_SOURCES:
                raise ConflictError("Scenario sources changed during calculation; no study was saved.")
            identity, stamp = uuid4().hex, _now()
            receipt = {"schema": ENVELOPE_SCHEMA if grid else SCHEMA, "study_id": identity, "project_id": project_id, "revision": revision,
                       "created_at": stamp, "spec": spec, "sources": deepcopy(_LOADED_SOURCES),
                       "baseline": {"run_id": baseline_run_id, "run_digest": _digest(baseline),
                                    "review": deepcopy(baseline["review"]), "model_origins": deepcopy(baseline["model_origins"])},
                       "cases": computed, "execution": "local_maintained_adapters_hypothetical_study",
                       "live_model_calls": 0, "limitations": deepcopy(ENVELOPE_LIMITATIONS if grid else LIMITATIONS)}
            if grid:
                receipt["axes"] = _grid(spec, project)[1]
                receipt["envelope_summary"] = envelope_findings_summary(computed, project)
            encoded = _encode(receipt)
            if len(encoded.encode("utf-8")) > MAX_RECEIPT_BYTES:
                raise WorkspaceError("The study exceeds the 32 MiB receipt limit; use fewer cases.")
            with self.store._connect(write=True) as connection:
                final_view = self.store._view(connection, project_id, revision)
                selected = final_view["run"]
                if (not selected or selected["run_id"] != baseline_run_id or _sources() != _LOADED_SOURCES
                        or (grid and revision != final_view["latest_revision"])
                        or _digest(self._baseline(connection, baseline_run_id)) != receipt["baseline"]["run_digest"]):
                    raise ConflictError("The baseline or calculation sources changed; no study was saved.")
                row = {"study_id": identity, "project_id": project_id, "revision": revision,
                       "created_at": stamp, "receipt": encoded, "digest": _digest(receipt)}
                self._read(connection, row)
                connection.execute("INSERT INTO scenario_studies (study_id,project_id,revision,created_at,receipt,digest) VALUES (?,?,?,?,?,?)",
                    (identity, project_id, revision, stamp, encoded, row["digest"]))
            return self.get(identity, revision)
        finally:
            self._lock.release()

    def _read(self, connection, row):
        try:
            receipt = json.loads(row["receipt"], object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            grid = receipt["schema"] == ENVELOPE_SCHEMA
            if (_digest(receipt) != row["digest"] or receipt["schema"] not in {SCHEMA, ENVELOPE_SCHEMA}
                    or any(receipt[key] != row[key] for key in ("study_id", "project_id", "revision", "created_at"))
                    or receipt["execution"] != "local_maintained_adapters_hypothetical_study" or receipt["live_model_calls"] != 0):
                raise ValueError("Study identity or digest is inconsistent.")
            if receipt["limitations"] != (ENVELOPE_LIMITATIONS if grid else LIMITATIONS):
                raise ValueError("Study scope disclosure is inconsistent.")
            baseline = self._baseline(connection, receipt["baseline"]["run_id"])
            if (baseline["project_id"] != receipt["project_id"] or baseline["revision"] != receipt["revision"]
                    or receipt["baseline"] != {"run_id": baseline["run_id"], "run_digest": _digest(baseline),
                                              "review": baseline["review"], "model_origins": baseline["model_origins"]}):
                raise ValueError("Study does not match its frozen baseline.")
            sources = receipt["sources"]
            if (set(sources) != set(baseline["review"]["verification_sources"]) | {"workspace_scenarios.py"}
                    or any(not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value) for value in sources.values())
                    or {k: v for k, v in sources.items() if k != "workspace_scenarios.py"} != baseline["review"]["verification_sources"]):
                raise ValueError("Study source binding is inconsistent.")
            project = baseline["review"]["project"]
            spec = validate_spec(receipt["spec"], project)
            if grid != (spec["schema"] == "sixd.envelope-spec.v1"):
                raise ValueError("Study schema and specification disagree.")
            if grid and receipt["axes"] != _grid(spec, project)[1]:
                raise ValueError("Study generated axes are inconsistent.")
            definitions = _cases(spec)
            if len(receipt["cases"]) != len(definitions):
                raise ValueError("Study case count is inconsistent.")
            for index, (case, definition) in enumerate(zip(receipt["cases"], definitions)):
                review = case["review"]
                lifecycle.verify_review(review)
                variant, changes = _variant(project, definition, spec["source"])
                findings = _findings(baseline["review"], review)
                executed, reused = case["executed_model_ids"], case["reused_model_ids"]
                ids = {model["id"] for model in project["models"]}
                if (case["index"] != index or case["name"] != definition["name"] or case["changes"] != changes
                        or case["context"] != "hypothetical_scenario_not_project_revision" or review["project"] != variant
                        or review["adapter_versions"] != baseline["review"]["adapter_versions"]
                        or review["verification_sources"] != baseline["review"]["verification_sources"]
                        or case["findings"] != findings or case["counts"] != _counts(findings)
                        or len(executed) != len(set(executed)) or len(reused) != len(set(reused))
                        or set(executed) & set(reused) or set(executed) | set(reused) != ids
                        or case["reused_model_origins"] != {key: baseline["model_origins"][key] for key in reused}):
                    raise ValueError("Study case evidence or applicability is inconsistent.")
                for model in project["models"]:
                    identity = model["id"]
                    same = chains.dependency_configuration(project, identity) == chains.dependency_configuration(variant, identity)
                    if same != (identity in reused):
                        raise ValueError("Study execution scope disagrees with changed bindings.")
                    if same and review["evidence"][identity] != baseline["review"]["evidence"][identity]:
                        raise ValueError("Reused study evidence differs from its baseline.")
            if grid and receipt["envelope_summary"] != envelope_findings_summary(receipt["cases"], project):
                raise ValueError("Sampled envelope summary disagrees with retained findings.")
            return receipt
        except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
            raise WorkspaceError("Stored scenario study is inconsistent: " + str(exc)) from exc

    def _freshness(self, receipt, view):
        source_current = receipt["sources"] == _sources()
        matches = receipt["revision"] == view["revision"]
        baseline_matches = bool(view["run"] and view["run"]["run_id"] == receipt["baseline"]["run_id"])
        return {"source_current": source_current, "selected_revision_matches": matches,
                "baseline_run_matches": baseline_matches, "historical": not(source_current and matches and baseline_matches),
                "context_revision": view["revision"],
                "note": "Study results are hypothetical evidence for their recorded baseline; they never replace the current project review."}

    def get(self, identity, revision=None):
        if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise WorkspaceError("Invalid scenario study ID.")
        with self.store._connect() as connection:
            connection.execute("BEGIN")
            row = connection.execute("SELECT * FROM scenario_studies WHERE study_id=?", (identity,)).fetchone()
            if row is None:
                raise WorkspaceError("Scenario study not found.")
            receipt = self._read(connection, row)
            view = self.store._view(connection, receipt["project_id"], revision)
            if receipt["revision"] > view["revision"]:
                raise WorkspaceError("This study belongs to a later revision than the selected context.")
            return {"receipt": receipt, "receipt_digest": row["digest"], "freshness": self._freshness(receipt, view),
                    "integrity": {"digest_valid": True, "baseline_binding_valid": True, "unsigned": True},
                    "current_sources": _sources()}

    def list(self, project_id, revision):
        _revision(revision)
        with self.store._connect() as connection:
            connection.execute("BEGIN")
            view = self.store._view(connection, project_id, revision)
            rows = connection.execute("SELECT * FROM scenario_studies WHERE project_id=? AND revision<=? ORDER BY sequence DESC LIMIT 20",
                                      (project_id, revision)).fetchall()
            studies = []
            for row in rows:
                receipt = self._read(connection, row)
                studies.append({key: receipt[key] for key in ("study_id", "project_id", "revision", "created_at")}
                               | {"name": receipt["spec"]["name"], "mode": receipt["spec"]["mode"],
                                  "case_count": len(receipt["cases"]), "baseline_run_id": receipt["baseline"]["run_id"],
                                  "freshness": self._freshness(receipt, view)})
        return {"project_id": project_id, "revision": revision, "latest_revision": view["latest_revision"], "studies": studies,
                "eligible_inputs": eligible_inputs(view["project"]), "limits": self._limits(),
                "baseline_run_id": view["run"]["run_id"] if view["run"] else None,
                "limitations": deepcopy(LIMITATIONS)}

    def envelope_snapshot(self, connection, view):
        """Freeze bounded full study records in the caller's read transaction."""
        project_id, revision = view["project_id"], view["revision"]
        total = connection.execute("SELECT count(*) FROM scenario_studies WHERE project_id=? AND revision<=? AND json_extract(receipt,'$.schema')=?",
                                   (project_id, revision, ENVELOPE_SCHEMA)).fetchone()[0]
        rows = connection.execute("SELECT * FROM scenario_studies WHERE project_id=? AND revision<=? AND json_extract(receipt,'$.schema')=? ORDER BY sequence DESC LIMIT 20",
                                  (project_id, revision, ENVELOPE_SCHEMA)).fetchall()
        result = {"project_id": project_id, "revision": revision, "studies": [], "history_limit": 20,
                  "history_truncated": False, "omitted_count": 0, "limitations": deepcopy(ENVELOPE_LIMITATIONS)}
        for row in rows:
            receipt = self._read(connection, row)
            record = {"receipt": receipt, "receipt_digest": row["digest"], "freshness": self._freshness(receipt, view),
                      "integrity": {"digest_valid": True, "baseline_binding_valid": True, "unsigned": True},
                      "current_sources": _sources()}
            result["studies"].append(record)
            # Never partially include a receipt or silently exceed the export
            # limit; the number omitted is explicit and individual reads remain.
            if len(_encode(result).encode("utf-8")) > MAX_RECEIPT_BYTES - 1024:
                result["studies"].pop()
                break
        result["omitted_count"] = total - len(result["studies"])
        result["history_truncated"] = bool(result["omitted_count"])
        result["digest"] = _digest(result)
        return result

    def envelope_summary(self, project_id, revision):
        with self.store._connect() as connection:
            connection.execute("BEGIN")
            return self.envelope_snapshot(connection, self.store._view(connection, project_id, _revision(revision)))
