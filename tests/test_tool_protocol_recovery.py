"""Offline protocol recovery and spending-boundary tests; no live inference."""
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import sixd.investigation as investigation_module
from sixd.examples import EXAMPLES
from sixd.contracts import digest
from sixd.investigation import investigate
from sixd.kernel import audit
from sixd.providers import BudgetLedger, FixtureProvider, LiveConfig, ProviderError, TokenFactoryProvider, Turn
from sixd.reporting import report_html, verify_payload

PRIVATE_VALUE = 'UNTRUSTED-ARGUMENT-VALUE-MUST-NOT-BE-RECORDED'
FREEFORM_VALUE = 'UNTRUSTED-CONTENT-MUST-NOT-BECOME-EVIDENCE'
EULER_IDS = ['central_force_reference', 'analytic_reference_refinement']
VERLET_IDS = EULER_IDS + ['method_time_reversal']


def call(name, args=None, identity='offline-protocol-1'):
    return {'id': identity, 'type': 'function', 'function': {
        'name': name, 'arguments': json.dumps({} if args is None else args)}}


def turn(*calls):
    return Turn({'role': 'assistant', 'content': FREEFORM_VALUE,
                 'tool_calls': list(calls)}, {})


def euler_batch(identity='offline-good'):
    return turn(call('check_force', identity=identity + '-force'),
                call('check_refinement', identity=identity + '-refinement'))


def finish(ids=EULER_IDS, identity='offline-finish'):
    return turn(call('finish', {'evidence_ids': list(ids)}, identity))


class RecordingSequence(FixtureProvider):
    def __init__(self, turns):
        self.turns = iter(turns)
        self.requests = []

    def complete(self, messages, tools):
        self.requests.append((deepcopy(messages), deepcopy(tools)))
        try:
            return next(self.turns)
        except StopIteration:
            raise ProviderError('Offline sequence exhausted.') from None


