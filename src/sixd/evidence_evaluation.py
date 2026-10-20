"""Three-case evidence-link comparison preparation, separate from selection proof.

These are AI-authored development cases. Offline execution tests orchestration,
never the named models' engineering correctness, latency or billed cost.
"""
from copy import deepcopy

from . import model_evaluation as baseline, workflow_evaluation as workflow
from .project_investigation import validate_investigation_view

PLAN_SCHEMA = "sixd.evidence-evaluation-plan.v2"
REPORT_SCHEMA = "sixd.evidence-evaluation-report.v2"
EXPLANATION_POLICY = "application_roles_v1"
CASE_IDS = ("orbit-met", "limit-only-change", "unsupported-control")
BATCH_CAP_USD = 2.00
BATCH_REQUESTS = 54


def build_plan(*, temporary_root=None):
    """Prepare fixed, identical snapshots for all candidates; no inference."""
    original = workflow.build_plan(temporary_root=temporary_root)
    selected = {case["id"]: case for case in original["cases"]}
    cases = []
    focus = {
        "orbit-met": "Explain the saved status, scope and next checks in words only. The app displays metric, limit and exact grid comparisons; do not copy quantities or source tokens. Distinguish grid agreement from true error and physical applicability.",
        "limit-only-change": "Explain the recorded revision change in words, distinguishing a changed requirement limit from unchanged physical inputs and model metrics. The app owns exact numerical evidence; do not type quantities, revision numbers or source tokens.",
        "unsupported-control": "Explain why the control requirement remains unassessed rather than failed. Identify concrete missing analysis inputs and the next applicable check without inventing solver results or numerical design changes.",
    }
    for identity in CASE_IDS:
        case = deepcopy(selected[identity])
        case["question"] = focus[identity]
        case["explanation_policy"] = EXPLANATION_POLICY
        case["case_digest"] = baseline._digest(baseline._case_payload(case))
        cases.append(case)
    plan = {
        "schema": PLAN_SCHEMA, "state": "prepared_offline", "live_calls": 0,
        "explanation_policy": EXPLANATION_POLICY, "cases": cases,
        "settings": deepcopy(baseline.SETTINGS), "candidates": deepcopy(list(baseline.CANDIDATES)),
        "manual_review_criteria": deepcopy(baseline.MANUAL_CRITERIA) + [
            "The app assigns displayed numerical roles to their exact captured source, revision, label and unit; model commentary remains qualitative.",
            "Grid differences retain the exact grid pair; revision changes retain the correct before/after scope.",
            "Concrete next checks remain review guidance rather than invented evidence or guaranteed outcomes."],
        "coverage_limit": "Three AI-authored constructed cases, not independent aerospace, held-out, customer or human-graded validation.",
        "budget_policy": {"batch_cap_usd": BATCH_CAP_USD, "max_request_reservations": BATCH_REQUESTS,
            "per_case_max_requests": 6, "cumulative_allowance_unchanged": True,
            "existing_ledger_required": True, "reset_ledger": False,
            "automatic_retries": 0, "automatic_model_selection": False,
            "live_requests_enabled_by_plan": False},
        "active_model_changed": False,
    }
    plan["plan_digest"] = baseline._digest(plan)
    validate_plan(plan)
    return plan


def validate_plan(plan, *, require_current_sources=True):
    if (not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA
            or plan.get("plan_digest") != baseline._digest({k: v for k, v in plan.items() if k != "plan_digest"})
            or plan.get("explanation_policy") != EXPLANATION_POLICY
            or plan.get("settings") != baseline.SETTINGS
            or plan.get("candidates") != list(baseline.CANDIDATES)
            or tuple(case["id"] for case in plan.get("cases", [])) != CASE_IDS
            or plan.get("budget_policy", {}).get("batch_cap_usd") != BATCH_CAP_USD
            or plan.get("budget_policy", {}).get("max_request_reservations") != BATCH_REQUESTS):
        raise ValueError("Use the intact three-case evidence-link evaluation plan.")
    for case in plan["cases"]:
        if (case.get("case_digest") != baseline._digest(baseline._case_payload(case))
                or case.get("explanation_policy") != EXPLANATION_POLICY
                or case.get("evaluation_policy") != baseline.CASE_POLICY
                or case["expected"]["requires_changes"] is not (case["view"].get("prior_run") is not None)):
            raise ValueError("The evidence-link evaluation case changed.")
        validate_investigation_view(case["view"], case["requirement_id"], require_current_sources=require_current_sources)
        baseline._assert_expected(case["view"], case["requirement_id"], case["expected"])
    return True


