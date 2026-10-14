from dataclasses import replace
from contextlib import closing
from pathlib import Path
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.examples import EXAMPLES
from sixd.investigation import investigate
from sixd.kernel import audit
from sixd.providers import (BudgetLedger, FixtureProvider, LiveConfig, ProviderError,
                            TokenFactoryProvider, Turn, make_provider)
from sixd.reporting import report_html, save_report, verify_payload
from sixd.cli import main


def call(name, args=None, identity='test-1'):
    return Turn({'role': 'assistant', 'content': 'Untrusted claim: spacecraft certified.',
                 'tool_calls': [{'id': identity, 'type': 'function',
                    'function': {'name': name, 'arguments': json.dumps(args or {})}}]}, {})


class SequenceProvider(FixtureProvider):
    def __init__(self, turns):
        self.turns = iter(turns)

    def complete(self, messages, tools):
        return next(self.turns)


class InvestigationTests(unittest.TestCase):
    def test_fixture_preserves_all_five_outcomes_and_evidence(self):
        for example in EXAMPLES.values():
            with self.subTest(case=example.id):
                baseline = audit(example)
                report = investigate(example, FixtureProvider())
                self.assertEqual(report['checks'], baseline['checks'])
                self.assertEqual(report['audit_id'], baseline['audit_id'])
                self.assertEqual(report['verdict'], baseline['verdict'])
                self.assertEqual(report['live_model_calls'], 0)
                self.assertEqual(report['model_mode'], 'fixture')
                self.assertEqual(report['not_tested'], baseline['not_tested'])
                verify_payload(report)
                self.assertEqual(report['investigation']['state'],
                    'blocked_contract' if example.contract.ambiguities() else 'completed')

    def test_agent_can_select_refinement_before_force(self):
        provider = SequenceProvider([call('check_refinement'), call('check_force', identity='test-2'),
            call('finish', {'evidence_ids': ['central_force_reference', 'analytic_reference_refinement']}, 'test-3')])
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual(report['investigation']['trace'][0]['tool'], 'check_refinement')
        self.assertEqual(report['verdict'], 'method_limitation')
        self.assertNotIn('spacecraft certified', json.dumps(report))

    def test_unsupported_calls_and_overrides_fail_without_changing_kernel_findings(self):
        for turn in [call('execute_python'), call('check_force', {'mu': 1}),
                     call('finish', {'evidence_ids': ['invented'], 'verdict': 'no_defect_found_in_scope'}),
                     Turn({'role': 'assistant', 'content': 'All checks passed.'}, {})]:
            with self.subTest(turn=turn):
                report = investigate(EXAMPLES['force_sign_error'], SequenceProvider([turn]))
                self.assertEqual(report['investigation']['state'], 'failed')
                self.assertEqual(report['verdict'], 'defect_likely')
                self.assertEqual(report['live_model_calls'], 0)
                verify_payload(report)

    def test_finish_cannot_invent_evidence_after_checks(self):
        provider = SequenceProvider([call('check_force'), call('check_refinement', identity='test-2'),
            call('finish', {'evidence_ids': ['invented', 'central_force_reference']}, 'test-3')])
        self.assertEqual(investigate(EXAMPLES['verlet_correct'], provider)['investigation']['state'], 'failed')

    def test_provider_failure_preserves_partial_trace_and_full_kernel_audit(self):
        class Interrupted(FixtureProvider):
            def complete(self, messages, tools):
                if len(messages) > 2:
                    raise ProviderError('Controlled transport failure.')
                return call('check_force')
        report = investigate(EXAMPLES['wrong_order'], Interrupted())
        self.assertEqual(report['investigation']['state'], 'failed')
        self.assertEqual(len(report['investigation']['trace']), 1)
        self.assertEqual(report['verdict'], 'defect_likely')
        self.assertEqual(len(report['checks']), 3)

    def test_verlet_fixture_selects_reversibility_and_cites_all_checks(self):
        report = investigate(EXAMPLES['verlet_correct'], FixtureProvider())
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual([event['tool'] for event in report['investigation']['trace']],
                         ['check_force', 'check_refinement', 'check_reversibility', 'finish'])
        self.assertEqual(set(report['investigation']['trace'][-1]['evidence_ids']),
                         {check['id'] for check in report['checks']})

    def test_verlet_cannot_finish_without_required_method_property_evidence(self):
        provider = SequenceProvider([call('check_force'), call('check_refinement', identity='test-2'),
            call('finish', {'evidence_ids': ['central_force_reference', 'analytic_reference_refinement']}, 'test-3')])
        report = investigate(EXAMPLES['verlet_correct'], provider)
        self.assertEqual(report['investigation']['state'], 'failed')
        self.assertEqual(report['verdict'], 'no_defect_found_in_scope')

    def test_euler_does_not_offer_verlet_property_check(self):
        class InspectTools(FixtureProvider):
            def complete(self, messages, tools):
                if any(item['function']['name'] == 'check_reversibility' for item in tools):
                    raise AssertionError('Verlet-specific check offered for Euler.')
                return super().complete(messages, tools)
        self.assertEqual(investigate(EXAMPLES['euler_method_limit'], InspectTools())['investigation']['state'], 'completed')

    def test_ambiguous_contract_never_calls_provider(self):
        with patch.object(FixtureProvider, 'complete', side_effect=AssertionError('must abstain')):
            report = investigate(EXAMPLES['verlet_correct'], FixtureProvider(),
                                 contract=EXAMPLES['verlet_correct'].contract.updated(frame='unspecified'))
        self.assertEqual(report['investigation']['provider_attempts'], 0)
        self.assertEqual(report['checks'], [])

    def test_repeat_check_and_turn_limit_are_visible_failures(self):
        provider = SequenceProvider([call('check_force'), call('check_force', identity='test-2')])
        self.assertEqual(investigate(EXAMPLES['verlet_correct'], provider)['investigation']['state'], 'failed')
        report = investigate(EXAMPLES['verlet_correct'], FixtureProvider(), max_turns=1)
        self.assertEqual(report['investigation']['state'], 'incomplete')

    def test_fixture_snapshot_reproduces_kernel_and_labels_export(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as directory:
            report = investigate(EXAMPLES['verlet_correct'], FixtureProvider())
            paths = save_report(report, directory)
            self.assertEqual(main(['reproduce', paths['json_path'], '--output', directory]), 0)
            self.assertIn('Provider: fixture', report_html(report))
            self.assertIn('no model inference', report_html(report))


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.directory.cleanup)
        self.local = Path(self.directory.name)
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1', 'nvidia/verified-nemotron-test',
                                 'offline-test-only', 0.02, 1.0, 3.0, 1024)
        self.ledger = BudgetLedger(self.local / 'budget.sqlite3')

    def reserved(self):
        with closing(sqlite3.connect(self.ledger.path)) as db:
            return db.execute('SELECT reserved FROM budget').fetchone()[0]

    def test_missing_config_cannot_send_inference(self):
        with self.assertRaises(ProviderError):
            make_provider('token-factory', self.local)

    def test_config_rejects_unverified_account_and_wrong_endpoint(self):
        data = {**self.config.__dict__, 'account_verified': True, 'model_license_reviewed': True, 'spend_approved': True}
        path = self.local / 'config.json'
        for mutation in ({'account_verified': False}, {'base_url': 'https://attacker.example/v1'},
                         {'spend_cap_usd': 0}, {'model': 'some-model'}):
            path.write_text(json.dumps({**data, **mutation}))
            with self.assertRaises(ProviderError):
                LiveConfig.load(path)
        path.write_text(json.dumps(data))
        self.assertEqual(LiveConfig.load(path), self.config)

    def test_http_shape_uses_tools_and_never_serializes_key(self):
        def transport(request):
            payload = json.loads(request.data)
            self.assertTrue(request.full_url.endswith('/v1/chat/completions'))
            self.assertEqual(payload['tool_choice'], 'auto')
            self.assertEqual(payload['max_tokens'], 1024)
            self.assertNotIn('test-secret', request.data.decode())
            return {'choices': [{'finish_reason': 'tool_calls', 'message': call('check_force').message}],
                    'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70, 'remote_echo': 'test-secret'}}
        provider = TokenFactoryProvider(self.config, self.ledger, api_key='test-secret', transport=transport)
        result = provider.complete([], [])
        self.assertEqual(result.usage, {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70})
        self.assertGreater(self.reserved(), 0)
        self.assertEqual(provider.request_attempts, 1)
        self.assertEqual(provider.mode, 'offline_transport_fixture')

    def test_failed_request_keeps_reservation_and_hides_remote_error(self):
        def transport(request):
            raise RuntimeError('test-secret echoed in remote exception')
        provider = TokenFactoryProvider(self.config, self.ledger, api_key='test-secret', transport=transport)
        with self.assertRaises(ProviderError) as exc:
            provider.complete([], [])
        self.assertNotIn('test-secret', str(exc.exception))
        self.assertGreater(self.reserved(), 0)

    def test_cap_survives_restart_and_blocks_before_transport(self):
        provider = TokenFactoryProvider(replace(self.config, spend_cap_usd=0.0001), self.ledger,
            api_key='test-secret', transport=lambda request: self.fail('no request allowed'))
        with self.assertRaises(ProviderError):
            provider.complete([], [])
        self.assertEqual(provider.request_attempts, 0)
        self.ledger.reserve(self.config, 0.019)
        with self.assertRaises(ProviderError):
            BudgetLedger(self.ledger.path).reserve(self.config, 0.002)
        with self.assertRaises(ProviderError):
            self.ledger.reserve(replace(self.config, approval_id='changed'), 0.001)


if __name__ == '__main__':
    unittest.main()
