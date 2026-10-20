"""Explicit comparison jobs, sharing the assistant's private session and ledger.

Status reads and connection never start inference. A batch is an explicit local
action; interrupted work is preserved, never retried or resumed automatically.
"""
from copy import deepcopy
from dataclasses import replace
import json
import math
import re
import threading
from uuid import uuid4

from .explanation_quality import evaluate_explanation
from .model_evaluation import CANDIDATES, build_evaluation_plan, run_comparison
from .providers import BudgetLedger, ProviderError, TokenFactoryProvider
from .workspace import ConflictError, WorkspaceError
from .workspace_ai import JobBudget, _digest, _encode, _now

BATCH_CAP_USD = 1.50
BATCH_REQUESTS = 90


def comparison_preflight(plan, config):
    """Offline request-size forecast; no real credential, transport or ledger.

    Use every available scoped read and a short synthetic finish. Reservations
    already include full output ceilings; add room for differing call-ID sizes.
    This is a capacity forecast, not a provider charge or a quality evaluation.
    """
    from .project_investigation import ProjectActionAdapter
    budgets = []

    class ForecastBudget:
        def __init__(self, candidate_id, case_id):
            self.candidate_id, self.case_id = candidate_id, case_id
            self.count, self.reserved = 0, 0.0

        def reserve(self, config, amount):
            self.count += 1
            self.reserved += amount

    def factory(candidate, case):
        forecast = ForecastBudget(candidate["id"], case["id"])
        budgets.append((forecast, candidate["per_case_cap_usd"]))
        settings = candidate["settings"]
        candidate_config = replace(config, model=candidate["model"],
            input_usd_per_million_ceiling=candidate["input_usd_per_million"],
            output_usd_per_million_ceiling=candidate["output_usd_per_million"],
            max_output_tokens=settings["max_output_tokens"], inference_profile=settings["inference_profile"],
            selection_protocol=settings["selection_protocol"])

        def transport(request):
            payload = json.loads(request.data)
            menu = json.loads(payload["messages"][-1]["content"])
            names = {item["action"] for item in menu["available_actions"]}
            action = next(name for name in ("read_requirement", "read_model", "read_changes", "recheck_model", "finish") if name in names)
            args = {"action": action, "evidence_ids": menu["recorded_evidence_ids"] if action == "finish" else [],
                    "summary": "Review the recorded finding, supplied inputs and model assumptions; missing evidence remains unresolved." if action == "finish" else ""}
            return {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "offline-capacity-" + action, "type": "function", "function": {
                    "name": "select_next_action", "arguments": json.dumps(args)}}]}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

        return TokenFactoryProvider(candidate_config, forecast, api_key="synthetic-offline-capacity-key-only",
                                    transport=transport, action_adapter=ProjectActionAdapter())

    report = run_comparison(plan, factory, mode="offline")
    cases = [{"candidate_id": b.candidate_id, "case_id": b.case_id, "requests": b.count,
              "forecast_reservation_usd": b.reserved, "with_headroom_usd": b.reserved * 1.15,
              "case_cap_usd": cap, "fits_case_cap": b.reserved * 1.15 <= cap and b.count <= 6}
             for b, cap in budgets]
    total = sum(case["with_headroom_usd"] for case in cases)
    return {"schema": "sixd.comparison-capacity.v1", "mode": "offline_forecast", "live_calls": 0,
            "plan_digest": plan["plan_digest"], "cases": cases, "forecast_with_headroom_usd": total,
            "batch_cap_usd": BATCH_CAP_USD, "request_reservations": sum(b.count for b, _ in budgets),
            "fits": len(cases) == 18 and all(c["fits_case_cap"] for c in cases) and total <= BATCH_CAP_USD
                    and all(row["state"] == "completed" for row in report["rows"]),
            "note": "Synthetic action-path capacity forecast with 15% headroom. Actual paths and reservations can differ; enforced caps still apply."}


class BatchBudget:
    def __init__(self, shared, check_session, lock, *, cap_usd=BATCH_CAP_USD, max_requests=BATCH_REQUESTS):
        if type(cap_usd) not in (int, float) or not math.isfinite(cap_usd) or not 0 < cap_usd <= 3.00:
            raise ValueError("The evaluation cap must stay within the approved comparison ceiling.")
        if type(max_requests) is not int or not 1 <= max_requests <= 180:
            raise ValueError("The evaluation request limit must be bounded.")
        self.shared, self.check_session, self.lock = shared, check_session, lock
        self.reserved, self.count = 0.0, 0
        self.cap_usd, self.max_requests = cap_usd, max_requests

    def reserve(self, config, amount):
        with self.lock:
            self.check_session()
            if type(amount) not in (int, float) or not math.isfinite(amount) or amount <= 0:
                raise ProviderError("Invalid comparison reservation.", code="budget_reservation_invalid")
            if self.count >= self.max_requests:
                raise ProviderError("The comparison reached its request ceiling. No further request was sent.", code="request_limit")
            if self.reserved + amount > self.cap_usd:
                raise ProviderError("The comparison reached its reservation ceiling. No further request was sent.", code="batch_budget_exhausted")
            self.shared.reserve(config, amount)
            self.reserved += amount
            self.count += 1


