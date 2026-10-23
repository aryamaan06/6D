"""Read-only links between frozen test comparisons and engineering reviews.

Applicability follows explicit recorded dependencies. It is not a new physical
validation, and historical measured outcomes are never recalculated against a
new design. Every public read uses one explicit SQLite snapshot.
"""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re

from . import chains, lifecycle, workspace
from .workspace import ConflictError, WorkspaceError, _digest, _encode, _revision

SCHEMA = "sixd.test-evidence.v1"
CONTEXT_SCHEMA = "sixd.test-evidence-investigation-context.v1"
EXPORT_SCHEMA = "sixd.engineering-review-with-tests.v1"
HISTORY_LIMIT = 20
MAX_CONTEXT_BYTES = 128 * 1024
MAX_EXPORT_BYTES = 64 * 1024 * 1024
LIMITATIONS = [
    "Measured criterion satisfaction and prediction agreement remain the original recorded outcomes against each comparison's frozen baseline; they do not replace the canonical engineering review.",
    "Applicability follows explicit requirement, model, bound input, criterion, adapter and source records only; physical coupling is not inferred.",
    "Same dependencies means the compared recorded dependencies match, not that a historic test has been independently verified for a later revision or repeated run.",
    "Matching conditions, observable and aggregation are an unverified user declaration. Authenticity, calibration, uncertainty and physical test execution are not established.",
    "Unknown, unsupported or invalid measurement rows remain evidence gaps; an applicability label cannot turn an unassessed comparison into a pass.",
    "History includes only the latest 20 comparisons at or before the selected revision; counts describe included rows, not a completeness or readiness score.",
    "No adapters, physical simulation or paid model calls run while reading these links or exporting the report.",
    "Record digests are unsigned consistency checks, not authenticated approval, physical validation, mission success or launch authorization.",
]


def _sources():
    directory = Path(__file__).resolve().parent
    return {**workspace._sources(), **{name: sha256((directory / name).read_bytes()).hexdigest()
                                     for name in ("workspace_test_data.py", "test_evidence.py")}}


def _comparison_sources(sources):
    return {key: value for key, value in sources.items() if key != "test_evidence.py"}


def _requirements(project):
    return {item["id"]: item for item in project["requirements"]}


def _models(project):
    return {item["id"]: item for item in project["models"]}


def _dependencies(project, requirement):
    model = _models(project)[requirement["model_id"]]
    inputs = lifecycle._bound_inputs(project, model)
    inputs[requirement["limit_input"]] = deepcopy(project["inputs"][requirement["limit_input"]])
    return model, inputs


def _compact_model(project, requirement, review):
    if requirement is None:
        return None
    model = _models(project)[requirement["model_id"]]
    evidence = review["evidence"].get(model["id"]) if review else None
    result = {"definition": deepcopy(model), "input_records": lifecycle._bound_inputs(project, model),
            "adapter_version": evidence["model_version"] if evidence else workspace.MODEL_VERSIONS.get(model["type"]),
            "verification_sources": deepcopy(review["verification_sources"]) if review else None,
            "status": evidence["status"] if evidence else "not_assessed",
            "evidence_fingerprint": evidence["fingerprint"] if evidence else None,
            "selected_metric": deepcopy(evidence["metrics"].get(requirement["metric"])) if evidence else None,
            "assumptions": deepcopy(evidence["assumptions"]) if evidence else [],
            "not_assessed": deepcopy(evidence["not_assessed"]) if evidence else ["The selected revision has no current canonical review."],
            "issues": deepcopy(evidence["issues"]) if evidence else []}
    if model.get("links"):
        result["calculation_dependencies"] = chains.dependency_configuration(project, model["id"])
    # Optional current assessment fields travel with their original receipt;
    # never add today's assessment to a historical compact record.
    for key in ("numerical_accuracy", "applicability"):
        if evidence is not None and key in evidence:
            if key == "numerical_accuracy":
                from .project_investigation import _accuracy_projection
                result[key] = _accuracy_projection(evidence[key])
            else:
                result[key] = deepcopy(evidence[key])
    if evidence is not None and "flight_response" in evidence:
        result["flight_response"] = {"diagnostics": deepcopy(evidence["flight_response"]["diagnostics"])}
    return result


