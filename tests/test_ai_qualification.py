"""Current live qualification contracts; all transports here are offline."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.ai_qualification import build_plan, validate_plan, run_plan, CAP_USD
from sixd.providers import LiveConfig, TokenFactoryProvider
from sixd.project_investigation import ProjectActionAdapter
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError
from sixd.workspace_ai import WorkspaceAI, _encode, _digest
from sixd.workspace_qualification import WorkspaceQualification, preflight
from test_workspace_ai_api import offline_transport, KEY


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1/', 'nvidia/nemotron-3-super-120b-a12b',
            'qualification-offline-test', 29.5, .3, .9, 2048, 45, 'native_no_thinking', 'forced_action_v1')
        self.config_path = self.folder / 'token-factory.json'
        self.config_path.write_text(json.dumps({**asdict(self.config), 'account_verified': True,
            'model_license_reviewed': True, 'spend_approved': True}), encoding='utf-8')
        self.store = WorkspaceStore(self.folder / 'workspace.sqlite3')
        self.pid = self.store.ensure_default()
        self.original = self.store.get(self.pid, 1)
        self.calls = []

        def factory(config, budget, key):
            def transport(request):
                self.calls.append(json.loads(request.data))
                return offline_transport(request)
            return TokenFactoryProvider(config, budget, api_key=key, transport=transport,
                action_adapter=ProjectActionAdapter())
        with patch.dict('os.environ', {'NEBIUS_API_KEY': ''}):
            self.ai = WorkspaceAI(self.store, self.folder, provider_factory=factory)
        self.stable = patch.object(self.ai, '_sources', return_value=self.ai._runtime)
        self.stable.start()
        self.addCleanup(self.stable.stop)
        self.service = WorkspaceQualification(self.ai)

    def wait(self, identity):
        until = time.monotonic() + 15
        while time.monotonic() < until:
            value = self.service.get(identity)
            if value['state'] not in ('queued', 'running') and self.ai._active is None:
                return value
            time.sleep(.02)
        self.fail('Offline qualification did not finish.')

    def test_pack_keeps_expected_oracles_outside_model_and_sources_untrusted(self):
        plan = build_plan(self.config, temporary_root=self.folder)
        self.assertEqual([c['expected']['status'] for c in plan['cases']], ['met', 'met', 'not_met', 'not_assessed'])
        source = plan['cases'][0]['view']['project_sources']
        self.assertEqual(len(source['links']), 1)
        changed = plan['cases'][2]['view']
        self.assertEqual(changed['project']['inputs']['maximum_temperature']['value'], 250)
        self.assertEqual(changed['run']['model_results']['thermal']['metrics'], changed['prior_run']['model_results']['thermal']['metrics'])
        self.assertEqual(self.store.get(self.pid, 1), self.original)
        self.assertFalse(self.calls)
        self.assertFalse((self.folder / 'budget.sqlite3').exists())

    def test_plan_tampering_or_unknown_model_stops_before_provider(self):
        plan = build_plan(self.config, temporary_root=self.folder)
        plan['cases'][0]['expected']['status'] = 'not_met'
        with self.assertRaises(ValueError):
            validate_plan(plan)
        with self.assertRaises(ValueError):
            build_plan(type('Config', (), {'model': 'unknown'})(), temporary_root=self.folder)
        self.assertFalse(self.calls)

    def test_preflight_exercises_real_protocol_without_private_session_or_budget(self):
        plan = build_plan(self.config, temporary_root=self.folder)
        value = preflight(plan, self.config)
        self.assertTrue(value['fits'])
        self.assertLess(value['forecast_with_headroom_usd'], CAP_USD)
        self.assertEqual(len(value['cases']), 4)
        self.assertEqual(value['live_calls'], 0)
        self.assertFalse(self.calls)
        self.assertFalse((self.folder / 'budget.sqlite3').exists())

    def test_invalid_consent_and_missing_key_never_create_job_or_budget(self):
        for amount, allow in [(True, True), (.8, False), (.81, True), (float('nan'), True)]:
            with self.assertRaises(WorkspaceError):
                self.service.start(allowance_usd=amount, allow_spend=allow)
        with self.assertRaises(ConflictError):
            self.service.start(allowance_usd=.8, allow_spend=True)
        self.assertIsNone(self.service.status()['latest'])
        self.assertFalse(self.calls)
        self.assertFalse((self.folder / 'budget.sqlite3').exists())

    def test_full_offline_receipts_do_not_change_project_or_selection(self):
        self.ai.connect(KEY)
        value = self.wait(self.service.start(allowance_usd=.8, allow_spend=True)['qualification_id'])
        self.assertEqual(value['state'], 'completed', value.get('error'))
        self.assertEqual(len(value['report']['rows']), 4)
        self.assertEqual(value['report']['mode'], 'offline_harness_validation')
        self.assertEqual(value['report']['live_calls'], 0)
        self.assertLessEqual(value['request_reservations'], 24)
        self.assertLessEqual(value['reserved_usd'], .8)
        self.assertTrue(all(r['score']['workflow_gate_pass'] for r in value['report']['rows']))
        self.assertTrue(self.service.status()['current_sources_match'])
        self.assertEqual(self.store.get(self.pid, 1), self.original)
        self.assertFalse((self.folder / 'project-assistant-model.json').exists())
        self.assertNotIn(KEY, json.dumps(value))
        for request in self.calls:
            wire = json.dumps(request)
            self.assertNotIn('reference_metric', wire)
            self.assertNotIn('evaluation_policy', wire)
        record = value['report']['rows'][0]['receipt']
        self.assertEqual(record['project_sources'], value['plan']['cases'][0]['view']['project_sources'])
        self.assertFalse(any(f['value'] == 9999 for f in record['evidence_facts']['facts']))

    def test_failed_first_case_stops_remaining_as_untested(self):
        plan = build_plan(self.config, temporary_root=self.folder)
        def factory(candidate, case):
            def bad(request):
                response = offline_transport(request)
                tool = response['choices'][0]['message']['tool_calls'][0]['function']
                args = json.loads(tool['arguments'])
                if args['action'] == 'finish':
                    args['summary'] = 'All subsystems are certified and cleared for launch.'
                    tool['arguments'] = json.dumps(args)
                return response
            class Ledger:
                count = 0
                reserved = 0
                def reserve(self, *args): pass
            return TokenFactoryProvider(self.config, Ledger(), api_key=KEY, transport=bad,
                action_adapter=ProjectActionAdapter())
        report = run_plan(plan, factory)
        self.assertEqual(report['rows'][0]['state'], 'failed')
        self.assertEqual([r['state'] for r in report['rows'][1:]], ['not_run'] * 3)
        self.assertFalse(report['active_model_changed'])

    def test_restart_and_tampering_keep_failure_evidence(self):
        record = {'schema': 'sixd.ai-qualification.v1', 'qualification_id': 'a' * 32,
            'state': 'running', 'created_at': '2026-10-24T00:00:00+00:00', 'completed_at': None,
            'rows': [], 'report': None, 'reserved_usd': .01, 'request_reservations': 1}
        with self.ai._db() as db:
            db.execute('INSERT INTO ai_qualifications VALUES (?,?,?,?,?,?)',
                ('a' * 32, record['created_at'], 'running', 'old-owner', _encode(record), _digest(record)))
        service = WorkspaceQualification(self.ai)
        self.assertEqual(service.get('a' * 32)['state'], 'interrupted')
        self.assertEqual(service.get('a' * 32)['reserved_usd'], .01)
        with self.ai._db() as db:
            db.execute("UPDATE ai_qualifications SET digest='bad'")
        with self.assertRaises(WorkspaceError):
            service.get('a' * 32)
        self.assertFalse(self.calls)


if __name__ == '__main__':
    unittest.main()
