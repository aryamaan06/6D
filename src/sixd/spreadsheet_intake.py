"""Bounded, read-only CSV/XLSX intake for explicit project records.

SpreadsheetML cell types/shared strings follow Microsoft's Open XML cell model:
https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.spreadsheet.cell
This importer reads literal values only. It never evaluates formulas, launches
Excel, follows a relationship over the network, or interprets formatted units.
"""
from __future__ import annotations

import base64
import binascii
import csv
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
import math
from pathlib import PurePosixPath
import posixpath
import re
import stat
import zipfile
import zlib
from xml.etree import ElementTree as ET

from . import lifecycle, project_authoring
from .engineering import MODEL_PARAMETERS
from .project_io import MAX_JSON_BYTES


MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 1536 * 1024
MAX_FILES = 3
MAX_SHEETS = 12
MAX_ROWS = 500
MAX_COLUMNS = 32
MAX_CELL_CHARS = 4096
MAX_MEMBERS = 64
MAX_INFLATED_BYTES = 8 * 1024 * 1024
MAX_SHARED_STRINGS = 5000
TABLE_FIELDS = {
    "inputs": ("id", "value", "unit", "source"),
    "bindings": ("model_id", "model_type", "parameter", "input_id"),
    "requirements": ("id", "title", "model_id", "metric", "operator", "limit_input", "critical"),
}
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
P = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")
CELL = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,5})\Z")


class IntakeError(ValueError):
    """Controlled intake failure; no files or project records were written."""


def _fields(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise IntakeError(f"{label} has missing or unsupported fields.")


def _text(value, label, *, maximum=MAX_CELL_CHARS, nonempty=True):
    if not isinstance(value, str) or len(value) > maximum or (nonempty and not value.strip()):
        raise IntakeError(f"{label} must be {'nonempty ' if nonempty else ''}text of at most {maximum} characters.")
    if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in value):
        raise IntakeError(f"{label} contains an unsupported control character.")
    return value


