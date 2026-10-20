"""Independent scalar measurement comparisons and immutable evidence records."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import engineering, workspace, workspace_test_data as test_data
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError, _digest, _encode

MAPPING = {"measurement_id": "id", "requirement_id": "req", "value": "reading", "unit": "units", "tolerance": "tol"}


def spec(csv_text=None, **changes):
    result = {"schema": "sixd.test-comparison-spec.v1", "name": "Constructed drag measurement comparison",
              "source": "Synthetic arithmetic test, not hardware evidence", "data_kind": "synthetic",
              "test_conditions": "Same scalar drag force observable; rho=1.2 kg/m^3, relative speed=50 m/s, Cd=.8, area=.25 m^2.",
              "conditions_match": "declared_match", "filename": "constructed.csv",
              "csv_text": csv_text if csv_text is not None else "id,req,reading,units,tol\nforce-1,drag_limit,310,N,15\n",
              "mapping": deepcopy(MAPPING)}
    return {**result, **changes}


class TestDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.path = Path(self.tmp.name) / "workspace.sqlite3"
        self.store = WorkspaceStore(self.path)
        self.service = test_data.WorkspaceTestData(self.store)
        self.project = example_projects()["baseline"]
        for key, value in {"density": 1.2, "relative_speed": 50, "drag_coefficient": .8,
                           "reference_area": .25, "maximum_drag_force": 305}.items():
            self.project["inputs"][key]["value"] = value
        self.store.create_project(self.project)
        self.view = self.store.run(self.project["project_id"], 1)
        self.identity, self.run_id = self.project["project_id"], self.view["run"]["run_id"]

    def tearDown(self):
        self.tmp.cleanup()

    def compare(self, value=None):
        return self.service.run(self.identity, 1, self.run_id, spec() if value is None else value)

    def row(self, result):
        return result["receipt"]["row_results"][0]

    def rewrite(self, receipt, *, digest=True):
        with self.store._connect(write=True) as connection:
            connection.execute("UPDATE test_comparisons SET receipt=?,digest=? WHERE comparison_id=?",
                               (_encode(receipt), _digest(receipt) if digest else "0" * 64, receipt["comparison_id"]))

    def test_independent_drag_arithmetic_separates_two_outcomes(self):
        result = self.compare()
        row = self.row(result)
        # Hand calculation: .5 * 1.2 * 50^2 * .8 * .25 = 300 N.
        self.assertAlmostEqual(row["prediction_agreement"]["prediction"]["value"], 300)
        self.assertEqual(row["measurement_requirement"]["status"], "not_met")
        self.assertEqual(row["measurement_requirement"]["limit"]["value"], 305)
        self.assertEqual(row["prediction_agreement"]["status"], "within_tolerance")
        self.assertAlmostEqual(row["prediction_agreement"]["signed_difference"], 10)
        self.assertAlmostEqual(row["prediction_agreement"]["absolute_difference"], 10)
        self.assertEqual(row["prediction_agreement"]["tolerance"], {"value": 15, "unit": "N"})
        self.assertFalse(row["conditions"]["verified"])
        self.assertFalse(result["freshness"]["historical"])

    def test_measurement_pass_does_not_imply_prediction_agreement(self):
        row = self.row(self.compare(spec("id,req,reading,units,tol\na,drag_limit,250,N,1\n")))
        self.assertEqual(row["measurement_requirement"]["status"], "met")
        self.assertEqual(row["prediction_agreement"]["status"], "outside_tolerance")
        self.assertAlmostEqual(row["prediction_agreement"]["signed_difference"], -50)
        self.assertAlmostEqual(row["prediction_agreement"]["absolute_difference"], 50)

    def test_missing_invalid_negative_tolerance_only_blocks_agreement(self):
        for tolerance in ("", "-1", "NaN", "=1+1", "1e999", "1e-999"):
            with self.subTest(tolerance=tolerance):
                result = self.compare(spec(f"id,req,reading,units,tol\na,drag_limit,310,N,{tolerance}\n"))
                self.assertEqual(self.row(result)["measurement_requirement"]["status"], "not_met")
                self.assertEqual(self.row(result)["prediction_agreement"]["status"], "not_assessed")
        mapping = {**MAPPING, "tolerance": ""}
        self.assertEqual(self.row(self.compare(spec(mapping=mapping)))["measurement_requirement"]["status"], "not_met")

    def test_exact_target_and_explicit_agreement_tolerance_are_separate(self):
        target = deepcopy(self.project)
        target["project_id"] = "exact-scalar-target"
        target["inputs"]["maximum_drag_force"]["value"] = 300
        next(r for r in target["requirements"] if r["id"] == "drag_limit")["operator"] = "=="
        self.store.create_project(target)
        run_id = self.store.run(target["project_id"], 1)["run"]["run_id"]
        for reading, expected in (("300", "met"), ("300.00000000000006", "not_met")):
            result = self.service.run(target["project_id"], 1, run_id, spec(f"id,req,reading,units,tol\na,drag_limit,{reading},N,1\n"))
            self.assertEqual(self.row(result)["measurement_requirement"]["status"], expected)
            self.assertEqual(self.row(result)["prediction_agreement"]["status"], "within_tolerance")
        exact = self.service.run(target["project_id"], 1, run_id, spec("id,req,reading,units,tol\na,drag_limit,300,N,0\n"))
        self.assertEqual(self.row(exact)["prediction_agreement"]["absolute_difference"], 0)
        self.assertEqual(self.row(exact)["prediction_agreement"]["status"], "within_tolerance")

    def test_ge_criterion_includes_exact_threshold_and_zero_tolerance(self):
        target = deepcopy(self.project)
        target["project_id"] = "minimum-drag-test"
        target["inputs"]["maximum_drag_force"]["value"] = 300
        next(r for r in target["requirements"] if r["id"] == "drag_limit")["operator"] = ">="
        self.store.create_project(target)
        run_id = self.store.run(target["project_id"], 1)["run"]["run_id"]
        row = self.row(self.service.run(target["project_id"], 1, run_id, spec("id,req,reading,units,tol\na,drag_limit,300,N,0\n")))
        self.assertEqual(row["measurement_requirement"]["status"], "met")
        self.assertEqual(row["prediction_agreement"]["status"], "within_tolerance")

    def test_difference_overflow_is_explicit_without_nonfinite_json(self):
        # A pure frozen-record arithmetic check, independent of any adapter.
        value = spec("id,req,reading,units,tol\na,drag_limit,-1e308,N,1e308\n")
        normalized, parsed = test_data.validate_spec(value)
        review = deepcopy(self.view["run"]["review"])
        review["findings"]["drag_limit"]["evidence"]["metric"]["value"] = 1e308
        row = test_data._row_results(normalized, parsed, review)[0]
        self.assertEqual(row["measurement_requirement"]["status"], "met")
        self.assertEqual(row["prediction_agreement"]["status"], "outside_tolerance")
        self.assertIsNone(row["prediction_agreement"]["signed_difference"])
        self.assertIsNone(row["prediction_agreement"]["absolute_difference"])
        json.dumps(row, allow_nan=False)

    def test_unsafe_csv_integer_is_a_gap_not_a_rounded_measurement(self):
        text = "id,req,reading,units,tol\na,drag_limit,9007199254740993,N,15\n"
        result = self.compare(spec(text))
        row = self.row(result)
        self.assertIsNone(result["receipt"]["preview"]["rows"][0]["value"])
        self.assertIn("safe-integer", result["receipt"]["preview"]["rows"][0]["issues"][0]["message"])
        self.assertEqual(row["measurement_requirement"]["status"], "not_assessed")
        self.assertEqual(row["prediction_agreement"]["status"], "not_assessed")
        self.assertIsNone(row["measurement_requirement"]["metric"])
        self.assertEqual(result["receipt"]["spec"]["csv_text"], text)
        self.assertEqual(test_data._numeric("9007199254740991"), 9007199254740991)
        # Scientific/decimal inputs explicitly use the shared binary-float
        # representation, rather than promising arbitrary decimal precision.
        self.assertEqual(test_data._numeric("1e20"), 1e20)

    def test_unsafe_integer_tolerance_blocks_agreement_only(self):
        result = self.compare(spec("id,req,reading,units,tol\na,drag_limit,310,N,9007199254740993\n"))
        self.assertEqual(self.row(result)["measurement_requirement"]["status"], "not_met")
        self.assertEqual(self.row(result)["prediction_agreement"]["status"], "not_assessed")
        self.assertIsNone(self.row(result)["prediction_agreement"]["tolerance"])

    def test_unsafe_baseline_limit_integer_blocks_both_outcomes(self):
        for limit in (9007199254740993, 9007199254740992):
            project = deepcopy(self.project)
            project["project_id"] = "unsafe-baseline-limit-" + str(limit)
            project["inputs"]["maximum_drag_force"]["value"] = limit
            self.store.create_project(project)
            baseline = self.store.run(project["project_id"], 1)
            result = self.service.run(project["project_id"], 1, baseline["run"]["run_id"], spec())
            row = self.row(result)
            self.assertEqual(row["measurement_requirement"]["status"], "not_assessed")
            self.assertEqual(row["prediction_agreement"]["status"], "not_assessed")
            self.assertIsNone(row["measurement_requirement"]["limit"])
            self.assertIn("safe-integer", row["measurement_requirement"]["reason"])
            self.assertEqual(result["receipt"]["baseline"]["review"]["project"]["inputs"]["maximum_drag_force"]["value"], limit)

    def test_unsafe_integer_prediction_is_omitted_including_equal_operands(self):
        normalized, parsed = test_data.validate_spec(spec("id,req,reading,units,tol\na,drag_limit,9007199254740992.0,N,1e20\n"))
        review = deepcopy(self.view["run"]["review"])
        evidence = review["findings"]["drag_limit"]["evidence"]
        evidence["metric"]["value"] = evidence["limit"]["value"] = 9007199254740993
        row = test_data._row_results(normalized, parsed, review)[0]
        self.assertEqual(row["measurement_requirement"]["status"], "not_assessed")
        self.assertEqual(row["prediction_agreement"]["status"], "not_assessed")
        self.assertIsNone(row["measurement_requirement"]["limit"])
        self.assertIsNone(row["prediction_agreement"]["prediction"])
        self.assertIsNone(row["prediction_agreement"]["absolute_difference"])

    def test_wrong_units_unknown_or_different_conditions_stay_gaps(self):
        variants = [spec("id,req,reading,units,tol\na,drag_limit,310,kN,15\n"),
                    spec(test_conditions=""), spec(test_conditions="   "),
                    spec(conditions_match="different"), spec(conditions_match="unknown")]
        for value in variants:
            with self.subTest(value=value):
                row = self.row(self.compare(value))
                self.assertEqual(row["measurement_requirement"]["status"], "not_assessed")
                self.assertEqual(row["prediction_agreement"]["status"], "not_assessed")
                self.assertIsNotNone(row["measurement_requirement"]["metric"])

    def test_unknown_and_unsupported_requirements_never_gain_prediction(self):
        value = spec("id,req,reading,units,tol\na,no-such-requirement,1,m,1\n")
        self.assertIsNone(self.row(self.compare(value))["prediction_agreement"]["prediction"])
        project = example_projects()["missing_evidence"]
        project["project_id"] = "unsupported-control-test"
        self.store.create_project(project)
        run_id = self.store.run(project["project_id"], 1)["run"]["run_id"]
        result = self.service.run(project["project_id"], 1, run_id,
                                  spec("id,req,reading,units,tol\na,control_tracking,1,m,1\n"))
        self.assertEqual(self.row(result)["measurement_requirement"]["status"], "not_assessed")
        self.assertEqual(self.row(result)["prediction_agreement"]["status"], "not_assessed")
        self.assertIsNone(self.row(result)["prediction_agreement"]["prediction"])

    def test_all_duplicate_ids_and_invalid_rows_retained_as_quality_gaps(self):
        text = "id,req,reading,units,tol\na,drag_limit,300,N,0\na,drag_limit,301,N,1\nb,drag_limit,NaN,N,1\n,drag_limit,300,N,0\n"
        result = self.compare(spec(text))
        self.assertEqual(result["receipt"]["preview"]["row_count"], 4)
        for row in result["receipt"]["row_results"]:
            self.assertEqual(row["measurement_requirement"]["status"], "not_assessed")
            self.assertEqual(row["prediction_agreement"]["status"], "not_assessed")
        self.assertIsNone(result["receipt"]["preview"]["rows"][2]["value"])
        self.assertEqual(result["receipt"]["preview"]["rows"][0]["value"], 300)

    def test_bom_quoted_commas_and_formula_text_preserve_exact_original_bytes(self):
        text = '\ufeffid,req,reading,units,tol,notes\r\n"=SUM(1,2)",drag_limit,3e2,N,0,"A quoted, note\nwith a newline"\r\n'
        result = self.compare(spec(text))
        self.assertEqual(result["receipt"]["spec"]["csv_text"], text)
        self.assertEqual(result["receipt"]["preview"]["csv_sha256"], sha256(text.encode("utf-8")).hexdigest())
        self.assertEqual(self.row(result)["measurement_id"], "=SUM(1,2)")
        self.assertEqual(self.row(result)["measurement_requirement"]["status"], "met")
        self.assertEqual(result["receipt"]["preview"]["raw_preview"][0]["notes"], "A quoted, note\nwith a newline")
        formula = self.compare(spec("id,req,reading,units,tol\na,drag_limit,=300+1,N,0\n"))
        self.assertIsNone(formula["receipt"]["preview"]["rows"][0]["value"])
        self.assertEqual(self.row(formula)["measurement_requirement"]["status"], "not_assessed")

    def test_empty_mapping_does_not_guess_headers_or_numbers(self):
        parsed = self.service.preview("test.csv", spec()["csv_text"], {})
        self.assertEqual(parsed["mapping"], dict.fromkeys(test_data.MAPPING_FIELDS, ""))
        self.assertEqual(parsed["rows"][0]["issues"].__len__(), 5)
        self.assertIsNone(parsed["rows"][0]["value"])
        self.assertEqual(parsed["rows"][0]["requirement_id"], "")

    def test_strict_csv_structure_and_bounds(self):
        invalid = ["", "a,b\n", "a,a\n1,2\n", "a, a \n1,2\n", "a,\n1,2\n", "a,b\n1\n", "a,b\n1,2,3\n",
                   'a,b\n"unclosed,2\n', 'a,b\n"closed"suffix,2\n', "a,b\n1,\x00\n", "a,b\n\n",
                   "a,b\n1," + "x" * 4097 + "\n", "h" * 129 + ",b\n1,2\n",
                   ",".join(str(i) for i in range(33)) + "\n" + ",".join("1" for _ in range(33)),
                   "a\n" + "\n".join("1" for _ in range(201)), "a\n" + "x" * (1024 * 1024)]
        for value in invalid:
            with self.subTest(value=value[:60]), self.assertRaises(WorkspaceError):
                self.service.preview("test.csv", value, {})
        with self.assertRaises(WorkspaceError):
            self.service.preview("test.csv", "a\n\ud800\n", {})

    def test_mapping_exact_columns_and_nonoverlap(self):
        for mapping in ({"value": "reading"}, {**MAPPING, "extra": "id"},
                        {**MAPPING, "value": "no-column"}, {**MAPPING, "unit": "reading"},
                        {**MAPPING, "value": None}):
            with self.subTest(mapping=mapping), self.assertRaises(WorkspaceError):
                self.service.preview("test.csv", spec()["csv_text"], mapping)

    def test_strict_spec_fields_labels_and_declarations(self):
        for value in ({**spec(), "extra": 1}, {**spec(), "schema": "other"}, spec(name=""), spec(source=""),
                      spec(data_kind="fixture"), spec(conditions_match="yes"), spec(test_conditions=10),
                      spec(filename=""), spec(mapping=None)):
            with self.subTest(value=str(value)[:100]), self.assertRaises(WorkspaceError):
                self.compare(value)

    def test_save_and_reads_use_no_model_or_ai_and_preserve_baseline(self):
        before = self.store.get(self.identity)
        with patch.object(workspace, "evaluate_models", side_effect=AssertionError("No solver")), \
             patch.object(engineering, "evaluate_models", side_effect=AssertionError("No solver")):
            result = self.compare()
            reopened = test_data.WorkspaceTestData(WorkspaceStore(self.path))
            self.assertEqual(reopened.get(result["receipt"]["comparison_id"], 1), result)
            self.assertEqual(reopened.list(self.identity, 1)["comparisons"][0]["comparison_id"], result["receipt"]["comparison_id"])
        self.assertEqual(self.store.get(self.identity), before)
        with self.store._connect() as connection:
            for table, expected in (("projects", 1), ("revisions", 1), ("runs", 1), ("test_comparisons", 1)):
                self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], expected)
        self.assertEqual(result["receipt"]["live_model_calls"], 0)

    def test_fresh_baseline_required_and_concurrent_guard(self):
        for value in ([], "wrong", True):
            with self.assertRaises(WorkspaceError):
                self.service.run(self.identity, 1, value, spec())
        with self.assertRaises(ConflictError):
            self.service.run(self.identity, 1, "0" * 32, spec())
        self.store.save_revision(self.identity, 1, self.project)
        with self.assertRaises(ConflictError):
            self.service.run(self.identity, 2, self.run_id, spec())
        self.service._lock.acquire()
        try:
            with self.assertRaises(ConflictError):
                self.compare()
        finally:
            self.service._lock.release()

    def test_history_on_new_baseline_revision_and_source(self):
        result = self.compare()
        identity = result["receipt"]["comparison_id"]
        self.store.run(self.identity, 1)
        self.assertTrue(self.service.get(identity, 1)["freshness"]["historical"])
        self.store.save_revision(self.identity, 1, self.project)
        self.assertFalse(self.service.get(identity, 2)["freshness"]["selected_revision_matches"])
        self.assertEqual(len(self.service.list(self.identity, 2)["comparisons"]), 1)
        changed = {**test_data._sources(), "workspace_test_data.py": "0" * 64}
        with patch.object(test_data, "_sources", return_value=changed):
            self.assertFalse(self.service.get(identity, 1)["freshness"]["source_current"])
            with self.assertRaises(ConflictError):
                self.compare()

    def test_future_context_and_invalid_identity_rejected(self):
        self.store.save_revision(self.identity, 1, self.project)
        run_id = self.store.run(self.identity, 2)["run"]["run_id"]
        result = self.service.run(self.identity, 2, run_id, spec())
        self.assertEqual(self.service.list(self.identity, 1)["comparisons"], [])
        with self.assertRaises(WorkspaceError):
            self.service.get(result["receipt"]["comparison_id"], 1)
        for identity in ([], "bad", "0" * 32):
            with self.assertRaises(WorkspaceError):
                self.service.get(identity)

    def test_rehashed_corrupt_findings_and_csv_hash_fail_integrity(self):
        original = self.compare()["receipt"]
        for mutate in (lambda r: r["row_results"][0]["measurement_requirement"].update(status="met"),
                       lambda r: r["preview"].update(csv_sha256="0" * 64),
                       lambda r: r["baseline"].update(run_digest="0" * 64),
                       lambda r: r["sources"].update({"engineering.py": "0" * 64}),
                       lambda r: r.update(live_model_calls=False),
                       lambda r: r.update(unexpected="field")):
            receipt = deepcopy(original)
            mutate(receipt)
            self.rewrite(receipt)
            with self.assertRaises(WorkspaceError):
                self.service.get(receipt["comparison_id"])
        self.rewrite(original, digest=False)
        with self.assertRaises(WorkspaceError):
            self.service.list(self.identity, 1)

    def test_rehashed_boolean_number_substitutions_are_not_equivalent(self):
        original = self.compare(spec("id,req,reading,units,tol\na,drag_limit,1,N,1\n"))["receipt"]
        for mutate in (
            lambda r: r["preview"]["rows"][0].update(value=True),
            lambda r: r["row_results"][0]["measurement_requirement"]["metric"].update(value=True),
            lambda r: r["baseline"]["review"]["project"]["inputs"]["radiator_area"].update(value=True),
            lambda r: r.update(revision=True),
        ):
            receipt = deepcopy(original)
            mutate(receipt)
            self.rewrite(receipt)
            with self.assertRaises(WorkspaceError):
                self.service.get(receipt["comparison_id"])

    def test_source_or_baseline_changes_during_save_append_nothing(self):
        original = test_data.validate_spec
        def rerun(value):
            self.store.run(self.identity, 1)
            return original(value)
        with patch.object(test_data, "validate_spec", side_effect=rerun):
            with self.assertRaises(ConflictError):
                self.compare()
        self.assertEqual(self.service.list(self.identity, 1)["comparisons"], [])
        self.run_id = self.store.get(self.identity)["run"]["run_id"]
        loaded = test_data._sources()
        count = 0
        def sources():
            nonlocal count
            count += 1
            return loaded if count == 1 else {**loaded, "workspace_test_data.py": "0" * 64}
        with patch.object(test_data, "_sources", side_effect=sources):
            with self.assertRaises(ConflictError):
                self.compare()
        self.assertEqual(self.service.list(self.identity, 1)["comparisons"], [])


if __name__ == "__main__":
    unittest.main()
