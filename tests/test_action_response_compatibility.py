"""Offline response-envelope compatibility without relaxing action/evidence rules."""
from contextlib import closing, redirect_stdout
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.action_selection import PROBLEM, PROTOCOL, WIRE_TOOL, decode_action_response
from sixd.examples import EXAMPLES
import sixd.investigation as investigation_module
from sixd.investigation import investigate, remaining_tools
from sixd.kernel import audit
import sixd.live_validation as validation
from sixd.providers import BudgetLedger, LiveConfig, ProviderError, TokenFactoryProvider
from sixd.reporting import read_report, save_report, verify_payload

KEY = 'synthetic-offline-compatibility-key'
PRIVATE = 'PRIVATE-REMOTE-TEXT-MUST-NOT-BE-RECORDED'
IDS = ['analytic_reference_refinement', 'central_force_reference']
CHECKS = {'check_force': None, 'check_refinement': None}


def menu(*, finish=False):
    return remaining_tools(CHECKS, set(CHECKS) if finish else set(),
                           {identity: {} for identity in IDS} if finish else {})


def selection(action='check_force', ids=None):
    return {'action': action, 'evidence_ids': [] if ids is None else ids}


def content_message(value=None, *, raw=None, tool_calls=None):
    result = {'role': 'assistant', 'content': raw if raw is not None else json.dumps(
        selection() if value is None else value), 'reasoning_content': PRIVATE}
    if tool_calls is not None:
        result['tool_calls'] = tool_calls
    return result


def native_message(value=None, identity='provider-selection-1'):
    return {'role': 'assistant', 'content': PRIVATE, 'reasoning_content': PRIVATE,
            'tool_calls': [{'id': identity, 'type': 'function', 'function': {
                'name': WIRE_TOOL, 'arguments': json.dumps(selection() if value is None else value)},
                'untrusted_metadata': PRIVATE}]}


def envelope(message, finish_reason='stop'):
    return {'choices': [{'finish_reason': finish_reason, 'message': message}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 40, 'total_tokens': 90},
            'private_remote_metadata': PRIVATE}