def _decode(filename, content_base64):
    _text(filename, "Filename", maximum=180)
    if filename != PurePosixPath(filename).name or "\\" in filename or ":" in filename:
        raise IntakeError("Use a filename without a directory or drive path.")
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in {".csv", ".xlsx"}:
        raise IntakeError("Choose a UTF-8 .csv file or a values-only .xlsx workbook; .xls and macro workbooks are unsupported.")
    if not isinstance(content_base64, str) or len(content_base64) > 4 * ((MAX_FILE_BYTES + 2) // 3):
        raise IntakeError("Each spreadsheet file must be at most 1 MiB.")
    try:
        raw = base64.b64decode(content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise IntakeError("Spreadsheet content must be valid base64.") from exc
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise IntakeError("Each spreadsheet file must be nonempty and at most 1 MiB.")
    return extension, raw


def _sheet(name, records, issues=None):
    """Normalize literal cells, preserving row numbers and every nonempty row."""
    issues = list(issues or [])
    if not records or records[0][0] != 1:
        raise IntakeError(f"Sheet {name}: put column headers in row 1.")
    headers = records[0][1]
    while headers and not headers[-1]:
        headers.pop()
    if not headers or len(headers) > MAX_COLUMNS:
        raise IntakeError(f"Sheet {name}: use between 1 and {MAX_COLUMNS} columns.")
    for header in headers:
        _text(header, f"Sheet {name} header")
    if len(set(headers)) != len(headers):
        raise IntakeError(f"Sheet {name}: column headers must be unique.")
    rows, row_numbers = [], []
    for number, row in records[1:]:
        if not any(row):
            continue
        if len(row) > len(headers) and any(row[len(headers):]):
            raise IntakeError(f"Sheet {name}, row {number}: data extends beyond the column headers.")
        for value in row:
            _text(value, f"Sheet {name}, row {number} cell", nonempty=False)
        rows.append((row + [""] * len(headers))[:len(headers)])
        row_numbers.append(number)
        if len(rows) > MAX_ROWS:
            raise IntakeError(f"Sheet {name}: at most {MAX_ROWS} data rows are supported.")
    return {"name": name, "headers": headers, "rows": rows, "row_numbers": row_numbers, "issues": issues}


def _csv(raw):
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        records = []
        for number, row in enumerate(reader, 1):
            if number > MAX_ROWS + 1 or len(row) > MAX_COLUMNS:
                raise IntakeError(f"CSV permits at most {MAX_ROWS} data rows and {MAX_COLUMNS} columns.")
            records.append((number, row))
        return [_sheet("CSV", records)]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise IntakeError("The CSV must be valid UTF-8 with comma-separated, consistently quoted cells.") from exc


def _xml(archive, name, *, expected=None):
    try:
        raw = archive.read(name)
    except (KeyError, OSError, RuntimeError, EOFError, zlib.error, zipfile.BadZipFile) as exc:
        raise IntakeError("The XLSX is missing or has an unreadable required XML part.") from exc
    # Reject declarations before parsing (including UTF-16/32 spelling).
    lowered = raw.replace(b"\x00", b"").lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise IntakeError("XLSX XML entity and document-type declarations are unsupported.")
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError) as exc:
        raise IntakeError("The XLSX contains invalid XML.") from exc
    if expected and root.tag != expected:
        raise IntakeError("The XLSX contains an unsupported XML part or namespace.")
    return root


def _relationships(archive, name, base):
    root = _xml(archive, name, expected=P + "Relationships")
    output = {}
    for rel in root:
        if rel.tag != P + "Relationship":
            raise IntakeError("Unsupported XLSX relationship record.")
        identity, target = rel.get("Id"), rel.get("Target", "")
        if not identity or identity in output:
            raise IntakeError("The XLSX has duplicate or missing relationship IDs.")
        if rel.get("TargetMode", "Internal") != "Internal" or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", target) or "\\" in target or "?" in target or "#" in target:
            raise IntakeError("External XLSX relationships are unsupported; save a local values-only copy.")
        if target.startswith("/"):
            resolved = target.lstrip("/")
        else:
            resolved = posixpath.normpath(posixpath.join(base, target))
        if resolved.startswith("../") or resolved == ".." or resolved not in archive.namelist():
            raise IntakeError("The XLSX relationship target is missing or outside the archive.")
        output[identity] = (rel.get("Type", ""), resolved)
    return output


def _string_content(item):
    # Phonetic annotations may contain their own <t> children. They are not
    # part of the visible cell text and must never alter a supplied ID.
    return "".join((node.text or "") for child in item
                   for node in ([child] if child.tag == S + "t" else child.findall(S + "t") if child.tag == S + "r" else []))


def _formatted_types(archive, names):
    """Identify dates/percentages whose stored scalar is ambiguous to intake."""
    if "xl/styles.xml" not in names:
        return set()
    root = _xml(archive, "xl/styles.xml", expected=S + "styleSheet")
    custom = {}
    formats = root.find(S + "numFmts")
    if formats is not None:
        for record in formats:
            custom[record.get("numFmtId", "")] = record.get("formatCode", "")
    unsafe = set()
    styles = root.find(S + "cellXfs")
    if styles is None:
        return unsafe
    for index, style in enumerate(styles):
        identity = style.get("numFmtId", "0")
        try:
            numeric_id = int(identity)
        except ValueError as exc:
            raise IntakeError("The XLSX contains an invalid number format.") from exc
        pattern = re.sub(r'"[^"]*"|\\.', "", custom.get(identity, "")).lower()
        if numeric_id in {9, 10, *range(14, 23), *range(27, 37), *range(45, 48), *range(50, 59)} or "%" in pattern or re.search(r"[ymdhs]", pattern):
            unsafe.add(str(index))
    return unsafe


def _xlsx(raw):
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (zipfile.BadZipFile, OSError) as exc:
        raise IntakeError("The file is not a readable XLSX ZIP workbook.") from exc
    with archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(members) > MAX_MEMBERS or len(set(names)) != len(names) or sum(m.file_size for m in members) > MAX_INFLATED_BYTES:
            raise IntakeError("The XLSX exceeds archive limits or contains duplicate members.")
        for member in members:
            name = member.filename
            if name.startswith("/") or "\\" in name or ":" in name or ".." in PurePosixPath(name).parts or member.flag_bits & 1 or stat.S_ISLNK(member.external_attr >> 16):
                raise IntakeError("The XLSX contains an unsafe, encrypted or linked archive member.")
            if member.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED} or member.file_size > MAX_INFLATED_BYTES:
                raise IntakeError("The XLSX archive compression is unsupported.")
            if name.lower().endswith("vbaproject.bin") or name.startswith("xl/externalLinks/"):
                raise IntakeError("Macro and external-link workbooks are unsupported; save a values-only XLSX.")
        root_links = _relationships(archive, "_rels/.rels", "")
        books = [path for kind, path in root_links.values() if kind == R[1:-1] + "/officeDocument"]
        if books != ["xl/workbook.xml"]:
            raise IntakeError("The XLSX must contain one standard xl/workbook.xml part.")
        relationships = _relationships(archive, "xl/_rels/workbook.xml.rels", "xl")
        # Reject external links anywhere, including unselected-sheet links.
        for name in names:
            if name.endswith(".rels") and name not in {"_rels/.rels", "xl/_rels/workbook.xml.rels"}:
                _relationships(archive, name, posixpath.dirname(posixpath.dirname(name)))
        shared_paths = [path for kind, path in relationships.values() if kind == R[1:-1] + "/sharedStrings"]
        if len(shared_paths) > 1:
            raise IntakeError("The XLSX contains ambiguous shared string tables.")
        shared = []
        if shared_paths:
            string_root = _xml(archive, shared_paths[0], expected=S + "sst")
            for item in string_root:
                if len(shared) >= MAX_SHARED_STRINGS:
                    raise IntakeError("The XLSX exceeds the shared-string limit.")
                value = _string_content(item)
                shared.append(_text(value, "XLSX shared string", nonempty=False))
        unsafe_styles = _formatted_types(archive, names)
        workbook = _xml(archive, "xl/workbook.xml", expected=S + "workbook")
        sheets_element = workbook.find(S + "sheets")
        if sheets_element is None or not 1 <= len(sheets_element) <= MAX_SHEETS:
            raise IntakeError(f"The XLSX must contain between 1 and {MAX_SHEETS} worksheets.")
        sheets, seen_names, seen_paths = [], set(), set()
        for element in sheets_element:
            name = _text(element.get("name"), "Sheet name", maximum=80)
            if name in seen_names:
                raise IntakeError("XLSX worksheet names must be unique.")
            seen_names.add(name)
            relation = relationships.get(element.get(R + "id"))
            if relation is None or relation[0] != R[1:-1] + "/worksheet" or relation[1] in seen_paths:
                raise IntakeError("The XLSX worksheet relationship is missing, duplicated or unsupported.")
            seen_paths.add(relation[1])
            sheet_root = _xml(archive, relation[1], expected=S + "worksheet")
            data = sheet_root.find(S + "sheetData")
            records, issues, seen_rows = [], [], set()
            if sheet_root.find(S + "mergeCells") is not None:
                issues.append({"row": None, "field": None, "message": "Merged cells are unsupported. Unmerge and supply explicit column values."})
            if element.get("state", "visible") != "visible":
                issues.append({"row": None, "field": None, "message": "This worksheet is hidden. Make it visible before importing it."})
            for row in ([] if data is None else data):
                try:
                    number = int(row.get("r", "0"))
                except ValueError as exc:
                    raise IntakeError("The XLSX contains an invalid row coordinate.") from exc
                if row.tag != S + "row" or number in seen_rows or not 1 <= number <= MAX_ROWS + 1:
                    raise IntakeError(f"Sheet {name}: duplicate, invalid or out-of-range row; use rows 1–{MAX_ROWS + 1}.")
                seen_rows.add(number)
                cells, seen_cells = {}, set()
                for cell in row:
                    match = CELL.fullmatch(cell.get("r", ""))
                    if cell.tag != S + "c" or not match or int(match[2]) != number:
                        raise IntakeError(f"Sheet {name}: invalid cell coordinates.")
                    column = 0
                    for char in match[1]:
                        column = column * 26 + ord(char) - 64
                    if column > MAX_COLUMNS or column in seen_cells:
                        raise IntakeError(f"Sheet {name}: duplicate or out-of-range cell; at most {MAX_COLUMNS} columns are supported.")
                    seen_cells.add(column)
                    kind, value = cell.get("t", "n"), cell.findtext(S + "v", "")
                    if cell.find(S + "f") is not None:
                        issues.append({"row": number, "field": match[1], "message": "Formula cells and cached formula results are not imported. Paste explicit values into a copy first."})
                        value = ""
                    elif kind == "s":
                        try:
                            index = int(value)
                            if index < 0:
                                raise ValueError
                            value = shared[index]
                        except (ValueError, IndexError) as exc:
                            raise IntakeError(f"Sheet {name}: invalid shared string reference.") from exc
                    elif kind == "inlineStr":
                        inline = cell.find(S + "is")
                        value = "" if inline is None else _string_content(inline)
                    elif kind == "b":
                        if value not in {"0", "1"}:
                            raise IntakeError(f"Sheet {name}: invalid boolean cell.")
                        value = "true" if value == "1" else "false"
                    elif kind not in {"n", "str"}:
                        issues.append({"row": number, "field": match[1], "message": "Date, error or unsupported cell types require explicit literal text/numbers."})
                        value = ""
                    if kind == "n" and value and cell.get("s", "0") in unsafe_styles:
                        issues.append({"row": number, "field": match[1], "message": "Date/time or percentage-formatted numbers are ambiguous. Supply a plain explicit numeric value and unit."})
                        value = ""
                    cells[column] = _text(value, f"Sheet {name} cell {cell.get('r')}", nonempty=False)
                records.append((number, [cells.get(column, "") for column in range(1, max(cells, default=0) + 1)]))
            sheets.append(_sheet(name, sorted(records), issues))
        return sheets


