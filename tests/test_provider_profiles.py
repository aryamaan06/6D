"""Offline hosted-profile and sanitized failure-receipt regressions."""
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import copy
import json
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.providers import BudgetLedger, LiveConfig, ProviderError, TokenFactoryProvider
from sixd.examples import EXAMPLES
from sixd.investigation import investigate
from sixd.kernel import audit
from sixd.reporting import verify_payload


TEST_KEY = 'synthetic-offline-profile-test-only'
PRIVATE_SENTINEL = 'private-remote-data-must-not-enter-diagnostics'
TOOLS = [{
    'type': 'function',
    'function': {'name': 'check_force', 'description': 'Run the supported force check.',
                 'parameters': {'type': 'object', 'properties': {},
                                'additionalProperties': False}},
}]


def tool_response(*, reason='tool_calls', usage=None):
    return {
        'choices': [{
            'finish_reason': reason,
            'message': {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'offline-profile-call', 'type': 'function',
                 'function': {'name': 'check_force', 'arguments': '{}'}}]},
        }],
        'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}
                 if usage is None else usage,
    }


class ProviderProfileTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / 'work'
        scratch.mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(directory.cleanup)
        self.local = Path(directory.name)
        self.config = LiveConfig(
            'https://api.tokenfactory.nebius.com/v1',
            'nvidia/offline-nemotron-profile-test',
            'offline-profile-tests-only', 5.0, 0.06, 0.24, 8192, 180,
        )
        self.ledger = BudgetLedger(self.local / 'budget.sqlite3')
        self.sent = []

    def load(self, mutation=None, omitted=()):
        data = {**self.config.__dict__, 'account_verified': True,
                'model_license_reviewed': True, 'spend_approved': True,
                **(mutation or {})}
        for field in omitted:
            data.pop(field, None)
        path = self.local / 'offline-config.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return LiveConfig.load(path)

    def reserved(self):
        if not self.ledger.path.exists():
            return 0.0
        with closing(sqlite3.connect(self.ledger.path)) as db:
            row = db.execute('SELECT id, cap, reserved FROM budget').fetchone()
        self.assertEqual(row[:2], (self.config.approval_id, self.config.spend_cap_usd))
        return row[2]

    def provider(self, result=None, profile=None):
        config = self.config if profile is None else replace(self.config, inference_profile=profile)

        def transport(request):
            payload = json.loads(request.data)
            self.sent.append(payload)
            self.assertNotIn(TEST_KEY, request.data.decode('utf-8'))
            return tool_response() if result is None else copy.deepcopy(result)

        return TokenFactoryProvider(config, self.ledger, api_key=TEST_KEY, transport=transport)

    def assert_common_payload(self, payload):
        self.assertEqual(payload['model'], self.config.model)
        self.assertEqual(payload['max_tokens'], 8192)
        self.assertIs(payload['stream'], False)
        self.assertEqual(payload['tools'], TOOLS)
        self.assertEqual(payload['tool_choice'],
                         {'type': 'function', 'function': {'name': 'check_force'}})
        self.assertNotIn('extra_body', payload)
        self.assertNotIn('max_completion_tokens', payload)

    def test_legacy_config_defaults_to_documented_tool_sampling(self):
        config = self.load(omitted=('inference_profile',))
        self.assertEqual(config.inference_profile, 'tool_sampling')
        self.assertEqual(config.max_output_tokens, 8192)
        self.assertEqual(config.spend_cap_usd, 5)

    def test_profiles_load_only_explicit_allowlisted_names(self):
        for profile in ('tool_sampling', 'nebius_no_reasoning', 'native_no_thinking'):
            with self.subTest(profile=profile):
                self.assertEqual(self.load({'inference_profile': profile}).inference_profile, profile)
        for value in (None, True, False, 0, 1.0, [], {}, '', 'auto', 'TOOL_SAMPLING',
                      'nebius_no_reasoning ', PRIVATE_SENTINEL):
            with self.subTest(value=value), self.assertRaises(ProviderError) as caught:
                self.load({'inference_profile': value})
            self.assertNotIn(PRIVATE_SENTINEL, str(caught.exception))

    def test_tool_sampling_payload_uses_publisher_tool_recommendation(self):
        provider = self.provider(profile='tool_sampling')
        provider.complete([], TOOLS)
        payload = self.sent[0]
        self.assert_common_payload(payload)
        self.assertEqual(payload['temperature'], 0.6)
        self.assertEqual(payload['top_p'], 0.95)
        self.assertNotIn('reasoning_effort', payload)
        self.assertNotIn('chat_template_kwargs', payload)
        self.assertEqual(provider.request_attempts, 1)

    def test_nebius_no_reasoning_uses_documented_top_level_effort(self):
        provider = self.provider(profile='nebius_no_reasoning')
        provider.complete([], TOOLS)
        payload = self.sent[0]
        self.assert_common_payload(payload)
        self.assertEqual(payload['temperature'], 0)
        self.assertEqual(payload['reasoning_effort'], 'none')
        self.assertNotIn('top_p', payload)
        self.assertNotIn('chat_template_kwargs', payload)
        self.assertEqual(provider.request_attempts, 1)

    def test_native_no_thinking_flattens_template_kwargs_into_wire_body(self):
        provider = self.provider(profile='native_no_thinking')
        provider.complete([], TOOLS)
        payload = self.sent[0]
        self.assert_common_payload(payload)
        self.assertEqual(payload['temperature'], 0)
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': False})
        self.assertNotIn('top_p', payload)
        self.assertNotIn('reasoning_effort', payload)
        self.assertEqual(provider.request_attempts, 1)

    def test_multi_tool_selection_stays_auto_for_every_profile(self):
        multiple = TOOLS + [{
            'type': 'function', 'function': {'name': 'finish', 'parameters': {'type': 'object'}}
        }]
        for profile in ('tool_sampling', 'nebius_no_reasoning', 'native_no_thinking'):
            with self.subTest(profile=profile):
                self.provider(profile=profile).complete([], multiple)
                self.assertEqual(self.sent[-1]['tool_choice'], 'auto')

    def test_reasoning_count_is_preserved_without_other_remote_metadata(self):
        usage = {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70,
                 'completion_tokens_details': {'reasoning_tokens': 15,
                     'private_metadata': PRIVATE_SENTINEL, 'accepted_prediction_tokens': 4},
                 'private_metadata': PRIVATE_SENTINEL}
        turn = self.provider(tool_response(usage=usage)).complete([], TOOLS)
        self.assertEqual(turn.usage, {'prompt_tokens': 50, 'completion_tokens': 20,
            'total_tokens': 70, 'completion_tokens_details': {'reasoning_tokens': 15}})
        self.assertNotIn(PRIVATE_SENTINEL, json.dumps(turn.usage))

    def test_absent_reasoning_count_is_not_invented(self):
        for usage in ({}, {'prompt_tokens': 50, 'completion_tokens': 20},
                      {'prompt_tokens': 50, 'completion_tokens': 20,
                       'completion_tokens_details': {'other': PRIVATE_SENTINEL}}):
            with self.subTest(usage=usage):
                turn = self.provider(tool_response(usage=usage)).complete([], TOOLS)
                expected = {key: value for key, value in usage.items()
                            if key in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
                self.assertEqual(turn.usage, expected)

    def test_zero_and_full_completion_reasoning_counts_are_valid(self):
        for count in (0, 20):
            with self.subTest(count=count):
                usage = {'prompt_tokens': 50, 'completion_tokens': 20,
                         'completion_tokens_details': {'reasoning_tokens': count}}
                turn = self.provider(tool_response(usage=usage)).complete([], TOOLS)
                self.assertEqual(turn.usage['completion_tokens_details']['reasoning_tokens'], count)

    def test_malformed_reasoning_count_is_rejected_without_retry_or_refund(self):
        for value in (True, False, -1, 21, 0.0, '1', None, {}, [], PRIVATE_SENTINEL):
            with self.subTest(value=value):
                usage = {'prompt_tokens': 50, 'completion_tokens': 20,
                         'completion_tokens_details': {'reasoning_tokens': value}}
                provider = self.provider(tool_response(usage=usage))
                before = self.reserved()
                with self.assertRaises(ProviderError) as caught:
                    provider.complete([], TOOLS)
                self.assertEqual(provider.request_attempts, 1)
                self.assertGreater(self.reserved(), before)
                self.assertNotIn(PRIVATE_SENTINEL, str(caught.exception))
                self.assertNotIn(PRIVATE_SENTINEL, repr(getattr(caught.exception, 'diagnostic', None)))

    def test_malformed_reasoning_details_container_is_rejected(self):
        for value in ([], 'private-details', 20, True):
            with self.subTest(value=value):
                usage = {'prompt_tokens': 50, 'completion_tokens': 20,
                         'completion_tokens_details': value}
                with self.assertRaises(ProviderError):
                    self.provider(tool_response(usage=usage)).complete([], TOOLS)

    def test_nullable_optional_reasoning_details_stay_unknown(self):
        usage = {'prompt_tokens': 50, 'completion_tokens': 20,
                 'completion_tokens_details': None}
        turn = self.provider(tool_response(usage=usage)).complete([], TOOLS)
        self.assertEqual(turn.usage, {'prompt_tokens': 50, 'completion_tokens': 20})

    def test_length_failure_retains_safe_observed_counts_and_configuration(self):
        usage = {'prompt_tokens': 50, 'completion_tokens': 8192, 'total_tokens': 8242,
                 'completion_tokens_details': {'reasoning_tokens': 8000,
                                               'private_metadata': PRIVATE_SENTINEL},
                 'echoed_secret': TEST_KEY}
        result = tool_response(reason='length', usage=usage)
        result['choices'][0]['message']['content'] = PRIVATE_SENTINEL
        result['choices'][0]['message']['reasoning_content'] = PRIVATE_SENTINEL
        result['remote_metadata'] = PRIVATE_SENTINEL
        provider = self.provider(result, profile='nebius_no_reasoning')
        with self.assertRaisesRegex(ProviderError, 'finish_reason=length') as caught:
            provider.complete([], TOOLS)
        diagnostic = caught.exception.diagnostic
        self.assertEqual(set(diagnostic),
                         {'finish_reason', 'usage', 'max_output_tokens', 'inference_profile'})
        self.assertEqual(diagnostic['finish_reason'], 'length')
        self.assertEqual(diagnostic['inference_profile'], 'nebius_no_reasoning')
        self.assertEqual(diagnostic['max_output_tokens'], 8192)
        self.assertEqual(diagnostic['usage'], {'prompt_tokens': 50, 'completion_tokens': 8192,
            'total_tokens': 8242, 'completion_tokens_details': {'reasoning_tokens': 8000}})
        self.assertNotIn(PRIVATE_SENTINEL, json.dumps(diagnostic))
        self.assertNotIn(TEST_KEY, json.dumps(diagnostic))
        self.assertEqual(provider.request_attempts, 1)
        self.assertEqual(len(self.sent), 1)
        self.assertGreater(self.reserved(), 0)

    def test_missing_usage_on_length_failure_remains_unknown(self):
        result = tool_response(reason='length')
        del result['usage']
        with self.assertRaises(ProviderError) as caught:
            self.provider(result).complete([], TOOLS)
        self.assertEqual(caught.exception.diagnostic['usage'], {})
        self.assertNotIn('completion_tokens_details', caught.exception.diagnostic['usage'])

    def test_unknown_finish_reason_is_never_echoed_into_error_or_receipt(self):
        provider = self.provider(tool_response(reason=PRIVATE_SENTINEL))
        with self.assertRaisesRegex(ProviderError, 'finish_reason=unknown') as caught:
            provider.complete([], TOOLS)
        self.assertEqual(caught.exception.diagnostic['finish_reason'], 'unknown')
        self.assertNotIn(PRIVATE_SENTINEL, str(caught.exception))
        self.assertNotIn(PRIVATE_SENTINEL, json.dumps(caught.exception.diagnostic))
        self.assertEqual(provider.request_attempts, 1)

    def test_overbound_usage_is_not_promoted_into_trustworthy_diagnostic(self):
        result = tool_response(reason='length', usage={
            'prompt_tokens': 50, 'completion_tokens': 8193, 'total_tokens': 8243,
            'completion_tokens_details': {'reasoning_tokens': 8193},
            'private_metadata': PRIVATE_SENTINEL,
        })
        with self.assertRaisesRegex(ProviderError, 'Usage exceeded') as caught:
            self.provider(result).complete([], TOOLS)
        diagnostic = getattr(caught.exception, 'diagnostic', {}) or {}
        self.assertNotIn('completion_tokens', diagnostic.get('usage', {}))
        self.assertNotIn(PRIVATE_SENTINEL, json.dumps(diagnostic))
        self.assertGreater(self.reserved(), 0)

    def test_profile_changes_keep_the_same_persistent_cumulative_budget(self):
        self.ledger.reserve(self.config, 1.0)
        previous = self.reserved()
        for profile in ('tool_sampling', 'nebius_no_reasoning', 'native_no_thinking'):
            with self.subTest(profile=profile):
                provider = self.provider(tool_response(reason='length'), profile=profile)
                with self.assertRaises(ProviderError):
                    provider.complete([], TOOLS)
                observed = self.reserved()
                self.assertGreater(observed, previous)
                self.assertLess(observed, 5.0)
                BudgetLedger(self.ledger.path).reserve(provider.config, 0.0)
                self.assertEqual(self.reserved(), observed)
                self.assertEqual(provider.config.approval_id, self.config.approval_id)
                self.assertEqual(provider.config.spend_cap_usd, 5.0)
                previous = observed

    def test_investigation_retains_failure_counts_without_accepting_a_tool_response(self):
        result = tool_response(reason='length', usage={
            'prompt_tokens': 50, 'completion_tokens': 8192, 'total_tokens': 8242,
            'completion_tokens_details': {'reasoning_tokens': 8000,
                                          'remote_metadata': PRIVATE_SENTINEL},
        })
        result['choices'][0]['message']['content'] = PRIVATE_SENTINEL
        provider = self.provider(result, profile='nebius_no_reasoning')
        example = EXAMPLES['euler_method_limit']
        baseline = audit(example)
        report = investigate(example, provider)
        run = report['investigation']
        self.assertEqual(run['state'], 'failed')
        self.assertEqual(run['provider_attempts'], 1)
        self.assertEqual(run['provider_successes'], 0)
        self.assertEqual(run['usage'], [])
        self.assertEqual(run['trace'], [])
        self.assertEqual(run['failed_provider_response'], {
            'finish_reason': 'length', 'max_output_tokens': 8192,
            'inference_profile': 'nebius_no_reasoning',
            'usage': {'prompt_tokens': 50, 'completion_tokens': 8192, 'total_tokens': 8242,
                      'completion_tokens_details': {'reasoning_tokens': 8000}},
        })
        self.assertEqual(report['checks'], baseline['checks'])
        self.assertEqual(report['verdict'], baseline['verdict'])
        self.assertEqual(report['live_model_calls'], 0)
        self.assertEqual(provider.request_attempts, 1)
        self.assertEqual(len(self.sent), 1)
        self.assertNotIn(PRIVATE_SENTINEL, json.dumps(report))
        self.assertGreater(self.reserved(), 0)
        verify_payload(report)


if __name__ == '__main__':
    unittest.main()
