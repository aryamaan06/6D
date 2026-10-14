"""Offline live-session orchestration tests; synthetic providers and temporary ledgers only."""
from contextlib import closing, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import io
import json
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import sixd.live_validation as validation
from sixd.providers import BudgetLedger, FAILURE_SUFFIX, FixtureProvider, LiveConfig, ProviderError, Turn
from sixd.contracts import digest
from sixd.action_selection import PROBLEM

SECRET = 'synthetic-session-credential-never-persist-or-display'
PRIVATE_DETAIL = 'untrusted-response-secret-never-persist-or-display'


class SyntheticLiveProvider:
    """A deliberately fake live-shaped provider, patchable without any HTTP transport."""
    mode = 'live_token_factory'

    def __init__(self, config, ledger, *, behavior='complete'):
        self.config, self.ledger, self.model = config, ledger, config.model
        self.request_attempts = 0
        self.behavior = behavior
        self.fixture = FixtureProvider()

    def complete(self, messages, tools):
        self.ledger.reserve(self.config, 0.001)
        self.request_attempts += 1
        if self.behavior == 'overbound':
            raise ProviderError('Usage exceeded the configured reservation bound; stop and review provider billing.' + FAILURE_SUFFIX)
        if self.behavior in ('unauthorized', 'timeout'):
            message = ('Nebius request failed: HTTP 401.' if self.behavior == 'unauthorized'
                       else 'Nebius request timed out.')
            raise ProviderError(message + FAILURE_SUFFIX)
        if self.behavior == 'fail':
            error = ProviderError('Controlled synthetic failure.')
            error.diagnostic = {'finish_reason': 'length', 'usage': {'prompt_tokens': 10,
                                'completion_tokens': 2048, 'total_tokens': 2058},
                                'max_output_tokens': 2048,
                                'inference_profile': self.config.inference_profile}
            raise error
        if self.behavior == 'recover' and self.request_attempts == 1:
            return Turn({'role': 'assistant', 'content': PRIVATE_DETAIL, 'tool_calls': [
                {'id': 'offline-invalid-arguments', 'type': 'function', 'function':
                    {'name': 'check_force', 'arguments': json.dumps({'mu': PRIVATE_DETAIL})}}]}, {})
        if self.behavior == 'selector_recover' and self.request_attempts == 1:
            return Turn({'role': 'assistant', 'content': PRIVATE_DETAIL, 'tool_calls': [
                {'id': 'offline-invalid-selection', 'type': 'function', 'function':
                    {'name': 'select_next_action', 'arguments': json.dumps({'extra': PRIVATE_DETAIL})}}]},
                        {}, protocol_error=dict(PROBLEM))
        return self.fixture.complete(messages, tools)


class LiveValidationTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'work').mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.local = self.root / '.local'
        self.local.mkdir()
        self.path = self.local / 'token-factory.json'
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1',
            'nvidia/offline-nemotron-validation', 'offline-session-approval', 5.0, 0.06, 0.24,
            8192, 180, 'tool_sampling')
        self.original = {**self.config.__dict__, 'account_verified': True,
                         'model_license_reviewed': True, 'spend_approved': True,
                         'custom_nonsecret_note': 'preserve this unrelated field'}
        self.path.write_text(json.dumps(self.original), encoding='utf-8')
        self.output = io.StringIO()

    def invoke(self, factory, *, accept=True, key=SECRET):
        with patch.dict('os.environ', {'NEBIUS_API_KEY': key}), redirect_stdout(self.output), \
                patch.object(validation, 'TokenFactoryProvider', side_effect=factory):
            return validation.validate_live(self.root, accept_contract=accept)

    def summary(self):
        paths = list((self.root / 'artifacts' / 'provider-validation').glob('validation-*.json'))
        self.assertEqual(len(paths), 1)
        return json.loads(paths[0].read_text(encoding='utf-8'))

    def assert_no_private_data(self):
        self.assertNotIn(SECRET, self.output.getvalue())
        self.assertNotIn(PRIVATE_DETAIL, self.output.getvalue())
        for path in self.root.rglob('*.json'):
            self.assertNotIn(SECRET, path.read_text(encoding='utf-8'))
            self.assertNotIn(PRIVATE_DETAIL, path.read_text(encoding='utf-8'))

    def test_acknowledgment_and_key_are_required_before_provider_or_ledger(self):
        for accept, key in ((False, SECRET), (True, '')):
            with self.subTest(accept=accept, key_present=bool(key)):
                factory = unittest.mock.Mock()
                self.assertEqual(self.invoke(factory, accept=accept, key=key), 2)
                factory.assert_not_called()
                self.assertFalse((self.local / 'budget.sqlite3').exists())
        self.assertEqual(json.loads(self.path.read_text()), self.original)
        self.assert_no_private_data()

    def test_invalid_configuration_blocks_before_any_provider(self):
        self.path.write_text('{broken', encoding='utf-8')
        factory = unittest.mock.Mock()
        self.assertEqual(self.invoke(factory), 2)
        factory.assert_not_called()
        self.assertFalse((self.local / 'budget.sqlite3').exists())

    def test_forced_protocol_must_complete_both_distinct_kernel_outcomes(self):
        calls = []

        def factory(config, budget):
            calls.append((config, budget))
            return SyntheticLiveProvider(config, budget)

        self.assertEqual(self.invoke(factory), 0)
        self.assertEqual([config.inference_profile for config, _ in calls],
                         ['native_no_thinking', 'native_no_thinking'])
        self.assertEqual([config.selection_protocol for config, _ in calls],
                         ['forced_action_v1', 'forced_action_v1'])
        summary = self.summary()
        self.assertEqual(summary['state'], 'completed')
        self.assertTrue(summary['configuration_updated'])
        self.assertEqual([row['case'] for row in summary['attempts']], list(validation.CASES))
        self.assertEqual([row['kernel_verdict'] for row in summary['attempts']],
                         ['method_limitation', 'defect_likely'])
        expected = dict(self.original, inference_profile='native_no_thinking', max_output_tokens=2048,
                        selection_protocol='forced_action_v1')
        self.assertEqual(json.loads(self.path.read_text()), expected)
        self.assertEqual(len({id(budget) for _, budget in calls}), 1)
        self.assert_no_private_data()

    def test_failure_on_second_case_does_not_install_partial_profile(self):
        calls = []

        def factory(config, budget):
            calls.append(config.inference_profile)
            return SyntheticLiveProvider(config, budget,
                behavior='complete' if len(calls) == 1 else 'fail')

        self.assertEqual(self.invoke(factory), 2)
        self.assertEqual(calls, ['native_no_thinking', 'native_no_thinking'])
        self.assertEqual(json.loads(self.path.read_text()), self.original)
        summary = self.summary()
        self.assertEqual(summary['attempts'][0]['state'], 'completed')
        self.assertEqual(summary['state'], 'failed')
        self.assertFalse(summary['configuration_updated'])
        self.assertEqual(len(summary['attempts']), 2)
        self.assert_no_private_data()

    def test_failure_stops_the_single_candidate_without_profile_tuning_or_second_case(self):
        calls = []

        def factory(config, budget):
            calls.append((config.inference_profile, config.max_output_tokens))
            return SyntheticLiveProvider(config, budget, behavior='fail')

        self.assertEqual(self.invoke(factory), 2)
        self.assertEqual(calls, [('native_no_thinking', 2048)])
        summary = self.summary()
        self.assertEqual([row['case'] for row in summary['attempts']], ['euler_method_limit'])
        self.assertEqual(summary['selection_protocol'], 'forced_action_v1')
        self.assertEqual(summary['wire_tool'], 'select_next_action')
        self.assertEqual(json.loads(self.path.read_text()), self.original)
        self.assert_no_private_data()

    def test_all_failures_preserve_active_settings_and_save_each_receipt(self):
        calls = []

        def factory(config, budget):
            calls.append((config.inference_profile, config.max_output_tokens))
            return SyntheticLiveProvider(config, budget, behavior='fail')

        self.assertEqual(self.invoke(factory), 2)
        self.assertEqual(calls, list(validation.PROFILES))
        self.assertEqual(json.loads(self.path.read_text()), self.original)
        summary = self.summary()
        self.assertEqual(summary['request_reservations'], 1)
        self.assertEqual(len(summary['attempts']), 1)
        self.assertEqual(summary['session_reserved_usd'], 0.001)
        self.assertEqual(len(list((self.root / 'artifacts' / 'provider-validation')
                                  .glob('????????????????????-*.json'))), 1)
        self.assert_no_private_data()

    def test_offline_mode_cannot_pass_live_gate_even_with_completed_trace(self):
        def factory(config, budget):
            provider = SyntheticLiveProvider(config, budget)
            provider.mode = 'offline_transport_fixture'
            return provider

        self.assertEqual(self.invoke(factory), 2)
        self.assertEqual(json.loads(self.path.read_text()), self.original)
        self.assertFalse(self.summary()['configuration_updated'])

    def test_one_controlled_protocol_correction_preserves_actual_kernel_evidence(self):
        self.assertEqual(self.invoke(lambda config, budget:
                                    SyntheticLiveProvider(config, budget, behavior='recover')), 0)
        summary = self.summary()
        from sixd.reporting import read_report
        for attempt in summary['attempts']:
            report = read_report(attempt['evidence_json'])
            self.assertEqual(report['investigation']['protocol_corrections'], 1)
            self.assertEqual(report['investigation']['trace'][0]['status'], 'rejected')
            self.assertEqual(report['investigation']['trace'][-1]['tool'], 'finish')
        self.assert_no_private_data()

    def test_forced_selector_rejection_is_recorded_as_controlled_operator_code(self):
        self.assertEqual(self.invoke(lambda config, budget:
                                    SyntheticLiveProvider(config, budget, behavior='selector_recover')), 0)
        summary = self.summary()
        from sixd.reporting import read_report
        for attempt in summary['attempts']:
            self.assertEqual(attempt['operator_error_codes'], ['invalid_action_selection'])
            self.assertEqual(attempt['selection_protocol'], 'forced_action_v1')
            self.assertEqual(attempt['wire_tool'], 'select_next_action')
            report = read_report(attempt['evidence_json'])
            rejected = report['investigation']['trace'][0]
            self.assertEqual(rejected['status'], 'rejected')
            self.assertEqual(rejected['error_code'], 'invalid_action_selection')
            self.assertEqual(rejected['wire_tool'], 'select_next_action')
        self.assert_no_private_data()

    def test_invalid_report_digest_never_updates_configuration(self):
        with patch.object(validation, 'verify_payload', side_effect=ValueError(PRIVATE_DETAIL)):
            self.assertEqual(self.invoke(lambda config, budget: SyntheticLiveProvider(config, budget)), 2)
        self.assertEqual(json.loads(self.path.read_text()), self.original)
        self.assertFalse(self.summary()['configuration_updated'])
        self.assert_no_private_data()

    def test_reported_usage_over_reservation_stops_before_another_profile(self):
        providers = []

        def factory(config, budget):
            provider = SyntheticLiveProvider(config, budget, behavior='overbound')
            providers.append(provider)
            return provider

        self.assertEqual(self.invoke(factory), 2)
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0].request_attempts, 1)
        self.assertEqual(len(self.summary()['attempts']), 1)
        self.assertEqual(json.loads(self.path.read_text()), self.original)
        self.assert_no_private_data()

    def test_authentication_and_timeout_failures_do_not_try_another_profile(self):
        for behavior in ('unauthorized', 'timeout'):
            with self.subTest(behavior=behavior):
                providers = []

                def factory(config, budget):
                    provider = SyntheticLiveProvider(config, budget, behavior=behavior)
                    providers.append(provider)
                    return provider

                self.assertEqual(self.invoke(factory), 2)
                self.assertEqual(len(providers), 1)
                self.assertEqual(providers[0].request_attempts, 1)
                self.assertEqual(json.loads(self.path.read_text()), self.original)
        self.assert_no_private_data()

    def test_safe_diagnostic_excludes_remote_text_and_invalid_values(self):
        result = validation.safe_diagnostic({
            'finish_reason': 'length', 'max_output_tokens': 2048, 'inference_profile': 'native_no_thinking',
            'selection_protocol': 'forced_action_v1',
            'private': PRIVATE_DETAIL, 'message': SECRET,
            'usage': {'prompt_tokens': 10, 'completion_tokens': 2048, 'total_tokens': 2058,
                      'remote': PRIVATE_DETAIL, 'completion_tokens_details': {'reasoning_tokens': 2048, 'private': SECRET}},
        })
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn(PRIVATE_DETAIL, json.dumps(result))
        self.assertEqual(result['usage']['completion_tokens_details'], {'reasoning_tokens': 2048})
        self.assertEqual(result['selection_protocol'], 'forced_action_v1')
        self.assertEqual(validation.safe_diagnostic({'finish_reason': SECRET,
                         'usage': {'completion_tokens': True}, 'max_output_tokens': -1}), {'usage': {}})

    def test_changed_configuration_is_not_overwritten_after_completed_cases(self):
        count = 0

        def factory(config, budget):
            nonlocal count
            count += 1
            if count == 2:
                self.path.write_text(json.dumps(dict(self.original, custom_nonsecret_note='external update')),
                                     encoding='utf-8')
            return SyntheticLiveProvider(config, budget)

        self.assertEqual(self.invoke(factory), 2)
        self.assertEqual(json.loads(self.path.read_text())['custom_nonsecret_note'], 'external update')
        self.assertFalse(self.summary()['configuration_updated'])
        self.assert_no_private_data()

    def test_completed_native_tool_receipt_cannot_install_forced_action_protocol(self):
        original_investigate = validation.investigate

        def wrong_protocol(*args, **kwargs):
            report = original_investigate(*args, **kwargs)
            report['investigation']['selection_protocol'] = 'native_tools_v1'
            report['report_payload_sha256'] = digest({key: value for key, value in report.items()
                                                     if key != 'report_payload_sha256'})
            return report

        with patch.object(validation, 'investigate', side_effect=wrong_protocol):
            self.assertEqual(self.invoke(lambda config, budget: SyntheticLiveProvider(config, budget)), 2)
        self.assertEqual(json.loads(self.path.read_text()), self.original)
        self.assertFalse(self.summary()['configuration_updated'])
        self.assert_no_private_data()


class SessionBudgetTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'work').mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'ledger.sqlite3'
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1',
                                'nvidia/offline-nemotron-validation', 'offline-session-approval',
                                5.0, 0.06, 0.24)
        self.ledger = BudgetLedger(self.path)

    def reserved(self):
        with closing(sqlite3.connect(self.path)) as connection:
            return connection.execute('SELECT reserved FROM budget').fetchone()[0]

    def test_session_subcap_preserves_global_cap_and_prior_reservations(self):
        self.ledger.reserve(self.config, 0.75)
        session = validation.SessionBudget(self.ledger)
        session.reserve(self.config, 0.06)
        with self.assertRaises(ProviderError):
            session.reserve(self.config, 0.05)
        self.assertAlmostEqual(session.reserved, 0.06)
        self.assertEqual(session.reservations, 1)
        self.assertAlmostEqual(self.reserved(), 0.81)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute('SELECT cap FROM budget').fetchone()[0], 5.0)

    def test_eleventh_reservation_blocks_before_delegate(self):
        session = validation.SessionBudget(self.ledger)
        for _ in range(10):
            session.reserve(self.config, 0.001)
        before = self.reserved()
        with self.assertRaises(ProviderError):
            session.reserve(self.config, 0.001)
        self.assertEqual(session.reservations, 10)
        self.assertEqual(self.reserved(), before)

    def test_global_rejection_does_not_consume_session_reservation(self):
        self.ledger.reserve(self.config, 4.99)
        session = validation.SessionBudget(self.ledger)
        with self.assertRaises(ProviderError):
            session.reserve(self.config, 0.02)
        self.assertEqual(session.reserved, 0)
        self.assertEqual(session.reservations, 0)

    def test_invalid_amounts_never_reach_ledger(self):
        session = validation.SessionBudget(self.ledger)
        for amount in (-1, float('nan'), float('inf'), True, '0.01'):
            with self.subTest(amount=amount), self.assertRaises(ProviderError):
                session.reserve(self.config, amount)
        self.assertFalse(self.path.exists())


if __name__ == '__main__':
    unittest.main()