def _current(view):
    review = view["run"]["review"] if view["run"] else None
    return {"run_id": view["run"]["run_id"] if view["run"] else None,
            "review_digest": review["digest"] if review else None, "review": review}


def _applicability(receipt, row, view, selected, sources, *, draft=False):
    original = receipt["baseline"]["review"]
    original_requirement = _requirements(original["project"]).get(row["requirement_id"])
    requirement = _requirements(selected).get(row["requirement_id"])
    base = {"reasons": [], "changed_inputs": [], "dependencies_match": False, "exact_baseline": False}
    if original_requirement is None:
        return {**base, "status": "unmapped", "reasons": ["The CSV row did not map to a requirement in its recorded baseline; a later requirement with that ID does not remap the original row."]}
    if requirement is None:
        return {**base, "status": "requirement_removed", "reasons": ["The recorded requirement is absent from the selected configuration. Its original outcomes are retained as historical evidence."]}
    old_model, old_inputs = _dependencies(original["project"], original_requirement)
    model, inputs = _dependencies(selected, requirement)
    changed = sorted(key for key in set(old_inputs) | set(inputs) if old_inputs.get(key) != inputs.get(key))
    reasons = []
    if original_requirement != requirement:
        reasons.append("The requirement definition changed, including its metric, criterion binding, operator, title or criticality; review the original test's applicability.")
    if old_model != model:
        reasons.append("The explicitly bound model definition changed.")
    if ((old_model.get("links") or model.get("links"))
            and chains.dependency_configuration(original["project"], old_model["id"])
                != chains.dependency_configuration(selected, model["id"])):
        reasons.append("The explicit calculation chain's upstream model definitions, transfer rationales or input records changed; review the original test's applicability even if the calculated number is unchanged.")
    if changed:
        reasons.append("Bound model or criterion input records changed: " + ", ".join(changed) + ".")
    source_current = receipt["sources"] == _comparison_sources(sources)
    if not source_current:
        reasons.append("The recorded comparison or verification source fingerprints differ from the current implementation.")
    expected_version = workspace.MODEL_VERSIONS.get(model["type"])
    recorded_version = original["evidence"][old_model["id"]]["model_version"]
    if recorded_version != expected_version:
        reasons.append("The relevant adapter version differs from the recorded baseline.")
    matching = not reasons
    # A newer canonical record with identical inputs can still contain changed
    # predictions, limitations or findings. Never infer sameness from inputs alone.
    current_review = view["run"]["review"] if view["run"] else None
    if matching and current_review:
        current_requirement = _requirements(current_review["project"]).get(requirement["id"])
        if current_requirement == requirement:
            old_evidence = original["evidence"][old_model["id"]]
            new_evidence = current_review["evidence"].get(model["id"])
            old_finding = original["findings"][original_requirement["id"]]
            new_finding = current_review["findings"].get(requirement["id"])
            if (new_evidence is None or old_evidence["fingerprint"] != new_evidence["fingerprint"]
                    or old_finding != new_finding):
                reasons.append("The current canonical result or evidence changed despite matching configuration dependencies; review the discrepancy before reusing this test.")
                matching = False
    exact = bool(matching and not draft and receipt["revision"] == view["revision"] and view["run"]
                 and receipt["baseline"]["run_id"] == view["run"]["run_id"]
                 and selected == view["project"])
    if matching:
        reasons.append("Recorded requirement, model, bound input, criterion, relevant adapter and verification source records match the selected configuration.")
        if exact:
            reasons.append("This comparison is bound to the exact selected current canonical run; its supplied conditions declaration remains unverified.")
        else:
            reasons.append("The comparison belongs to a different revision or run, or a draft context. Matching dependencies do not independently verify historical test applicability.")
        if not current_review:
            reasons.append("The selected revision has no current canonical review; no current prediction is inferred.")
    return {"status": "exact_baseline" if exact else "same_dependencies" if matching else "needs_review",
            "reasons": reasons, "changed_inputs": changed, "dependencies_match": matching, "exact_baseline": exact}


