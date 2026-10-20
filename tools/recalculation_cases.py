"""Seeded, finite JSON revision edits for incremental/full recomputation checks.

These are constructed software-verification cases, not independent validation of
the engineering equations. ``expected_valid`` describes the strict project
schema/graph contract only. Some accepted projects deliberately contain units or
numerical domains that calculators must leave invalid/unassessed. Cases carry
their complete before/after snapshots so a result remains reproducible without
depending on a later random-number-generator state.

No model, workspace, inference provider or database is executed/imported here.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import random


DEFAULT_SEED = 20261019
DEFAULT_COUNT = 1000
_ROOT = Path(__file__).resolve().parents[1]
_FAMILIES = (
    "ideal_propulsion", "static_cantilever", "radiative_equilibrium",
    "drag_load", "orbital_trajectory", "power_energy_budget",
    "attitude_control", "calculation_chains",
)
_FOCUS = {
    "ideal_propulsion": ("propulsion", "specific_impulse"),
    "static_cantilever": ("mount", "young_modulus"),
    "radiative_equilibrium": ("thermal", "heat_input"),
    "drag_load": ("atmospheric_load", "relative_speed"),
    "orbital_trajectory": ("orbit", "duration_s"),
    "power_energy_budget": ("electrical_budget", "usable_battery_energy"),
    "attitude_control": ("pointing", "inertia"),
}
_COMMON = (
    "numeric_input", "input_source", "input_unit", "input_remap",
    "model_description", "requirement_threshold", "requirement_operator",
    "requirement_metadata", "requirement_add", "requirement_remove",
    "model_reorder", "input_add_unused", "input_remove_unused",
    "numeric_representation_noop", "multi_input_edit", "model_add",
    "model_remove", "missing_bound_input", "dangling_requirement_model",
    "duplicate_model", "invalid_requirement_operator", "boolean_input",
    "empty_input_source", "exact_noop", "requirement_limit_unit",
    "unknown_requirement_metric", "unknown_project_field", "limit_remap",
    "unsupported_model", "missing_limit_input", "project_metadata",
    "sequential_edit_snapshot",
)
_CHAIN = (
    "upstream_numeric", "upstream_source", "rationale_change",
    "link_remove_to_literal", "link_add_from_literal", "source_rewire",
    "metric_rewire", "link_unit_mismatch", "link_cycle", "dangling_link",
    "link_direct_collision", "unknown_link_metric", "empty_link_rationale",
    "source_model_delete", "upstream_domain_gap", "upstream_unit_gap",
    "multihop_numeric", "fanout_numeric", "same_output_new_sources",
    "linked_numeric_representation", "linked_model_reorder",
    "linked_threshold", "multihop_rewire", "sequential_chain_snapshot",
    "linked_input_remap", "remove_link_leave_unbound", "upstream_description",
    "independent_branch_edit", "source_requirement_fail", "source_unknown_type",
    "unknown_link_role", "link_extra_field",
)


def _load(name):
    return json.loads((_ROOT / "examples" / name).read_text(encoding="utf-8"))


def _record(value, unit, source="Constructed seeded software-verification input; not flight data."):
    return {"value": value, "unit": unit, "source": source}


def _models(project):
    return {item["id"]: item for item in project["models"]}


def _without_architecture(project):
    # These cases exercise calculation reuse. Interface-result projections have
    # their own tests and are not silently credited as covered by this corpus.
    project.pop("systems", None)
    project.pop("interfaces", None)
    return project


def _templates():
    base = _load("design-baseline.json")
    power = _without_architecture(_load("power-energy-reference.project.json"))
    attitude = _load("attitude-reference.project.json")
    # Small but valid fixed grids keep 1000 software-edit checks practical.
    # They do not replace higher-resolution independent physical benchmarks.
    attitude["inputs"]["duration"]["value"] = 2
    attitude["inputs"]["steps"]["value"] = 64
    attitude["inputs"]["assessment_start"]["value"] = 1
    orbital = deepcopy(attitude)
    orbital.update(name="Constructed short two-body verification case",
                   description="Short unforced circular reference for software edit verification only.")
    orbital["models"] = [deepcopy(_models(base)["thermal"])]
    orbital["requirements"] = [deepcopy(next(r for r in base["requirements"] if r["model_id"] == "thermal"))]
    mu, radius = 398600441800000.0, 7000000.0
    parameters = {
        "mu_m3_s2": (mu, "m^3/s^2"), "exclusion_radius_m": (6371000, "m"),
        "position_x": (radius, "m"), "position_y": (0, "m"), "position_z": (0, "m"),
        "velocity_x": (0, "m/s"), "velocity_y": (math.sqrt(mu / radius), "m/s"),
        "velocity_z": (0, "m/s"), "duration_s": (120, "s"), "steps": (32, "1"),
    }
    orbital["inputs"].update({key: _record(*value) for key, value in parameters.items()})
    orbital["inputs"]["minimum_radius"] = _record(6900000, "m")
    orbital["inputs"]["maximum_radius"] = _record(7100000, "m")
    orbital["models"].insert(0, {"id": "orbit", "type": "orbital_trajectory",
        "inputs": {key: key for key in parameters}})
    for identity, metric, operator, limit in (
        ("minimum_radius", "min_radius_m", ">=", "minimum_radius"),
        ("maximum_radius", "max_radius_m", "<=", "maximum_radius"),
    ):
        orbital["requirements"].append({"id": identity, "title": identity, "model_id": "orbit",
            "metric": metric, "operator": operator, "limit_input": limit, "critical": True})
    return {**{family: base for family in _FAMILIES[:4]}, "orbital_trajectory": orbital,
            "power_energy_budget": power, "attitude_control": attitude,
            "calculation_chains": _load("calculation-chain-reference.project.json")}


def _common_edit(before, family, operation, rng, ordinal):
    after = deepcopy(before)
    model_id, role = _FOCUS[family]
    model = _models(after)[model_id]
    input_id = model["inputs"][role]
    record = after["inputs"][input_id]
    requirement = next(item for item in after["requirements"] if item["model_id"] == model_id)
    factor = rng.choice((0.75, 0.9, 1.1, 1.25, 1.5))
    valid = True
    detail = "A constructed edit; strict acceptance is distinct from a completed numerical result."
    if operation == "numeric_input":
        record["value"] *= factor
    elif operation == "input_source":
        record["source"] += f" Revised provenance record {ordinal}."
    elif operation == "input_unit":
        record["unit"] = "unsupported-verification-unit"
        detail = "Nonempty units pass structural intake; the maintained calculator must reject the exact-unit mismatch."
    elif operation == "input_remap":
        alias = "verification_remapped_input"
        after["inputs"][alias] = deepcopy(record)
        after["inputs"][alias]["value"] *= factor
        model["inputs"][role] = alias
    elif operation == "model_description":
        model["description"] = f"Explicit revised model/load-case assumption record {ordinal}; no physical validation implied."
    elif operation == "requirement_threshold":
        threshold = after["inputs"][requirement["limit_input"]]
        threshold["value"] = threshold["value"] * factor if threshold["value"] else rng.choice((-1, 1, 10))
    elif operation == "requirement_operator":
        requirement["operator"] = rng.choice([operator for operator in ("<=", ">=", "==") if operator != requirement["operator"]])
    elif operation == "requirement_metadata":
        requirement["title"] += f" Review {ordinal}"
        requirement["critical"] = not requirement["critical"]
    elif operation == "requirement_add":
        added = deepcopy(requirement)
        added.update(id="verification_added_requirement", title="Additional declared criterion", critical=False)
        added["operator"] = "=="
        after["requirements"].append(added)
    elif operation == "requirement_remove":
        after["requirements"].remove(requirement)
    elif operation == "model_reorder":
        after["models"].reverse()
        after["requirements"].reverse()
    elif operation == "input_add_unused":
        after["inputs"]["verification_unused"] = _record(rng.uniform(0, 1000), "m")
    elif operation == "input_remove_unused":
        before["inputs"]["verification_unused"] = _record(rng.uniform(0, 1000), "m")
    elif operation == "numeric_representation_noop":
        original = record["value"]
        record["value"] = float(original) if isinstance(original, int) else int(original) if original.is_integer() else original
        detail = "Equal representable numeric value with int/float JSON spelling; evidence may retain original spelling."
    elif operation == "multi_input_edit":
        record["value"] *= factor
        after["inputs"]["heat_input"]["value"] *= rng.choice((0.5, 1.5, 2))
        requirement["operator"] = "=="
    elif operation == "model_add":
        added = deepcopy(model)
        added["id"] = "verification_added_model"
        after["models"].insert(0, added)
        criterion = deepcopy(requirement)
        criterion.update(id="verification_added_requirement", model_id=added["id"])
        after["requirements"].append(criterion)
    elif operation == "model_remove":
        after["models"].remove(model)
        after["requirements"] = [item for item in after["requirements"] if item["model_id"] != model_id]
    elif operation == "missing_bound_input":
        del after["inputs"][input_id]
        valid = False
    elif operation == "dangling_requirement_model":
        requirement["model_id"] = "verification_missing_model"
        valid = False
    elif operation == "duplicate_model":
        after["models"].append(deepcopy(model))
        valid = False
    elif operation == "invalid_requirement_operator":
        requirement["operator"] = "approximately"
        valid = False
    elif operation == "boolean_input":
        record["value"] = True
        valid = False
    elif operation == "empty_input_source":
        record["source"] = " "
        valid = False
    elif operation == "exact_noop":
        detail = "Unchanged project content except the runner's saved revision identity."
    elif operation == "requirement_limit_unit":
        after["inputs"][requirement["limit_input"]]["unit"] = "unsupported-verification-unit"
    elif operation == "unknown_requirement_metric":
        requirement["metric"] = "verification_unknown_metric"
    elif operation == "unknown_project_field":
        after["unknown_verification_field"] = ordinal
        valid = False
    elif operation == "limit_remap":
        after["inputs"]["verification_limit"] = deepcopy(after["inputs"][requirement["limit_input"]])
        after["inputs"]["verification_limit"]["source"] += " Explicit remapped limit."
        requirement["limit_input"] = "verification_limit"
    elif operation == "unsupported_model":
        model["type"] = "verification_unsupported_model"
    elif operation == "missing_limit_input":
        del after["inputs"][requirement["limit_input"]]
        valid = False
    elif operation == "project_metadata":
        after.update(name=f"Revised constructed project {ordinal}", lifecycle_stage="physical_test",
                     description="Metadata change only; a physical_test label supplies no measured evidence.")
    elif operation == "sequential_edit_snapshot":
        # The before snapshot is itself a previously edited, valid state. This
        # exercises undo/new edits against that state rather than only template->R2.
        before["inputs"][input_id]["value"] *= factor
        before["inputs"][input_id]["source"] += " Prior explicit edit."
        after = deepcopy(before)
        after["inputs"][input_id]["value"] /= factor
        after["inputs"]["heat_input"]["value"] *= 1.2
        detail = "Before already includes a prior numeric/provenance change; after undoes the number and edits an independent branch."
    else:
        raise AssertionError(operation)
    return before, after, valid, detail


def _link(source, metric="drag_force", unit="N"):
    return {"model_id": source, "metric": metric, "unit": unit,
            "rationale": "Constructed software dependency fixture; transfer direction, geometry and physical applicability require independent validation."}


def _add_aero_copy(project):
    clone = deepcopy(_models(project)["aero"])
    clone["id"] = "aero_alternative"
    project["models"].append(clone)
    return clone


def _add_downstream(project, *, multihop):
    clone = deepcopy(_models(project)["beam"])
    clone["id"] = "beam_second"
    if multihop:
        del clone["inputs"]["length"]
        clone["links"]["length"] = _link("beam", "tip_deflection", "m")
    project["models"].insert(0, clone)
    criterion = deepcopy(next(r for r in project["requirements"] if r["id"] == "mount_stress"))
    criterion.update(id="second_stress", model_id="beam_second")
    project["requirements"].append(criterion)


def _chain_edit(before, operation, rng, ordinal):
    if operation in {"source_rewire", "metric_rewire", "multihop_rewire"}:
        _add_aero_copy(before)
    if operation in {"multihop_numeric", "multihop_rewire"}:
        _add_downstream(before, multihop=True)
    elif operation == "fanout_numeric":
        _add_downstream(before, multihop=False)
    if operation == "link_add_from_literal":
        beam = _models(before)["beam"]
        beam.pop("links")
        before["inputs"]["literal_tip_load"] = _record(20, "N")
        beam["inputs"]["tip_force"] = "literal_tip_load"
    after = deepcopy(before)
    model = _models(after)["beam"]
    link = model.get("links", {}).get("tip_force")
    valid = True
    detail = "Explicit scalar dependency change; not simultaneous physics coupling."
    if operation in {"upstream_numeric", "multihop_numeric", "fanout_numeric"}:
        after["inputs"]["relative_speed"]["value"] *= rng.choice((0.5, 1.5, 2, 3))
    elif operation == "upstream_source":
        after["inputs"]["relative_speed"]["source"] += f" Provenance correction {ordinal}."
    elif operation == "rationale_change":
        link["rationale"] += f" Explicit revised transfer assumption {ordinal}."
    elif operation == "link_remove_to_literal":
        del model["links"]["tip_force"]
        after["inputs"]["literal_tip_load"] = _record(rng.choice((20, 40, 80)), "N")
        model["inputs"]["tip_force"] = "literal_tip_load"
    elif operation == "link_add_from_literal":
        del model["inputs"]["tip_force"]
        model["links"] = {"tip_force": _link("aero")}
    elif operation == "source_rewire":
        link["model_id"] = "aero_alternative"
        detail = "Same numeric source output, different named source identity and dependency provenance."
    elif operation == "metric_rewire":
        # Both static deflection and orbital radius use m. The explicit fixture
        # replaces the beam-length literal with a same-unit upstream metric.
        del model["inputs"]["length"]
        model["links"]["length"] = _link("thermal", "equilibrium_temperature", "K")
        valid = False
        detail = "A named source metric exists but its unit cannot bind to the receiving length role."
    elif operation == "link_unit_mismatch":
        link["unit"] = "kN"
        valid = False
    elif operation == "link_cycle":
        aero = _models(after)["aero"]
        del aero["inputs"]["reference_area"]
        # This unit-valid cycle uses an extra beam whose tip deflection (m)
        # feeds the first beam length; the second already depends on the first.
        _add_downstream(after, multihop=True)
        del model["inputs"]["length"]
        model["links"]["length"] = _link("beam_second", "tip_deflection", "m")
        valid = False
    elif operation == "dangling_link":
        link["model_id"] = "absent_source"
        valid = False
    elif operation == "link_direct_collision":
        after["inputs"]["literal_tip_load"] = _record(20, "N")
        model["inputs"]["tip_force"] = "literal_tip_load"
        valid = False
    elif operation == "unknown_link_metric":
        link["metric"] = "verification_absent_metric"
        valid = False
    elif operation == "empty_link_rationale":
        link["rationale"] = " "
        valid = False
    elif operation == "source_model_delete":
        after["models"] = [m for m in after["models"] if m["id"] != "aero"]
        after["requirements"] = [r for r in after["requirements"] if r["model_id"] != "aero"]
        valid = False
    elif operation == "upstream_domain_gap":
        after["inputs"]["density"]["value"] = -rng.uniform(0.01, 2)
        detail = "Structurally accepted negative density must leave source invalid and receiver unassessed."
    elif operation == "upstream_unit_gap":
        after["inputs"]["density"]["unit"] = "g/cm^3"
    elif operation == "same_output_new_sources":
        # Binary-exact factors retain F=rho*v^2*C*A/2 while changing sources.
        after["inputs"]["density"]["value"] /= 4
        after["inputs"]["relative_speed"]["value"] *= 2
        detail = "Upstream output is unchanged, but its changed source records must propagate into downstream provenance."
    elif operation == "linked_numeric_representation":
        after["inputs"]["relative_speed"]["value"] = float(after["inputs"]["relative_speed"]["value"])
    elif operation == "linked_model_reorder":
        after["models"].reverse()
    elif operation == "linked_threshold":
        after["inputs"]["maximum_bending_stress"]["value"] *= rng.choice((0.1, 0.5, 2))
    elif operation == "multihop_rewire":
        model["links"]["tip_force"]["model_id"] = "aero_alternative"
    elif operation == "sequential_chain_snapshot":
        before["inputs"]["relative_speed"]["value"] = 20
        before["inputs"]["relative_speed"]["source"] += " Prior saved change."
        after = deepcopy(before)
        after["inputs"]["relative_speed"]["value"] = 10
        after["inputs"]["heat_input"]["value"] *= 1.5
    elif operation == "linked_input_remap":
        after["inputs"]["new_speed"] = deepcopy(after["inputs"]["relative_speed"])
        after["inputs"]["new_speed"]["source"] += " Explicit replacement record."
        _models(after)["aero"]["inputs"]["relative_speed"] = "new_speed"
    elif operation == "remove_link_leave_unbound":
        del model["links"]["tip_force"]
        detail = "Missing model parameter is structurally representable but must yield invalid/unassessed numerical evidence."
    elif operation == "upstream_description":
        _models(after)["aero"]["description"] += f" Reviewed assumption correction {ordinal}."
    elif operation == "independent_branch_edit":
        after["inputs"]["heat_input"]["value"] *= rng.choice((0.5, 1.5, 2))
    elif operation == "source_requirement_fail":
        after["inputs"]["maximum_drag_force"]["value"] = 0
        detail = "An unmet source requirement cannot discard its completed calculation output."
    elif operation == "source_unknown_type":
        _models(after)["aero"]["type"] = "verification_unknown_source"
        valid = False
    elif operation == "unknown_link_role":
        model["links"]["unrecognized_role"] = deepcopy(link)
        valid = False
    elif operation == "link_extra_field":
        link["scale"] = 2
        valid = False
    else:
        raise AssertionError(operation)
    return before, after, valid, detail


def build_cases(seed: int = DEFAULT_SEED, count: int = DEFAULT_COUNT):
    """Yield a deterministic, stratified collection of complete edit snapshots.

    Counts need not be multiples of eight; family counts differ by at most one.
    Within each family the operation schedule cycles before repeating, while the
    seed changes numeric choices, scalar values and family presentation order.
    Invalid setup edits are labelled, not filtered out after validation.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer.")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer.")
    templates, rng = _templates(), random.Random(seed)
    families = list(_FAMILIES)
    rng.shuffle(families)
    for index in range(count):
        family = families[index % len(families)]
        family_ordinal = index // len(families)
        operations = _CHAIN if family == "calculation_chains" else _COMMON
        operation = operations[family_ordinal % len(operations)]
        before = deepcopy(templates[family])
        identity = f"verification-{seed}-{index + 1:05d}"
        before.update(project_id=identity, revision="1")
        edit = _chain_edit if family == "calculation_chains" else _common_edit
        if family == "calculation_chains":
            before, after, valid, detail = edit(before, operation, rng, index + 1)
        else:
            before, after, valid, detail = edit(before, family, operation, rng, index + 1)
        after["revision"] = "2"
        yield {"id": identity, "family": family, "operation": operation,
               "before": before, "after": after, "expected_valid": valid, "detail": detail}
