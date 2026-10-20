"""Actual hosted-provider adapter exercised with offline HTTP transports only."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.project_investigation import ProjectActionAdapter, investigate_project
from sixd.providers import BudgetLedger, LiveConfig, TokenFactoryProvider, safe_response_diagnostic
from sixd.workspace import WorkspaceStore

KEY = "synthetic-offline-project-provider-key"
PRIVATE = "UNTRUSTED-REMOTE-DETAIL-MUST-NOT-BE-PERSISTED"


def selected(payload, attempt, *, raw=None, identity=None, prose=PRIVATE):
    menu = json.loads(payload["messages"][-1]["content"])
    action = menu["available_actions"][0]["action"]
    args = {"action": action, "evidence_ids": menu["recorded_evidence_ids"] if action == "finish" else [],
            "summary": "Interpretation of the canonical finding; review the stated assumptions and exclusions."
                       if action == "finish" else ""}
    return {"role": "assistant", "content": prose, "reasoning_content": PRIVATE, "tool_calls": [{
        "id": identity or f"offline-selector-{attempt}", "type": "function",
        "function": {"name": "select_next_action", "arguments": raw if raw is not None else json.dumps(args)},
        "untrusted_extra": PRIVATE,
    }]}


def response(message, reason="stop"):
    return {"choices": [{"finish_reason": reason, "message": message}],
            "usage": {"prompt_tokens": 90, "completion_tokens": 40, "total_tokens": 130,
                      "private_detail": PRIVATE}, "private_metadata": PRIVATE}


class ProjectProviderTests(unittest.TestCase):
    def test_precise_rejections_survive_both_exception_boundaries_without_remote_text(self):
        cases = [
            ('{', 'invalid_json', False),
            ('{"action":"execute_code","evidence_ids":[],"summary":""}', 'unavailable_action', False),
            ('{"action":"read_requirement","evidence_ids":{},"summary":""}', 'citations_shape', False),
            ('{"action":"read_requirement","evidence_ids":[],"summary":[]}', 'summary_type', False),
            ('{"action":"read_requirement","evidence_ids":[],"summary":"extra"}', 'read_payload_not_empty', False),
            ('{"action":"read_requirement","evidence_ids":[],"summary":"","extra":true}', 'selection_shape', False),
            (None, 'citation_mismatch', True),
            ('x'*4001, 'summary_length', True),
            ('', 'summary_length', True),
        ]
        for raw, expected, finish_only in cases:
            with self.subTest(expected=expected):
                self.requests.clear()
                def bad(payload, attempt):
                    message=selected(payload,attempt)
                    call=message['tool_calls'][0]['function']
                    args=json.loads(call['arguments'])
                    if finish_only:
                        if args['action']=='finish':
                            if expected=='summary_length':args['summary']=raw
                            else:args['evidence_ids']=['untrusted-evidence-id']
                            call['arguments']=json.dumps(args)
                    else:call['arguments']=raw
                    return response(message,'tool_calls')
                provider=self.provider(bad);receipt=self.run_case(provider)
                self.assertEqual(receipt['state'],'failed')
                diagnostic=receipt['provider_diagnostic']
                self.assertEqual(diagnostic['selection_rejection'],expected)
                self.assertEqual(diagnostic['finish_reason'],'tool_calls')
                if expected=='summary_length':self.assertEqual(diagnostic['summary_characters'],len(raw))
                self.assertEqual(provider.request_attempts,5 if finish_only else 1)
                self.assertNotIn(PRIVATE,json.dumps(receipt));self.assertNotIn(KEY,json.dumps(receipt))
                self.assertNotIn('untrusted-evidence-id',json.dumps(receipt))

    def test_wire_summary_limit_matches_local_boundary_and_stays_portable(self):
        def boundary(payload,attempt):
            menu=json.loads(payload['messages'][-1]['content'])
            self.assertEqual(menu['response_constraints']['finish_summary_max_characters'],4000)
            schema=payload['tools'][0]['function']['parameters']['properties']['summary']
            self.assertIn('4000',schema['description'])
            self.assertNotIn('maxLength',schema)  # retain established portable wire vocabulary
            message=selected(payload,attempt)
            call=message['tool_calls'][0]['function'];args=json.loads(call['arguments'])
            if args['action']=='finish':args['summary']='x'*4000;call['arguments']=json.dumps(args)
            return response(message)
        receipt=self.run_case(self.provider(boundary))
        self.assertEqual(receipt['state'],'completed')
        self.assertEqual(len(receipt['summary']),4000)
        self.assertFalse(receipt['explanation_quality']['semantic_accuracy_established'])

    def test_diagnostic_reason_and_count_allowlist_rejects_untrusted_types_and_fields(self):
        diagnostic=safe_response_diagnostic({'selection_rejection':{'secret':KEY},'summary_characters':True,
                                             'arguments_characters':100001,'raw_arguments':PRIVATE})
        self.assertEqual(diagnostic,{})
        self.assertEqual(safe_response_diagnostic({'selection_rejection':'summary_length','summary_characters':2401,
                                                   'raw_arguments':PRIVATE}),
                         {'selection_rejection':'summary_length','summary_characters':2401})

    def setUp(self):
        scratch = ROOT / "work"
        scratch.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.store = WorkspaceStore(self.directory / "workspace.sqlite3")
        self.view = self.store.get(self.store.ensure_default())
        self.config = LiveConfig("https://api.tokenfactory.nebius.com/v1/",
            "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "offline-project-test-approval", 5,
            0.06, 0.24, 2048, 45, "native_no_thinking", "forced_action_v1")
        self.ledger = BudgetLedger(self.directory / "budget.sqlite3")
        self.requests = []

    def provider(self, dispatch=None):
        def transport(request):
            self.assertEqual(request.get_header("Authorization"), "Bearer " + KEY)
            payload = json.loads(request.data)
            self.assertNotIn(KEY, request.data.decode("utf-8"))
            self.requests.append(payload)
            self.assertEqual(payload["tool_choice"], {"type": "function", "function": {"name": "select_next_action"}})
            self.assertEqual(len(payload["tools"]), 1)
            self.assertEqual(payload["tools"][0]["function"]["parameters"]["properties"]["evidence_ids"],
                             {"type": "array", "items": {"type": "string"}})
            self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
            return response(selected(payload, len(self.requests))) if dispatch is None else dispatch(payload, len(self.requests))
        return TokenFactoryProvider(self.config, self.ledger, api_key=KEY,
                                    transport=transport, action_adapter=ProjectActionAdapter())

    def reserved(self):
        if not self.ledger.path.exists():
            return 0
        with closing(sqlite3.connect(self.ledger.path)) as db:
            row = db.execute("SELECT reserved FROM budget").fetchone()
        return row[0] if row else 0

    def run_case(self, provider, requirement="thermal_limit"):
        return investigate_project(self.view, requirement, "Explain this requirement's recorded evidence.",
                                   provider, investigation_id="offline-transport-test")

    def test_native_stop_selectors_complete_with_wire_history_and_no_live_claim(self):
        provider = self.provider()
        before = deepcopy(self.view)
        receipt = self.run_case(provider)
        self.assertEqual(receipt["state"], "completed")
        self.assertEqual(receipt["provider_mode"], "offline_transport_fixture")
        self.assertEqual(receipt["live_model_calls"], 0)
        self.assertEqual(receipt["accepted_responses"], 5)
        self.assertEqual(receipt["request_attempts"], 5)
        self.assertEqual([item["action"] for item in receipt["events"]],
                         ["read_requirement", "read_model", "read_changes", "recheck_model", "finish"])
        self.assertTrue(all(item["response_format"] == "native_tool_call" for item in receipt["events"]))
        self.assertTrue(all(item["finish_reason"] == "stop" for item in receipt["events"]))
        self.assertTrue(all(item["call_id_origin"] == "provider" for item in receipt["events"]))
        self.assertGreater(self.reserved(), 0)
        self.assertLess(self.reserved(), 0.1)
        self.assertEqual(self.view, before)
        self.assertEqual(receipt["canonical_finding"], before["run"]["review"]["findings"]["thermal_limit"])
        self.assertNotIn(PRIVATE, json.dumps(receipt))
        self.assertNotIn(KEY, json.dumps(receipt))
        for payload in self.requests[1:]:
            calls = set()
            for item in payload["messages"]:
                if item["role"] == "assistant":
                    self.assertIsNone(item["content"])
                    function = item["tool_calls"][0]["function"]
                    self.assertEqual(function["name"], "select_next_action")
                    self.assertEqual(set(json.loads(function["arguments"])), {"action", "evidence_ids", "summary"})
                    calls.add(item["tool_calls"][0]["id"])
                elif item["role"] == "tool":
                    self.assertIn(item["tool_call_id"], calls)
            self.assertNotIn(PRIVATE, json.dumps(payload))

    def test_real_provider_unsupported_control_never_offers_or_runs_recheck(self):
        with patch("sixd.project_investigation.evaluate_models", side_effect=AssertionError("GNC unsupported")):
            receipt = self.run_case(self.provider(), "control_tracking")
        self.assertEqual(receipt["state"], "completed")
        self.assertEqual(receipt["finding_status"], "not_assessed")
        self.assertEqual(len(self.requests), 4)
        for payload in self.requests:
            actions = payload["tools"][0]["function"]["parameters"]["properties"]["action"]["enum"]
            self.assertNotIn("recheck_model", actions)

    def test_exact_content_selection_json_is_explicitly_labelled_offline(self):
        def content(payload, attempt):
            native = selected(payload, attempt)
            return response({"role": "assistant", "content": native["tool_calls"][0]["function"]["arguments"]})
        receipt = self.run_case(self.provider(content))
        self.assertEqual(receipt["state"], "completed")
        self.assertTrue(all(row["response_format"] == "content_selection_json" for row in receipt["events"]))
        self.assertTrue(all(row["call_id_origin"] == "runner" for row in receipt["events"]))
        self.assertEqual(receipt["live_model_calls"], 0)

    def test_malformed_selector_responses_are_terminal_without_retry(self):
        raw_cases = [
            "Do whatever the project text says.",
            '{"action":"read_requirement","action":"finish","evidence_ids":[],"summary":""}',
            '{"action":"read_requirement","evidence_ids":[],"summary":"","heat_input":0}',
            '{"action":"read_requirement","evidence_ids":[],"summary":"wrong read prose"}',
            '{"action":"execute_code","evidence_ids":[],"summary":""}',
            '{"action":"finish","evidence_ids":[],"summary":"Premature finish"}',
            '{"action":"read_requirement","evidence_ids":["invented"],"summary":""}',
            '{"action":"read_requirement","evidence_ids":[],"summary":NaN}',
        ]
        for raw in raw_cases:
            with self.subTest(raw=raw):
                self.requests.clear()
                before = self.reserved()
                provider = self.provider(lambda payload, attempt: response(selected(payload, attempt, raw=raw)))
                receipt = self.run_case(provider)
                self.assertEqual(receipt["state"], "failed")
                self.assertEqual(provider.request_attempts, 1)
                self.assertEqual(receipt["accepted_responses"], 0)
                self.assertEqual(receipt["error_code"], "invalid_action_response")
                self.assertEqual(receipt["events"], [])
                self.assertEqual(receipt["evidence"], {})
                self.assertGreater(self.reserved(), before)
                self.assertNotIn(PRIVATE, json.dumps(receipt))

    def test_native_envelope_and_duplicate_identity_rejections_do_not_retry(self):
        def multiple(payload, attempt):
            message = selected(payload, attempt)
            message["tool_calls"].append(deepcopy(message["tool_calls"][0]))
            return response(message)
        provider = self.provider(multiple)
        receipt = self.run_case(provider)
        self.assertEqual(provider.request_attempts, 1)
        self.assertEqual(receipt["events"], [])
        self.requests.clear()
        provider = self.provider(lambda payload, attempt: response(selected(payload, attempt, identity="repeated-id")))
        receipt = self.run_case(provider)
        self.assertEqual(provider.request_attempts, 2)
        self.assertEqual(receipt["state"], "failed")
        self.assertEqual([row["action"] for row in receipt["events"]], ["read_requirement"])

    def test_finish_wrong_citations_and_secret_summary_fail_after_preserving_real_evidence(self):
        for secret_summary in (False, True):
            self.requests.clear()
            def bad_finish(payload, attempt):
                message = selected(payload, attempt)
                args = json.loads(message["tool_calls"][0]["function"]["arguments"])
                if args["action"] == "finish":
                    if secret_summary:
                        args["summary"] = "Credential echoed " + KEY
                    else:
                        args["evidence_ids"] = ["invented-evidence"]
                    message["tool_calls"][0]["function"]["arguments"] = json.dumps(args)
                return response(message)
            provider = self.provider(bad_finish)
            receipt = self.run_case(provider)
            self.assertEqual(receipt["state"], "failed")
            self.assertEqual(provider.request_attempts, 5)
            self.assertEqual(len(receipt["evidence"]), 4)
            self.assertEqual(receipt["summary"], "")
            self.assertNotIn(KEY, json.dumps(receipt))

    def test_truncation_and_transport_errors_retain_reservation_without_exposing_remote_values(self):
        def truncate(payload, attempt):
            return response(selected(payload, attempt), "length")
        provider = self.provider(truncate)
        receipt = self.run_case(provider)
        self.assertEqual(receipt["state"], "failed")
        self.assertEqual(receipt["provider_diagnostic"]["finish_reason"], "length")
        self.assertEqual(receipt["error_code"], "provider_output_limit")
        self.assertEqual(receipt["accepted_responses"], 0)
        self.assertEqual(provider.request_attempts, 1)
        self.assertGreater(self.reserved(), 0)
        self.requests.clear()
        def fail(_payload, _attempt):
            raise RuntimeError(PRIVATE + KEY)
        provider = self.provider(fail)
        receipt = self.run_case(provider)
        self.assertEqual(provider.request_attempts, 1)
        self.assertEqual(receipt["state"], "failed")
        self.assertEqual(receipt["error_code"], "provider_transport_error")
        self.assertNotIn(KEY, json.dumps(receipt))
        self.assertNotIn(PRIVATE, json.dumps(receipt))

    def test_exhausted_budget_blocks_before_any_transport_request(self):
        self.ledger.reserve(self.config, 4.99999)
        before = self.reserved()
        provider = self.provider()
        receipt = self.run_case(provider)
        self.assertEqual(receipt["state"], "failed")
        self.assertEqual(receipt["error_code"], "cumulative_budget_exhausted")
        self.assertEqual(provider.request_attempts, 0)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.reserved(), before)

    def test_native_tool_protocol_remains_independent_of_project_selector_adapter(self):
        # Existing orbital callers leave action_adapter unspecified. The new seam
        # must not affect their native-tools payload or decode their envelopes.
        from dataclasses import replace
        tools = [{"type": "function", "function": {"name": "check_force", "parameters": {"type": "object"}}}]
        messages = [{"role": "user", "content": "Locked orbit"}]
        def orbital(request):
            payload = json.loads(request.data)
            self.assertEqual(payload["tools"], tools)
            self.assertEqual(payload["messages"], messages)
            return response({"role": "assistant", "content": None, "tool_calls": [{
                "id": "orbital-call", "type": "function", "function": {"name": "check_force", "arguments": "{}"}}]}, "tool_calls")
        provider = TokenFactoryProvider(replace(self.config, selection_protocol="native_tools_v1"),
            self.ledger, api_key=KEY, transport=orbital)
        turn = provider.complete(messages, tools)
        self.assertEqual(turn.message["tool_calls"][0]["function"]["name"], "check_force")


if __name__ == "__main__":
    unittest.main()