def validate_investigation_context(bundle, view, requirement_id):
    """Validate a helper-created frozen bundle against the selected saved view.

    This is an internal structural/binding guard, not authentication of arbitrary
    client data. The caller must obtain the bundle from ``investigation_context``
    (which verifies database receipts), never accept it from a network request.
    """
    try:
        fields = {"schema", "project_id", "revision", "requirement_id", "project_digest", "selection", "recorded",
                  "current", "applicability", "limitations", "sources", "context_digest"}
        if not isinstance(bundle, dict) or set(bundle) != fields or bundle["schema"] != CONTEXT_SCHEMA:
            raise ValueError("Invalid test-evidence investigation context schema.")
        if len(_encode(bundle).encode("utf-8")) > MAX_CONTEXT_BYTES:
            raise ValueError("Test-evidence investigation context exceeds its bounded wire size.")
        if bundle["context_digest"] != _digest({key: value for key, value in bundle.items() if key != "context_digest"}):
            raise ValueError("Frozen test-evidence context digest does not match.")
        if (bundle["project_id"] != view["project_id"] or bundle["revision"] != view["revision"]
                or type(bundle["revision"]) is not int or bundle["requirement_id"] != requirement_id
                or bundle["project_digest"] != _digest(view["project"])):
            raise ValueError("Test-evidence context does not match the selected saved configuration.")
        selection = bundle["selection"]
        if set(selection) != {"comparison_id", "row_number", "pointer", "receipt_digest", "csv_sha256"}:
            raise ValueError("Test-evidence selection is incomplete.")
        if (not isinstance(selection["comparison_id"], str) or re.fullmatch(r"[a-f0-9]{32}", selection["comparison_id"]) is None
                or type(selection["row_number"]) is not int or not 2 <= selection["row_number"] <= 201
                or selection["pointer"] != "/row_results/" + str(selection["row_number"] - 2)
                or any(not isinstance(selection[key], str) or re.fullmatch(r"[a-f0-9]{64}", selection[key]) is None
                       for key in ("receipt_digest", "csv_sha256"))):
            raise ValueError("Test-evidence selection contains an invalid identity, pointer or digest.")
        recorded = bundle["recorded"]
        required_recorded = {"row", "requirement", "finding", "model", "criterion_input", "baseline_run_id", "baseline_review_digest",
                             "baseline_run_digest", "tested_revision", "name", "data_kind", "source", "filename", "test_conditions",
                             "conditions_match", "conditions_declaration_verified", "sources"}
        if not isinstance(recorded, dict) or set(recorded) != required_recorded:
            raise ValueError("The frozen recorded test bundle has unsupported fields.")
        if (recorded["row"]["requirement_id"] != requirement_id or recorded["row"]["row_number"] != selection["row_number"]
                or recorded["requirement"]["id"] != requirement_id
                or recorded["row"]["model_id"] != recorded["requirement"]["model_id"]
                or recorded["model"]["definition"]["id"] != recorded["requirement"]["model_id"]
                or recorded["conditions_declaration_verified"] is not False
                or recorded["conditions_match"] != recorded["row"]["conditions"]["declared_relation"]
                or recorded["test_conditions"] != recorded["row"]["conditions"]["description"]
                or type(recorded["tested_revision"]) is not int or not 1 <= recorded["tested_revision"] <= view["revision"]):
            raise ValueError("The frozen test row does not match its selected requirement and conditions.")
        current = _current(view)
        requirement = _requirements(view["project"]).get(requirement_id)
        expected = {"run_id": current["run_id"], "review_digest": current["review_digest"],
                    "requirement": requirement,
                    "finding": deepcopy(current["review"]["findings"].get(requirement_id)) if current["review"] else None,
                    "model": _compact_model(view["project"], requirement, current["review"]),
                    "criterion_input": deepcopy(view["project"]["inputs"][requirement["limit_input"]]) if requirement else None}
        if _encode(bundle["current"]) != _encode(expected):
            raise ValueError("The frozen test context's current canonical evidence has changed.")
        # Rebuild the selected row arithmetic and applicability from its compact
        # frozen records, without rerunning an adapter or reading other rows.
        from .workspace_test_data import _row_results
        row, original_model = recorded["row"], recorded["model"]
        original_requirement = recorded["requirement"]
        original_inputs = deepcopy(original_model["input_records"])
        original_inputs[original_requirement["limit_input"]] = deepcopy(recorded["criterion_input"])
        original_project = {"inputs": original_inputs, "models": [original_model["definition"]],
                            "requirements": [original_requirement]}
        if original_model["definition"].get("links"):
            configuration = original_model["calculation_dependencies"]
            if not isinstance(configuration, dict) or set(configuration) != {"models", "input_records"}:
                raise ValueError("The frozen calculation dependency configuration is incomplete.")
            original_project["models"] = list(deepcopy(configuration["models"]).values())
            chains.ordered_models(original_project)
            if (configuration != chains.dependency_configuration(original_project, original_model["definition"]["id"])
                    or configuration["input_records"] != original_model["input_records"]
                    or configuration["models"].get(original_model["definition"]["id"]) != original_model["definition"]):
                raise ValueError("The frozen calculation dependency records do not match their model and input bindings.")
        elif "calculation_dependencies" in original_model:
            raise ValueError("An unlinked original model cannot claim calculation dependencies.")
        original_finding = recorded["finding"]
        verifier_names = set(workspace._LOADED_VERIFICATION_SOURCES)
        recorded_verifier_names = set(lifecycle._validate_sources(original_model["verification_sources"]))
        if (set(bundle["sources"]) != verifier_names | {"workspace_test_data.py", "test_evidence.py"}
                or set(recorded["sources"]) != recorded_verifier_names | {"workspace_test_data.py"}
                or any(not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None
                       for value in [*bundle["sources"].values(), *recorded["sources"].values()])
                or original_model["verification_sources"] != {key: recorded["sources"][key] for key in recorded_verifier_names}
                or not isinstance(original_model["evidence_fingerprint"], str)
                or re.fullmatch(r"[a-f0-9]{64}", original_model["evidence_fingerprint"]) is None):
            raise ValueError("The scoped evidence source fingerprints are incomplete or inconsistent.")
        if current["review"] and {key: bundle["sources"][key] for key in verifier_names} != current["review"]["verification_sources"]:
            raise ValueError("The context sources do not match the selected current verifier sources.")
        dependency = {"model_definition": original_model["definition"], "input_records": original_inputs,
                      "model_version": original_model["adapter_version"], "requirement": original_requirement,
                      "verification_sources": original_model["verification_sources"]}
        if original_model["definition"].get("links"):
            dependency["calculation_dependencies"] = chains.dependency_configuration(original_project, original_model["definition"]["id"])
        if (original_finding["dependency_fingerprint"] != _digest(dependency)
                or original_finding["requirement_id"] != requirement_id
                or original_finding["model_id"] != original_requirement["model_id"]
                or original_finding["metric"] != original_requirement["metric"]
                or original_finding["critical"] != original_requirement["critical"]
                or original_finding["dependencies"] != {"model_id": original_requirement["model_id"], "input_ids": sorted(original_inputs)}):
            raise ValueError("The original finding dependency binding is inconsistent.")
        from .engineering import evidence_accuracy_gap, requirement_accuracy_gap
        retained_result = {"model_type": original_model["definition"]["type"],
                           "model_version": original_model["adapter_version"],
                           "status": original_model["status"],
                           "metrics": {original_requirement["metric"]: original_model["selected_metric"]}
                                      if original_model["selected_metric"] is not None else {},
                           **{key: original_model[key] for key in ("numerical_accuracy", "flight_response") if key in original_model}}
        accuracy_gap = evidence_accuracy_gap(retained_result)
        if accuracy_gap is None and original_model["selected_metric"] is not None:
            accuracy_gap = requirement_accuracy_gap(retained_result, original_requirement,
                                                    original_model["selected_metric"], recorded["criterion_input"])
        expected_measured = ({"metric": original_model["selected_metric"], "operator": original_requirement["operator"],
                              "limit": recorded["criterion_input"]} if original_model["selected_metric"] is not None
                             and original_model["status"] == "completed"
                             and not accuracy_gap
                             and original_model["selected_metric"]["unit"] == recorded["criterion_input"]["unit"] else None)
        if original_finding["evidence"] != expected_measured:
            raise ValueError("The frozen original finding disagrees with its metric and criterion records.")
        metric, tolerance = row["measurement_requirement"]["metric"], row["prediction_agreement"]["tolerance"]
        parsed_row = {"row_number": row["row_number"], "measurement_id": row["measurement_id"],
                      "requirement_id": row["requirement_id"], "value": metric["value"] if metric else None,
                      "unit": metric["unit"] if metric else tolerance["unit"] if tolerance else "",
                      "tolerance": tolerance["value"] if tolerance else None, "issues": deepcopy(row["issues"])}
        original_review = {"project": original_project, "findings": {requirement_id: original_finding},
                           "evidence": {original_requirement["model_id"]: {"model_version": original_model["adapter_version"],
                                                                        "fingerprint": original_model["evidence_fingerprint"]}}}
        if _encode(_row_results({"test_conditions": recorded["test_conditions"], "conditions_match": recorded["conditions_match"]},
                               {"rows": [parsed_row]}, original_review)[0]) != _encode(row):
            raise ValueError("The frozen original row does not match its recorded scalar arithmetic.")
        frozen_receipt = {"baseline": {"review": original_review, "run_id": recorded["baseline_run_id"]},
                          "revision": recorded["tested_revision"], "sources": recorded["sources"]}
        if _encode(bundle["applicability"]) != _encode(_applicability(frozen_receipt, row, view, view["project"], bundle["sources"])):
            raise ValueError("The frozen applicability label disagrees with its explicit dependencies.")
        if bundle["limitations"] != LIMITATIONS:
            raise ValueError("Test-evidence context disclosures do not match.")
        if set(bundle["applicability"]) != {"status", "reasons", "changed_inputs", "dependencies_match", "exact_baseline"}:
            raise ValueError("Test-evidence applicability record has unsupported fields.")
        if bundle["applicability"]["status"] not in {"exact_baseline", "same_dependencies", "needs_review", "requirement_removed"}:
            raise ValueError("Unmapped rows cannot be investigated as a mapped requirement.")
        return True
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise WorkspaceError("Invalid test-evidence investigation context: " + str(exc)) from exc