def run_comparison(plan, factory, *, mode="offline", on_case=None):
    validate_plan(plan)
    from .explanation_quality import evaluate_explanation
    report = baseline._run_checked_comparison(plan, factory, quality_evaluator=evaluate_explanation,
        mode=mode, on_case=on_case, report_schema=REPORT_SCHEMA)
    report["explanation_policy"] = EXPLANATION_POLICY
    report["coverage_limit"] = plan["coverage_limit"]
    report["budget_policy"] = deepcopy(plan["budget_policy"])
    report["independent_human_review"] = False
    for row in report["rows"]:
        receipt = row.get("receipt") or {}
        row["fact_policy_recorded"] = receipt.get("evidence_facts_prose_policy") == EXPLANATION_POLICY
        row["fact_contract_accepted"] = (row["fact_policy_recorded"] and receipt.get("state") == "completed"
            and (receipt.get("explanation_acceptance") or {}).get("accepted") is True)
        row["referenced_fact_count"] = len((receipt.get("explanation_quality") or {}).get("fact_links", {}).get("references", []))
    report["report_digest"] = baseline._digest({k: v for k, v in report.items() if k != "report_digest"})
    return report


def scorecard(report):
    """Report workflow results without upgrading them into semantic approval."""
    expected_policy = {REPORT_SCHEMA: EXPLANATION_POLICY,
                       "sixd.evidence-evaluation-report.v1": "evidence_links_v1"}.get(report.get("schema"))
    if (expected_policy is None
            or report.get("report_digest") != baseline._digest({k: v for k, v in report.items() if k != "report_digest"})
            or report.get("explanation_policy") != expected_policy):
        raise ValueError("The evidence-link comparison report is inconsistent.")
    candidates = []
    for candidate in report["candidates"]:
        rows = [row for row in report["rows"] if row["candidate_id"] == candidate["id"]]
        candidates.append({"candidate_id": candidate["id"], "model": candidate["model"], "label": candidate["label"],
            "planned": len(rows), "attempted": sum(row["state"] != "not_run" for row in rows),
            "completed": sum(row["state"] == "completed" for row in rows),
            "untested": sum(row["state"] == "not_run" for row in rows),
            "workflow_passes": sum(bool((row.get("score") or {}).get("workflow_gate_pass")) for row in rows),
            "fact_contract_passes": sum(row.get("fact_contract_accepted") is True for row in rows),
            "linked_explanations": sum(row.get("fact_contract_accepted") is True and row.get("referenced_fact_count", 0) > 0 for row in rows),
            "stopped_cases": [{"case_id": row["case_id"], "error_code": (row.get("receipt") or {}).get("error_code") or row.get("error_code"),
                "reason": (row.get("receipt") or {}).get("error") or row.get("reason")}
                for row in rows if row["state"] not in {"completed", "not_run"}],
            "reserved_usd": sum(row.get("reserved_usd") or 0 for row in rows),
            "elapsed_seconds": sum(row.get("elapsed_seconds") or 0 for row in rows),
            "semantic_review": "pending_independent_human_review"})
    return {"schema": "sixd.evidence-scorecard.v1", "mode": report["mode"], "report_digest": report["report_digest"],
        "explanation_policy": expected_policy, "candidates": candidates, "active_model_changed": False,
        "semantic_accuracy_established": False, "billed_cost_usd": None,
        "note": "Workflow completion and bounded fact checks do not establish semantic correctness. Skipped cases are untested; reservations are not billed cost."}
