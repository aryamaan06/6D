"""Explicit capped live workflow evaluation, separate from historical model selection.

Only start() can acquire a private session and initiate paid work. Reads return
no credential and preserve complete responses and interruption records.
"""
from copy import deepcopy
from dataclasses import replace
import json
import re
import threading
from uuid import uuid4

from .workflow_evaluation import BATCH_CAP_USD, BATCH_REQUESTS, build_plan, run_comparison, scorecard
from .providers import BudgetLedger, ProviderError, TokenFactoryProvider
from .workspace import ConflictError, WorkspaceError
from .workspace_ai import JobBudget, _digest, _encode, _now
from .workspace_evaluation import BatchBudget


def workflow_preflight(plan, config):
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
            "fits": len(cases) == 30 and all(c["fits_case_cap"] for c in cases) and total <= BATCH_CAP_USD
                    and all(row["state"] == "completed" for row in report["rows"]),
            "note": "Synthetic action-path capacity forecast with 15% headroom. Actual paths and reservations can differ; enforced caps still apply."}


class WorkflowEvaluation:
    TABLE = "workflow_evaluations"

    def __init__(self, ai):
        self.ai = ai
        with ai._db() as db:
            db.execute(f"""CREATE TABLE IF NOT EXISTS {self.TABLE} (
                comparison_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                state TEXT NOT NULL, owner TEXT NOT NULL, record TEXT NOT NULL, digest TEXT NOT NULL)""")
            for row in db.execute(f"SELECT * FROM {self.TABLE} WHERE state IN ('queued','running')").fetchall():
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

    @classmethod
    def _write(cls, db, record):
        db.execute(f"UPDATE {cls.TABLE} SET state=?,record=?,digest=? WHERE comparison_id=?",
                   (record["state"], _encode(record), _digest(record), record["comparison_id"]))

    def _save(self, record):
        with self.ai._db() as db:
            row = db.execute(f"SELECT owner,state FROM {self.TABLE} WHERE comparison_id=?",
                             (record["comparison_id"],)).fetchone()
            if row and row["owner"] == self.ai.owner and row["state"] in {"queued", "running"}:
                self._write(db, record)

    def get(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise WorkspaceError("Invalid comparison ID.")
        with self.ai._db() as db:
            row = db.execute(f"SELECT * FROM {self.TABLE} WHERE comparison_id=?", (identity,)).fetchone()
            if not row:
                raise WorkspaceError("Comparison not found.")
            return self._read(row)

    def status(self):
        with self.ai._db() as db:
            row = db.execute("SELECT * FROM workflow_evaluations ORDER BY created_at DESC LIMIT 1").fetchone()
        latest = self._read(row) if row else None
        return {"schema": "sixd.workflow-evaluation-status.v1", "batch_cap_usd": BATCH_CAP_USD,
                "max_request_reservations": BATCH_REQUESTS, "planned_tasks": 30,
                "automatic_model_selection": False, "connection": self.ai.status(),
                "latest": {key: latest.get(key) for key in ("comparison_id", "state", "created_at", "completed_at", "reserved_usd", "request_reservations", "error")} if latest else None,
                "scorecard": scorecard(latest["report"]) if latest and latest.get("report") else None}

    def start(self, *, allowance_usd, allow_spend):
        if allow_spend is not True or type(allowance_usd) not in (int, float) or allowance_usd != BATCH_CAP_USD:
            raise WorkspaceError("Explicitly authorize the fixed USD 3.00 workflow-evaluation ceiling inside the existing allowance.")
        identity = uuid4().hex
        # Complete all deterministic preparation before obtaining the private session.
        plan = build_plan(temporary_root=self.ai.local / "evaluation-work")
        preflight = workflow_preflight(plan, self.ai._config())
        if not preflight["fits"]:
            raise ConflictError("The offline forecast exceeds this comparison's ceilings. No request was sent.")
        if self.ai._budget(self.ai._config())["remaining_usd"] < BATCH_CAP_USD:
            raise ConflictError("The cumulative allowance has insufficient room for this batch ceiling. No request was sent.")
        config, key, epoch = self.ai.begin_comparison(identity)
        try:
            record = {"schema": "sixd.workspace-workflow-evaluation.v1", "comparison_id": identity,
                      "state": "queued", "created_at": _now(), "completed_at": None,
                      "batch_cap_usd": BATCH_CAP_USD, "max_request_reservations": BATCH_REQUESTS,
                      "cumulative_allowance_usd": config.spend_cap_usd, "plan": plan,
                      "agent_sources": self.ai._runtime, "rows": [], "report": None, "error": None,
                      "reserved_usd": 0.0, "request_reservations": 0,
                      "budget_before": self.ai._budget(config), "provider_mode": self.ai._provider_mode}
            record["capacity_preflight"] = preflight
            with self.ai._db() as db:
                db.execute("INSERT INTO workflow_evaluations VALUES (?,?,?,?,?,?)",
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
                row = db.execute("SELECT owner,state FROM workflow_evaluations WHERE comparison_id=?", (identity,)).fetchone()
                if not row or row["owner"] != self.ai.owner or row["state"] not in {"queued", "running"}:
                    raise ProviderError("The comparison was interrupted. No further request was sent.")
        batch = BatchBudget(BudgetLedger(self.ai.local / "budget.sqlite3"), check, self.ai._lock, cap_usd=BATCH_CAP_USD, max_requests=BATCH_REQUESTS)
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

            report = run_comparison(record["plan"], factory, 
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


class UltraDiagnostic(WorkflowEvaluation):
    """One explicit compatibility case; never replaces comparison/selection proof."""
    TABLE = "ultra_diagnostics"
    CAP_USD = .50

    def status(self):
        with self.ai._db() as db:
            row = db.execute("SELECT * FROM ultra_diagnostics ORDER BY created_at DESC LIMIT 1").fetchone()
        record = self._read(row) if row else None
        latest = None
        if record:
            receipt = record.get("receipt") or {}
            latest = {key: record.get(key) for key in ("comparison_id", "state", "created_at", "completed_at", "reserved_usd", "request_reservations")}
            latest.update(error_code=receipt.get("error_code"), error=receipt.get("error") or record.get("error"),
                          diagnostic=receipt.get("provider_diagnostic"), model=record["model"])
        return {"schema": "sixd.ultra-diagnostic-status.v1", "cap_usd": self.CAP_USD,
                "max_requests": 6, "latest": latest, "automatic_model_selection": False}

    def start(self, *, allowance_usd, allow_spend):
        if allow_spend is not True or type(allowance_usd) not in (int, float) or allowance_usd != self.CAP_USD:
            raise WorkspaceError("Explicitly authorize the fixed USD .50 single-case Ultra diagnostic ceiling.")
        from .model_evaluation import CANDIDATES
        from .project_investigation import SUMMARY_MAX_CHARACTERS
        candidate = next(c for c in CANDIDATES if c["id"] == "ultra")
        case = build_plan(temporary_root=self.ai.local / "evaluation-work")["cases"][0]
        assert case["id"] == "orbit-met"
        if self.ai._budget(self.ai._config())["remaining_usd"] < self.CAP_USD:
            raise ConflictError("Insufficient cumulative reservation capacity. No request was sent.")
        identity = uuid4().hex
        config, key, epoch = self.ai.begin_comparison(identity)
        try:
            config = replace(config, model=candidate["model"],
                             input_usd_per_million_ceiling=candidate["input_usd_per_million"],
                             output_usd_per_million_ceiling=candidate["output_usd_per_million"])
            record = {"schema": "sixd.ultra-diagnostic.v1", "comparison_id": identity,
                      "state": "queued", "created_at": _now(), "completed_at": None,
                      "model": config.model, "case": case, "cap_usd": self.CAP_USD,
                      "case_cap_usd": candidate["per_case_cap_usd"], "max_requests": 6,
                      "settings": {"inference_profile": config.inference_profile,
                                   "selection_protocol": config.selection_protocol,
                                   "max_output_tokens": config.max_output_tokens,
                                   "summary_max_characters": SUMMARY_MAX_CHARACTERS},
                      "agent_sources": self.ai._runtime,
                      "provider_mode": self.ai._provider_mode, "receipt": None, "activity": [],
                      "reserved_usd": 0.0, "request_reservations": 0, "error": None,
                      "budget_before": self.ai._budget(config),
                      "purpose": "Fresh compatibility check of the original constructed case. The exact cause of the unretained historical response remains unknown.",
                      "active_model_changed": False}
            with self.ai._db() as db:
                db.execute("INSERT INTO ultra_diagnostics VALUES (?,?,?,?,?,?)",
                           (identity, record["created_at"], "queued", self.ai.owner, _encode(record), _digest(record)))
            threading.Thread(target=self._run, args=(deepcopy(record), config, key, epoch), daemon=True).start()
            return {"comparison_id": identity, "state": "queued", "cap_usd": self.CAP_USD}
        except Exception:
            self.ai.finish_comparison(identity)
            raise

    def _run(self, record, config, key, epoch):
        from .project_investigation import investigate_project
        identity = record["comparison_id"]
        def check():
            self.ai.check_comparison_session(identity, epoch)
            with self.ai._db() as db:
                row = db.execute("SELECT owner,state FROM ultra_diagnostics WHERE comparison_id=?", (identity,)).fetchone()
            if not row or row["owner"] != self.ai.owner or row["state"] not in {"queued", "running"}:
                raise ProviderError("Diagnostic interrupted; no automatic retry.")
        batch = BatchBudget(BudgetLedger(self.ai.local / "budget.sqlite3"), check, self.ai._lock,
                            cap_usd=self.CAP_USD, max_requests=6)
        try:
            record["state"] = "running"; self._save(record)
            job = JobBudget(batch, check_session=check, request_lock=self.ai._lock,
                            max_reservation_usd=record["case_cap_usd"])
            def progress(event):
                record["activity"].append(deepcopy(event))
                record.update(reserved_usd=batch.reserved, request_reservations=batch.count)
                self._save(record)
                check()
            case = record["case"]
            receipt = investigate_project(case["view"], case["requirement_id"], case["question"],
                self.ai._factory(config, job, key), investigation_id=identity, on_event=progress)
            check()
            record.update(receipt=receipt, state=receipt["state"], completed_at=_now())
        except Exception:
            record.update(state="failed", completed_at=_now(), error="Diagnostic stopped; partial evidence retained, no retry or fallback.")
        finally:
            record.update(reserved_usd=batch.reserved, request_reservations=batch.count)
            try:
                self._save(record)
            finally:
                self.ai.finish_comparison(identity)