class TestEvidence:
    def __init__(self, store, test_data):
        if test_data.store is not store:
            raise WorkspaceError("Test evidence and comparisons must use the same workspace store.")
        self.store, self.test_data = store, test_data

    @contextmanager
    def _snapshot(self, project_id, revision, project=None):
        revision = _revision(revision)
        sources, versions = _sources(), deepcopy(workspace.MODEL_VERSIONS)
        with self.store._connect() as connection:
            connection.execute("BEGIN")
            view = self.store._view(connection, project_id, revision)
            selected = view["project"]
            if project is not None:
                try:
                    selected = lifecycle.validate_project(project, allow_empty=True)
                except (ValueError, TypeError, OverflowError) as exc:
                    raise WorkspaceError("Invalid test-evidence draft: " + str(exc)) from exc
                if selected["project_id"] != project_id or selected["revision"] not in {str(revision), str(revision + 1)}:
                    raise WorkspaceError("The draft must belong to the selected project and base revision.")
            yield connection, view, selected, sources
            if sources != _sources() or versions != workspace.MODEL_VERSIONS:
                raise ConflictError("Evidence-link sources or adapter versions changed during this read. Refresh the saved context.")

    def _rows(self, connection, project_id, revision):
        rows = connection.execute("SELECT * FROM test_comparisons WHERE project_id=? AND revision<=? ORDER BY sequence DESC LIMIT ?",
                                  (project_id, revision, HISTORY_LIMIT + 1)).fetchall()
        return [(row, self.test_data._read(connection, row)) for row in rows[:HISTORY_LIMIT]], len(rows) > HISTORY_LIMIT

    def _summary(self, view, selected, receipts, truncated, sources, *, draft):
        comparisons = []
        counts = dict.fromkeys(("rows", "current", "historical", "discrepancies", "unassessed", "needs_review"), 0)
        for record, receipt in receipts:
            rows = []
            for original in receipt["row_results"]:
                row = deepcopy(original)
                row["applicability"] = _applicability(receipt, original, view, selected, sources, draft=draft)
                rows.append(row)
                counts["rows"] += 1
                counts["current" if row["applicability"]["exact_baseline"] else "historical"] += 1
                counts["discrepancies"] += int(row["prediction_agreement"]["status"] == "outside_tolerance")
                counts["unassessed"] += int(row["measurement_requirement"]["status"] == "not_assessed" or row["prediction_agreement"]["status"] == "not_assessed")
                counts["needs_review"] += int(row["applicability"]["status"] in {"needs_review", "requirement_removed", "unmapped"})
            spec = receipt["spec"]
            comparisons.append({"comparison_id": receipt["comparison_id"], "receipt_digest": record["digest"],
                                "tested_revision": receipt["revision"], "created_at": receipt["created_at"],
                                **{key: spec[key] for key in ("name", "data_kind", "source", "filename", "test_conditions", "conditions_match")},
                                "csv_sha256": receipt["preview"]["csv_sha256"],
                                "baseline_run_id": receipt["baseline"]["run_id"],
                                "baseline_review_digest": receipt["baseline"]["review"]["digest"],
                                "source_current": receipt["sources"] == _comparison_sources(sources), "rows": rows})
        return {"schema": SCHEMA, "project_id": view["project_id"], "revision": view["revision"],
                "project_digest": _digest(selected), "current_run_id": view["run"]["run_id"] if view["run"] else None,
                "current_review_digest": view["run"]["review"]["digest"] if view["run"] else None,
                "context": "draft" if draft else "saved", "comparisons": comparisons, "counts": counts,
                "count_definitions": {"current": "Rows bound to the exact selected current canonical run; physical test applicability remains unverified.",
                                      "historical": "Rows that are not bound to the exact selected current canonical run.",
                                      "discrepancies": "Recorded prediction agreement is outside the supplied absolute tolerance.",
                                      "unassessed": "Either recorded measurement criterion or prediction agreement is unassessed.",
                                      "needs_review": "Changed dependencies/sources/results, removed requirements or originally unmapped rows."},
                "history_limit": HISTORY_LIMIT, "history_truncated": truncated,
                "limitations": deepcopy(LIMITATIONS), "sources": deepcopy(sources)}

    def summary(self, project_id, revision, project=None):
        with self._snapshot(project_id, revision, project) as (connection, view, selected, sources):
            receipts, truncated = self._rows(connection, project_id, revision)
            return self._summary(view, selected, receipts, truncated, sources, draft=project is not None)

    def investigation_context(self, project_id, revision, requirement_id, comparison_id, row_number):
        if not isinstance(requirement_id, str) or not requirement_id.strip():
            raise WorkspaceError("Select a requirement for the recorded test investigation.")
        if not isinstance(comparison_id, str) or re.fullmatch(r"[a-f0-9]{32}", comparison_id) is None:
            raise WorkspaceError("Invalid test comparison ID.")
        if type(row_number) is not int or not 2 <= row_number <= 201:
            raise WorkspaceError("Select an exact CSV data row number from 2 through 201.")
        with self._snapshot(project_id, revision) as (connection, view, selected, sources):
            record = connection.execute("SELECT * FROM test_comparisons WHERE comparison_id=? AND project_id=? AND revision<=?",
                                        (comparison_id, project_id, revision)).fetchone()
            if record is None:
                raise WorkspaceError("The selected comparison is not available in this project revision.")
            receipt = self.test_data._read(connection, record)
            original = next((row for row in receipt["row_results"] if row["row_number"] == row_number), None)
            baseline = receipt["baseline"]["review"]
            requirement = _requirements(baseline["project"]).get(requirement_id)
            if original is None or original["requirement_id"] != requirement_id or requirement is None:
                raise WorkspaceError("The selected test row does not map to this requirement in its recorded baseline.")
            current = _current(view)
            selected_requirement = _requirements(selected).get(requirement_id)
            spec = receipt["spec"]
            bundle = {"schema": CONTEXT_SCHEMA, "project_id": project_id, "revision": revision, "requirement_id": requirement_id,
                      "project_digest": _digest(selected),
                      "selection": {"comparison_id": comparison_id, "row_number": row_number,
                                    "pointer": "/row_results/" + str(receipt["row_results"].index(original)),
                                    "receipt_digest": record["digest"], "csv_sha256": receipt["preview"]["csv_sha256"]},
                      "recorded": {"row": deepcopy(original), "requirement": deepcopy(requirement),
                                   "finding": deepcopy(baseline["findings"][requirement_id]),
                                   "model": _compact_model(baseline["project"], requirement, baseline),
                                   "criterion_input": deepcopy(baseline["project"]["inputs"][requirement["limit_input"]]),
                                   "baseline_run_id": receipt["baseline"]["run_id"], "baseline_review_digest": baseline["digest"],
                                   "baseline_run_digest": receipt["baseline"]["run_digest"], "tested_revision": receipt["revision"],
                                   **{key: spec[key] for key in ("name", "data_kind", "source", "filename", "test_conditions", "conditions_match")},
                                   "conditions_declaration_verified": False, "sources": deepcopy(receipt["sources"])},
                      "current": {"run_id": current["run_id"], "review_digest": current["review_digest"],
                                  "requirement": deepcopy(selected_requirement),
                                  "finding": deepcopy(current["review"]["findings"].get(requirement_id)) if current["review"] else None,
                                  "model": _compact_model(selected, selected_requirement, current["review"]),
                                  "criterion_input": deepcopy(selected["inputs"][selected_requirement["limit_input"]]) if selected_requirement else None},
                      "applicability": _applicability(receipt, original, view, selected, sources),
                      "limitations": deepcopy(LIMITATIONS), "sources": deepcopy(sources)}
            bundle["context_digest"] = _digest(bundle)
            validate_investigation_context(bundle, view, requirement_id)
            return bundle

    def review_export(self, project_id, revision, *, source_library=None, action_queue=None, coverage=None, simulation_imports=None, operating_envelopes=None):
        with self._snapshot(project_id, revision) as (connection, view, selected, sources):
            receipts, truncated = self._rows(connection, project_id, revision)
            summary = self._summary(view, selected, receipts, truncated, sources, draft=False)
            original_files = [{"comparison_id": receipt["comparison_id"], "receipt_digest": record["digest"],
                               "csv_sha256": receipt["preview"]["csv_sha256"], "tested_revision": receipt["revision"],
                               "baseline_run_id": receipt["baseline"]["run_id"],
                               "baseline_review_digest": receipt["baseline"]["review"]["digest"],
                               **{key: deepcopy(receipt["spec"][key]) for key in ("name", "filename", "csv_text", "mapping", "source", "data_kind", "test_conditions", "conditions_match")},
                               "conditions_declaration_verified": False, "sources": deepcopy(receipt["sources"]),
                               "limitations": deepcopy(receipt["limitations"])} for record, receipt in receipts]
            result = {"schema": EXPORT_SCHEMA, "project_id": project_id, "revision": revision,
                      "project_digest": _digest(selected), "workspace": deepcopy(view), "test_evidence": summary,
                      "original_test_sources": original_files, "history_limit": HISTORY_LIMIT,
                      "history_truncated": truncated, "launch_authorization": False, "live_model_calls": 0,
                      "execution": "read_only_recorded_engineering_and_test_evidence", "limitations": deepcopy(LIMITATIONS),
                      "sources": deepcopy(sources)}
            if source_library is not None:
                result["project_sources"] = source_library.summary_in_snapshot(connection, view)
                result["limitations"].append("Project source references are supplemental user-supplied annotations captured with this export; links and manual review do not alter the original engineering findings or establish source accuracy.")
            if action_queue is not None:
                result["engineering_actions"] = action_queue.summary_in_snapshot(connection, view)
                result["limitations"].append("Engineering actions are supplemental workflow records. Closing an action does not change a numerical finding or establish that engineering completion criteria have been verified.")
            if coverage is not None:
                result["engineering_coverage"] = coverage.summary_in_snapshot(connection, view)
                result["limitations"].append("Engineering coverage records user-declared scope and model applicability alongside original findings. A met criterion or declared fit is not whole-mission verification.")
            if simulation_imports is not None:
                result["simulation_imports"] = simulation_imports.snapshot(connection, view)
                result["limitations"].append("Imported time histories and declared conditions are supplemental recorded evidence; comparison agreement does not change canonical requirement findings or verify physical validity.")
            if operating_envelopes is not None:
                result["operating_envelopes"] = operating_envelopes.envelope_snapshot(connection, view)
                result["limitations"].append("Operating-envelope studies report only sampled combinations against fixed criteria. Worst observed margins do not bound unsampled conditions or establish a continuous safe operating range.")
            result["export_digest"] = _digest(result)
            if len(_encode(result).encode("utf-8")) > MAX_EXPORT_BYTES:
                raise WorkspaceError("The combined review exceeds its 64 MiB export bound. Export individual comparisons instead.")
            return result
