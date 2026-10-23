"""Coverage declarations cannot replace calculation findings through real HTTP."""
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import workspace, workspace_server
from sixd.project_examples import example_projects
from sixd.workspace_server import create_server


class WorkspaceCoverageAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.server = create_server(port=0, db_path=Path(self.temp.name) / 'workspace.sqlite3',
            provider_factory=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('Coverage cannot invoke AI')))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.project = deepcopy(example_projects()['baseline'])
        self.project['inputs']['maximum_temperature']['value'] = 250
        self.identity = self.project['project_id']
        self.server.store.create_project(self.project)
        self.initial = self.server.store.run(self.identity, 1)
        self.assertEqual(self.initial['run']['review']['findings']['thermal_limit']['status'], 'not_met')

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.temp.cleanup()

    def request(self, path, body=None, origin=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        conn.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), headers)
        response = conn.getresponse()
        code, raw = response.status, response.read()
        value = json.loads(raw) if 'application/json' in response.getheader('Content-Type', '') else raw
        conn.close()
        return code, value

    def query(self, revision=1, identity=None):
        return '?project_id=' + (identity or self.identity) + '&revision=' + str(revision)

    def profile(self, revision=1):
        code, value = self.request('/api/coverage' + self.query(revision))
        self.assertEqual(code, 200, value)
        return value

    def spec(self, **changes):
        result = {'check_id': None, 'base_version': None, 'title': 'Transient entry heat assessment',
                  'phase': 'Entry and descent', 'discipline': 'Thermal', 'requirement_id': None,
                  'applicability': 'required', 'applicability_note': 'Constructed review scope.',
                  'model_fit': 'unknown', 'fit_note': '',
                  'next_step': 'Supply an applicable transient model and time history.'}
        result.update(changes)
        return result

    def body(self, spec=None, revision=1, profile=None):
        profile = profile or self.profile(revision)
        return {'project_id': self.identity, 'revision': revision,
                'expected_digest': profile['digest'], 'spec': spec or self.spec()}

    def save(self, spec=None, revision=1):
        code, result = self.request('/api/coverage/save', self.body(spec, revision))
        self.assertEqual(code, 200, result)
        return result

    def declared(self, profile):
        return [row for row in profile['checks'] if row['origin'] == 'declared']

    def test_unmapped_requirements_and_new_missing_analysis_are_visible_without_calculating(self):
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('Coverage must not calculate')):
            profile = self.profile()
            self.assertEqual({r['requirement_id'] for r in profile['checks']},
                             {r['id'] for r in self.project['requirements']})
            self.assertTrue(all(row['origin'] == 'requirement' and row['model_fit'] == 'unknown'
                                for row in profile['checks']))
            self.assertEqual(profile['criterion_counts']['not_met'], 1)
            saved = self.save()
            check = self.declared(saved)[0]
            self.assertEqual(check['coverage_status'], 'missing_analysis')
            self.assertIsNone(check['criterion_status'])
            self.assertEqual(len(saved['checks']), len(self.project['requirements']) + 1)
            self.assertTrue(check['next_step'])
        self.assertEqual(self.server.store.get(self.identity, 1)['run'], self.initial['run'])

    def test_excluding_an_unmet_requirement_cannot_hide_its_numerical_result(self):
        saved = self.save(self.spec(requirement_id='thermal_limit', applicability='excluded',
            applicability_note='Constructed exclusion from this particular phase; still a recorded unmet criterion.'))
        check = self.declared(saved)[0]
        self.assertEqual(check['coverage_status'], 'excluded')
        self.assertEqual(check['criterion_status'], 'not_met')
        self.assertEqual(saved['criterion_counts']['not_met'], 1)
        self.assertEqual(self.server.store.get(self.identity, 1)['run'], self.initial['run'])

    def test_changed_dependencies_need_review_and_old_revision_refuses_writes(self):
        first = self.save(self.spec(requirement_id='thermal_limit', model_fit='declared_fit',
            fit_note='Supplied applicability declaration for the original steady condition.'))
        original_check = self.declared(first)[0]
        changed = deepcopy(self.project)
        changed['inputs']['heat_input']['value'] += 10
        self.server.store.save_revision(self.identity, 1, changed)
        current = self.profile(2)
        check = self.declared(current)[0]
        self.assertTrue(check['needs_review'])
        self.assertEqual(check['coverage_status'], 'needs_review')
        self.assertTrue(check['review_reasons'])
        self.assertIsNone(check['criterion_status'])
        old = self.profile(1)
        self.assertFalse(old['can_edit'])
        self.assertEqual(self.declared(old)[0]['digest'], original_check['digest'])
        code, error = self.request('/api/coverage/save', self.body(revision=1, profile=old))
        self.assertEqual(code, 409, error)

    def test_display_digest_and_record_version_protect_against_unseen_changes(self):
        original = self.profile()
        saved = self.save()
        body = self.body(profile=original)
        self.assertEqual(self.request('/api/coverage/save', body)[0], 409)
        for bad_digest in (None, '', 'wrong', 42):
            with self.subTest(digest=bad_digest):
                body['expected_digest'] = bad_digest
                self.assertEqual(self.request('/api/coverage/save', body)[0], 400)
        check = self.declared(saved)[0]
        edit = self.spec(check_id=check['check_id'], base_version=1, next_step='A different explicit next step.')
        self.save(edit)
        self.assertEqual(self.request('/api/coverage/save', self.body(edit))[0], 409)
        self.assertEqual(len(self.declared(self.profile())), 1)

    def test_unknown_adapter_remains_unsupported_after_a_fit_declaration(self):
        project = deepcopy(example_projects()['missing_evidence'])
        project['project_id'] = 'coverage-unsupported-case'
        self.server.store.create_project(project)
        self.server.store.run(project['project_id'], 1)
        query = self.query(identity=project['project_id'])
        code, before = self.request('/api/coverage' + query)
        self.assertEqual(code, 200, before)
        spec = self.spec(requirement_id='control_tracking', model_fit='declared_fit',
                         fit_note='A user claim cannot create a missing deterministic adapter.')
        body = {'project_id': project['project_id'], 'revision': 1, 'expected_digest': before['digest'], 'spec': spec}
        code, result = self.request('/api/coverage/save', body)
        self.assertEqual(code, 200, result)
        check = self.declared(result)[0]
        self.assertEqual(check['calculation_status'], 'unsupported')
        self.assertEqual(check['criterion_status'], 'not_assessed')
        self.assertNotEqual(check['coverage_status'], 'criterion_met')
        self.assertFalse(check['model']['supported'])

    def test_report_uses_one_snapshot_and_preserves_original_review(self):
        saved = self.save(self.spec(requirement_id='thermal_limit', model_fit='outside_assumptions',
            fit_note='The planned transient phase is outside this steady model.'))
        observed_connections = []
        source_summary = self.server.sources.summary_in_snapshot
        coverage_summary = self.server.coverage.summary_in_snapshot
        def sources(connection, view):
            observed_connections.append(id(connection))
            self.assertTrue(connection.in_transaction)
            return source_summary(connection, view)
        def coverage(connection, view):
            observed_connections.append(id(connection))
            self.assertTrue(connection.in_transaction)
            return coverage_summary(connection, view)
        with patch.object(self.server.sources, 'summary_in_snapshot', side_effect=sources), \
                patch.object(self.server.coverage, 'summary_in_snapshot', side_effect=coverage), \
                patch.object(workspace, 'evaluate_models', side_effect=AssertionError('Export must not calculate')):
            code, report = self.request('/api/engineering-review-export' + self.query())
        self.assertEqual(code, 200, report)
        self.assertGreaterEqual(len(observed_connections), 2)
        self.assertEqual(len(set(observed_connections)), 1)
        self.assertEqual(report['engineering_coverage']['digest'], saved['digest'])
        self.assertEqual(report['engineering_coverage']['run_id'], self.initial['run']['run_id'])
        self.assertEqual(report['workspace']['run']['review'], self.initial['run']['review'])
        self.assertFalse(report['launch_authorization'])
        self.assertEqual(report['live_model_calls'], 0)
        enclosing = report.pop('export_digest')
        self.assertEqual(enclosing, workspace._digest(report))

    def test_request_scope_origin_and_runtime_guards_prevent_changes(self):
        body = self.body()
        self.assertEqual(self.request('/api/coverage/save', body, origin='https://example.invalid')[0], 403)
        body['project'] = deepcopy(self.project)  # A draft must not be silently treated as the saved revision.
        self.assertEqual(self.request('/api/coverage/save', body)[0], 400)
        body.pop('project')
        body['spec']['requirement_id'] = 'requirement-not-in-this-project'
        code, error = self.request('/api/coverage/save', body)
        self.assertIn(code, (400, 409), error)
        with patch.object(workspace_server, '_code_fingerprint', return_value='runtime-has-changed'):
            self.assertEqual(self.request('/api/coverage' + self.query())[0], 409)
            self.assertEqual(self.request('/api/coverage/save', self.body(profile={'digest': 'a' * 64}))[0], 409)
        self.assertEqual(self.declared(self.profile()), [])

    def test_assets_and_saved_annotations_survive_store_reopen(self):
        saved = self.save()
        from sixd.workspace_coverage import WorkspaceCoverage
        reopened = WorkspaceCoverage(workspace.WorkspaceStore(self.server.store.db_path))
        self.assertEqual(reopened.summary(self.identity, 1)['digest'], saved['digest'])
        for path in ('/engineering-coverage.js', '/engineering-coverage.css'):
            code, content = self.request(path)
            self.assertEqual(code, 200)
            self.assertTrue(content)


if __name__ == '__main__':
    unittest.main()
