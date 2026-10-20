"""Recorded scalar measurements compared with a frozen canonical review.

CSV contents are untrusted data, never expressions or calculation instructions.
This module evaluates recorded numbers and declared comparisons only: it does
not execute adapters, authenticate a test, or change the canonical review.
"""
from collections import Counter
from copy import deepcopy
import csv
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import re
import threading
from uuid import uuid4

from . import workspace
from .project_io import _reject_constant, _unique_object
from .workspace import ConflictError, WorkspaceError, _digest, _encode, _now, _revision

SCHEMA = "sixd.test-comparison.v1"
PREVIEW_SCHEMA = "sixd.test-data-preview.v1"
SPEC_SCHEMA = "sixd.test-comparison-spec.v1"
MAPPING_FIELDS = ("measurement_id", "requirement_id", "value", "unit", "tolerance")
MAX_CSV_BYTES, MAX_ROWS, MAX_COLUMNS, MAX_FIELD = 1024 * 1024, 200, 32, 4096
MAX_RECEIPT_BYTES = 32 * 1024 * 1024
MAX_SAFE_INTEGER = 2**53 - 1
_NUMERIC = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
LIMITATIONS = [
    "Imported records are supplied test data; authenticity, calibration, uncertainty and test execution are not verified.",
    "Matching conditions are an unverified user declaration covering the same observable, aggregation and model conditions; no independent applicability assessment is performed.",
    "Measured criterion satisfaction and prediction agreement are separate findings; neither changes the canonical project review.",
    "Only mapped scalar values in exact matching units are compared; no conversion, interpolation or time-series alignment is performed.",
    "Agreement uses each row's explicit nonnegative absolute tolerance; exact requirement targets retain exact equality with no inferred tolerance.",
    "CSV formulas are retained as text and never evaluated. Decimal/scientific values use finite binary floating-point JSON numbers, not arbitrary decimal precision; the exact original CSV is retained.",
    "Integer tokens outside the browser's exact safe-integer range are quality gaps. Unsafe integer prediction or criterion records cannot support a displayed comparison.",
    "A discrepancy is evidence for investigation, not proof of a particular physical defect or model validity.",
    "Transient observations are not automatically steady-state equilibrium measurements, and instantaneous orbital positions are not sampled-window extrema; the supplied metric definition and conditions must correspond.",
    "No physical validation, whole-mission readiness, certification or launch approval is established by importing data.",
    "Record digests are unsigned consistency checks, not authenticated approval or proof of truth.",
]


def _sources():
    return {**workspace._sources(), "workspace_test_data.py": sha256(Path(__file__).read_bytes()).hexdigest()}


_LOADED_SOURCES = _sources()


