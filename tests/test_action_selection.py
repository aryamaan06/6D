"""Offline action-selector wire replay, evidence protection and budget tests."""
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.action_selection import (WIRE_TOOL, PROTOCOL, build_action_request,
                                   decode_action_message)
from sixd.examples import EXAMPLES
import sixd.investigation as investigation_module
from sixd.investigation import investigate, remaining_tools
from sixd.kernel import audit
from sixd.providers import BudgetLedger, LiveConfig, ProviderError, TokenFactoryProvider
from sixd.reporting import verify_payload

TEST_KEY = 'synthetic-offline-action-selection-only'
PRIVATE_VALUE = 'PRIVATE-ARGUMENT-MUST-NOT-BECOME-RECORDED-EVIDENCE'
FREEFORM_VALUE = 'UNTRUSTED-PROSE-MUST-NOT-BECOME-RECORDED-EVIDENCE'
EULER_CHECKS = {'check_force': None, 'check_refinement': None}
VERLET_CHECKS = {**EULER_CHECKS, 'check_reversibility': None}
EULER_IDS = ['analytic_reference_refinement', 'central_force_reference']


def message(action='check_force', ids=None, identity='offline-action-1', *, raw=None):
    return {'role': 'assistant', 'content': FREEFORM_VALUE, 'tool_calls': [{
        'id': identity, 'type': 'function', 'function': {
            'name': WIRE_TOOL, 'arguments': raw if raw is not None else json.dumps({
                'action': action, 'evidence_ids': [] if ids is None else ids}),
        },
        'private_metadata': PRIVATE_VALUE,
    }], 'reasoning_content': FREEFORM_VALUE}


def response(selected):
    return {'choices': [{'finish_reason': 'tool_calls', 'message': selected}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}}


def check_menu(checks=EULER_CHECKS, executed=None):
    return remaining_tools(checks, set() if executed is None else executed, {})


def finish_menu(ids=EULER_IDS):
    return remaining_tools(EULER_CHECKS, set(EULER_CHECKS), {key: {} for key in ids})


