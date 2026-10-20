"""Explicit bounded evidence-link comparisons using the shared private session.

Preparation and reads make no inference calls. Only start() can acquire the
private key/session and run a fixed batch; there is no retry or model activation.
"""
from copy import deepcopy
from dataclasses import replace
import json
import threading
from uuid import uuid4

from .evidence_evaluation import (BATCH_CAP_USD, BATCH_REQUESTS, EXPLANATION_POLICY,
    build_plan, run_comparison, scorecard)
from .providers import BudgetLedger, ProviderError, TokenFactoryProvider
from .workspace import ConflictError, WorkspaceError
from .workspace_ai import JobBudget, _digest, _encode, _now
from .workspace_evaluation import BatchBudget
from .workspace_workflow_evaluation import WorkflowEvaluation


def comparison_preflight(plan, config):
    """Forecast all nine bounded action paths offline with output/headroom costs."""
    from .project_investigation import ProjectActionAdapter
    forecasts = []

    class ForecastBudget:
        def __init__(self):
            self.count, self.reserved = 0, 0.0

        def reserve(self, config, amount):
            self.count += 1
            self.reserved += amount

    def factory(candidate, case):
        ledger = ForecastBudget()
        forecasts.append((candidate, case["id"], ledger))
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
            arguments = {"action": action, "evidence_ids": menu["recorded_evidence_ids"] if action == "finish" else [],
                "summary": "Review the recorded canonical finding, supplied inputs and bounded model assumptions. Missing evidence remains unresolved; obtain the applicable independent analysis before extending this result." if action == "finish" else ""}
            return {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "offline-capacity-" + action, "type": "function", "function": {
                    "name": "select_next_action", "arguments": json.dumps(arguments)}}]}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

        return TokenFactoryProvider(candidate_config, ledger, api_key="synthetic-evidence-capacity-key-only",
            transport=transport, action_adapter=ProjectActionAdapter())

    report = run_comparison(plan, factory, mode="offline")
    rows = [{"candidate_id": candidate["id"], "case_id": identity,
        "requests": ledger.count, "forecast_reservation_usd": ledger.reserved,
        "with_headroom_usd": ledger.reserved * 1.15, "case_cap_usd": candidate["per_case_cap_usd"],
        "fits_case_cap": ledger.reserved * 1.15 <= candidate["per_case_cap_usd"] and ledger.count <= 6}
        for candidate, identity, ledger in forecasts]
    total = sum(row["with_headroom_usd"] for row in rows)
    requests = sum(row["requests"] for row in rows)
    return {"schema": "sixd.evidence-capacity.v1", "mode": "offline_forecast", "live_calls": 0,
        "plan_digest": plan["plan_digest"], "explanation_policy": EXPLANATION_POLICY, "cases": rows,
        "forecast_with_headroom_usd": total, "batch_cap_usd": BATCH_CAP_USD,
        "request_reservations": requests, "max_request_reservations": BATCH_REQUESTS,
        "fits": len(rows) == 9 and all(row["fits_case_cap"] for row in rows)
            and requests <= BATCH_REQUESTS and total <= BATCH_CAP_USD
            and all(row["state"] == "completed" for row in report["rows"]),
        "note": "Synthetic capacity forecast includes full output ceilings and fifteen percent headroom. Actual request paths and reservations can differ; enforced limits remain authoritative. This is not model-quality evidence."}


