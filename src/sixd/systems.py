"""Explicit project architecture and scalar interface-contract review.

These functions never execute adapters, feed an output into another model, or
infer physical coupling. A contract compares a declared/recorded scalar with an
explicit project input. Its verdict is separate from canonical requirements.
"""
from collections import defaultdict, deque
from copy import deepcopy
import json
import math


MAX_SYSTEMS = 64
MAX_INTERFACES = 128
INTERFACE_SCHEMA = "sixd.interface-checks.v1"
LIMITATIONS = [
    "Interfaces are explicit scalar declarations; their physical meaning and completeness are not validated.",
    "A source input is a supplied declaration, not independently calculated or measured evidence.",
    "Only a current matching maintained review supplies model metrics; no adapter runs during this projection.",
    "Units must match exactly; no conversion, vector mapping, frame transformation or implicit tolerance occurs.",
    "Connections flag dependencies for review; they do not feed values to models or solve coupled physics.",
    "Interface results do not replace canonical requirement findings or issue launch authorization.",
]


def _text(value, label, *, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"{label} must be {'a' if empty else 'a nonempty'} string.")
    if len(value) > 4096:
        raise ValueError(f"{label} is too long (maximum 4096 characters).")
    return value


def _fields(record, expected, label):
    if not isinstance(record, dict) or set(record) != set(expected):
        raise ValueError(f"{label} must contain exactly {sorted(expected)}.")


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _same(left, right):
    # JSON equality preserves booleans versus numbers and explicit definitions.
    return _encode(left) == _encode(right)


def _indexes(project):
    if not isinstance(project, dict):
        raise ValueError("Project architecture requires a project object.")
    systems = project.get("systems", [])
    interfaces = project.get("interfaces", [])
    if not isinstance(systems, list) or len(systems) > MAX_SYSTEMS:
        raise ValueError(f"project.systems must be a list of at most {MAX_SYSTEMS} systems.")
    if not isinstance(interfaces, list) or len(interfaces) > MAX_INTERFACES:
        raise ValueError(f"project.interfaces must be a list of at most {MAX_INTERFACES} interfaces.")
    models = project.get("models", [])
    inputs = project.get("inputs", {})
    requirements = project.get("requirements", [])
    if not isinstance(models, list) or not isinstance(inputs, dict) or not isinstance(requirements, list):
        raise ValueError("Project models, inputs and requirements must use their declared collection types.")
    model_map = {}
    for model in models:
        if not isinstance(model, dict) or not isinstance(model.get("id"), str) or model["id"] in model_map:
            raise ValueError("Project models must have unique string IDs.")
        model_map[model["id"]] = model
    system_map = {}
    owner = {}
    for system in systems:
        _fields(system, {"id", "title", "description", "parent_id", "model_ids"}, "system")
        for key in ("id", "title"):
            _text(system[key], f"system.{key}")
        _text(system["description"], "system.description", empty=True)
        system_id = system["id"]
        if system_id in system_map:
            raise ValueError(f"Duplicate system ID {system_id}.")
        system_map[system_id] = system
        if system["parent_id"] is not None:
            _text(system["parent_id"], f"system {system_id}.parent_id")
        if not isinstance(system["model_ids"], list):
            raise ValueError(f"system {system_id}.model_ids must be a list.")
        for model_id in system["model_ids"]:
            _text(model_id, "system model ID")
            if model_id not in model_map:
                raise ValueError(f"System {system_id} refers to missing model {model_id}.")
            if model_id in owner:
                raise ValueError(f"Model {model_id} is assigned more than once; each model may have only one owner.")
            owner[model_id] = system_id
    for system_id, system in system_map.items():
        parent = system["parent_id"]
        if parent is not None and parent not in system_map:
            raise ValueError(f"System {system_id} refers to missing parent {parent}.")
    for system_id, system in system_map.items():
        parent = system["parent_id"]
        seen = {system_id}
        while parent is not None:
            if parent in seen:
                raise ValueError("System parent hierarchy contains a cycle.")
            seen.add(parent)
            parent = system_map[parent]["parent_id"]
    return system_map, interfaces, model_map, inputs, requirements, owner


def _descendants(system_map, root):
    children = defaultdict(list)
    for system_id, system in system_map.items():
        children[system["parent_id"]].append(system_id)
    found, pending = set(), [root]
    while pending:
        item = pending.pop()
        if item in found:
            continue
        found.add(item)
        pending.extend(children[item])
    return found


