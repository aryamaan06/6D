"""Adversarial wording cases test bounded rejection, never semantic validation."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sixd import change_evidence, evidence_facts, evidence_roles
from sixd.explanation_quality import evaluate_explanation, explanation_acceptance
from sixd.whole_project_investigation import _quality


def record(status="met", *, current=False, summary=""):
    finding = {"requirement_id": "thermal_limit", "model_id": "thermal",
               "metric": "equilibrium_temperature", "status": status,
               "evidence": {"operator": "<=", "metric": {"value": 250, "unit": "K"},
                            "limit": {"value": 320, "unit": "K"}}}
    scope = {"project_id": "adversarial-wording", "revision": 1,
             "run_id": "frozen-run", "review_digest": "frozen-review"}
    result = {**scope, "requirement_id": "thermal_limit", "finding_status": status,
              "canonical_finding": finding, "summary": summary,
              "evidence": {"requirement:thermal_limit": {
                  **scope, "id": "requirement:thermal_limit", "kind": "requirement",
                  "requirement": {"id": "thermal_limit"}, "finding": deepcopy(finding),
                  "limit": {"value": 320, "unit": "K"}}},
              "citations": ["requirement:thermal_limit"]}
    if current:
        result["evidence_facts_prose_policy"] = evidence_roles.POLICY
        result["evidence_facts"] = evidence_facts.build_fact_catalog(result)
        result["evidence_roles"] = evidence_roles.build_roles(result)
    return result


def resign_current(result):
    """Build a fresh proposed record; never update a saved historical receipt."""
    result["evidence_facts"] = evidence_facts.build_fact_catalog(result)
    result["evidence_roles"] = evidence_roles.build_roles(result)


def change_context(direction):
    # Source quantities are independent held-out thresholds, not solver output.
    before, after = {"increased": (40, 55), "decreased": (55, 40),
                     "unchanged": (40, 40)}[direction]
    def finding(value):
        return {"requirement_id": "force_limit", "model_id": "load", "metric": "force",
                "evidence": {"operator": "<=", "limit": {"value": value, "unit": "N"},
                             "metric": {"value": 30, "unit": "N"}}}
    return change_evidence.build_change_context({"id": "changes", "kind": "changes",
        "comparison": {"scope": {"requirement_id": "force_limit", "model_id": "load"},
                       "before": {"finding": finding(before)},
                       "after": {"finding": finding(after)}}})


class ExplicitStatusRegressionTests(unittest.TestCase):
    def test_all_three_canonical_statuses_reject_each_other_in_both_contract_paths(self):
        phrases = {"met": "is met", "not_met": "is not met",
                   "not_assessed": "is not assessed"}
        for current in (False, True):
            for canonical, wording in phrases.items():
                for claimed, phrase in phrases.items():
                    with self.subTest(current=current, canonical=canonical, claimed=claimed):
                        proposed = record(canonical, current=current,
                            summary=f"This requirement {phrase}. Review the bounded model.")
                        before = deepcopy(proposed)
                        quality = evaluate_explanation(proposed)
                        blocked = explanation_acceptance(proposed)["blocked_codes"]
                        self.assertEqual("canonical_status_contradiction" in blocked,
                                         claimed != canonical, blocked)
                        self.assertFalse(quality["semantic_accuracy_established"])
                        self.assertEqual(proposed, before)

    def test_internal_named_and_contracted_statuses_are_explicit_claims(self):
        for statement in ("Status: not_met.", "The thermal limit is not_met.",
                          "The requirement thermal_limit is unassessed.",
                          "This requirement isn't satisfied.",
                          "This requirement has not been met.",
                          "This requirement has never been met.",
                          "This requirement has not yet been satisfied.",
                          "This requirement has not been assessed.",
                          "The canonical design criterion fails.",
                          "Review scope: this requirement is not met.",
                          "This requirement is not met, which may warrant another review."):
            with self.subTest(statement=statement):
                result = explanation_acceptance(record(summary=statement + " Review bounded evidence."))
                self.assertIn("canonical_status_contradiction", result["blocked_codes"])

    def test_negation_questions_and_future_checks_do_not_assert_changed_statuses(self):
        for statement in ("Review whether this requirement is not met after a justified change.",
                          "If this requirement is not met, inspect the revised inputs.",
                          "This requirement could be unmet after a design change.",
                          "It is not true that this requirement is not met.",
                          "Do not assume that this requirement is not met.",
                          "Don't conclude that this requirement has not been met.",
                          "If this requirement has never been met, inspect the revised inputs.",
                          "We cannot conclude that this requirement is not assessed."):
            with self.subTest(statement=statement):
                result = explanation_acceptance(record(current=True,
                    summary="The criterion is met within the bounded model. " + statement))
                self.assertTrue(result["accepted"], result["blocked_codes"])
        result = explanation_acceptance(record("not_met",
            summary="The requirement is not met. Is this requirement met? Review bounded evidence."))
        self.assertNotIn("canonical_status_contradiction", result["blocked_codes"])
        for status, expected_block in (("met", False), ("not_met", True), ("not_assessed", True)):
            result = explanation_acceptance(record(status,
                summary="This requirement has been met. Review the bounded evidence."))
            self.assertEqual("canonical_status_contradiction" in result["blocked_codes"], expected_block)

    def test_uncertainty_does_not_hide_a_later_conflicting_assertion(self):
        for statement in ("We cannot determine whether this requirement is not met, but this requirement is not met.",
                          "If this requirement is not met, review inputs. This requirement is not met.",
                          "Review whether this requirement is not met; this requirement is not met."):
            with self.subTest(statement=statement):
                result = explanation_acceptance(record(summary=statement + " Inspect bounded evidence."))
                self.assertIn("canonical_status_contradiction", result["blocked_codes"])

    def test_only_exact_attributed_captured_quotes_are_exempt_in_both_paths(self):
        reason = "This requirement is not met."
        for current in (False, True):
            proposed = record(current=current)
            proposed["canonical_finding"]["reason"] = reason
            proposed["evidence"]["requirement:thermal_limit"]["finding"]["reason"] = reason
            if current:
                resign_current(proposed)
            for attributed, expected_block in ((True, False), (False, True)):
                proposed["summary"] = ("The criterion is met. "
                    + ("The requirement finding records a reason: " if attributed else "My conclusion is: ")
                    + repr(reason) + " Review the bounded evidence.")
                before = deepcopy(proposed)
                acceptance = explanation_acceptance(proposed)
                self.assertEqual("canonical_status_contradiction" in acceptance["blocked_codes"], expected_block)
                self.assertEqual(proposed, before)


class LegacyQuantityRegressionTests(unittest.TestCase):
    def test_common_prefixes_are_checked_literally_without_conversion(self):
        for unit in ("km", "km/s", "kN", "MPa", "GPa", "kW", "MJ", "mm", "ms"):
            with self.subTest(unit=unit):
                proposed = record(summary=f"The criterion is met. Review a proposed condition of 7 {unit} within the bounded scope.")
                checked = evaluate_explanation(proposed)
                self.assertEqual(checked["unmatched_quantities"], [f"7 {unit}"])
                # A same-number SI quantity is not evidence for a prefixed unit.
                proposed["canonical_finding"]["evidence"]["metric"] = {"value": 7, "unit": "m"}
                self.assertIn(f"7 {unit}", evaluate_explanation(proposed)["unmatched_quantities"])
        proposed = record(summary="Review the bounded model: 1 km is above 2 km.")
        self.assertIn("literal_comparison_contradiction", explanation_acceptance(proposed)["blocked_codes"])
        proposed["summary"] = "Review the bounded model: 1000 m is above 2 km."
        self.assertNotIn("literal_comparison_contradiction", explanation_acceptance(proposed)["blocked_codes"])

    def test_legacy_grounding_and_current_words_only_contract_stay_distinct(self):
        for current in (False, True):
            proposed = record(current=current, summary="The criterion is met at 250 K. Review the bounded evidence.")
            result = explanation_acceptance(proposed)
            self.assertNotIn("unmatched_quantity", {flag["code"] for flag in result["quality"]["flags"]})
            self.assertEqual("unbound_numeric_literal" in result["blocked_codes"], current)
        proposed = record("not_assessed", summary="The stress will be 4 MPa. Review bounded input sources.")
        proposed["canonical_finding"]["evidence"] = None
        self.assertIn("unsupported_result_prediction", explanation_acceptance(proposed)["blocked_codes"])


class DirectionSynonymRegressionTests(unittest.TestCase):
    def test_held_out_upward_and_downward_vocabulary_follows_exact_changes(self):
        for direction, phrases in (
            ("increased", ("rose", "went up", "has gone up", "climbed", "is larger", "became greater")),
            ("decreased", ("dropped", "declined", "went down", "has gone down", "is smaller"))):
            for phrase in phrases:
                with self.subTest(direction=direction, phrase=phrase):
                    statement = f"The declared limit {phrase} in the saved revision."
                    correct = change_evidence.evaluate_change_commentary(statement, change_context(direction))
                    opposite = "decreased" if direction == "increased" else "increased"
                    wrong = change_evidence.evaluate_change_commentary(statement, change_context(opposite))
                    self.assertEqual(correct, [])
                    self.assertTrue(any(f["code"] == "change_direction_contradiction" for f in wrong), statement)

    def test_relaxation_needs_more_than_scalar_direction_but_recommendations_are_allowed(self):
        context = change_context("increased")
        before = deepcopy(context)
        for statement in ("The declared limit was loosened.", "A relaxed declared limit explains the finding."):
            self.assertIn("change_comparison_unavailable",
                {f["code"] for f in change_evidence.evaluate_change_commentary(statement, context)})
        for statement in ("Consider whether a loosened declared limit is justified.",
                          "The declared limit should not be loosened solely to obtain a pass.",
                          "The declared limit was not loosened.",
                          "A larger declared limit may be justified in a future design.",
                          "A loosened declared limit should be evaluated against its source.",
                          "If the declared limit rose, review source provenance.",
                          "We cannot conclude that the declared limit dropped.",
                          "The declared limit is greater than the calculated metric.",
                          "Review higher-fidelity analysis for the declared limit."):
            self.assertEqual(change_evidence.evaluate_change_commentary(statement, context), [], statement)
        self.assertEqual(context, before)


class WholeProjectPolarityRegressionTests(unittest.TestCase):
    findings = {"thermal_limit": {"status": "met"},
                "burnout_height": {"status": "not_met"},
                "launch_guidance": {"status": "not_assessed"}}

    def test_mixed_statuses_bind_only_to_their_named_requirement(self):
        correct = ("The thermal limit is met; burnout height is not met; launch guidance is not assessed. "
                   "Review the bounded model assumptions.")
        self.assertTrue(_quality(correct, self.findings)["accepted"])
        for statement in ("The thermal limit is not met.", "Burnout height is met.",
                          "Launch guidance is not met.", "The thermal limit is not assessed."):
            self.assertIn("canonical_status_contradiction",
                _quality(statement + " Review bounded evidence.", self.findings)["blocked_codes"])
        for statement in ("Review whether the thermal limit is not met in a future design.",
                          "If burnout height is met after a change, verify the assumptions.",
                          "The thermal limit is met and the vehicle is not ready to launch."):
            self.assertTrue(_quality(statement + " Review bounded evidence.", self.findings)["accepted"], statement)

    def test_blanket_claims_are_checked_in_both_directions(self):
        for statement in ("All requirements are met.", "Everything is not met.",
                          "All checks are not assessed."):
            self.assertIn("blanket_status_contradiction",
                _quality(statement + " Review bounded evidence.", self.findings)["blocked_codes"])
        for statement in ("We cannot claim that all requirements are met.",
                          "Review whether all checks are met.", "If all checks are met, review excluded scope."):
            self.assertNotIn("blanket_status_contradiction", _quality(statement, self.findings)["blocked_codes"])

    def test_whole_project_words_only_direction_guard_handles_synonyms_and_specific_actions(self):
        for phrase in ("rose", "went up", "climbed", "dropped", "declined", "went down",
                       "is larger", "is greater", "was loosened"):
            self.assertIn("direction_or_causality_prose",
                _quality(f"The thrust {phrase}. Review bounded evidence.", self.findings)["blocked_codes"])
        for statement in ("Review higher-fidelity analysis for burnout height within the bounded scope.",
                          "Review higher fidelity analysis for burnout height within the bounded scope.",
                          "If the declared limit rose, verify the source basis within its scope.",
                          "A larger declared limit may be justified; verify its basis within the bounded scope.",
                          "Consider whether a loosened declared limit is justified, then verify its source within the bounded scope."):
            self.assertTrue(_quality(statement, self.findings)["accepted"], statement)
        self.assertIn("direction_or_causality_prose",
            _quality("Review scope: thrust went up.", self.findings)["blocked_codes"])


if __name__ == "__main__":
    unittest.main()
