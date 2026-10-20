"""Exact captured changes and a deliberately bounded English direction guard.

No current-project lookup, unit conversion, physical causality inference or model
call occurs here. Lack of a flag is not general semantic approval.
"""
from copy import deepcopy
import math
import re

from .evidence_facts import _digest, _escape

POLICY = "application_changes_v1"
SCHEMA = "sixd.change-context.v1"


def _quantity_direction(before, after, identity_matches=True):
    if (not identity_matches or not isinstance(before, dict) or not isinstance(after, dict)
            or not isinstance(before.get("unit"), str) or not before["unit"]
            or before["unit"] != after.get("unit")
            or type(before.get("value")) not in (int, float)
            or type(after.get("value")) not in (int, float)
            or not math.isfinite(before["value"]) or not math.isfinite(after["value"])):
        return "not_comparable"
    return ("increased" if after["value"] > before["value"] else
            "decreased" if after["value"] < before["value"] else "unchanged")


def _words(value):
    return re.sub(r"[_-]+", " ", str(value)).strip()


def build_change_context(changes_payload):
    """Build source-bound facts from the full captured changes wrapper."""
    if not isinstance(changes_payload, dict):
        raise ValueError("Captured changes are required.")
    source_digest = _digest(changes_payload)  # Nonfinite source JSON is invalid.
    comparison = changes_payload.get("comparison")
    scope = {key: changes_payload.get(key) for key in
             ("project_id", "revision", "run_id", "review_digest")}
    rows = []
    if comparison is not None:
        if not isinstance(comparison, dict):
            raise ValueError("Invalid captured comparison.")
        scope.update({key: (comparison.get("scope") or {}).get(key)
                      for key in ("requirement_id", "model_id")})
        scope.update(from_revision=comparison.get("from_revision"),
                     to_revision=comparison.get("to_revision"))
        before, after = comparison.get("before") or {}, comparison.get("after") or {}
        old_finding, new_finding = before.get("finding") or {}, after.get("finding") or {}
        old_evidence, new_evidence = old_finding.get("evidence") or {}, new_finding.get("evidence") or {}
        same_metric = (old_finding.get("metric") is not None
                       and old_finding.get("metric") == new_finding.get("metric")
                       and old_finding.get("requirement_id") == new_finding.get("requirement_id")
                       and old_finding.get("model_id") == new_finding.get("model_id"))
        same_operator = (old_evidence.get("operator") is not None
                         and old_evidence.get("operator") == new_evidence.get("operator"))

        def add(subject, label, left, right, old_path, new_path, identity=True, aliases=None):
            rows.append({"subject": subject, "label": label,
                "direction": _quantity_direction(left, right, identity),
                "before": deepcopy(left), "after": deepcopy(right),
                "before_pointer": "/comparison/before/" + old_path,
                "after_pointer": "/comparison/after/" + new_path,
                "source_evidence_id": "changes", "aliases": aliases or [],
                "identity_matches": bool(identity)})

        metric_name = _words(new_finding.get("metric", ""))
        add("declared_limit", "Declared limit", old_evidence.get("limit"), new_evidence.get("limit"),
            "finding/evidence/limit", "finding/evidence/limit", same_metric and same_operator,
            ["declared limit", "requirement limit", "limit"])
        metric_aliases = ["calculated metric", "calculated result", "model output", "calculated output"]
        if metric_name:
            metric_aliases.extend([metric_name, "calculated " + metric_name])
        add("calculated_metric", "Calculated metric", old_evidence.get("metric"), new_evidence.get("metric"),
            "finding/evidence/metric", "finding/evidence/metric", same_metric, metric_aliases)
        old_inputs, new_inputs = before.get("input_records") or {}, after.get("input_records") or {}
        for identity in sorted(set(old_inputs) | set(new_inputs)):
            word = _words(identity)
            add("input:" + identity, word[:1].upper() + word[1:], old_inputs.get(identity), new_inputs.get(identity),
                "input_records/" + _escape(identity), "input_records/" + _escape(identity),
                aliases=[word, word + " input", word + " value"] if word else [])
    result = {"schema": SCHEMA, "available": comparison is not None,
        "source_evidence_id": "changes", "source_digest": source_digest,
        "scope": scope, "comparisons": rows,
        "meaning": "Exact scalar direction within captured before/after records only. Equal units are required; no conversion, physical cause or whole-model equivalence is inferred."}
    result["digest"] = _digest(result)
    return result