def _text(value, label, maximum, *, empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise WorkspaceError(f"{label} requires {'text' if empty else 'nonempty text'} up to {maximum} characters.")
    return value.strip()


def _csv_text(value):
    if not isinstance(value, str):
        raise WorkspaceError("Supply CSV contents as UTF-8 text.")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise WorkspaceError("CSV contents must be valid UTF-8 text.") from exc
    if not encoded or len(encoded) > MAX_CSV_BYTES:
        raise WorkspaceError("Supply a nonempty CSV no larger than 1 MiB.")
    if "\x00" in value:
        raise WorkspaceError("CSV contents cannot contain NUL characters.")
    return encoded


def _mapping(value, columns):
    if value == {}:
        value = dict.fromkeys(MAPPING_FIELDS, "")
    if not isinstance(value, dict) or set(value) != set(MAPPING_FIELDS):
        raise WorkspaceError("Mapping requires exactly measurement_id, requirement_id, value, unit and tolerance columns.")
    if any(not isinstance(column, str) or (column and column not in columns) for column in value.values()):
        raise WorkspaceError("Each mapped field must be an existing CSV column name or an empty string.")
    selected = [column for column in value.values() if column]
    if len(selected) != len(set(selected)):
        raise WorkspaceError("Map each CSV column to at most one measurement field.")
    return {field: value[field] for field in MAPPING_FIELDS}


def _numeric(text):
    """Return a finite number without interpreting expressions or missing data."""
    if not text or _NUMERIC.fullmatch(text) is None:
        return None
    try:
        value = int(text) if not any(c in text.lower() for c in ".e") else float(text)
        if _unsafe_integer(value):
            return None
        if not math.isfinite(value):
            return None
        # Do not silently relabel a nonzero measurement as zero after underflow.
        if value == 0 and Decimal(text) != 0:
            return None
        return value
    except (ValueError, OverflowError, InvalidOperation):
        return None


def _unsafe_integer(value):
    return type(value) is int and abs(value) > MAX_SAFE_INTEGER


def _integer_precision_issue(text):
    """Identify oversized integer tokens without rounding them for display."""
    if text and _NUMERIC.fullmatch(text) and not any(c in text.lower() for c in ".e"):
        try:
            return _unsafe_integer(int(text))
        except (ValueError, OverflowError):
            return True
    return False


def preview(filename, csv_text, mapping):
    """Parse bounded CSV and retain row quality gaps without default values."""
    filename = _text(filename, "CSV filename", 240)
    encoded = _csv_text(csv_text)
    parsed = []
    try:
        reader = csv.reader(io.StringIO(csv_text.removeprefix("\ufeff"), newline=""), strict=True)
        for row in reader:
            if len(row) > MAX_COLUMNS or any(len(field) > MAX_FIELD for field in row):
                raise WorkspaceError("CSV supports at most 32 columns and 4096 characters per field.")
            parsed.append(row)
            if len(parsed) > MAX_ROWS + 1:
                raise WorkspaceError("CSV supports at most 200 data rows.")
    except csv.Error as exc:
        raise WorkspaceError("Malformed CSV: " + str(exc)) from exc
    if len(parsed) < 2:
        raise WorkspaceError("CSV requires a header and at least one data row.")
    columns = parsed[0]
    if (not columns or any(not column.strip() or len(column) > 128 for column in columns)
            or len({column.strip() for column in columns}) != len(columns)):
        raise WorkspaceError("CSV headers must be nonempty, distinct names up to 128 characters.")
    if any(len(row) != len(columns) for row in parsed[1:]):
        raise WorkspaceError("Malformed CSV: every data row must have exactly the header's number of columns.")
    mapping = _mapping(mapping, columns)
    raw = [dict(zip(columns, row)) for row in parsed[1:]]
    rows = []
    for index, record in enumerate(raw, 2):
        row = {"row_number": index, "measurement_id": "", "requirement_id": "", "value": None,
               "unit": "", "tolerance": None, "issues": []}
        for field in MAPPING_FIELDS:
            column = mapping[field]
            text = record[column].strip() if column else ""
            issue = None
            if not column:
                issue = "No CSV column was mapped to this field."
            elif not text:
                issue = "A value is required; no default is inferred."
            elif field in {"value", "tolerance"}:
                number = _numeric(text)
                if number is None:
                    issue = ("Integer exceeds the browser's exact safe-integer range; this field remains unassessed and the original CSV is retained."
                             if _integer_precision_issue(text) else
                             "Use a finite decimal or scientific number without expressions or units.")
                elif field == "tolerance" and number < 0:
                    issue = "Absolute comparison tolerance must be nonnegative."
                else:
                    row[field] = number
            else:
                row[field] = text
                maximum = 80 if field == "unit" else 120
                if len(text) > maximum:
                    issue = f"Use at most {maximum} characters."
            if issue:
                row["issues"].append({"field": field, "message": issue})
        rows.append(row)
    counts = Counter(row["measurement_id"] for row in rows if row["measurement_id"])
    for row in rows:
        if row["measurement_id"] and counts[row["measurement_id"]] > 1:
            row["issues"].append({"field": "measurement_id", "message": "Measurement ID is duplicated in this CSV; all matching rows remain unassessed."})
    return {"schema": PREVIEW_SCHEMA, "filename": filename, "csv_sha256": sha256(encoded).hexdigest(),
            "columns": columns, "mapping": mapping, "raw_preview": raw[:10], "row_count": len(rows), "rows": rows}


def validate_spec(spec):
    fields = {"schema", "name", "source", "data_kind", "test_conditions", "conditions_match", "filename", "csv_text", "mapping"}
    if not isinstance(spec, dict) or set(spec) != fields or spec.get("schema") != SPEC_SCHEMA:
        raise WorkspaceError("Supply exactly the fields in a sixd.test-comparison-spec.v1 specification.")
    if spec["data_kind"] not in ("measured", "synthetic") or spec["conditions_match"] not in ("declared_match", "different", "unknown"):
        raise WorkspaceError("Choose measured or synthetic data and declared_match, different or unknown conditions.")
    result = deepcopy(spec)
    result["name"] = _text(spec["name"], "Comparison name", 120)
    result["source"] = _text(spec["source"], "Test-data source", 1200)
    result["test_conditions"] = _text(spec["test_conditions"], "Test conditions", 2400, empty=True)
    parsed = preview(spec["filename"], spec["csv_text"], spec["mapping"])
    result["filename"], result["mapping"] = parsed["filename"], parsed["mapping"]
    return result, parsed


def _difference(value, prediction):
    try:
        # All displayed differences share the browser's binary floating-point
        # representation. Unsafe integer operands are blocked before this call.
        result = float(value) - float(prediction)
        return result if math.isfinite(result) else None
    except OverflowError:
        return None


def _row_results(spec, parsed, review):
    requirements = {r["id"]: r for r in review["project"]["requirements"]}
    results = []
    for row in parsed["rows"]:
        requirement = requirements.get(row["requirement_id"])
        finding = review["findings"].get(row["requirement_id"])
        evidence = finding["evidence"] if finding else None
        measurement = {"value": row["value"], "unit": row["unit"]} if row["value"] is not None and row["unit"] else None
        unsafe_prediction = bool(evidence and _unsafe_integer(evidence["metric"]["value"]))
        unsafe_limit = bool(evidence and _unsafe_integer(evidence["limit"]["value"]))
        prediction = deepcopy(evidence["metric"]) if evidence and not unsafe_prediction else None
        limit = deepcopy(evidence["limit"]) if evidence and not unsafe_limit else None
        operator = requirement["operator"] if requirement else None
        tolerance = {"value": row["tolerance"], "unit": row["unit"]} if row["tolerance"] is not None and row["unit"] else None
        criterion = {"status": "not_assessed", "reason": "", "metric": measurement, "operator": operator, "limit": limit}
        agreement = {"status": "not_assessed", "reason": "", "prediction": prediction,
                     "signed_difference": None, "absolute_difference": None, "tolerance": tolerance}
        required_issues = [issue for issue in row["issues"] if issue["field"] != "tolerance"]
        common_gap = (
            "Measurement identity, requirement, value or unit is missing or invalid; resolve this row's quality gaps." if required_issues else
            "The mapped requirement does not exist in the frozen baseline revision." if requirement is None else
            "The frozen baseline has no assessed supported prediction/criterion for this requirement; the imported row cannot close that coverage gap." if not evidence else
            "The frozen prediction or criterion contains an integer outside the browser's exact safe-integer range; both comparisons remain unassessed and unsafe numerical comparison records are omitted." if unsafe_prediction or unsafe_limit else
            "Record the test conditions before comparing measurements with this requirement and prediction." if not spec["test_conditions"] else
            "The test conditions are different or unknown; matching applicability has not been declared." if spec["conditions_match"] != "declared_match" else
            "Measurement, prediction and criterion units must match exactly; no implicit conversion is permitted." if row["unit"] != prediction["unit"] or row["unit"] != limit["unit"] else "")
        if common_gap:
            criterion["reason"] = agreement["reason"] = common_gap
        else:
            value, threshold = row["value"], limit["value"]
            passes = {"<=": value <= threshold, ">=": value >= threshold, "==": value == threshold}[operator]
            criterion.update(status="met" if passes else "not_met",
                             reason="Recorded measurement meets the declared criterion under the supplied conditions declaration." if passes else
                                    "Recorded measurement violates the declared criterion under the supplied conditions declaration.")
            if row["tolerance"] is None:
                agreement["reason"] = "Prediction agreement requires this row's explicit nonnegative absolute tolerance; none is inferred."
            else:
                difference = _difference(value, prediction["value"])
                absolute = abs(difference) if difference is not None else None
                # Finite operands with overflowing subtraction differ by more
                # than every permitted finite tolerance. Do not emit infinity.
                within = difference is not None and absolute <= row["tolerance"]
                agreement.update(status="within_tolerance" if within else "outside_tolerance",
                                 signed_difference=difference, absolute_difference=absolute,
                                 reason=("Recorded measurement differs from the saved prediction by no more than the supplied absolute tolerance." if within else
                                         "The recorded difference exceeds the supplied absolute tolerance." if difference is not None else
                                         "The difference exceeds finite numeric range and every permitted finite tolerance; inspect the original operands."))
        next_steps = []
        if criterion["status"] == "not_assessed" or agreement["status"] == "not_assessed":
            next_steps.append("Resolve the stated data or applicability gap before drawing the corresponding conclusion.")
        if criterion["status"] == "not_met":
            next_steps.append("Review the recorded test, its calibration and applicability with the responsible engineer; investigate the exceeded criterion.")
        if agreement["status"] == "outside_tolerance":
            next_steps.append("Check units, calibration, conditions and model assumptions before attributing the discrepancy to a particular defect.")
        if not next_steps:
            next_steps.append("Retain the original test record and review provenance, calibration, model applicability and excluded effects before relying on this comparison.")
        results.append({"row_number": row["row_number"], "measurement_id": row["measurement_id"],
                        "requirement_id": row["requirement_id"], "title": requirement["title"] if requirement else "Unknown requirement",
                        "model_id": requirement["model_id"] if requirement else None,
                        "metric": requirement["metric"] if requirement else None,
                        "canonical_status": finding["status"] if finding else "not_assessed",
                        "issues": deepcopy(row["issues"]), "measurement_requirement": criterion,
                        "prediction_agreement": agreement, "next_steps": next_steps,
                        "conditions": {"description": spec["test_conditions"], "declared_relation": spec["conditions_match"], "verified": False}})
    return results


class WorkspaceTestData:
    def __init__(self, store):
        self.store, self._lock = store, threading.Lock()
        with store._connect(write=True) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS test_comparisons (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, comparison_id TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                receipt TEXT NOT NULL, digest TEXT NOT NULL,
                FOREIGN KEY(project_id,revision) REFERENCES revisions(project_id,revision))""")
            connection.execute("CREATE INDEX IF NOT EXISTS tests_project_revision ON test_comparisons(project_id,revision,sequence)")

    @staticmethod
    def preview(filename, csv_text, mapping):
        return preview(filename, csv_text, mapping)

    def _baseline(self, connection, run_id):
        row = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise WorkspaceError("The test-comparison baseline run is missing.")
        baseline = self.store._receipt(row)
        snapshot = connection.execute("SELECT * FROM revisions WHERE project_id=? AND revision=?",
                                      (baseline["project_id"], baseline["revision"])).fetchone()
        if snapshot is None or self.store._project(snapshot) != baseline["review"]["project"]:
            raise WorkspaceError("The test-comparison baseline does not match its saved revision.")
        return baseline

    def run(self, project_id, revision, baseline_run_id, spec):
        _revision(revision)
        if not isinstance(baseline_run_id, str) or re.fullmatch(r"[a-f0-9]{32}", baseline_run_id) is None:
            raise WorkspaceError("Choose a saved baseline run ID.")
        if not self._lock.acquire(blocking=False):
            raise ConflictError("A test-data comparison is already being saved. Wait for it to finish.")
        try:
            workspace._require_current_runtime()
            if _sources() != _LOADED_SOURCES:
                raise ConflictError("Test-data comparison code changed; restart 6D before saving a comparison.")
            view = self.store.get(project_id, revision)
            if not view["run"] or view["run"]["run_id"] != baseline_run_id:
                raise ConflictError("Run baseline checks for this saved revision and select its current run before saving a test comparison.")
            with self.store._connect() as connection:
                baseline = self._baseline(connection, baseline_run_id)
            normalized, parsed = validate_spec(spec)
            identity, stamp = uuid4().hex, _now()
            receipt = {"schema": SCHEMA, "comparison_id": identity, "project_id": project_id, "revision": revision,
                       "created_at": stamp, "spec": normalized, "preview": parsed,
                       "baseline": {"run_id": baseline_run_id, "run_digest": _digest(baseline), "review": deepcopy(baseline["review"])},
                       "row_results": _row_results(normalized, parsed, baseline["review"]), "sources": deepcopy(_LOADED_SOURCES),
                       "limitations": deepcopy(LIMITATIONS), "live_model_calls": 0, "execution": "local_recorded_test_comparison"}
            encoded = _encode(receipt)
            if len(encoded.encode("utf-8")) > MAX_RECEIPT_BYTES:
                raise WorkspaceError("The comparison exceeds its 32 MiB receipt limit; use a smaller test record.")
            with self.store._connect(write=True) as connection:
                selected = self.store._view(connection, project_id, revision)["run"]
                if (not selected or selected["run_id"] != baseline_run_id or _sources() != _LOADED_SOURCES
                        or _digest(self._baseline(connection, baseline_run_id)) != receipt["baseline"]["run_digest"]):
                    raise ConflictError("The baseline or comparison sources changed; no test comparison was saved.")
                row = {"comparison_id": identity, "project_id": project_id, "revision": revision,
                       "created_at": stamp, "receipt": encoded, "digest": _digest(receipt)}
                self._read(connection, row)
                connection.execute("INSERT INTO test_comparisons (comparison_id,project_id,revision,created_at,receipt,digest) VALUES (?,?,?,?,?,?)",
                                   (identity, project_id, revision, stamp, encoded, row["digest"]))
            return self.get(identity, revision)
        finally:
            self._lock.release()

    def _read(self, connection, row):
        try:
            receipt = json.loads(row["receipt"], object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            fields = {"schema", "comparison_id", "project_id", "revision", "created_at", "spec", "preview", "baseline",
                      "row_results", "sources", "limitations", "live_model_calls", "execution"}
            if (not isinstance(receipt, dict) or set(receipt) != fields or _digest(receipt) != row["digest"]
                    or receipt["schema"] != SCHEMA or receipt["execution"] != "local_recorded_test_comparison"
                    or type(receipt["revision"]) is not int or receipt["revision"] < 1
                    or type(receipt["live_model_calls"]) is not int or receipt["live_model_calls"] != 0
                    or receipt["limitations"] != LIMITATIONS
                    or any(receipt[key] != row[key] for key in ("comparison_id", "project_id", "revision", "created_at"))):
                raise ValueError("Comparison identity, digest or scope disclosure is inconsistent.")
            baseline = self._baseline(connection, receipt["baseline"]["run_id"])
            if (baseline["project_id"] != receipt["project_id"] or baseline["revision"] != receipt["revision"]
                    or _encode(receipt["baseline"]) != _encode({"run_id": baseline["run_id"], "run_digest": _digest(baseline), "review": baseline["review"]})):
                raise ValueError("Comparison does not match its frozen canonical baseline.")
            sources = receipt["sources"]
            if (not isinstance(sources, dict) or set(sources) != set(baseline["review"]["verification_sources"]) | {"workspace_test_data.py"}
                    or any(not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None for value in sources.values())
                    or {key: value for key, value in sources.items() if key != "workspace_test_data.py"} != baseline["review"]["verification_sources"]):
                raise ValueError("Comparison source binding is inconsistent.")
            normalized, parsed = validate_spec(receipt["spec"])
            if (_encode(normalized) != _encode(receipt["spec"]) or _encode(parsed) != _encode(receipt["preview"])
                    or _encode(_row_results(normalized, parsed, baseline["review"])) != _encode(receipt["row_results"])):
                raise ValueError("Recorded CSV, mappings or comparison findings are inconsistent.")
            return receipt
        except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
            raise WorkspaceError("Stored test comparison is inconsistent: " + str(exc)) from exc

    @staticmethod
    def _freshness(receipt, view):
        source_current = receipt["sources"] == _sources()
        selected_matches = receipt["revision"] == view["revision"]
        baseline_matches = bool(view["run"] and view["run"]["run_id"] == receipt["baseline"]["run_id"])
        return {"source_current": source_current, "selected_revision_matches": selected_matches,
                "baseline_run_matches": baseline_matches, "historical": not (source_current and selected_matches and baseline_matches),
                "context_revision": view["revision"],
                "note": "Test comparisons refer to their recorded baseline and unverified conditions declaration; they never replace the project review."}

    def get(self, identity, revision=None):
        if not isinstance(identity, str) or re.fullmatch(r"[a-f0-9]{32}", identity) is None:
            raise WorkspaceError("Invalid test comparison ID.")
        with self.store._connect() as connection:
            row = connection.execute("SELECT * FROM test_comparisons WHERE comparison_id=?", (identity,)).fetchone()
            if row is None:
                raise WorkspaceError("Test comparison not found.")
            receipt = self._read(connection, row)
            view = self.store._view(connection, receipt["project_id"], revision)
            if receipt["revision"] > view["revision"]:
                raise WorkspaceError("This test comparison belongs to a later revision than the selected context.")
            return {"receipt": receipt, "receipt_digest": row["digest"], "freshness": self._freshness(receipt, view),
                    "integrity": {"digest_valid": True, "baseline_binding_valid": True, "unsigned": True}, "current_sources": _sources()}

    def list(self, project_id, revision):
        view = self.store.get(project_id, _revision(revision))
        with self.store._connect() as connection:
            rows = connection.execute("SELECT * FROM test_comparisons WHERE project_id=? AND revision<=? ORDER BY sequence DESC LIMIT 20",
                                      (project_id, revision)).fetchall()
            comparisons = []
            for row in rows:
                receipt = self._read(connection, row)
                comparisons.append({key: receipt[key] for key in ("comparison_id", "project_id", "revision", "created_at")}
                                   | {"name": receipt["spec"]["name"], "data_kind": receipt["spec"]["data_kind"],
                                      "row_count": receipt["preview"]["row_count"], "baseline_run_id": receipt["baseline"]["run_id"],
                                      "freshness": self._freshness(receipt, view)})
        return {"project_id": project_id, "revision": revision, "comparisons": comparisons,
                "baseline_run_id": view["run"]["run_id"] if view["run"] else None,
                "limits": {"max_csv_bytes": MAX_CSV_BYTES, "max_rows": MAX_ROWS, "max_columns": MAX_COLUMNS,
                           "max_field_characters": MAX_FIELD, "history_limit": 20}, "limitations": deepcopy(LIMITATIONS)}
