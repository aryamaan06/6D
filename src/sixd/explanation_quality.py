"""Grounded review guidance and deliberately limited explanation checks.

Guidance is derived from verified saved records and maintained adapter metadata;
it does not add calculations, validate applicability, or alter a finding. The
text checks detect specific risky phrases and ungrounded literal quantities.
Their absence is not a proof of factual or semantic accuracy.
"""
from copy import deepcopy
import json
import math
import re

from . import lifecycle
from .engineering import MODEL_PARAMETERS, MODEL_VERSIONS
from .evidence_facts import evaluate_fact_links


GUIDANCE_SCHEMA = "sixd.engineering-guidance.v1"
QUALITY_SCHEMA = "sixd.explanation-quality.v1"
ACCEPTANCE_SCHEMA = "sixd.explanation-acceptance.v1"
# This is a bounded rejection policy, not a claim that unflagged prose is true.
# Literal-quantity and wording warnings deliberately remain review-only.
_BLOCKING_CODES = frozenset({
    "unsupported_result_prediction", "canonical_status_contradiction",
    "recorded_status_mismatch", "unassessed_as_impossible", "unassessed_as_failure",
    "readiness_or_guarantee_claim", "citation_mismatch", "empty_summary",
    "missing_canonical_status",
    "literal_comparison_contradiction",
    "test_evidence_binding_mismatch", "test_evidence_status_contradiction",
    "test_evidence_unmatched_quantity", "test_evidence_validation_claim",
    "fact_catalog_mismatch", "unknown_fact_reference", "unbound_numeric_literal",
    "change_direction_contradiction", "change_context_mismatch", "change_comparison_unavailable",
})
_MEANINGS = {
    "met": "The calculated metric meets the declared criterion within this bounded model and its stated assumptions.",
    "not_met": "The calculated metric violates the declared criterion for this saved configuration. This finding alone does not establish a physical failure or its cause.",
    "not_assessed": "The available evidence does not establish whether this requirement is satisfied. This is an evidence gap, not a finding that the design is physically impossible or has failed.",
}
_DOMAIN_REVIEW = {
    "powered_flight": (
        "Review the vertical flight assumptions and burnout evidence",
        "Verify the initial and dry masses, constant thrust and specific impulse, reference area and drag coefficient, exponential atmosphere and gravity inputs against their sources. Inspect the saved burnout event, mass depletion, above-surface coast and sampled pressure and acceleration histories. Review both retained grid comparisons and declared altitude, velocity and relative tolerances; use independent analysis to check the applicable regime. Staging, steering, lateral motion, aeroheating, landing and whole-mission performance require separate evidence.",
        "Sourced engine and usable-propellant data, atmosphere and coefficient validity, gravity and geometry, justified numerical tolerances and resolution, independent vertical-flight reference evidence, and applicable analyses of effects excluded from this single-axis model.",
    ),
    "attitude_control": (
        "Review the pointing window, controller and torque authority",
        "Inspect the saved signed error, angular rate, requested versus applied torque and clipped-command samples. Verify the inertia, axis/reference, target, gain signs, disturbance estimate and actuator limit against their sources. Review the explicit assessment window and numerical grid differences; refine the grid and compare an independent analysis before relying on the sampled criterion. Check sensor/delay effects and actuator momentum or bandwidth separately. Do not relax engineering limits to obtain a pass.",
        "Sourced inertia, angle/rate convention, controller gains, actuator and disturbance data, required pointing window and accuracy, numerical tolerances, independent control analysis and applicable sensor, three-axis, momentum and hardware evidence.",
    ),
    "power_energy_budget": (
        "Review simultaneous loads, mode durations and usable energy",
        "Check each mode's simultaneous equipment counts and power, its duration, available bus generation, bus limit, battery power capacity and reserve-adjusted bus-deliverable usable energy. Inspect power and energy margins separately. Surplus generation receives no recharge credit; a negative remaining energy budget is a shortfall, not a physical state-of-charge prediction. Obtain source and duty/schedule evidence before relying on this bounded budget.",
        "Equipment load provenance and concurrency, duration and generation assumptions, usable battery energy after reserves/losses, discharge capability, bus limits, and any charging, illumination, degradation or transient analysis excluded here.",
    ),
    "orbital_trajectory": (
        "Review the orbit's inputs, time window and sampling",
        "Verify the initial position and velocity, body-centered inertial frame, gravitational parameter and their sources. Inspect the saved trajectory and time window. Compare a deliberately refined step count in a new revision and use an independent reference analysis before relying on sampled extrema; a same-adapter recheck alone establishes reproducibility. Review thrust, atmosphere, perturbations and uncertainty separately when applicable.",
        "Sourced initial state and frame, central-body gravity, duration and time-step justification, independent reference evidence and applicable environmental or maneuver models. Sampled extrema cannot establish clearance between samples; the exclusion radius is a numerical boundary, not terrain or a safety assessment.",
    ),
    "radiative_equilibrium": (
        "Check the thermal model's applicability",
        "Review the heat-load source, emitting area, infrared emissivity and background temperature. Check whether steady, isothermal, radiation-only assumptions apply; obtain a transient or multi-path thermal analysis when they do not.",
        "Evidence for heat-load provenance, material/coating emissivity, view factors, and whether transient heating or other heat-transfer paths matter.",
    ),
    "ideal_propulsion": (
        "Check the propulsion budget's applicability",
        "Review usable propellant, dry/initial mass, required delta-v, specific impulse and thrust sources. Obtain trajectory losses, staging and reserve allocations before treating this ideal single-burn budget as a mission budget.",
        "Evidence for engine performance, usable propellant and reserves, flight losses, staging and the maneuver's actual operating conditions.",
    ),
    "static_cantilever": (
        "Check the beam idealization and allowable",
        "Review the load mapping, geometry, bending-axis section property, modulus and constraint. Check the small-deflection beam assumptions and the allowable's basis; use appropriate structural analysis or tests for buckling, joints, vibration or other excluded effects.",
        "Evidence for the material/allowable, load and boundary conditions, section properties and whether excluded failure modes apply.",
    ),
    "drag_load": (
        "Check the atmospheric condition and coefficient",
        "Review density, relative speed, drag coefficient and reference-area convention for the supplied flow condition. Obtain regime-appropriate aerodynamic evidence before extending this one-condition force magnitude to stability, aeroheating, trajectory or structural loads.",
        "Evidence for atmospheric conditions, attitude, coefficient/reference-area compatibility and relevant Mach, Reynolds or Knudsen regime.",
    ),
}


