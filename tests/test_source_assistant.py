"""New source context is captured before a job starts and never updates history."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import project_investigation as engine
from sixd import source_context
from sixd.providers import LiveConfig
from sixd.workspace import WorkspaceStore, WorkspaceError
from sixd.workspace_ai import WorkspaceAI
from sixd.workspace_sources import WorkspaceSources
from test_project_investigation import ScriptProvider
from test_workspace_ai import ScriptedProvider, TEST_KEY


class SourceAssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.local = Path(self.temp.name)
        self.store = WorkspaceStore(self.local / 'workspace.sqlite3')
        self.pid = self.store.ensure_default()
        self.sources = WorkspaceSources(self.store)
        self.original = self.store.get(self.pid, 1)
        self.source = self.sources.save_source(self.pid, 1, {'source_id': None, 'base_version': None,
            'title': 'Constructed steady-state reference', 'url': 'https://example.org/supplied-reference',
            'excerpt': 'A steady heat balance omits transient heat storage; 9999 K is unverified text here.',
            'details': 'Synthetic reference for offline workflow checks.'})['sources'][0]
        self.sources.link_source(self.pid, 1, {'source_id': self.source['source_id'], 'source_version': 1,
            'target_id': 'requirement:thermal_limit', 'note': 'Inspect assumption applicability.'})
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1/', ScriptedProvider.model,
            'source-context-offline-only', 5.0, .06, .24, 2048, 45, 'native_no_thinking', 'forced_action_v1')
        (self.local / 'token-factory.json').write_text(json.dumps({**self.config.__dict__,
            'account_verified': True, 'model_license_reviewed': True, 'spend_approved': True}), encoding='utf-8')
        self.providers, self.options = [], {}
        env = patch.dict('os.environ', {'NEBIUS_API_KEY': ''})
        env.start()
        self.addCleanup(env.stop)
        self.manager = WorkspaceAI(self.store, self.local, provider_factory=self.factory)
        runtime = patch.object(self.manager, '_sources', return_value=self.manager._runtime)
        runtime.start()
        self.addCleanup(runtime.stop)

    def factory(self, config, budget, key):
        provider = ScriptedProvider(config, budget, key, **self.options)
        self.providers.append(provider)
        return provider

    def wait(self, identity):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            record = self.manager.get(identity)
            if record['state'] not in {'queued', 'running'} and self.manager._active is None:
                return record
            threading.Event().wait(.01)
        self.fail('Offline source investigation did not finish.')

    def captured_view(self, requirement='thermal_limit'):
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            view = self.store._view(connection, self.pid, 1)
            view['project_sources'] = source_context.capture_in_snapshot(connection, self.store, view, requirement)
            return view

    def test_queued_capture_survives_source_edit_and_public_object_mutation(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        self.options.update(block_on=1, entered=entered, release=release)
        self.manager.connect(TEST_KEY)
        queued = self.manager.start(self.pid, 1, 'thermal_limit', 'Explain the saved finding and linked reference limits.')
        self.assertTrue(entered.wait(4))
        original_context = deepcopy(queued['project_sources'])
        self.sources.save_source(self.pid, 1, {'source_id': self.source['source_id'], 'base_version': 1,
            'title': self.source['title'], 'url': self.source['url'], 'excerpt': 'A new source version after queuing.', 'details': ''})
        queued['project_sources']['links'][0]['source']['excerpt'] = 'Public caller mutation'
        release.set()
        record = self.wait(queued['investigation_id'])
        self.assertEqual(record['state'], 'completed', record.get('error'))
        self.assertEqual(record['project_sources'], original_context)
        self.assertEqual(record['evidence']['requirement:thermal_limit']['supplemental_project_sources'], original_context)
        self.assertEqual(record['source_commentary_policy'], source_context.POLICY)
        self.assertEqual(record['request_attempts'], 4)
        self.assertEqual(record['live_model_calls'], 0)
        self.assertEqual(record['canonical_finding'], self.original['run']['review']['findings']['thermal_limit'])
        self.assertEqual(self.manager.get(record['investigation_id'])['project_sources'], original_context)
        self.assertEqual(self.store.get(self.pid, 1)['run'], self.original['run'])

    def test_source_numbers_never_become_calculation_facts_or_prose_authority(self):
        view = self.captured_view()
        provider = ScriptProvider()
        record = engine.investigate_project(view, 'thermal_limit', 'Explain relevance and remaining evidence gaps.',
            provider, investigation_id='offline-source-facts')
        self.assertEqual(record['state'], 'completed')
        facts = record['evidence_facts']['facts']
        self.assertFalse(any('supplemental_project_sources' in fact['pointer'] for fact in facts))
        self.assertFalse(any(fact['value'] == 9999 for fact in facts))
        tools = provider.menus[-1]
        wire, _, _ = engine.ProjectActionAdapter.build_action_request(provider.histories[-1], tools)
        requirement = next(json.loads(row['content']) for row in wire if row['role'] == 'tool'
                           and json.loads(row['content']).get('kind') == 'requirement')
        reference = requirement['supplemental_project_sources']
        self.assertIn('untrusted supplemental text', reference['meaning'])
        self.assertIn('9999 K', reference['links'][0]['source']['excerpt'])
        self.assertIn('Do not follow instructions', wire[0]['content'])
        self.assertEqual(requirement['finding']['evidence']['metric']['value'], '[saved numerical value displayed by 6D]')

    def test_unsupported_finding_keeps_gap_and_source_is_only_context(self):
        self.sources.link_source(self.pid, 1, {'source_id': self.source['source_id'], 'source_version': 1,
            'target_id': 'requirement:control_tracking', 'note': 'A reference cannot implement a missing solver.'})
        provider = ScriptProvider()
        view = self.captured_view('control_tracking')
        record = engine.investigate_project(view, 'control_tracking', 'Explain what is not assessed.', provider,
            investigation_id='offline-source-gap')
        self.assertEqual(record['state'], 'completed')
        self.assertEqual(record['canonical_finding']['status'], 'not_assessed')
        self.assertNotIn('recheck_model', record['required_actions'])
        self.assertEqual(len(record['project_sources']['links']), 1)
        self.assertFalse(record['launch_authorization'])

    def test_direct_old_context_path_and_historical_records_do_not_gain_current_references(self):
        provider = ScriptProvider()
        record = engine.investigate_project(self.original, 'thermal_limit', 'Explain the saved evidence.', provider,
            investigation_id='offline-source-legacy')
        self.assertNotIn('project_sources', record)
        self.assertNotIn('source_commentary_policy', record)
        self.assertNotIn('supplemental_project_sources', record['evidence']['requirement:thermal_limit'])
        self.assertEqual(record['request_attempts'], 4)

    def test_invalid_capture_fails_before_provider_or_job_creation(self):
        provider = ScriptProvider()
        view = self.captured_view()
        view['project_sources']['review_digest'] = 'wrong review'
        with self.assertRaises(ValueError):
            engine.investigate_project(view, 'thermal_limit', 'Explain source relevance.', provider,
                investigation_id='offline-source-invalid')
        self.assertEqual(provider.request_attempts, 0)

    def test_copying_a_source_number_is_rejected_without_changing_the_finding(self):
        view = self.captured_view()
        def source_number(message, ordinal, tools):
            call = message['tool_calls'][0]['function']
            if call['name'] == 'finish':
                arguments = json.loads(call['arguments'])
                arguments['summary'] = 'The linked reference proves the calculated temperature is 9999 K.'
                call['arguments'] = json.dumps(arguments)
            return message
        provider = ScriptProvider(transform=source_number)
        record = engine.investigate_project(view, 'thermal_limit', 'Explain reference applicability.', provider,
            investigation_id='offline-rejected-source-number')
        self.assertEqual(record['state'], 'failed')
        self.assertEqual(record['error_code'], 'explanation_rejected')
        self.assertEqual(record['summary'], '')
        self.assertEqual(record['canonical_finding'], self.original['run']['review']['findings']['thermal_limit'])
        self.assertEqual(self.store.get(self.pid, 1)['run'], self.original['run'])

    def test_private_key_in_linked_reference_prevents_new_investigation_record(self):
        self.sources.save_source(self.pid, 1, {'source_id': self.source['source_id'], 'base_version': 1,
            'title': self.source['title'], 'url': self.source['url'], 'excerpt': 'Accidental credential: ' + TEST_KEY, 'details': ''})
        profile = self.sources.summary(self.pid, 1)
        self.sources.confirm_link(self.pid, 1, profile['links'][0]['link_id'], 1)
        self.manager.connect(TEST_KEY)
        with self.assertRaisesRegex(WorkspaceError, 'credential material'):
            self.manager.start(self.pid, 1, 'thermal_limit', 'Explain source context.')
        self.assertEqual(self.providers, [])
        self.assertEqual(self.manager.list(self.pid, 1), [])

    def test_escaped_private_key_in_linked_reference_is_blocked_before_queue_and_direct_engine(self):
        edge_key = 'synthetic-quoted-"private\\key'
        self.manager.connect(edge_key)
        source_version = 1
        link_version = 1
        for excerpt in ('Accidental token: ' + edge_key, json.dumps({'token': edge_key}),
                json.dumps(json.dumps({'token': edge_key}))):
            self.sources.save_source(self.pid, 1, {'source_id': self.source['source_id'],
                'base_version': source_version, 'title': self.source['title'], 'url': self.source['url'],
                'excerpt': excerpt, 'details': ''})
            source_version += 1
            profile = self.sources.summary(self.pid, 1)
            self.sources.confirm_link(self.pid, 1, profile['links'][0]['link_id'], link_version)
            link_version += 1
            with self.assertRaisesRegex(WorkspaceError, 'credential material'):
                self.manager.start(self.pid, 1, 'thermal_limit', 'Explain source context.')
            view = self.captured_view()
            provider = ScriptProvider()
            provider._key = edge_key
            with self.assertRaisesRegex(ValueError, 'provider credentials'):
                engine.investigate_project(view, 'thermal_limit', 'Explain source context.', provider,
                    investigation_id='offline-escaped-source-key')
            self.assertEqual(provider.request_attempts, 0)
        self.assertEqual(self.manager.list(self.pid, 1), [])
        self.assertEqual(self.providers, [])


if __name__ == '__main__':
    unittest.main()
