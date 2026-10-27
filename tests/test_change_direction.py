"""Independent acceptance cases for source-bound revision directions.

These are checks of exact recorded values and bounded wording rejection, not
physical validation or a guarantee that unflagged commentary is correct.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import change_evidence
from sixd.evidence_facts import _digest, resolve_pointer
from sixd.explanation_quality import explanation_acceptance
from sixd.project_investigation import investigate_project, ProjectActionAdapter
from sixd.providers import LiveConfig, TokenFactoryProvider, BudgetLedger
from sixd.workspace import WorkspaceStore
from test_project_investigation import ScriptProvider
from test_project_provider import selected, response


LIVE_BATCH = ROOT / "artifacts/application-roles/44e03643f53f480c94df66aa1f87765b.json"


def quantity(value, unit="K"):
    return {"value": value, "unit": unit, "source": "Constructed acceptance fixture."}


def changes(*, before_limit=320, after_limit=250, before_metric=257.68080585928254,
            after_metric=257.68080585928254):
    """Independent two-revision fixture, with no model or provider execution."""
    old_inputs = {"maximum_temperature": quantity(before_limit),
                  "heat_input": quantity(200, "W"), "radiator_area": quantity(1, "m^2")}
    new_inputs = {**deepcopy(old_inputs), "maximum_temperature": quantity(after_limit)}
    def finding(limit, metric):
        return {"requirement_id": "thermal_limit", "model_id": "thermal",
                "metric": "equilibrium_temperature", "status": "not_met",
                "evidence": {"operator": "<=", "limit": quantity(limit), "metric": quantity(metric)}}
    return {"id": "changes", "kind": "changes", "project_id": "direction-acceptance",
            "revision": 2, "run_id": "after-run", "review_digest": "after-review",
            "comparison": {"schema": "sixd.review-comparison.v1", "project_id": "direction-acceptance",
                "from_revision": "1", "to_revision": "2",
                "scope": {"requirement_id": "thermal_limit", "model_id": "thermal",
                          "input_ids": sorted(old_inputs)},
                "before": {"finding": finding(before_limit, before_metric), "input_records": old_inputs},
                "after": {"finding": finding(after_limit, after_metric), "input_records": new_inputs},
                "changed_inputs": ["maximum_temperature"], "added_inputs": [], "removed_inputs": []}}


def rows(context):
    return {row["subject"]: row for row in context["comparisons"]}


def contradiction(summary, context):
    return any(flag["code"] == "change_direction_contradiction"
               for flag in change_evidence.evaluate_change_commentary(summary, context))


class ChangeDirectionContextTests(unittest.TestCase):
    def test_exact_before_after_values_and_source_paths_are_captured_read_only(self):
        source = changes()
        original = deepcopy(source)
        context = change_evidence.build_change_context(source)
        self.assertEqual(source, original)
        self.assertEqual(context["schema"], "sixd.change-context.v1")
        self.assertEqual(context["source_evidence_id"], "changes")
        self.assertEqual(context["source_digest"], _digest(source))
        self.assertEqual(context["digest"], _digest({k: v for k, v in context.items() if k != "digest"}))
        selected = rows(context)
        self.assertEqual(selected["declared_limit"]["direction"], "decreased")
        self.assertEqual(selected["calculated_metric"]["direction"], "unchanged")
        self.assertEqual(selected["input:maximum_temperature"]["direction"], "decreased")
        self.assertEqual(selected["input:heat_input"]["direction"], "unchanged")
        for row in context["comparisons"]:
            self.assertEqual(row["before"], resolve_pointer(source, row["before_pointer"]))
            self.assertEqual(row["after"], resolve_pointer(source, row["after_pointer"]))
        self.assertEqual(selected["declared_limit"]["before_pointer"], "/comparison/before/finding/evidence/limit")
        self.assertEqual(selected["calculated_metric"]["after_pointer"], "/comparison/after/finding/evidence/metric")

    def test_signed_values_and_equality_use_numeric_order_without_rounding(self):
        for old, new, expected in ((-3, -2, "increased"), (-2, -3, "decreased"),
                                   (-1, 1, "increased"), (1, -1, "decreased"),
                                   (0, -0.0, "unchanged"), (7, 7.0, "unchanged"),
                                   (1.0, 1.0000000000000002, "increased")):
            with self.subTest(old=old, new=new):
                context = change_evidence.build_change_context(changes(before_limit=old, after_limit=new))
                self.assertEqual(rows(context)["declared_limit"]["direction"], expected)

    def test_metadata_changed_inputs_cannot_override_values_or_supply_new_evidence(self):
        source = changes()
        source["comparison"]["changed_inputs"] = ["heat_input", "invented_engine_thrust"]
        source["comparison"]["scope"]["input_ids"].append("invented_engine_thrust")
        context = change_evidence.build_change_context(source)
        selected = rows(context)
        self.assertEqual(selected["input:heat_input"]["direction"], "unchanged")
        self.assertEqual(selected["input:maximum_temperature"]["direction"], "decreased")
        self.assertNotIn("input:invented_engine_thrust", selected)
        self.assertEqual(set(selected), {"declared_limit", "calculated_metric", "input:heat_input",
                                         "input:maximum_temperature", "input:radiator_area"})

    def test_exact_units_required_without_implicit_conversions(self):
        source = changes()
        source["comparison"]["after"]["finding"]["evidence"]["limit"] = quantity(-23.15, "degC")
        context = change_evidence.build_change_context(source)
        self.assertEqual(rows(context)["declared_limit"]["direction"], "not_comparable")
        self.assertFalse(contradiction("The declared limit increased.", context))

    def test_changed_observable_or_model_identity_is_not_a_comparable_output(self):
        for key, value in (("metric", "surface_peak_temperature"), ("model_id", "other_thermal_model")):
            with self.subTest(key=key):
                source = changes()
                source["comparison"]["after"]["finding"][key] = value
                selected = rows(change_evidence.build_change_context(source))
                self.assertEqual(selected["calculated_metric"]["direction"], "not_comparable")
                self.assertEqual(selected["declared_limit"]["direction"], "not_comparable")
                self.assertEqual(selected["input:maximum_temperature"]["direction"], "decreased")

    def test_changed_operator_does_not_become_an_unchanged_criterion(self):
        source = changes()
        source["comparison"]["after"]["finding"]["evidence"]["operator"] = ">="
        selected = rows(change_evidence.build_change_context(source))
        self.assertEqual(selected["declared_limit"]["direction"], "not_comparable")
        self.assertEqual(selected["calculated_metric"]["direction"], "unchanged")

    def test_missing_previous_and_non_numeric_values_do_not_create_numeric_evidence(self):
        source = changes()
        source["comparison"]["before"]["finding"] = None
        source["comparison"]["after"]["input_records"]["heat_input"]["value"] = "300"
        source["comparison"]["after"]["input_records"]["radiator_area"]["value"] = True
        context = change_evidence.build_change_context(source)
        selected = rows(context)
        for subject in ("declared_limit", "calculated_metric", "input:heat_input", "input:radiator_area"):
            self.assertEqual(selected[subject]["direction"], "not_comparable")

    def test_added_removed_inputs_remain_not_comparable_with_exact_paths(self):
        source = changes()
        source["comparison"]["after"]["input_records"]["new_input"] = quantity(10, "W")
        del source["comparison"]["after"]["input_records"]["radiator_area"]
        selected = rows(change_evidence.build_change_context(source))
        for subject in ("input:new_input", "input:radiator_area"):
            self.assertEqual(selected[subject]["direction"], "not_comparable")

    def test_nonfinite_captured_values_cannot_be_hashed_as_valid_evidence(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    change_evidence.build_change_context(changes(after_limit=value))

    def test_pointer_escaping_preserves_original_input_identity(self):
        source = changes()
        for label, value in (("before", 9), ("after", 8)):
            source["comparison"][label]["input_records"]["load~/x"] = quantity(value, "W")
        row = rows(change_evidence.build_change_context(source))["input:load~/x"]
        self.assertEqual(row["before_pointer"], "/comparison/before/input_records/load~0~1x")
        self.assertEqual(row["before"], resolve_pointer(source, row["before_pointer"]))
        self.assertEqual(row["direction"], "decreased")

    def test_no_previous_review_or_changes_source_has_no_invented_comparison(self):
        self.assertIsNone(change_evidence.context_from_record({"evidence": {}}))
        context = change_evidence.build_change_context({"id": "changes", "kind": "changes", "comparison": None})
        self.assertFalse(context["available"])
        self.assertEqual(context["comparisons"], [])
        self.assertFalse(contradiction("Review whether a later revision increases the declared limit.", context))

    def test_context_cannot_be_borrowed_from_another_scope(self):
        source = changes()
        record = {key: source[key] for key in ("project_id", "revision", "run_id", "review_digest")}
        record.update(requirement_id="thermal_limit", canonical_finding=deepcopy(source["comparison"]["after"]["finding"]),
                      evidence={"changes": source})
        expected = change_evidence.context_from_record(record)
        self.assertEqual(expected["scope"]["requirement_id"], "thermal_limit")
        self.assertEqual(expected["scope"]["model_id"], "thermal")
        self.assertEqual(expected["scope"]["from_revision"], "1")
        self.assertEqual(expected["scope"]["to_revision"], "2")
        for key, value in (("project_id", "other-project"), ("revision", 3),
                           ("run_id", "other-run"), ("review_digest", "other-review")):
            with self.subTest(key=key):
                changed = deepcopy(record)
                changed["evidence"]["changes"][key] = value
                with self.assertRaises(ValueError):
                    change_evidence.context_from_record(changed)
        for key, value in (("requirement_id", "other-requirement"), ("model_id", "other-model")):
            with self.subTest(key=key):
                changed = deepcopy(record)
                changed["evidence"]["changes"]["comparison"]["scope"][key] = value
                with self.assertRaises(ValueError):
                    change_evidence.context_from_record(changed)
        changed = deepcopy(record)
        changed["evidence"]["changes"]["comparison"]["to_revision"] = "3"
        with self.assertRaises(ValueError):
            change_evidence.context_from_record(changed)


class ChangeDirectionCommentaryTests(unittest.TestCase):
    def setUp(self):
        self.context = change_evidence.build_change_context(changes())

    def test_clear_opposite_direction_and_false_unchanged_assertions_are_rejected(self):
        for summary in (
            "The declared limit increased in the saved revision.",
            "The maximum temperature input was raised while other inputs remained unchanged.",
            "An increased maximum temperature input caused this changed finding.",
            "The declared limit remained unchanged.",
            "The calculated metric decreased between the recorded revisions.",
            "The equilibrium temperature increased in the current revision.",
            "The heat input increased.",
            "The radiator area decreased.",
        ):
            with self.subTest(summary=summary):
                self.assertTrue(contradiction(summary, self.context), summary)

    def test_correct_changes_equality_and_separate_subjects_are_accepted(self):
        for summary in (
            "The declared limit decreased, while the calculated metric remained unchanged.",
            "The maximum temperature input decreased. The heat input remained unchanged.",
            "The radiator area and heat input are unchanged.",
            "Unlike the decreased declared limit, the calculated equilibrium temperature is unchanged.",
        ):
            with self.subTest(summary=summary):
                self.assertFalse(contradiction(summary, self.context), summary)

    def test_increased_context_rejects_decrease_and_accepts_increase(self):
        context = change_evidence.build_change_context(changes(before_limit=250, after_limit=320))
        self.assertTrue(contradiction("The declared limit decreased.", context))
        self.assertFalse(contradiction("The declared limit increased.", context))

    def test_equal_context_rejects_both_direction_claims(self):
        context = change_evidence.build_change_context(changes(before_limit=250, after_limit=250))
        self.assertTrue(contradiction("The declared limit increased.", context))
        self.assertTrue(contradiction("The declared limit decreased.", context))
        self.assertFalse(contradiction("The declared limit is unchanged.", context))

    def test_questions_conditionals_negations_and_next_actions_are_not_factual_changes(self):
        for summary in (
            "Review whether an increased declared limit is justified.",
            "If the declared limit increased, the requirement would need another review.",
            "Could the declared limit increase in a later revision?",
            "Did the declared limit increase?",
            "Has the declared limit increased?",
            "The declared limit did not increase; it decreased.",
            "Do not increase the maximum temperature input solely to obtain a pass.",
            "Investigate whether the calculated metric decreased in a different configuration.",
        ):
            with self.subTest(summary=summary):
                self.assertFalse(contradiction(summary, self.context), summary)

    def test_unverified_attribution_and_quotes_do_not_exempt_a_wrong_claim(self):
        # No matching captured quote establishes the asserted earlier output.
        # Mere quotation marks must not provide a guard bypass.
        summary = ('The earlier output said "the declared limit increased". '
                   'The captured declared limit decreased; inspect the original sources.')
        self.assertTrue(contradiction(summary, self.context))
        self.assertTrue(contradiction('The app says "the declared limit increased".', self.context))

    def test_hypothetical_suffix_cannot_hide_an_earlier_factual_contradiction(self):
        self.assertTrue(contradiction("The declared limit increased, which may warrant another review.", self.context))
        self.assertTrue(contradiction("The declared limit increased and a higher fidelity analysis may be needed.", self.context))

    def test_static_metric_limit_comparison_is_not_a_revision_direction(self):
        for summary in ("The declared limit is lower than the calculated metric.",
                        "The calculated metric is higher than the declared limit."):
            with self.subTest(summary=summary):
                self.assertFalse(contradiction(summary, self.context))

    @unittest.skipUnless(LIVE_BATCH.exists(), "The immutable local live receipt is not distributed with source code.")
    def test_actual_super_error_rejected_ultra_text_accepted_and_receipt_unchanged(self):
        before_hash = hashlib.sha256(LIVE_BATCH.read_bytes()).hexdigest()
        artifact = json.loads(LIVE_BATCH.read_text(encoding="utf-8"))
        actual = {row["candidate_id"]: row["receipt"] for row in artifact["rows"]
                  if row["case_id"] == "limit-only-change" and row.get("receipt")}
        for candidate, expected in (("super", True), ("ultra", False)):
            record = actual[candidate]
            original = deepcopy(record)
            context = change_evidence.context_from_record(record)
            self.assertEqual(rows(context)["declared_limit"]["direction"], "decreased")
            self.assertEqual(rows(context)["calculated_metric"]["direction"], "unchanged")
            self.assertEqual(contradiction(record["summary"], context), expected, candidate)
            self.assertEqual(record, original)
        self.assertEqual(hashlib.sha256(LIVE_BATCH.read_bytes()).hexdigest(), before_hash)


class WithinRunAssumptionTests(unittest.TestCase):
    def setUp(self):
        # Independently supplied before/after scalar values: thrust really rose.
        # Whether a solver holds each chosen value constant during time is a
        # different question from equality between these saved configurations.
        source = changes(before_limit=250, after_limit=250)
        source["comparison"]["before"]["input_records"]["thrust"] = quantity(10, "N")
        source["comparison"]["after"]["input_records"]["thrust"] = quantity(20, "N")
        self.context = change_evidence.build_change_context(source)
        self.assertEqual(rows(self.context)["input:thrust"]["direction"], "increased")

    def test_within_run_time_or_model_assumptions_are_not_revision_equality_claims(self):
        for summary in (
            "The model assumes constant thrust during the burn.",
            "The model assumptions include constant thrust and a supplied atmosphere.",
            "The model's assumptions—such as constant thrust—need engineering review.",
            "Within the model scope: one radial vertical degree of freedom, constant thrust and instantaneous cutoff.",
            "The thrust is constant throughout the simulation.",
            "During the burn the thrust remains constant.",
            "The thrust increased between saved revisions. The model assumes constant thrust during each burn.",
            "Increased thrust was used in the saved revision; the model assumes constant thrust during the burn.",
            "The next engineering check is to verify constant thrust and dry mass against sources.",
            "A concrete next engineering review is to verify the initial masses, constant thrust and atmosphere inputs.",
            "In this saved vertical flight model, the vehicle ascends straight up with constant thrust and changing mass.",
            "The finding applies only to the stated assumptions: one vertical degree of freedom, constant thrust and instantaneous cutoff.",
            "Using the bounded model, ascent is computed with constant thrust.",
        ):
            with self.subTest(summary=summary):
                self.assertEqual(change_evidence.evaluate_change_commentary(summary, self.context), [])

    def test_explicit_revision_equality_and_opposite_directions_remain_rejected(self):
        for summary in (
            "The thrust remained constant between revisions.",
            "The model assumes thrust remained constant between the saved revisions.",
            "The thrust is constant compared with the prior revision.",
            "The model scope: the thrust remained constant from the previous revision.",
            "The thrust stayed unchanged.",
            "Unchanged thrust was used in the revised design.",
            "The thrust decreased between revisions.",
            "The decreased thrust is a modelling assumption.",
            "The recorded thrust remained constant.",
            "Constant thrust from the baseline configuration was retained.",
            "In this saved vertical flight model, the thrust remained constant between saved revisions.",
            "The finding applies only to the stated assumptions: the thrust remained constant from the prior revision.",
            "In this model, the thrust is unchanged.",
            "In this model, the thrust decreased.",
        ):
            with self.subTest(summary=summary):
                flags = change_evidence.evaluate_change_commentary(summary, self.context)
                self.assertTrue(any(flag["code"] == "change_direction_contradiction"
                                    and flag["subject"] == "input:thrust" for flag in flags), summary)

    def test_model_assumption_cannot_exempt_a_different_subject_or_later_claim(self):
        for summary, subject in (
            ("The model assumes constant thrust during the burn, but the thrust decreased between revisions.", "input:thrust"),
            ("The model assumes constant thrust while the declared limit increased.", "declared_limit"),
            ("The model assumes constant thrust and the thrust is unchanged between revisions.", "input:thrust"),
            ("The model assumes constant thrust; the calculated metric decreased.", "calculated_metric"),
            ("In this saved model, with constant thrust the calculated metric decreased.", "calculated_metric"),
        ):
            with self.subTest(summary=summary):
                flags = change_evidence.evaluate_change_commentary(summary, self.context)
                self.assertTrue(any(flag["code"] == "change_direction_contradiction"
                                    and flag["subject"] == subject for flag in flags), summary)


class ChangeDirectionPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        cls.store = WorkspaceStore(cls.folder / "workspace.sqlite3")
        cls.project_id = cls.store.ensure_default()
        baseline = cls.store.get(cls.project_id)
        project = deepcopy(baseline["project"])
        project["inputs"]["maximum_temperature"]["value"] = 250
        cls.store.save_revision(cls.project_id, 1, project)
        cls.view = cls.store.run(cls.project_id, 2)
        cls.good = ("The calculated criterion is not met within the bounded thermal model. "
                    "The declared limit decreased while the calculated metric remained unchanged. "
                    "Review the limit source and physical assumptions.")
        cls.bad = ("The calculated criterion is not met within the bounded thermal model. "
                   "The declared limit increased while the calculated metric remained unchanged. "
                   "Review the limit source and physical assumptions.")

    def record(self, summary):
        def finish_text(message, attempt, tools):
            call = message["tool_calls"][0]["function"]
            if call["name"] == "finish":
                arguments = json.loads(call["arguments"])
                arguments["summary"] = summary
                call["arguments"] = json.dumps(arguments)
            return message
        return investigate_project(self.view, "thermal_limit", "Explain this recorded revision change.",
            ScriptProvider(transform=finish_text), investigation_id="independent-direction-fixture")

    def test_new_pipeline_preserves_good_prose_and_rejects_bad_prose_without_changing_findings(self):
        before = deepcopy(self.view)
        good = self.record(self.good)
        bad = self.record(self.bad)
        self.assertEqual(good["state"], "completed", good.get("error"))
        self.assertEqual(good["change_commentary_policy"], change_evidence.POLICY)
        self.assertEqual(good["evidence_change_context"], change_evidence.context_from_record(good))
        self.assertEqual(good["summary"], self.good)
        self.assertTrue(good["explanation_acceptance"]["accepted"])
        self.assertEqual(bad["state"], "failed")
        self.assertEqual(bad["error_code"], "explanation_rejected")
        self.assertIn("change_direction_contradiction", bad["explanation_acceptance"]["blocked_codes"])
        self.assertEqual(bad["rejected_interpretation"]["summary"], self.bad)
        self.assertEqual(bad["summary"], "")
        self.assertEqual(good["canonical_finding"], bad["canonical_finding"])
        self.assertEqual(self.view, before)
        self.assertEqual(self.store.get(self.project_id, 2), before)

    def test_forged_but_self_hashed_context_is_rederived_from_source_and_rejected(self):
        record = self.record(self.good)
        row = next(row for row in record["evidence_change_context"]["comparisons"]
                   if row["subject"] == "declared_limit")
        row["direction"] = "increased"
        record["evidence_change_context"]["digest"] = _digest({
            k: v for k, v in record["evidence_change_context"].items() if k != "digest"})
        self.assertIn("change_context_mismatch", explanation_acceptance(record)["blocked_codes"])

    def test_changes_cannot_substitute_a_different_current_finding(self):
        record = self.record(self.good)
        record["evidence"]["changes"]["comparison"]["after"]["finding"]["evidence"]["limit"]["value"] = 260
        with self.assertRaises(ValueError):
            change_evidence.context_from_record(record)
        self.assertIn("change_context_mismatch", explanation_acceptance(record)["blocked_codes"])

    def test_provider_wire_contains_qualitative_directions_but_not_withheld_exact_values(self):
        requests = []
        config = LiveConfig("https://api.tokenfactory.nebius.com/v1/", "nvidia/offline-change-fixture",
                            "offline-change-approval", 5, .06, .24, 2048, 45, "native_no_thinking", "forced_action_v1")
        def transport(request):
            wire = json.loads(request.data)
            requests.append(wire)
            return response(selected(wire, len(requests)))
        provider = TokenFactoryProvider(config, BudgetLedger(self.folder / "budget.sqlite3"),
            api_key="synthetic-offline-change-key", transport=transport, action_adapter=ProjectActionAdapter())
        record = investigate_project(self.view, "thermal_limit", "Explain this change.", provider,
                                     investigation_id="independent-change-wire")
        self.assertEqual(record["state"], "completed", record.get("error"))
        final = requests[-1]["messages"]
        contract = json.loads(final[-1]["content"])["explanation_contract"]
        self.assertEqual(contract["change_commentary_policy"], change_evidence.POLICY)
        wire_context = contract["application_change_context"]
        selected_rows = rows(wire_context)
        self.assertEqual(selected_rows["declared_limit"]["direction"], "decreased")
        self.assertEqual(selected_rows["calculated_metric"]["direction"], "unchanged")
        self.assertNotIn("257.68080585928254", json.dumps(final))
        self.assertNotIn("before", selected_rows["declared_limit"])
        self.assertEqual(rows(record["evidence_change_context"])["declared_limit"]["before"]["value"], 320)

    @unittest.skipUnless(LIVE_BATCH.exists(), "The immutable local live receipt is not distributed with source code.")
    def test_actual_legacy_acceptance_preserved_new_policy_reassessment_is_separate(self):
        raw = LIVE_BATCH.read_bytes()
        artifact = json.loads(raw)
        actual = {row["candidate_id"]: row["receipt"] for row in artifact["rows"]
                  if row["case_id"] == "limit-only-change" and row.get("receipt")}
        for candidate, expected in (("super", False), ("ultra", True)):
            historical = actual[candidate]
            self.assertNotIn("change_commentary_policy", historical)
            self.assertTrue(explanation_acceptance(historical)["accepted"])
            reassessment = deepcopy(historical)
            reassessment["change_commentary_policy"] = change_evidence.POLICY
            reassessment["evidence_change_context"] = change_evidence.context_from_record(reassessment)
            acceptance = explanation_acceptance(reassessment)
            self.assertEqual(acceptance["accepted"], expected, candidate)
            self.assertEqual(reassessment["summary"], historical["summary"])
        self.assertEqual(LIVE_BATCH.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