def build_guidance(project, review, requirement_id, evidence_ids=()):
    """Return review actions tied to one verified requirement, without mutation.

    ``basis`` values are JSON Pointer paths within the locked review, not claims
    that a project source label has been independently validated. Evidence IDs
    identify available investigation receipts; they do not invent new evidence.
    """
    lifecycle.verify_review(review)
    if project != review["project"]:
        raise ValueError("Guidance requires the project captured in this review.")
    if requirement_id not in review["findings"]:
        raise ValueError("Guidance requires an existing reviewed requirement.")
    if (not isinstance(evidence_ids, (list, tuple))
            or any(not isinstance(item, str) or not item for item in evidence_ids)
            or len(set(evidence_ids)) != len(evidence_ids)):
        raise ValueError("Guidance evidence IDs must be unique strings.")
    requirement = next(item for item in project["requirements"] if item["id"] == requirement_id)
    model = next(item for item in project["models"] if item["id"] == requirement["model_id"])
    finding = review["findings"][requirement_id]
    receipt = review["evidence"][model["id"]]
    status = finding["status"]
    ids = sorted(evidence_ids)
    escape = lambda value: value.replace("~", "~0").replace("/", "~1")
    finding_path = "/findings/" + escape(requirement_id)
    model_path = "/evidence/" + escape(model["id"])
    actions, missing = [], []

    def add(identity, title, action, *basis):
        actions.append({"id": identity, "title": title, "action": action,
                        "basis": list(basis), "evidence_ids": ids[:]})

    def need(item, why, *basis):
        missing.append({"item": item, "why": why, "basis": list(basis)})

    if model.get("links"):
        add("review_calculation_transfers", "Review the declared transfers between calculations",
            "Trace each linked role to its saved source metric, exact unit and transfer rationale. Verify direction, geometry, load case, timing and the receiving model's assumptions against engineering evidence. Inspect upstream gaps before altering downstream inputs. A completed source result may still violate its own requirement; that violation remains separate. After a justified upstream change, rerun the dependent chain.",
            model_path + "/calculation_inputs", model_path + "/model_definition/links")
        need("Engineering justification for each scalar transfer and compatible source/receiver conditions.",
             "Matching units and successful calculation do not establish physical equivalence or validate a load mapping.",
             model_path + "/model_definition/links")

    if status == "not_met":
        add("review_limit_violation", "Review the calculated criterion violation",
            "Compare the recorded metric and declared limit, confirm their input sources and requirement basis, then evaluate a justified design change or higher-fidelity analysis. Save a new revision and rerun affected checks; do not relax the limit solely to obtain a pass.",
            finding_path + "/evidence", model_path + "/input_records")
    elif status == "met":
        add("review_supported_pass", "Confirm the supported pass applies to the design",
            "Inspect the recorded comparison, assumptions and input provenance. Review excluded effects separately before extending this component result to a larger system. Rerun affected checks after a justified input or requirement change.",
            finding_path + "/evidence", model_path + "/assumptions", model_path + "/not_assessed")
    else:
        from .engineering import evidence_accuracy_gap, requirement_accuracy_gap
        accuracy_gap = evidence_accuracy_gap(receipt)
        selected_metric = receipt["metrics"].get(requirement["metric"])
        selected_limit = project["inputs"][requirement["limit_input"]]
        if accuracy_gap is None and selected_metric is not None and selected_metric["unit"] == selected_limit["unit"]:
            accuracy_gap = requirement_accuracy_gap(receipt, requirement, selected_metric, selected_limit)
        expected = MODEL_PARAMETERS.get(model["type"], {})
        mismatches = [(parameter, input_id, unit, project["inputs"][input_id]["unit"])
                      for parameter, unit in expected.items()
                      if (input_id := model["inputs"].get(parameter)) in project["inputs"]
                      and project["inputs"][input_id]["unit"] != unit]
        if mismatches:
            for parameter, input_id, expected_unit, actual in mismatches:
                path = "/project/inputs/" + escape(input_id)
                add("resolve_unit_" + parameter, "Resolve the declared input unit",
                    f"The {parameter} binding requires {expected_unit}; its saved input declares {actual}. Verify the physical value and source, explicitly convert the value if needed, then save a corrected revision and rerun. Changing the unit label alone is not a conversion.",
                    path, model_path + "/issues")
                need(f"Verified {parameter} value expressed in {expected_unit}.",
                     "The maintained adapter requires an explicit SI value and does not convert units.", path)
        elif model["type"] not in MODEL_VERSIONS:
            add("obtain_supported_analysis", "Obtain an applicable analysis and verification method",
                "Select or implement an applicable, validated analysis outside the current unsupported adapter, document its inputs and acceptance method, and connect its evidence through a supported integration. Repeating this investigation cannot create the missing solver or establish satisfaction.",
                model_path + "/model_type", model_path + "/not_assessed", finding_path)
            if "gnc" in model["type"].casefold() or "control" in model["type"].casefold():
                need("Vehicle dynamics, guidance/control architecture, sensor and actuator models, disturbances, operating conditions and reference frames.",
                     "A control-performance claim needs applicable dynamics and closed-loop analysis inputs; the current model produces no tracking result.", model_path)
                need("A defined tracking-error measurement, acceptance conditions and supported simulation or test evidence tied to this revision.",
                     "The declared limit alone cannot establish control performance.", finding_path, model_path + "/metrics")
            else:
                need("An applicable model, documented input/condition definitions and verified results for the declared metric.",
                     "No maintained adapter supports this model type.", model_path)
        elif (model["type"] == "attitude_control" and receipt["status"] != "completed"
                and any(issue.startswith("Attitude grid refinement did not meet the supplied angle/rate numerical tolerances.")
                        for issue in receipt["issues"])):
            add("resolve_attitude_accuracy", "Resolve the attitude response's numerical accuracy gap",
                "The recorded angle or angular-rate refinement comparison exceeds its supplied numerical tolerance. Verify the angle and rate criteria and their engineering sources, then save a revision with a finer supported step count or obtain an independently checked analysis. Keep the assessment window, target, gain signs and actuator assumptions explicit. Do not loosen tolerances to obtain a pass; this stopped calculation supplies no completed pointing or rate result.",
                model_path + "/issues", model_path + "/model_definition", model_path + "/input_records", finding_path)
            need("Sourced angle and angular-rate numerical tolerances, a supported grid refinement and independent control-response analysis when needed.",
                 "The recorded attitude calculation did not meet its numerical comparison criteria and produced no completed metrics.",
                 model_path + "/issues", finding_path)
        elif receipt["status"] != "completed":
            add("resolve_invalid_inputs", "Resolve the recorded model input issues",
                "Inspect the model's recorded issues and exact parameter bindings, units and allowed input ranges. Verify each correction against its source, save a new revision and rerun before interpreting a requirement outcome.",
                model_path + "/issues", model_path + "/model_definition", model_path + "/input_records")
            need("Corrected, sourced inputs satisfying the maintained adapter's declared parameter requirements.",
                 "The calculation did not produce an assessable result.", model_path + "/issues")
        elif requirement["metric"] not in receipt["metrics"]:
            add("resolve_missing_metric", "Resolve the required metric mapping",
                "Check whether the declared metric is produced by the selected adapter. Correct a mistaken binding in a new revision or supply a validated model/integration that actually produces the required metric; do not substitute an unrelated result.",
                finding_path + "/metric", model_path + "/metrics")
            need("A supported result for the exact required metric.", "The completed calculation omitted this required metric.", finding_path)
        elif accuracy_gap:
            if model["type"] == "powered_flight":
                add("resolve_flight_accuracy", "Resolve the vertical flight's numerical accuracy gap",
                    "Inspect both saved altitude and velocity grid comparisons, the exact burnout event and the supplied absolute and relative numerical tolerances. Verify those tolerances and their engineering sources. Save a revision with a finer supported step count or obtain an independently checked vertical-flight analysis when the current grid does not support the criterion. If the saved metric allowance overlaps its engineering limit, obtain evidence that separates them. Do not loosen tolerances to obtain a pass. Grid agreement is not a guaranteed error bound or physical validation, and sampled extrema do not bound values between samples.",
                    model_path + "/flight_response/diagnostics", model_path + "/model_definition", finding_path)
                need("Sourced altitude, velocity and relative numerical tolerances, retained grid comparisons and independent vertical-flight analysis when needed.",
                     accuracy_gap["reason"], model_path + "/flight_response/diagnostics", finding_path)
            else:
                add("resolve_orbital_accuracy", "Resolve the orbit's numerical accuracy gap",
                    "Inspect the recorded grid comparisons, observed refinement and supplied position/velocity tolerances. "
                    "Declare engineering-justified tolerances with their source when missing. If the current grid does not support them, "
                    "save a revision with a finer supported grid or obtain an independently checked analysis that meets the required accuracy. "
                    "If the declared numerical allowance overlaps the engineering limit, obtain evidence that separates the result from that limit. "
                    "Do not loosen tolerances just to obtain a pass. Grid agreement is an estimate, not a guaranteed error bound or physical validation.",
                    model_path + "/numerical_accuracy", model_path + "/model_definition", finding_path)
                need("Sourced numerical position and velocity accuracy criteria, a supported refinement comparison and independent analysis when needed.",
                     accuracy_gap["reason"], model_path + "/numerical_accuracy", finding_path)
        else:
            add("resolve_comparison_units", "Resolve the metric and limit units",
                "Compare the recorded metric unit with the limit's declared unit. Verify and explicitly convert the limit value if justified, save a new revision and rerun. Do not compare unlike units or change only a label.",
                model_path + "/metrics", "/project/inputs/" + escape(requirement["limit_input"]))
            need("A sourced requirement limit in the same physical unit as the required metric.",
                 "The current metric and limit cannot be compared without an explicit justified conversion.", finding_path)

    if model["type"] in _DOMAIN_REVIEW:
        title, action, information = _DOMAIN_REVIEW[model["type"]]
        add("review_model_applicability", title, action,
            model_path + "/assumptions", model_path + "/not_assessed", model_path + "/input_records")
        need(information, "These applicability questions are outside the maintained calculation; their relevance and adequacy require engineering review.",
             model_path + "/not_assessed")
    return {
        "schema": GUIDANCE_SCHEMA,
        "scope": {"project_id": review["project_id"], "revision": review["revision"],
                  "requirement_id": requirement_id, "model_id": model["id"], "review_digest": review["digest"]},
        "canonical_assessment": {"status": status, "meaning": _MEANINGS[status],
                                 "reason": _MEANINGS[status], "criterion": deepcopy(finding["evidence"])},
        "review_actions": actions, "missing_information": missing,
        "assumptions": deepcopy(receipt["assumptions"]), "exclusions": deepcopy(receipt["not_assessed"]),
        "limitations": ["Actions are review guidance, not new calculated evidence or an automatic design change.",
                        "A same-adapter recheck establishes reproducibility only; it does not independently validate the physics.",
                        "No component finding or AI explanation authorizes launch or guarantees mission success."],
        "evidence_ids": ids,
    }


