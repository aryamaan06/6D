"""Manual references remain separate from calculated engineering evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import workspace, workspace_sources
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError, _digest, _encode
from sixd.workspace_sources import WorkspaceSources


class WorkspaceSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.store = WorkspaceStore(Path(self.temp.name) / 'workspace.sqlite3')
        self.project = deepcopy(example_projects()['baseline'])
        self.identity = self.project['project_id']
        self.store.create_project(self.project)
        self.library = WorkspaceSources(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def source(self, title='A supplied reference', **overrides):
        value = {'source_id': None, 'base_version': None, 'title': title,
                 'url': 'https://example.org/engineering/reference?version=1',
                 'excerpt': 'A manually supplied supporting passage; relevance is unverified.',
                 'details': 'Constructed source record for an acceptance test.'}
        value.update(overrides)
        return value

    def add(self, revision=1):
        summary = self.library.save_source(self.identity, revision, self.source())
        return summary['sources'][-1]

    def link(self, source, target='requirement:thermal_limit', revision=1):
        return self.library.link_source(self.identity, revision,
            {'source_id': source['source_id'], 'source_version': source['version'],
             'target_id': target, 'note': 'Supplied support for this exact context.'})

    def revise(self, **inputs):
        project = deepcopy(self.store.get(self.identity)['project'])
        base = int(project['revision'])
        for identity, value in inputs.items():
            project['inputs'][identity]['value'] = value
        self.store.save_revision(self.identity, base, project)
        return base + 1

    def canonical(self):
        with self.store._connect() as connection:
            return {table: [tuple(row) for row in connection.execute('SELECT * FROM '+table+' ORDER BY rowid')]
                    for table in ('projects', 'revisions', 'runs')}

    def test_empty_summary_has_targets_and_stable_digest_without_creating_evidence(self):
        before = self.canonical()
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('No calculations')):
            first = self.library.summary(self.identity, 1)
            second = self.library.summary(self.identity, 1)
        self.assertEqual(first, second)
        self.assertEqual(first['project_digest'], _digest(self.project))
        self.assertEqual(first['sources'], [])
        self.assertEqual(first['links'], [])
        self.assertIsNone(first['run_id'])
        kinds = {item['kind'] for item in first['targets']}
        self.assertEqual(kinds, {'requirement', 'model_assumption'})
        self.assertEqual(before, self.canonical())

    def test_source_and_link_are_supplemental_and_save_exact_escaped_text(self):
        original = self.store.run(self.identity, 1)
        before = self.canonical()
        source = self.library.save_source(self.identity, 1, self.source(title='<script>alert(1)</script>'))['sources'][0]
        with patch.object(workspace, 'evaluate_model', side_effect=AssertionError('No adapter recheck')):
            summary = self.link(source)
        self.assertEqual(summary['sources'][0]['title'], '<script>alert(1)</script>')
        link = summary['links'][0]
        self.assertEqual(link['status'], 'linked')
        self.assertEqual(link['source']['version'], 1)
        self.assertEqual(link['source']['digest'], link['source_digest'])
        self.assertEqual(before, self.canonical())
        self.assertEqual(self.store.get(self.identity)['run']['run_id'], original['run']['run_id'])

    def test_source_edits_append_and_pin_original_source_until_explicit_review(self):
        source = self.add()
        linked = self.link(source)['links'][0]
        updated = self.library.save_source(self.identity, 1, self.source(
            title='Revised supplied reference', source_id=source['source_id'], base_version=1))
        self.assertEqual(updated['sources'][0]['version'], 2)
        self.assertEqual(len(updated['sources'][0]['history']), 2)
        self.assertEqual(updated['links'][0]['source']['title'], source['title'])
        self.assertEqual(updated['links'][0]['status'], 'needs_review')
        reviewed = self.library.confirm_link(self.identity, 1, linked['link_id'], 1)
        self.assertEqual(reviewed['links'][0]['source_version'], 2)
        self.assertEqual(reviewed['links'][0]['status'], 'linked')
        self.assertEqual([item['source_version'] for item in reviewed['links'][0]['history']], [1, 2])

    def test_stale_source_and_link_edits_conflict_without_overwrite(self):
        source = self.add()
        linked = self.link(source)['links'][0]
        self.library.save_source(self.identity, 1, self.source(source_id=source['source_id'], base_version=1))
        with self.assertRaises(ConflictError):
            self.library.save_source(self.identity, 1, self.source(source_id=source['source_id'], base_version=1))
        self.library.confirm_link(self.identity, 1, linked['link_id'], 1)
        with self.assertRaises(ConflictError):
            self.library.confirm_link(self.identity, 1, linked['link_id'], 1)
        self.assertEqual(self.library.summary(self.identity, 1)['links'][0]['version'], 2)

    def test_duplicate_link_and_invented_targets_are_refused(self):
        source = self.add()
        self.link(source)
        with self.assertRaises(ConflictError):
            self.link(source)
        for target in ('finding:thermal_limit', 'requirement:nonexistent', 'assumption:thermal:999'):
            with self.subTest(target=target), self.assertRaises(ConflictError):
                self.link(source, target)

    def test_requirement_limit_change_flags_link_and_retains_its_basis(self):
        source = self.add()
        link = self.link(source)['links'][0]
        self.revise(maximum_temperature=250)
        summary = self.library.summary(self.identity, 2)
        self.assertEqual(summary['links'][0]['status'], 'needs_review')
        self.assertEqual(summary['links'][0]['context']['criterion_input']['value'], 320)
        reviewed = self.library.confirm_link(self.identity, 2, link['link_id'], 1)
        self.assertEqual(reviewed['links'][0]['context']['criterion_input']['value'], 250)
        self.assertEqual(reviewed['links'][0]['basis_revision'], 2)
        self.assertEqual(reviewed['links'][0]['history'][0]['basis_revision'], 1)
        self.assertEqual(self.library.summary(self.identity, 1)['links'][0]['version'], 1)

    def test_unrelated_changed_input_does_not_flag_thermal_reference(self):
        source = self.add()
        self.link(source)
        self.revise(delta_v=900)
        self.assertEqual(self.library.summary(self.identity, 2)['links'][0]['status'], 'linked')

    def test_chained_upstream_change_flags_the_downstream_reference(self):
        project = deepcopy(example_projects()['chain_review'])
        self.store.create_project(project)
        identity = project['project_id']
        source = self.library.save_source(identity, 1, self.source())['sources'][0]
        first = self.library.link_source(identity, 1, {'source_id': source['source_id'], 'source_version': 1,
            'target_id': 'requirement:mount_stress', 'note': 'Supplied chain load-case rationale.'})
        context = first['links'][0]['context']['model']
        self.assertIn('aero', context['calculation_dependencies']['models'])
        project['inputs']['density']['value'] = .8
        self.store.save_revision(identity, 1, project)
        self.assertEqual(self.library.summary(identity, 2)['links'][0]['status'], 'needs_review')

    def test_verifier_context_change_flags_link_without_running_a_model(self):
        source = self.add()
        self.link(source)
        changed = dict(workspace._sources(), **{'engineering.py': '0' * 64})
        with patch.object(workspace, '_sources', return_value=changed), patch.object(workspace, 'evaluate_model', side_effect=AssertionError('No recheck')):
            self.assertEqual(self.library.summary(self.identity, 1)['links'][0]['status'], 'needs_review')

    def test_assumption_link_uses_exact_maintained_text_and_bound_dependencies(self):
        source = self.add()
        before = self.link(source, 'assumption:thermal:0')['links'][0]
        self.assertIn('isothermal', before['context']['assumption'])
        self.revise(heat_input=400)
        self.assertEqual(self.library.summary(self.identity, 2)['links'][0]['status'], 'needs_review')

    def test_removed_requirement_keeps_reference_but_marks_target_unavailable(self):
        source = self.add()
        self.link(source)
        project = deepcopy(self.project)
        project['requirements'] = [item for item in project['requirements'] if item['id'] != 'thermal_limit']
        self.store.save_revision(self.identity, 1, project)
        summary = self.library.summary(self.identity, 2)
        self.assertEqual(summary['links'][0]['status'], 'target_unavailable')
        with self.assertRaises(ConflictError):
            self.library.confirm_link(self.identity, 2, summary['links'][0]['link_id'], 1)

    def test_finding_link_pins_run_and_new_run_needs_explicit_context_review(self):
        first = self.store.run(self.identity, 1)
        source = self.add()
        link = self.link(source, 'finding:thermal_limit')['links'][0]
        self.assertEqual(link['target']['run_id'], first['run']['run_id'])
        second = self.store.run(self.identity, 1)
        self.assertNotEqual(first['run']['run_id'], second['run']['run_id'])
        changed = self.library.summary(self.identity, 1)['links'][0]
        self.assertEqual(changed['status'], 'needs_review')
        self.assertEqual(changed['target']['run_id'], first['run']['run_id'])
        confirmed = self.library.confirm_link(self.identity, 1, link['link_id'], 1)['links'][0]
        self.assertEqual(confirmed['target']['run_id'], second['run']['run_id'])
        self.assertEqual(confirmed['history'][0]['target']['run_id'], first['run']['run_id'])

    def test_confirmation_refuses_a_source_version_not_seen_in_reviewed_profile(self):
        source = self.add()
        original_link = self.link(source)['links'][0]
        reviewed = self.library.save_source(self.identity, 1, self.source(
            title='Reviewed version two', source_id=source['source_id'], base_version=1))
        self.library.save_source(self.identity, 1, self.source(
            title='Unseen version three', source_id=source['source_id'], base_version=2))
        with self.assertRaises(ConflictError):
            self.library.confirm_link(self.identity, 1, original_link['link_id'], 1,
                                      expected_digest=reviewed['digest'])
        current = self.library.summary(self.identity, 1)
        self.assertEqual(current['links'][0]['source_version'], 1)
        self.assertEqual(current['links'][0]['version'], 1)
        confirmed = self.library.confirm_link(self.identity, 1, original_link['link_id'], 1,
                                             expected_digest=current['digest'])
        self.assertEqual(confirmed['links'][0]['source_version'], 3)

    def test_new_finding_link_refuses_a_rerun_not_seen_in_displayed_profile(self):
        first = self.store.run(self.identity, 1)
        source = self.add()
        displayed = self.library.summary(self.identity, 1)
        second = self.store.run(self.identity, 1)
        spec = {'source_id': source['source_id'], 'source_version': 1,
                'target_id': 'finding:thermal_limit', 'note': 'Reviewed current finding.'}
        with self.assertRaises(ConflictError):
            self.library.link_source(self.identity, 1, spec, expected_digest=displayed['digest'])
        current = self.library.summary(self.identity, 1)
        self.assertEqual(current['links'], [])
        linked = self.library.link_source(self.identity, 1, spec, expected_digest=current['digest'])
        self.assertNotEqual(first['run']['run_id'], second['run']['run_id'])
        self.assertEqual(linked['links'][0]['target']['run_id'], second['run']['run_id'])

    def test_supplied_profile_digest_must_be_explicit_sha256_text(self):
        source = self.add()
        spec = {'source_id': source['source_id'], 'source_version': 1,
                'target_id': 'requirement:thermal_limit', 'note': ''}
        for digest in ('', '0' * 63, 'A' * 64, 42, True):
            with self.subTest(digest=digest), self.assertRaises(WorkspaceError):
                self.library.link_source(self.identity, 1, spec, expected_digest=digest)

    def test_historical_summary_hides_future_sources_and_edits_are_latest_only(self):
        source = self.add()
        self.revise(heat_input=400)
        self.library.save_source(self.identity, 2, self.source(source_id=source['source_id'], base_version=1, title='R2 source'))
        self.library.save_source(self.identity, 2, self.source(title='Entirely new in R2'))
        history = self.library.summary(self.identity, 1)
        self.assertEqual(len(history['sources']), 1)
        self.assertEqual(history['sources'][0]['version'], 1)
        self.assertEqual(len(self.library.summary(self.identity, 2)['sources']), 2)
        with self.assertRaises(ConflictError):
            self.library.save_source(self.identity, 1, self.source())
        with self.assertRaises(ConflictError):
            self.link(source, revision=1)

    def test_newer_source_version_cannot_be_linked_using_stale_selection(self):
        source = self.add()
        self.library.save_source(self.identity, 1, self.source(source_id=source['source_id'], base_version=1))
        with self.assertRaises(ConflictError):
            self.link(source)

    def test_url_and_field_validation_refuses_active_and_ambiguous_links(self):
        invalid = ['javascript:alert(1)', 'file:///C:/secret', 'https://name:password@example.org',
                   'https://example.org/with space', 'https://example.org\\evil', 'https://',
                   'https://example.org:99999', '//example.org/path', 'https://<script>.example.org']
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(WorkspaceError):
                self.library.save_source(self.identity, 1, self.source(url=url))
        for field, value in [('title', ''), ('excerpt', ''), ('details', 'x' * 4001), ('title', '\x00')]:
            with self.subTest(field=field), self.assertRaises(WorkspaceError):
                self.library.save_source(self.identity, 1, self.source(**{field: value}))

    def test_source_id_is_project_scoped_and_arbitrary_versions_are_refused(self):
        source = self.add()
        other = deepcopy(self.project)
        other['project_id'] = 'separate-project'
        self.store.create_project(other)
        with self.assertRaises(ConflictError):
            self.library.link_source(other['project_id'], 1, {'source_id': source['source_id'],
                'source_version': 1, 'target_id': 'requirement:thermal_limit', 'note': ''})
        with self.assertRaises(WorkspaceError):
            self.library.save_source(self.identity, 1, self.source(base_version=1))
        with self.assertRaises(WorkspaceError):
            self.library.confirm_link(self.identity, 1, 'invented', True)

    def test_stored_digest_and_cross_binding_inconsistency_are_controlled(self):
        source = self.add()
        self.link(source)
        with self.store._connect(write=True) as connection:
            row = connection.execute('SELECT * FROM project_source_link_versions').fetchone()
            payload = __import__('json').loads(row['snapshot'])
            payload['source_digest'] = '0' * 64
            connection.execute('UPDATE project_source_link_versions SET snapshot=?,digest=?', (_encode(payload), _digest(payload)))
        with self.assertRaises(WorkspaceError):
            self.library.summary(self.identity, 1)

    def test_limits_do_not_drop_or_replace_records(self):
        self.add()
        with patch.object(workspace_sources, 'MAX_SOURCES', 1), self.assertRaises(WorkspaceError):
            self.add()
        self.assertEqual(len(self.library.summary(self.identity, 1)['sources']), 1)


if __name__ == '__main__':
    unittest.main()
