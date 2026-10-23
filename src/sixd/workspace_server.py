"""Local connected workspace with explicit, budgeted AI investigations."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sqlite3
import threading
from urllib.parse import parse_qs, urlsplit

from .project_examples import example_projects
from .project_io import MAX_JSON_BYTES, _reject_constant, _unique_object
from . import project_authoring, spreadsheet_intake
from .workspace import ConflictError, WorkspaceError, WorkspaceStore
from .workspace_ai import WorkspaceAI
from .workspace_evaluation import WorkspaceEvaluation
from .workspace_workflow_evaluation import WorkflowEvaluation, UltraDiagnostic
from .workspace_evidence_evaluation import EvidenceEvaluation
from .workspace_simulation import WorkspaceSimulation
from .workspace_scenarios import WorkspaceScenarios
from .workspace_test_data import WorkspaceTestData
from .test_evidence import TestEvidence
from .workspace_systems import WorkspaceSystems
from .workspace_sources import WorkspaceSources
from .workspace_actions import WorkspaceActions
from .workspace_comparison import WorkspaceComparison
from .workspace_research import WorkspaceResearch
from .workspace_coverage import WorkspaceCoverage
from .workspace_series import WorkspaceSeries
from .workspace_review import WorkspaceReview
from .workspace_qualification import WorkspaceQualification
from .workspace_observability import WorkspaceObservability


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT = "127.0.0.1", 8768
SERVICE = "sixd-connected-workspace"
SERVER_VERSION = "workspace-2"
WORKSPACE_ID = sha256(str(ROOT).casefold().encode()).hexdigest()[:16]
MAX_BODY_BYTES = 3 * 1024 * 1024
WEB = Path(__file__).resolve().parent / "web"
VENDOR = ROOT / "design" / "vendor" / "lucide.min.js"
BUILD_FILES = [WEB / name for name in ("workspace.html", "workspace.css", "workspace.js", "review-guide.js", "simulation.css", "simulation.js", "scenarios.css", "scenarios.js", "test-data.css", "test-data.js", "test-evidence.css", "test-evidence.js", "systems.css", "systems.js", "power-budget.css", "power-budget.js", "attitude.css", "attitude.js", "powered-flight.css", "powered-flight.js", "chains.css", "chains.js", "spreadsheet-intake.css", "spreadsheet-intake.js", "source-library.js", "source-library.css", "action-queue.js", "action-queue.css", "design-comparison.js", "design-comparison.css", "source-research.js", "source-research.css", "engineering-coverage.js", "engineering-coverage.css")]
CODE_FILES = [Path(__file__).with_name(name) for name in (
    "workspace_server.py", "workspace.py", "engineering.py", "lifecycle.py",
    "__init__.py", "project_examples.py", "project_io.py", "workspace_ai.py",
    "project_investigation.py", "explanation_quality.py", "model_evaluation.py", "workspace_evaluation.py", "providers.py", "action_selection.py",
    "chains.py", "attitude.py", "powered_flight.py", "simulation.py", "orbital_adapter.py", "workspace_simulation.py", "project_authoring.py", "spreadsheet_intake.py", "workspace_scenarios.py", "workspace_test_data.py", "test_evidence.py", "systems.py", "workspace_systems.py", "workflow_evaluation.py", "workspace_workflow_evaluation.py", "evidence_facts.py", "evidence_roles.py", "change_evidence.py", "credential_store.py", "evidence_evaluation.py", "workspace_evidence_evaluation.py", "workspace_sources.py", "workspace_actions.py", "workspace_comparison.py", "source_context.py", "workspace_research.py", "workspace_coverage.py")]


BUILD_FILES += [WEB / name for name in ("simulation-imports.js", "simulation-imports.css", "envelopes.js", "envelopes.css")]
BUILD_FILES += [WEB / name for name in ("review-workspace.js", "review-workspace.css", "units.js", "connected-review.css")]
CODE_FILES += [Path(__file__).with_name("workspace_review.py")]
CODE_FILES += [Path(__file__).with_name("workspace_series.py")]
CODE_FILES += [Path(__file__).with_name(name) for name in ("ai_qualification.py", "workspace_qualification.py", "workspace_observability.py")]
BUILD_FILES += [WEB / name for name in ("ai-quality.js", "ai-quality.css")]


def _code_fingerprint():
    digest = sha256()
    for path in CODE_FILES:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


RUNTIME_ID = _code_fingerprint()
RUNTIME_MODIFIED = max(path.stat().st_mtime for path in CODE_FILES)


def build_status():
    digest = sha256(RUNTIME_ID.encode())
    modified = RUNTIME_MODIFIED
    for path in BUILD_FILES:
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
            modified = max(modified, path.stat().st_mtime)
    return {"service": SERVICE, "server_version": SERVER_VERSION,
            "workspace": WORKSPACE_ID, "mode": "connected_workspace",
            "calculation_mode": "local_deterministic", "inference_mode": "off",
            "runtime_id": RUNTIME_ID, "restart_required": _code_fingerprint() != RUNTIME_ID,
            "build_id": digest.hexdigest()[:12],
            "updated_at": datetime.fromtimestamp(modified, timezone.utc).isoformat()}


class WorkspaceHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, db_path, *, ai_local_directory=None, provider_factory=None, research_transport=None, observability_transport=None):
        self._post_lock = threading.RLock()
        self._stopping = False
        self.store = WorkspaceStore(db_path)
        self.simulations = WorkspaceSimulation(self.store)
        self.scenarios = WorkspaceScenarios(self.store)
        self.test_data = WorkspaceTestData(self.store)
        self.series = WorkspaceSeries(self.store)
        self.test_evidence = TestEvidence(self.store, self.test_data)
        self.systems = WorkspaceSystems(self.store)
        self.sources = WorkspaceSources(self.store)
        self.research = WorkspaceResearch(self.store, self.sources, transport=research_transport)
        self.actions = WorkspaceActions(self.store, self.sources)
        self.coverage = WorkspaceCoverage(self.store)
        self.comparison = WorkspaceComparison(self.store, self.scenarios)
        self.review_workspace = WorkspaceReview(self.store, self.coverage, self.actions, self.sources, self.series, self.scenarios)
        self.ai = WorkspaceAI(self.store, ai_local_directory or Path(db_path).parent,
                              provider_factory=provider_factory)
        self.evaluation = WorkspaceEvaluation(self.ai)
        self.workflow_evaluation = WorkflowEvaluation(self.ai)
        self.ultra_diagnostic = UltraDiagnostic(self.ai)
        self.evidence_evaluation = EvidenceEvaluation(self.ai)
        self.qualification = WorkspaceQualification(self.ai)
        self.observability = WorkspaceObservability(self.ai, self.qualification, transport=observability_transport)
        super().__init__(address, WorkspaceHandler)


class WorkspaceHandler(BaseHTTPRequestHandler):
    server_version = "6DLocal/1"

    def _reply(self, status, body, content_type="application/json; charset=utf-8", *, filename=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=True, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, message):
        self._reply(status, {"error": message})

    def _local_request(self):
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host", "") not in allowed:
            self._error(403, "Open 6D using its local address.")
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + host for host in allowed}:
            self._error(403, "Cross-origin workspace requests are not accepted.")
            return False
        return True

    def _query(self):
        return urlsplit(self.path).path, parse_qs(urlsplit(self.path).query)

    @staticmethod
    def _one(query, name, default=None):
        values = query.get(name)
        if not values:
            return default
        if len(values) != 1 or not values[0]:
            raise WorkspaceError(f"Provide exactly one {name}.")
        return values[0]

    @staticmethod
    def _revision(value, *, optional=False):
        if value is None and optional:
            return None
        if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r"[1-9][0-9]*", str(value)):
            raise WorkspaceError("Revision must be a positive integer.")
        return int(value)

    def do_GET(self):
        if not self._local_request():
            return
        try:
            route, query = self._query()
            if route == "/health":
                self._reply(200, {key: value for key, value in build_status().items()
                                  if key in {"service", "server_version", "workspace", "build_id", "runtime_id", "restart_required"}})
            elif route == "/api/status":
                status = build_status()
                status["inference_mode"] = "on_request" if self.server.ai.status()["configured"] else "off"
                self._reply(200, status)
            elif route == "/api/ai/status":
                self._reply(200, self.server.ai.status())
            elif route == "/api/model-evaluation/status":
                self._reply(200, self.server.evaluation.status())
            elif route == "/api/research/status":
                self._reply(200, self.server.research.status())
            elif route == "/api/research":
                if _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("6D code changed. Restart before reviewing reference research.")
                self._reply(200, self.server.research.list(self._one(query, "project_id"), self._revision(self._one(query, "revision"))))
            elif route.startswith("/api/research/"):
                if _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("6D code changed. Restart before reviewing reference research.")
                suffix = route.removeprefix("/api/research/")
                preview = suffix.endswith("/preview")
                identity = suffix.removesuffix("/preview") if preview else suffix
                receipt = self.server.research.get(identity, self._one(query, "project_id"), self._revision(self._one(query, "revision")))
                if preview:
                    index = self._one(query, "result_index")
                    if not re.fullmatch(r"0|[1-9][0-9]*", index):
                        raise WorkspaceError("Select an exact research result index.")
                    self._reply(200, {"source": self.server.research.preview_source(receipt, int(index)),
                        "search_id": receipt["search_id"], "receipt_digest": receipt["digest"], "result_index": int(index),
                        "project_id": receipt["project_id"], "revision": self._revision(self._one(query, "revision")),
                        "search_revision": receipt["revision"]})
                else:
                    self._reply(200, receipt)
            elif route == "/api/coverage":
                if _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("6D code changed. Restart before projecting engineering coverage.")
                self._reply(200, self.server.coverage.summary(self._one(query, "project_id"),
                    self._revision(self._one(query, "revision"))))
            elif route == "/api/sources":
                if _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("6D code changed. Restart before projecting project source links.")
                self._reply(200, self.server.sources.summary(self._one(query, "project_id"),
                    self._revision(self._one(query, "revision"))))
            elif route == "/api/actions":
                if _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("6D code changed. Restart before projecting engineering actions.")
                self._reply(200, self.server.actions.summary(self._one(query, "project_id"),
                    self._revision(self._one(query, "revision"))))
            elif route == "/api/design-comparison/catalog":
                if _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("6D code changed. Restart before comparing recorded designs.")
                self._reply(200, self.server.comparison.catalog(self._one(query, "project_id"),
                    self._revision(self._one(query, "revision"))))
            elif route == "/api/project-intake/example-workbook":
                self._reply(200, (ROOT / "examples/project-intake/constructed-drag.xlsx").read_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    filename="6d-constructed-drag.xlsx")
            elif route == "/api/test-evidence":
                if _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("6D application code has changed. Restart the local workspace server before projecting linked test evidence.")
                self._reply(200, self.server.test_evidence.summary(self._one(query, "project_id"),
                    self._revision(self._one(query, "revision"))))
            elif route == "/api/interfaces":
                if _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("6D code changed. Restart before projecting interface checks.")
                self._reply(200, self.server.systems.get(self._one(query, "project_id"),
                    self._revision(self._one(query, "revision"))))
            elif route == "/api/engineering-review-export":
                if _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("6D application code has changed. Restart the local workspace server before exporting a combined review.")
                review = self.server.test_evidence.review_export(self._one(query, "project_id"),
                    self._revision(self._one(query, "revision")), source_library=self.server.sources, action_queue=self.server.actions, coverage=self.server.coverage, simulation_imports=self.server.series, operating_envelopes=self.server.scenarios)
                self._reply(200, review, filename="6d-engineering-review.json")
            elif route == "/api/simulation-import-summary":
                self._reply(200, self.server.series.summary(self._one(query, "project_id"), self._revision(self._one(query, "revision"))))
            elif route == "/api/simulation-imports":
                self._reply(200, self.server.series.list(self._one(query, "project_id"), self._revision(self._one(query, "revision"))))
            elif route == "/api/simulation-import-export":
                detail = self.server.series.get(self._one(query, "id"), self._revision(self._one(query, "revision"), optional=True))
                self._reply(200, detail, filename=f"6d-simulation-import-{detail['receipt']['import_id']}.json")
            elif route.startswith("/api/simulation-imports/"):
                self._reply(200, self.server.series.get(route.removeprefix("/api/simulation-imports/"), self._revision(self._one(query, "revision"), optional=True)))
            elif route in {"/simulation-imports.js", "/simulation-imports.css"}:
                path = WEB / route[1:]
                self._reply(200, path.read_bytes(), "application/javascript; charset=utf-8" if path.suffix == ".js" else "text/css; charset=utf-8")
            elif route == "/api/test-comparisons":
                self._reply(200, self.server.test_data.list(self._one(query, "project_id"),
                    self._revision(self._one(query, "revision"))))
            elif route == "/api/test-comparison-export":
                detail = self.server.test_data.get(self._one(query, "id"), self._revision(self._one(query, "revision"), optional=True))
                self._reply(200, detail, filename=f"6d-test-comparison-{detail['receipt']['comparison_id']}.json")
            elif route.startswith("/api/test-comparisons/"):
                self._reply(200, self.server.test_data.get(route.removeprefix("/api/test-comparisons/"),
                    self._revision(self._one(query, "revision"), optional=True)))
            elif route == "/api/review-workspace":
                if _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("Application code changed. Restart 6D before loading the connected review.")
                self._reply(200, self.server.review_workspace.summary(self._one(query, "project_id"), self._revision(self._one(query, "revision"))))
            elif route in {"/review-workspace.js", "/review-workspace.css", "/units.js", "/connected-review.css"}:
                path = WEB / route[1:]
                self._reply(200, path.read_bytes(), "application/javascript; charset=utf-8" if path.suffix == ".js" else "text/css; charset=utf-8")
            elif route == "/api/envelopes/summary":
                self._reply(200, self.server.scenarios.envelope_summary(self._one(query, "project_id"), self._revision(self._one(query, "revision"))))
            elif route in {"/envelopes.js", "/envelopes.css"}:
                path = WEB / route[1:]
                self._reply(200, path.read_bytes(), "application/javascript; charset=utf-8" if path.suffix == ".js" else "text/css; charset=utf-8")
            elif route == "/api/scenarios":
                self._reply(200, self.server.scenarios.list(self._one(query, "project_id"),
                    self._revision(self._one(query, "revision"))))
            elif route == "/api/scenario-export":
                detail = self.server.scenarios.get(self._one(query, "id"), self._revision(self._one(query, "revision"), optional=True))
                self._reply(200, detail, filename=f"6d-scenario-{detail['receipt']['study_id']}.json")
            elif route.startswith("/api/scenarios/"):
                self._reply(200, self.server.scenarios.get(route.removeprefix("/api/scenarios/"),
                    self._revision(self._one(query, "revision"), optional=True)))
            elif route == "/api/simulations":
                project_id = self._one(query, "project_id")
                revision = self._revision(self._one(query, "revision"))
                self._reply(200, self.server.simulations.list(project_id, revision))
            elif route == "/api/simulation-comparison":
                self._reply(200, self.server.simulations.compare(self._one(query, "left_id"), self._one(query, "right_id")))
            elif route == "/api/simulation-export":
                detail = self.server.simulations.get(self._one(query, "id"), self._revision(self._one(query, "revision"), optional=True))
                self._reply(200, detail, filename=f"6d-simulation-{detail['receipt']['simulation_id']}.json")
            elif route.startswith("/api/simulations/"):
                self._reply(200, self.server.simulations.get(route.removeprefix("/api/simulations/"),
                    self._revision(self._one(query, "revision"), optional=True)))
            elif route.startswith("/api/model-evaluation/comparisons/"):
                self._reply(200, self.server.evaluation.get(route.removeprefix("/api/model-evaluation/comparisons/")))
            elif route == "/api/workflow-evaluation/status":
                self._reply(200, self.server.workflow_evaluation.status())
            elif route == "/api/ai-quality/status":
                self._reply(200, {"schema": "sixd.ai-quality-status.v1", "connection": self.server.ai.status(),
                    "qualification": self.server.qualification.status(), "observability": self.server.observability.status(),
                    "research": self.server.research.status()})
            elif route.startswith("/api/ai-quality/runs/"):
                detail = self.server.qualification.get(route.removeprefix("/api/ai-quality/runs/"))
                self._reply(200, detail, filename=f"6d-ai-qualification-{detail['qualification_id']}.json")
            elif route in {"/ai-quality.js", "/ai-quality.css"}:
                path = WEB / route[1:]
                self._reply(200, path.read_bytes(), "text/javascript; charset=utf-8" if path.suffix == ".js" else "text/css; charset=utf-8")
            elif route == "/api/ultra-diagnostic/status":
                self._reply(200, self.server.ultra_diagnostic.status())
            elif route == "/api/evidence-evaluation/status":
                self._reply(200, self.server.evidence_evaluation.status())
            elif route.startswith("/api/evidence-evaluation/runs/"):
                detail = self.server.evidence_evaluation.get(route.removeprefix("/api/evidence-evaluation/runs/"))
                self._reply(200, detail, filename=f"6d-evidence-evaluation-{detail['comparison_id']}.json")
            elif route.startswith("/api/ultra-diagnostic/runs/"):
                detail = self.server.ultra_diagnostic.get(route.removeprefix("/api/ultra-diagnostic/runs/"))
                self._reply(200, detail, filename=f"6d-ultra-diagnostic-{detail['comparison_id']}.json")
            elif route.startswith("/api/workflow-evaluation/runs/"):
                detail = self.server.workflow_evaluation.get(route.removeprefix("/api/workflow-evaluation/runs/"))
                self._reply(200, detail, filename=f"6d-workflow-evaluation-{detail['comparison_id']}.json")
            elif route == "/api/investigations":
                project_id = self._one(query, "project_id")
                revision = self._revision(self._one(query, "revision"))
                requirement_id = self._one(query, "requirement_id")
                if project_id is None:
                    raise WorkspaceError("A project ID is required.")
                self._reply(200, {"investigations": self.server.ai.list(project_id, revision, requirement_id)})
            elif route.startswith("/api/investigations/"):
                self._reply(200, self.server.ai.get(route.removeprefix("/api/investigations/")))
            elif route == "/api/projects":
                self._reply(200, {"projects": self.server.store.list_projects()})
            elif route == "/api/model-catalog":
                self._reply(200, project_authoring.catalog())
            elif route == "/api/templates":
                projects = example_projects()
                self._reply(200, {"templates": [{"id": identity, "name": title, "project": projects[identity]}
                            for identity, title in (("baseline", "Four bounded component checks"),
                                                    ("missing_evidence", "Changed inputs with a control evidence gap"),
                                                    ("power_budget", "Operating-mode power and energy budget"),
                                                    ("attitude_review", "Single-axis spacecraft pointing review"),
                                                    ("powered_flight_review", "Constructed powered vertical flight"),
                                                    ("chain_review", "Connected aerodynamic load and structure review"),
                                                    ("orbital_review", "Orbital trajectory and engineering review"))]})
            elif route in {"/api/workspace", "/api/export"}:
                project_id = self._one(query, "project_id")
                if project_id is None:
                    project_id = self.server.store.ensure_default()
                revision = self._revision(self._one(query, "revision"), optional=True)
                view = self.server.store.get(project_id, revision)
                if "system_interfaces" in view and _code_fingerprint() != RUNTIME_ID:
                    raise ConflictError("6D code changed. Restart before viewing or exporting projected interfaces; original saved receipts remain preserved.")
                if route == "/api/workspace":
                    self._reply(200, view)
                elif not view["run"]:
                    self._error(409, "Run checks for this saved revision before exporting its report.")
                else:
                    exported = {"schema": "sixd.workspace-export.v1",
                                **{key: view[key] for key in ("project_id", "revision", "project", "run", "graph", "impact")}}
                    if "system_interfaces" in view:
                        exported["system_interfaces"] = view["system_interfaces"]
                    identity = sha256(project_id.encode()).hexdigest()[:12]
                    self._reply(200, exported, filename=f"6d-{identity}-r{view['revision']}.json")
            elif route in {"/", "/index.html", "/workspace.css", "/workspace.js", "/review-guide.js", "/simulation.css", "/simulation.js", "/scenarios.css", "/scenarios.js", "/test-data.css", "/test-data.js", "/test-evidence.css", "/test-evidence.js", "/systems.css", "/systems.js", "/power-budget.css", "/power-budget.js", "/attitude.css", "/attitude.js", "/powered-flight.css", "/powered-flight.js", "/chains.css", "/chains.js", "/spreadsheet-intake.js", "/spreadsheet-intake.css", "/source-library.js", "/source-library.css", "/action-queue.js", "/action-queue.css", "/design-comparison.js", "/design-comparison.css", "/source-research.js", "/source-research.css", "/engineering-coverage.js", "/engineering-coverage.css", "/lucide.js"}:
                if route in {"/", "/index.html"}:
                    path, mime = WEB / "workspace.html", "text/html; charset=utf-8"
                elif route == "/lucide.js":
                    path, mime = VENDOR, "text/javascript; charset=utf-8"
                else:
                    path = WEB / route.removeprefix("/")
                    mime = "text/css; charset=utf-8" if route.endswith(".css") else "text/javascript; charset=utf-8"
                self._reply(200, path.read_bytes(), mime)
            else:
                self._error(404, "This workspace route is not available.")
        except ConflictError as error:
            self._error(409, str(error))
        except (WorkspaceError, ValueError, UnicodeError) as error:
            self._error(400, str(error))
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # View changes may cancel a read after its response was prepared.
            # An ended client connection is not a workspace storage failure.
            self.close_connection = True
        except (OSError, sqlite3.Error):
            self._error(503, "Local workspace storage or an application file is unavailable. Your saved records have not been replaced.")

    def _body(self):
        if self.headers.get("Transfer-Encoding"):
            raise WorkspaceError("Chunked workspace requests are not supported.")
        if self.headers.get_content_type() != "application/json":
            raise WorkspaceError("Send workspace records as application/json.")
        raw_size = self.headers.get("Content-Length", "")
        if not re.fullmatch(r"[0-9]+", raw_size):
            raise WorkspaceError("A bounded Content-Length is required.")
        length = int(raw_size)
        if length > (26 * 1024 * 1024 if self._query()[0] in {"/api/simulation-imports", "/api/simulation-imports/preview"} else MAX_BODY_BYTES):
            raise WorkspaceError("The workspace request exceeds the three-megabyte limit.")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise WorkspaceError("The workspace request was incomplete.")
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        if not isinstance(value, dict):
            raise WorkspaceError("A workspace request must be a JSON object.")
        return value

    @staticmethod
    def _fields(value, expected):
        if set(value) != set(expected):
            raise WorkspaceError("The request has missing or unsupported fields.")
        if "project" in value and len(json.dumps(value["project"], ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_JSON_BYTES:
            raise WorkspaceError("The structured project exceeds the two-megabyte limit.")

    def do_POST(self):
        if not self._local_request():
            return
        # Serialize explicit writes with stopping, so no new mutation begins
        # after shutdown has been accepted. Background AI jobs are checked too.
        with self.server._post_lock:
            if self.server._stopping:
                self._error(409, "6D is stopping. Reopen it before changing project data.")
                return
            self._post_action()

    def _post_action(self):
        try:
            route, query = self._query()
            value = self._body()
            if route == "/api/shutdown":
                self._fields(value, set())
                with self.server.ai._lock:
                    if self.server.ai._active:
                        raise ConflictError("Wait for the active investigation or comparison before stopping 6D.")
                    self.server._stopping = True
                self._reply(200, {"stopping": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if _code_fingerprint() != RUNTIME_ID:
                raise ConflictError("6D application code has changed. Restart the local workspace server before saving or running checks.")
            if route not in {"/api/envelopes/preview", "/api/simulation-imports", "/api/simulation-imports/preview", "/api/projects", "/api/revisions", "/api/impact", "/api/run", "/api/ai/connect", "/api/ai/disconnect", "/api/ai/forget", "/api/investigations", "/api/model-evaluation/start", "/api/workflow-evaluation/start", "/api/ultra-diagnostic/start", "/api/evidence-evaluation/prepare", "/api/evidence-evaluation/start", "/api/simulations", "/api/authoring/preflight", "/api/scenarios", "/api/test-data/preview", "/api/test-comparisons", "/api/test-evidence/impact", "/api/interfaces/preview", "/api/project-intake/inspect", "/api/project-intake/preview", "/api/sources", "/api/source-links", "/api/source-links/confirm", "/api/actions", "/api/actions/update", "/api/actions/review", "/api/design-comparison", "/api/research/connect", "/api/research/disconnect", "/api/research/search", "/api/coverage/save", "/api/ai-quality/prepare", "/api/ai-quality/start", "/api/observability/connect", "/api/observability/disconnect", "/api/observability/preview", "/api/observability/export"}:
                self._error(404, "This workspace action is not available.")
                return
            if route in {"/api/source-links", "/api/source-links/confirm"}:
                if not isinstance(value.get("expected_digest"), str) or re.fullmatch(r"[a-f0-9]{64}", value["expected_digest"]) is None:
                    raise WorkspaceError("Refresh the source library and supply its exact displayed context digest.")
            if route == "/api/research/connect":
                self._fields(value, {"api_key", "credit_limit"})
                view = self.server.research.connect(value["api_key"], value["credit_limit"])
            elif route == "/api/research/disconnect":
                self._fields(value, set())
                view = self.server.research.disconnect()
            elif route == "/api/research/search":
                self._fields(value, {"project_id", "revision", "target_id", "query", "expected_digest"})
                view = self.server.research.search(value["project_id"], self._revision(value["revision"]),
                    value["target_id"], value["query"], value["expected_digest"])
            elif route == "/api/coverage/save":
                self._fields(value, {"project_id", "revision", "spec", "expected_digest"})
                view = self.server.coverage.save(value["project_id"], self._revision(value["revision"]),
                    value["spec"], expected_digest=value["expected_digest"])
            elif route == "/api/design-comparison":
                self._fields(value, {"project_id", "revision", "left", "right"})
                view = self.server.comparison.compare(value["project_id"], self._revision(value["revision"]), value["left"], value["right"])
            elif route == "/api/actions":
                self._fields(value, {"project_id", "revision", "spec", "expected_digest"})
                view = self.server.actions.create(value["project_id"], self._revision(value["revision"]), value["spec"], expected_digest=value["expected_digest"])
            elif route == "/api/actions/update":
                self._fields(value, {"project_id", "revision", "action_id", "base_version", "spec", "expected_digest"})
                view = self.server.actions.update(value["project_id"], self._revision(value["revision"]), value["action_id"], value["base_version"], value["spec"], expected_digest=value["expected_digest"])
            elif route == "/api/actions/review":
                self._fields(value, {"project_id", "revision", "action_id", "base_version", "expected_digest"})
                view = self.server.actions.review(value["project_id"], self._revision(value["revision"]), value["action_id"], value["base_version"], expected_digest=value["expected_digest"])
            elif route == "/api/sources":
                self._fields(value, {"project_id", "revision", "source"})
                view = self.server.sources.save_source(value["project_id"], self._revision(value["revision"]), value["source"])
            elif route == "/api/source-links":
                self._fields(value, {"project_id", "revision", "spec", "expected_digest"})
                view = self.server.sources.link_source(value["project_id"], self._revision(value["revision"]), value["spec"], expected_digest=value["expected_digest"])
            elif route == "/api/source-links/confirm":
                self._fields(value, {"project_id", "revision", "link_id", "base_version", "expected_digest"})
                view = self.server.sources.confirm_link(value["project_id"], self._revision(value["revision"]), value["link_id"], value["base_version"], expected_digest=value["expected_digest"])
            elif route == "/api/project-intake/inspect":
                self._fields(value, {"filename", "content_base64"})
                view = spreadsheet_intake.inspect_document(value["filename"], value["content_base64"])
            elif route == "/api/project-intake/preview":
                self._fields(value, {"project", "files", "tables"})
                view = spreadsheet_intake.preview(value)
            elif route == "/api/interfaces/preview":
                self._fields(value, {"project_id", "base_revision", "project"})
                view = self.server.systems.preview(value["project_id"], self._revision(value["base_revision"]), value["project"])
            elif route == "/api/test-evidence/impact":
                self._fields(value, {"project_id", "base_revision", "project"})
                view = self.server.test_evidence.summary(value["project_id"], self._revision(value["base_revision"]), project=value["project"])
            elif route == "/api/simulation-imports/preview":
                self._fields(value, {"spec"})
                view = self.server.series.preview(value["spec"])
            elif route == "/api/simulation-imports":
                self._fields(value, {"project_id", "revision", "baseline_run_id", "spec"})
                view = self.server.series.save(value["project_id"], self._revision(value["revision"]), value["baseline_run_id"], value["spec"])
            elif route == "/api/test-data/preview":
                self._fields(value, {"filename", "csv_text", "mapping"})
                view = self.server.test_data.preview(value["filename"], value["csv_text"], value["mapping"])
            elif route == "/api/test-comparisons":
                self._fields(value, {"project_id", "revision", "baseline_run_id", "spec"})
                view = self.server.test_data.run(value["project_id"], self._revision(value["revision"]), value["baseline_run_id"], value["spec"])
            elif route == "/api/envelopes/preview":
                self._fields(value, {"project_id", "revision", "baseline_run_id", "spec"})
                view = self.server.scenarios.preview_envelope(value["project_id"], self._revision(value["revision"]), value["baseline_run_id"], value["spec"])
            elif route == "/api/scenarios":
                self._fields(value, {"project_id", "revision", "baseline_run_id", "spec"})
                view = self.server.scenarios.run(value["project_id"], self._revision(value["revision"]), value["baseline_run_id"], value["spec"])
            elif route == "/api/authoring/preflight":
                self._fields(value, {"project"})
                view = project_authoring.preflight(value["project"])
            elif route == "/api/simulations":
                self._fields(value, {"project_id", "revision", "spec"})
                view = self.server.simulations.run(value["project_id"], self._revision(value["revision"]), value["spec"])
            elif route == "/api/model-evaluation/start":
                self._fields(value, {"allow_spend", "allowance_usd"})
                view = self.server.evaluation.start(allow_spend=value["allow_spend"], allowance_usd=value["allowance_usd"])
            elif route == "/api/workflow-evaluation/start":
                self._fields(value, {"allow_spend", "allowance_usd"})
                view = self.server.workflow_evaluation.start(allow_spend=value["allow_spend"], allowance_usd=value["allowance_usd"])
            elif route == "/api/ai-quality/prepare":
                self._fields(value, set())
                view = self.server.qualification.prepare()
            elif route == "/api/ai-quality/start":
                self._fields(value, {"allow_spend", "allowance_usd"})
                view = self.server.qualification.start(allow_spend=value["allow_spend"], allowance_usd=value["allowance_usd"])
            elif route == "/api/observability/connect":
                self._fields(value, {"api_key", "region", "workspace_id"})
                view = self.server.observability.connect(value["api_key"], region=value["region"], workspace_id=value["workspace_id"])
            elif route == "/api/observability/disconnect":
                self._fields(value, set())
                view = self.server.observability.disconnect()
            elif route == "/api/observability/preview":
                self._fields(value, {"qualification_id"})
                view = self.server.observability.preview(value["qualification_id"])
            elif route == "/api/observability/export":
                self._fields(value, {"qualification_id", "preview_digest", "allow_upload"})
                view = self.server.observability.export(value["qualification_id"], value["preview_digest"], allow_upload=value["allow_upload"])
            elif route == "/api/ultra-diagnostic/start":
                self._fields(value, {"allow_spend", "allowance_usd"})
                view = self.server.ultra_diagnostic.start(allow_spend=value["allow_spend"], allowance_usd=value["allowance_usd"])
            elif route == "/api/evidence-evaluation/prepare":
                self._fields(value, set())
                view = self.server.evidence_evaluation.prepare()
            elif route == "/api/evidence-evaluation/start":
                self._fields(value, {"allow_spend", "allowance_usd"})
                view = self.server.evidence_evaluation.start(allow_spend=value["allow_spend"], allowance_usd=value["allowance_usd"])
            elif route == "/api/ai/connect":
                self._fields(value, {"api_key", "remember"} if "remember" in value else {"api_key"})
                view = self.server.ai.connect(value["api_key"], remember=value.get("remember", False))
            elif route == "/api/ai/disconnect":
                self._fields(value, set())
                view = self.server.ai.disconnect()
            elif route == "/api/ai/forget":
                self._fields(value, set())
                view = self.server.ai.forget_key()
            elif route == "/api/investigations":
                basic = {"project_id", "revision", "requirement_id", "question"}
                selected_test = {"test_comparison_id", "test_row_number"}
                self._fields(value, basic | selected_test if set(value) & selected_test else basic)
                if set(value) & selected_test and (not isinstance(value["test_comparison_id"], str)
                        or re.fullmatch(r"[a-f0-9]{32}", value["test_comparison_id"]) is None
                        or type(value["test_row_number"]) is not int or not 2 <= value["test_row_number"] <= 201):
                    raise WorkspaceError("Select a saved test comparison and an exact CSV row number from 2 through 201.")
                if not isinstance(value["project_id"], str) or not value["project_id"].strip():
                    raise WorkspaceError("A project ID is required.")
                extras = {key: value[key] for key in selected_test} if set(value) & selected_test else {}
                view = self.server.ai.start(value["project_id"], self._revision(value["revision"]),
                                            value["requirement_id"], value["question"], **extras)
            elif route == "/api/projects":
                self._fields(value, {"project"})
                view = self.server.store.create_project(value["project"])
            else:
                required = {"project_id", "revision"} if route == "/api/run" else {"project_id", "base_revision", "project"}
                self._fields(value, required)
                if not isinstance(value["project_id"], str) or not value["project_id"].strip():
                    raise WorkspaceError("A project ID is required.")
                if route == "/api/run":
                    view = self.server.store.run(value["project_id"], self._revision(value["revision"]))
                else:
                    revision = self._revision(value["base_revision"])
                    if route == "/api/impact":
                        view = {"impact": self.server.store.preview_change(value["project_id"], revision, value["project"])}
                    else:
                        view = self.server.store.save_revision(value["project_id"], revision, value["project"])
            self._reply(200, view)
        except ConflictError as error:
            self._error(409, str(error))
        except (WorkspaceError, ValueError, UnicodeError, RecursionError) as error:
            self._error(400, str(error))
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # A committed explicit write is never retried after disconnection.
            self.close_connection = True
        except (OSError, sqlite3.Error):
            self._error(503, "Local workspace storage is unavailable. Reload the selected revision to check its saved state.")

    def log_message(self, *_):
        pass


def create_server(host=HOST, port=PORT, db_path=None, *, ai_local_directory=None, provider_factory=None, research_transport=None, observability_transport=None):
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The development workspace must bind to loopback.")
    return WorkspaceHTTPServer((host, port), db_path or ROOT / ".local" / "workspace.sqlite3",
                               ai_local_directory=ai_local_directory, provider_factory=provider_factory,
                               research_transport=research_transport, observability_transport=observability_transport)


def serve():
    with create_server() as server:
        print(f"6D connected workspace: http://{HOST}:{PORT}/", flush=True)
        server.serve_forever()