_QUANTITY = re.compile(r"(?<![\w.])([-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*(kg\*m\^2|N\*m\*s/rad|N\*m/rad|N\*m|rad/s|rad|kg/m\^3|m/s\^2|kg/s|m/s|m\^4|m\^2|Pa|kg|K|W|J|N|s|m)\b")


def _nonasserted_prefix(prefix):
    """Recognize a few explicit question/negation prefixes, not general logic."""
    prefix = re.split(r"(?<=[.!?;])\s+|\n+", prefix)[-1]
    prefix = re.split(r"\b(?:but|however|nevertheless)\b", prefix)[-1]
    if re.search(r"\b(?:whether|if)\s+(?:(?:the|this)\s+)?$", prefix):
        return True
    if re.search(r"\b(?:cannot|can't|can\s+not|do\s+not|does\s+not|did\s+not|must\s+not)\s+(?:yet\s+)?(?:claim|say|conclude|determine|establish|know|predict|assert|show|mean|imply)\b[^;.!?]{0,100}$", prefix):
        return True
    if re.search(r"\bnot\s+(?:a\s+)?(?:finding|claim|conclusion|indication|evidence|proof)\s+(?:that|of)\b[^;.!?]{0,100}$", prefix):
        return True
    return bool(re.search(r"\bno\s+(?:(?:valid|quantitative|recorded)\s+)?evidence\s+(?:shows?|establishes?|supports?|predicts?)\b[^;.!?]{0,60}$", prefix))


