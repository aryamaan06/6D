"""Literal intake, independent equation result and hostile-file acceptance checks."""
import base64
from copy import deepcopy
import csv
from io import BytesIO, StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import warnings
import zipfile
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import spreadsheet_intake as intake
from sixd.engineering import evaluate_models


HEADERS = {role: list(fields) for role, fields in intake.TABLE_FIELDS.items()}
DATA = {
    "inputs": [["rho", "1", "kg/m^3", "Supplied synthetic density"],
               ["speed", "10", "m/s", "Supplied synthetic speed"],
               ["cd", "1", "1", "Supplied synthetic coefficient"],
               ["area", "2", "m^2", "Supplied synthetic area"],
               ["maximum", "150", "N", "Declared constructed limit"]],
    "bindings": [["load", "drag_load", "density", "rho"],
                 ["load", "drag_load", "relative_speed", "speed"],
                 ["load", "drag_load", "drag_coefficient", "cd"],
                 ["load", "drag_load", "reference_area", "area"]],
    "requirements": [["drag_limit", "Declared drag magnitude", "load", "drag_force", "<=", "maximum", "true"]],
}


def encoded(raw):
    return base64.b64encode(raw).decode("ascii")


def csv_file(role, rows=None, headers=None):
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers or HEADERS[role])
    writer.writerows(DATA[role] if rows is None else rows)
    return {"filename": role + ".csv", "content_base64": encoded(stream.getvalue().encode())}


def payload():
    roles = list(HEADERS)
    return {"project": {"project_id": "spreadsheet-example", "name": "Supplied spreadsheet example",
                        "description": "Constructed single-condition drag calculation; no hardware claim.",
                        "lifecycle_stage": "design"},
            "files": [csv_file(role) for role in roles],
            "tables": {role: {"file_index": index, "sheet": "CSV", "mapping": {field: field for field in HEADERS[role]}}
                       for index, role in enumerate(roles)}}


def column(index):
    result = ""
    while index:
        index, digit = divmod(index - 1, 26)
        result = chr(65 + digit) + result
    return result