def inspect_document(filename, content_base64):
    """Return literal tables without writing, calculating or saving a project."""
    extension, raw = _decode(filename, content_base64)
    try:
        sheets = _csv(raw) if extension == ".csv" else _xlsx(raw)
    except (zipfile.BadZipFile, RuntimeError, EOFError, zlib.error, OverflowError) as exc:
        raise IntakeError("The spreadsheet archive is invalid or exceeds supported bounds.") from exc
    return {"schema": "sixd.spreadsheet-document.v1", "filename": filename,
            "sha256": sha256(raw).hexdigest(), "size_bytes": len(raw), "sheets": sheets,
            "limits": {"max_file_bytes": MAX_FILE_BYTES, "max_total_bytes": MAX_TOTAL_BYTES,
                       "max_files": MAX_FILES, "max_sheets": MAX_SHEETS,
                       "max_rows": MAX_ROWS, "max_columns": MAX_COLUMNS,
                       "max_cell_characters": MAX_CELL_CHARS}}


def preview(payload):
    """Reparse supplied bytes and validate all mappings; never calculate/save."""
    _fields(payload, {"project", "files", "tables"}, "Spreadsheet preview")
    metadata = payload["project"]
    _fields(metadata, {"project_id", "name", "description", "lifecycle_stage"}, "Project details")
    for field, value in metadata.items():
        _text(value, f"Project {field}")
    files = payload["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise IntakeError(f"Choose between 1 and {MAX_FILES} files.")
    documents = []
    for file in files:
        _fields(file, {"filename", "content_base64"}, "Spreadsheet file")
        documents.append(inspect_document(file["filename"], file["content_base64"]))
    if sum(document["size_bytes"] for document in documents) > MAX_TOTAL_BYTES:
        raise IntakeError("The selected files exceed the combined 1.5 MiB limit.")
    _fields(payload["tables"], TABLE_FIELDS, "Table selections")
    issues, rows_by_role = [], {}

    def issue(table, row, field, message, severity="error"):
        issues.append({"severity": severity, "table": table, "row": row, "field": field, "message": message})

    selected_tables = set()
    for role, fields in TABLE_FIELDS.items():
        selection = payload["tables"][role]
        _fields(selection, {"file_index", "sheet", "mapping"}, f"{role} table selection")
        index = selection["file_index"]
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(documents):
            raise IntakeError(f"Select a supplied file for {role}.")
        sheet = next((item for item in documents[index]["sheets"] if item["name"] == selection["sheet"]), None)
        if sheet is None:
            raise IntakeError(f"Select an available worksheet for {role}.")
        table_identity = (documents[index]["sha256"], sheet["name"])
        if table_identity in selected_tables:
            raise IntakeError("Inputs, bindings and requirements each need a separate record table; select distinct sheets/files.")
        selected_tables.add(table_identity)
        mapping = selection["mapping"]
        _fields(mapping, fields, f"{role} column mapping")
        if any(not isinstance(header, str) or header not in sheet["headers"] for header in mapping.values()):
            raise IntakeError(f"Map every {role} field to an available column.")
        if len(set(mapping.values())) != len(mapping):
            raise IntakeError(f"Each {role} field must use a different column.")
        for item in sheet["issues"]:
            issue(role, item["row"], item["field"], item["message"])
        if not sheet["rows"]:
            issue(role, None, None, "Supply at least one data row.")
        offsets = {field: sheet["headers"].index(header) for field, header in mapping.items()}
        rows_by_role[role] = [(number, {field: row[offset] for field, offset in offsets.items()})
                              for number, row in zip(sheet["row_numbers"], sheet["rows"])]

    provenance = {"files": [{"filename": item["filename"], "sha256": item["sha256"]} for item in documents],
                  "tables": {role: {"filename": documents[selection["file_index"]]["filename"],
                                    "sheet": selection["sheet"], "mapping": dict(selection["mapping"])}
                             for role, selection in payload["tables"].items()}}
    description = metadata["description"] + "\n\nSpreadsheet import provenance (source bytes and explicit mappings; not source authentication or engineering validation):\n" + json.dumps(provenance, ensure_ascii=False, sort_keys=True)
    candidate = {"schema": lifecycle.PROJECT_SCHEMA, **metadata, "description": description, "revision": "1",
                 "inputs": {}, "models": [], "requirements": []}
    for role, rows in rows_by_role.items():
        for number, record in rows:
            for field, value in record.items():
                if not value.strip():
                    issue(role, number, field, "Supply an explicit value; empty cells are not defaulted.")
                elif field not in {"source", "title"} and value != value.strip():
                    issue(role, number, field, "Remove surrounding whitespace; IDs, values and units are used exactly as supplied.")

    input_rows, model_rows, requirement_rows, models = {}, {}, {}, {}
    for number, row in rows_by_role["inputs"]:
        if row["id"] in input_rows:
            issue("inputs", number, "id", f"Duplicate input ID; first supplied at row {input_rows[row['id']]}.")
            continue
        input_rows[row["id"]] = number
        value = row["value"]
        if not NUMBER.fullmatch(value):
            issue("inputs", number, "value", "Use a finite plain decimal/scientific number, without formulas, grouping separators or locale commas.")
            continue
        try:
            numeric = float(value)
        except (ValueError, OverflowError):
            numeric = math.inf
        if not math.isfinite(numeric):
            issue("inputs", number, "value", "The supplied number is outside the finite supported range.")
            continue
        try:
            if numeric == 0 and Decimal(value) != 0:
                issue("inputs", number, "value", "The supplied nonzero number would underflow to zero; use a representable value.")
                continue
        except InvalidOperation:
            issue("inputs", number, "value", "Supply a supported finite decimal number.")
            continue
        if not any(char in value.lower() for char in ".e"):
            numeric = int(value)
            if abs(numeric) > 9007199254740991:
                issue("inputs", number, "value", "This integer exceeds the browser's exact integer range (±9007199254740991). Supply an explicitly justified representable decimal/scientific value instead.")
                continue
        candidate["inputs"][row["id"]] = {"value": numeric, "unit": row["unit"], "source": row["source"]}
    for number, row in rows_by_role["bindings"]:
        identity, kind, parameter, input_id = (row[field] for field in TABLE_FIELDS["bindings"])
        if kind == "power_energy_budget":
            issue("bindings", number, "model_type", "Operating-mode power budgets require the existing power editor or structured JSON; this scalar sheet layout does not encode modes/equipment.")
        elif kind not in MODEL_PARAMETERS:
            issue("bindings", number, "model_type", "Choose a maintained model type from the model catalog; this import does not invent a solver.")
        if identity not in models:
            models[identity] = {"id": identity, "type": kind, "inputs": {}}
            model_rows[identity] = number
        elif models[identity]["type"] != kind:
            issue("bindings", number, "model_type", "All parameter rows for one model ID must declare the same model type.")
        if parameter in models[identity]["inputs"]:
            issue("bindings", number, "parameter", "A model parameter is mapped more than once; remove the duplicate instead of overwriting it.")
        else:
            models[identity]["inputs"][parameter] = input_id
        if input_id not in candidate["inputs"]:
            issue("bindings", number, "input_id", "This binding references an absent or invalid input ID.")
        elif kind in MODEL_PARAMETERS:
            expected = MODEL_PARAMETERS[kind].get(parameter)
            if expected is None:
                issue("bindings", number, "parameter", "This parameter is absent from the selected model's maintained schema.")
            elif candidate["inputs"][input_id]["unit"] != expected:
                issue("bindings", number, "input_id", f"Bound input must use exact unit {expected}; no conversion is performed.")
    candidate["models"] = list(models.values())
    for number, row in rows_by_role["requirements"]:
        if row["id"] in requirement_rows:
            issue("requirements", number, "id", f"Duplicate requirement ID; first supplied at row {requirement_rows[row['id']]}.")
            continue
        requirement_rows[row["id"]] = number
        if row["critical"].lower() not in {"true", "false"}:
            issue("requirements", number, "critical", "Declare true or false explicitly.")
        requirement = {**row, "critical": row["critical"].lower() == "true"}
        candidate["requirements"].append(requirement)
        if row["model_id"] not in models:
            issue("requirements", number, "model_id", "This requirement references an absent model ID.")
        if row["limit_input"] not in candidate["inputs"]:
            issue("requirements", number, "limit_input", "This criterion references an absent or invalid input ID.")
        if row["operator"] not in {"<=", ">=", "=="}:
            issue("requirements", number, "operator", "Use <=, >= or == explicitly.")
    preflight = project_authoring.preflight(candidate)
    for item in preflight["issues"]:
        path = item["path"]
        role, row, field = "project", None, path
        match = re.match(r"project\.(models|requirements)\[(\d+)\](?:\.(.*))?", path)
        if match:
            kind, index, field = match.groups()
            values = candidate[kind]
            if int(index) < len(values):
                identity = values[int(index)]["id"]
                role = "bindings" if kind == "models" else "requirements"
                row = (model_rows if kind == "models" else requirement_rows).get(identity)
        issue(role, row, field, item["message"], item["severity"])
    if len(json.dumps(candidate, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_JSON_BYTES:
        issue("project", None, None, "The resulting project exceeds the two-megabyte project limit.")
    valid = not any(item["severity"] == "error" for item in issues)
    if valid:
        candidate = lifecycle.validate_project(candidate)
    return {"schema": "sixd.spreadsheet-preview.v1", "valid": valid, "project": candidate,
            "issues": issues, "preflight": preflight,
            "source_files": [{"filename": item["filename"], "sha256": item["sha256"]} for item in documents],
            "counts": {"inputs": len(candidate["inputs"]), "models": len(candidate["models"]), "requirements": len(candidate["requirements"])}}
