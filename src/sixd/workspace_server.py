"""Local connected workspace with explicit, budgeted AI investigations."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit

from .project_examples import example_projects
from .project_io import MAX_JSON_BYTES, _reject_constant, _unique_object
from . import project_authoring
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


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT = "127.0.0.1", 8768
SERVICE = "sixd-connected-workspace"
SERVER_VERSION = "workspace-2"
WORKSPACE_ID = sha256(str(ROOT).casefold().encode()).hexdigest()[:16]
MAX_BODY_BYTES = 3 * 1024 * 1024
WEB = Path(__file__).resolve().parent / "web"
VENDOR = ROOT / "design" / "vendor" / "lucide.min.js"
BUILD_FILES = [WEB / name for name in ("workspace.html", "workspace.css", "workspace.js", "review-guide.js", "simulation.css", "simulation.js", "scenarios.css", "scenarios.js", "test-data.css", "test-data.js", "test-evidence.css", "test-evidence.js", "systems.css", "systems.js", "power-budget.css", "power-budget.js", "attitude.css", "attitude.js", "chains.css", "chains.js")]
CODE_FILES = [Path(__file__).with_name(name) for name in (
    "workspace_server.py", "workspace.py", "engineering.py", "lifecycle.py",
    "__init__.py", "project_examples.py", "project_io.py", "workspace_ai.py",
    "project_investigation.py", "explanation_quality.py", "model_evaluation.py", "workspace_evaluation.py", "providers.py", "action_selection.py",
    "chains.py", "attitude.py", "simulation.py", "orbital_adapter.py", "workspace_simulation.py", "project_authoring.py", "workspace_scenarios.py", "workspace_test_data.py", "test_evidence.py", "systems.py", "workspace_systems.py", "workflow_evaluation.py", "workspace_workflow_evaluation.py", "evidence_facts.py", "evidence_roles.py", "evidence_evaluation.py", "workspace_evidence_evaluation.py")]


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

    def __init__(self, address, db_path, *, ai_local_directory=None, provider_factory=None):
        self.store = WorkspaceStore(db_path)
        self.simulations = WorkspaceSimulation(self.store)
        self.scenarios = WorkspaceScenarios(self.store)
        self.test_data = WorkspaceTestData(self.store)
        self.test_evidence = TestEvidence(self.store, self.test_data)
        self.systems = WorkspaceSystems(self.store)
        self.ai = WorkspaceAI(self.store, ai_local_directory or Path(db_path).parent,
                              provider_factory=provider_factory)
        self.evaluation = WorkspaceEvaluation(self.ai)
        self.workflow_evaluation = WorkflowEvaluation(self.ai)
        self.ultra_diagnostic = UltraDiagnostic(self.ai)
        self.evidence_evaluation = EvidenceEvaluation(self.ai)
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
                    self._revision(self._one(query, "revision")))
                self._reply(200, review, filename="6d-engineering-review.json")
            elif route == "/api/test-comparisons":
                self._reply(200, self.server.test_data.list(self._one(query, "project_id"),
                    self._revision(self._one(query, "revision"))))
            elif route == "/api/test-comparison-export":
                detail = self.server.test_data.get(self._one(query, "id"), self._revision(self._one(query, "revision"), optional=True))
                self._reply(200, detail, filename=f"6d-test-comparison-{detail['receipt']['comparison_id']}.json")
            elif route.startswith("/api/test-comparisons/"):
                self._reply(200, self.server.test_data.get(route.removeprefix("/api/test-comparisons/"),
                    self._revision(self._one(query, "revision"), optional=True)))
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
            elif route in {"/", "/index.html", "/workspace.css", "/workspace.js", "/review-guide.js", "/simulation.css", "/simulation.js", "/scenarios.css", "/scenarios.js", "/test-data.css", "/test-data.js", "/test-evidence.css", "/test-evidence.js", "/systems.css", "/systems.js", "/power-budget.css", "/power-budget.js", "/attitude.css", "/attitude.js", "/chains.css", "/chains.js", "/lucide.js"}:
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
        if length > MAX_BODY_BYTES:
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
        try:
            route, query = self._query()
            value = self._body()
            if _code_fingerprint() != RUNTIME_ID:
                raise ConflictError("6D application code has changed. Restart the local workspace server before saving or running checks.")
            if route not in {"/api/projects", "/api/revisions", "/api/impact", "/api/run", "/api/ai/connect", "/api/ai/disconnect", "/api/investigations", "/api/model-evaluation/start", "/api/workflow-evaluation/start", "/api/ultra-diagnostic/start", "/api/evidence-evaluation/prepare", "/api/evidence-evaluation/start", "/api/simulations", "/api/authoring/preflight", "/api/scenarios", "/api/test-data/preview", "/api/test-comparisons", "/api/test-evidence/impact", "/api/interfaces/preview"}:
                self._error(404, "This workspace action is not available.")
                return
            if route == "/api/interfaces/preview":
                self._fields(value, {"project_id", "base_revision", "project"})
                view = self.server.systems.preview(value["project_id"], self._revision(value["base_revision"]), value["project"])
            elif route == "/api/test-evidence/impact":
                self._fields(value, {"project_id", "base_revision", "project"})
                view = self.server.test_evidence.summary(value["project_id"], self._revision(value["base_revision"]), project=value["project"])
            elif route == "/api/test-data/preview":
                self._fields(value, {"filename", "csv_text", "mapping"})
                view = self.server.test_data.preview(value["filename"], value["csv_text"], value["mapping"])
            elif route == "/api/test-comparisons":
                self._fields(value, {"project_id", "revision", "baseline_run_id", "spec"})
                view = self.server.test_data.run(value["project_id"], self._revision(value["revision"]), value["baseline_run_id"], value["spec"])
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
                self._fields(value, {"api_key"})
                view = self.server.ai.connect(value["api_key"])
            elif route == "/api/ai/disconnect":
                self._fields(value, set())
                view = self.server.ai.disconnect()
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
        except (OSError, sqlite3.Error):
            self._error(503, "Local workspace storage is unavailable. Reload the selected revision to check its saved state.")

    def log_message(self, *_):
        pass


def create_server(host=HOST, port=PORT, db_path=None, *, ai_local_directory=None, provider_factory=None):
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The development workspace must bind to loopback.")
    return WorkspaceHTTPServer((host, port), db_path or ROOT / ".local" / "workspace.sqlite3",
                               ai_local_directory=ai_local_directory, provider_factory=provider_factory)


def serve():
    with create_server() as server:
        print(f"6D connected workspace: http://{HOST}:{PORT}/", flush=True)
        server.serve_forever()