def _affirmative(pattern, text):
    """Ignore selected explicit negation/question prefixes.

    This intentionally does not attempt general natural-language inference.
    """
    for match in re.finditer(pattern, text):
        prefix = text[max(0, match.start() - 180):match.start()]
        if (not _nonasserted_prefix(prefix)
                and not re.search(r"\b(?:not|never|cannot|can't|no\s+claim\s+that|does\s+not|do\s+not)\s+(?:be\s+|been\s+|considered\s+|declared\s+|automatically\s+)?$", prefix)):
            return True
    return False


def _readiness_claim_text(text):
    """Mask only two explicitly coordinated denials, not later assertions."""
    denial = (r"\b(?:does\s+not|doesn't|do\s+not|cannot|can\s+not|can't|must\s+not)\s+"
              r"(?:authorize\s+launch\s+or\s+guarantee\s+mission\s+success|"
              r"guarantee\s+mission\s+success\s+or\s+authorize\s+launch)\b")
    return re.sub(denial, lambda match: " " * len(match.group(0)), text)


def _attributed_source_quotes(record, summary):
    """Mask only exact captured reason/issue strings with explicit attribution.

    Quotation marks alone do not exempt a claim. Neither project source labels
    nor arbitrary prose fields qualify as a captured reason or issue. This is
    deliberately narrower than general quotation or attribution understanding.
    """
    allowed = set()

    def include(value):
        if isinstance(value, str) and value:
            allowed.add(value)

    def include_finding(value):
        if isinstance(value, dict):
            include(value.get("reason"))
            for item in value.get("not_assessed", []):
                include(item)

    include_finding(record.get("canonical_finding"))
    evidence = record.get("evidence", {})
    if isinstance(evidence, dict):
        for item in evidence.values():
            if not isinstance(item, dict):
                continue
            if item.get("kind") == "requirement":
                include_finding(item.get("finding"))
            result = (item.get("recorded_evidence") if item.get("kind") == "model"
                      else item.get("fresh_result") if item.get("kind") == "recheck" else None)
            if isinstance(result, dict):
                for field in ("issues", "not_assessed"):
                    for value in result.get(field, []):
                        include(value)
    quote = re.compile(r"'([^'\n]{1,1200})'|\"([^\"\n]{1,1200})\"|‘([^’\n]{1,1200})’|“([^”\n]{1,1200})”|`([^`\n]{1,1200})`")
    masked, attributed = list(summary), []
    for match in quote.finditer(summary):
        value = next(group for group in match.groups() if group is not None)
        prefix = summary[max(0, match.start() - 180):match.start()].casefold()
        prefix = re.split(r"(?<=[.!?;])\s+|\n+", prefix)[-1]
        explicit = (re.search(r"\b(?:recorded|captured|canonical|requirement|model|finding)\b[^.!?;]{0,150}\b(?:reason|issues?|exclusions?)\s*:\s*$", prefix)
                    and re.search(r"\b(?:records?|shows?|states?|lists?|reports?)\b", prefix))
        if value in allowed and explicit:
            masked[match.start():match.end()] = " " * (match.end() - match.start())
            attributed.append(value)
    return "".join(masked), attributed