class WorkspaceEvaluation:
    def __init__(self, ai):
        self.ai = ai
        with ai._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS model_comparisons (
                comparison_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                state TEXT NOT NULL, owner TEXT NOT NULL, record TEXT NOT NULL, digest TEXT NOT NULL)""")
            for row in db.execute("SELECT * FROM model_comparisons WHERE state IN ('queued','running')").fetchall():
                record = self._read(row)
                record.update(state="interrupted", completed_at=_now(),
                              error="The server restarted. Partial comparison evidence is preserved; no automatic retry was made.")
                self._write(db, record)

    @staticmethod
    def _read(row):
        record = json.loads(row["record"])
        if (_digest(record) != row["digest"] or record.get("comparison_id") != row["comparison_id"]
                or record.get("state") != row["state"]):
            raise WorkspaceError("A saved comparison record is inconsistent.")
        return record

    @staticmethod
    def _write(db, record):
        db.execute("UPDATE model_comparisons SET state=?,record=?,digest=? WHERE comparison_id=?",
                   (record["state"], _encode(record), _digest(record), record["comparison_id"]))

    def _save(self, record):
        with self.ai._db() as db:
            row = db.execute("SELECT owner,state FROM model_comparisons WHERE comparison_id=?",
                             (record["comparison_id"],)).fetchone()
            if row and row["owner"] == self.ai.owner and row["state"] in {"queued", "running"}:
                self._write(db, record)

    def get(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise WorkspaceError("Invalid comparison ID.")
        with self.ai._db() as db:
            row = db.execute("SELECT * FROM model_comparisons WHERE comparison_id=?", (identity,)).fetchone()
            if not row:
                raise WorkspaceError("Comparison not found.")
            return self._read(row)

    def status(self):
        with self.ai._db() as db:
            row = db.execute("SELECT * FROM model_comparisons ORDER BY created_at DESC LIMIT 1").fetchone()
            latest = self._read(row) if row else None
        active_model = self.ai.status().get("model")
        active_candidate = next((c for c in CANDIDATES if c["model"] == active_model), None)
        actual_total = len(latest.get("plan", {}).get("cases", [])) * len(latest.get("plan", {}).get("candidates", [])) if latest else 18
        return {"stage": ("running" if latest and latest["state"] in {"queued", "running"} else
                          "evaluated" if latest and latest.get("report") else "comparison_pending"),
                "active_model": {"name": active_candidate["label"] if active_candidate else "Nano", "id": active_model}, "case_count": 6,
                "candidates": [{"name": c["label"], "id": c["model"], "enabled": c["model"] == active_model or c["id"] == "nano",
                                "reason": "Selected after a qualifying comparison and manual review." if c["model"] == active_model and c["id"] != "nano" else "Existing baseline." if c["id"] == "nano" else
                                "Requires a complete live comparison and manually reviewed benefit before activation."}
                               for c in CANDIDATES],
                "live_evaluation_pending": not bool(latest and latest.get("report")),
                "note": "Six constructed cases screen this bounded workflow; they do not establish general model superiority. The active project model is chosen through explicit review; no automatic model switch.",
                "batch_cap_usd": BATCH_CAP_USD, "max_request_reservations": BATCH_REQUESTS,
                "latest_comparison": None if not latest else {
                    "comparison_id": latest["comparison_id"], "state": latest["state"],
                    "policy_version": latest.get("plan", {}).get("schema"),
                    "model_decision": latest.get("model_decision"),
                    "batch_cap_usd": latest.get("batch_cap_usd"),
                    "max_request_reservations": latest.get("max_request_reservations"),
                    "per_case_caps": [{"name": c["label"], "cap_usd": c.get("per_case_cap_usd", .10)}
                                      for c in latest.get("plan", {}).get("candidates", [])],
                    "completed_cases": sum(r["state"] == "completed" for r in latest.get("rows", [])),
                    "total_cases": actual_total, "attempted_cases": sum(r["state"] != "not_run" for r in latest.get("rows", [])),
                    "reserved_usd": latest.get("reserved_usd", 0), "error": latest.get("error"),
                    "candidate_results": [{"name": c["label"],
                        "completed": sum(r["state"] == "completed" for r in latest.get("rows", []) if r["candidate_id"] == c["id"]),
                        "workflow_passes": sum(bool((r.get("score") or {}).get("workflow_gate_pass")) for r in latest.get("rows", []) if r["candidate_id"] == c["id"]),
                        "total": 6} for c in CANDIDATES]}}

    def start(self, *, allowance_usd, allow_spend):
        if allow_spend is not True or type(allowance_usd) not in (int, float) or allowance_usd != BATCH_CAP_USD:
            raise WorkspaceError("Explicitly authorize the fixed USD 1.50 comparison ceiling inside the existing allowance.")
        identity = uuid4().hex
        # Complete all deterministic preparation before obtaining the private session.
        plan = build_evaluation_plan(temporary_root=self.ai.local / "evaluation-work")
        preflight = comparison_preflight(plan, self.ai._config())
        if not preflight["fits"]:
            raise ConflictError("The offline forecast exceeds this comparison's ceilings. No request was sent.")
        if self.ai._budget(self.ai._config())["remaining_usd"] < BATCH_CAP_USD:
            raise ConflictError("The cumulative allowance has insufficient room for this batch ceiling. No request was sent.")
        config, key, epoch = self.ai.begin_comparison(identity)
        try:
            record = {"schema": "sixd.workspace-comparison.v1", "comparison_id": identity,
                      "state": "queued", "created_at": _now(), "completed_at": None,
                      "batch_cap_usd": BATCH_CAP_USD, "max_request_reservations": BATCH_REQUESTS,
                      "cumulative_allowance_usd": config.spend_cap_usd, "plan": plan,
                      "agent_sources": self.ai._runtime, "rows": [], "report": None, "error": None,
                      "reserved_usd": 0.0, "request_reservations": 0,
                      "budget_before": self.ai._budget(config), "provider_mode": self.ai._provider_mode}
            record["capacity_preflight"] = preflight
            with self.ai._db() as db:
                db.execute("INSERT INTO model_comparisons VALUES (?,?,?,?,?,?)",
                           (identity, record["created_at"], "queued", self.ai.owner, _encode(record), _digest(record)))
            threading.Thread(target=self._run, args=(deepcopy(record), config, key, epoch), daemon=True).start()
            return {"comparison_id": identity, "state": "queued", "batch_cap_usd": BATCH_CAP_USD}
        except Exception:
            self.ai.finish_comparison(identity)
            raise

    def _run(self, record, config, key, epoch):
        identity = record["comparison_id"]
        def check():
            self.ai.check_comparison_session(identity, epoch)
            with self.ai._db() as db:
                row = db.execute("SELECT owner,state FROM model_comparisons WHERE comparison_id=?", (identity,)).fetchone()
                if not row or row["owner"] != self.ai.owner or row["state"] not in {"queued", "running"}:
                    raise ProviderError("The comparison was interrupted. No further request was sent.")
        batch = BatchBudget(BudgetLedger(self.ai.local / "budget.sqlite3"), check, self.ai._lock)
        try:
            record["state"] = "running"
            self._save(record)

            def factory(candidate, case):
                check()
                settings = candidate["settings"]
                candidate_config = replace(config, model=candidate["model"],
                    input_usd_per_million_ceiling=candidate["input_usd_per_million"],
                    output_usd_per_million_ceiling=candidate["output_usd_per_million"],
                    max_output_tokens=settings["max_output_tokens"],
                    inference_profile=settings["inference_profile"], selection_protocol=settings["selection_protocol"])
                budget = JobBudget(batch, check_session=check, request_lock=self.ai._lock,
                                   max_reservation_usd=candidate["per_case_cap_usd"])
                return self.ai._factory(candidate_config, budget, key)

            def progress(row):
                record["rows"].append(row)
                record.update(reserved_usd=batch.reserved, request_reservations=batch.count)
                self._save(record)
                check()
                return batch.count < BATCH_REQUESTS and batch.reserved < BATCH_CAP_USD

            report = run_comparison(record["plan"], factory, quality_evaluator=evaluate_explanation,
                                    mode="live" if self.ai._provider_mode == "live_token_factory" else "offline", on_case=progress)
            check()
            record.update(report=report, rows=report["rows"], state="completed", completed_at=_now())
        except Exception:
            # Provider/credential exception text must never reach an API or receipt.
            record.update(state="failed", completed_at=_now(),
                          error="The comparison stopped. Saved partial results are retained; no retry or model fallback was made.")
        finally:
            record.update(reserved_usd=batch.reserved, request_reservations=batch.count)
            try:
                self._save(record)
            finally:
                self.ai.finish_comparison(identity)
