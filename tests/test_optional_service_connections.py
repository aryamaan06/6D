"""Remembering a connection never searches, uploads or resets retained allowances."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.credential_store import CredentialError, MAX_FILE_BYTES
from sixd.project_examples import example_projects
from sixd.service_credentials import ServiceCredentialStore
from sixd.workspace import ConflictError, WorkspaceError, WorkspaceStore, _encode
from sixd.workspace_observability import ENDPOINTS, WorkspaceObservability
from sixd.workspace_research import WorkspaceResearch
from sixd.workspace_sources import WorkspaceSources
from test_service_credentials import FixtureProtection, UnsupportedProtection
from test_workspace_observability import QualificationFixture

TAVILY_KEY = 'synthetic-tavily-key-no-account-access'
LANGSMITH_KEY = 'synthetic-langsmith-key-no-account-access'
WORKSPACE_ID = '0c678cf0-6414-4356-bb55-188cf9725820'


class OptionalConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.local = Path(self.temp.name)
        self.store = WorkspaceStore(self.local / 'workspace.sqlite3')
        project = deepcopy(example_projects()['baseline'])
        self.store.create_project(project)
        self.project_id = project['project_id']
        self.sources = WorkspaceSources(self.store)
        self.ai = SimpleNamespace(store=self.store, _key='synthetic-nebius-session-key')
        self.qualification = QualificationFixture()
        self.calls = []
        self.codec = FixtureProtection()
        self.tavily_store = self.credential_store('tavily')
        self.langsmith_store = self.credential_store('langsmith')
        self.research = self.new_research()
        self.observability = self.new_observability()

    def credential_store(self, service, protection=None):
        return ServiceCredentialStore(self.local / 'credentials' / (service + '.dpapi'), service=service,
            protection=protection if protection is not None else self.codec)

    def new_research(self, **kwargs):
        return WorkspaceResearch(self.store, self.sources, transport=self.search_transport,
            credential_store=kwargs.pop('credential_store', self.tavily_store), **kwargs)

    def new_observability(self, **kwargs):
        return WorkspaceObservability(self.ai, self.qualification, transport=self.export_transport,
            credential_store=kwargs.pop('credential_store', self.langsmith_store), **kwargs)

    def search_transport(self, key, body):
        self.calls.append(('tavily', key, deepcopy(body)))
        return {'results': [], 'usage': {'credits': 1}}

    def export_transport(self, endpoint, headers, body):
        self.calls.append(('langsmith', endpoint, deepcopy(headers), deepcopy(body)))
        return {'status': 202}

    def search(self, service=None):
        service = service or self.research
        return service.search(self.project_id, 1, 'requirement:thermal_limit', 'deliberately entered query',
            self.sources.summary(self.project_id, 1)['digest'])

    def export(self, service=None, **kwargs):
        service = service or self.observability
        preview = service.preview(self.qualification.record['qualification_id'])
        return service.export(preview['qualification_id'], preview['preview_digest'], **kwargs)

    def test_initial_status_and_constructor_default_paths_are_workspace_isolated(self):
        for service in (self.research, self.observability):
            status = service.status()
            self.assertTrue(status['remember_supported'])
            self.assertFalse(status['key_present'])
            self.assertFalse(status['key_remembered'])
            self.assertIsNone(status['key_source'])
            self.assertIsNone(status['credential_error'])
            self.assertEqual(status['key_storage'], 'server_memory_only')
        plain_research = WorkspaceResearch(self.store, self.sources, self.search_transport)
        plain_observation = WorkspaceObservability(self.ai, self.qualification, transport=self.export_transport)
        self.assertEqual(plain_research._credential_store.path, self.local / 'credentials' / 'tavily.dpapi')
        self.assertEqual(plain_observation._credential_store.path, self.local / 'credentials' / 'langsmith.dpapi')
        other = self.local / 'explicit-local'
        plain_research = WorkspaceResearch(self.store, self.sources, local_directory=other)
        plain_observation = WorkspaceObservability(self.ai, self.qualification, local_directory=other)
        self.assertEqual(plain_research._credential_store.path, other / 'credentials' / 'tavily.dpapi')
        self.assertEqual(plain_observation._credential_store.path, other / 'credentials' / 'langsmith.dpapi')
        self.assertEqual(self.calls, [])
        self.assertFalse(other.exists())

    def test_connect_restore_forget_and_disconnect_are_offline_and_exclude_secrets(self):
        with patch('socket.create_connection', side_effect=AssertionError('No implicit provider connection')):
            self.research.connect(TAVILY_KEY, 8, remember=True)
            self.observability.connect(LANGSMITH_KEY, 'eu', WORKSPACE_ID, remember=True)
            research, observability = self.new_research(), self.new_observability()
            statuses = [research.status(), observability.status()]
            for status in statuses:
                self.assertTrue(status['key_present'])
                self.assertTrue(status['key_remembered'])
                self.assertEqual(status['key_source'], 'remembered')
                self.assertEqual(status['key_storage'], 'windows_current_user_dpapi')
                self.assertIsNone(status['credential_error'])
            self.assertEqual(statuses[0]['credit_limit'], 8)
            self.assertEqual(statuses[1]['region'], 'eu')
            self.assertEqual(statuses[1]['workspace_id'], WORKSPACE_ID)
            self.assertEqual(statuses[1]['endpoint'], ENDPOINTS['eu'])
            for service in (research, observability):
                status = service.forget_key()
                self.assertTrue(status['key_present'])
                self.assertFalse(status['key_remembered'])
                self.assertEqual(status['key_source'], 'session')
                self.assertEqual(status['key_storage'], 'server_memory_only')
                self.assertFalse(service.disconnect()['key_present'])
        self.assertEqual(self.calls, [])
        self.assertFalse(self.new_research().status()['key_present'])
        self.assertFalse(self.new_observability().status()['key_present'])
        encoded = _encode(statuses)
        for key in (TAVILY_KEY, LANGSMITH_KEY, self.ai._key):
            self.assertNotIn(key, encoded)

    def test_session_connection_removes_prior_remembered_copy_and_cannot_resurrect(self):
        for service, connect, store in (
                (self.research, lambda remember: self.research.connect(TAVILY_KEY, 4, remember), self.tavily_store),
                (self.observability, lambda remember: self.observability.connect(LANGSMITH_KEY, 'eu', WORKSPACE_ID, remember), self.langsmith_store)):
            connect(True)
            self.assertTrue(store.exists())
            status = connect(False)
            self.assertTrue(status['key_present'])
            self.assertEqual(status['key_source'], 'session')
            self.assertFalse(status['key_remembered'])
            self.assertFalse(store.exists())
        self.assertFalse(self.new_research().status()['key_present'])
        self.assertFalse(self.new_observability().status()['key_present'])
        self.assertEqual(self.calls, [])

    def test_tavily_restore_preserves_absolute_credit_limit_and_retained_reservations(self):
        self.research.connect(TAVILY_KEY, 2, remember=True)
        self.search()
        fresh = self.new_research()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(fresh.status()['reserved_credits'], 1)
        self.assertEqual(fresh.status()['remaining_credits'], 1)
        self.search(fresh)
        fresh.forget_key()
        fresh.connect(TAVILY_KEY, 2, remember=True)
        restarted = self.new_research()
        self.assertEqual(restarted.status()['credit_limit'], 2)
        self.assertEqual(restarted.status()['reserved_credits'], 2)
        self.assertFalse(restarted.status()['can_search'])
        for action in (lambda: self.search(restarted), lambda: restarted.connect(TAVILY_KEY, 1, True)):
            with self.assertRaises(WorkspaceError):
                action()
        self.assertEqual(len(self.calls), 2)

    def test_tavily_restore_below_retained_cap_fails_closed_without_changing_reservations(self):
        self.research.connect(TAVILY_KEY, 3)
        self.search()
        self.search()
        self.tavily_store.save(TAVILY_KEY, {'credit_limit': 1})
        fresh = self.new_research()
        status = fresh.status()
        self.assertFalse(status['key_present'])
        self.assertTrue(status['key_remembered'])
        self.assertEqual(status['credential_error'], 'credential_data_invalid')
        self.assertEqual(status['reserved_credits'], 2)
        self.assertIsNone(status['credit_limit'])
        self.assertEqual(fresh.connect(TAVILY_KEY, 2)['remaining_credits'], 0)
        self.assertFalse(self.tavily_store.exists())
        self.assertEqual(len(self.calls), 2)

    def test_remembered_tavily_restore_never_clears_provider_usage_review(self):
        self.research.connect(TAVILY_KEY, 5, True)
        self.research._transport = lambda *args: {'results': [], 'usage': {'credits': 2}}
        receipt = self.search()
        self.assertIsNotNone(receipt['usage_warning'])
        fresh = self.new_research()
        status = fresh.status()
        self.assertEqual(status['credit_limit'], 5)
        self.assertEqual(status['reserved_credits'], 1)
        self.assertTrue(status['usage_review_required'])
        self.assertFalse(status['can_search'])
        with self.assertRaises(WorkspaceError):
            self.search(fresh)
        self.assertEqual(self.calls, [])

    def test_langsmith_restore_keeps_endpoint_metadata_explicit_approval_and_one_attempt(self):
        self.observability.connect(LANGSMITH_KEY, 'eu', WORKSPACE_ID, True)
        fresh = self.new_observability()
        fresh.preview(self.qualification.record['qualification_id'])
        self.assertEqual(self.calls, [])
        with self.assertRaises(WorkspaceError):
            self.export(fresh, allow_upload=False)
        self.assertEqual(self.calls, [])
        receipt = self.export(fresh, allow_upload=True)
        self.assertEqual(receipt['state'], 'accepted_by_api')
        self.assertEqual(self.calls[0][1], ENDPOINTS['eu'])
        self.assertEqual(self.calls[0][2]['x-tenant-id'], WORKSPACE_ID)
        restarted = self.new_observability()
        self.assertEqual(restarted.status()['attempts'], 1)
        with self.assertRaises(ConflictError):
            self.export(restarted, allow_upload=True)
        restarted.disconnect()
        restarted.connect(LANGSMITH_KEY, 'eu', WORKSPACE_ID, True)
        with self.assertRaises(ConflictError):
            self.export(restarted, allow_upload=True)
        self.assertEqual(len(self.calls), 1)

    def test_failed_and_interrupted_attempts_never_retry_on_restore(self):
        self.research.connect(TAVILY_KEY, 3, True)
        self.observability.connect(LANGSMITH_KEY, remember=True)
        self.research._transport = lambda *args: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.search()
        self.observability._transport = lambda *args: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.export()
        fresh_research = self.new_research()
        fresh_observation = self.new_observability()
        self.assertEqual(fresh_research.status()['reserved_credits'], 1)
        self.assertEqual(fresh_observation.status()['attempts'], 1)
        self.assertEqual(fresh_observation.list()['exports'][0]['state'], 'interrupted')
        with self.assertRaises(ConflictError):
            self.export(fresh_observation)
        self.assertEqual(self.calls, [])

    def test_remember_and_forget_failure_preserve_prior_session_and_settings(self):
        self.research.connect(TAVILY_KEY, 6, True)
        self.observability.connect(LANGSMITH_KEY, 'eu', WORKSPACE_ID, True)
        for service, store, replace in ((self.research, self.tavily_store,
                lambda: self.research.connect(TAVILY_KEY + '-new', 9, True)),
                (self.observability, self.langsmith_store,
                lambda: self.observability.connect(LANGSMITH_KEY + '-new', 'us', None, True))):
            before = store.path.read_bytes()
            old_key = service._key
            with patch('sixd.service_credentials.os.replace', side_effect=PermissionError(old_key)):
                with self.assertRaises(WorkspaceError) as error:
                    replace()
            self.assertNotIn(old_key, str(error.exception))
            self.assertEqual(service._key, old_key)
            self.assertEqual(store.path.read_bytes(), before)
            self.assertTrue(service.status()['key_remembered'])
            with patch.object(store, 'forget', side_effect=CredentialError('credential_storage_unavailable')):
                for action in (service.forget_key, service.disconnect):
                    with self.assertRaises(WorkspaceError):
                        action()
                self.assertEqual(service._key, old_key)
            self.assertTrue(service.forget_key()['key_present'])
        self.assertEqual(self.research.status()['credit_limit'], 6)
        self.assertEqual(self.observability.status()['region'], 'eu')
        self.assertEqual(self.observability.status()['workspace_id'], WORKSPACE_ID)
        self.assertEqual(self.calls, [])

    def test_failed_session_only_switch_cannot_leave_new_session_with_old_saved_key(self):
        self.research.connect(TAVILY_KEY, 6, True)
        self.observability.connect(LANGSMITH_KEY, 'eu', WORKSPACE_ID, True)
        for service, store, replace in ((self.research, self.tavily_store,
                lambda: self.research.connect(TAVILY_KEY + '-new', 9)),
                (self.observability, self.langsmith_store,
                lambda: self.observability.connect(LANGSMITH_KEY + '-new', 'us'))):
            old_key = service._key
            with patch.object(store, 'forget', side_effect=CredentialError('credential_path_invalid')):
                with self.assertRaises(WorkspaceError):
                    replace()
            self.assertEqual(service._key, old_key)
            self.assertEqual(service.status()['key_source'], 'remembered')
            self.assertTrue(service.status()['key_remembered'])
            self.assertEqual(store.load()['key'], old_key)

    def test_corrupt_oversized_swapped_and_unsupported_copies_fail_closed_with_session_recovery(self):
        self.research.connect(TAVILY_KEY, 5, True)
        self.observability.connect(LANGSMITH_KEY, 'eu', WORKSPACE_ID, True)
        tavily_blob = self.tavily_store.path.read_bytes()
        langsmith_blob = self.langsmith_store.path.read_bytes()
        for blob in (b'corrupt ' + TAVILY_KEY.encode(), b'x' * (MAX_FILE_BYTES + 1), langsmith_blob):
            self.tavily_store.path.write_bytes(blob)
            fresh = self.new_research()
            self.assertFalse(fresh.status()['key_present'])
            self.assertIsNotNone(fresh.status()['credential_error'])
            self.assertNotIn(TAVILY_KEY, _encode(fresh.status()))
            self.assertTrue(fresh.connect(TAVILY_KEY, 5)['key_present'])
            self.assertFalse(self.tavily_store.exists())
        self.langsmith_store.path.write_bytes(tavily_blob)
        fresh = self.new_observability()
        self.assertFalse(fresh.status()['key_present'])
        self.assertEqual(fresh.status()['region'], 'us')
        self.assertIsNone(fresh.status()['workspace_id'])
        for name, constructor, connect in (
                ('tavily', self.new_research, lambda service, remember: service.connect(TAVILY_KEY, 5, remember)),
                ('langsmith', self.new_observability, lambda service, remember: service.connect(LANGSMITH_KEY, 'eu', WORKSPACE_ID, remember))):
            store = self.credential_store(name, UnsupportedProtection())
            store.path.write_bytes(tavily_blob if name == 'tavily' else langsmith_blob)
            fresh = constructor(credential_store=store)
            self.assertFalse(fresh.status()['remember_supported'])
            self.assertFalse(fresh.status()['key_present'])
            self.assertEqual(fresh.status()['credential_error'], 'credential_storage_unsupported')
            with self.assertRaises(WorkspaceError):
                connect(fresh, True)
            self.assertFalse(fresh.status()['key_present'])
            status = connect(fresh, False)
            self.assertTrue(status['key_present'])
            self.assertEqual(status['key_source'], 'session')
            self.assertIsNone(status['credential_error'])
            self.assertFalse(store.exists())
        self.assertEqual(self.calls, [])

    def test_remember_flag_and_invalid_metadata_are_rejected_before_storage_or_state_changes(self):
        for remember in (None, 0, 1, 'true', [], {}):
            for connect in (lambda: self.research.connect(TAVILY_KEY, 5, remember),
                    lambda: self.observability.connect(LANGSMITH_KEY, remember=remember)):
                with self.assertRaises(WorkspaceError):
                    connect()
        for settings in ({'region': 'other'}, {'workspace_id': 'invalid'}, {'workspace_id': 42}):
            with self.assertRaises(WorkspaceError):
                self.observability.connect(LANGSMITH_KEY, remember=True, **settings)
        self.assertFalse(self.tavily_store.exists())
        self.assertFalse(self.langsmith_store.exists())
        self.assertEqual(self.calls, [])

    def test_active_requests_reject_all_connection_and_remember_changes(self):
        self.research.connect(TAVILY_KEY, 5, True)
        self.observability.connect(LANGSMITH_KEY, 'eu', WORKSPACE_ID, True)
        cases = ((self.research, self.tavily_store, self.search,
            lambda: self.research.connect(TAVILY_KEY + '-new', 6, False), {'results': []}),
            (self.observability, self.langsmith_store, self.export,
            lambda: self.observability.connect(LANGSMITH_KEY + '-new', 'us'), {'status': 202}))
        for service, store, request, connect, response in cases:
            started, finish = threading.Event(), threading.Event()
            outcome = []
            def blocked(*args):
                started.set()
                self.assertTrue(finish.wait(5))
                return response
            service._transport = blocked
            worker = threading.Thread(target=lambda: outcome.append(request()))
            before = store.path.read_bytes()
            worker.start()
            try:
                self.assertTrue(started.wait(3))
                self.assertEqual(service.status()['active_requests'], 1)
                for action in (connect, service.forget_key, service.disconnect):
                    with self.assertRaises(ConflictError):
                        action()
                self.assertEqual(store.path.read_bytes(), before)
            finally:
                finish.set()
                worker.join(6)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(outcome), 1)
            self.assertEqual(service.status()['active_requests'], 0)
            self.assertTrue(service.forget_key()['key_present'])


if __name__ == '__main__':
    unittest.main()
