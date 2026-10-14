"""Offline checks for actionable, credential-safe inference failure diagnostics."""
from contextlib import closing
from pathlib import Path
import copy
import io
import json
import sqlite3
import ssl
import sys
import tempfile
import unittest
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.providers import BudgetLedger, LiveConfig, ProviderError, TokenFactoryProvider


SECRET = 'offline-synthetic-credential-never-display'
REMOTE_DETAIL = 'untrusted-provider-body-and-headers-never-display'


def tool_response():
    return {
        'choices': [{
            'finish_reason': 'tool_calls',
            'message': {
                'role': 'assistant', 'content': None,
                'tool_calls': [{'id': 'offline-call-1', 'type': 'function',
                    'function': {'name': 'check_force', 'arguments': '{}'}}],
            },
        }],
        'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70},
    }


class ProviderDiagnosticTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'work').mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(directory.cleanup)
        self.local = Path(directory.name)
        self.config = LiveConfig(
            'https://api.tokenfactory.nebius.com/v1',
            'nvidia/offline-nemotron-diagnostic-test',
            'offline-diagnostic-tests-only', 5.0, 0.06, 0.24, 1024,
        )
        self.ledger = BudgetLedger(self.local / 'budget.sqlite3')

    def reserved(self):
        if not self.ledger.path.exists():
            return 0.0
        with closing(sqlite3.connect(self.ledger.path)) as db:
            return db.execute('SELECT reserved FROM budget').fetchone()[0]

    def failed_completion(self, *, exception=None, response=None, diagnostic):
        attempts = []
        before = self.reserved()

        def transport(request):
            attempts.append(request.full_url)
            if exception is not None:
                raise exception
            return copy.deepcopy(response)

        provider = TokenFactoryProvider(
            self.config, self.ledger, api_key=SECRET, transport=transport,
        )
        self.assertEqual(provider.mode, 'offline_transport_fixture')
        with self.assertRaises(ProviderError) as caught:
            provider.complete([], [])
        message = str(caught.exception)
        self.assertIn(diagnostic, message)
        self.assertNotIn(SECRET, message)
        self.assertNotIn(REMOTE_DETAIL, message)
        self.assertEqual(provider.request_attempts, 1)
        self.assertEqual(len(attempts), 1, 'A failed completion must not retry automatically.')
        self.assertGreater(self.reserved(), before, 'The failed request must retain its reservation.')
        return message

    def test_http_status_is_actionable_without_remote_body_headers_or_exception_text(self):
        for status in (400, 401, 403, 404, 429, 500):
            with self.subTest(status=status):
                error = HTTPError(
                    'https://invalid.example/' + SECRET, status,
                    SECRET + REMOTE_DETAIL, {'Remote-Detail': REMOTE_DETAIL},
                    io.BytesIO((SECRET + REMOTE_DETAIL).encode()),
                )
                self.addCleanup(error.close)
                self.failed_completion(exception=error, diagnostic=f'HTTP {status}')

    def test_timeout_is_distinguished_from_invalid_model_output(self):
        for error in (TimeoutError(SECRET + REMOTE_DETAIL),
                      URLError(TimeoutError(SECRET + REMOTE_DETAIL))):
            with self.subTest(error_type=type(error).__name__):
                self.failed_completion(exception=error, diagnostic='timed out')

    def test_network_error_does_not_echo_url_or_operating_system_error(self):
        self.failed_completion(
            exception=URLError(SECRET + REMOTE_DETAIL), diagnostic='network connection',
        )

    def test_tls_failure_is_distinguished_from_general_network_failure(self):
        for error in (ssl.SSLError(SECRET + REMOTE_DETAIL),
                      URLError(ssl.SSLCertVerificationError(SECRET + REMOTE_DETAIL))):
            with self.subTest(error_type=type(error).__name__):
                self.failed_completion(exception=error, diagnostic='TLS')

    def test_non_json_response_does_not_echo_provider_document(self):
        self.failed_completion(
            exception=json.JSONDecodeError(REMOTE_DETAIL, SECRET, 0), diagnostic='valid JSON',
        )

    def test_malformed_response_structure_is_reported_without_echoing_values(self):
        valid = tool_response()
        variants = [
            None, [], {'choices': []}, {'choices': None}, {'choices': [None]},
            {'choices': [{'finish_reason': 'tool_calls', 'message': None}]},
            {'choices': [{'finish_reason': 'tool_calls', 'message': [SECRET]}]},
            {**valid, 'usage': [SECRET]}, {**valid, 'usage': None},
        ]
        for position, result in enumerate(variants):
            with self.subTest(case=position):
                self.failed_completion(
                    response=result, diagnostic='Invalid provider response structure',
                )

    def test_invalid_usage_counts_are_not_silently_treated_as_zero(self):
        for field, value in (('prompt_tokens', -1), ('completion_tokens', True),
                             ('total_tokens', SECRET), ('completion_tokens', 1.5)):
            with self.subTest(field=field):
                result = tool_response()
                result['usage'][field] = value
                self.failed_completion(
                    response=result, diagnostic='Invalid provider response structure',
                )

    def test_output_truncation_identifies_token_limit_without_showing_partial_text(self):
        result = tool_response()
        result['choices'][0]['finish_reason'] = 'length'
        result['choices'][0]['message'] = {'role': 'assistant', 'content': SECRET + REMOTE_DETAIL}
        message = self.failed_completion(response=result, diagnostic='finish_reason=length')
        self.assertIn('output token limit', message)

    def test_text_stop_is_distinguished_from_token_truncation(self):
        result = tool_response()
        result['choices'][0]['finish_reason'] = 'stop'
        result['choices'][0]['message'] = {'role': 'assistant', 'content': SECRET}
        self.failed_completion(response=result, diagnostic='finish_reason=stop')

    def test_missing_or_unrecognized_finish_reason_never_echoes_it(self):
        for reason in (None, SECRET + REMOTE_DETAIL, {'untrusted': SECRET}):
            with self.subTest(reason_type=type(reason).__name__):
                result = tool_response()
                result['choices'][0]['finish_reason'] = reason
                self.failed_completion(response=result, diagnostic='unknown')
        result = tool_response()
        del result['choices'][0]['finish_reason']
        self.failed_completion(response=result, diagnostic='unknown')

    def test_usage_over_the_reserved_limit_retains_its_specific_diagnostic(self):
        result = tool_response()
        result['usage']['completion_tokens'] = self.config.max_output_tokens + 1
        self.failed_completion(response=result, diagnostic='Usage exceeded')

    def test_bounded_response_error_has_a_controlled_safe_message(self):
        self.failed_completion(
            exception=ProviderError('Provider response exceeded the bounded size.'),
            diagnostic='bounded size',
        )

    def test_arbitrary_transport_exception_and_provider_error_are_sanitized(self):
        for error in (RuntimeError(SECRET + REMOTE_DETAIL),
                      ProviderError(SECRET + REMOTE_DETAIL)):
            with self.subTest(error_type=type(error).__name__):
                self.failed_completion(exception=error, diagnostic='transport failed')

    def test_valid_tool_calls_keep_usage_and_drop_untrusted_remote_metadata(self):
        result = tool_response()
        result['usage']['remote_echo'] = SECRET
        result['id'] = SECRET
        attempts = []

        def transport(request):
            attempts.append(request.full_url)
            return result

        provider = TokenFactoryProvider(
            self.config, self.ledger, api_key=SECRET, transport=transport,
        )
        turn = provider.complete([], [])
        self.assertEqual(provider.mode, 'offline_transport_fixture')
        self.assertEqual(turn.message, result['choices'][0]['message'])
        self.assertEqual(turn.usage, {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70})
        self.assertIsNone(turn.request_id)
        self.assertNotIn(SECRET, repr(turn))
        self.assertEqual(provider.request_attempts, 1)
        self.assertEqual(len(attempts), 1)
        self.assertGreater(self.reserved(), 0)

    def test_absent_usage_remains_unknown_with_the_reservation_intact(self):
        result = tool_response()
        del result['usage']
        provider = TokenFactoryProvider(
            self.config, self.ledger, api_key=SECRET, transport=lambda request: result,
        )
        turn = provider.complete([], [])
        self.assertEqual(turn.usage, {})
        self.assertEqual(provider.mode, 'offline_transport_fixture')
        self.assertEqual(provider.request_attempts, 1)
        self.assertGreater(self.reserved(), 0)


if __name__ == '__main__':
    unittest.main()
