"""Versioned requirements and bounded deterministic engineering evidence.

``review_project`` expects fresh results from maintained adapters, supplied by a
trusted deterministic caller. It is not an ingestion API for externally claimed
results. Digests detect inconsistent records, not authenticated truth. Lifecycle
stage is descriptive metadata; a design calculation is never hardware approval.
"""
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import re


PROJECT_SCHEMA = "sixd.project.v1"
REVIEW_SCHEMA = "sixd.review.v1"
STAGES = {"design", "simulation", "physical_test", "operation"}
RESULT_STATUSES = {"completed", "not_assessed", "invalid_inputs"}
LEGACY_VERIFICATION_SOURCE_NAMES = {"engineering.py", "lifecycle.py", "__init__.py"}
ORBITAL_VERIFICATION_SOURCE_NAMES = LEGACY_VERIFICATION_SOURCE_NAMES | {"orbital_adapter.py", "simulation.py"}
ATTITUDE_VERIFICATION_SOURCE_NAMES = ORBITAL_VERIFICATION_SOURCE_NAMES | {"attitude.py"}
CHAIN_VERIFICATION_SOURCE_NAMES = ATTITUDE_VERIFICATION_SOURCE_NAMES | {"chains.py"}
POWERED_FLIGHT_VERIFICATION_SOURCE_NAMES = CHAIN_VERIFICATION_SOURCE_NAMES | {"powered_flight.py"}
GUIDED_ASCENT_VERIFICATION_SOURCE_NAMES = POWERED_FLIGHT_VERIFICATION_SOURCE_NAMES | {"guided_ascent.py"}
VERIFICATION_SOURCE_NAMES = GUIDED_ASCENT_VERIFICATION_SOURCE_NAMES | {"staged_ascent.py"}
EXCLUSIONS = [
    "Only explicitly declared requirements and bound deterministic models are reviewed.",
    "Physical model validity, uncertainty and environmental qualification are not established by these calculations.",
    "Physical tests, operational performance and whole-mission readiness are not verified by lifecycle-stage metadata.",
    "Subsystem interactions are not inferred from shared names or a passing requirement.",
    "No flight certification or launch authorization is issued.",
    "Record digests detect inconsistency; they are not authenticated signatures or proof of truth.",
]


def _object(value, label):
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be a JSON object with string keys.")
    return value


def _fields(value, required, label, optional=()):
    _object(value, label)
    missing = set(required) - set(value)
    extra = set(value) - set(required) - set(optional)
    if missing or extra:
        raise ValueError(f"{label} has missing fields {sorted(missing)} or unsupported fields {sorted(extra)}.")


def _string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string.")
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite JSON number, not a boolean.")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{label} must be finite.")
    return value


