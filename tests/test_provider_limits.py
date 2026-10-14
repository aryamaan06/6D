"""Offline completion-budget and timeout regressions; never use live credentials."""
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.providers import BudgetLedger, LiveConfig, ProviderError, TokenFactoryProvider


TEST_KEY = 'synthetic-offline-limit-test-only'


def tool_response(completion_tokens=20):
    return {
        'choices': [{
            'finish_reason': 'tool_calls',
            'message': {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'offline-limit-call', 'type': 'function',
                 'function': {'name': 'check_force', 'arguments': '{}'}}]},
        }],
        'usage': {'prompt_tokens': 50, 'completion_tokens': completion_tokens,
                  'total_tokens': completion_tokens + 50},
    }


class ProviderLimitTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / 'work'
        scratch.mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(directory.cleanup)
        self.local = Path(directory.name)
        self.config = LiveConfig(
            'https://api.tokenfactory.nebius.com/v1',
            'nvidia/offline-nemotron-limit-test',
            'offline-limit-tests-only', 5.0, 0.06, 0.24, 1024,
        )
        self.ledger = BudgetLedger(self.local / 'budget.sqlite3')

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

    def test_legacy_config_without_timeout_keeps_original_45_second_default(self):
        config = self.load(omitted=('request_timeout_seconds',))
        self.assertEqual(config.request_timeout_seconds, 45)
        self.assertEqual(config.max_output_tokens, 1024)

    def test_missing_optional_fields_use_defaults_without_weakening_required_gates(self):
        config = self.load(omitted=('request_timeout_seconds', 'max_output_tokens'))
        self.assertEqual(config.request_timeout_seconds, 45)
        self.assertEqual(config.max_output_tokens, 1024)
        for missing in ('model', 'approval_id', 'spend_cap_usd'):
            with self.subTest(missing=missing), self.assertRaises(ProviderError):
                self.load(omitted=(missing,))
        with self.assertRaises(ProviderError):
            self.load({'spend_approved': False})

    def test_supported_completion_and_timeout_boundaries_load(self):
        for tokens, timeout in ((128, 15), (1024, 45), (8192, 180)):
            with self.subTest(tokens=tokens, timeout=timeout):
                config = self.load({'max_output_tokens': tokens,
                                    'request_timeout_seconds': timeout})
                self.assertEqual(config.max_output_tokens, tokens)
                self.assertEqual(config.request_timeout_seconds, timeout)

    def test_completion_limit_rejects_non_integer_or_out_of_range_values(self):
        for value in (127, 8193, -1, True, False, 8192.0, '8192', None):
            with self.subTest(value=value), self.assertRaises(ProviderError):
                self.load({'max_output_tokens': value})

    def test_timeout_rejects_non_integer_or_out_of_range_values(self):
        for value in (14, 181, -1, True, False, 180.0, '180', None):
            with self.subTest(value=value), self.assertRaises(ProviderError):
                self.load({'request_timeout_seconds': value})

    def test_larger_completion_retains_failed_prior_reservation_across_restart(self):
        truncated = tool_response()
        truncated['choices'][0]['finish_reason'] = 'length'
        original = TokenFactoryProvider(
            self.config, self.ledger, api_key=TEST_KEY,
            transport=lambda request: truncated,
        )
        with self.assertRaisesRegex(ProviderError, 'finish_reason=length'):
            original.complete([], [])
        prior = self.reserved()
        self.assertGreater(prior, 0)

        larger = replace(self.config, max_output_tokens=8192, request_timeout_seconds=180)
        restarted = TokenFactoryProvider(
            larger, BudgetLedger(self.ledger.path), api_key=TEST_KEY,
            transport=lambda request: tool_response(),
        )
        restarted.complete([], [])
        after = self.reserved()
        self.assertGreater(after - prior, prior, 'The larger output allowance must reserve more.')
        self.assertGreater(after, prior, 'Existing reservations must not be reset.')
        # A new ledger instance sees the cumulative amount for the same approval.
        BudgetLedger(self.ledger.path).reserve(larger, 0.0)
        self.assertEqual(self.reserved(), after)
        self.assertEqual(original.request_attempts, 1)
        self.assertEqual(restarted.request_attempts, 1)

    def test_larger_completion_cap_blocks_before_transport_and_preserves_ledger(self):
        self.ledger.reserve(self.config, 4.999)
        before = self.reserved()
        attempted = []

        def forbidden_transport(request):
            attempted.append(request)
            self.fail('Insufficient allowance must block before the transport.')

        provider = TokenFactoryProvider(
            replace(self.config, max_output_tokens=8192), BudgetLedger(self.ledger.path),
            api_key=TEST_KEY, transport=forbidden_transport,
        )
        with self.assertRaisesRegex(ProviderError, 'allowance is exhausted'):
            provider.complete([], [])
        self.assertEqual(attempted, [])
        self.assertEqual(provider.request_attempts, 0)
        self.assertEqual(self.reserved(), before)

    def test_usage_above_new_completion_bound_is_rejected_without_refund(self):
        provider = TokenFactoryProvider(
            replace(self.config, max_output_tokens=8192), self.ledger, api_key=TEST_KEY,
            transport=lambda request: tool_response(completion_tokens=8193),
        )
        with self.assertRaisesRegex(ProviderError, 'Usage exceeded'):
            provider.complete([], [])
        self.assertEqual(provider.request_attempts, 1)
        self.assertGreater(self.reserved(), 0)

    def test_exact_new_completion_bound_is_accepted_in_offline_response(self):
        observed = []

        def transport(request):
            payload = json.loads(request.data)
            observed.append(payload)
            self.assertEqual(payload['max_tokens'], 8192)
            self.assertNotIn('max_completion_tokens', payload)
            self.assertNotIn('reasoning', payload)
            self.assertNotIn(TEST_KEY, request.data.decode('utf-8'))
            return tool_response(completion_tokens=8192)

        provider = TokenFactoryProvider(
            replace(self.config, max_output_tokens=8192), self.ledger,
            api_key=TEST_KEY, transport=transport,
        )
        turn = provider.complete([], [])
        self.assertEqual(turn.usage['completion_tokens'], 8192)
        self.assertEqual(len(observed), 1)
        self.assertEqual(provider.mode, 'offline_transport_fixture')

    def test_configured_timeout_reaches_http_opener_without_network(self):
        config = self.load({'max_output_tokens': 8192, 'request_timeout_seconds': 180})
        response = io.BytesIO(json.dumps(tool_response()).encode('utf-8'))
        provider = TokenFactoryProvider(config, self.ledger, api_key=TEST_KEY)
        with patch('sixd.providers.build_opener') as build:
            opener = build.return_value
            opener.open.return_value = response
            turn = provider.complete([], [])
            self.assertEqual(opener.open.call_count, 1)
            positional, keyword = opener.open.call_args
            self.assertEqual(keyword['timeout'], 180)
            self.assertEqual(positional[0].full_url,
                             'https://api.tokenfactory.nebius.com/v1/chat/completions')
            self.assertEqual(json.loads(positional[0].data)['max_tokens'], 8192)
        self.assertEqual(turn.usage['completion_tokens'], 20)
        self.assertEqual(provider.request_attempts, 1)
        self.assertTrue(response.closed)


if __name__ == '__main__':
    unittest.main()