def _valid_quantity(value):
    return (isinstance(value, dict) and type(value.get("value")) in (int, float)
            and math.isfinite(value["value"]) and isinstance(value.get("unit"), str)
            and bool(value["unit"].strip()))


def _captured_metric_available(record, finding):
    """Inspect only captured result locations for the selected metric/model.

    Input records, limits, source labels and quantities in other model results
    must not supply a missing selected result. This does not validate physics.
    """
    criterion = finding.get("evidence")
    if isinstance(criterion, dict) and _valid_quantity(criterion.get("metric")):
        return True
    metric, model_id = finding.get("metric"), finding.get("model_id")
    if not isinstance(metric, str) or not isinstance(model_id, str):
        return False
    for item in record.get("evidence", {}).values():
        if not isinstance(item, dict):
            continue
        if item.get("kind") == "model":
            model = item.get("model")
            if not isinstance(model, dict) or model.get("id") != model_id:
                continue
            result = item.get("recorded_evidence")
        elif item.get("kind") == "recheck" and item.get("model_id") == model_id:
            # An inconsistent fresh result cannot ground a claim about the
            # locked calculation even if it happens to contain a quantity.
            if item.get("matches_saved_result") is not True:
                continue
            result = item.get("fresh_result")
        else:
            continue
        if (isinstance(result, dict) and result.get("status") == "completed"
                and isinstance(result.get("metrics"), dict)
                and _valid_quantity(result["metrics"].get(metric))):
            return True
    return False


def _unsupported_result_statements(text, finding):
    """Find specific affirmative predictions, not general semantic mistakes.

    Conditional certainty ("would exceed if corrected") still asserts a result
    that needs a calculation. Questions, uncertainty, and proposed analyses do
    not. The vocabulary and prefix checks are intentionally limited.
    """
    subjects = [r"equilibrium[_\s]+temperature", r"temperature", r"stress",
                r"strain", r"drag[_\s]+force", r"force", r"deflection",
                r"tracking[_\s]+error", r"propellant[_\s]+margin", r"delta[-_\s]+v",
                r"burn[_\s]+time", r"requirement", r"criterion", r"result", r"metric"]
    metric = finding.get("metric")
    if isinstance(metric, str) and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,100}", metric):
        subjects.insert(0, r"[_\s]+".join(re.escape(part) for part in metric.casefold().split("_")))
    subject = r"\b(?:" + "|".join(subjects) + r")\b"
    comparison = (
        r"(?:(?:(?:would|will|does|did)\s+)?(?:exceed\w*|surpass\w*|violat\w*|"
        r"satisf\w*|meet\w*|pass\w*|fail\w*)\b|"
        r"(?:would|will)\s+(?:be\s+)?(?:met|not[_\s]+met|satisfied|above|below|within)\b|"
        r"(?:is|was|would\s+be|will\s+be)\s+(?:above|below|greater\s+than|less\s+than)\b)"
    )
    quantity = r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?\s*(?:kg\*m\^2|N\*m\*s/rad|N\*m/rad|N\*m|rad/s|rad|kg/m\^3|m/s\^2|kg/s|m/s|m\^4|m\^2|Pa|kg|K|W|J|N|s|m)\b"
    # Use original case for unit recognition; other words are case-insensitive.
    assertion = re.compile(subject + r"\s+(?:" + comparison + r"|"
                           r"(?:(?:would|will)\s+(?:be|reach|equal)|is|was|equals?|reaches?|"
                           r"is\s+calculated\s+(?:as|at)|is\s+predicted\s+to\s+be)\s+" + quantity + r")", re.I)
    found = []
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", text):
        for match in assertion.finditer(sentence):
            prefix = sentence[:match.start()].casefold()
            # A later contrast starts a new assertion rather than extending
            # an earlier "cannot determine" qualification across the sentence.
            prefix = re.split(r"\b(?:but|however|nevertheless)\b", prefix)[-1]
            if _nonasserted_prefix(prefix):
                continue
            if re.search(r"\b(?:background|ambient|maximum|minimum|limit|declared|required|input|specified)\s+$", prefix):
                continue
            found.append(sentence.strip())
            break
    return found