def validate_architecture(project):
    """Validate optional architecture fields without adding defaults or mutation.

    Core project records are validated by lifecycle.validate_project. This
    independent function avoids recursion when that validator calls us.
    """
    systems, interfaces, models, inputs, _, owners = _indexes(project)
    interface_ids = set()
    for interface in interfaces:
        _fields(interface, {"id", "title", "description", "from_system", "to_system",
                            "source", "target_input", "quantity", "unit", "operator", "critical"},
                "interface")
        for key in ("id", "title", "from_system", "to_system", "target_input", "quantity", "unit", "operator"):
            _text(interface[key], f"interface.{key}")
        _text(interface["description"], "interface.description", empty=True)
        interface_id = interface["id"]
        if interface_id in interface_ids:
            raise ValueError(f"Duplicate interface ID {interface_id}.")
        interface_ids.add(interface_id)
        for endpoint in ("from_system", "to_system"):
            if interface[endpoint] not in systems:
                raise ValueError(f"Interface {interface_id} refers to missing {endpoint}.")
        if interface["from_system"] == interface["to_system"]:
            raise ValueError(f"Interface {interface_id} must connect different systems.")
        if interface["target_input"] not in inputs:
            raise ValueError(f"Interface {interface_id} refers to missing target input.")
        if interface["operator"] not in {"<=", ">=", "=="}:
            raise ValueError(f"Interface {interface_id} has an unsupported operator.")
        if not isinstance(interface["critical"], bool):
            raise ValueError(f"Interface {interface_id}.critical must be a boolean.")
        source = interface["source"]
        if not isinstance(source, dict):
            raise ValueError(f"Interface {interface_id}.source must be an object.")
        if source.get("kind") == "input":
            _fields(source, {"kind", "input_id"}, "interface input source")
            _text(source["input_id"], "interface source.input_id")
            if source["input_id"] not in inputs:
                raise ValueError(f"Interface {interface_id} refers to missing source input.")
        elif source.get("kind") == "model_metric":
            _fields(source, {"kind", "model_id", "metric"}, "interface model source")
            _text(source["model_id"], "interface source.model_id")
            _text(source["metric"], "interface source.metric")
            if source["model_id"] not in models:
                raise ValueError(f"Interface {interface_id} refers to missing source model.")
            allowed = _descendants(systems, interface["from_system"])
            if owners.get(source["model_id"]) not in allowed:
                raise ValueError(f"Interface {interface_id} source model must belong to its source system subtree.")
        else:
            raise ValueError(f"Interface {interface_id} has an unsupported source kind.")
    return None


def systems_graph(project):
    """Return declared system rows, preserving caller order and tree ownership."""
    validate_architecture(project)
    systems, _, _, _, requirements, _ = _indexes(project)
    rows = []
    for system_id, system in systems.items():
        descendants = _descendants(systems, system_id)
        model_ids = sorted({model_id for child in descendants for model_id in systems[child]["model_ids"]})
        rows.append({"id": "subsystem:" + system_id, "title": system["title"],
                     "parent_id": "subsystem:" + system["parent_id"] if system["parent_id"] is not None else None,
                     "model_ids": model_ids, "own_model_ids": deepcopy(system["model_ids"]),
                     "requirement_ids": sorted(item["id"] for item in requirements if item["model_id"] in model_ids),
                     "description": system["description"], "declared": True})
    return rows


def _current_review(project, review):
    if review is None:
        return None, "No current matching reviewed model evidence was supplied."
    try:
        from .lifecycle import verify_review, _verification_sources
        from .engineering import MODEL_VERSIONS
        verify_review(review)
        if not _same(review["project"], project):
            return None, "The supplied review belongs to a different project configuration or revision."
        if review["verification_sources"] != _verification_sources() or review["adapter_versions"] != MODEL_VERSIONS:
            return None, "The supplied review uses historical verifier sources or adapter versions."
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return None, "The supplied review could not be verified as internally consistent."
    return review, None


def _numeric(record):
    if not isinstance(record, dict) or not isinstance(record.get("unit"), str):
        return False
    value = record.get("value")
    try:
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        return False


