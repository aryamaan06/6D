"""Application-owned numerical roles and qualitative-only model context."""
from copy import deepcopy
import re

POLICY = "application_roles_v1"
SCHEMA = "sixd.evidence-roles.v1"


def build_roles(record):
    from .evidence_facts import build_fact_catalog, _digest
    catalog = build_fact_catalog(record)
    roles = []
    for fact in catalog["facts"]:
        path = fact["pointer"]
        role = None
        if fact["evidence_id"].startswith("requirement:"):
            role = {"/finding/evidence/metric/value": "calculated_metric",
                    "/limit/value": "declared_limit"}.get(path)
            prefix = "/selected_test_evidence/recorded/row/"
            test_roles = {"measurement_requirement/metric/value": "test_observation",
                "measurement_requirement/limit/value": "original_test_limit",
                "prediction_agreement/prediction/value": "original_test_prediction",
                "prediction_agreement/tolerance/value": "test_agreement_tolerance",
                "prediction_agreement/absolute_difference": "test_absolute_difference"}
            if path.startswith(prefix):
                role = test_roles.get(path[len(prefix):])
        elif fact["evidence_id"].startswith("model:"):
            prefix = "/recorded_evidence/numerical_accuracy/"
            role = {prefix + "criteria/position_tolerance_m": "position_grid_tolerance",
                    prefix + "criteria/velocity_tolerance_m_s": "velocity_grid_tolerance"}.get(path)
            match = re.fullmatch(re.escape(prefix) + r"comparisons/([01])/(max_position_difference_m|max_velocity_difference_m_s)", path)
            if match:
                pair = "coarse_to_middle" if match[1] == "0" else "middle_to_fine"
                quantity = "position" if match[2] == "max_position_difference_m" else "velocity"
                role = quantity + "_difference_" + pair
        elif fact["evidence_id"].startswith("recheck:") and path == "/matches_saved_result":
            role = "same_adapter_reproduced"
        if role:
            if any(item["role"] == role for item in roles):
                raise ValueError("Ambiguous numerical role in captured evidence.")
            roles.append({"role": role, "fact_id": fact["id"]})
    result = {"schema": SCHEMA, "scope": deepcopy(catalog["scope"]),
              "catalog_digest": catalog["digest"], "roles": roles,
              "canonical_status": record["canonical_finding"]["status"],
              "operator": (record["canonical_finding"].get("evidence") or {}).get("operator"),
              "meaning": "Numerical roles are selected by the application from captured sources, never by model prose. No physical validity or semantic guarantee follows."}
    result["digest"] = _digest(result)
    return result


def evaluate_roles(record):
    from .evidence_facts import build_fact_catalog, _digest
    flags = []
    try:
        expected = build_fact_catalog(record)
        if (_digest(record.get("evidence_facts")) != _digest(expected)
                or _digest(record.get("evidence_roles")) != _digest(build_roles(record))):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        flags.append({"code": "fact_catalog_mismatch", "severity": "error",
                      "message": "Application-owned numerical roles do not match the exact captured sources and scope."})
    summary = record.get("summary", "")
    if record.get("canonical_finding", {}).get("status") == "met":
        from .explanation_quality import _affirmative
        negative = (r"\b(?:(?:the|this)\s+(?:(?:canonical(?:\s+design)?|calculated|design)\s+)?|"
                    r"(?:canonical(?:\s+design)?|calculated|design)\s+)(?:criterion|requirement)\s+"
                    r"(?:(?:is|was)\s+)?(?:not[_\s]+met|unmet|violat\w*|fails?)\b")
        if _affirmative(negative, summary.casefold()):
            flags.append({"code": "canonical_status_contradiction", "severity": "error",
                          "message": "The qualitative commentary contradicts the captured met criterion."})
    if re.search(r"\[\[(?:fact|role):", summary):
        flags.append({"code": "unknown_fact_reference", "severity": "error",
                      "message": "Inline numerical references are not part of this qualitative contract. The app displays their source-bound roles separately."})
    text = re.sub(r"\b6D\b", "the product", summary, flags=re.IGNORECASE)
    literals = re.findall(r"\d+(?:[.,]\d+)*(?:[eE][-+]?\d+)?", text)
    if literals:
        flags.append({"code": "unbound_numeric_literal", "severity": "error",
                      "message": "The model retyped numbers in qualitative commentary. Read the application-owned numerical evidence separately."})
    # Earlier application_roles_v1 receipts have no change-policy marker. Their
    # saved acceptance remains historical; new records opt in explicitly.
    if "change_commentary_policy" in record:
        from .change_evidence import POLICY as CHANGE_POLICY, context_from_record, evaluate_change_commentary
        try:
            context = context_from_record(record)
            if (record["change_commentary_policy"] != CHANGE_POLICY
                    or _digest(record.get("evidence_change_context")) != _digest(context)):
                raise ValueError
        except (KeyError, TypeError, ValueError, OverflowError):
            flags.append({"code": "change_context_mismatch", "severity": "error",
                          "message": "Change directions do not match the exact captured source and investigation scope."})
        else:
            flags.extend(evaluate_change_commentary(summary, context))
    return {"policy": POLICY, "flags": flags, "references": [], "numeric_literals": literals,
            "application_owned_role_count": len((record.get("evidence_roles") or {}).get("roles", [])),
            "semantic_accuracy_established": False}


def qualitative_projection(payload):
    """Withhold numeric payload values only on the new commentary wire path.

    The full original stays in the investigation receipt. Metadata/source IDs,
    units and untrusted source prose retain their explicit context; their digits
    must not be interpreted as new numerical evidence.
    """
    def project(value):
        if type(value) in (int, float):
            return "[saved numerical value displayed by 6D]"
        if isinstance(value, dict):
            return {key: project(item) for key, item in value.items() if key != "evidence_facts"}
        if isinstance(value, list):
            return [project(item) for item in value]
        return deepcopy(value)
    result = project(payload)
    if payload.get("kind") == "changes":
        from .change_evidence import build_change_context, provider_change_context
        result["application_change_context"] = provider_change_context(build_change_context(payload))
    result["numerical_context_disclosure"] = (
        "Numerical payload values are withheld from this qualitative commentary view. "
        "6D displays exact metric, limit and grid evidence in application-owned roles. "
        "The complete original records remain captured locally. Explain status, scope and next checks in words; do not estimate omitted values. "
        "For revision changes, use the application_change_context directions; do not infer a direction from withheld values.")
    return result