def _literal_comparison_contradictions(text):
    """Check narrow explicit same-unit inequalities, not general prose logic.

    Compare adjacent literal quantities only when their intervening words are
    an unambiguous affirmative direction. Do not infer quantities from model
    names, convert units, decide a requirement verdict or treat an absent flag
    as semantic validation. Questions, requested checks and explicit negations
    remain review-only. Original receipt text is never changed.
    """
    bridge = re.compile(
        r"\s*[,)]?\s*(?:(?:which|that)\s+)?(?:(?:is|was)\s+)?"
        r"(?P<relation>exceeds?|greater\s+than|above|less\s+than|below)\s+"
        r"(?:(?:the|its|declared|stated|recorded|specified|maximum|minimum|"
        r"upper|lower|bound|threshold|requirement|limit|value|of)\s+){0,8}", re.I)
    found = []
    quantities = list(_QUANTITY.finditer(text))
    for left, right in zip(quantities, quantities[1:]):
        if left.group(2) != right.group(2):
            continue
        match = bridge.fullmatch(text[left.end():right.start()])
        if match is None:
            continue
        prefix = re.split(r"(?<=[.!?;])\s+|\n+", text[:left.start()])[-1].casefold()
        if (_nonasserted_prefix(prefix)
                or re.search(r"\b(?:whether|if)\b", prefix)
                or re.search(r"\b(?:check|verify|determine|assess|investigate)\b", prefix)
                or re.match(r"\s*(?:does|is|was|can|could|would|will)\b", prefix)):
            continue
        first, second = (float(item.group(1).replace(",", "")) for item in (left, right))
        if not math.isfinite(first) or not math.isfinite(second):
            continue
        relation = match.group("relation").casefold()
        greater = relation.startswith("exceed") or relation in {"greater than", "above"}
        if (first > second if greater else first < second):
            continue
        # Equal printed values may reflect independent rounding. Do not infer
        # a strict comparison outcome from that presentation ambiguity.
        if first == second:
            continue
        found.append(text[left.start():right.end()])
    return found


def explanation_acceptance(record):
    """Return the limited blocking decision without changing the raw receipt.

    Call this on the proposed complete record before accepting its finish.
    Preserve rejected prose separately for inspection; this helper never edits
    it. Acceptance is only absence of the allowlisted detectable problems.
    """
    quality = evaluate_explanation(record)
    blocked = sorted({item["code"] for item in quality["flags"]
                      if item["severity"] == "error" and item["code"] in _BLOCKING_CODES})
    return {"schema": ACCEPTANCE_SCHEMA, "policy": "limited_deterministic_blocking",
            "accepted": not blocked, "blocked_codes": blocked, "quality": quality}


