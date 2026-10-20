"""Prepared comparison of project investigation orchestration.

The fixed case pack is a constructed development evaluation, not customer or
flight evidence. Providers are explicitly injected by the trusted host, which
owns authorization, private credentials and the shared spending ledger. This
module never constructs a transport, changes routing or enables a candidate.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import tempfile
from time import perf_counter

from .project_examples import example_projects
from .project_investigation import investigate_project, validate_investigation_view
from .workspace import WorkspaceStore
from .providers import ERROR_CODES, ProviderError


LEGACY_PLAN_SCHEMA = "sixd.model-evaluation-plan.v1"
LEGACY_REPORT_SCHEMA = "sixd.model-evaluation-report.v1"
PLAN_SCHEMA = "sixd.model-evaluation-plan.v2"
REPORT_SCHEMA = "sixd.model-evaluation-report.v2"
CASE_POLICY = "sixd.model-evaluation-case-policy.v2"
BATCH_CAP_USD = 1.50
BATCH_REQUESTS = 90
CANDIDATES = (
    {"id": "nano", "label": "Nemotron 3 Nano", "model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
     "input_usd_per_million": 0.06, "output_usd_per_million": 0.24, "per_case_cap_usd": 0.10},
    {"id": "super", "label": "Nemotron 3 Super", "model": "nvidia/nemotron-3-super-120b-a12b",
     "input_usd_per_million": 0.30, "output_usd_per_million": 0.90, "per_case_cap_usd": 0.20},
    {"id": "ultra", "label": "Nemotron 3 Ultra", "model": "nvidia/Nemotron-3-Ultra-550b-a55b",
     "input_usd_per_million": 1.00, "output_usd_per_million": 3.00, "per_case_cap_usd": 0.35},
)
SETTINGS = {
    "max_output_tokens": 2048, "inference_profile": "native_no_thinking",
    "selection_protocol": "forced_action_v1", "max_requests_per_case": 6,
    "automatic_retries": 0, "model_fallback": False,
}
MANUAL_CRITERIA = [
    "Explanation agrees with the canonical requirement result and its numerical evidence.",
    "Missing evidence is described as unresolved, never an impossible or failed design.",
    "No invented solver, physical test, subsystem interaction, measurement or launch clearance.",
    "Next steps name useful checks or missing data, preserve units and declared model limits.",
    "Revision explanation distinguishes changed thresholds from changed physical inputs.",
]


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return sha256(_encode(value).encode("utf-8")).hexdigest()


def _case_payload(case):
    return {key: value for key, value in case.items() if key != "case_digest"}


def _reference_temperature(heat):
    # Independent closed-form oracle, not a call to the maintained adapter.
    return math.pow(heat / (0.8 * 5.670374419e-8) + math.pow(3.0, 4), 0.25)


def _assert_expected(view, requirement_id, expected):
    finding = view["run"]["review"]["findings"][requirement_id]
    model = view["run"]["model_results"][finding["model_id"]]
    if finding["status"] != expected["status"] or model["status"] != expected["model_status"]:
        raise ValueError("The constructed case disagrees with its independent expected state.")
    reference = expected.get("reference_metric")
    if reference is not None:
        observed = model["metrics"][reference["name"]]
        if (observed["unit"] != reference["unit"] or not math.isclose(
                observed["value"], reference["value"], rel_tol=1e-11, abs_tol=1e-11)):
            raise ValueError("The constructed case does not match the independent reference calculation.")
    if expected["model_status"] != "completed" and model["metrics"]:
        raise ValueError("An unassessed case must not contain quantitative model results.")


def build_evaluation_plan(*, temporary_root=None):
    """Calculate six fixed examples in disposable storage; perform no inference.

    Each returned case contains the same locked view and question that every
    candidate will receive. Its independent expected metric/status is evaluator
    data and is not added to the model's prompt or available tools. The held-out
    case varies the demonstrated drag inputs rather than repeating the UI case.
    """
    baseline = example_projects()["baseline"]
    cases = []
    scratch = Path(temporary_root) if temporary_root is not None else Path(__file__).resolve().parents[2] / "work"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sixd-evaluation-", dir=scratch) as temporary:
        store = WorkspaceStore(Path(temporary) / "constructed.sqlite3")

        def add(identity, description, requirement, expected, *, edits=None,
                unsupported=False, revision_edit=None, held_out=False):
            project = deepcopy(baseline)
            project["project_id"] = "evaluation-" + identity
            project["name"] = "Constructed evaluation: " + description
            if unsupported:
                gap = example_projects()["missing_evidence"]
                project["inputs"]["maximum_tracking_error"] = deepcopy(gap["inputs"]["maximum_tracking_error"])
                project["models"].append(deepcopy(gap["models"][-1]))
                project["requirements"].append(deepcopy(gap["requirements"][-1]))
            for name, fields in (edits or {}).items():
                project["inputs"][name].update(fields)
            store.create_project(project)
            view = store.run(project["project_id"], 1)
            if revision_edit:
                changed = deepcopy(view["project"])
                for name, fields in revision_edit.items():
                    changed["inputs"][name].update(fields)
                store.save_revision(project["project_id"], 1, changed)
                view = store.run(project["project_id"], 2)
            _assert_expected(view, requirement, expected)
            has_prior = view.get("prior_run") is not None
            case = {"id": identity, "description": description,
                    "evaluation_policy": CASE_POLICY,
                    "constructed": True, "held_out_variation": held_out,
                    "requirement_id": requirement, "view": view,
                    "question": (
                        "Explain the selected saved requirement's actual result and evidence limits. "
                        "Identify concrete next engineering checks or information needed. "
                        + ("Read and cite the recorded revision differences, and explain whether the changed result "
                           "comes from an input, a requirement limit, or missing evidence. " if has_prior else
                           "This is the first reviewed revision; do not invent earlier changes or require a change comparison. ") +
                        "Do not authorize launch or assume unsupported capabilities."),
                    "expected": deepcopy(expected)}
            case["expected"]["requires_changes"] = has_prior
            case["case_digest"] = _digest(_case_payload(case))
            cases.append(case)

        thermal = lambda heat, status: {
            "status": status, "model_status": "completed", "requires_recheck": True,
            "requires_changes": False, "changed_inputs": [],
            "reference_metric": {"name": "equilibrium_temperature", "unit": "K",
                                 "value": _reference_temperature(heat)},
        }
        add("thermal-met", "Supported thermal criterion met", "thermal_limit", thermal(200, "met"))
        add("thermal-exceeded", "Supported thermal criterion exceeded at 700 W", "thermal_limit",
            thermal(700, "not_met"), edits={"heat_input": {"value": 700}})
        add("unsupported-control", "Control model unavailable", "control_tracking",
            {"status": "not_assessed", "model_status": "not_assessed", "requires_recheck": False,
             "requires_changes": False, "changed_inputs": []}, unsupported=True)
        add("invalid-unit", "Thermal heat unit unsupported", "thermal_limit",
            {"status": "not_assessed", "model_status": "invalid_inputs", "requires_recheck": True,
             "requires_changes": False, "changed_inputs": []}, edits={"heat_input": {"unit": "kW"}})
        limit = thermal(200, "not_met")
        limit.update(changed_inputs=["maximum_temperature"], limit_only_change=True)
        add("limit-only-change", "Requirement limit changes while calculated temperature stays fixed",
            "thermal_limit", limit, revision_edit={"maximum_temperature": {"value": 250}})
        drag = 0.5 * 0.037 * 173 ** 2 * 0.82 * 0.63
        add("held-out-drag", "Held-out single-condition drag inputs", "drag_limit",
            {"status": "met", "model_status": "completed", "requires_recheck": True,
             "requires_changes": False, "changed_inputs": [],
             "reference_metric": {"name": "drag_force", "unit": "N", "value": drag}},
            edits={"density": {"value": 0.037}, "relative_speed": {"value": 173},
                   "drag_coefficient": {"value": 0.82}, "reference_area": {"value": 0.63},
                   "maximum_drag_force": {"value": 300}}, held_out=True)
    plan = {
        "schema": PLAN_SCHEMA, "state": "prepared_offline", "live_calls": 0,
        "purpose": "Compare bounded requirement investigation quality on identical constructed evidence.",
        "coverage_limit": "Six constructed cases are an initial screen, not a general engineering benchmark.",
        "settings": deepcopy(SETTINGS), "candidates": deepcopy(list(CANDIDATES)), "cases": cases,
        "metadata": {"source": "Founder account console", "observed_at": "2026-10-15",
                     "currency": "USD", "prices_require_reverification_before_live": True,
                     "candidate_protocol_compatibility": "unverified_except_prior_nano_integration"},
        "budget_policy": {"cumulative_allowance_usd": 29.5,
                          "cumulative_allowance_kind": "Approved maximum from existing balance; actual configured ledger may remain lower.",
                          "future_batch_maximum_usd": BATCH_CAP_USD,
                          "max_request_reservations": BATCH_REQUESTS,
                          "per_case_max_requests": SETTINGS["max_requests_per_case"],
                          "per_case_reservation_policy": "Model-price-aware headroom; identical evidence, protocol and output limits.",
                          "preflight_against_remaining_allowance_required": True,
                          "full_pack_completion_guaranteed": False,
                          "existing_ledger_required": True, "reset_ledger": False,
                          "live_requests_enabled_by_plan": False,
                          "note": "The plan grants no spending authority; host authorization, current metadata and the existing ledger gate every live request."},
        "manual_review_criteria": deepcopy(MANUAL_CRITERIA),
        "selection_policy": {"offline_can_enable": False, "automatic_enable": False,
                             "requires_all_live_cases": True, "requires_manual_review": True,
                             "candidate_must_pass_all_cases": True,
                             "paired_baseline_failure_requires_explicit_review": True,
                             "spending_or_transport_failure_is_not_quality_benefit": True,
                             "stronger_model_requires_demonstrated_benefit": True},
    }
    plan["plan_digest"] = _digest(plan)
    return plan


def validate_evaluation_plan(plan, *, require_current_sources=True):
    """Reject mutated case/evidence/settings packs before an injected provider runs."""
    if (not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA
            or plan.get("plan_digest") != _digest({k: v for k, v in plan.items() if k != "plan_digest"})
            or plan.get("settings") != SETTINGS or plan.get("candidates") != list(CANDIDATES)
            or len(plan.get("cases", [])) != 6):
        raise ValueError("Use an intact prepared evaluation plan.")
    ids = set()
    for case in plan["cases"]:
        if (case["id"] in ids or case.get("case_digest") != _digest(_case_payload(case))
                or case.get("evaluation_policy") != CASE_POLICY
                or case["expected"].get("requires_changes") is not (case["view"].get("prior_run") is not None)):
            raise ValueError("The evaluation case pack changed.")
        ids.add(case["id"])
        validate_investigation_view(case["view"], case["requirement_id"], require_current_sources=require_current_sources)
        _assert_expected(case["view"], case["requirement_id"], case["expected"])
    return True


def evaluation_summary(plan):
    """Small UI/API representation; no project records, factory or paid trigger."""
    validate_evaluation_plan(plan)
    return {"schema": PLAN_SCHEMA, "state": plan["state"], "plan_digest": plan["plan_digest"],
            "live_calls": 0, "active_model_changed": False, "winner": None,
            "candidates": deepcopy(plan["candidates"]), "settings": deepcopy(plan["settings"]),
            "cases": [{key: deepcopy(case[key]) for key in
                       ("id", "description", "constructed", "held_out_variation", "requirement_id")}
                      for case in plan["cases"]],
            "metadata": deepcopy(plan["metadata"]), "budget_policy": deepcopy(plan["budget_policy"]),
            "coverage_limit": plan["coverage_limit"],
            "manual_review_criteria": deepcopy(plan["manual_review_criteria"]),
            "selection_policy": deepcopy(plan["selection_policy"])}


def score_receipt(case, receipt, quality_evaluator=None):
    """Transparent workflow checks, separate from unproven prose correctness.

    Citation metrics measure exact identifier coverage, not whether prose claims
    are entailed by those sources. The canonical status is preserved by the
    runner; that fact alone does not grade the model's interpretation of it.
    """
    expected = case["expected"]
    evidence, citations = receipt.get("evidence", {}), receipt.get("citations", [])
    cited = set(citations)
    known = set(evidence)
    actions = [event["action"] for event in receipt.get("events", [])]
    model_id = case["view"]["run"]["review"]["findings"][case["requirement_id"]]["model_id"]
    recheck = evidence.get("recheck:" + model_id)
    changes = evidence.get("changes", {}).get("comparison")
    actual_changed = [] if changes is None else changes.get("changed_inputs", [])
    checks = {
        "completed": receipt.get("state") == "completed",
        "canonical_status_preserved": receipt.get("canonical_finding") ==
            case["view"]["run"]["review"]["findings"][case["requirement_id"]],
        "finding_status_recorded": receipt.get("finding_status") == expected["status"],
        "exact_evidence_ids": bool(known) and cited == known and len(citations) == len(cited),
        "required_reads": {"read_requirement", "read_model"}.issubset(actions),
        "recheck_policy": (recheck is not None and recheck.get("matches_saved_result") is True)
            if expected["requires_recheck"] else (recheck is None and "recheck_model" not in actions),
        "changes_read": "read_changes" in actions,
        "scoped_changes_correct": "read_changes" in actions and sorted(actual_changed) == sorted(expected["changed_inputs"]),
        "no_launch_authorization": receipt.get("launch_authorization") is False,
    }
    if case.get("evaluation_policy") == CASE_POLICY:
        # Version one required a changes read even for a first revision. Keep
        # that historical scoring intact, while the new pack requires it only
        # where a real preceding reviewed revision exists. Optional first-revision
        # reads are still checked if the model elects to collect that evidence.
        changes_read = "read_changes" in actions
        required = expected["requires_changes"]
        checks["changes_read"] = changes_read or not required
        checks["scoped_changes_correct"] = (
            changes_read and sorted(actual_changed) == sorted(expected["changed_inputs"])
            and ((changes is not None) if required else (changes is None))) or (not required and not changes_read)
        checks["relevant_changes_cited"] = not required or "changes" in cited
    if expected.get("limit_only_change"):
        before = case["view"]["prior_run"]["review"]["evidence"][model_id]["metrics"]
        after = case["view"]["run"]["review"]["evidence"][model_id]["metrics"]
        checks["unchanged_physics_evidence"] = before == after
    quality = quality_evaluator(deepcopy(receipt)) if quality_evaluator is not None else None
    return {"evaluation_policy": case.get("evaluation_policy", "sixd.model-evaluation-case-policy.v1"),
            "checks": checks, "workflow_checks_passed": sum(checks.values()),
            "workflow_checks_total": len(checks), "workflow_gate_pass": all(checks.values()),
            "citation_identifier_precision": len(cited & known) / len(cited) if cited else 0.0,
            "citation_identifier_recall": len(cited & known) / len(known) if known else 0.0,
            "prose_status_correctness": "manual_review_required",
            "unsupported_claims": "manual_review_required",
            "next_steps_usefulness": "manual_review_required",
            "revision_change_explained": "manual_review_required" if expected.get("requires_changes") else "not_applicable",
            "quality_checks": quality,
            "note": "No language-model judge or keyword score establishes semantic correctness."}


class _ObservedProvider:
    def __init__(self, provider):
        self.provider = provider
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.accepted_usage_records = 0
        self.request_digests = []

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def complete(self, messages, tools):
        self.request_digests.append(_digest({"messages": messages, "tools": tools}))
        turn = self.provider.complete(messages, tools)
        if isinstance(turn.usage, dict):
            for key in self.usage:
                value = turn.usage.get(key)
                if type(value) is int and value >= 0:
                    self.usage[key] += value
            self.accepted_usage_records += 1
        return turn


def _nonnegative(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def run_comparison(plan, provider_factory, *, quality_evaluator=None, mode="offline", on_case=None):
    """Exercise the actual runner using an explicitly injected trusted factory.

    Factory signature is ``factory(candidate, case)``. Inputs are deep copies so
    candidates cannot change each other's evidence or settings. This callback is
    trusted host code, never uploaded/project-provided executable material.
    Offline mode rejects live providers. Live mode additionally verifies the
    exact candidate model and common settings. The host factory must enforce
    authorized batch and per-case limits against the existing cumulative ledger.
    A failed case stops that candidate; there is no retry or model fallback.
    ``on_case(row)`` can return False to stop the entire batch after persistence.
    """
    validate_evaluation_plan(plan)
    return _run_checked_comparison(plan, provider_factory, quality_evaluator=quality_evaluator,
                                   mode=mode, on_case=on_case, report_schema=REPORT_SCHEMA)


def _run_checked_comparison(plan, provider_factory, *, quality_evaluator=None, mode="offline", on_case=None, report_schema=REPORT_SCHEMA):
    """Trusted host runner; caller must validate its versioned fixed case pack."""
    if mode not in ("offline", "live"):
        raise ValueError("Select explicit offline or live comparison mode.")
    rows, stopped = [], False
    for candidate in plan["candidates"]:
        failed = False
        for case in plan["cases"]:
            if stopped or failed:
                rows.append({"candidate_id": candidate["id"], "proposed_model": candidate["model"],
                             "case_id": case["id"], "case_digest": case["case_digest"], "state": "not_run",
                             "reason": "batch_stopped" if stopped else "earlier_candidate_case_failed",
                             "live_model_calls": 0, "receipt": None, "score": None})
                continue
            factory_candidate = {**deepcopy(candidate), "settings": deepcopy(plan["settings"])}
            try:
                provider = provider_factory(factory_candidate, deepcopy(case))
            except Exception as error:
                # Configuration/budget/transport construction failures may carry
                # secrets; preserve a controlled outcome instead of their text.
                row = {"candidate_id": candidate["id"], "proposed_model": candidate["model"],
                       "case_id": case["id"], "case_digest": case["case_digest"], "state": "failed",
                       "reason": "provider_factory_rejected", "live_model_calls": 0,
                       "receipt": None, "score": None}
                if isinstance(error, ProviderError):
                    code = getattr(error, "code", None)
                    if isinstance(code, str) and code in ERROR_CODES:
                        row["error_code"] = code
                rows.append(row)
                failed = True
                if on_case is not None and on_case(deepcopy(row)) is False:
                    stopped = True
                continue
            provider_mode = getattr(provider, "mode", None)
            if mode == "offline":
                if not isinstance(provider_mode, str) or not provider_mode.startswith("offline_"):
                    raise ValueError("The offline comparison accepts explicit offline providers only.")
            elif provider_mode != "live_token_factory" or getattr(provider, "model", None) != candidate["model"]:
                raise ValueError("Live comparison requires the exact candidate and live Token Factory provider.")
            config = getattr(provider, "config", None)
            if mode == "live":
                for key in ("max_output_tokens", "inference_profile", "selection_protocol"):
                    if getattr(config, key, None) != plan["settings"][key]:
                        raise ValueError("The live candidate settings do not match the common evaluation plan.")
            observed = _ObservedProvider(provider)
            start = perf_counter()
            receipt = investigate_project(deepcopy(case["view"]), case["requirement_id"],
                case["question"], observed, investigation_id="evaluation-" + candidate["id"] + "-" + case["id"])
            elapsed = perf_counter() - start
            # An offline fixture may label its model with a candidate name. Keep
            # that separate from actual live comparative model evidence.
            ledger = getattr(provider, "ledger", None)
            row = {"candidate_id": candidate["id"], "proposed_model": candidate["model"],
                         "case_id": case["id"], "case_digest": case["case_digest"],
                         "state": receipt["state"], "provider_mode": provider_mode,
                         "actual_provider_model": receipt["model"],
                         "elapsed_seconds": elapsed,
                         "elapsed_kind": "live_wall_clock" if mode == "live" else "offline_execution_only",
                         "score": score_receipt(case, receipt, quality_evaluator), "receipt": receipt,
                         "request_digests": observed.request_digests,
                         "usage": observed.usage, "usage_coverage": "accepted_responses_only",
                         "reserved_usd": _nonnegative(getattr(ledger, "reserved", None)),
                         "request_reservations": _nonnegative(getattr(ledger, "count", None)),
                         "live_model_calls": receipt["live_model_calls"], "billed_cost_usd": None}
            rows.append(row)
            failed = receipt["state"] != "completed"
            if on_case is not None and on_case(deepcopy(row)) is False:
                stopped = True
    report = {"schema": report_schema,
              "mode": "live_comparison" if mode == "live" else "offline_harness_validation",
              "live_calls": sum(row["live_model_calls"] for row in rows),
              "plan_digest": plan["plan_digest"], "created_at": datetime.now(timezone.utc).isoformat(),
              "settings": deepcopy(plan["settings"]), "candidates": deepcopy(plan["candidates"]),
              "rows": rows, "expected_rows": len(plan["candidates"]) * len(plan["cases"]),
              "winner": None, "enabled_models": [], "active_model_changed": False,
              "selection_state": "live_comparison_and_manual_review_pending",
              "note": ("Live case receipts require manual semantic review before a model decision."
                       if mode == "live" else "Fixtures validate the harness, not the named models' quality, latency or cost."),
              "manual_review_criteria": deepcopy(plan["manual_review_criteria"])}
    report["report_digest"] = _digest(report)
    return report


def run_offline_comparison(plan, provider_factory, *, quality_evaluator=None, on_case=None):
    return run_comparison(plan, provider_factory, quality_evaluator=quality_evaluator,
                          mode="offline", on_case=on_case)


def write_evaluation_artifact(path, artifact):
    """Append-only JSON artifact; never overwrites a ledger or active config."""
    if (not isinstance(artifact, dict) or artifact.get("schema") not in (
            PLAN_SCHEMA, REPORT_SCHEMA, LEGACY_PLAN_SCHEMA, LEGACY_REPORT_SCHEMA)):
        raise ValueError("Only evaluation plans and reports can be exported.")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(artifact, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    return destination


def candidate_selection_gate(report, candidate_id, *, manual_review=None, plan=None):
    """Return a review gate, never mutate production routing.

    A candidate must pass every current live case and an explicit semantic
    review. A paired baseline may have an observed model/prose failure, provided
    its exact receipt and attribution are reviewed. A budget or connection
    failure cannot establish that another model has better engineering quality.
    A positive result grants no automatic activation or general quality claim.
    """
    if candidate_id not in {candidate["id"] for candidate in CANDIDATES}:
        raise ValueError("Unknown comparison candidate.")
    result = {"candidate_id": candidate_id, "eligible": False, "enable": False,
            "reason": "Live comparison and a manually reviewed benefit are pending.",
            "manual_review_received": manual_review is not None,
            "automatic_enable": False, "active_model_changed": False}
    if candidate_id == "nano" or plan is None or not isinstance(manual_review, dict):
        return result
    try:
        # Selection is supported by the original immutable live comparison.
        # Current investigations separately require fresh source fingerprints.
        validate_evaluation_plan(plan, require_current_sources=False)
        if (report.get("schema") != REPORT_SCHEMA
                or report.get("report_digest") != _digest({k: v for k, v in report.items() if k != "report_digest"})
                or report.get("mode") != "live_comparison" or report.get("plan_digest") != plan["plan_digest"]
                or report.get("settings") != plan["settings"] or report.get("candidates") != plan["candidates"]
                or len(report.get("rows", [])) != 18):
            return result
        case_ids = {case["id"] for case in plan["cases"]}
        cases = {case["id"]: case for case in plan["cases"]}
        candidates = {c["id"]: c for c in plan["candidates"]}
        from .explanation_quality import evaluate_explanation
        candidate_rows = [row for row in report["rows"] if row["candidate_id"] == candidate_id]
        baseline_rows = [row for row in report["rows"] if row["candidate_id"] == "nano"]
        if (len(candidate_rows) != 6 or {row["case_id"] for row in candidate_rows} != case_ids
                or len(baseline_rows) != 6 or {row["case_id"] for row in baseline_rows} != case_ids):
            return result
        for row in candidate_rows:
            case = cases[row["case_id"]]
            if (row.get("provider_mode") != "live_token_factory" or row.get("live_model_calls", 0) < 1
                    or row.get("actual_provider_model") != candidates[candidate_id]["model"]
                    or row.get("case_digest") != case["case_digest"]
                    or not score_receipt(case, row["receipt"])["workflow_gate_pass"]
                    or row.get("request_reservations", 0) < 1
                    or row.get("reserved_usd", 0) <= 0
                    or any(flag["severity"] == "error" for flag in evaluate_explanation(row["receipt"])["flags"])):
                return result
        review = manual_review
        benefit = review.get("paired_benefit", {})
        judgments = review.get("case_reviews", [])
        baseline_judgments = review.get("baseline_case_reviews", [])
        if (review.get("schema") != "sixd.model-manual-review.v2"
                or review.get("report_digest") != report["report_digest"]
                or review.get("plan_digest") != plan["plan_digest"]
                or review.get("candidate_id") != candidate_id
                or not review.get("reviewer") or not review.get("reviewed_at")
                or review.get("no_critical_unsupported_claims") is not True
                or len(review.get("reviewed_case_ids", [])) != 6 or set(review["reviewed_case_ids"]) != case_ids
                or benefit.get("baseline_candidate_id") != "nano" or benefit.get("demonstrated") is not True
                or not benefit.get("rationale") or not benefit.get("case_ids")
                or not set(benefit["case_ids"]).issubset(case_ids)
                or len(benefit["case_ids"]) != len(set(benefit["case_ids"]))
                or len(judgments) != 6 or {item["case_id"] for item in judgments} != case_ids
                or any(not item.get("notes") or any(item.get(field) is not True for field in
                    ("canonical_status_correct", "claims_supported", "next_steps_useful")) for item in judgments)):
            return result
        if any(cases[item["case_id"]]["expected"]["requires_changes"]
               and item.get("revision_change_explained") is not True for item in judgments):
            return result
        if (len(baseline_judgments) != len(benefit["case_ids"])
                or {item["case_id"] for item in baseline_judgments} != set(benefit["case_ids"])):
            return result
        for judgment in baseline_judgments:
            row = next(row for row in baseline_rows if row["case_id"] == judgment["case_id"])
            receipt = row.get("receipt")
            case = cases[row["case_id"]]
            if (not isinstance(receipt, dict) or row.get("provider_mode") != "live_token_factory"
                    or row.get("actual_provider_model") != candidates["nano"]["model"]
                    or row.get("case_digest") != case["case_digest"]
                    or row.get("request_reservations", 0) < 1 or row.get("reserved_usd", 0) <= 0
                    or receipt.get("request_attempts", 0) < 1
                    or receipt.get("canonical_finding") != case["view"]["run"]["review"]["findings"][case["requirement_id"]]
                    or row.get("state") not in {"completed", "failed"}
                    or receipt.get("state") != row["state"]
                    or judgment.get("outcome") != row["state"]
                    or judgment.get("receipt_digest") != _digest(receipt)
                    or judgment.get("comparison_supports_benefit") is not True
                    or not judgment.get("notes")):
                return result
            if row["state"] == "completed":
                if row.get("live_model_calls", 0) < 1:
                    return result
            elif (judgment.get("failure_reviewed") is not True
                    or judgment.get("failure_attribution") not in {"model_protocol", "evidence_quality"}
                    or receipt.get("error_code") in {
                        "case_spending_limit", "batch_spending_limit", "cumulative_spending_limit",
                        "case_request_limit", "batch_request_limit", "session_disconnected",
                        "source_changed", "comparison_preflight_limit", "transport_error", "request_timeout",
                        "cumulative_budget_exhausted", "case_budget_exhausted", "batch_budget_exhausted",
                        "request_limit", "budget_ledger_error", "configuration_error", "provider_transport_error",
                        "verification_sources_changed", "recheck_mismatch", "session_changed",
                        "budget_approval_mismatch", "budget_reservation_invalid",
                    }):
                return result
    except (ValueError, KeyError, TypeError, StopIteration):
        return result
    result.update(eligible=True, reason="The candidate passed every recorded live case; explicit semantic review supports a documented paired benefit for that case pack. Current investigations still require fresh evidence. Activation remains a separate deliberate change.")
    return result