def context_from_record(record):
    """Rederive context and require its source to match this investigation."""
    payload = (record.get("evidence") or {}).get("changes")
    if payload is None:
        return None
    for key in ("project_id", "revision", "run_id", "review_digest"):
        if payload.get(key) != record.get(key):
            raise ValueError("Captured changes have a different investigation scope.")
    if payload.get("id") != "changes" or payload.get("kind") != "changes":
        raise ValueError("Captured changes identity is invalid.")
    context = build_change_context(payload)
    if context["available"]:
        scope = context["scope"]
        comparison = payload["comparison"]
        if (scope["requirement_id"] != record.get("requirement_id")
                or scope["model_id"] != (record.get("canonical_finding") or {}).get("model_id")
                or comparison.get("project_id") != record.get("project_id")
                or str(scope["to_revision"]) != str(record.get("revision"))
                or _digest((comparison.get("after") or {}).get("finding")) != _digest(record.get("canonical_finding"))):
            raise ValueError("Captured comparison scope does not match this investigation.")
    return context


def provider_change_context(context):
    """Words-only facts; the exact source-bound numbers stay in local evidence."""
    if context is None:
        return None
    return {"schema": SCHEMA, "available": context["available"],
        "comparisons": [{"subject": row["subject"], "label": row["label"],
                         "direction": row["direction"]} for row in context["comparisons"]],
        "instruction": "Use only these application-derived directions for factual before/after claims. Not comparable means no direction is established. Do not infer physical cause or that all inputs/models were unchanged."}


_DIRECTION = (r"increas(?:e|es|ed|ing)|rais(?:e|es|ed|ing)|higher|grew|grown|"
              r"decreas(?:e|es|ed|ing)|reduc(?:e|es|ed|ing)|lower(?:ed)?|fell|fallen|"
              r"unchanged|constant|identical|the same|equal")


def _claimed_direction(word):
    if re.match(r"increas|rais|higher|grew|grown", word):
        return "increased"
    if re.match(r"decreas|reduc|lower|fell|fallen", word):
        return "decreased"
    return "unchanged"


def evaluate_change_commentary(summary, context):
    """Reject clear named-subject contradictions, not arbitrary English logic.

    Review questions and hypothetical/conditional/proposed future actions are
    not treated as assertions about a saved change. Quotation marks alone do
    not exempt a factual assertion from checking.
    """
    if context is None or not context.get("available"):
        return []
    flags = []
    text = summary.casefold().replace("didn't", "did not").replace("hasn't", "has not")
    clauses = []
    for sentence in re.findall(r"[^.!?;\n]+[.!?;\n]?", text):
        if sentence.endswith("?") and re.match(r"\s*(?:did|does|do|has|have|had|is|are|was|were|why|how|what|could|would|should|can)\b", sentence):
            continue
        clauses.extend(re.split(r"\b(?:while|whereas|but)\b|,\s*(?=(?:which|and)\b)", sentence.rstrip(".!?;\n")))
    for clause in clauses:
        if (re.match(r"\s*(?:if|unless|whether|could|would|should|might|may|hypothetical|proposed)\b", clause)
                or re.match(r"\s*(?:next\b.*?|then\s+)?(?:review|check|consider|evaluate|obtain|verify|compare|inspect)\b", clause)):
            continue
        for row in context.get("comparisons", []):
            for alias in row.get("aliases", []):
                if not alias or len(alias) > 180:
                    continue
                subject = r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)"
                # Typical factual forms: 'the limit has decreased' and
                # 'an increased maximum temperature input'. Keep the binding
                # local so a different subject elsewhere cannot inherit it.
                patterns = [
                    subject + r"(?:\s+(?:input|value|metric))?\s+(?:(?:has|have|had|is|are|was|were|been|did|does|do|now|remains?|remained|stayed)\s+){0,3}(?P<neg>not\s+|never\s+)?(?P<direction>" + _DIRECTION + r")\b",
                    r"(?P<neg>not\s+|never\s+)?(?P<direction>" + _DIRECTION + r")\s+" + subject,
                ]
                for pattern in patterns:
                    for match in re.finditer(pattern, clause):
                        if re.search(r"\b(?:if|unless|whether|could|would|should|might|may|hypothetical|proposed)\b", clause[:match.start()]):
                            continue
                        if (match["direction"] in ("higher", "lower", "equal", "the same", "identical")
                                and re.match(r"\s+(?:than|to|as)\s+", clause[match.end():])
                                and not re.search(r"\b(?:prior|previous|before|earlier)\b", clause[match.end():])):
                            continue  # A static cross-quantity comparison is not a revision direction.
                        direction = _claimed_direction(match["direction"])
                        if match.start() and re.search(r"\b(?:not|no|never)\s+(?:an?\s+)?$", clause[:match.start()]):
                            continue
                        contradicts = (row["direction"] == direction if match["neg"] else
                                       row["direction"] != direction)
                        if contradicts:
                            flag = {"code": ("change_comparison_unavailable" if row["direction"] == "not_comparable" else "change_direction_contradiction"), "severity": "error",
                                "message": "A factual change-direction statement conflicts with the captured before/after records.",
                                "subject": row["subject"], "recorded_direction": row["direction"],
                                "claimed_direction": direction, "negated": bool(match["neg"])}
                            if flag not in flags:
                                flags.append(flag)
    return flags