def _selected_test_claims(record, summary):
    """Separate only explicitly attributed measurement outcome clauses.

    This is a narrow phrase check, not semantic verification. A clause with
    both design and measurement subjects remains visible to the old checks.
    Numbers and approval/validation claims are always checked in the original
    text. No source-label prose is allowed to supply a measurement value.
    """
    bundle = record.get("test_evidence")
    if bundle is None:
        return summary, None, [], []
    flags, quantities = [], []
    def add(code, message, severity="error"):
        flags.append({"code": code, "message": message, "severity": severity})
    evidence = record.get("evidence", {})
    captured = [item.get("selected_test_evidence") for item in evidence.values()
                if isinstance(item, dict) and item.get("kind") == "requirement"] if isinstance(evidence, dict) else []
    try:
        # Python equates False with 0 and True with 1. The cited context must
        # preserve the actual frozen JSON records, including these types.
        captured_matches = (isinstance(bundle, dict) and len(captured) == 1
                            and json.dumps(captured[0], sort_keys=True, allow_nan=False)
                            == json.dumps(bundle, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError):
        captured_matches = False
    if not captured_matches:
        add("test_evidence_binding_mismatch", "The selected test row is not exactly captured in the cited requirement evidence.")
        return summary, bundle, flags, quantities
    try:
        row = bundle["recorded"]["row"]
        measured = row["measurement_requirement"]
        agreement = row["prediction_agreement"]
        if (measured["status"] not in {"met", "not_met", "not_assessed"}
                or agreement["status"] not in {"within_tolerance", "outside_tolerance", "not_assessed"}):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        add("test_evidence_binding_mismatch", "The captured selected test row has no recognized comparison findings.")
        return summary, bundle, flags, quantities
    for value in (measured.get("metric"), measured.get("limit"), agreement.get("prediction"), agreement.get("tolerance")):
        if _valid_quantity(value):
            quantities.append((value["value"], value["unit"]))
    unit = (agreement.get("prediction") or {}).get("unit")
    for field in ("signed_difference", "absolute_difference"):
        number = agreement.get(field)
        if type(number) in (int, float) and math.isfinite(number) and isinstance(unit, str):
            quantities.append((number, unit))
    masked = list(summary)
    # Restrict exemptions to one explicitly measured clause. Conjunctions and
    # punctuation delimit them, so a following design claim is never hidden.
    clauses = re.finditer(r"[^,;.!?\n]+(?:\.(?!\s|$)[^,;.!?\n]+)*", summary)
    for match in clauses:
        clause = match.group(0).casefold()
        agreement_subject = bool(re.search(r"\b(?:prediction|recorded|measurement)\s+agreement\b", clause))
        if not agreement_subject and not re.search(r"\b(?:measurement|measurements|measured|observed|test\s+row)\b", clause):
            continue
        if re.search(r"\b(?:canonical|design|calculated)\b", clause):
            add("test_evidence_ambiguous_attribution", "A clause blends design and measurement claims; review which evidence supports each statement.", "warning")
            continue
        # Agreement wording is a separate question and is not a requirement
        # verdict. It normally does not trigger the canonical-status patterns.
        # A proposed review/question does not assert that its outcome is true.
        # Keep this local to selected-test wording rather than broadening the
        # existing canonical acceptance policy.
        if re.search(r"\b(?:check|review|verify|determine|assess|investigate|confirm|establish)\s+whether\b", clause):
            continue
        if agreement_subject or re.search(r"\b(?:agreement|tolerance|agrees?|differs?|difference)\b", clause):
            within = _affirmative(r"\b(?:within[_\s]+tolerance|agrees?\s+with|agrees?\s+to)\b", clause)
            outside = _affirmative(r"\b(?:outside[_\s]+tolerance|exceeds?\s+(?:the\s+)?tolerance|does\s+not\s+agree)\b", clause)
            unassessed = _affirmative(r"\b(?:not[_\s]+assessed|unassessed)\b", clause)
            if ((within and agreement["status"] != "within_tolerance")
                    or (outside and agreement["status"] != "outside_tolerance")
                    or (unassessed and agreement["status"] != "not_assessed")):
                add("test_evidence_status_contradiction", "The measurement-agreement statement conflicts with the frozen row's explicit tolerance finding.")
            continue
        negative = _affirmative(r"\b(?:not[_\s]+met|unmet|violat\w*|exceed\w*|fails?\s+(?:the\s+)?(?:criterion|requirement|limit))\b", clause)
        positive = _affirmative(r"\b(?:meets?|met|satisf\w*|passes?|passed)\b", clause)
        if negative:
            positive = False
        if ((positive and measured["status"] != "met")
                or (negative and measured["status"] != "not_met")):
            add("test_evidence_status_contradiction", "The explicitly measured criterion statement conflicts with the frozen row's criterion finding.")
        elif positive or negative:
            # Only a matching attributed status statement is exempted from
            # canonical wording checks. All other clauses keep those checks.
            if not re.search(r"\b(?:but|while|however|and|whereas)\b", clause):
                masked[match.start():match.end()] = " " * (match.end() - match.start())
    original = summary.casefold()
    if _affirmative(r"\b(?:validates?|validated|proves?|confirms?)\s+(?:the\s+)?(?:hardware|model|physics|physical\s+validity)\b|\b(?:hardware|model|physics)\s+(?:is|has\s+been|are)\s+(?:validated|proven|confirmed)\b|\b(?:overrides?|replaces?)\s+(?:the\s+)?canonical\s+(?:finding|review|result)\b|\b(?:discrepancy|difference)\s+proves?\s+(?:a\s+)?(?:defect|failure)\b", original):
        add("test_evidence_validation_claim", "A supplied scalar comparison cannot establish hardware/model validity, prove a defect, or override the canonical finding.")
    if not re.search(r"\b(?:unverified|not\s+(?:independently\s+)?verified|declared\s+conditions)\b", original):
        add("test_conditions_not_explained", "Review whether the explanation distinguishes declared conditions from independently verified applicability.", "warning")
    return "".join(masked), bundle, flags, quantities


def evaluate_explanation(record):
    """Flag bounded, observable explanation problems, preserving raw prose.

    This does not parse general logic, reliably identify every negation, prove
    numerical attribution, or recognize every valid paraphrase. Unsupported
    quantity flags require review: proposed values/conversions are not always
    fabricated findings. No 'quality passed' or semantic score is returned.
    """
    if not isinstance(record, dict):
        raise ValueError("An investigation record is required.")
    summary = record.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("An investigation summary must be text.")
    text = summary.casefold()
    claim_summary, attributed_quotes = _attributed_source_quotes(record, summary)
    claim_summary, test_bundle, test_flags, test_quantities = _selected_test_claims(record, claim_summary)
    claim_text = claim_summary.casefold()
    finding = record.get("canonical_finding") or {}
    status = finding.get("status", record.get("finding_status"))
    flags = []

    def flag(code, message, severity="warning"):
        if not any(item["code"] == code for item in flags):
            flags.append({"code": code, "severity": severity, "message": message})

    for item in test_flags:
        flag(item["code"], item["message"], item["severity"])
    fact_links = evaluate_fact_links(record)
    for item in fact_links["flags"]:
        flag(item["code"], item["message"], item["severity"])

    ids = set(record.get("evidence", {}))
    citations = record.get("citations", [])
    exact_citations = isinstance(citations, list) and all(isinstance(item, str) for item in citations) and len(citations) == len(set(citations)) and set(citations) == ids
    if not exact_citations:
        flag("citation_mismatch", "Citations do not exactly match the recorded investigation evidence.", "error")
    if not summary.strip():
        flag("empty_summary", "The model did not provide an explanation.", "error")
    if status not in _MEANINGS:
        flag("missing_canonical_status", "No recognized canonical finding is available for this check.", "error")
    if (finding.get("status") is not None and record.get("finding_status") is not None
            and finding["status"] != record["finding_status"]):
        flag("recorded_status_mismatch", "The investigation status disagrees with its captured canonical finding.", "error")
    if status == "not_assessed":
        if _affirmative(r"\b(?:cannot|can\s+not|can't)\s+(?:be\s+)?(?:satisfied|met|achieved)\b|\b(?:physically\s+impossible|design\s+is\s+impossible)\b", claim_text):
            flag("unassessed_as_impossible", "The wording can turn missing evidence into a claim that the requirement or design cannot succeed.", "error")
        if _affirmative(r"\b(?:requirement|design|vehicle|rocket)\s+(?:has\s+|is\s+)?(?:failed|fails)\b", claim_text):
            flag("unassessed_as_failure", "The explanation describes physical or requirement failure despite an unassessed finding.", "error")
        if _affirmative(r"\b(?:cannot|can\s+not|can't)\s+(?:satisfy|meet|achieve)\s+(?:(?:the|this|a|declared|stated|current)\s+){0,3}(?:requirement|limit|criterion)\b", claim_text):
            flag("unassessed_satisfaction_wording", "The wording 'cannot satisfy/meet' can blur missing evidence with physical inability. Review the interpretation; satisfaction cannot be established from the available evidence.")
    metric_available = _captured_metric_available(record, finding)
    unsupported_statements = (_unsupported_result_statements(claim_summary, finding)
                              if status == "not_assessed" and not metric_available else [])
    if unsupported_statements:
        flag("unsupported_result_prediction", "The explanation asserts a quantitative result or criterion outcome although the captured model has no valid result for the selected metric. Correct inputs and rerun before predicting that outcome.", "error")
    comparison_contradictions = _literal_comparison_contradictions(claim_summary)
    if comparison_contradictions:
        flag("literal_comparison_contradiction", "An explicit same-unit numerical comparison contradicts the literal values printed in the explanation. Inspect the recorded metric and limit; this check does not determine requirement satisfaction.", "error")
    positive = _affirmative(r"\b(?:everything|all\s+(?:requirements|checks))\s+(?:(?:has|have|are|were|is|was)\s+)?(?:passed|passes|met)\b|\b(?:this|the)\s+requirement\s+(?:(?:is|was|has)\s+)?(?:met|satisfied|passes|passed)\b", claim_text)
    if status in {"not_met", "not_assessed"} and positive:
        flag("canonical_status_contradiction", "A positive outcome claim conflicts with the canonical requirement status.", "error")
    readiness_text = _readiness_claim_text(text if test_bundle is not None else claim_text)
    if _affirmative(r"\b(?:mission\s+success\s+is\s+guaranteed|guarantees?\s+mission\s+success|(?:ready|safe|cleared|approved)\s+(?:for|to)\s+launch|launch\s+(?:is\s+)?authorized)\b", readiness_text):
        flag("readiness_or_guarantee_claim", "Readiness or guarantee language requires review; this evidence does not authorize launch.", "error")
    status_words = {
        "met": r"\b(?:meets?|met|satisfied|passes|passed)\b",
        "not_met": r"\b(?:violat\w*|exceed\w*|not\s+met|unmet|shortfall|insufficient\s+propellant|fails?\s+the\s+(?:criterion|limit))\b",
        "not_assessed": r"\b(?:not\s+assessed|unassessed|missing\s+evidence|insufficient\s+evidence|cannot\s+(?:be\s+)?(?:establish\w*|determin\w*|assess\w*))\b",
    }
    # These exact internal status tokens are legitimate outcome vocabulary.
    # Normalize them only for wording checks, preserving original model text.
    status_text = re.sub(r"\bnot_(assessed|met|validated)\b", r"not \1", text)
    status_signaled = status in status_words and bool(re.search(status_words[status], status_text))
    if not status_signaled:
        flag("status_not_explained", "The text does not clearly express the canonical outcome in the checked vocabulary.")
    has_next_step = bool(re.search(r"\b(?:review|verify|obtain|provide|confirm|inspect|rerun|re-run|check|correct|measure|validate|collect|document)\b", text))
    if not has_next_step:
        flag("next_step_missing", "No concrete review-action verb was found; inspect whether the next step is useful.")
    has_scope = bool(re.search(r"\b(?:assumption\w*|bounded|scope|exclud\w*|limitation\w*|not\s+(?:assessed|validated)|does\s+not\s+(?:establish|prove)|only)\b", status_text))
    if not has_scope:
        flag("scope_not_explained", "The text does not clearly state the checked scope or limitations.")

    # Only structured value/unit records count as grounding, never quantities
    # injected into questions, source labels, model descriptions or old prose.
    quantities = list(test_quantities)
    def collect(value):
        if isinstance(value, dict):
            number, unit = value.get("value"), value.get("unit")
            if (type(number) in (int, float) and isinstance(unit, str)
                    and math.isfinite(number)):
                quantities.append((number, unit))
            for key, item in value.items():
                if key not in {"question", "source", "description", "summary"}:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect(finding.get("evidence"))
    collect(record.get("evidence", {}))
    unmatched = []
    for match in _QUANTITY.finditer(summary):
        literal, unit = match.groups()
        value = float(literal.replace(",", ""))
        # A modest display-rounding tolerance is intentionally not a proof that
        # the number is attributed to the correct input or result.
        if not any(unit == recorded_unit and math.isclose(value, recorded, rel_tol=0.005, abs_tol=1e-9)
                   for recorded, recorded_unit in quantities):
            unmatched.append(match.group(0))
    if unmatched:
        flag("unmatched_quantity", "One or more literal quantities are absent from structured scoped evidence; review their attribution.")
        if test_bundle is not None:
            flag("test_evidence_unmatched_quantity", "The selected-test explanation includes a literal quantity absent from its scoped recorded evidence.", "error")
    return {"schema": QUALITY_SCHEMA, "method": "deterministic_limited_checks",
            "checks": {"has_summary": bool(summary.strip()), "canonical_status_available": status in _MEANINGS,
                       "citations_match_records": exact_citations, "status_signaled": status_signaled,
                       "review_action_signaled": has_next_step, "scope_signaled": has_scope,
                       "captured_metric_available": metric_available},
            "flags": flags, "unmatched_quantities": unmatched,
            "fact_links": fact_links,
            "unsupported_result_statements": unsupported_statements,
            "literal_comparison_contradictions": comparison_contradictions,
            "attributed_source_quotes": attributed_quotes,
            "review_required": bool(flags), "semantic_accuracy_established": False,
            "limitations": "Phrase and literal-quantity checks are incomplete heuristics. A clean result does not establish semantic accuracy or engineering validity."}