def evaluate_interfaces(project, review=None, *, draft=False):
    """Project explicit scalar contracts, with no numerical conclusions in drafts."""
    if not isinstance(draft, bool):
        raise ValueError("draft must be a boolean.")
    validate_architecture(project)
    _, interfaces, models, inputs, _, _ = _indexes(project)
    checked, review_reason = _current_review(project, review) if not draft else (None, None)
    rows = []
    counts = {"met": 0, "not_met": 0, "not_assessed": 0, "total": len(interfaces)}
    for contract in interfaces:
        row = deepcopy(contract)
        source = contract["source"]
        target = deepcopy(inputs[contract["target_input"]])
        dependency_ids = {contract["target_input"]}
        source_value, source_origin, issues = None, None, []
        if source["kind"] == "input":
            dependency_ids.add(source["input_id"])
            supplied = inputs[source["input_id"]]
            source_origin = {"kind": "declared_input", "input_id": source["input_id"],
                             "source": supplied.get("source")}
            if _numeric(supplied):
                source_value = {"value": supplied["value"], "unit": supplied["unit"]}
            else:
                issues.append({"code": "invalid_source_value", "message": "The source input is not a finite numeric scalar."})
        else:
            dependency_ids.update(models[source["model_id"]]["inputs"].values())
            if not draft:
                if checked is None:
                    issues.append({"code": "review_unavailable", "message": review_reason})
                else:
                    evidence = checked["evidence"].get(source["model_id"], {})
                    source_origin = {"kind": "reviewed_model_metric", "model_id": source["model_id"],
                                     "metric": source["metric"], "review_digest": checked["digest"],
                                     "evidence_fingerprint": evidence.get("fingerprint")}
                    metric = evidence.get("metrics", {}).get(source["metric"])
                    from .engineering import evidence_accuracy_gap, requirement_accuracy_gap
                    accuracy_gap = evidence_accuracy_gap(evidence)
                    if accuracy_gap is None and _numeric(metric) and _numeric(target):
                        accuracy_gap = requirement_accuracy_gap(evidence,
                            {"metric": source["metric"], "operator": contract["operator"]}, metric, target)
                    if evidence.get("status") != "completed":
                        issues.append({"code": "model_unassessed", "message": "The source model did not complete a supported calculation."})
                    elif accuracy_gap:
                        issues.append({"code": accuracy_gap["status"], "message": accuracy_gap["reason"]})
                    elif not _numeric(metric):
                        issues.append({"code": "metric_unavailable", "message": "The completed source model does not supply this finite scalar metric."})
                    else:
                        source_value = deepcopy(metric)
        if not _numeric(target):
            issues.append({"code": "invalid_target_value", "message": "The target input is not a finite numeric scalar."})
        mismatches = []
        if target.get("unit") != contract["unit"]:
            mismatches.append("target input")
        if source_value is not None and source_value["unit"] != contract["unit"]:
            mismatches.append("source value")
        if mismatches:
            issues.append({"code": "unit_mismatch", "message": "Exact contract units differ from " + " and ".join(mismatches) + "; no conversion is applied."})
        if draft:
            issues.append({"code": "draft_no_verdict", "message": "Draft architecture has no numeric interface verdict; save it before checking contracts."})
        if issues or source_value is None:
            status = "not_assessed"
            reason = " ".join(issue["message"] for issue in issues) or "No supported scalar source is available."
        else:
            actual, limit = source_value["value"], target["value"]
            passes = {"<=": actual <= limit, ">=": actual >= limit, "==": actual == limit}[contract["operator"]]
            status = "met" if passes else "not_met"
            origin = "Declared source value" if source["kind"] == "input" else "Recorded model metric"
            reason = origin + (" meets" if passes else " violates") + " the declared scalar interface comparison."
        row.update(status=status, reason=reason, source_value=source_value, target_value=target,
                   source_kind=source["kind"], source_origin=source_origin,
                   dependency_input_ids=sorted(dependency_ids), issues=issues)
        rows.append(row)
        counts[status] += 1
    return {"schema": INTERFACE_SCHEMA, "rows": rows, "counts": counts, "limitations": deepcopy(LIMITATIONS)}


