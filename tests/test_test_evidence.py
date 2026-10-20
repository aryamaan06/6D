"""Read-only test linkage against hand-calculated drag and immutable baselines."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import test_evidence as links
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError, _digest, _encode
from sixd.workspace_test_data import WorkspaceTestData

CSV = "\ufeffid,req,reading,units,tol\r\nselected,drag_limit,310,N,15\r\nPRIVATE-OTHER-ROW,thermal_limit,290,K,3\r\n"
MAPPING = {"measurement_id": "id", "requirement_id": "req", "value": "reading", "unit": "units", "tolerance": "tol"}


class TestEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.tmp.cleanup)
        self.store = WorkspaceStore(Path(self.tmp.name) / "workspace.sqlite3")
        self.tests = WorkspaceTestData(self.store)
        self.links = links.TestEvidence(self.store, self.tests)
        self.project = example_projects()["baseline"]
        for key, value in {"density": 1.2, "relative_speed": 50, "drag_coefficient": .8,
                           "reference_area": .25, "maximum_drag_force": 305}.items():
            self.project["inputs"][key]["value"] = value
        self.identity = self.project["project_id"]
        self.store.create_project(self.project)
        self.view = self.store.run(self.identity, 1)
        self.comparison = self.compare()

    def compare(self, csv_text=CSV, *, revision=1, run_id=None):
        spec = {"schema": "sixd.test-comparison-spec.v1", "name": "Independent scalar comparison",
                "source": "Constructed arithmetic, not hardware data", "data_kind": "synthetic",
                "test_conditions": "Declared same scalar drag observable and supplied baseline conditions.",
                "conditions_match": "declared_match", "filename": "constructed.csv", "csv_text": csv_text,
                "mapping": deepcopy(MAPPING)}
        return self.tests.run(self.identity, revision, run_id or self.view["run"]["run_id"], spec)

    def row(self, summary=None):
        summary = self.links.summary(self.identity, 1) if summary is None else summary
        return summary["comparisons"][0]["rows"][0]

    def selection(self, *, revision=1, requirement="drag_limit", comparison_id=None, row_number=2):
        return self.links.investigation_context(self.identity, revision, requirement,
            comparison_id or self.comparison["receipt"]["comparison_id"], row_number)

    def resign(self, bundle):
        bundle["context_digest"] = _digest({k: v for k, v in bundle.items() if k != "context_digest"})
        return bundle

    def contents(self):
        with self.store._connect() as connection:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name: [tuple(row) for row in connection.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
                    for name in tables}

    def test_exact_baseline_preserves_three_independent_outcomes(self):
        result = self.links.summary(self.identity, 1)
        row = self.row(result)
        # Independently: .5 * rho1.2 * speed50^2 * Cd.8 * area.25 = 300 N.
        self.assertEqual(self.view["run"]["review"]["findings"]["drag_limit"]["status"], "met")
        self.assertEqual(row["measurement_requirement"]["status"], "not_met")
        self.assertEqual(row["prediction_agreement"]["status"], "within_tolerance")
        self.assertEqual(row["prediction_agreement"]["prediction"]["value"], 300)
        self.assertEqual(row["applicability"]["status"], "exact_baseline")
        self.assertEqual(result["counts"]["current"], 2)
        self.assertEqual(result["counts"]["historical"], 0)
        self.assertFalse(row["conditions"]["verified"])
        self.assertEqual(result, self.links.summary(self.identity, 1))

    def test_draft_is_never_exact_and_original_outcomes_are_not_recomputed(self):
        unchanged = self.links.summary(self.identity, 1, project=deepcopy(self.project))
        self.assertEqual(unchanged["context"], "draft")
        self.assertEqual(self.row(unchanged)["applicability"]["status"], "same_dependencies")
        changed = deepcopy(self.project)
        changed["inputs"]["maximum_drag_force"]["value"] = 1000
        before = deepcopy(self.comparison["receipt"]["row_results"][0])
        row = self.row(self.links.summary(self.identity, 1, project=changed))
        self.assertEqual(row["applicability"]["status"], "needs_review")
        self.assertEqual(row["applicability"]["changed_inputs"], ["maximum_drag_force"])
        self.assertEqual({k: v for k, v in row.items() if k != "applicability"}, before)
        self.assertEqual(row["measurement_requirement"]["limit"]["value"], 305)
        self.assertEqual(row["measurement_requirement"]["status"], "not_met")

    def test_unrelated_changes_do_not_infer_physical_coupling(self):
        for key in ("heat_input", "thrust"):
            changed = deepcopy(self.project)
            changed["inputs"][key]["value"] *= 2
            with self.subTest(key=key):
                row = self.row(self.links.summary(self.identity, 1, project=changed))
                self.assertEqual(row["applicability"]["status"], "same_dependencies")
                self.assertEqual(row["applicability"]["changed_inputs"], [])
        changed = deepcopy(self.project)
        changed["name"] = "Only project metadata changed"
        self.store.save_revision(self.identity, 1, changed)
        summary = self.links.summary(self.identity, 2)
        self.assertIsNone(summary["current_run_id"])
        self.assertEqual(self.row(summary)["applicability"]["status"], "same_dependencies")
        self.assertTrue(any("no current canonical review" in s for s in self.row(summary)["applicability"]["reasons"]))
        self.store.run(self.identity, 2)
        self.assertEqual(self.row(self.links.summary(self.identity, 2))["applicability"]["status"], "same_dependencies")

    def test_rerun_changes_identity_without_adopting_historical_tests(self):
        self.store.run(self.identity, 1)
        result = self.links.summary(self.identity, 1)
        self.assertEqual(self.row(result)["applicability"]["status"], "same_dependencies")
        self.assertEqual(result["counts"]["current"], 0)
        self.assertEqual(result["counts"]["historical"], 2)
        self.assertNotEqual(result["current_run_id"], result["comparisons"][0]["baseline_run_id"])

    def test_each_explicit_dependency_change_requires_review(self):
        mutations = {
            "model_input": lambda p: p["inputs"]["relative_speed"].update(value=51),
            "input_source": lambda p: p["inputs"]["density"].update(source="New source"),
            "criterion": lambda p: p["inputs"]["maximum_drag_force"].update(value=290),
            "operator": lambda p: next(r for r in p["requirements"] if r["id"] == "drag_limit").update(operator=">="),
            "title": lambda p: next(r for r in p["requirements"] if r["id"] == "drag_limit").update(title="New requirement meaning"),
            "model_definition": lambda p: next(m for m in p["models"] if m["id"] == "atmospheric_load").update(description="Revised model applicability"),
        }
        for name, mutate in mutations.items():
            changed = deepcopy(self.project)
            mutate(changed)
            with self.subTest(name=name):
                self.assertEqual(self.row(self.links.summary(self.identity, 1, project=changed))["applicability"]["status"], "needs_review")

    def test_removed_and_originally_unmapped_rows_are_retained(self):
        changed = deepcopy(self.project)
        changed["requirements"] = [r for r in changed["requirements"] if r["id"] != "drag_limit"]
        self.assertEqual(self.row(self.links.summary(self.identity, 1, project=changed))["applicability"]["status"], "requirement_removed")
        self.compare("id,req,reading,units,tol\na,not-in-baseline,1,N,1\n")
        changed = deepcopy(self.project)
        new_requirement = deepcopy(changed["requirements"][-1])
        new_requirement["id"] = "not-in-baseline"
        changed["requirements"].append(new_requirement)
        summary = self.links.summary(self.identity, 1, project=changed)
        self.assertEqual(self.row(summary)["applicability"]["status"], "unmapped")
        self.assertEqual(self.row(summary)["measurement_requirement"]["status"], "not_assessed")
        self.assertEqual(summary["counts"]["needs_review"], 1)

    def test_old_comparison_sources_and_adapter_version_are_disclosed(self):
        sources = links._sources()
        sources["workspace_test_data.py"] = "0" * 64
        with patch.object(links, "_sources", return_value=sources):
            result = self.links.summary(self.identity, 1)
        self.assertFalse(result["comparisons"][0]["source_current"])
        self.assertEqual(self.row(result)["applicability"]["status"], "needs_review")
        with patch.dict(links.workspace.MODEL_VERSIONS, {"drag_load": "changed-adapter-version"}):
            result = self.links.summary(self.identity, 1)
        self.assertEqual(self.row(result)["applicability"]["status"], "needs_review")
        self.assertTrue(any("adapter version" in reason for reason in self.row(result)["applicability"]["reasons"]))

    def test_changed_current_prediction_requires_review_even_with_same_inputs(self):
        view = deepcopy(self.view)
        model = view["run"]["review"]["findings"]["drag_limit"]["model_id"]
        view["run"]["review"]["evidence"][model]["fingerprint"] = "0" * 64
        with patch.object(self.store, "_view", return_value=view):
            result = self.links.summary(self.identity, 1)
        self.assertEqual(self.row(result)["applicability"]["status"], "needs_review")
        self.assertTrue(any("canonical result" in reason for reason in self.row(result)["applicability"]["reasons"]))

    def test_read_and_export_never_execute_models_or_change_database(self):
        before = self.contents()
        with patch("sixd.workspace.evaluate_models", side_effect=AssertionError("No calculations in test linkage")), \
                patch("sixd.engineering.evaluate_models", side_effect=AssertionError("No calculations in test linkage")):
            self.links.summary(self.identity, 1)
            self.links.summary(self.identity, 1, project=deepcopy(self.project))
            self.selection()
            exported = self.links.review_export(self.identity, 1)
        self.assertEqual(self.contents(), before)
        self.assertEqual(exported["live_model_calls"], 0)
        self.assertFalse(exported["launch_authorization"])

    def test_export_binds_original_bytes_identity_and_selected_review(self):
        export = self.links.review_export(self.identity, 1)
        source = export["original_test_sources"][0]
        summary = export["test_evidence"]
        self.assertEqual(source["csv_text"], CSV)
        self.assertEqual(source["csv_sha256"], sha256(CSV.encode("utf-8")).hexdigest())
        self.assertEqual(source["comparison_id"], summary["comparisons"][0]["comparison_id"])
        self.assertEqual(source["receipt_digest"], summary["comparisons"][0]["receipt_digest"])
        self.assertEqual(export["workspace"]["run"]["run_id"], summary["current_run_id"])
        self.assertEqual(export["workspace"]["run"]["review"]["digest"], summary["current_review_digest"])
        self.assertEqual(export["export_digest"], _digest({k: v for k, v in export.items() if k != "export_digest"}))
        self.assertEqual(export, self.links.review_export(self.identity, 1))

    def test_history_is_bounded_and_explicitly_truncated_before_filtering(self):
        for _ in range(20):
            self.compare("id,req,reading,units,tol\na,drag_limit,250,N,1\n")
        result = self.links.summary(self.identity, 1)
        self.assertEqual(len(result["comparisons"]), 20)
        self.assertTrue(result["history_truncated"])
        self.assertEqual(result["counts"]["rows"], 20)
        self.assertEqual(result["counts"]["discrepancies"], 20)
        self.assertEqual(result["history_limit"], 20)
        self.assertNotIn(self.comparison["receipt"]["comparison_id"], [c["comparison_id"] for c in result["comparisons"]])
        self.assertEqual(len(self.links.review_export(self.identity, 1)["original_test_sources"]), 20)
        self.assertEqual(self.selection()["recorded"]["row"]["measurement_id"], "selected")

    def test_one_database_snapshot_prevents_mixed_history_and_review(self):
        with self.store._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
        original = self.links._rows
        def append_between_reads(connection, project_id, revision):
            self.compare("id,req,reading,units,tol\nnew,drag_limit,100,N,1\n")
            return original(connection, project_id, revision)
        with patch.object(self.links, "_rows", side_effect=append_between_reads):
            export = self.links.review_export(self.identity, 1)
        self.assertEqual(len(export["test_evidence"]["comparisons"]), 1)
        self.assertEqual(len(export["original_test_sources"]), 1)
        self.assertEqual(len(self.links.summary(self.identity, 1)["comparisons"]), 2)

    def test_investigation_is_one_row_and_one_requirement_without_csv_or_other_model(self):
        bundle = self.selection()
        self.assertTrue(links.validate_investigation_context(bundle, self.view, "drag_limit"))
        encoded = _encode(bundle)
        self.assertNotIn("PRIVATE-OTHER-ROW", encoded)
        self.assertNotIn("csv_text", encoded)
        self.assertNotIn("radiative_equilibrium", encoded)
        self.assertEqual(bundle["selection"]["row_number"], 2)
        self.assertEqual(bundle["selection"]["pointer"], "/row_results/0")
        self.assertEqual(bundle["recorded"]["row"]["measurement_requirement"]["limit"]["value"], 305)
        self.assertEqual(bundle["current"]["finding"]["status"], "met")
        bundle["recorded"]["row"]["measurement_id"] = "client-copy"
        self.assertEqual(self.selection()["recorded"]["row"]["measurement_id"], "selected")

    def test_historical_selection_keeps_original_limit_and_current_finding(self):
        changed = deepcopy(self.project)
        changed["inputs"]["maximum_drag_force"]["value"] = 200
        self.store.save_revision(self.identity, 1, changed)
        self.store.run(self.identity, 2)
        bundle = self.selection(revision=2)
        self.assertEqual(bundle["recorded"]["criterion_input"]["value"], 305)
        self.assertEqual(bundle["current"]["criterion_input"]["value"], 200)
        self.assertEqual(bundle["recorded"]["finding"]["status"], "met")
        self.assertEqual(bundle["current"]["finding"]["status"], "not_met")
        self.assertEqual(bundle["applicability"]["status"], "needs_review")

    def test_invalid_selection_and_cross_project_or_future_bindings_are_rejected(self):
        for changes in ({"comparison_id": "0" * 32}, {"comparison_id": "invalid"},
                        {"row_number": True}, {"row_number": 1}, {"row_number": 202}, {"row_number": 2.0},
                        {"row_number": 4}, {"requirement": "thermal_limit"}, {"requirement": ""}):
            with self.subTest(changes=changes), self.assertRaises(WorkspaceError):
                self.selection(**changes)
        other = deepcopy(self.project)
        other["project_id"] = "other-project"
        self.store.create_project(other)
        with self.assertRaises(WorkspaceError):
            self.links.investigation_context("other-project", 1, "drag_limit", self.comparison["receipt"]["comparison_id"], 2)
        self.store.save_revision(self.identity, 1, self.project)
        later = self.store.run(self.identity, 2)
        future = self.compare(revision=2, run_id=later["run"]["run_id"])
        with self.assertRaises(WorkspaceError):
            self.selection(comparison_id=future["receipt"]["comparison_id"])
        self.assertEqual(len(self.links.summary(self.identity, 1)["comparisons"]), 1)

    def test_draft_scope_and_revision_types_are_strict(self):
        for revision in (True, "1", 0, 1.0):
            with self.subTest(revision=revision), self.assertRaises(WorkspaceError):
                self.links.summary(self.identity, revision)
        for updates in ({"project_id": "other"}, {"revision": "3"}):
            with self.subTest(updates=updates), self.assertRaises(WorkspaceError):
                self.links.summary(self.identity, 1, project={**self.project, **updates})
        with self.assertRaises(WorkspaceError):
            links.TestEvidence(self.store, WorkspaceTestData(WorkspaceStore(Path(self.tmp.name) / "other.sqlite3")))

    def test_corrupt_comparison_cannot_be_linked_or_exported(self):
        identity = self.comparison["receipt"]["comparison_id"]
        with self.store._connect(write=True) as connection:
            connection.execute("UPDATE test_comparisons SET digest=? WHERE comparison_id=?", ("0" * 64, identity))
        for action in (lambda: self.links.summary(self.identity, 1), lambda: self.links.review_export(self.identity, 1), self.selection):
            with self.assertRaisesRegex(WorkspaceError, "Stored test comparison is inconsistent"):
                action()

    def test_mid_read_source_change_or_export_size_bound_fails_closed(self):
        current = links._sources()
        changed = {**current, "test_evidence.py": "0" * 64}
        with patch.object(links, "_sources", side_effect=[current, changed]), self.assertRaises(ConflictError):
            self.links.summary(self.identity, 1)
        with patch.object(links, "MAX_EXPORT_BYTES", 10), self.assertRaisesRegex(WorkspaceError, "export bound"):
            self.links.review_export(self.identity, 1)

    def test_context_rejects_changed_bindings_arithmetic_and_disclosures(self):
        mutations = [lambda b: b.update(project_id="other"), lambda b: b.update(revision=True),
            lambda b: b["selection"].update(pointer="/row_results/1"),
            lambda b: b["current"].update(run_id="0" * 32),
            lambda b: b["recorded"]["row"]["prediction_agreement"].update(signed_difference=9),
            lambda b: b["recorded"].update(conditions_declaration_verified=True),
            lambda b: b["recorded"]["model"].update(evidence_fingerprint="bad"),
            lambda b: b["applicability"].update(status="needs_review"),
            lambda b: b.update(limitations=[])]
        for mutate in mutations:
            bundle = self.selection()
            mutate(bundle)
            with self.subTest(bundle=bundle), self.assertRaises(WorkspaceError):
                links.validate_investigation_context(self.resign(bundle), self.view, "drag_limit")
        bundle = self.selection()
        bundle["context_digest"] = "0" * 64
        with self.assertRaises(WorkspaceError):
            links.validate_investigation_context(bundle, self.view, "drag_limit")

    def test_context_does_not_accept_boolean_numeric_aliases_as_frozen_records(self):
        for mutate in (lambda b: b["current"]["requirement"].update(critical=1),
                       lambda b: b["applicability"].update(exact_baseline=1),
                       lambda b: b["recorded"]["row"]["conditions"].update(verified=0)):
            bundle = self.selection()
            mutate(bundle)
            with self.subTest(bundle=bundle), self.assertRaises(WorkspaceError):
                links.validate_investigation_context(self.resign(bundle), self.view, "drag_limit")


if __name__ == "__main__":
    unittest.main()
