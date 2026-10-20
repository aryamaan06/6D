"""Local jobs, optional current-user encrypted credentials and shared budgets.

The public surface never returns credentials. Project revisions and calculation
receipts are read-only to this service. No call is sent on connect or startup.
"""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
from uuid import uuid4

from .providers import BudgetLedger, LiveConfig, ProviderError, TokenFactoryProvider
from .workspace import ConflictError, WorkspaceError
from .credential_store import CredentialStore, CredentialError, valid_key

MAX_JOB_REQUESTS = 6
MAX_JOB_RESERVATION_USD = .10
MAX_APPROVED_ALLOWANCE_USD = 29.50
ACTIVE = {"queued", "running"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return sha256(_encode(value).encode()).hexdigest()


class JobBudget:
    """Bound one job while reserving against the existing cumulative ledger."""
    def __init__(self, shared, *, check_session, request_lock=None, max_reservation_usd=MAX_JOB_RESERVATION_USD):
        if type(max_reservation_usd) not in (int, float) or not math.isfinite(max_reservation_usd) or not 0 < max_reservation_usd <= .35:
            raise ProviderError("Invalid per-investigation ceiling.", code="configuration_error")
        self.shared = shared
        self.check_session = check_session
        self.request_lock = request_lock
        self.count = 0
        self.reserved = 0.0
        self.max_reservation_usd = max_reservation_usd

    def reserve(self, config, amount):
        with self.request_lock or nullcontext():
            self.check_session()
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0:
                raise ProviderError("Invalid request reservation. No request was sent.", code="budget_reservation_invalid")
            if self.count >= MAX_JOB_REQUESTS:
                raise ProviderError("This investigation reached its request ceiling. No further request was sent.", code="request_limit")
            if self.reserved + amount > self.max_reservation_usd:
                raise ProviderError("This investigation reached its reservation ceiling. No further request was sent.", code="case_budget_exhausted")
            self.shared.reserve(config, amount)
            self.count += 1
            self.reserved += amount


class WorkspaceAI:
    def __init__(self, store, local_directory, *, provider_factory=None, credential_store=None):
        self.store = store
        self.local = Path(local_directory)
        self.owner = uuid4().hex
        self._lock = threading.RLock()
        self._active = None
        self._epoch = 0
        self._credential_store = (credential_store if credential_store is not None else
                                  CredentialStore(self.local / "credentials" / "nebius.dpapi"))
        self._credential_error = None
        self._remembered = False
        environment_key = os.environ.get("NEBIUS_API_KEY") or None
        self._environment_key_configured = bool(environment_key)
        self._key = environment_key if valid_key(environment_key) else None
        self._key_source = "environment" if self._key else None
        if environment_key and self._key is None:
            self._credential_error = "environment_key_invalid"
        try:
            self._remembered = self._credential_store.exists()
            if self._key is None and self._remembered:
                restored = self._credential_store.load()
                if not valid_key(restored):
                    raise CredentialError("credential_data_invalid")
                self._key, self._key_source = restored, "remembered"
        except CredentialError as error:
            self._credential_error = error.code
        self._factory = provider_factory or self._provider
        self._provider_mode = "offline_transport_fixture" if provider_factory is not None else "live_token_factory"
        self._runtime = self._sources()
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS project_investigations (
                investigation_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                revision INTEGER NOT NULL, requirement_id TEXT NOT NULL,
                created_at TEXT NOT NULL, state TEXT NOT NULL,
                owner TEXT NOT NULL, record TEXT NOT NULL, digest TEXT NOT NULL,
                FOREIGN KEY (project_id,revision) REFERENCES revisions(project_id,revision))""")
            # A restarted server preserves partial activity and never retries it.
            for row in db.execute("SELECT * FROM project_investigations WHERE state IN ('queued','running')").fetchall():
                record = self._read(row)
                record.update(state="failed", error="The local server restarted. Partial activity is preserved; no automatic retry was made.", completed_at=_now())
                self._write(db, record)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(str(self.store.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _sources():
        folder = Path(__file__).resolve().parent
        names = ("workspace_ai.py", "credential_store.py", "project_investigation.py", "explanation_quality.py", "evidence_facts.py", "evidence_roles.py", "change_evidence.py", "evidence_evaluation.py", "workspace_evidence_evaluation.py", "test_evidence.py", "workspace_test_data.py", "model_evaluation.py", "workspace_evaluation.py", "workflow_evaluation.py", "workspace_workflow_evaluation.py", "providers.py", "action_selection.py", "workspace.py", "engineering.py", "lifecycle.py", "__init__.py")
        return {name: sha256((folder / name).read_bytes()).hexdigest() for name in names if (folder / name).is_file()}

    def _config(self):
        config = LiveConfig.load(self.local / "token-factory.json")
        if config.spend_cap_usd > MAX_APPROVED_ALLOWANCE_USD:
            raise ProviderError("The configured allowance exceeds the approved cumulative USD 29.50 cap.", code="configuration_error")
        if config.inference_profile != "native_no_thinking" or config.selection_protocol != "forced_action_v1":
            raise ProviderError("The project assistant requires the established native tool-selection configuration.")
        selection = self.local / "project-assistant-model.json"
        if selection.exists():
            try:
                from .model_evaluation import CANDIDATES, candidate_selection_gate
                choice = json.loads(selection.read_text(encoding="utf-8"))
                if (not isinstance(choice, dict) or set(choice) != {"comparison_id", "candidate_id"}
                        or not isinstance(choice["comparison_id"], str)
                        or not re.fullmatch(r"[a-f0-9]{32}", choice["comparison_id"])):
                    raise ValueError
                candidate = next(c for c in CANDIDATES if c["id"] == choice["candidate_id"] and c["id"] != "nano")
                with self._db() as db:
                    row = db.execute("SELECT * FROM model_comparisons WHERE comparison_id=?", (choice["comparison_id"],)).fetchone()
                    if not row:
                        raise ValueError
                    record = json.loads(row["record"])
                    if (not isinstance(record, dict) or _digest(record) != row["digest"]
                            or row["state"] != "completed" or record.get("state") != "completed"
                            or record.get("comparison_id") != choice["comparison_id"]
                            or not isinstance(record.get("report"), dict)
                            or not isinstance(record.get("model_reviews"), dict)):
                        raise ValueError
                gate = candidate_selection_gate(record["report"], candidate["id"], plan=record["plan"],
                    manual_review=record.get("model_reviews", {}).get(candidate["id"]))
                if not gate["eligible"]:
                    raise ValueError
                config = replace(config, model=candidate["model"],
                    input_usd_per_million_ceiling=candidate["input_usd_per_million"],
                    output_usd_per_million_ceiling=candidate["output_usd_per_million"])
            except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, StopIteration, AttributeError):
                raise ProviderError("The selected project model has no intact qualifying comparison and manual review. Review the saved selection; no fallback was made.", code="configuration_error") from None
        return config

    @staticmethod
    def _job_ceiling(config):
        from .model_evaluation import CANDIDATES
        return next((c["per_case_cap_usd"] for c in CANDIDATES if c["model"] == config.model), MAX_JOB_RESERVATION_USD)

    def _budget(self, config):
        path = self.local / "budget.sqlite3"
        reserved = 0.0
        if path.exists():
            # Read-only status cannot create a budget approval or reset usage.
            db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
            try:
                exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='budget'").fetchone()
                rows = db.execute("SELECT id,cap,reserved FROM budget").fetchall() if exists else []
                if rows:
                    if (len(rows) != 1 or rows[0][0] != config.approval_id or rows[0][1] != config.spend_cap_usd
                            or isinstance(rows[0][2], bool) or not isinstance(rows[0][2], (int, float))
                            or not math.isfinite(rows[0][2]) or not 0 <= rows[0][2] <= config.spend_cap_usd):
                        raise ProviderError("The existing budget record needs operator review; it has not been changed.")
                    reserved = rows[0][2]
            finally:
                db.close()
        return {"cap_usd": config.spend_cap_usd, "reserved_usd": reserved,
                "remaining_usd": max(0.0, config.spend_cap_usd - reserved),
                "accounting": "Conservative reservations, not provider billed usage."}

    @staticmethod
    def _provider(config, ledger, key):
        from .project_investigation import ProjectActionAdapter
        return TokenFactoryProvider(config, ledger, api_key=key, action_adapter=ProjectActionAdapter())

    @staticmethod
    def _settings(config):
        return {name: getattr(config, name) for name in (
            "base_url", "model", "inference_profile", "selection_protocol", "max_output_tokens",
            "request_timeout_seconds", "input_usd_per_million_ceiling", "output_usd_per_million_ceiling")}

    def status(self):
        with self._lock:
            present = bool(self._key)
            credential_status = {"remember_supported": self._credential_store.supported,
                "key_remembered": self._remembered, "key_source": self._key_source,
                "credential_error": self._credential_error,
                "environment_key_configured": self._environment_key_configured}
        value = {"configured": False, "key_present": present, "model": None,
                 "provider_mode": self._provider_mode, "max_job_requests": MAX_JOB_REQUESTS,
                 "max_job_reservation_usd": MAX_JOB_RESERVATION_USD,
                 "live_validated": False, "budget": None, **credential_status}
        try:
            config = self._config()
            value.update(model=config.model, budget=self._budget(config), configured=present,
                         max_job_reservation_usd=self._job_ceiling(config))
            with self._db() as db:
                records = [self._read(row) for row in db.execute("SELECT * FROM project_investigations WHERE state='completed' ORDER BY created_at DESC LIMIT 100")]
            value["live_validated"] = any(record.get("provider_mode") == "live_token_factory"
                and record.get("live_model_calls", 0) > 0 and record.get("agent_sources") == self._runtime
                and record.get("model") == config.model and record.get("provider_settings") == self._settings(config)
                for record in records)
            if self._key_source == "remembered":
                value["note"] = "Connected with a key remembered in Windows-encrypted local storage. No inference call is made until you start an investigation."
            elif self._key_source == "environment":
                value["note"] = "Connected using the process environment. Remove NEBIUS_API_KEY from the launch environment to prevent restoration after a restart. No inference call was made."
            else:
                value["note"] = ("Connected for this session. No inference call is made until you start an investigation."
                                 if present else "Connect a Nebius key privately to enable live investigations.")
        except (ProviderError, sqlite3.Error, OSError):
            value["note"] = "The local provider configuration or budget is unavailable. Saved project work is preserved."
        return value

    def connect(self, key, remember=False):
        if not valid_key(key):
            raise WorkspaceError("Enter a valid private API key. The value is never returned.")
        if type(remember) is not bool:
            raise WorkspaceError("Remember on this device must be true or false.")
        self._config()
        with self._lock:
            if self._active:
                raise ConflictError("Wait for the active investigation before changing its connection.")
            try:
                if remember:
                    self._credential_store.save(key)
                else:
                    self._credential_store.forget()
            except CredentialError as error:
                self._credential_error = error.code
                raise WorkspaceError("The private connection was not changed because local credential storage could not be updated. Use the storage status to review it.") from None
            self._key = key
            self._key_source = "remembered" if remember else "session"
            self._remembered = remember
            self._credential_error = None
            self._epoch += 1
        return self.status()

    def disconnect(self):
        with self._lock:
            self._key = None
            self._key_source = None
            self._epoch += 1
            try:
                self._credential_store.forget()
            except CredentialError as error:
                self._credential_error = error.code
                raise WorkspaceError("Disconnected for this session, but the remembered copy could not be removed. Review local credential storage before restarting.") from None
            self._remembered = False
            self._credential_error = None
        return self.status()

    def forget_key(self):
        """Delete the remembered copy while leaving a current session connected."""
        with self._lock:
            if self._active:
                raise ConflictError("Wait for the active investigation before changing its remembered connection.")
            try:
                self._credential_store.forget()
            except CredentialError as error:
                self._credential_error = error.code
                raise WorkspaceError("The remembered copy could not be removed. The current private connection was not changed.") from None
            self._remembered = False
            self._credential_error = None
            if self._key_source == "remembered":
                self._key_source = "session"
        return self.status()

    def begin_comparison(self, identity):
        """Private host helper; never return this tuple through an HTTP route."""
        if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise WorkspaceError("Invalid comparison ID.")
        with self._lock:
            if self._active:
                raise ConflictError("An investigation or comparison is already running.")
            if not self._key:
                raise ConflictError("Connect Nebius privately before starting the comparison. No request was sent.")
            if self._sources() != self._runtime:
                raise ConflictError("Application sources changed. Restart 6D before a comparison.")
            config = self._config()
            if self._budget(config)["remaining_usd"] <= 0:
                raise ConflictError("The approved cumulative allowance is exhausted.")
            self._active = identity
            self._comparison = (identity, config)
            return config, self._key, self._epoch

    def check_comparison_session(self, identity, epoch):
        with self._lock:
            if (not self._key or epoch != self._epoch or self._active != identity
                    or getattr(self, "_comparison", (None,))[0] != identity):
                raise ProviderError("The private comparison session changed. No further request was sent.", code="session_changed")
            if self._sources() != self._runtime or self._config() != self._comparison[1]:
                raise ProviderError("Application sources or provider settings changed. No further request was sent.", code="session_changed")

    def finish_comparison(self, identity):
        with self._lock:
            if getattr(self, "_comparison", (None,))[0] == identity:
                self._comparison = (None,)
                if self._active == identity:
                    self._active = None

    def _projection(self, record, db):
        """Annotate a response from the exact historical review, never rewrite it."""
        from .evidence_facts import build_fact_catalog
        record = deepcopy(record)
        if "evidence_facts" in record:
            record["evidence_facts_origin"] = "recorded"
        elif record.get("evidence") and record.get("canonical_finding"):
            try:
                record["evidence_facts"] = build_fact_catalog(record)
                record["evidence_facts_origin"] = "current_app_read_only_projection"
            except (KeyError, TypeError, ValueError, OverflowError):
                record["evidence_facts_unavailable"] = "The exact captured scope is unavailable; current evidence was not substituted."
        if record.get("state") != "completed":
            return record
        from .explanation_quality import build_guidance, evaluate_explanation
        record = deepcopy(record)
        if "guidance" in record:
            record["guidance_origin"] = "recorded"
        else:
            for row in db.execute("SELECT * FROM runs WHERE project_id=? AND revision=? ORDER BY sequence DESC",
                                  (record["project_id"], record["revision"])).fetchall():
                receipt = self.store._receipt(row)
                review = receipt["review"]
                if review["digest"] == record.get("review_digest"):
                    record["guidance"] = build_guidance(review["project"], review, record["requirement_id"],
                                                         list(record.get("evidence", {})))
                    record["guidance_origin"] = "current_app_read_only_projection"
                    break
            if "guidance" not in record:
                record["guidance_unavailable"] = "The exact captured review is unavailable; current evidence was not substituted."
        if "explanation_quality" not in record:
            record["explanation_quality"] = evaluate_explanation(record)
        return record

    @staticmethod
    def _read(row):
        record = json.loads(row["record"])
        if (_digest(record) != row["digest"] or record.get("investigation_id") != row["investigation_id"]
                or record.get("project_id") != row["project_id"] or record.get("revision") != row["revision"]
                or record.get("requirement_id") != row["requirement_id"] or record.get("state") != row["state"]):
            raise WorkspaceError("A saved investigation record is inconsistent.")
        return record

    def _write(self, db, record):
        db.execute("UPDATE project_investigations SET state=?,record=?,digest=? WHERE investigation_id=?",
                   (record["state"], _encode(record), _digest(record), record["investigation_id"]))

    def get(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise WorkspaceError("Invalid investigation ID.")
        with self._db() as db:
            row = db.execute("SELECT * FROM project_investigations WHERE investigation_id=?", (identity,)).fetchone()
            if not row:
                raise WorkspaceError("Investigation not found.")
            return self._projection(self._read(row), db)

    def list(self, project_id, revision, requirement_id=None):
        # Check identity/revision even when no investigation exists.
        self.store.get(project_id, revision)
        with self._db() as db:
            query = "SELECT * FROM project_investigations WHERE project_id=? AND revision=?"
            values = [project_id, revision]
            if requirement_id is not None:
                query += " AND requirement_id=?"
                values.append(requirement_id)
            rows = db.execute(query + " ORDER BY created_at DESC LIMIT 50", values).fetchall()
            return [self._projection(self._read(row), db) for row in rows]

    def start(self, project_id, revision, requirement_id, question, *, test_comparison_id=None, test_row_number=None):
        if not isinstance(requirement_id, str) or not requirement_id:
            raise WorkspaceError("Select a requirement for the investigation.")
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
            raise WorkspaceError("Enter an investigation question of 1–2000 characters.")
        view = self.store.get(project_id, revision)
        if not view["run"]:
            raise ConflictError("Run checks for the selected saved revision before starting an investigation.")
        if not any(item["id"] == requirement_id for item in view["project"]["requirements"]):
            raise WorkspaceError("The requirement is not in the selected saved revision.")
        if (test_comparison_id is None) != (test_row_number is None):
            raise WorkspaceError("Select both a saved test comparison and its row number.")
        if test_comparison_id is not None:
            # Wire callers supply identities only. Never accept a client-built
            # evidence bundle or substitute current rows into an older job.
            from .test_evidence import TestEvidence
            from .workspace_test_data import WorkspaceTestData
            view["test_evidence"] = TestEvidence(self.store, WorkspaceTestData(self.store)).investigation_context(
                project_id, revision, requirement_id, test_comparison_id, test_row_number)
        from .project_investigation import validate_investigation_view
        validate_investigation_view(view, requirement_id)
        config = self._config()
        if self._budget(config)["remaining_usd"] <= 0:
            raise ConflictError("The approved cumulative allowance is exhausted. No request was sent.")
        with self._lock:
            if self._active:
                raise ConflictError("An investigation is already running. No duplicate job was started.")
            if not self._key:
                raise ConflictError("Connect Nebius privately before starting an investigation. No request was sent.")
            if self._key in question:
                raise WorkspaceError("Remove private credential material from the question before saving or sending it.")
            if self._sources() != self._runtime:
                raise ConflictError("Application sources changed. Restart 6D before an investigation.")
            identity = uuid4().hex
            record = {"schema": "sixd.project-investigation.v1", "investigation_id": identity,
                      "project_id": project_id, "revision": revision,
                      "review_digest": view["run"]["review"]["digest"],
                      "requirement_id": requirement_id, "question": question.strip(),
                      "state": "queued", "model": config.model, "provider_mode": self._provider_mode,
                      "started_at": _now(), "completed_at": None, "events": [], "evidence": {},
                      "summary": "", "citations": [], "live_model_calls": 0, "request_attempts": 0,
                      "error": None, "agent_sources": self._runtime, "provider_settings": self._settings(config)}
            if "test_evidence" in view:
                record["test_evidence"] = deepcopy(view["test_evidence"])
            with self._db() as db:
                db.execute("INSERT INTO project_investigations VALUES (?,?,?,?,?,?,?,?,?)",
                           (identity, project_id, revision, requirement_id, record["started_at"],
                            "queued", self.owner, _encode(record), _digest(record)))
            self._active = identity
            epoch, key = self._epoch, self._key
            worker = threading.Thread(target=self._run, args=(record, deepcopy(view), config, key, epoch), daemon=True)
            worker.start()
            # The public queued projection must not share mutable context with
            # a worker that may not have started copying its inputs yet.
            return deepcopy(record)

    def _check_session(self, identity, epoch):
        with self._lock:
            if not self._key or self._epoch != epoch:
                raise ProviderError("The private connection changed. No further request was sent.", code="session_changed")
            if self._sources() != self._runtime:
                raise ProviderError("Application sources changed. Restart 6D before further requests.", code="session_changed")
        with self._db() as db:
            row = db.execute("SELECT owner,state FROM project_investigations WHERE investigation_id=?", (identity,)).fetchone()
            if not row or row["owner"] != self.owner or row["state"] not in ACTIVE:
                raise ProviderError("The local job was interrupted. No further request was sent.", code="session_changed")

    def _save_owned(self, record):
        with self._db() as db:
            row = db.execute("SELECT owner,state FROM project_investigations WHERE investigation_id=?", (record["investigation_id"],)).fetchone()
            if row and row["owner"] == self.owner and row["state"] in ACTIVE:
                self._write(db, record)

    def _run(self, queued, view, config, key, epoch):
        from .project_investigation import investigate_project, _failure
        record = deepcopy(queued)
        record["state"] = "running"
        budget = JobBudget(BudgetLedger(self.local / "budget.sqlite3"),
                           check_session=lambda: self._check_session(record["investigation_id"], epoch),
                           request_lock=self._lock, max_reservation_usd=self._job_ceiling(config))
        provider = None
        try:
            self._save_owned(record)
            provider = self._factory(config, budget, key)
            # Offline injected providers cannot be described as live progress.
            record["provider_mode"] = provider.mode
            self._save_owned(record)
            def event(item):
                update = deepcopy(item)
                evidence = update.pop("evidence_record", None)
                evidence_ids = update.get("evidence_ids", [])
                evidence_id = update.get("evidence_id") or (evidence_ids[0] if len(evidence_ids) == 1 else None)
                if evidence is not None and evidence_id:
                    record["evidence"][evidence_id] = evidence
                for counter in ("accepted_responses", "live_model_calls", "request_attempts"):
                    if counter in update:
                        record[counter] = update.pop(counter)
                record["events"].append(update)
                record["request_attempts"] = getattr(provider, "request_attempts", 0)
                self._save_owned(record)
            result = investigate_project(view, record["requirement_id"], record["question"], provider,
                                         investigation_id=record["investigation_id"], on_event=event)
            record = {**result, "agent_sources": self._runtime, "reserved_usd": budget.reserved,
                      "request_reservations": budget.count, "provider_settings": queued["provider_settings"]}
            self._check_session(record["investigation_id"], epoch)
        except Exception as error:
            # Suppress all raw factory/session exception text, including typed
            # ProviderError messages. The engine mapping is a fixed allowlist.
            record.update(state="failed", **_failure(error), completed_at=_now(), summary="", citations=[],
                          request_attempts=getattr(provider, "request_attempts", 0),
                          reserved_usd=budget.reserved, request_reservations=budget.count)
        finally:
            try:
                self._save_owned(record)
            finally:
                with self._lock:
                    if self._active == queued["investigation_id"]:
                        self._active = None