class ActionSelectionUnitTests(unittest.TestCase):
    def test_actual_wire_menu_forces_one_selector_and_dynamic_applicable_actions(self):
        for checks, expected in ((EULER_CHECKS, set(EULER_CHECKS)),
                                 (VERLET_CHECKS, set(VERLET_CHECKS))):
            with self.subTest(checks=checks):
                original = [{'role': 'system', 'content': 'Canonical runner policy.'},
                            {'role': 'user', 'content': 'Locked design inputs.'}]
                snapshot = deepcopy(original)
                messages, tools, choice = build_action_request(original, check_menu(checks))
                self.assertEqual(original, snapshot)
                self.assertEqual(len(tools), 1)
                self.assertEqual(tools[0]['function']['name'], WIRE_TOOL)
                self.assertEqual(choice, {'type': 'function', 'function': {'name': WIRE_TOOL}})
                schema = tools[0]['function']['parameters']
                self.assertEqual(set(schema['required']), {'action', 'evidence_ids'})
                self.assertIs(schema['additionalProperties'], False)
                self.assertEqual(set(schema['properties']['action']['enum']), expected)
                self.assertEqual(schema['properties']['evidence_ids']['maxItems'], 0)
                self.assertEqual([item['role'] for item in messages].count('system'), 1)
                self.assertIn(snapshot[1], messages)

    def test_finish_wire_schema_uses_exact_recorded_ids_and_no_check_actions(self):
        _, tools, _ = build_action_request([], finish_menu())
        schema = tools[0]['function']['parameters']['properties']
        self.assertEqual(schema['action']['enum'], ['finish'])
        self.assertEqual(schema['evidence_ids']['items']['enum'], EULER_IDS)
        self.assertEqual(schema['evidence_ids']['minItems'], len(EULER_IDS))
        self.assertEqual(schema['evidence_ids']['maxItems'], len(EULER_IDS))
        self.assertIs(schema['evidence_ids']['uniqueItems'], True)

    def test_valid_check_decodes_only_action_with_locked_inputs(self):
        decoded, problem = decode_action_message(message(), check_menu())
        self.assertIsNone(problem)
        self.assertEqual(decoded, {'role': 'assistant', 'content': None, 'tool_calls': [{
            'id': 'offline-action-1', 'type': 'function',
            'function': {'name': 'check_force', 'arguments': '{}'},
        }]})
        self.assertNotIn(PRIVATE_VALUE, json.dumps(decoded))
        self.assertNotIn(FREEFORM_VALUE, json.dumps(decoded))

    def test_valid_finish_preserves_original_call_id_and_actual_evidence_ids(self):
        selected = message('finish', list(reversed(EULER_IDS)), identity='offline-finish')
        decoded, problem = decode_action_message(selected, finish_menu())
        self.assertIsNone(problem)
        call = decoded['tool_calls'][0]
        self.assertEqual(call['id'], 'offline-finish')
        self.assertEqual(call['function']['name'], 'finish')
        self.assertEqual(json.loads(call['function']['arguments']),
                         {'evidence_ids': list(reversed(EULER_IDS))})

    def test_semantic_errors_return_controlled_problem_without_echoing_values(self):
        bad_selections = [
            {'action': 'check_force'},
            {'action': 'check_force', 'evidence_ids': [], 'radius': PRIVATE_VALUE},
            {'action': 'check_force', 'evidence_ids': [PRIVATE_VALUE]},
            {'action': 'check_force', 'evidence_ids': {}},
            {'action': [], 'evidence_ids': []},
            {'action': 'finish', 'evidence_ids': []},
            {'action': 'check_reversibility', 'evidence_ids': []},
            [], None, PRIVATE_VALUE,
        ]
        for selected in bad_selections:
            with self.subTest(selection=selected):
                decoded, problem = decode_action_message(message(raw=json.dumps(selected)), check_menu())
                self.assertEqual(problem['code'], 'invalid_action_selection')
                self.assertNotIn(PRIVATE_VALUE, json.dumps(problem))
                self.assertEqual(decoded['tool_calls'][0]['id'], 'offline-action-1')
                self.assertEqual(decoded['tool_calls'][0]['function']['name'], WIRE_TOOL)
                self.assertIsNone(decoded['content'])
                self.assertNotIn('reasoning_content', decoded)

    def test_duplicate_json_keys_and_nonfinite_values_are_nonexecuted_semantic_errors(self):
        for raw in ('{"action":"check_force","action":"finish","evidence_ids":[]}',
                    '{"action":"check_force","evidence_ids":[],"evidence_ids":[]}',
                    '{"action":"check_force","evidence_ids":NaN}',
                    '{"action":"check_force","evidence_ids":Infinity}',
                    '{"action":', 'not-json'):
            with self.subTest(raw=raw):
                decoded, problem = decode_action_message(message(raw=raw), check_menu())
                self.assertEqual(problem['code'], 'invalid_action_selection')
                self.assertEqual(decoded['tool_calls'][0]['function']['arguments'], raw)

    def test_finish_cannot_cite_duplicate_missing_or_invented_evidence(self):
        for ids in ([], EULER_IDS[:1], [EULER_IDS[0], EULER_IDS[0]],
                    EULER_IDS + [PRIVATE_VALUE], [PRIVATE_VALUE], [True, 2]):
            with self.subTest(ids=ids):
                _, problem = decode_action_message(message('finish', ids), finish_menu())
                self.assertEqual(problem['code'], 'invalid_action_selection')
                self.assertNotIn(PRIVATE_VALUE, json.dumps(problem))

    def test_bad_envelope_identity_or_unknown_wire_tool_fails_terminally(self):
        invalid = [None, {}, {'role': 'user', 'tool_calls': []}]
        for change in ('wrong-tool', 'bad-id', 'missing-id', 'multiple-calls', 'wrong-type'):
            item = message()
            call = item['tool_calls'][0]
            if change == 'wrong-tool':
                call['function']['name'] = PRIVATE_VALUE
            elif change == 'bad-id':
                call['id'] = 'invalid/' + PRIVATE_VALUE
            elif change == 'missing-id':
                del call['id']
            elif change == 'multiple-calls':
                item['tool_calls'].append(deepcopy(call))
            else:
                call['type'] = PRIVATE_VALUE
            invalid.append(item)
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ProviderError) as caught:
                decode_action_message(item, check_menu())
            self.assertNotIn(PRIVATE_VALUE, str(caught.exception))

    def test_history_rewrites_canonical_actions_preserving_response_pairings(self):
        canonical = {'role': 'assistant', 'content': FREEFORM_VALUE, 'tool_calls': [{
            'id': 'completed-force', 'type': 'function',
            'function': {'name': 'check_force', 'arguments': '{}'},
        }]}
        evidence = {'role': 'tool', 'tool_call_id': 'completed-force',
                    'content': '{"id":"central_force_reference","status":"pass"}'}
        original = [canonical, evidence]
        snapshot = deepcopy(original)
        messages, tools, _ = build_action_request(original,
                                                  check_menu(executed={'check_force'}))
        self.assertEqual(original, snapshot)
        prior = next(item for item in messages if item['role'] == 'assistant')
        call = prior['tool_calls'][0]
        self.assertEqual(call['id'], 'completed-force')
        self.assertEqual(call['function']['name'], WIRE_TOOL)
        self.assertEqual(json.loads(call['function']['arguments']),
                         {'action': 'check_force', 'evidence_ids': []})
        self.assertIsNone(prior['content'])
        self.assertIn(evidence, messages)
        self.assertEqual(tools[0]['function']['parameters']['properties']['action']['enum'],
                         ['check_refinement'])

    def test_rejected_wire_history_keeps_its_original_call_id_for_correction(self):
        invalid = message(raw=json.dumps({'action': 'check_force', 'evidence_ids': [],
                                         'radius': PRIVATE_VALUE}), identity='rejected-selector')
        sanitized, problem = decode_action_message(invalid, check_menu())
        reply = {'role': 'tool', 'tool_call_id': 'rejected-selector',
                 'content': json.dumps({'error': problem, 'retry_allowed': True})}
        messages, _, _ = build_action_request([sanitized, reply], check_menu())
        prior = next(item for item in messages if item['role'] == 'assistant')
        self.assertEqual(prior['tool_calls'][0]['id'], reply['tool_call_id'])
        self.assertEqual(prior['tool_calls'][0]['function']['arguments'],
                         sanitized['tool_calls'][0]['function']['arguments'])
        self.assertIn(reply, messages)


class ActionSelectionIntegrationTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / 'work'
        scratch.mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(directory.cleanup)
        self.local = Path(directory.name)
        self.config = LiveConfig(
            'https://api.tokenfactory.nebius.com/v1',
            'nvidia/offline-nemotron-action-test', 'offline-action-tests-only',
            5.0, 0.06, 0.24, 8192, 180,
            inference_profile='nebius_no_reasoning', selection_protocol=PROTOCOL,
        )
        self.ledger = BudgetLedger(self.local / 'budget.sqlite3')
        self.requests = []

    def reserved(self):
        if not self.ledger.path.exists():
            return 0.0
        with closing(sqlite3.connect(self.ledger.path)) as db:
            row = db.execute('SELECT id, cap, reserved FROM budget').fetchone()
        self.assertEqual(row[:2], (self.config.approval_id, 5.0))
        return row[2]

    def config_load(self, value='missing'):
        data = {**self.config.__dict__, 'account_verified': True,
                'model_license_reviewed': True, 'spend_approved': True}
        if value == 'missing':
            data.pop('selection_protocol')
        else:
            data['selection_protocol'] = value
        path = self.local / 'offline-config.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return LiveConfig.load(path)

    def provider(self, select):
        def transport(request):
            payload = json.loads(request.data)
            self.requests.append(payload)
            self.assertNotIn(TEST_KEY, request.data.decode('utf-8'))
            self.assertEqual(payload['tool_choice'],
                             {'type': 'function', 'function': {'name': WIRE_TOOL}})
            self.assertEqual(len(payload['tools']), 1)
            self.assertEqual(payload['tools'][0]['function']['name'], WIRE_TOOL)
            self.assertEqual(payload['max_tokens'], 8192)
            self.assertEqual(payload['reasoning_effort'], 'none')
            self.assertEqual(payload['model'], self.config.model)
            return response(select(payload, len(self.requests)))
        return TokenFactoryProvider(self.config, self.ledger, api_key=TEST_KEY, transport=transport)

    def assert_independent_findings(self, report, example):
        baseline = audit(example)
        for key in ('checks', 'findings', 'verdict', 'summary', 'audit_id',
                    'not_tested', 'contract_sha256'):
            self.assertEqual(report[key], baseline[key], key)
        self.assertEqual(report['model_mode'], 'offline_transport_fixture')
        self.assertEqual(report['live_model_calls'], 0)
        self.assertNotIn(PRIVATE_VALUE, json.dumps(report))
        self.assertNotIn(FREEFORM_VALUE, json.dumps(report))
        verify_payload(report)

    def test_config_defaults_to_native_and_allows_only_explicit_protocol_names(self):
        self.assertEqual(self.config_load().selection_protocol, 'native_tools_v1')
        for value in ('native_tools_v1', PROTOCOL):
            self.assertEqual(self.config_load(value).selection_protocol, value)
        for value in (None, True, 0, [], {}, '', 'forced', PRIVATE_VALUE):
            with self.subTest(value=value), self.assertRaises(ProviderError) as caught:
                self.config_load(value)
            self.assertNotIn(PRIVATE_VALUE, str(caught.exception))

    def test_one_bounded_wire_replay_corrects_then_completes_three_distinct_kernel_cases(self):
        self.ledger.reserve(self.config, 0.5)
        previous_reservation = self.reserved()
        for case in ('euler_method_limit', 'verlet_correct', 'force_sign_error'):
            with self.subTest(case=case):
                self.requests = []
                def select(payload, attempt):
                    schema = payload['tools'][0]['function']['parameters']['properties']
                    actions = schema['action']['enum']
                    if attempt == 1:
                        return message(raw=json.dumps({'action': actions[0], 'evidence_ids': [],
                            'radius': PRIVATE_VALUE}), identity=f'{case}-rejected')
                    action = actions[0]
                    ids = schema['evidence_ids']['items'].get('enum', []) if action == 'finish' else []
                    return message(action, ids, identity=f'{case}-accepted-{attempt}')
                provider = self.provider(select)
                example = EXAMPLES[case]
                report = investigate(example, provider)
                run = report['investigation']
                self.assertEqual(run['state'], 'completed')
                self.assertEqual(run['selection_protocol'], PROTOCOL)
                self.assertEqual(run['protocol_corrections'], 1)
                self.assertEqual(run['protocol_rejections'], 1)
                checks = 2 if case == 'euler_method_limit' else 3
                self.assertEqual(provider.request_attempts, checks + 2)
                self.assertEqual(run['provider_successes'], checks + 2)
                self.assertEqual(len(run['usage']), checks + 2)
                rejected = [item for item in run['trace'] if item['status'] == 'rejected']
                self.assertEqual(len(rejected), 1)
                self.assertEqual(rejected[0]['error_code'], 'invalid_action_selection')
                self.assertNotIn('arguments', rejected[0])
                for event in run['trace']:
                    if event['status'] != 'rejected':
                        self.assertEqual(event['selection_protocol'], PROTOCOL)
                        self.assertEqual(event['wire_tool'], WIRE_TOOL)
                # Every historical assistant selector still matches its tool reply.
                for payload in self.requests[1:]:
                    assistant_ids = []
                    for history in payload['messages']:
                        if history['role'] == 'assistant':
                            for call in history['tool_calls']:
                                self.assertEqual(call['function']['name'], WIRE_TOOL)
                                assistant_ids.append(call['id'])
                        elif history['role'] == 'tool':
                            self.assertIn(history['tool_call_id'], assistant_ids)
                            if history['tool_call_id'].endswith('-rejected'):
                                feedback = json.loads(history['content'])
                                self.assertEqual(feedback['error']['code'], 'invalid_action_selection')
                                self.assertNotIn(PRIVATE_VALUE, history['content'])
                menus = [set(payload['tools'][0]['function']['parameters']['properties']['action']['enum'])
                         for payload in self.requests]
                self.assertEqual(menus[0], menus[1], 'The rejected action must not consume a check.')
                self.assertEqual(menus[-1], {'finish'})
                self.assert_independent_findings(report, example)
                self.assertGreater(self.reserved(), previous_reservation)
                previous_reservation = self.reserved()

    def test_repeated_semantic_rejection_exhausts_one_correction_without_executing_checks(self):
        def select(payload, attempt):
            return message(raw='{"action":"check_force","action":"finish","evidence_ids":[]}',
                           identity=f'offline-repeated-{attempt}')
        provider = self.provider(select)
        traps = {name: Mock(side_effect=AssertionError('Rejected selections must not execute checks.'))
                 for name in VERLET_CHECKS}
        with patch.dict(investigation_module.CHECKS, traps):
            report = investigate(EXAMPLES['euler_method_limit'], provider)
        run = report['investigation']
        self.assertEqual(run['state'], 'failed')
        self.assertEqual(run['protocol_corrections'], 1)
        self.assertEqual(run['protocol_rejections'], 2)
        self.assertEqual(provider.request_attempts, 2)
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(all(row['status'] == 'rejected' for row in run['trace']))
        for trap in traps.values():
            trap.assert_not_called()
        self.assertGreater(self.reserved(), 0)
        self.assert_independent_findings(report, EXAMPLES['euler_method_limit'])

    def test_unknown_wire_tool_is_terminal_without_a_semantic_retry(self):
        def select(payload, attempt):
            result = message(identity='offline-unknown-tool')
            result['tool_calls'][0]['function']['name'] = PRIVATE_VALUE
            return result
        provider = self.provider(select)
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        run = report['investigation']
        self.assertEqual(run['state'], 'failed')
        self.assertEqual(run['provider_successes'], 0)
        self.assertEqual(run['protocol_corrections'], 0)
        self.assertEqual(run['trace'], [])
        self.assertEqual(provider.request_attempts, 1)
        self.assertEqual(len(self.requests), 1)
        self.assert_independent_findings(report, EXAMPLES['euler_method_limit'])

    def test_exhausted_allowance_blocks_selector_before_transport(self):
        self.ledger.reserve(self.config, 4.999)
        before = self.reserved()
        def forbidden(payload, attempt):
            self.fail('The exhausted allowance must stop before transport.')
        provider = self.provider(forbidden)
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        self.assertEqual(report['investigation']['state'], 'failed')
        self.assertEqual(provider.request_attempts, 0)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.reserved(), before)
        self.assert_independent_findings(report, EXAMPLES['euler_method_limit'])


if __name__ == '__main__':
    unittest.main()