class ResponseAdapterUnitTests(unittest.TestCase):
    def test_content_exact_selection_has_runner_origin_and_no_untrusted_fields(self):
        for calls in (None, []):
            with self.subTest(tool_calls=calls):
                decoded, problem, form, origin = decode_action_response(
                    content_message(tool_calls=calls), menu(), internal_call_id='runner-selection-1')
                self.assertIsNone(problem)
                self.assertEqual((form, origin), ('content_selection_json', 'runner'))
                self.assertEqual(decoded, {'role': 'assistant', 'content': None, 'tool_calls': [{
                    'id': 'runner-selection-1', 'type': 'function',
                    'function': {'name': 'check_force', 'arguments': '{}'}}]})
                self.assertNotIn(PRIVATE, json.dumps(decoded))

    def test_native_selection_preserves_provider_identity_and_reports_representation(self):
        original = native_message(identity='provider-kept-identity')
        snapshot = deepcopy(original)
        decoded, problem, form, origin = decode_action_response(
            original, menu(), internal_call_id='runner-unused')
        self.assertIsNone(problem)
        self.assertEqual((form, origin), ('native_tool_call', 'provider'))
        self.assertEqual(decoded['tool_calls'][0]['id'], 'provider-kept-identity')
        self.assertNotIn(PRIVATE, json.dumps(decoded))
        self.assertEqual(original, snapshot)

    def test_content_parser_rejects_prose_fences_extra_fields_duplicates_and_nonfinite(self):
        malformed = [
            'Choose check_force next.',
            '```json\n{"action":"check_force","evidence_ids":[]}\n```',
            'prefix {"action":"check_force","evidence_ids":[]}',
            '{"action":"check_force","evidence_ids":[]} trailing',
            '{"action":"check_force","action":"finish","evidence_ids":[]}',
            '{"action":"check_force","evidence_ids":[],"evidence_ids":[]}',
            '{"action":"check_force","evidence_ids":NaN}',
            '{"action":"check_force","evidence_ids":Infinity}',
            json.dumps({'action': 'check_force', 'evidence_ids': [], 'radius': PRIVATE}),
            json.dumps({'action': 'check_force'}),
            json.dumps({'action': [], 'evidence_ids': []}),
            json.dumps({'action': 'check_force', 'evidence_ids': [True]}),
            '[]', 'null', '', ' ' * 2049,
        ]
        for raw in malformed:
            with self.subTest(raw=raw[:100]), self.assertRaises(ProviderError) as caught:
                decode_action_response(content_message(raw=raw), menu(),
                                       internal_call_id='runner-rejected')
            self.assertNotIn(PRIVATE, str(caught.exception))

    def test_content_semantic_errors_use_same_controlled_action_feedback(self):
        cases = [(selection('finish'), menu()),
                 (selection('check_reversibility'), menu()),
                 (selection('check_force', [PRIVATE]), menu()),
                 (selection('finish', IDS[:1]), menu(finish=True)),
                 (selection('finish', [IDS[0], IDS[0]]), menu(finish=True)),
                 (selection('finish', IDS + [PRIVATE]), menu(finish=True))]
        for value, tools in cases:
            with self.subTest(selection=value):
                decoded, problem, form, origin = decode_action_response(
                    content_message(value), tools, internal_call_id='runner-rejected')
                self.assertEqual(problem, PROBLEM)
                self.assertEqual((form, origin), ('content_selection_json', 'runner'))
                self.assertEqual(decoded['tool_calls'][0]['function']['name'], WIRE_TOOL)
                self.assertNotIn(PRIVATE, json.dumps(problem))

    def test_finish_content_preserves_exact_recorded_ids_only(self):
        decoded, problem, form, origin = decode_action_response(
            content_message(selection('finish', list(reversed(IDS)))), menu(finish=True),
            internal_call_id='runner-finish')
        self.assertIsNone(problem)
        self.assertEqual((form, origin), ('content_selection_json', 'runner'))
        call = decoded['tool_calls'][0]
        self.assertEqual(call['function']['name'], 'finish')
        self.assertEqual(json.loads(call['function']['arguments']),
                         {'evidence_ids': list(reversed(IDS))})

    def test_invalid_native_envelopes_cannot_fall_back_to_valid_content(self):
        invalid_calls = [{}, 'not-an-envelope', [native_message()['tool_calls'][0]] * 2]
        for calls in invalid_calls:
            with self.subTest(calls=calls), self.assertRaises(ProviderError):
                decode_action_response(content_message(tool_calls=calls), menu(),
                                       internal_call_id='runner-must-not-rescue')
        malformed = native_message()
        malformed['tool_calls'][0]['function']['name'] = PRIVATE
        malformed['content'] = json.dumps(selection())
        with self.assertRaises(ProviderError):
            decode_action_response(malformed, menu(), internal_call_id='runner-must-not-rescue')


class ResponseCompatibilityIntegrationTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'work').mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1',
            'nvidia/offline-nemotron-compatibility', 'offline-envelope-tests-only',
            5.0, 0.06, 0.24, 2048, 180,
            inference_profile='native_no_thinking', selection_protocol=PROTOCOL)
        self.ledger = BudgetLedger(self.root / 'budget.sqlite3')

    def provider(self, form='native', *, finish_reason='stop', first_value=None,
                 terminal_raw=None, config=None):
        requests = []
        def transport(request):
            payload = json.loads(request.data)
            self.assertNotIn(KEY, request.data.decode('utf-8'))
            self.assertEqual(payload['tool_choice'],
                {'type': 'function', 'function': {'name': WIRE_TOOL}})
            self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': False})
            requests.append(payload)
            current = json.loads(payload['messages'][-1]['content'])
            action = current['available_actions'][0]['action']
            value = selection(action, current['recorded_evidence_ids'] if action == 'finish' else [])
            if len(requests) == 1 and first_value is not None:
                value = first_value
            chosen = form if form != 'mixed' else ('content' if len(requests) % 2 else 'native')
            if terminal_raw is not None:
                message = content_message(raw=terminal_raw)
            elif chosen == 'content':
                message = content_message(value)
            else:
                message = native_message(value, identity=f'provider-turn-{len(requests)}')
            return envelope(message, finish_reason)
        provider = TokenFactoryProvider(config or self.config, self.ledger,
                                        api_key=KEY, transport=transport)
        return provider, requests

    def assert_unchanged_kernel(self, report, example):
        baseline = audit(example)
        for key in ('checks', 'findings', 'verdict', 'summary', 'audit_id',
                    'not_tested', 'contract_sha256'):
            self.assertEqual(report[key], baseline[key], key)
        self.assertEqual(report['model_mode'], 'offline_transport_fixture')
        self.assertEqual(report['live_model_calls'], 0)
        self.assertEqual(report['investigation']['live_request_attempts'], 0)
        self.assertNotIn(KEY, json.dumps(report))
        self.assertNotIn(PRIVATE, json.dumps(report))
        verify_payload(report)

    def test_stop_native_and_content_complete_both_cases_with_persisted_true_format(self):
        for form in ('native', 'content'):
            for case in ('euler_method_limit', 'force_sign_error'):
                with self.subTest(form=form, case=case):
                    provider, requests = self.provider(form)
                    example = EXAMPLES[case]
                    report = investigate(example, provider)
                    run = report['investigation']
                    self.assertEqual(run['state'], 'completed')
                    self.assertEqual(run['protocol_corrections'], 0)
                    count = 3 if case == 'euler_method_limit' else 4
                    self.assertEqual(len(requests), count)
                    self.assertEqual(provider.request_attempts, count)
                    self.assertEqual(run['provider_successes'], count)
                    for event in run['trace']:
                        self.assertEqual(event['finish_reason'], 'stop')
                        self.assertEqual(event['response_format'],
                            'native_tool_call' if form == 'native' else 'content_selection_json')
                        self.assertEqual(event['call_id_origin'],
                            'provider' if form == 'native' else 'runner')
                    self.assertEqual(len({row['call_id'] for row in run['trace']}), count)
                    self.assertEqual(run['trace'][-1]['tool'], 'finish')
                    self.assert_unchanged_kernel(report, example)
                    directory = self.root / f'{form}-{case}'
                    saved = read_report(save_report(report, directory)['json_path'])
                    self.assertEqual(saved['investigation']['trace'], run['trace'])
                    # Every adapted history call has a matching tool response.
                    for payload in requests[1:]:
                        identities = set()
                        for message in payload['messages']:
                            if message['role'] == 'assistant':
                                for call in message['tool_calls']:
                                    self.assertEqual(call['function']['name'], WIRE_TOOL)
                                    identities.add(call['id'])
                            elif message['role'] == 'tool':
                                self.assertIn(message['tool_call_id'], identities)

    def test_tool_calls_reason_remains_supported_for_native_selector(self):
        provider, requests = self.provider('native', finish_reason='tool_calls')
        turn = provider.complete([], menu())
        self.assertEqual(turn.response_meta,
                         {'finish_reason': 'tool_calls', 'response_format': 'native_tool_call',
                          'call_id_origin': 'provider'})
        self.assertEqual(len(requests), 1)

    def test_mixed_representations_record_each_actual_source_without_claiming_live_calls(self):
        provider, _ = self.provider('mixed')
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual([event['response_format'] for event in report['investigation']['trace']],
            ['content_selection_json', 'native_tool_call', 'content_selection_json'])
        self.assert_unchanged_kernel(report, EXAMPLES['euler_method_limit'])

    def test_content_semantic_rejection_gets_only_one_controlled_correction(self):
        provider, requests = self.provider('content', first_value=selection('finish', [PRIVATE]))
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        run = report['investigation']
        self.assertEqual(run['state'], 'completed')
        self.assertEqual((run['protocol_rejections'], run['protocol_corrections']), (1, 1))
        self.assertEqual(len(requests), 4)
        rejected = run['trace'][0]
        self.assertEqual(rejected['status'], 'rejected')
        self.assertEqual(rejected['error_code'], PROBLEM['code'])
        self.assertEqual(rejected['response_format'], 'content_selection_json')
        self.assertEqual(rejected['call_id_origin'], 'runner')
        self.assertFalse({'evidence_id', 'evidence_ids', 'evidence_sha256'} & set(rejected))
        self.assert_unchanged_kernel(report, EXAMPLES['euler_method_limit'])

    def test_prose_and_length_never_execute_selected_checks_or_retry_transport(self):
        for raw, reason in ((PRIVATE, 'stop'), (json.dumps(selection()), 'length')):
            with self.subTest(reason=reason):
                provider, requests = self.provider('content', terminal_raw=raw, finish_reason=reason)
                traps = {name: Mock(side_effect=AssertionError('No rejected selection may execute.'))
                         for name in ('check_force', 'check_refinement', 'check_reversibility')}
                with patch.dict(investigation_module.CHECKS, traps):
                    report = investigate(EXAMPLES['euler_method_limit'], provider)
                self.assertEqual(report['investigation']['state'], 'failed')
                self.assertEqual(report['investigation']['provider_successes'], 0)
                self.assertEqual(report['investigation']['trace'], [])
                self.assertEqual(provider.request_attempts, 1)
                self.assertEqual(len(requests), 1)
                for trap in traps.values():
                    trap.assert_not_called()
                self.assert_unchanged_kernel(report, EXAMPLES['euler_method_limit'])
        with closing(sqlite3.connect(self.ledger.path)) as connection:
            self.assertGreater(connection.execute('SELECT reserved FROM budget').fetchone()[0], 0)

    def test_stop_prose_diagnostic_retains_shape_without_remote_text(self):
        provider, _ = self.provider('content', terminal_raw=PRIVATE)
        with self.assertRaises(ProviderError) as caught:
            provider.complete([], menu())
        diagnostic = caught.exception.diagnostic
        self.assertEqual(diagnostic['finish_reason'], 'stop')
        self.assertEqual(diagnostic['response_shape'], 'content_without_tool_calls')
        self.assertEqual(diagnostic['tool_call_count'], 0)
        self.assertIs(diagnostic['content_present'], True)
        self.assertNotIn(PRIVATE, json.dumps(diagnostic))
        self.assertNotIn(PRIVATE, str(caught.exception))

    def test_native_protocol_is_not_silently_relaxed_to_accept_stop(self):
        config = replace(self.config, selection_protocol='native_tools_v1')
        calls = []
        def transport(request):
            calls.append(request)
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                'id': 'legacy-native-check', 'type': 'function',
                'function': {'name': 'check_force', 'arguments': '{}'}}]}
            return envelope(message, 'stop')
        provider = TokenFactoryProvider(config, self.ledger, api_key=KEY, transport=transport)
        with self.assertRaises(ProviderError):
            provider.complete([], menu())
        self.assertEqual(len(calls), 1)

    def test_completed_offline_compatible_responses_cannot_install_live_configuration(self):
        local = self.root / '.local'
        local.mkdir()
        path = local / 'token-factory.json'
        original = {**replace(self.config, inference_profile='tool_sampling',
                              selection_protocol='native_tools_v1').__dict__,
                    'account_verified': True, 'model_license_reviewed': True, 'spend_approved': True}
        path.write_text(json.dumps(original), encoding='utf-8')
        def factory(config, ledger):
            def transport(request):
                payload = json.loads(request.data)
                current = json.loads(payload['messages'][-1]['content'])
                action = current['available_actions'][0]['action']
                ids = current['recorded_evidence_ids'] if action == 'finish' else []
                return envelope(content_message(selection(action, ids)), 'stop')
            return TokenFactoryProvider(config, ledger, api_key=KEY, transport=transport)
        output = io.StringIO()
        with patch.dict('os.environ', {'NEBIUS_API_KEY': KEY}), redirect_stdout(output), \
                patch.object(validation, 'TokenFactoryProvider', side_effect=factory):
            self.assertEqual(validation.validate_live(self.root, accept_contract=True), 2)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), original)
        summaries = list((self.root / 'artifacts' / 'provider-validation').glob('validation-*.json'))
        self.assertEqual(len(summaries), 1)
        summary = json.loads(summaries[0].read_text(encoding='utf-8'))
        self.assertEqual(summary['state'], 'failed')
        self.assertFalse(summary['configuration_updated'])
        self.assertNotIn(KEY, output.getvalue())
        self.assertNotIn(PRIVATE, output.getvalue())


if __name__ == '__main__':
    unittest.main()
