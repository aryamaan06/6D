"""Explicit, acyclic scalar assignments between maintained calculations.

No conversion, inferred physics, interpolation or fixed-point iteration occurs.
The rationale is a supplied load-case/applicability declaration, not validation.
History checks reconstruct bindings and digests without executing a solver.
"""
from copy import deepcopy
from hashlib import sha256
import json
import math

MAX_MODELS = 128
MAX_LINKS = 1024
MAX_DEPTH = 64


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def parameter_units(model):
    from .engineering import MODEL_PARAMETERS, power_parameters
    bindings = {**model.get("inputs", {}), **model.get("links", {})}
    if model["type"] == "power_energy_budget":
        return power_parameters(bindings)
    if model["type"] == "staged_ascent":
        from .staged_ascent import parameter_units as staged_units
        return staged_units(bindings)
    return MODEL_PARAMETERS.get(model["type"], {})


def metric_units(model):
    from .project_authoring import _MODEL_DETAILS
    details = _MODEL_DETAILS.get(model["type"])
    return {name: unit for name, unit, _ in details[2]} if details else {}


def ordered_models(project):
    """Validate link contracts and return stable topological model order."""
    models = project["models"]
    indexed = {model["id"]: model for model in models}
    if len(indexed) != len(models):
        raise ValueError("Duplicate model IDs in calculation graph.")
    if not any("links" in model for model in models):
        return list(models)
    if len(models) > MAX_MODELS:
        raise ValueError(f"Calculation chains support at most {MAX_MODELS} models.")
    dependencies = {identity: set() for identity in indexed}
    count = 0
    for model in models:
        links = model.get("links", {})
        if not isinstance(links, dict) or any(not isinstance(role, str) or not role.strip() for role in links):
            raise ValueError("Model links must be an object of nonempty parameter roles.")
        if set(links).intersection(model["inputs"]):
            raise ValueError("A parameter cannot have both a direct input and a calculation link.")
        if not links:
            continue
        expected = parameter_units(model)
        for role, link in links.items():
            count += 1
            if count > MAX_LINKS:
                raise ValueError(f"Calculation chains support at most {MAX_LINKS} links.")
            if role not in expected:
                raise ValueError(f"Unsupported linked parameter {model['id']}.{role}.")
            if not isinstance(link, dict) or set(link) != {"model_id", "metric", "unit", "rationale"}:
                raise ValueError("Each calculation link requires model_id, metric, unit and rationale.")
            if any(not isinstance(value, str) or not value.strip() for value in link.values()):
                raise ValueError("Calculation link fields must be nonempty strings, including a physical/load-case rationale.")
            if len(link["rationale"]) > 4000:
                raise ValueError("Calculation link rationale exceeds 4000 characters.")
            source = indexed.get(link["model_id"])
            if source is None:
                raise ValueError(f"Calculation link refers to missing source model {link['model_id']}.")
            units = metric_units(source)
            if link["metric"] not in units:
                raise ValueError(f"Source model does not support linked metric {link['metric']}.")
            if link["unit"] != expected[role] or units[link["metric"]] != link["unit"]:
                raise ValueError(f"Calculation link unit mismatch for {model['id']}.{role}; no conversion is performed.")
            dependencies[model["id"]].add(source["id"])
    ordered, depth, remaining = [], {}, set(indexed)
    while remaining:
        available = [identity for identity in indexed if identity in remaining and not dependencies[identity].intersection(remaining)]
        if not available:
            raise ValueError("Calculation links contain a cycle; coupled iterative execution is unsupported.")
        for identity in available:
            depth[identity] = 1 + max((depth[source] for source in dependencies[identity]), default=0)
            if depth[identity] > MAX_DEPTH:
                raise ValueError(f"Calculation dependency depth exceeds {MAX_DEPTH} models.")
            ordered.append(indexed[identity])
            remaining.remove(identity)
    return ordered


def ancestor_ids(project, model_id):
    models = {model["id"]: model for model in project["models"]}
    if model_id not in models:
        raise ValueError("Calculation model is absent from project.")
    found, pending = set(), [model_id]
    while pending:
        identity = pending.pop()
        for link in models[identity].get("links", {}).values():
            source = link["model_id"]
            if source not in models:
                raise ValueError("Calculation source is absent from project.")
            if source == model_id:
                raise ValueError("Calculation dependency cycle.")
            if source not in found:
                found.add(source)
                pending.append(source)
    return sorted(found)


