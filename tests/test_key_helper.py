from contextlib import redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
spec = spec_from_file_location('sixd_key_helper', ROOT / 'tools' / 'with_token_factory_key.py')
helper = module_from_spec(spec)
spec.loader.exec_module(helper)


class KeyHelperTests(unittest.TestCase):
    def test_noninteractive_entry_cannot_prompt_or_run(self):
        with patch.object(helper.sys.stdin, 'isatty', return_value=False), patch.object(helper, 'getpass') as prompt:
            with redirect_stdout(StringIO()):
                self.assertEqual(helper.main(), 2)
            prompt.assert_not_called()

    def test_echo_fallback_is_rejected_and_previous_environment_restored(self):
        def insecure_prompt(*args):
            warnings.warn('No secure terminal', helper.GetPassWarning)
            self.fail('GetPassWarning must abort before insecure input')
        with patch.dict(os.environ, {'NEBIUS_API_KEY': 'offline-prior-test-value'}), \
             patch.object(helper.sys.stdin, 'isatty', return_value=True), \
             patch.object(helper.sys, 'argv', ['helper', 'provider-status']), \
             patch.object(helper, 'getpass', side_effect=insecure_prompt), \
             patch('sixd.cli.main') as command:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(helper.main(), 2)
            command.assert_not_called()
            self.assertEqual(os.environ['NEBIUS_API_KEY'], 'offline-prior-test-value')
            self.assertNotIn('offline-prior-test-value', output.getvalue())

    def test_key_is_available_only_during_command_without_printing(self):
        def local_command(args):
            self.assertEqual(args, ['provider-status'])
            self.assertEqual(os.environ['NEBIUS_API_KEY'], 'offline-new-test-value')
            return 0
        with patch.dict(os.environ, {'NEBIUS_API_KEY': 'offline-prior-test-value'}), \
             patch.object(helper.sys.stdin, 'isatty', return_value=True), \
             patch.object(helper.sys, 'argv', ['helper']), \
             patch.object(helper, 'getpass', return_value='offline-new-test-value'), \
             patch('sixd.cli.main', side_effect=local_command):
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(helper.main(), 0)
            self.assertEqual(os.environ['NEBIUS_API_KEY'], 'offline-prior-test-value')
            self.assertNotIn('offline-new-test-value', output.getvalue())

    def test_cancellation_does_not_run_command(self):
        with patch.object(helper.sys.stdin, 'isatty', return_value=True), \
             patch.object(helper.sys, 'argv', ['helper', 'provider-status']), \
             patch.object(helper, 'getpass', side_effect=KeyboardInterrupt), \
             patch('sixd.cli.main') as command, redirect_stdout(StringIO()):
            self.assertEqual(helper.main(), 2)
            command.assert_not_called()

    def test_live_validation_requires_acknowledgment_before_key_entry(self):
        with patch.object(helper.sys.stdin, 'isatty', return_value=True), \
             patch.object(helper.sys, 'argv', ['helper', 'verify-live']), \
             patch.object(helper, 'getpass') as prompt, redirect_stdout(StringIO()):
            self.assertEqual(helper.main(), 2)
            prompt.assert_not_called()

    def test_live_validation_uses_one_private_entry_and_restores_environment(self):
        def validate(root, *, accept_contract):
            self.assertEqual(root, ROOT)
            self.assertTrue(accept_contract)
            self.assertEqual(os.environ['NEBIUS_API_KEY'], 'offline-new-test-value')
            return 0
        with patch.dict(os.environ, {'NEBIUS_API_KEY': 'offline-prior-test-value'}), \
             patch.object(helper.sys.stdin, 'isatty', return_value=True), \
             patch.object(helper.sys, 'argv', ['helper', 'verify-live', '--accept-contract']), \
             patch.object(helper, 'getpass', return_value='offline-new-test-value') as prompt, \
             patch('sixd.live_validation.validate_live', side_effect=validate), \
             patch('sixd.cli.main') as ordinary_command:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(helper.main(), 0)
            prompt.assert_called_once()
            ordinary_command.assert_not_called()
            self.assertEqual(os.environ['NEBIUS_API_KEY'], 'offline-prior-test-value')
            self.assertNotIn('offline-new-test-value', output.getvalue())

    def test_unexpected_live_validation_error_hides_private_details_and_cleans_key(self):
        with patch.dict(os.environ, {'NEBIUS_API_KEY': 'offline-prior-test-value'}), \
             patch.object(helper.sys.stdin, 'isatty', return_value=True), \
             patch.object(helper.sys, 'argv', ['helper', 'verify-live', '--accept-contract']), \
             patch.object(helper, 'getpass', return_value='offline-new-test-value'), \
             patch('sixd.live_validation.validate_live', side_effect=RuntimeError('offline-new-test-value')):
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(helper.main(), 2)
            self.assertEqual(os.environ['NEBIUS_API_KEY'], 'offline-prior-test-value')
            self.assertNotIn('offline-new-test-value', output.getvalue())


if __name__ == '__main__':
    unittest.main()