class ToolProtocolRecoveryTests(unittest.TestCase):
    def assert_kernel_unchanged(self, report, example):
        baseline = audit(example)
        for field in ('checks', 'findings', 'verdict', 'summary', 'not_tested',
                      'audit_id', 'contract_sha256'):
            self.assertEqual(report[field], baseline[field], field)
        verify_payload(report)
        self.assertNotIn(PRIVATE_VALUE, json.dumps(report))
        self.assertNotIn(FREEFORM_VALUE, json.dumps(report))

    def rejected(self, report):
        return [row for row in report['investigation']['trace']
                if row.get('status') == 'rejected']

    def test_nonempty_initial_arguments_recover_without_mutating_kernel(self):
        example = EXAMPLES['euler_method_limit']
        provider = RecordingSequence([
            turn(call('check_force', {'mu': PRIVATE_VALUE})),
            euler_batch(), finish(),
        ])
        report = investigate(example, provider, max_protocol_corrections=1)
        self.assertEqual(report['investigation']['state'], 'completed')
        rejected = self.rejected(report)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]['error_code'], 'check_arguments_not_empty')
        self.assertEqual(rejected[0]['argument_count'], 1)
        self.assertNotIn('arguments', rejected[0])
        self.assertEqual(len(provider.requests), 3)
        self.assert_kernel_unchanged(report, example)

    def test_error_tool_reply_matches_each_call_and_contains_only_controlled_data(self):
        provider = RecordingSequence([
            turn(call('check_force', {'mu': PRIVATE_VALUE}, 'offline-bad-force'),
                 call('check_refinement', {'duration': PRIVATE_VALUE}, 'offline-bad-refinement')),
            euler_batch(), finish(),
        ])
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        second_messages = provider.requests[1][0]
        assistant_index = next(i for i, message in enumerate(second_messages)
                               if message['role'] == 'assistant')
        assistant_message = second_messages[assistant_index]
        self.assertIsNone(assistant_message['content'])
        replies = second_messages[assistant_index + 1:]
        self.assertEqual([m['role'] for m in replies], ['tool', 'tool'])
        self.assertEqual({m['tool_call_id'] for m in replies},
                         {call['id'] for call in assistant_message['tool_calls']})
        for message in replies:
            data = json.loads(message['content'])
            self.assertIsInstance(data, dict)
            self.assertNotIn('id', data, 'Error replies must not masquerade as evidence.')
            self.assertNotIn(PRIVATE_VALUE, message['content'])
            self.assertNotIn(FREEFORM_VALUE, message['content'])
        self.assert_kernel_unchanged(report, EXAMPLES['euler_method_limit'])

    def test_batch_is_rejected_atomically_before_any_experiment_executes(self):
        example = EXAMPLES['euler_method_limit']
        counts = {'check_force': 0, 'check_refinement': 0}
        original = dict(investigation_module.CHECKS)

        def counted(name):
            def run(candidate, contract):
                counts[name] += 1
                return original[name](candidate, contract)
            return run

        provider = RecordingSequence([
            turn(call('check_force', identity='offline-batch-force'),
                 call('check_refinement', {'steps': PRIVATE_VALUE}, 'offline-batch-refinement')),
            euler_batch(), finish(),
        ])
        with patch.dict(investigation_module.CHECKS,
                        {name: counted(name) for name in counts}):
            report = investigate(example, provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual(counts, {'check_force': 1, 'check_refinement': 1})
        self.assertEqual(len(self.rejected(report)), 2)
        self.assert_kernel_unchanged(report, example)

    def test_three_distinct_verlet_checks_can_complete_in_one_batch(self):
        example = EXAMPLES['verlet_correct']
        provider = RecordingSequence([
            turn(call('check_force', identity='offline-three-force'),
                 call('check_refinement', identity='offline-three-refinement'),
                 call('check_reversibility', identity='offline-three-reversal')),
            finish(VERLET_IDS),
        ])
        report = investigate(example, provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual(len(provider.requests), 2)
        self.assertEqual(self.rejected(report), [])
        self.assert_kernel_unchanged(report, example)

    def test_premature_finish_gets_one_correction_and_cannot_create_evidence(self):
        example = EXAMPLES['euler_method_limit']
        provider = RecordingSequence([
            finish([], 'offline-premature'), euler_batch(), finish(),
        ])
        report = investigate(example, provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        rejected = self.rejected(report)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]['tool'], 'finish')
        self.assertNotIn('evidence_id', rejected[0])
        self.assert_kernel_unchanged(report, example)

    def test_repeated_check_is_not_rerun_even_if_agent_recovers(self):
        example = EXAMPLES['euler_method_limit']
        force = investigation_module.CHECKS['check_force']
        provider = RecordingSequence([
            turn(call('check_force', identity='offline-first-force')),
            turn(call('check_force', identity='offline-repeat-force')),
            turn(call('check_refinement', identity='offline-after-repeat')),
            finish(),
        ])
        counted = Mock(wraps=force)
        with patch.dict(investigation_module.CHECKS, {'check_force': counted}):
            report = investigate(example, provider)
            self.assertEqual(counted.call_count, 1)
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual(len(self.rejected(report)), 1)
        self.assertEqual(self.rejected(report)[0]['tool'], 'check_force')
        self.assert_kernel_unchanged(report, example)

    def test_second_violation_exhausts_repair_allowance_without_extra_call(self):
        example = EXAMPLES['euler_method_limit']
        provider = RecordingSequence([
            turn(call('check_force', {'mu': PRIVATE_VALUE}, 'offline-violation-1')),
            turn(call('check_force', {'radius': PRIVATE_VALUE}, 'offline-violation-2')),
            euler_batch(), finish(),
        ])
        report = investigate(example, provider, max_protocol_corrections=1)
        self.assertEqual(report['investigation']['state'], 'failed')
        self.assertEqual(len(provider.requests), 2)
        self.assertEqual(len(self.rejected(report)), 2)
        self.assertTrue(report['investigation']['error'])
        self.assert_kernel_unchanged(report, example)

    def test_disabled_repair_and_turn_limit_do_not_send_unbounded_followups(self):
        example = EXAMPLES['euler_method_limit']
        for kwargs in ({'max_protocol_corrections': 0}, {'max_turns': 1}):
            with self.subTest(kwargs=kwargs):
                provider = RecordingSequence([
                    turn(call('check_force', {'mu': PRIVATE_VALUE})),
                    euler_batch(), finish(),
                ])
                report = investigate(example, provider, **kwargs)
                self.assertIn(report['investigation']['state'], ('failed', 'incomplete'))
                self.assertEqual(len(provider.requests), 1)
                self.assert_kernel_unchanged(report, example)

    def test_default_five_turn_bound_fits_one_correction_and_sequential_verlet_checks(self):
        example = EXAMPLES['verlet_correct']
        provider = RecordingSequence([
            turn(call('check_force', {'radius': PRIVATE_VALUE}, 'offline-five-bad')),
            turn(call('check_force', identity='offline-five-force')),
            turn(call('check_refinement', identity='offline-five-refinement')),
            turn(call('check_reversibility', identity='offline-five-reversal')),
            finish(VERLET_IDS),
        ])
        report = investigate(example, provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual(len(provider.requests), 5)
        self.assert_kernel_unchanged(report, example)

    def test_duplicate_check_names_in_batch_are_rejected_before_any_execution(self):
        example = EXAMPLES['euler_method_limit']
        counted = Mock(wraps=investigation_module.CHECKS['check_force'])
        provider = RecordingSequence([
            turn(call('check_force', identity='offline-duplicate-a'),
                 call('check_force', identity='offline-duplicate-b')),
            euler_batch(), finish(),
        ])
        with patch.dict(investigation_module.CHECKS, {'check_force': counted}):
            report = investigate(example, provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual(counted.call_count, 1)
        self.assertEqual(len(self.rejected(report)), 2)
        self.assert_kernel_unchanged(report, example)

    def test_dynamic_menu_omits_executed_checks_and_only_then_offers_exact_finish_ids(self):
        provider = RecordingSequence([
            turn(call('check_force', identity='offline-menu-force')),
            turn(call('check_refinement', identity='offline-menu-refinement')),
            finish(),
        ])
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        menus = [tools for _, tools in provider.requests]
        self.assertEqual([{t['function']['name'] for t in tools} for tools in menus],
                         [{'check_force', 'check_refinement'}, {'check_refinement'}, {'finish'}])
        self.assertEqual(set(menus[-1][0]['function']['parameters']['properties']
                             ['evidence_ids']['items']['enum']), set(EULER_IDS))
        for tools in menus[:-1]:
            for tool in tools:
                parameters = tool['function']['parameters']
                self.assertEqual(parameters['properties'], {})
                self.assertFalse(parameters['additionalProperties'])

    def test_wrong_finish_ids_are_never_accepted_or_written_as_evidence(self):
        example = EXAMPLES['euler_method_limit']
        provider = RecordingSequence([
            euler_batch(), finish([PRIVATE_VALUE, 'central_force_reference'], 'offline-forged'),
            finish(),
        ])
        report = investigate(example, provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual(len(self.rejected(report)), 1)
        self.assert_kernel_unchanged(report, example)

    def test_finish_combined_with_checks_rejects_batch_without_partial_execution(self):
        provider = RecordingSequence([
            turn(call('check_force', identity='offline-combined-force'),
                 call('finish', {'evidence_ids': []}, 'offline-combined-finish')),
            euler_batch(), finish(),
        ])
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual(len(self.rejected(report)), 2)
        self.assert_kernel_unchanged(report, EXAMPLES['euler_method_limit'])

    def test_unsupported_tools_shapes_and_identifiers_remain_terminal(self):
        bad_id = call('check_force', identity='invalid call identity')
        malformed = call('check_force')
        malformed['function']['arguments'] = '{'
        for bad in (call('execute_python'), call('check_force', [PRIVATE_VALUE]),
                    bad_id, malformed):
            with self.subTest(bad=bad['function']['name']):
                provider = RecordingSequence([turn(bad), euler_batch(), finish()])
                report = investigate(EXAMPLES['euler_method_limit'], provider)
                self.assertEqual(report['investigation']['state'], 'failed')
                self.assertEqual(len(provider.requests), 1)
                self.assert_kernel_unchanged(report, EXAMPLES['euler_method_limit'])

    def test_fixture_ignores_protocol_error_replies_without_evidence_ids(self):
        tools = [deepcopy(t) for t in investigation_module.TOOLS
                 if t['function']['name'] in ('check_force', 'check_refinement')]
        result = FixtureProvider().complete([
            {'role': 'tool', 'tool_call_id': 'offline-error',
             'content': json.dumps({'error_code': 'check_arguments_not_empty'})},
        ], tools)
        self.assertEqual(result.message['tool_calls'][0]['function']['name'], 'check_force')

    def test_recovered_html_distinguishes_rejected_calls_from_executed_experiments(self):
        provider = RecordingSequence([
            turn(call('check_force', {'mu': PRIVATE_VALUE})), euler_batch(), finish(),
        ])
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        html = report_html(report)
        self.assertIn('<li>check_force: rejected</li>', html)
        self.assertIn('<li>check_force: executed</li>', html)
        self.assertIn('<li>check_refinement: executed</li>', html)
        self.assertIn('State: completed', html)
        self.assertNotIn(PRIVATE_VALUE, html)
        self.assertNotIn(FREEFORM_VALUE, html)

    def test_rejected_trace_cannot_claim_evidence_even_with_recomputed_payload_digest(self):
        provider = RecordingSequence([
            turn(call('check_force', {'mu': PRIVATE_VALUE})), euler_batch(), finish(),
        ])
        original = investigate(EXAMPLES['euler_method_limit'], provider)
        verify_payload(original)
        mutations = (
            {'evidence_id': 'central_force_reference'},
            {'evidence_ids': ['central_force_reference']},
            {'evidence_sha256': digest(original['checks'][0])},
        )
        for fields in mutations:
            with self.subTest(fields=tuple(fields)):
                forged = deepcopy(original)
                rejected = next(row for row in forged['investigation']['trace']
                                if row.get('status') == 'rejected')
                rejected.update(fields)
                forged['report_payload_sha256'] = digest({
                    key: value for key, value in forged.items()
                    if key != 'report_payload_sha256'})
                with self.assertRaisesRegex(ValueError,
                                            'A rejected tool call cannot claim recorded evidence'):
                    verify_payload(forged)


class ToolRecoveryBudgetTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / 'work'
        scratch.mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(directory.cleanup)
        self.ledger = BudgetLedger(Path(directory.name) / 'offline-budget.sqlite3')
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1',
                                 'nvidia/offline-nemotron-protocol',
                                 'offline-protocol-budget-only', 1.0, 0.06, 0.24, 1024)

    def response(self, message):
        return {'choices': [{'finish_reason': 'tool_calls', 'message': message}],
                'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}}

    def test_singleton_tool_is_forced_and_multiple_tools_use_auto(self):
        payloads = []

        def transport(request):
            payloads.append(json.loads(request.data))
            return self.response(turn(call('check_force')).message)

        provider = TokenFactoryProvider(self.config, self.ledger,
            api_key='synthetic-offline-protocol-key', transport=transport)
        force = deepcopy(next(t for t in investigation_module.TOOLS
                              if t['function']['name'] == 'check_force'))
        refinement = deepcopy(next(t for t in investigation_module.TOOLS
                                   if t['function']['name'] == 'check_refinement'))
        provider.complete([], [force])
        provider.complete([], [force, refinement])
        self.assertEqual(payloads[0]['tool_choice'],
                         {'type': 'function', 'function': {'name': 'check_force'}})
        self.assertEqual(payloads[1]['tool_choice'], 'auto')
        self.assertNotIn('synthetic-offline-protocol-key', json.dumps(payloads))

    def test_budget_exhaustion_during_correction_blocks_before_second_transport(self):
        sent = []

        def transport(request):
            sent.append(request)
            with closing(sqlite3.connect(self.ledger.path)) as db:
                reserved = db.execute('SELECT reserved FROM budget').fetchone()[0]
            self.ledger.reserve(self.config, self.config.spend_cap_usd - reserved)
            return self.response(turn(call('check_force', {'mu': PRIVATE_VALUE})).message)

        provider = TokenFactoryProvider(self.config, self.ledger,
            api_key='synthetic-offline-protocol-key', transport=transport)
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        self.assertEqual(report['investigation']['state'], 'failed')
        self.assertEqual(len(sent), 1)
        self.assertEqual(provider.request_attempts, 1)
        self.assertIn('allowance is exhausted', report['investigation']['error'])
        self.assertEqual(len([row for row in report['investigation']['trace']
                              if row.get('status') == 'rejected']), 1)
        self.assertEqual(report['checks'], audit(EXAMPLES['euler_method_limit'])['checks'])
        self.assertNotIn(PRIVATE_VALUE, json.dumps(report))
        verify_payload(report)


if __name__ == '__main__':
    unittest.main()
