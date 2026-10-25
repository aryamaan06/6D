"""Per-request model routing against isolated, explicitly offline evidence."""
from dataclasses import asdict, replace
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_workspace_ai_api import offline_factory, offline_transport
from sixd.model_choices import POLICY, catalog, explicit_config, permitted_variant
from sixd.project_investigation import ProjectActionAdapter
from sixd.providers import BudgetLedger, LiveConfig, ProviderError, TokenFactoryProvider
from sixd.workspace import ConflictError, WorkspaceStore
from sixd.workspace_ai import WorkspaceAI
from sixd.workspace_server import create_server

KEY = 'synthetic-three-choice-key-no-network'


class WorkspaceModelChoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1/',
            'nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B', 'same-three-model-approval',
            29.5, .06, .24, 2048, 45, 'native_no_thinking', 'forced_action_v1')
        self.path = self.folder / 'token-factory.json'
        self.path.write_text(json.dumps({**asdict(self.config), 'account_verified': True,
            'model_license_reviewed': True, 'spend_approved': True}), encoding='utf-8')
        self.original_config = self.path.read_bytes()
        BudgetLedger(self.folder / 'budget.sqlite3').reserve(self.config, .25)
        self.store = WorkspaceStore(self.folder / 'workspace.sqlite3')
        self.project = self.store.ensure_default()
        self.providers = []
        def factory(config, ledger, key):
            self.providers.append((config, ledger.max_reservation_usd, key))
            return offline_factory(config, ledger, key)
        with patch.dict('os.environ', {'NEBIUS_API_KEY': ''}):
            self.ai = WorkspaceAI(self.store, self.folder, provider_factory=factory)
        self.guard = patch.object(self.ai, '_sources', return_value=self.ai._runtime)
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.ai.connect(KEY)
        self.original_view = self.store.get(self.project, 1)

    def wait(self, job):
        deadline = time.monotonic() + 15
        while self.ai._active and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertIsNone(self.ai._active)
        return self.ai.get(job['investigation_id'])

    def start(self, choice):
        return self.ai.start(self.project, 1, 'thermal_limit',
            'Explain this saved finding and useful next checks.', model_choice=choice)

    def test_each_choice_reaches_exact_model_without_resetting_allowance_or_rewriting_history(self):
        previous, records = .25, []
        for item in catalog():
            with self.subTest(choice=item['id']):
                record = self.wait(self.start(item['id']))
                self.assertEqual(record['state'], 'completed', record.get('error'))
                self.assertEqual(record['model'], item['model'])
                self.assertEqual(record['model_choice'], item['id'])
                self.assertEqual(record['model_selection_policy'], POLICY)
                self.assertTrue(record['model_selection_explicit'])
                self.assertEqual(record['max_job_reservation_usd'], item['max_job_reservation_usd'])
                config, ceiling, key = self.providers[-1]
                self.assertEqual(config.model, item['model'])
                self.assertEqual(ceiling, item['max_job_reservation_usd'])
                self.assertEqual(config.approval_id, self.config.approval_id)
                self.assertEqual(config.spend_cap_usd, 29.5)
                self.assertEqual(key, KEY)
                balance = self.ai._budget(config)
                self.assertGreater(balance['reserved_usd'], previous)
                self.assertEqual(balance['cap_usd'], 29.5)
                previous = balance['reserved_usd']
                records.append(record)
        self.assertEqual(self.path.read_bytes(), self.original_config)
        self.assertFalse((self.folder / 'project-assistant-model.json').exists())
        self.assertEqual(self.store.get(self.project, 1), self.original_view)
        for record in records:
            self.assertEqual(self.ai.get(record['investigation_id']), record)

    def test_status_lists_choices_without_requests_or_promoting_default(self):
        for _ in range(3):
            value = self.ai.status()
            self.assertEqual([c['id'] for c in value['available_models']], ['nano', 'super', 'ultra'])
            self.assertEqual(value['default_model_choice'], 'nano')
            self.assertFalse(value['automatic_model_selection'])
            self.assertTrue(all(not c['live_validated'] for c in value['available_models']))
        self.assertEqual(self.providers, [])
        self.assertEqual(self.ai._budget(self.config)['reserved_usd'], .25)

    def test_unknown_choice_rejected_before_job_or_reservation(self):
        for choice in ('gpt', 'ULTRA', 'nvidia/Nemotron-3-Ultra-550b-a55b', '', True, 3, {}):
            with self.subTest(choice=repr(choice)), self.assertRaises(ProviderError):
                self.start(choice)
        self.assertEqual(self.providers, [])
        self.assertEqual(self.ai.list(self.project, 1), [])
        self.assertEqual(self.ai._budget(self.config)['reserved_usd'], .25)

    def test_legacy_default_and_broken_proof_remain_fail_closed(self):
        record = self.wait(self.ai.start(self.project, 1, 'thermal_limit', 'Explain this evidence.'))
        self.assertEqual(record['model'], self.config.model)
        self.assertEqual(record['model_selection_policy'], 'legacy_default')
        self.assertFalse(record['model_selection_explicit'])
        (self.folder / 'project-assistant-model.json').write_text('{bad-json', encoding='utf-8')
        for choice in (None, 'nano', 'super', 'ultra'):
            with self.subTest(choice=choice), self.assertRaises(ProviderError):
                self.ai._config(choice)
        self.assertEqual(len(self.providers), 1)

    def test_variants_cannot_change_operator_budget_endpoint_protocol_or_other_settings(self):
        for option in catalog():
            variant = explicit_config(self.config, option['id'])
            self.assertTrue(permitted_variant(self.config, variant))
            for changes in ({'spend_cap_usd': 58}, {'approval_id': 'reset'},
                    {'base_url': 'https://api.tokenfactory.us-central1.nebius.com/v1/'},
                    {'max_output_tokens': 8192}, {'request_timeout_seconds': 60},
                    {'input_usd_per_million_ceiling': 0}, {'selection_protocol': 'native_tools_v1'}):
                with self.subTest(choice=option['id'], changes=changes):
                    self.assertFalse(permitted_variant(self.config, replace(variant, **changes)))

    def test_shared_job_lock_blocks_switching_models_during_active_request(self):
        entered, release = threading.Event(), threading.Event()
        def transport(request):
            entered.set()
            if not release.wait(10):
                raise AssertionError('Blocked offline fixture timed out')
            return offline_transport(request)
        self.ai._factory = lambda config, ledger, key: TokenFactoryProvider(config, ledger,
            api_key=key, transport=transport, action_adapter=ProjectActionAdapter())
        job = self.start('nano')
        try:
            self.assertTrue(entered.wait(5))
            self.assertTrue(self.ai.status()['investigation_active'])
            with self.assertRaises(ConflictError):
                self.start('ultra')
        finally:
            release.set()
            self.wait(job)
        self.assertFalse(self.ai.status()['investigation_active'])
        self.assertEqual(len(self.ai.list(self.project, 1)), 1)
        self.assertEqual(self.path.read_bytes(), self.original_config)

    def test_all_choices_preserve_project_scope_and_whole_project_guards(self):
        from test_whole_project_investigation import SUMMARY
        def transport(request):
            menu = json.loads(json.loads(request.data)['messages'][-1]['content'])
            action = menu['available_actions'][0]['action']
            args = {'action': action, 'evidence_ids': menu['recorded_evidence_ids'] if action == 'finish' else [],
                    'summary': SUMMARY if action == 'finish' else ''}
            return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': None,
                'tool_calls': [{'id': 'offline-whole-' + action, 'type': 'function', 'function': {
                    'name': 'select_next_action', 'arguments': json.dumps(args)}}]}}],
                'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}}
        self.ai._factory = lambda config, ledger, key: TokenFactoryProvider(config, ledger,
            api_key=key, transport=transport)
        for item in catalog():
            with self.subTest(choice=item['id']):
                record = self.wait(self.ai.start(self.project, 1, None,
                    'What needs review across this saved project?', scope='project', model_choice=item['id']))
                self.assertEqual(record['state'], 'completed', record.get('error'))
                self.assertEqual(record['scope'], 'project')
                self.assertEqual(record['model'], item['model'])
                self.assertEqual(record['model_choice'], item['id'])
                self.assertEqual(record['model_selection_policy'], POLICY)
                self.assertFalse(self.ai.status()['whole_project_live_validated'])
        self.assertEqual(self.store.get(self.project, 1), self.original_view)