def _strings(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of strings.")
    for item in value:
        _string(item, label)
    return deepcopy(value)


def _digest(value):
    try:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Evidence must be finite JSON-serializable data.") from exc
    return sha256(canonical.encode("utf-8")).hexdigest()


def validate_project(project, *, allow_empty=False):
    """Validate strict shared records and return a caller-independent snapshot.

    No unit conversion, inferred references or arbitrary code execution occurs.
    Unknown model types remain representable so their coverage gaps are visible.
    Workspace authoring may explicitly allow empty model/requirement lists;
    review validation keeps the strict default and still requires both.
    """
    _fields(project, {"schema", "project_id", "name", "revision", "description",
                      "lifecycle_stage", "inputs", "models", "requirements"}, "project", {"systems", "interfaces"})
    if project["schema"] != PROJECT_SCHEMA:
        raise ValueError("Unsupported project schema.")
    for key in ("project_id", "name", "revision", "description", "lifecycle_stage"):
        _string(project[key], f"project.{key}")
    if project["lifecycle_stage"] not in STAGES:
        raise ValueError("Unsupported lifecycle stage.")
    inputs = _object(project["inputs"], "project.inputs")
    for key, record in inputs.items():
        _string(key, "input ID")
        _fields(record, {"value", "unit", "source"}, f"input {key}")
        _number(record["value"], f"input {key}.value")
        _string(record["unit"], f"input {key}.unit")
        _string(record["source"], f"input {key}.source")
    models = project["models"]
    if not isinstance(models, list) or (not models and not allow_empty):
        qualifier = "a list" if allow_empty else "a nonempty list"
        raise ValueError(f"project.models must be {qualifier}.")
    model_ids = set()
    for model in models:
        _fields(model, {"id", "type", "inputs"}, "model", {"description", "links", "accuracy"})
        model_id = _string(model["id"], "model.id")
        _string(model["type"], "model.type")
        if model_id in model_ids:
            raise ValueError(f"Duplicate model ID {model_id}.")
        model_ids.add(model_id)
        if "description" in model:
            _string(model["description"], f"model {model_id}.description")
        if "accuracy" in model:
            if model["type"] != "orbital_trajectory" or model["accuracy"] is None:
                raise ValueError("Only an orbital model may declare a nonempty accuracy criteria object.")
            from .orbital_adapter import validate_accuracy_criteria
            validate_accuracy_criteria(model["accuracy"])
        for parameter, input_id in _object(model["inputs"], "model.inputs").items():
            _string(parameter, "model parameter")
            _string(input_id, "model input reference")
            if input_id not in inputs:
                raise ValueError(f"Model {model_id} refers to missing input {input_id}.")
    from .chains import ordered_models
    ordered_models(project)
    requirements = project["requirements"]
    if not isinstance(requirements, list) or (not requirements and not allow_empty):
        qualifier = "a list" if allow_empty else "a nonempty list"
        raise ValueError(f"project.requirements must be {qualifier}.")
    requirement_ids = set()
    for requirement in requirements:
        _fields(requirement, {"id", "title", "model_id", "metric", "operator",
                              "limit_input", "critical"}, "requirement")
        for key in ("id", "title", "model_id", "metric", "operator", "limit_input"):
            _string(requirement[key], f"requirement.{key}")
        requirement_id = requirement["id"]
        if requirement_id in requirement_ids:
            raise ValueError(f"Duplicate requirement ID {requirement_id}.")
        requirement_ids.add(requirement_id)
        if requirement["model_id"] not in model_ids:
            raise ValueError(f"Requirement {requirement_id} refers to a missing model.")
        if requirement["limit_input"] not in inputs:
            raise ValueError(f"Requirement {requirement_id} refers to a missing limit input.")
        if requirement["operator"] not in {"<=", ">=", "=="}:
            raise ValueError(f"Unsupported comparison operator for {requirement_id}.")
        if not isinstance(requirement["critical"], bool):
            raise ValueError(f"Requirement {requirement_id}.critical must be a boolean.")
    # Optional architecture stays absent from legacy snapshots. It declares
    # organization and review contracts; it never rewrites model bindings.
    if "systems" in project or "interfaces" in project:
        from .systems import validate_architecture
        validate_architecture(project)
    _digest(project)
    return deepcopy(project)


def _versions(versions):
    _object(versions, "adapter_versions")
    for model_type, version in versions.items():
        _string(model_type, "adapter type")
        _string(version, "adapter version")
    return deepcopy(versions)


def _verification_sources():
    """Hash actual maintained verification code; version labels alone can drift."""
    directory = Path(__file__).resolve().parent
    return {name: sha256((directory / name).read_bytes()).hexdigest()
            for name in sorted(VERIFICATION_SOURCE_NAMES)}


def _validate_sources(sources):
    _object(sources, "verification_sources")
    if set(sources) not in (LEGACY_VERIFICATION_SOURCE_NAMES, ORBITAL_VERIFICATION_SOURCE_NAMES, ATTITUDE_VERIFICATION_SOURCE_NAMES, CHAIN_VERIFICATION_SOURCE_NAMES, POWERED_FLIGHT_VERIFICATION_SOURCE_NAMES, GUIDED_ASCENT_VERIFICATION_SOURCE_NAMES, VERIFICATION_SOURCE_NAMES):
        raise ValueError("Verification sources must match a complete maintained or legacy source set.")
    for name, fingerprint in sources.items():
        if not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
            raise ValueError(f"Verification source {name} must have a lowercase SHA-256 digest.")
    return deepcopy(sources)


def _normalize_results(project, results, versions, sources):
    _object(results, "model results")
    models = {model["id"]: model for model in project["models"]}
    if set(results) - set(models):
        raise ValueError("Results include model IDs absent from the project.")
    normalized = {}
    from .chains import ordered_models, resolve, verify_calculation_inputs
    for model in ordered_models(project):
        model_id = model["id"]
        model_type = model["type"]
        version = versions.get(model_type)
        if model_id not in results:
            normalized[model_id] = {
                "model_id": model_id, "model_type": model_type, "model_version": version,
                "status": "not_assessed", "metrics": {}, "assumptions": [],
                "not_assessed": ["No fresh deterministic adapter result was supplied."],
                "issues": [],
            }
            if model.get("links"):
                normalized[model_id]["calculation_inputs"] = resolve(project, model, normalized)[2]
            continue
        result = results[model_id]
        _fields(result, {"model_id", "model_type", "model_version", "status", "metrics",
                         "assumptions", "not_assessed", "issues"}, f"result {model_id}", {"references", "simulation", "power_budget", "attitude_response", "flight_response", "guided_response", "staged_response", "calculation_inputs", "numerical_accuracy", "applicability"})
        if result["model_id"] != model_id or result["model_type"] != model_type:
            raise ValueError(f"Result identity does not match model {model_id}.")
        if result["model_version"] != version:
            raise ValueError(f"Result version does not match maintained adapter {model_id}.")
        _string(result["status"], "result status")
        if result["status"] not in RESULT_STATUSES:
            raise ValueError(f"Unsupported result status for {model_id}.")
        metrics = _object(result["metrics"], f"result {model_id}.metrics")
        for name, metric in metrics.items():
            _string(name, "metric name")
            _fields(metric, {"value", "unit"}, "metric")
            _number(metric["value"], f"metric {name}.value")
            _string(metric["unit"], f"metric {name}.unit")
        for key in ("assumptions", "not_assessed", "issues"):
            _strings(result[key], f"result {model_id}.{key}")
        if "references" in result:
            _strings(result["references"], f"result {model_id}.references")
        if "applicability" in result:
            context = result["applicability"]
            _fields(context, {"schema", "physical_applicability", "scope", "checks", "requires_external_evidence", "references", "reference_disclosure"}, "model applicability")
            if context["schema"] != "sixd.model-applicability.v1" or context["physical_applicability"] != "not_assessed":
                raise ValueError("A reference context cannot assert physical applicability.")
            for key in ("scope", "reference_disclosure"):
                _string(context[key], "applicability " + key)
            for key in ("checks", "requires_external_evidence"):
                _strings(context[key], "applicability " + key)
            if not isinstance(context["references"], list):
                raise ValueError("Applicability references must be a list.")
            for reference in context["references"]:
                _fields(reference, {"title", "url", "kind", "note"}, "applicability reference")
                for value in reference.values():
                    _string(value, "applicability reference field")
                if not reference["url"].startswith("https://"):
                    raise ValueError("Applicability source links require HTTPS.")
        if "numerical_accuracy" in result and (model_type != "orbital_trajectory" or version not in {"2", "3"} or result["status"] != "completed"):
            raise ValueError("Only completed orbital v2/v3 evidence may retain numerical accuracy.")
        if "simulation" in result and (model_type != "orbital_trajectory" or result["status"] != "completed" or version is None):
            raise ValueError("Only a completed maintained orbital model may retain a simulation artifact.")
        if "power_budget" in result and (model_type != "power_energy_budget" or result["status"] != "completed" or version is None):
            raise ValueError("Only a completed maintained power model may retain an operating-mode budget artifact.")
        if "attitude_response" in result and (model_type != "attitude_control" or result["status"] != "completed" or version is None):
            raise ValueError("Only a completed maintained attitude model may retain an attitude response artifact.")
        if "flight_response" in result and (model_type != "powered_flight" or result["status"] != "completed" or version not in {"1", "2"}):
            raise ValueError("Only completed powered-flight v1/v2 evidence may retain a flight response.")
        if "guided_response" in result and (model_type != "guided_ascent" or result["status"] != "completed" or version != "1"):
            raise ValueError("Only completed guided-ascent v1 evidence may retain a guided response.")
        if "staged_response" in result and (model_type != "staged_ascent" or result["status"] != "completed" or version != "1"):
            raise ValueError("Only completed staged-ascent v1 evidence may retain a staged response.")
        if model.get("links") and not CHAIN_VERIFICATION_SOURCE_NAMES.issubset(sources):
            raise ValueError("Linked calculation evidence requires its complete calculation-chain source manifest.")
        bound_project, bound_model = verify_calculation_inputs(project, model, normalized, result)
        if model_type == "powered_flight" and version is not None:
            if result["status"] == "completed":
                if "flight_response" not in result or not POWERED_FLIGHT_VERIFICATION_SOURCE_NAMES.issubset(sources):
                    raise ValueError("Completed powered-flight evidence requires retained response and solver sources.")
                from .engineering import _bind_inputs
                if result["flight_response"].get("solver", {}).get("version", "1") != version:
                    raise ValueError("Powered-flight adapter and solver versions disagree.")
                from .powered_flight import validate_artifact
                validate_artifact(result["flight_response"], metrics, _bind_inputs(bound_project, bound_model), sources["powered_flight.py"])
            elif metrics:
                raise ValueError("Invalid or unassessed powered-flight evidence cannot carry metrics.")
        if model_type == "guided_ascent" and version is not None:
            if result["status"] == "completed":
                if "guided_response" not in result or not GUIDED_ASCENT_VERIFICATION_SOURCE_NAMES.issubset(sources):
                    raise ValueError("Completed guided-ascent evidence requires retained response and solver sources.")
                if result["guided_response"].get("solver", {}).get("version") != version:
                    raise ValueError("Guided-ascent adapter and solver versions disagree.")
                from .engineering import _bind_inputs
                from .guided_ascent import validate_artifact
                validate_artifact(result["guided_response"], metrics, _bind_inputs(bound_project, bound_model), sources["guided_ascent.py"])
            elif metrics:
                raise ValueError("Invalid or unassessed guided-ascent evidence cannot carry metrics.")
        if model_type == "staged_ascent" and version is not None:
            if result["status"] == "completed":
                if "staged_response" not in result or not VERIFICATION_SOURCE_NAMES.issubset(sources):
                    raise ValueError("Completed staged-ascent evidence requires retained response and solver sources.")
                if result["staged_response"].get("solver", {}).get("version") != version:
                    raise ValueError("Staged-ascent adapter and solver versions disagree.")
                from .engineering import _bind_inputs
                from .staged_ascent import validate_artifact
                validate_artifact(result["staged_response"], metrics, _bind_inputs(bound_project,bound_model), sources["staged_ascent.py"])
            elif metrics:
                raise ValueError("Invalid or unassessed staged-ascent evidence cannot carry metrics.")
        if model_type == "attitude_control" and version is not None:
            if result["status"] == "completed":
                if "attitude_response" not in result or not ATTITUDE_VERIFICATION_SOURCE_NAMES.issubset(sources):
                    raise ValueError("Completed attitude evidence requires its response and complete retained solver sources.")
                from .engineering import _bind_inputs
                from .attitude import validate_artifact
                validate_artifact(result["attitude_response"], metrics, _bind_inputs(bound_project, bound_model), sources["attitude.py"])
            elif metrics:
                raise ValueError("Unassessed or invalid attitude evidence cannot carry numerical metrics.")
        if model_type == "power_energy_budget" and version is not None:
            if result["status"] == "completed":
                if "power_budget" not in result:
                    raise ValueError("Completed power evidence requires its operating-mode budget artifact.")
                from .engineering import verify_power_artifact
                verify_power_artifact(result["power_budget"], metrics, bound_project, bound_model)
            elif metrics:
                raise ValueError("Unassessed or invalid power evidence cannot carry numerical metrics.")
        if model_type == "orbital_trajectory" and version is not None:
            if result["status"] == "completed":
                if "simulation" not in result or not ORBITAL_VERIFICATION_SOURCE_NAMES.issubset(sources):
                    raise ValueError("Completed orbital evidence requires a trajectory and complete retained solver sources.")
                from .engineering import _bind_inputs
                from .orbital_adapter import validate_artifact
                validate_artifact(result["simulation"], metrics, _bind_inputs(bound_project, bound_model), sources["simulation.py"])
                expected_method = "rk4" if version == "3" else "velocity_verlet"
                if result["simulation"]["method"]["name"] != expected_method:
                    raise ValueError("Orbital adapter and retained solver version disagree.")
                if version in {"2", "3"}:
                    from .orbital_adapter import validate_accuracy
                    if "numerical_accuracy" not in result:
                        raise ValueError("Completed orbital v2/v3 evidence requires its numerical accuracy receipt.")
                    validate_accuracy(result["numerical_accuracy"], result["simulation"],
                                      _bind_inputs(bound_project, bound_model), model.get("accuracy"), sources["simulation.py"])
            elif metrics:
                raise ValueError("Unassessed or invalid orbital evidence cannot carry numerical metrics.")
        result = deepcopy(result)
        if version is None:
            result["status"] = "not_assessed"
            result["metrics"] = {}
            reason = "No maintained deterministic adapter supports this model type."
            if reason not in result["not_assessed"]:
                result["not_assessed"].append(reason)
        normalized[model_id] = result
    return normalized


def _bound_inputs(project, model):
    from .chains import input_ids
    return {input_id: deepcopy(project["inputs"][input_id])
            for input_id in input_ids(project, model["id"])}


def _assemble(project, results, versions, sources):
    evidence = {}
    models = {model["id"]: model for model in project["models"]}
    for model_id, model in models.items():
        record = deepcopy(results[model_id])
        record["model_definition"] = deepcopy(model)
        record["input_records"] = _bound_inputs(project, model)
        record["verification_sources"] = deepcopy(sources)
        record["fingerprint"] = _digest(record)
        evidence[model_id] = record
    findings = {}
    for requirement in project["requirements"]:
        requirement_id = requirement["id"]
        model = models[requirement["model_id"]]
        receipt = evidence[model["id"]]
        limit = project["inputs"][requirement["limit_input"]]
        dependency_inputs = _bound_inputs(project, model)
        dependency_inputs[requirement["limit_input"]] = deepcopy(limit)
        dependency = {"model_definition": model, "input_records": dependency_inputs,
                      "model_version": receipt["model_version"], "requirement": requirement,
                      "verification_sources": sources}
        if model.get("links"):
            from .chains import dependency_configuration
            dependency["calculation_dependencies"] = dependency_configuration(project, model["id"])
        status = "not_assessed"
        measured = None
        accuracy_gap = None
        if receipt["status"] != "completed":
            reason = f"Model evidence is {receipt['status']}; it cannot satisfy this requirement."
        elif requirement["metric"] not in receipt["metrics"]:
            reason = "The completed adapter did not produce the required metric."
        else:
            metric = receipt["metrics"][requirement["metric"]]
            if metric["unit"] != limit["unit"]:
                reason = "Metric and limit units differ; no implicit conversion is permitted."
            else:
                from .engineering import requirement_accuracy_gap
                accuracy_gap = requirement_accuracy_gap(receipt, requirement, metric, limit)
                if accuracy_gap:
                    reason = accuracy_gap["reason"]
                else:
                    value, threshold = metric["value"], limit["value"]
                    operator = requirement["operator"]
                    passes = {"<=": value <= threshold, ">=": value >= threshold,
                              "==": value == threshold}[operator]
                    status = "met" if passes else "not_met"
                    reason = "Calculated metric meets the declared limit." if passes else "Calculated metric violates the declared limit."
                    measured = {"metric": deepcopy(metric), "operator": operator, "limit": deepcopy(limit)}
        exclusions = deepcopy(receipt["not_assessed"])
        if status == "not_assessed" and reason not in exclusions:
            exclusions.append(reason)
        findings[requirement_id] = {
            "requirement_id": requirement_id, "model_id": model["id"],
            "metric": requirement["metric"], "critical": requirement["critical"],
            "status": status, "reason": reason,
            "dependencies": {"model_id": model["id"], "input_ids": sorted(dependency_inputs)},
            "dependency_fingerprint": _digest(dependency), "evidence": measured,
            "assumptions": deepcopy(receipt["assumptions"]), "not_assessed": exclusions,
        }
        if accuracy_gap:
            findings[requirement_id]["assessment_status"] = accuracy_gap["status"]
    unresolved = sorted(key for key, finding in findings.items() if finding["status"] == "not_assessed")
    failed = sorted(key for key, finding in findings.items() if finding["status"] == "not_met")
    review_status = "incomplete" if unresolved else "requirements_not_met" if failed else "supported_requirements_met"
    report = {
        "schema": REVIEW_SCHEMA, "project_id": project["project_id"], "revision": project["revision"],
        "project": deepcopy(project), "adapter_versions": deepcopy(versions),
        "verification_sources": deepcopy(sources), "evidence": evidence,
        "findings": findings, "review_status": review_status,
        "unresolved_requirements": unresolved, "failed_requirements": failed,
        "exclusions": deepcopy(EXCLUSIONS), "launch_authorization": False,
    }
    report["digest"] = _digest(report)
    return report


def review_project(project, model_results):
    """Bind fresh maintained-adapter results to a validated project snapshot.

    Comparisons use the declared operator exactly, including exact equality.
    Numeric tolerance must be represented by explicit requirement limits, not
    guessed by the assistant. An unresolved requirement takes review precedence
    over a failure, which remains visible in ``failed_requirements``.
    """
    from .engineering import MODEL_VERSIONS
    snapshot = validate_project(project)
    versions = _versions(MODEL_VERSIONS)
    sources = _validate_sources(_verification_sources())
    results = _normalize_results(snapshot, model_results, versions, sources)
    return _assemble(snapshot, results, versions, sources)


def verify_review(review):
    """Return True for internally consistent snapshots, otherwise raise ValueError.

    Recorded adapter versions and code hashes allow old evidence to remain
    inspectable after an adapter upgrade. This verification does not rerun physics or authenticate who
    generated the record; externally recomputed forged digests are not prevented.
    """
    _fields(review, {"schema", "project_id", "revision", "project", "adapter_versions",
                     "verification_sources",
                     "evidence", "findings", "review_status", "unresolved_requirements",
                     "failed_requirements", "exclusions", "launch_authorization", "digest"}, "review")
    if review["schema"] != REVIEW_SCHEMA:
        raise ValueError("Unsupported review schema.")
    _string(review["digest"], "review digest")
    body = {key: value for key, value in review.items() if key != "digest"}
    if _digest(body) != review["digest"]:
        raise ValueError("Review digest does not match its contents.")
    project = validate_project(review["project"])
    versions = _versions(review["adapter_versions"])
    sources = _validate_sources(review["verification_sources"])
    _object(review["evidence"], "review evidence")
    results = {}
    for model_id, record in review["evidence"].items():
        _fields(record, {"model_id", "model_type", "model_version", "status", "metrics",
                         "assumptions", "not_assessed", "issues", "model_definition",
                         "input_records", "verification_sources", "fingerprint"}, "evidence receipt", {"references", "simulation", "power_budget", "attitude_response", "flight_response", "guided_response", "staged_response", "calculation_inputs", "numerical_accuracy", "applicability"})
        results[model_id] = {key: deepcopy(value) for key, value in record.items()
                             if key not in {"model_definition", "input_records", "verification_sources", "fingerprint"}}
    expected = _assemble(project, _normalize_results(project, results, versions, sources), versions, sources)
    if expected != review:
        raise ValueError("Review evidence, dependencies or findings do not match their snapshots.")
    return True


def compare_reviews(old, new):
    """Compare explicit dependency applicability without mutating old reports.

    Unbound physical interactions are not inferred. A same-input result change is
    reported separately and does not imply a configuration dependency changed.
    """
    verify_review(old)
    verify_review(new)
    if old["project_id"] != new["project_id"]:
        raise ValueError("Reviews from different projects cannot be compared.")

    def differences(before, after):
        shared = set(before) & set(after)
        return (sorted(key for key in shared if before[key] != after[key]),
                sorted(set(after) - set(before)), sorted(set(before) - set(after)))

    changed_inputs, added_inputs, removed_inputs = differences(old["project"]["inputs"], new["project"]["inputs"])
    old_models = {model["id"]: model for model in old["project"]["models"]}
    new_models = {model["id"]: model for model in new["project"]["models"]}
    changed_models, added_models, removed_models = differences(old_models, new_models)
    version_changes = sorted(key for key in set(old_models) & set(new_models)
                             if old["evidence"][key]["model_version"] != new["evidence"][key]["model_version"])
    changed_models = sorted(set(changed_models) | set(version_changes))
    old_requirements = {item["id"]: item for item in old["project"]["requirements"]}
    new_requirements = {item["id"]: item for item in new["project"]["requirements"]}
    changed_requirements, added_requirements, removed_requirements = differences(old_requirements, new_requirements)
    recheck, unchanged, unassessed = [], [], []
    for key in sorted(set(old_requirements) & set(new_requirements)):
        before, after = old["findings"][key], new["findings"][key]
        if before["dependency_fingerprint"] != after["dependency_fingerprint"]:
            recheck.append(key)
        elif before["status"] != "not_assessed":
            unchanged.append(key)
        else:
            unassessed.append(key)
    changed_evidence = sorted(key for key in set(old["evidence"]) & set(new["evidence"])
                              if old["evidence"][key]["fingerprint"] != new["evidence"][key]["fingerprint"])
    changed_sources = sorted(name for name in set(old["verification_sources"]) | set(new["verification_sources"])
                             if old["verification_sources"].get(name) != new["verification_sources"].get(name))
    comparison = {
        "schema": "sixd.review-comparison.v1", "project_id": old["project_id"],
        "from_revision": old["revision"], "to_revision": new["revision"],
        "changed_inputs": changed_inputs, "added_inputs": added_inputs, "removed_inputs": removed_inputs,
        "changed_models": changed_models, "added_models": added_models, "removed_models": removed_models,
        "changed_model_versions": version_changes,
        "verification_sources_changed": changed_sources,
        "changed_requirements": changed_requirements, "added_requirements": added_requirements,
        "removed_requirements": removed_requirements,
        "previous_evidence_needs_rechecking": recheck,
        "unchanged_evidence_applicability": unchanged,
        "unchanged_unassessed_requirements": unassessed, "changed_evidence": changed_evidence,
        "exclusions": ["Impact is derived only from explicit model/input/requirement bindings.",
                       "Unchanged applicability does not establish model validity or whole-mission readiness."],
    }
    if any(key in project for project in (old["project"], new["project"]) for key in ("systems", "interfaces")):
        from .systems import architecture_impact
        comparison.update(architecture_impact(old["project"], new["project"],
            changed_input_ids=changed_inputs + added_inputs + removed_inputs,
            changed_model_ids=changed_models + added_models + removed_models,
            sources_changed=bool(changed_sources)))
    return comparison
