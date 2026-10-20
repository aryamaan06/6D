"""Captured numerical references retain their source, label and revision.

These are orchestration/security regressions over isolated synthetic projects,
not independent physics validation. No network, founder data or live key is used.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import evidence_facts, project_investigation
from sixd.explanation_quality import explanation_acceptance
from sixd.project_examples import example_projects
from sixd.test_evidence import TestEvidence
from sixd.workspace import WorkspaceStore
from sixd.workspace_test_data import WorkspaceTestData
from test_project_investigation import ScriptProvider


class FactProvider(ScriptProvider):
    """Select actual captured facts only after the required reads complete."""

    def __init__(self, summary):
        super().__init__()
        self.summary = summary

    def complete(self, messages, tools):
        turn = super().complete(messages, tools)
        function = turn.message["tool_calls"][0]["function"]
        if function["name"] == "finish":
            latest = next(message for message in reversed(messages) if message["role"] == "tool")
            catalog = json.loads(latest["content"])["evidence_facts"]
            arguments = json.loads(function["arguments"])
            arguments["summary"] = self.summary(catalog) if callable(self.summary) else self.summary
            function["arguments"] = json.dumps(arguments)
        return turn


class EvidenceFactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "work").mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.store = WorkspaceStore(Path(cls.temporary.name) / "workspace.sqlite3")
        cls.project = example_projects()["orbital_review"]
        cls.store.create_project(cls.project)
        cls.view = cls.store.run(cls.project["project_id"], 1)
        cls.requirement = next(row["id"] for row in cls.project["requirements"] if row["model_id"] == "orbit")
        cls.record, _ = cls.investigate(cls.view)
        if cls.record["state"] != "completed":
            raise AssertionError("Offline reference investigation failed: " + repr(cls.record))

    @classmethod
    def investigate(cls, view, summary="The recorded criterion is met within the bounded scope. Review the assumptions and declared limits.", requirement=None):
        provider = FactProvider(summary)
        # Parallel source edits are unrelated to this isolated policy fixture.
        # Exact captured-source/catalog/revision validation remains unpatched.
        with patch.object(project_investigation, "_runtime_matches", return_value=True):
            receipt = project_investigation.investigate_project(view, requirement or cls.requirement,
                "Explain the selected saved evidence.", provider, investigation_id="offline-fact-reference",
                explanation_policy=evidence_facts.PROSE_POLICY)
        return receipt, provider

    def clone(self):
        return deepcopy(self.record)

    def test_saved_catalog_matches_each_exact_source_pointer_without_mutation(self):
        record = self.clone()
        before = deepcopy(record)
        catalog = evidence_facts.build_fact_catalog(record)
        self.assertEqual(catalog, record["evidence_facts"])
        self.assertEqual(catalog["scope"], {**{key: record[key] for key in
            ("project_id", "revision", "run_id", "review_digest", "requirement_id")}, "model_id": "orbit"})
        self.assertGreater(len(catalog["facts"]), 5)
        for fact in catalog["facts"]:
            source = record["evidence"][fact["evidence_id"]]
            self.assertEqual(fact["value"], evidence_facts.resolve_pointer(source, fact["pointer"]))
            self.assertEqual(fact["evidence_digest"], evidence_facts._digest(source))
            self.assertRegex(fact["id"], r"^f[a-f0-9]{24}$")
        self.assertEqual(record, before)
        catalog["facts"][0]["value"] = "changed only in returned copy"
        self.assertEqual(record, before)

    def test_grid_differences_cannot_be_rendered_without_their_actual_pair_and_value(self):
        facts = self.record["evidence_facts"]["facts"]
        comparisons = self.record["evidence"]["model:orbit"]["recorded_evidence"]["numerical_accuracy"]["comparisons"]
        self.assertEqual([(row["coarse_steps"], row["fine_steps"]) for row in comparisons],
                         [(512, 1024), (1024, 2048)])
        for index, row in enumerate(comparisons):
            for field, unit, label in (
                ("max_position_difference_m", "m", "Maximum aligned position difference"),
                ("max_velocity_difference_m_s", "m/s", "Maximum aligned velocity difference"),
            ):
                pointer = f"/recorded_evidence/numerical_accuracy/comparisons/{index}/{field}"
                fact = next(item for item in facts if item["pointer"] == pointer)
                self.assertEqual(fact["value"], row[field])
                self.assertEqual(fact["unit"], unit)
                self.assertEqual(fact["label"], f"{label} · grids {row['coarse_steps']} → {row['fine_steps']}")
                self.assertEqual(fact["context"], {key: row[key] for key in
                    ("coarse_steps", "fine_steps", "aligned_sample_count")})
        coarse = next(item for item in facts if item["pointer"].endswith("/0/max_position_difference_m"))
        fine = next(item for item in facts if item["pointer"].endswith("/1/max_position_difference_m"))
        self.assertNotEqual(coarse["id"], fine["id"])
        self.assertGreater(coarse["value"], fine["value"] * 3.9)

    def test_exact_fact_token_is_accepted_by_investigation_and_is_not_semantic_approval(self):
        def summary(catalog):
            fact = next(item for item in catalog["facts"]
                        if item["label"] == "Maximum aligned position difference · grids 1024 → 2048")
            return ("The criterion is met within the declared bounded scope. The saved comparison is "
                    f"[[fact:{fact['id']}]]. Review the independent reference and model assumptions.")
        before = deepcopy(self.view)
        record, provider = self.investigate(self.view, summary)
        self.assertEqual(record["state"], "completed")
        self.assertEqual(record["live_model_calls"], 0)
        self.assertEqual(record["accepted_responses"], 4)
        self.assertEqual(record["evidence_facts_prose_policy"], evidence_facts.PROSE_POLICY)
        result = evidence_facts.evaluate_fact_links(record)
        self.assertEqual(result["flags"], [])
        self.assertEqual(len(result["references"]), 1)
        self.assertFalse(result["semantic_accuracy_established"])
        self.assertFalse(record["explanation_quality"]["semantic_accuracy_established"])
        self.assertEqual(self.store.get(self.project["project_id"], 1), before)
        # Exactly one current catalog is visible to the provider, avoiding a
        # duplicated catalog for every earlier evidence read.
        for history in provider.histories[1:]:
            catalogs = [json.loads(message["content"])["evidence_facts"] for message in history
                        if message["role"] == "tool" and "evidence_facts" in json.loads(message["content"])]
            self.assertEqual(len(catalogs), 1)

    def test_new_prose_cannot_retype_wrong_grid_numbers_while_legacy_is_preserved(self):
        raw = ("The criterion is met within the bounded scope. The 512/1024 grid comparison is 432.5 m. "
               "Review independent analysis before relying on this result.")
        record, _ = self.investigate(self.view, raw)
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["error_code"], "explanation_rejected")
        self.assertEqual(record["summary"], "")
        self.assertEqual(record["rejected_interpretation"]["summary"], raw)
        self.assertIn("unbound_numeric_literal", record["explanation_acceptance"]["blocked_codes"])
        self.assertEqual(record["canonical_finding"], self.record["canonical_finding"])
        legacy = self.clone()
        legacy.pop("evidence_facts_prose_policy")
        legacy["summary"] = raw
        before = deepcopy(legacy)
        result = evidence_facts.evaluate_fact_links(legacy)
        self.assertEqual(result["policy"], "historical_unbound_prose")
        self.assertEqual(result["flags"], [])
        self.assertNotIn("unbound_numeric_literal", explanation_acceptance(legacy)["blocked_codes"])
        self.assertEqual(legacy, before)

    def test_legacy_parent_run_binding_is_explicit_without_weakening_new_receipts(self):
        legacy = deepcopy(self.record)
        legacy.pop("evidence_facts_prose_policy", None)
        for payload in legacy["evidence"].values():
            payload.pop("run_id")
        before = deepcopy(legacy)
        catalog = evidence_facts.build_fact_catalog(legacy)
        self.assertEqual(catalog["scope"]["run_id"], legacy["run_id"])
        self.assertTrue(catalog["scope_notes"])
        self.assertEqual(legacy, before)
        legacy["evidence_facts_prose_policy"] = evidence_facts.PROSE_POLICY
        with self.assertRaises(ValueError):
            evidence_facts.build_fact_catalog(legacy)
        legacy.pop("evidence_facts_prose_policy")
        next(iter(legacy["evidence"].values()))["run_id"] = "wrong-explicit-run"
        with self.assertRaises(ValueError):
            evidence_facts.build_fact_catalog(legacy)

    def test_product_name_is_not_a_quantity_but_other_numbers_stay_bound(self):
        record, _ = self.investigate(self.view,
            "6D records a criterion met within the bounded model scope. Review the saved assumptions.")
        self.assertEqual(record["state"], "completed")
        self.assertEqual(evidence_facts.evaluate_fact_links(record)["numeric_literals"], [])
        for prose in ("6D records a value of 9 m.", "60D records a result.", "Review revision 6."):
            record["summary"] = prose
            self.assertIn("unbound_numeric_literal", explanation_acceptance(record)["blocked_codes"])

    def test_unknown_malformed_and_cross_revision_tokens_are_rejected(self):
        record = self.clone()
        altered = self.clone()
        altered["revision"] = 2
        for payload in altered["evidence"].values():
            payload["revision"] = 2
        foreign = evidence_facts.build_fact_catalog(altered)["facts"][0]["id"]
        self.assertNotIn(foreign, {fact["id"] for fact in record["evidence_facts"]["facts"]})
        for token in ("[[fact:f" + "0" * 24 + "]]", f"[[fact:{foreign}]]", "[[fact:UNKNOWN]]",
                      "[[fact:f" + "a" * 23 + "]]", "[[fact:f" + "a" * 25 + "]]", "[[fact:<script>]]"):
            with self.subTest(token=token):
                record["summary"] = "Review this saved comparison within scope: " + token
                self.assertIn("unknown_fact_reference", explanation_acceptance(record)["blocked_codes"])

    def test_reused_token_from_another_same_revision_run_is_rejected(self):
        old = self.clone()
        other = self.clone()
        other["run_id"] = "another-saved-run"
        for payload in other["evidence"].values():
            payload["run_id"] = other["run_id"]
        foreign = evidence_facts.build_fact_catalog(other)["facts"][0]["id"]
        old["summary"] = f"Review the saved evidence [[fact:{foreign}]] within the bounded scope."
        self.assertIn("unknown_fact_reference", explanation_acceptance(old)["blocked_codes"])

    def test_source_and_catalog_tampering_are_rejected_even_if_summary_has_no_numbers(self):
        def tamper_source(record):
            record["evidence"]["model:orbit"]["recorded_evidence"]["metrics"]["max_radius_m"]["value"] += 1
        def tamper_label(record):
            record["evidence_facts"]["facts"][0]["label"] = "Other value"
        def tamper_value(record):
            record["evidence_facts"]["facts"][0]["value"] = -999
        def tamper_pointer(record):
            record["evidence_facts"]["facts"][0]["pointer"] = "/finding/status"
        def tamper_scope(record):
            record["evidence_facts"]["scope"]["revision"] = 2
        def tamper_digest(record):
            record["evidence_facts"]["digest"] = "f" * 64
        def drop_fact(record):
            record["evidence_facts"]["facts"].pop()
        for change in (tamper_source, tamper_label, tamper_value, tamper_pointer, tamper_scope, tamper_digest, drop_fact):
            with self.subTest(change=change.__name__):
                record = self.clone()
                change(record)
                self.assertIn("fact_catalog_mismatch", explanation_acceptance(record)["blocked_codes"])

    def test_each_captured_source_must_match_the_exact_selected_scope_and_identity(self):
        for key, value in (("project_id", "another-project"), ("revision", 2), ("revision", True),
                           ("run_id", "another-run"), ("review_digest", "different-review"),
                           ("id", "model:different")):
            with self.subTest(key=key, value=value):
                record = self.clone()
                record["evidence"]["model:orbit"][key] = value
                self.assertIn("fact_catalog_mismatch", explanation_acceptance(record)["blocked_codes"])
        for source, key, value in (("model:orbit", "model", {"id": "different-model"}),
                                   ("requirement:" + self.requirement, "requirement", {"id": "different-requirement"}),
                                   ("recheck:orbit", "model_id", "different-model")):
            with self.subTest(source=source):
                record = self.clone()
                record["evidence"][source][key] = value
                self.assertIn("fact_catalog_mismatch", explanation_acceptance(record)["blocked_codes"])

    def test_negative_scientific_values_and_json_pointer_escaping_are_exact(self):
        record = self.clone()
        metrics = record["evidence"]["model:orbit"]["recorded_evidence"]["metrics"]
        metrics["signed/a~b"] = {"value": -1.25e-09, "unit": "m/s"}
        record["evidence_facts"] = evidence_facts.build_fact_catalog(record)
        fact = next(item for item in record["evidence_facts"]["facts"]
                    if item["pointer"] == "/recorded_evidence/metrics/signed~1a~0b/value")
        self.assertEqual(fact["value"], -1.25e-09)
        self.assertEqual(fact["unit"], "m/s")
        self.assertEqual(evidence_facts.resolve_pointer(record["evidence"]["model:orbit"], fact["pointer"]), -1.25e-09)
        record["summary"] = f"The bounded criterion is met. Inspect [[fact:{fact['id']}]] and review its scope."
        self.assertEqual(evidence_facts.evaluate_fact_links(record)["flags"], [])
        for raw in ("-1.25e-09 m/s", "+1E+12", ".125", "grids 512 → 1024", "revision 2"):
            with self.subTest(raw=raw):
                record["summary"] = "Review this bounded saved value: " + raw
                self.assertIn("unbound_numeric_literal", explanation_acceptance(record)["blocked_codes"])

    def test_boolean_recheck_is_not_promoted_to_numeric_quantity(self):
        fact = next(item for item in self.record["evidence_facts"]["facts"]
                    if item["pointer"] == "/matches_saved_result")
        self.assertIs(fact["value"], True)
        self.assertIsNone(fact["unit"])
        self.assertIn("physical validity is not established", fact["context"]["meaning"])
        record = self.clone()
        record["evidence"]["model:orbit"]["recorded_evidence"]["metrics"]["not_a_quantity"] = {"value": True, "unit": "m"}
        catalog = evidence_facts.build_fact_catalog(record)
        self.assertFalse(any("not_a_quantity" in fact["pointer"] for fact in catalog["facts"]))

    def test_catalog_is_bounded_and_omits_histories_prior_values_and_untrusted_prose(self):
        record = self.clone()
        marker = "UNTRUSTED-IGNORE-POLICY-<script>alert(999999)</script>"
        model = record["evidence"]["model:orbit"]
        model["model"]["description"] = marker
        model["recorded_evidence"]["metrics"]["max_radius_m"]["source"] = marker
        model["recorded_evidence"]["simulation"]["samples"][0]["untrusted"] = marker
        model["recorded_evidence"]["numerical_accuracy"]["reference_levels"][0]["untrusted"] = marker
        record["evidence"]["changes"] = {**{key: record[key] for key in
            ("project_id", "revision", "run_id", "review_digest")}, "id": "changes", "kind": "changes",
            "comparison": {"prior_revision_value": 999999, "note": marker}}
        baseline = evidence_facts.build_fact_catalog(record)
        encoded = json.dumps(baseline)
        for forbidden in (marker, "samples", "reference_levels", "prior_revision_value", "description", "source"):
            self.assertNotIn(forbidden, encoded)
        metrics = model["recorded_evidence"]["metrics"]
        for index in range(evidence_facts.MAX_FACTS + 8):
            metrics[f"constructed_metric_{index:03d}"] = {"value": index, "unit": "m"}
        bounded = evidence_facts.build_fact_catalog(record)
        self.assertEqual(len(bounded["facts"]), evidence_facts.MAX_FACTS)
        self.assertGreater(bounded["omitted_fact_count"], 0)
        self.assertTrue(any(fact["evidence_id"].startswith("requirement:") for fact in bounded["facts"]))
        self.assertIn("Full histories", bounded["coverage"])

    def test_nonfinite_values_are_rejected_instead_of_receiving_reference_ids(self):
        for invalid in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(invalid=invalid):
                record = self.clone()
                record["evidence"]["model:orbit"]["recorded_evidence"]["metrics"]["max_radius_m"]["value"] = invalid
                self.assertIn("fact_catalog_mismatch", explanation_acceptance(record)["blocked_codes"])

    def test_catalog_order_and_digest_do_not_depend_on_evidence_insertion_order(self):
        record = self.clone()
        record["evidence"] = dict(reversed(list(record["evidence"].items())))
        self.assertEqual(evidence_facts.build_fact_catalog(record), self.record["evidence_facts"])

    def test_selected_test_values_keep_their_frozen_baseline_and_exact_selected_row(self):
        project = example_projects()["baseline"]
        project["project_id"] = "isolated-fact-test-evidence"
        for key, value in {"density": 1.2, "relative_speed": 50, "drag_coefficient": .8,
                           "reference_area": .25, "maximum_drag_force": 305}.items():
            project["inputs"][key]["value"] = value
        self.store.create_project(project)
        original = self.store.run(project["project_id"], 1)
        tests = WorkspaceTestData(self.store)
        spec = {"schema": "sixd.test-comparison-spec.v1", "name": "Selected synthetic scalar row",
                "source": "Constructed arithmetic", "data_kind": "synthetic",
                "test_conditions": "Declared same observable and baseline conditions.",
                "conditions_match": "declared_match", "filename": "selected.csv",
                "mapping": {"measurement_id": "id", "requirement_id": "req", "value": "reading", "unit": "units", "tolerance": "tol"},
                "csv_text": "id,req,reading,units,tol\nselected,drag_limit,250,N,1\nPRIVATE-OTHER-ROW,thermal_limit,290,K,3\n"}
        comparison = tests.run(project["project_id"], 1, original["run"]["run_id"], spec)
        project["inputs"]["maximum_drag_force"]["value"] = 200
        self.store.save_revision(project["project_id"], 1, project)
        view = self.store.run(project["project_id"], 2)
        view["test_evidence"] = TestEvidence(self.store, tests).investigation_context(project["project_id"], 2,
            "drag_limit", comparison["receipt"]["comparison_id"], 2)
        record, _ = self.investigate(view, requirement="drag_limit",
            summary="Interpretation of the recorded finding and stated model limitations. Review the source evidence.")
        self.assertEqual(record["state"], "completed")
        facts = record["evidence_facts"]["facts"]
        selected = [fact for fact in facts if fact["label"].startswith("Original test row")]
        self.assertTrue(selected)
        for fact in selected:
            self.assertEqual(fact["context"]["tested_revision"], 1)
            self.assertEqual(fact["context"]["baseline_run_id"], original["run"]["run_id"])
            self.assertEqual(fact["context"]["row_number"], 2)
            self.assertEqual(fact["context"]["comparison_id"], comparison["receipt"]["comparison_id"])
            self.assertIn("unverified", fact["context"]["conditions"])
        historical_limit = next(fact for fact in selected if fact["pointer"].endswith("/measurement_requirement/limit/value"))
        current_limit = next(fact for fact in facts if fact["pointer"] == "/limit/value")
        self.assertEqual(historical_limit["value"], 305)
        self.assertEqual(current_limit["value"], 200)
        self.assertNotEqual(historical_limit["id"], current_limit["id"])
        self.assertEqual(record["evidence_facts"]["scope"]["revision"], 2)
        self.assertNotIn("PRIVATE-OTHER-ROW", json.dumps(record))
        self.assertEqual(evidence_facts.evaluate_fact_links(record)["flags"], [])


if __name__ == "__main__":
    unittest.main()