def xlsx_bytes(rows_by_name=None, *, changes=None):
    rows_by_name = rows_by_name or {role: [HEADERS[role], *DATA[role]] for role in HEADERS}
    parts = {"[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>',
             "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="book" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'}
    sheets, links = [], []
    for index, (name, rows) in enumerate(rows_by_name.items(), 1):
        sheets.append(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="s{index}"/>')
        links.append(f'<Relationship Id="s{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>')
        row_xml = []
        for r, values in enumerate(rows, 1):
            cells = "".join(f'<c r="{column(c)}{r}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>' for c, value in enumerate(values, 1))
            row_xml.append(f'<row r="{r}">{cells}</row>')
        parts[f"xl/worksheets/sheet{index}.xml"] = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(row_xml) + '</sheetData></worksheet>'
    parts["xl/workbook.xml"] = '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + "".join(sheets) + '</sheets></workbook>'
    parts["xl/_rels/workbook.xml.rels"] = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(links) + '</Relationships>'
    for name, change in (changes or {}).items():
        parts[name] = change(parts.get(name, "")) if callable(change) else change
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in parts.items():
            archive.writestr(name, text)
    return output.getvalue()


def xlsx_payload(raw=None):
    result = payload()
    result["files"] = [{"filename": "project.xlsx", "content_base64": encoded(raw or xlsx_bytes())}]
    for role, selection in result["tables"].items():
        selection.update(file_index=0, sheet=role)
    return result


class SpreadsheetIntakeTests(unittest.TestCase):
    def test_csv_project_matches_explicit_inputs_and_hand_computed_drag(self):
        request = payload()
        original = deepcopy(request)
        result = intake.preview(request)
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual(request, original)
        self.assertEqual(result["counts"], {"inputs": 5, "models": 1, "requirements": 1})
        self.assertEqual(result["project"]["inputs"]["rho"], {"value": 1, "unit": "kg/m^3", "source": "Supplied synthetic density"})
        # Independent arithmetic: q = .5 * 1 * 10^2 = 50 Pa;
        # F = q * 1 * 2 = 100 N; declared limit is 150 N.
        results = evaluate_models(result["project"])
        self.assertEqual(results["load"]["metrics"]["drag_force"], {"value": 100, "unit": "N"})
        self.assertEqual(result["project"]["requirements"][0]["limit_input"], "maximum")
        self.assertEqual(len(result["source_files"]), 3)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in result["source_files"]))

    def test_xlsx_and_csv_yield_identical_project_without_calculating(self):
        with patch("sixd.engineering.evaluate_models", side_effect=AssertionError("Preview must not calculate")):
            result = intake.preview(xlsx_payload())
            self.assertTrue(result["valid"], result["issues"])
            other = intake.preview(payload())
            # Their engineering records agree; each description deliberately
            # retains its own source-byte receipt rather than hiding origin.
            for field in ("inputs", "models", "requirements"):
                self.assertEqual(result["project"][field], other["project"][field])
            self.assertTrue(result["project"]["description"].startswith(payload()["project"]["description"]))
            self.assertIn(result["source_files"][0]["sha256"], result["project"]["description"])
            self.assertIn('"sheet": "bindings"', result["project"]["description"])

    def test_explicit_header_mapping_without_name_guessing(self):
        request = payload()
        headers = ["Identifier", "Supplied value", "SI", "Provenance"]
        request["files"][0] = csv_file("inputs", headers=headers)
        request["tables"]["inputs"]["mapping"] = dict(zip(HEADERS["inputs"], headers))
        self.assertTrue(intake.preview(request)["valid"])
        request["tables"]["inputs"]["mapping"]["unit"] = "unit"
        with self.assertRaisesRegex(intake.IntakeError, "Map every inputs"):
            intake.preview(request)

    def test_bad_units_are_specific_and_block_preview(self):
        rows = deepcopy(DATA["inputs"])
        rows[1][2] = "km/s"
        request = payload()
        request["files"][0] = csv_file("inputs", rows)
        result = intake.preview(request)
        self.assertFalse(result["valid"])
        self.assertTrue(any(item["table"] == "bindings" and item["row"] == 3 and "m/s" in item["message"] for item in result["issues"]))

    def test_duplicate_records_do_not_silently_overwrite(self):
        for role, rows in (("inputs", [*DATA["inputs"], DATA["inputs"][0]]),
                           ("bindings", [*DATA["bindings"], DATA["bindings"][0]]),
                           ("requirements", [*DATA["requirements"], DATA["requirements"][0]])):
            request = payload()
            index = list(HEADERS).index(role)
            request["files"][index] = csv_file(role, rows)
            result = intake.preview(request)
            self.assertFalse(result["valid"], role)
            self.assertTrue(any(item["table"] == role and ("Duplicate" in item["message"] or "more than once" in item["message"]) for item in result["issues"]))

    def test_bad_numeric_literals_and_underflow_are_rejected(self):
        for value in ("NaN", "Infinity", "1e999", "1,000", "=A1*2", "12 W", "1e-9999", "", " 10"):
            rows = deepcopy(DATA["inputs"])
            rows[1][1] = value
            request = payload()
            request["files"][0] = csv_file("inputs", rows)
            result = intake.preview(request)
            self.assertFalse(result["valid"], value)
            self.assertTrue(any(item["table"] == "inputs" and item["row"] == 3 for item in result["issues"]), value)

    def test_large_integer_round_trip_is_rejected_and_zero_is_valid(self):
        rows = deepcopy(DATA["inputs"])
        rows[1][1] = "9007199254740993"
        rows[0][1] = "0"
        request = payload()
        request["files"][0] = csv_file("inputs", rows)
        result = intake.preview(request)
        self.assertFalse(result["valid"])
        self.assertTrue(any("exact integer range" in item["message"] for item in result["issues"]))
        self.assertEqual(result["project"]["inputs"]["rho"]["value"], 0)
        rows[1][1] = "9007199254740991"
        request["files"][0] = csv_file("inputs", rows)
        result = intake.preview(request)
        self.assertTrue(result["valid"])
        self.assertEqual(result["project"]["inputs"]["speed"]["value"], 9007199254740991)

    def test_sources_limits_flags_and_parameter_bindings_are_explicit(self):
        cases = [("inputs", 0, 3, ""), ("requirements", 0, 5, "missing"),
                 ("requirements", 0, 6, "yes"), ("requirements", 0, 4, "<"),
                 ("requirements", 0, 3, "guessed_drag"), ("bindings", 0, 3, "missing"),
                 ("bindings", 0, 2, "guessed_density"), ("bindings", 0, 1, "power_energy_budget")]
        for role, row, field, value in cases:
            rows = deepcopy(DATA[role])
            rows[row][field] = value
            request = payload()
            request["files"][list(HEADERS).index(role)] = csv_file(role, rows)
            result = intake.preview(request)
            self.assertFalse(result["valid"], (role, field, value))

    def test_missing_parameter_and_conflicting_model_type_block_preview(self):
        for rows in (DATA["bindings"][:-1], [*DATA["bindings"], ["load", "static_cantilever", "tip_force", "area"]]):
            request = payload()
            request["files"][1] = csv_file("bindings", rows)
            self.assertFalse(intake.preview(request)["valid"])

    def test_formula_cached_value_is_never_accepted(self):
        def formula(text):
            return text.replace('<c r="B3" t="inlineStr"><is><t xml:space="preserve">10</t></is></c>', '<c r="B3"><f>5*2</f><v>10</v></c>')
        raw = xlsx_bytes(changes={"xl/worksheets/sheet1.xml": formula})
        document = intake.inspect_document("project.xlsx", encoded(raw))
        self.assertTrue(any("Formula" in item["message"] and item["row"] == 3 for item in document["sheets"][0]["issues"]))
        result = intake.preview(xlsx_payload(raw))
        self.assertFalse(result["valid"])
        self.assertNotIn("speed", result["project"]["inputs"])

    def test_shared_strings_and_excel_booleans_are_read_literally(self):
        def shared(text):
            return text.replace('<c r="A2" t="inlineStr"><is><t xml:space="preserve">rho</t></is></c>', '<c r="A2" t="s"><v>0</v></c>')
        def boolean(text):
            return text.replace('<c r="G2" t="inlineStr"><is><t xml:space="preserve">true</t></is></c>', '<c r="G2" t="b"><v>1</v></c>')
        raw = xlsx_bytes(changes={"xl/worksheets/sheet1.xml": shared, "xl/worksheets/sheet3.xml": boolean,
            "xl/sharedStrings.xml": '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>rho</t></si></sst>',
            "xl/_rels/workbook.xml.rels": lambda text: text.replace('</Relationships>', '<Relationship Id="strings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>')})
        self.assertTrue(intake.preview(xlsx_payload(raw))["valid"])

    def test_merged_hidden_or_percentage_formatted_cells_block_selection(self):
        for changes in ({"xl/worksheets/sheet1.xml": lambda text: text.replace('</worksheet>', '<mergeCells><mergeCell ref="A2:A3"/></mergeCells></worksheet>')},
                        {"xl/workbook.xml": lambda text: text.replace('name="inputs"', 'state="hidden" name="inputs"')},
                        {"xl/styles.xml": '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cellXfs><xf numFmtId="9"/></cellXfs></styleSheet>',
                         "xl/worksheets/sheet1.xml": lambda text: text.replace('<c r="B3" t="inlineStr"><is><t xml:space="preserve">10</t></is></c>', '<c r="B3"><v>10</v></c>')}):
            self.assertFalse(intake.preview(xlsx_payload(xlsx_bytes(changes=changes)))["valid"])

    def test_external_relationship_entities_macro_and_paths_are_rejected(self):
        changes = [{"xl/_rels/workbook.xml.rels": lambda text: text.replace('Target="worksheets/sheet1.xml"', 'TargetMode="External" Target="https://example.invalid/evil"')},
                   {"xl/workbook.xml": lambda text: '<!DOCTYPE workbook [<!ENTITY secret "private">]>' + text},
                   {"xl/vbaProject.bin": "macro"}, {"../escape.xml": "escape"},
                   {"xl/worksheets/sheet1.xml": lambda text: text.replace('r="B3"', 'r="XFD999999"')}]
        for change in changes:
            with self.assertRaises(intake.IntakeError):
                intake.inspect_document("project.xlsx", encoded(xlsx_bytes(changes=change)))

    def test_duplicate_zip_members_are_rejected(self):
        stream = BytesIO(xlsx_bytes())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(stream, "a") as archive:
                archive.writestr("xl/workbook.xml", "duplicate")
        with self.assertRaisesRegex(intake.IntakeError, "duplicate"):
            intake.inspect_document("project.xlsx", encoded(stream.getvalue()))

    def test_file_mapping_and_size_bounds(self):
        for filename, raw in (("../project.csv", b"a\n1"), ("project.xls", b"a\n1"),
                              ("project.xlsx", b"not a zip"), ("project.csv", b"\xff"),
                              ("project.csv", b"x" * (intake.MAX_FILE_BYTES + 1))):
            with self.assertRaises(intake.IntakeError):
                intake.inspect_document(filename, encoded(raw))
        request = payload()
        request["tables"]["inputs"]["mapping"]["unit"] = "value"
        with self.assertRaisesRegex(intake.IntakeError, "different column"):
            intake.preview(request)
        request = payload()
        request["tables"]["inputs"]["file_index"] = True
        with self.assertRaises(intake.IntakeError):
            intake.preview(request)

    def test_extra_data_columns_headers_and_empty_rows_are_not_lost(self):
        for text in ("a,a\n1,2\n", "a,b\n1,2,3\n", ",b\n1,2\n", ""):
            with self.assertRaises(intake.IntakeError):
                intake.inspect_document("project.csv", encoded(text.encode()))
        document = intake.inspect_document("project.csv", encoded(b"a,b\n\n1,2\n"))
        self.assertEqual(document["sheets"][0]["rows"], [["1", "2"]])
        self.assertEqual(document["sheets"][0]["row_numbers"], [3])

    def test_each_role_requires_a_distinct_record_table(self):
        request = xlsx_payload()
        request["tables"]["bindings"]["sheet"] = "inputs"
        with self.assertRaisesRegex(intake.IntakeError, "separate record table"):
            intake.preview(request)


if __name__ == "__main__":
    unittest.main()
