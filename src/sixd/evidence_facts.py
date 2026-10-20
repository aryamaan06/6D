"""Bounded, captured-source facts for Assistant explanations.

No calculation or current-project lookup occurs here. A fact reference renders
its application-owned label and exact saved value together. It establishes
traceability, not the truth of surrounding natural-language interpretation.
"""
from copy import deepcopy
from hashlib import sha256
import json
import math
import re

SCHEMA = "sixd.evidence-facts.v1"
PROSE_POLICY = "evidence_links_v1"
MAX_FACTS = 160
TOKEN = re.compile(r"\[\[fact:(f[a-f0-9]{24})\]\]")


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _escape(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def resolve_pointer(value, pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("A captured-source JSON pointer is required.")
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def build_fact_catalog(record):
    """Copy a small explicit subset of one investigation's captured evidence.

    All identities and source hashes are part of each fact ID. Full trajectories,
    arbitrary prose, provider text and source labels never supply facts.
    """
    finding = record.get("canonical_finding", {})
    scope = {key: record.get(key) for key in
             ("project_id", "revision", "run_id", "review_digest", "requirement_id")}
    scope["model_id"] = finding.get("model_id")
    if (not all(isinstance(scope[k], str) and scope[k] for k in
                ("project_id", "run_id", "review_digest", "requirement_id", "model_id"))
            or type(scope["revision"]) is not int or scope["revision"] < 1):
        raise ValueError("Exact captured investigation scope is unavailable.")
    evidence = record.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("Captured evidence is unavailable.")
    facts, omitted = [], 0

    def add(eid, payload, pointer, label, unit=None, context=None):
        nonlocal omitted
        value = resolve_pointer(payload, pointer)
        if type(value) not in (int, float, bool, str):
            return
        if type(value) in (int, float) and not math.isfinite(value):
            raise ValueError("Nonfinite captured fact.")
        if len(facts) >= MAX_FACTS:
            omitted += 1
            return
        fact = {"label": label, "value": deepcopy(value), "unit": unit,
                "evidence_id": eid, "pointer": pointer,
                "evidence_digest": source_digests[eid], "context": context or {}}
        fact["id"] = "f" + _digest({"scope": scope, **fact})[:24]
        facts.append(fact)

    def quantities(eid, payload, path, values, label, context=None):
        for key, quantity in sorted(values.items()):
            if (isinstance(quantity, dict) and type(quantity.get("value")) in (int, float)
                    and isinstance(quantity.get("unit"), str)):
                add(eid, payload, path + "/" + _escape(key) + "/value",
                    label + " · " + key, quantity["unit"], context)

    source_digests = {}
    legacy_parent_run = False
    for eid, payload in evidence.items():
        if (not isinstance(eid, str) or not isinstance(payload, dict) or payload.get("id") != eid
                or any(type(payload.get(k)) is not type(scope[k]) or payload.get(k) != scope[k]
                       for k in ("project_id", "revision", "review_digest"))):
            raise ValueError("Captured evidence does not match this investigation scope.")
        if payload.get("run_id") != scope["run_id"]:
            if record.get("evidence_facts_prose_policy") is None and "run_id" not in payload:
                # The first saved investigations recorded the run ID only on
                # their immutable parent receipt. Never borrow a current run or
                # rewrite that old payload to manufacture a stronger binding.
                legacy_parent_run = True
            else:
                raise ValueError("Captured evidence run does not match this investigation.")
        source_digests[eid] = _digest(payload)

    for eid, payload in sorted(evidence.items(), key=lambda item: (
            {"requirement": 0, "model": 1, "recheck": 2}.get(item[1].get("kind"), 3), item[0])):
        kind = payload.get("kind")
        if kind == "requirement":
            if (payload.get("requirement", {}).get("id") != scope["requirement_id"]
                    or _digest(payload.get("finding")) != _digest(finding)):
                raise ValueError("Captured requirement does not match its canonical finding.")
            context = {"metric": finding.get("metric"),
                       "operator": (finding.get("evidence") or {}).get("operator"),
                       "canonical_status": finding.get("status")}
            quantities(eid, payload, "/finding/evidence", finding.get("evidence") or {},
                       "Requirement comparison", context)
            if isinstance(payload.get("limit"), dict):
                quantities(eid, payload, "", {"limit": payload["limit"]}, "Declared limit", context)
            bundle = payload.get("selected_test_evidence")
            if isinstance(bundle, dict):
                # This row is a frozen original baseline, not the current design.
                selected, original = bundle.get("selection", {}), bundle.get("recorded", {})
                row = original.get("row", {})
                test_context = {"comparison_id": selected.get("comparison_id"),
                    "row_number": selected.get("row_number"), "receipt_digest": selected.get("receipt_digest"),
                    "baseline_run_id": original.get("baseline_run_id"),
                    "tested_revision": original.get("tested_revision"),
                    "conditions": "Supplied test conditions are unverified."}
                for field in ("measurement_requirement", "prediction_agreement"):
                    data = row.get(field, {})
                    quantities(eid, payload, "/selected_test_evidence/recorded/row/" + field,
                               data, "Original test row · " + field, test_context)
                agreement = row.get("prediction_agreement", {})
                prediction = agreement.get("prediction") or {}
                for key in ("signed_difference", "absolute_difference"):
                    if type(agreement.get(key)) in (int, float) and isinstance(prediction.get("unit"), str):
                        add(eid, payload, "/selected_test_evidence/recorded/row/prediction_agreement/" + key,
                            "Original test row · prediction_agreement · " + key, prediction["unit"], test_context)
        elif kind == "model":
            if payload.get("model", {}).get("id") != scope["model_id"]:
                raise ValueError("Captured model does not match the selected requirement.")
            result = payload.get("recorded_evidence", {})
            quantities(eid, payload, "/recorded_evidence/metrics", result.get("metrics", {}),
                       "Saved calculated metric")
            accuracy = result.get("numerical_accuracy", {})
            criteria = accuracy.get("criteria") or {}
            for key, unit in (("position_tolerance_m", "m"), ("velocity_tolerance_m_s", "m/s")):
                if type(criteria.get(key)) in (int, float):
                    add(eid, payload, "/recorded_evidence/numerical_accuracy/criteria/" + key,
                        "Declared grid-agreement tolerance · " + key, unit)
            for index, row in enumerate(accuracy.get("comparisons", [])):
                context = {key: row[key] for key in ("coarse_steps", "fine_steps", "aligned_sample_count")}
                pair = f"grids {row['coarse_steps']} → {row['fine_steps']}"
                for key, label, unit in (("max_position_difference_m", "Maximum aligned position difference", "m"),
                                         ("max_velocity_difference_m_s", "Maximum aligned velocity difference", "m/s")):
                    add(eid, payload, f"/recorded_evidence/numerical_accuracy/comparisons/{index}/{key}",
                        label + " · " + pair, unit, context)
            quantities(eid, payload, "/recorded_evidence/input_records", result.get("input_records", {}),
                       "Saved input")
        elif kind == "recheck":
            if payload.get("model_id") != scope["model_id"]:
                raise ValueError("Captured recheck does not match the selected model.")
            if type(payload.get("matches_saved_result")) is bool:
                add(eid, payload, "/matches_saved_result", "Same-adapter reproducibility · matches saved result",
                    context={"meaning": "Reproducibility only; physical validity is not established."})
        # Change payloads remain inspectable in full, but prior values are not
        # silently mixed with the selected revision's facts.
    catalog = {"schema": SCHEMA, "scope": scope, "facts": facts,
               "omitted_fact_count": omitted,
               "scope_notes": (["Legacy payloads omit run_id; the run identity comes from their preserved investigation receipt, not the current project."]
                               if legacy_parent_run else []),
               "coverage": "Selected requirement comparisons, model metrics, inputs, orbital grid comparisons and frozen test quantities only. Full histories, prior-revision values and other diagnostics remain in captured JSON."}
    catalog["digest"] = _digest(catalog)
    return catalog


def evaluate_fact_links(record):
    """Strict numeric-reference policy for new records; old prose stays legacy."""
    from .evidence_roles import POLICY, evaluate_roles
    if record.get("evidence_facts_prose_policy") == POLICY:
        return evaluate_roles(record)
    if record.get("evidence_facts_prose_policy") != PROSE_POLICY:
        return {"policy": "historical_unbound_prose", "flags": [], "references": [], "numeric_literals": []}
    flags, references = [], []
    def flag(code, message):
        flags.append({"code": code, "severity": "error", "message": message})
    try:
        expected = build_fact_catalog(record)
        if _digest(record.get("evidence_facts")) != _digest(expected):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        flag("fact_catalog_mismatch", "The saved fact catalog does not exactly match this investigation's captured evidence and scope.")
        expected = {"facts": []}
    ids = {fact["id"] for fact in expected["facts"]}
    summary = record.get("summary", "")
    for match in TOKEN.finditer(summary):
        references.append(match.group(1))
        if match.group(1) not in ids:
            flag("unknown_fact_reference", "A numerical reference is absent from this captured review's fact catalog.")
    plain = TOKEN.sub(" captured fact ", summary)
    if "[[fact:" in plain:
        flag("unknown_fact_reference", "A numerical reference is malformed or outside the supported reference format.")
    # New prose must not retype numerical values, grid labels or revision IDs.
    # Written-out numbers and relational assertions still need human review.
    # The exact product name is a label, not an engineering quantity. This
    # exception does not exempt numbered model names, grid IDs or measurements.
    numeric_prose = re.sub(r"\b6D\b", "the product", plain, flags=re.IGNORECASE)
    literals = re.findall(r"\d+(?:[.,]\d+)*(?:[eE][-+]?\d+)?", numeric_prose)
    if literals:
        flag("unbound_numeric_literal", "AI prose contains numbers outside saved fact references. Use the labelled captured facts; do not retype values or grid/revision labels.")
    return {"policy": PROSE_POLICY, "flags": flags,
            "references": sorted(set(references)), "numeric_literals": literals,
            "semantic_accuracy_established": False}


def provider_fact_catalog(record):
    """Compact wire projection; full source pointers stay in the saved catalog."""
    catalog = build_fact_catalog(record)
    return {"schema": SCHEMA, "scope": catalog["scope"], "digest": catalog["digest"],
            "facts": [{key: fact[key] for key in ("id", "label", "value", "unit", "context")}
                      for fact in catalog["facts"]],
            "omitted_fact_count": catalog["omitted_fact_count"], "coverage": catalog["coverage"],
            "instruction": "For numerical details use [[fact:ID]] with an exact listed ID. The app renders the full saved label/value/unit; do not retype numbers or assign the reference another meaning. Full source pointers and digests remain in the captured catalog."}