def architecture_impact(before, after, changed_input_ids=(), changed_model_ids=(), sources_changed=False):
    """Conservatively flag interface review across both old and new topology.

    Review propagation is finite even when interface edges form cycles. This
    does not change canonical model execution/reuse or any numerical verdict.
    """
    validate_architecture(before)
    validate_architecture(after)
    old_systems, old_interfaces, old_models, old_inputs, old_requirements, old_owners = _indexes(before)
    new_systems, new_interfaces, new_models, new_inputs, new_requirements, new_owners = _indexes(after)
    old_links = {item["id"]: item for item in old_interfaces}
    new_links = {item["id"]: item for item in new_interfaces}

    def differences(old, new):
        return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
                "changed": sorted(key for key in old.keys() & new.keys() if not _same(old[key], new[key]))}

    system_changes = differences(old_systems, new_systems)
    interface_changes = differences(old_links, new_links)
    input_changes = differences(old_inputs, new_inputs)
    model_changes = differences(old_models, new_models)
    touched_inputs = set(changed_input_ids)
    touched_models = set(changed_model_ids)
    touched_systems = set()
    for values in input_changes.values():
        touched_inputs.update(values)
    for values in model_changes.values():
        touched_models.update(values)
    for values in system_changes.values():
        touched_systems.update(values)
    for model_id, model in list(old_models.items()) + list(new_models.items()):
        if touched_inputs.intersection(model["inputs"].values()):
            touched_models.add(model_id)
    links = list(old_links.values()) + list(new_links.values())
    by_source = defaultdict(list)
    for link in links:
        by_source[link["from_system"]].append(link)
    children, parents = defaultdict(set), defaultdict(set)
    for collection in (old_systems, new_systems):
        for system_id, system in collection.items():
            if system["parent_id"] is not None:
                children[system["parent_id"]].add(system_id)
                parents[system_id].add(system["parent_id"])
    affected = set()
    review_systems = set()
    reasons, reason_keys = [], set()

    def reason(code, *, interface_id=None, system_id=None, message):
        key = (code, interface_id, system_id, message)
        if key not in reason_keys:
            reason_keys.add(key)
            reasons.append({"code": code, "interface_id": interface_id, "system_id": system_id, "message": message})

    def hierarchy_scope(system_id, direction):
        # Combining two individually valid trees may introduce cycles when a
        # system was reparented. Visit each ID once in this conservative union.
        result, queue = set(), [system_id]
        while queue:
            current = queue.pop()
            if current not in result:
                result.add(current)
                queue.extend(direction[current])
        return result

    pending = deque()

    def seed_system(system_id, code, message):
        # Receiving a parent also puts every contained system in review. Those
        # descendants' outgoing contracts must propagate, rather than merely
        # being added to the final display after traversal has already ended.
        descendants = hierarchy_scope(system_id, children)
        review_systems.update(descendants)
        for descendant in sorted(descendants):
            # A changed child can also affect a parent-exposed contract.
            pending.extend(sorted(hierarchy_scope(descendant, parents)))
            if descendant != system_id:
                reason("descendant_system_review", system_id=descendant,
                       message=f"Contained system needs review because receiving/changed system {system_id} is affected.")
        reason(code, system_id=system_id, message=message)

    def seed_link(link, code, message):
        affected.add(link["id"])
        reason(code, interface_id=link["id"], message=message)
        seed_system(link["to_system"], "downstream_interface", "Declared receiving system needs interface applicability review.")

    for system_id in sorted(touched_systems):
        seed_system(system_id, "system_definition_changed", "System hierarchy, ownership or metadata changed in the declared architecture.")
    for model_id in sorted(touched_models):
        for owners in (old_owners, new_owners):
            if model_id in owners:
                seed_system(owners[model_id], "model_dependency_changed", f"Model {model_id} or one of its declared inputs changed.")
    changed_links = set().union(*interface_changes.values())
    for link in links:
        source = link["source"]
        source_dependencies = ({source["input_id"]} if source["kind"] == "input" else
                               set(old_models.get(source["model_id"], {}).get("inputs", {}).values()) |
                               set(new_models.get(source["model_id"], {}).get("inputs", {}).values()))
        if link["id"] in changed_links:
            seed_link(link, "interface_definition_changed", "Interface was added, removed or changed; both recorded topologies are reviewed.")
        if sources_changed:
            seed_link(link, "verification_sources_changed", "Maintained sources changed; interface evidence needs review.")
        if touched_inputs.intersection(source_dependencies | {link["target_input"]}):
            seed_link(link, "interface_input_changed", "A declared source dependency or receiving limit/input changed.")
        if source["kind"] == "model_metric" and source["model_id"] in touched_models:
            seed_link(link, "interface_model_changed", "The declared source model changed or needs a canonical recheck.")
    visited = set()
    while pending:
        system_id = pending.popleft()
        if system_id in visited:
            continue
        visited.add(system_id)
        for link in by_source[system_id]:
            seed_link(link, "downstream_dependency", "Review propagates along an explicit interface edge; no physical outcome is inferred.")
    review_models = {model_id for collection in (old_systems, new_systems)
                     for system_id in review_systems if system_id in collection
                     for model_id in collection[system_id]["model_ids"]}
    review_requirements = {item["id"] for item in old_requirements + new_requirements if item["model_id"] in review_models}
    result = {f"{kind}_systems": system_changes[kind] for kind in ("added", "removed", "changed")}
    result.update({f"{kind}_interfaces": interface_changes[kind] for kind in ("added", "removed", "changed")})
    result.update(affected_interface_ids=sorted(affected), interface_review_system_ids=sorted(review_systems),
                  interface_review_model_ids=sorted(review_models), interface_review_requirement_ids=sorted(review_requirements),
                  reasons=sorted(reasons, key=lambda row: (row["interface_id"] or "", row["system_id"] or "", row["code"], row["message"])))
    return result