class EvidenceEvaluation(WorkflowEvaluation):
    TABLE = "evidence_evaluations"

    def prepare(self):
        """Build a fresh offline plan and forecast without a key or ledger write."""
        plan = build_plan(temporary_root=self.ai.local / "evaluation-work")
        preflight = comparison_preflight(plan, self.ai._config())
        return {"schema": "sixd.evidence-preparation.v1", "state": "prepared_offline", "live_calls": 0,
            "plan": plan, "capacity_preflight": preflight, "active_model_changed": False}

    def status(self):
        with self.ai._db() as db:
            row = db.execute("SELECT * FROM evidence_evaluations ORDER BY created_at DESC LIMIT 1").fetchone()
        record = self._read(row) if row else None
        return {"schema": "sixd.evidence-evaluation-status.v1", "batch_cap_usd": BATCH_CAP_USD,
            "max_request_reservations": BATCH_REQUESTS, "planned_tasks": 9, "case_count": 3,
            "explanation_policy": EXPLANATION_POLICY, "automatic_model_selection": False,
            "latest": {key: record.get(key) for key in ("comparison_id", "state", "created_at", "completed_at",
                "reserved_usd", "request_reservations", "error")} if record else None,
            "scorecard": scorecard(record["report"]) if record and record.get("report") else None,
            "note": "Three constructed cases per candidate screen the evidence-link workflow. Independent engineering and human review remain pending; active model selection is unchanged."}

    def start(self, *, allowance_usd, allow_spend):
        if allow_spend is not True or type(allowance_usd) not in (int, float) or allowance_usd != BATCH_CAP_USD:
            raise WorkspaceError("Explicitly authorize the fixed USD 2.00 evidence-comparison ceiling inside the existing allowance.")
        prepared = self.prepare()
        if not prepared["capacity_preflight"]["fits"]:
            raise ConflictError("The offline evidence-comparison forecast exceeds its ceilings. No request was sent.")
        if self.ai._budget(self.ai._config())["remaining_usd"] < BATCH_CAP_USD:
            raise ConflictError("The cumulative allowance has insufficient capacity for this batch. No request was sent.")
        identity = uuid4().hex
        config, key, epoch = self.ai.begin_comparison(identity)
        try:
            record = {"schema": "sixd.workspace-evidence-evaluation.v1", "comparison_id": identity,
                "state": "queued", "created_at": _now(), "completed_at": None,
                "batch_cap_usd": BATCH_CAP_USD, "max_request_reservations": BATCH_REQUESTS,
                "cumulative_allowance_usd": config.spend_cap_usd, "plan": prepared["plan"],
                "capacity_preflight": prepared["capacity_preflight"], "agent_sources": self.ai._runtime,
                "explanation_policy": EXPLANATION_POLICY, "active_model_changed": False,
                "rows": [], "report": None, "error": None, "reserved_usd": 0.0, "request_reservations": 0,
                "budget_before": self.ai._budget(config), "provider_mode": self.ai._provider_mode}
            with self.ai._db() as db:
                db.execute("INSERT INTO evidence_evaluations VALUES (?,?,?,?,?,?)",
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
                row = db.execute("SELECT owner,state FROM evidence_evaluations WHERE comparison_id=?", (identity,)).fetchone()
                if not row or row["owner"] != self.ai.owner or row["state"] not in {"queued", "running"}:
                    raise ProviderError("The evidence comparison was interrupted.", code="session_changed")

        batch = BatchBudget(BudgetLedger(self.ai.local / "budget.sqlite3"), check, self.ai._lock,
            cap_usd=BATCH_CAP_USD, max_requests=BATCH_REQUESTS)
        try:
            record["state"] = "running"
            self._save(record)

            def factory(candidate, case):
                check()
                settings = candidate["settings"]
                candidate_config = replace(config, model=candidate["model"],
                    input_usd_per_million_ceiling=candidate["input_usd_per_million"],
                    output_usd_per_million_ceiling=candidate["output_usd_per_million"],
                    max_output_tokens=settings["max_output_tokens"], inference_profile=settings["inference_profile"],
                    selection_protocol=settings["selection_protocol"])
                budget = JobBudget(batch, check_session=check, request_lock=self.ai._lock,
                    max_reservation_usd=candidate["per_case_cap_usd"])
                return self.ai._factory(candidate_config, budget, key)

            def progress(row):
                record["rows"].append(row)
                record.update(reserved_usd=batch.reserved, request_reservations=batch.count)
                self._save(record)
                check()
                return batch.count < BATCH_REQUESTS and batch.reserved < BATCH_CAP_USD

            report = run_comparison(record["plan"], factory,
                mode="live" if self.ai._provider_mode == "live_token_factory" else "offline", on_case=progress)
            check()
            record.update(report=report, rows=report["rows"], state="completed", completed_at=_now())
        except Exception:
            record.update(state="failed", completed_at=_now(),
                error="The evidence comparison stopped. Partial results are preserved; no retry, fallback or model activation followed.")
        finally:
            record.update(reserved_usd=batch.reserved, request_reservations=batch.count)
            try:
                self._save(record)
            finally:
                self.ai.finish_comparison(identity)
