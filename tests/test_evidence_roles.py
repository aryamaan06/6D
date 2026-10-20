"""Typed numerical roles remain authoritative while commentary is qualitative."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import evidence_roles, evidence_facts, evidence_evaluation
from sixd.project_investigation import investigate_project, ProjectActionAdapter
from sixd.project_examples import example_projects
from sixd.explanation_quality import explanation_acceptance
from sixd.providers import LiveConfig, TokenFactoryProvider, BudgetLedger
from sixd.workspace import WorkspaceStore
from test_project_investigation import ScriptProvider
from test_project_provider import selected, response


class ApplicationRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / "work")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        cls.store = WorkspaceStore(cls.folder / "workspace.sqlite3")
        cls.project = example_projects()["orbital_review"]
        cls.store.create_project(cls.project)
        cls.view = cls.store.run(cls.project["project_id"], 1)
        cls.record = investigate_project(cls.view, "orbit_max_radius", "Explain this finding.",
            ScriptProvider(), investigation_id="role-fixture")
        if cls.record["state"] != "completed":
            raise AssertionError(cls.record)

    def test_metric_limit_and_grid_roles_use_exact_paths_and_keep_pairs(self):
        rec = self.record
        self.assertEqual(rec["evidence_facts_prose_policy"], evidence_roles.POLICY)
        facts = {f["id"]: f for f in rec["evidence_facts"]["facts"]}
        roles = {r["role"]: facts[r["fact_id"]] for r in rec["evidence_roles"]["roles"]}
        self.assertEqual(roles["calculated_metric"]["pointer"], "/finding/evidence/metric/value")
        self.assertEqual(roles["declared_limit"]["pointer"], "/limit/value")
        self.assertEqual(roles["declared_limit"]["value"], 7100000)
        for pair, steps in (("coarse_to_middle", (512, 1024)), ("middle_to_fine", (1024, 2048))):
            f = roles["position_difference_" + pair]
            self.assertEqual((f["context"]["coarse_steps"], f["context"]["fine_steps"]), steps)
        self.assertTrue(rec["explanation_acceptance"]["accepted"])
        self.assertFalse(rec["explanation_quality"]["semantic_accuracy_established"])

    def test_valid_final_radius_fact_cannot_be_forged_into_limit_role(self):
        rec = deepcopy(self.record)
        final = next(f for f in rec["evidence_facts"]["facts"] if f["pointer"] == "/recorded_evidence/metrics/final_radius_m/value")
        role = next(r for r in rec["evidence_roles"]["roles"] if r["role"] == "declared_limit")
        role["fact_id"] = final["id"]
        rec["evidence_roles"]["digest"] = evidence_facts._digest({k:v for k,v in rec["evidence_roles"].items() if k != "digest"})
        self.assertIn("fact_catalog_mismatch", explanation_acceptance(rec)["blocked_codes"])

    def test_actual_failure_shapes_stay_rejected_without_rewriting_their_text(self):
        for text in (
            "The criterion is met at 7000032.9432812715 m against 7100000 m. Review scope.",
            "The criterion is met. Inspect [[fact:f96828357bf4fbd952aecf8fc]].",
            "Inspect [[fact:faaaa], [fact:fbbbb]] within the bounded model."):
            rec = deepcopy(self.record); rec["summary"] = text
            result = explanation_acceptance(rec)
            self.assertFalse(result["accepted"])
            self.assertEqual(rec["summary"], text)

    def test_wire_discloses_withheld_values_and_final_action_gives_words_only_example(self):
        requests = []
        config = LiveConfig("https://api.tokenfactory.nebius.com/v1/", "nvidia/offline-nemotron-roles",
                            "offline-role-approval", 5, .06, .24, 2048, 45, "native_no_thinking", "forced_action_v1")
        def transport(request):
            wire = json.loads(request.data); requests.append(wire)
            return response(selected(wire, len(requests)))
        provider = TokenFactoryProvider(config, BudgetLedger(self.folder / "budget.sqlite3"),
            api_key="synthetic-role-provider-key", transport=transport, action_adapter=ProjectActionAdapter())
        before = deepcopy(self.view)
        rec = investigate_project(self.view, "orbit_max_radius", "Explain this finding.", provider,
                                  investigation_id="role-wire")
        self.assertEqual(rec["state"], "completed", rec.get("error"))
        wire_text = json.dumps(requests[-1]["messages"])
        self.assertNotIn("7000032.9432812715", wire_text)
        self.assertIn("withheld", wire_text)
        menu = json.loads(requests[-1]["messages"][-1]["content"])
        self.assertEqual(menu["explanation_contract"]["policy"], evidence_roles.POLICY)
        self.assertIn("words only", menu["explanation_contract"]["instruction"])
        self.assertEqual(menu["explanation_contract"]["canonical_status"], "met")
        self.assertEqual(self.view, before)
        captured = rec["evidence"]["model:orbit"]["recorded_evidence"]["metrics"]["max_radius_m"]["value"]
        self.assertEqual(captured, 7000032.9432812715)

    def test_projection_is_read_only_and_preserves_booleans_status_and_context(self):
        source = {"kind": "recheck", "matches_saved_result": True,
                  "finding": {"status": "not_assessed", "evidence": None},
                  "metric": {"value": -1.2e-6, "unit": "m"}, "source": "Untrusted label"}
        before = deepcopy(source)
        view = evidence_roles.qualitative_projection(source)
        self.assertEqual(source, before)
        self.assertIs(view["matches_saved_result"], True)
        self.assertEqual(view["finding"]["status"], "not_assessed")
        self.assertNotEqual(view["metric"]["value"], -1.2e-6)
        self.assertIn("withheld", view["numerical_context_disclosure"])

    def test_plain_canonical_status_contradiction_is_rejected_but_review_question_is_not(self):
        record = deepcopy(self.record)
        record["summary"] = "The calculated criterion is not met within this bounded model. Review the input sources."
        self.assertIn("canonical_status_contradiction", explanation_acceptance(record)["blocked_codes"])
        record["summary"] = "The criterion is met within its scope. Review whether the criterion is not met after a justified change."
        self.assertNotIn("canonical_status_contradiction", explanation_acceptance(record)["blocked_codes"])

    def test_current_role_report_reader_preserves_historical_policy(self):
        report = {"schema": "sixd.evidence-evaluation-report.v1", "explanation_policy": "evidence_links_v1",
                  "candidates": [], "rows": [], "mode": "live_comparison"}
        report["report_digest"] = evidence_evaluation.baseline._digest(report)
        before = deepcopy(report)
        card = evidence_evaluation.scorecard(report)
        self.assertEqual(card["explanation_policy"], "evidence_links_v1")
        self.assertEqual(report, before)

    def test_new_contract_never_accepts_model_supplied_numeric_role_fields(self):
        def extra(message, attempt, tools):
            call = message["tool_calls"][0]["function"]
            if call["name"] == "finish":
                args = json.loads(call["arguments"])
                args["evidence_roles"] = {"declared_limit": "final_radius"}
                call["arguments"] = json.dumps(args)
            return message
        rec = investigate_project(self.view, "orbit_max_radius", "Explain.",
            ScriptProvider(transform=extra), investigation_id="forged-role")
        self.assertEqual(rec["state"], "failed")
        self.assertEqual(rec["error_code"], "invalid_action_response")


if __name__ == "__main__":
    unittest.main()
