"""Bounded HTTP rejection diagnostics; offline bodies, credentials and ledgers only."""
from contextlib import closing
from pathlib import Path
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.examples import EXAMPLES
from sixd.investigation import investigate
from sixd.live_validation import safe_diagnostic
from sixd.providers import (BudgetLedger, LiveConfig, ProviderError, TokenFactoryProvider,
                            safe_response_diagnostic, transport_failure)
from sixd.reporting import read_report, save_report, verify_payload

SECRET = 'synthetic-http-diagnostic-key-never-output'
PRIVATE = 'untrusted-remote-body-headers-values-never-output'


class ReadRecorder(io.BytesIO):
    def __init__(self, body, *, broken=False):
        super().__init__(body)
        self.limits = []
        self.broken = broken

    def read(self, amount=-1):
        self.limits.append(amount)
        if self.broken:
            raise OSError(SECRET + PRIVATE)
        return super().read(amount)


class HttpValidationDiagnosticTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'work').mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(directory.cleanup)
        self.local = Path(directory.name)
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1',
            'nvidia/offline-nemotron-http-diagnostics', 'offline-http-only', 5.0, 0.06, 0.24)
        self.ledger = BudgetLedger(self.local / 'offline-ledger.sqlite3')

    def error(self, body, *, status=400, broken=False):
        encoded = json.dumps(body).encode() if not isinstance(body, bytes) else body
        reader = ReadRecorder(encoded, broken=broken)
        error = HTTPError('https://invalid.example/' + SECRET, status,
                          PRIVATE + SECRET, {'Untrusted-Header': PRIVATE}, reader)
        self.addCleanup(error.close)
        return error, reader

    def assert_private(self, value):
        encoded = json.dumps(value) if not isinstance(value, str) else value
        self.assertNotIn(SECRET, encoded)
        self.assertNotIn(PRIVATE, encoded)

    def recognized_error(self):
        return self.error({'error': {'type': 'invalid_request_error', 'code': 'invalid_schema',
            'param': 'tools', 'message': f'Unsupported uniqueItems and maxItems in schema. {PRIVATE} {SECRET}',
            'request': SECRET}, 'headers': PRIVATE, 'credentials': SECRET})

    def test_recognized_json_rejection_retains_only_controlled_facts(self):
        error, reader = self.recognized_error()
        result = transport_failure(error)
        self.assertEqual(str(result), 'Nebius request failed: HTTP 400. Reservation retained; no automatic retry.')
        self.assertEqual({key: value for key, value in result.diagnostic.items()
                          if key != 'schema_keyword_mentions'}, {'http_status': 400,
            'api_error_type': 'invalid_request_error', 'api_error_code': 'invalid_schema',
            'rejected_parameter': 'tools'})
        self.assertEqual(set(result.diagnostic['schema_keyword_mentions']), {'maxItems', 'uniqueItems'})
        self.assertTrue(reader.limits)
        # One sentinel byte detects bodies larger than the 8,192-byte parse ceiling.
        self.assertTrue(all(type(limit) is int and 0 < limit <= 8193 for limit in reader.limits))
        self.assert_private(str(result))
        self.assert_private(result.diagnostic)

    def test_unknown_fields_and_embedded_keyword_fragments_are_discarded(self):
        error, _ = self.error({'error': {'type': PRIVATE, 'code': SECRET, 'param': SECRET,
            'message': f'notuniqueItems prefixmaxItemsuffix {PRIVATE} {SECRET}',
            'schema_keyword_mentions': ['anyOf'], 'full_request': SECRET}})
        result = transport_failure(error)
        self.assertEqual(result.diagnostic, {'http_status': 400})
        self.assert_private(result.diagnostic)

    def test_allowed_api_type_numeric_code_and_parameter_are_retained(self):
        error, _ = self.error({'error': {'type': 'BadRequestError', 'code': 400,
            'param': 'response_format', 'message': 'Schema contains oneOf and anyOf.'}})
        result = transport_failure(error).diagnostic
        self.assertEqual({key: value for key, value in result.items()
                          if key != 'schema_keyword_mentions'}, {'http_status': 400,
            'api_error_type': 'BadRequestError', 'api_error_code': 400,
            'rejected_parameter': 'response_format'})
        self.assertEqual(set(result['schema_keyword_mentions']), {'anyOf', 'contains', 'oneOf'})
        for code in (True, 99, 600, 3.5, {'private': SECRET}):
            with self.subTest(code_type=type(code).__name__):
                error, _ = self.error({'error': {'code': code}})
                self.assertEqual(transport_failure(error).diagnostic, {'http_status': 400})

    def test_invalid_large_and_non_json_bodies_fall_back_to_status_only(self):
        bodies = (b'<html>' + SECRET.encode() + b'</html>', b'{broken',
                  json.dumps({'error': {'message': 'x' * 9000 + PRIVATE,
                                       'type': 'invalid_request_error'}}).encode(),
                  json.dumps([{'error': {'type': 'invalid_request_error'}}]).encode())
        for body in bodies:
            with self.subTest(body_length=len(body)):
                error, reader = self.error(body)
                result = transport_failure(error)
                self.assertEqual(result.diagnostic, {'http_status': 400})
                self.assertTrue(all(0 < limit <= 8193 for limit in reader.limits))
                self.assert_private(str(result))
                self.assert_private(result.diagnostic)

    def test_error_body_read_failure_is_private_and_bounded(self):
        error, reader = self.error(b'{}', broken=True)
        result = transport_failure(error)
        self.assertEqual(result.diagnostic, {'http_status': 400})
        self.assertTrue(all(0 < limit <= 8193 for limit in reader.limits))
        self.assert_private(str(result))

    def test_http_rejection_sends_once_and_preserves_budget_reservation(self):
        error, _ = self.recognized_error()
        attempts = []

        def transport(request):
            attempts.append(request.full_url)
            raise error

        provider = TokenFactoryProvider(self.config, self.ledger, api_key=SECRET, transport=transport)
        with self.assertRaises(ProviderError) as caught:
            provider.complete([], [])
        self.assertEqual(len(attempts), 1)
        self.assertEqual(provider.request_attempts, 1)
        self.assertEqual(caught.exception.diagnostic['http_status'], 400)
        with closing(sqlite3.connect(self.ledger.path)) as connection:
            self.assertGreater(connection.execute('SELECT reserved FROM budget').fetchone()[0], 0)
        self.assert_private(str(caught.exception))

    def test_failed_investigation_receipt_preserves_safe_http_facts(self):
        error, _ = self.recognized_error()

        def transport(request):
            raise error

        provider = TokenFactoryProvider(self.config, self.ledger, api_key=SECRET, transport=transport)
        report = investigate(EXAMPLES['euler_method_limit'], provider)
        self.assertEqual(report['investigation']['state'], 'failed')
        self.assertEqual(report['investigation']['failed_provider_response']['api_error_code'], 'invalid_schema')
        self.assertEqual(report['investigation']['failed_provider_response']['rejected_parameter'], 'tools')
        self.assertEqual(provider.request_attempts, 1)
        self.assertEqual(report['live_model_calls'], 0)
        verify_payload(report)
        paths = save_report(report, self.local / 'offline-receipts')
        saved = read_report(paths['json_path'])
        self.assertEqual(saved['investigation']['failed_provider_response'],
                         report['investigation']['failed_provider_response'])
        self.assert_private(json.dumps(saved))

    def test_validation_summary_retains_metadata_without_remote_text(self):
        error, _ = self.recognized_error()
        safe = transport_failure(error).diagnostic
        self.assertEqual(safe_diagnostic(safe), safe)
        polluted = dict(safe, raw_body=PRIVATE, message=SECRET, headers=PRIVATE)
        self.assertEqual(safe_response_diagnostic(polluted), safe)
        self.assertEqual(safe_diagnostic(polluted), safe)
        self.assert_private(safe_diagnostic(polluted))


if __name__ == '__main__':
    unittest.main()