class WorkspaceModelChoiceHTTPTests(unittest.TestCase):
    def test_model_choice_wire_validation_and_recording(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temporary:
            folder = Path(temporary)
            config = LiveConfig('https://api.tokenfactory.nebius.com/v1/',
                'nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B', 'three-model-http-approval',
                29.5, .06, .24, 2048, 45, 'native_no_thinking', 'forced_action_v1')
            (folder / 'token-factory.json').write_text(json.dumps({**asdict(config),
                'account_verified': True, 'model_license_reviewed': True, 'spend_approved': True}))
            server = create_server(port=0, db_path=folder / 'workspace.sqlite3',
                ai_local_directory=folder, provider_factory=offline_factory)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            def request(path, body=None):
                client = HTTPConnection('127.0.0.1', server.server_port, timeout=15)
                client.request('GET' if body is None else 'POST', path,
                    None if body is None else json.dumps(body), {'Content-Type': 'application/json'})
                response = client.getresponse()
                result = response.status, json.loads(response.read())
                client.close()
                return result
            try:
                project = server.store.ensure_default()
                with patch.object(server.ai, '_sources', return_value=server.ai._runtime):
                    self.assertEqual(request('/api/ai/connect', {'api_key': KEY})[0], 200)
                    status, value = request('/api/ai/status')
                    self.assertEqual(status, 200)
                    self.assertEqual([m['id'] for m in value['available_models']], ['nano', 'super', 'ultra'])
                    body = {'project_id': project, 'revision': 1, 'requirement_id': 'thermal_limit',
                            'question': 'Explain this saved finding.', 'model_choice': 'ultra'}
                    for invalid in (None, False, 'other', {'model': 'ultra'}):
                        self.assertEqual(request('/api/investigations', {**body, 'model_choice': invalid})[0], 400)
                    self.assertEqual(request('/api/investigations', {**body, 'spend_cap_usd': 58})[0], 400)
                    status, record = request('/api/investigations', body)
                    self.assertEqual(status, 200, record)
                    deadline = time.monotonic() + 15
                    while server.ai._active and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertIsNone(server.ai._active)
                    status, record = request('/api/investigations/' + record['investigation_id'])
                    self.assertEqual(status, 200)
                    self.assertEqual(record['state'], 'completed', record.get('error'))
                    self.assertEqual(record['model_choice'], 'ultra')
                    self.assertEqual(record['model'], catalog()[2]['model'])
                    self.assertNotIn(KEY, json.dumps(record))
            finally:
                deadline = time.monotonic() + 15
                while server.ai._active and time.monotonic() < deadline:
                    time.sleep(.01)
                server.shutdown(); server.server_close(); worker.join()


if __name__ == '__main__':
    unittest.main()
