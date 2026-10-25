"""Operator-only hosted settings and carryforward; no provider calls."""
from dataclasses import replace
import json
import os
from pathlib import Path
import runpy
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from sixd.hosted_runtime import HostedRuntimeFactory, carried_reservation, read_private_file
from sixd.providers import LiveConfig, ProviderError

KEY = 'synthetic-hosted-operator-key-only'


class HostedRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.folder = Path(self.temp.name)
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1/',
            'nvidia/offline-nemotron-http-test', 'hosted-test-approval', 5, .06, .24,
            2048, 45, 'native_no_thinking', 'forced_action_v1')
        self.prior = self.folder / 'frozen-budget.sqlite3'
        db = sqlite3.connect(self.prior)
        try:
            db.execute('CREATE TABLE budget (id TEXT PRIMARY KEY,cap REAL,reserved REAL)')
            db.execute('INSERT INTO budget VALUES (?,?,?)', (self.config.approval_id, 5, 1.25))
            db.commit()
        finally:
            db.close()
        self.state = self.folder / 'state'

    def tearDown(self):
        self.temp.cleanup()

    def factory(self, **overrides):
        options = dict(config=self.config, api_key=KEY, prior_budget_path=self.prior,
                       daily_cap_usd=1, session_cap_usd=.2, transport=lambda request: self.fail('No provider request allowed'))
        options.update(overrides)
        return HostedRuntimeFactory(self.state, **options)

    def test_offline_mode_ignores_ambient_key_and_never_copies_founder_credentials(self):
        with patch.dict(os.environ, {'NEBIUS_API_KEY': KEY}):
            runtime = HostedRuntimeFactory(self.state)(self.state / '1234567890abcdef1234567890abcdef', '1234567890abcdef1234567890abcdef')
        self.assertFalse(runtime.ai.status()['key_present'])
        self.assertFalse(runtime.ai.status()['configured'])
        self.assertFalse(runtime.research.status()['key_present'])
        self.assertFalse(runtime.observability.status()['key_present'])
        self.assertFalse((self.state / '1234567890abcdef1234567890abcdef/private/credentials').exists())

    def test_live_key_stays_in_memory_and_carryforward_is_preserved(self):
        before = self.prior.read_bytes()
        factory = self.factory()
        runtime = factory(self.state / '1234567890abcdef1234567890abcdef', '1234567890abcdef1234567890abcdef')
        self.assertTrue(runtime.ai.status()['configured'])
        self.assertEqual(runtime.ai.status()['key_source'], 'hosted_operator')
        self.assertEqual(runtime.ai.status()['budget']['remaining_usd'], 3.75)
        self.assertEqual(runtime.ai.status()['budget']['hosted_limits']['session_remaining_usd'], .2)
        for path in self.state.rglob('*'):
            if path.is_file():
                self.assertNotIn(KEY.encode(), path.read_bytes())
        self.assertEqual(self.prior.read_bytes(), before)
        self.assertEqual(carried_reservation(self.prior, self.config), 1.25)
        self.assertIsNotNone(factory.ledger)

    def test_live_requires_complete_configuration_and_matching_frozen_ledger(self):
        for overrides in ({'api_key': None}, {'prior_budget_path': None},
                          {'config': replace(self.config, approval_id='other')},
                          {'config': replace(self.config, spend_cap_usd=6)},
                          {'config': replace(self.config, selection_protocol='native_tools_v1')}):
            with self.subTest(overrides=list(overrides)):
                with self.assertRaises((ValueError, ProviderError)):
                    self.factory(**overrides)
        with self.assertRaises(ValueError):
            HostedRuntimeFactory(self.state, api_key=KEY)

    def test_session_cannot_escape_state_root_or_change_saved_provider_settings(self):
        factory = self.factory()
        with self.assertRaises(ValueError):
            factory(self.folder / 'outside', '1234567890abcdef1234567890abcdef')
        factory(self.state / '1234567890abcdef1234567890abcdef', '1234567890abcdef1234567890abcdef')
        factory(self.state / '1234567890abcdef1234567890abcdef', '1234567890abcdef1234567890abcdef')
        path = self.state / '1234567890abcdef1234567890abcdef/private/token-factory.json'
        data = json.loads(path.read_text())
        data['max_output_tokens'] = 4096
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            factory(self.state / '1234567890abcdef1234567890abcdef', '1234567890abcdef1234567890abcdef')

    def test_hosted_factory_wraps_provider_with_session_budget_before_transport(self):
        factory = self.factory()
        runtime = factory(self.state / '1234567890abcdef1234567890abcdef', '1234567890abcdef1234567890abcdef')
        class Job:
            def __init__(self): self.count = 0
            def reserve(self, config, amount): self.count += 1
        job = Job()
        provider = runtime.ai._factory(self.config, job, KEY)
        provider.ledger.reserve(self.config, .15)
        with self.assertRaises(ProviderError):
            provider.ledger.reserve(self.config, .1)
        self.assertEqual(job.count, 1)
        with self.assertRaises(ProviderError):
            runtime.ai._factory(self.config, job, KEY + 'other')

    def test_operator_file_reads_are_bounded_and_do_not_echo_values(self):
        p = self.folder / 'secret'
        p.write_text(KEY)
        self.assertEqual(read_private_file(p).decode(), KEY)
        with self.assertRaises(ValueError) as caught:
            read_private_file(p, 1)
        self.assertNotIn(KEY, str(caught.exception))
        with self.assertRaises(ValueError):
            read_private_file(self.folder / 'missing')

    def test_cli_defaults_off_and_requires_explicit_ledger_handoff_for_live(self):
        code = self.folder / 'invitation'
        code.write_text('synthetic-hosted-invitation-code-32-characters')
        configure = runpy.run_path(str(ROOT / 'tools/serve_hosted.py'))['configured_server']
        env = {'SIXD_STATE_ROOT': str(self.state), 'SIXD_PUBLIC_ORIGIN': 'https://review.example.com',
               'SIXD_JUDGE_ACCESS_CODE_FILE': str(code)}
        config, factory, host, port = configure(env)
        self.assertIsNone(factory.config)
        self.assertEqual(host, '127.0.0.1')
        self.assertEqual(port, 8080)
        with self.assertRaises(ValueError) as caught:
            configure({**env, 'SIXD_LIVE_AI_ENABLED': '1', 'SIXD_NEBIUS_API_KEY_FILE': KEY})
        self.assertNotIn(KEY, str(caught.exception))


if __name__ == '__main__':
    unittest.main()