def input_ids(project, model_id):
    ids = set(ancestor_ids(project, model_id)) | {model_id}
    return sorted({identity for model in project["models"] if model["id"] in ids
                   for identity in model["inputs"].values()})


def dependency_configuration(project, model_id):
    identities = set(ancestor_ids(project, model_id)) | {model_id}
    return {"models": {model["id"]: deepcopy(model) for model in project["models"] if model["id"] in identities},
            "input_records": {identity: deepcopy(project["inputs"][identity]) for identity in input_ids(project, model_id)}}


def dependency_fingerprint(project, model_id):
    return digest(dependency_configuration(project, model_id))


def ancestor_project(project, model_id):
    identities = set(ancestor_ids(project, model_id)) | {model_id}
    result = deepcopy(project)
    result["models"] = [model for model in ordered_models(project) if model["id"] in identities]
    result["requirements"] = [item for item in result.get("requirements", []) if item["model_id"] in identities]
    result.pop("systems", None)
    result.pop("interfaces", None)
    return result


def resolve(project, model, results):
    """Return ephemeral direct-bound inputs, provenance and unavailable roles.

    Original model/input records never change. A failed engineering requirement
    does not invalidate its completed source calculation.
    """
    if not model.get("links"):
        return project, model, None, []
    local_project = {**project, "inputs": deepcopy(project["inputs"])}
    local_model = deepcopy(model)
    local_model.pop("links", None)
    values = {role: {"value": project["inputs"][identity]["value"], "unit": project["inputs"][identity]["unit"]}
              for role, identity in model["inputs"].items()}
    links, ancestors, unavailable = {}, {}, []
    indexed = {item["id"]: item for item in project["models"]}
    for identity in ancestor_ids(project, model["id"]):
        source_model = indexed[identity]
        ancestors[identity] = {"model_definition": deepcopy(source_model),
            "input_records": {key: deepcopy(project["inputs"][key]) for key in sorted(set(source_model["inputs"].values()))},
            "result_digest": digest(results[identity]) if identity in results else None,
            "dependency_fingerprint": dependency_fingerprint(project, identity)}
    for role, link in sorted(model["links"].items()):
        source = results.get(link["model_id"])
        metric = source.get("metrics", {}).get(link["metric"]) if source else None
        status = source.get("status", "unavailable") if source else "unavailable"
        valid = (status == "completed" and isinstance(metric, dict) and set(metric) == {"value", "unit"}
                 and metric["unit"] == link["unit"] and isinstance(metric["value"], (float, int))
                 and not isinstance(metric["value"], bool))
        if source is not None:
            from .engineering import evidence_accuracy_gap
            accuracy_gap = evidence_accuracy_gap(source)
            if accuracy_gap is not None:
                valid = False
                status = accuracy_gap["status"]
        if valid:
            try:
                valid = math.isfinite(metric["value"])
            except OverflowError:
                valid = False
        if status == "completed" and not valid:
            status = "metric_unavailable"
        links[role] = {**deepcopy(link), "source_result_digest": digest(source) if source is not None else None,
                       "source_dependency_fingerprint": dependency_fingerprint(project, link["model_id"]), "status": status}
        if not valid:
            unavailable.append(role)
            continue
        values[role] = deepcopy(metric)
        synthetic = "__sixd_calculation_link_" + role
        while synthetic in local_project["inputs"]:
            synthetic = "_" + synthetic
        local_project["inputs"][synthetic] = {**deepcopy(metric), "source": "Explicit calculation link: " + link["rationale"]}
        local_model["inputs"][role] = synthetic
    record = {"schema": "sixd.calculation-inputs.v1", "dependency_fingerprint": dependency_fingerprint(project, model["id"]),
              "values": values, "links": links, "ancestors": ancestors}
    return local_project, local_model, record, unavailable


def verify_calculation_inputs(project, model, results, result):
    local_project, local_model, expected, unavailable = resolve(project, model, results)
    if expected is None:
        if "calculation_inputs" in result:
            raise ValueError("Unlinked model cannot retain calculation-link provenance.")
    elif digest(result.get("calculation_inputs")) != digest(expected):
        raise ValueError("Calculation-link inputs/provenance disagree with the retained source results and project configuration.")
    if unavailable and (result["status"] != "not_assessed" or result["metrics"]):
        raise ValueError("Unavailable calculation source must leave downstream evidence unassessed without metrics.")
    return local_project, local_model
