"""Engineering work progress never rewrites canonical engineering results."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import workspace
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError, _digest, _encode
from sixd.workspace_sources import WorkspaceSources
from sixd.workspace_actions import WorkspaceActions, TEXT_FIELDS


class WorkspaceActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.store = WorkspaceStore(Path(self.temp.name) / 'workspace.sqlite3')
        self.project = deepcopy(example_projects()['missing_evidence'])
        self.project['inputs']['maximum_temperature']['value'] = 250
        self.identity = self.project['project_id']
        self.store.create_project(self.project)
        self.library = WorkspaceSources(self.store)
        self.queue = WorkspaceActions(self.store, self.library)

    def tearDown(self):
        self.temp.cleanup()

    def profile(self, revision=None):
        if revision is None:
            revision = self.store.get(self.identity)['revision']
        return self.queue.summary(self.identity, revision)

    def canonical(self):
        with self.store._connect() as connection:
            return {table: [tuple(row) for row in connection.execute('SELECT * FROM ' + table + ' ORDER BY rowid')]
                    for table in ('projects', 'revisions', 'runs')}

    def calculate(self, revision=1):
        return self.store.run(self.identity, revision)

    def create(self, origin='finding:thermal_limit', revision=1):
        profile = self.profile(revision)
        selected = next(item for item in profile['origins'] if item['target_id'] == origin)
        return self.queue.create(self.identity, revision, {'origin_id': origin, **selected['suggested'], 'note': 'User-declared action.'},
                                 expected_digest=profile['digest'])

    def action(self, profile=None):
        return (profile or self.profile())['actions'][0]

    def spec(self, action, status=None, **overrides):
        result = {key: deepcopy(action[key]) for key in TEXT_FIELDS}
        result.update(status=status or action['status'], closure_note=action['closure_note'], support_ids=action['support_ids'])
        result.update(overrides)
        return result

    def update(self, action, status=None, revision=None, **overrides):
        if revision is None:
            revision = self.store.get(self.identity)['revision']
        return self.queue.update(self.identity, revision, action['action_id'], action['version'], self.spec(action, status, **overrides),
                                 expected_digest=self.profile(revision)['digest'])

    def source(self, **overrides):
        value = {'source_id': None, 'base_version': None, 'title': 'Supplied thermal reference',
                 'url': 'https://example.org/thermal', 'excerpt': 'Constructed user-supplied reference text.', 'details': ''}
        value.update(overrides)
        return value

    def add_source(self, revision=1):
        return self.library.save_source(self.identity, revision, self.source())['sources'][-1]

    def revise(self, **changes):
        project = deepcopy(self.store.get(self.identity)['project'])
        revision = int(project['revision'])
        for identity, value in changes.items():
            project['inputs'][identity]['value'] = value
        self.store.save_revision(self.identity, revision, project)
        return revision + 1

    def close(self, action, support='finding:thermal_limit'):
        action = self.action(self.update(action, 'in_progress', support_ids=[support]))
        action = self.action(self.update(action, 'ready_for_review'))
        return self.action(self.update(action, 'closed', closure_note='Recorded work and limitations reviewed; engineering finding remains separate.'))

    def test_no_review_means_no_invented_finding_or_automatic_action(self):
        before = self.canonical()
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('Queue reads must not calculate')):
            profile = self.profile(1)
            self.assertEqual(profile['actions'], [])
            self.assertEqual(profile['origins'], [])
            self.assertEqual(profile['support_options'], [])
            self.assertIsNone(profile['run_id'])
        self.assertEqual(self.canonical(), before)

    def test_creation_uses_supported_guidance_and_does_not_auto_create_work(self):
        self.calculate()
        before = self.canonical()
        profile = self.profile(1)
        self.assertEqual(profile['actions'], [])
        self.assertIn('finding:thermal_limit', [item['target_id'] for item in profile['origins']])
        self.assertIn('finding:control_tracking', [item['target_id'] for item in profile['origins']])
        created = self.action(self.create())
        self.assertEqual(created['status'], 'todo')
        self.assertEqual(created['review_status'], 'current')
        self.assertIn('temperature', (created['title'] + created['next_check']).lower())
        self.assertTrue(created['completion_criteria'])
        self.assertEqual(self.canonical(), before)

    def test_forward_workflow_requires_review_note_and_support_for_closure(self):
        baseline = self.calculate()
        before = self.canonical()
        action = self.action(self.create())
        with self.assertRaises(ConflictError):
            self.update(action, 'closed', closure_note='Done', support_ids=['finding:thermal_limit'])
        action = self.action(self.update(action, 'in_progress'))
        action = self.action(self.update(action, 'ready_for_review'))
        for updates in ({'closure_note': 'Done'}, {'support_ids': ['finding:thermal_limit']}):
            with self.subTest(updates=updates), self.assertRaises(WorkspaceError):
                self.update(action, 'closed', **updates)
        action = self.action(self.update(action, 'closed', closure_note='Checked evidence; issue remains visible.', support_ids=['finding:thermal_limit']))
        self.assertEqual(action['status'], 'closed')
        self.assertEqual(len(action['history']), 4)
        self.assertEqual(action['supports'][0]['snapshot']['finding']['status'], 'not_met')
        self.assertEqual(self.store.get(self.identity, 1)['run']['review'], baseline['run']['review'])
        self.assertEqual(self.canonical(), before)

    def test_unassessed_action_closure_does_not_close_engineering_coverage(self):
        self.calculate()
        source = self.add_source()
        action = next(item for item in self.create('finding:control_tracking')['actions'] if item['origin']['id'] == 'control_tracking')
        closed = self.close(action, 'source:' + source['source_id'])
        self.assertEqual(closed['status'], 'closed')
        self.assertEqual(self.store.get(self.identity, 1)['run']['review']['findings']['control_tracking']['status'], 'not_assessed')

    def test_new_source_version_flags_closed_action_and_never_refreshes_same_support_id(self):
        self.calculate()
        source = self.add_source()
        support_id = 'source:' + source['source_id']
        closed = self.close(self.action(self.create()), support_id)
        self.library.save_source(self.identity, 1, self.source(source_id=source['source_id'], base_version=1, excerpt='New passage not reviewed for closure.'))
        flagged = self.action()
        self.assertEqual(flagged['status'], 'closed')
        self.assertEqual(flagged['review_status'], 'needs_review')
        self.assertEqual(flagged['supports'][0]['snapshot']['version'], 1)
        with self.assertRaises(ConflictError):
            self.update(flagged, 'closed')
        reopened = self.action(self.update(flagged, 'in_progress'))
        self.assertEqual(reopened['supports'][0]['snapshot']['version'], 1)
        self.assertEqual(reopened['closure_note'], '')
        reviewed = self.action(self.queue.review(self.identity, 1, reopened['action_id'], reopened['version'], expected_digest=self.profile()['digest']))
        self.assertEqual(reviewed['supports'], [])
        self.assertEqual(reviewed['review_status'], 'current')
        selected = self.action(self.update(reviewed, support_ids=[support_id]))
        self.assertEqual(selected['supports'][0]['snapshot']['version'], 2)
        self.assertEqual(selected['history'][3]['supports'][0]['snapshot']['version'], 1)

    def test_same_revision_rerun_flags_origin_and_pins_original_finding(self):
        first = self.calculate()
        closed = self.close(self.action(self.create()))
        second = self.calculate()
        flagged = self.action()
        self.assertEqual(flagged['review_status'], 'needs_review')
        self.assertEqual(flagged['origin']['run_id'], first['run']['run_id'])
        self.assertEqual(flagged['supports'][0]['snapshot']['run_id'], first['run']['run_id'])
        reviewed = self.action(self.queue.review(self.identity, 1, flagged['action_id'], flagged['version'], expected_digest=self.profile()['digest']))
        self.assertEqual(reviewed['status'], 'in_progress')
        self.assertEqual(reviewed['origin']['run_id'], second['run']['run_id'])
        self.assertEqual(reviewed['history'][-2]['status'], 'closed')
        with self.store._connect() as connection:
            original = connection.execute('SELECT receipt FROM runs WHERE run_id=?', (first['run']['run_id'],)).fetchone()
        self.assertEqual(__import__('json').loads(original['receipt'])['review'], first['run']['review'])

    def test_missing_current_review_flags_origin_unavailable_without_rewriting_workflow(self):
        self.calculate()
        action = self.action(self.create())
        revision = self.revise(heat_input=250)
        flagged = self.action(self.profile(revision))
        self.assertEqual(flagged['review_status'], 'origin_unavailable')
        self.assertEqual(flagged['status'], 'todo')
        self.assertIsNone(flagged['current_origin'])
        with self.assertRaises(ConflictError):
            self.queue.review(self.identity, revision, action['action_id'], action['version'], expected_digest=self.profile(revision)['digest'])
        self.calculate(revision)
        current = self.profile(revision)
        reviewed = self.action(self.queue.review(self.identity, revision, action['action_id'], action['version'], expected_digest=current['digest']))
        self.assertEqual(reviewed['review_status'], 'current')
        self.assertEqual(self.action(self.profile(1))['version'], 1)

    def test_origin_can_be_reviewed_after_a_new_finding_becomes_met(self):
        self.calculate()
        action = self.action(self.create())
        revision = self.revise(maximum_temperature=500)
        self.calculate(revision)
        profile = self.profile(revision)
        self.assertNotIn('finding:thermal_limit', [item['target_id'] for item in profile['origins']])
        reviewed = self.action(self.queue.review(self.identity, revision, action['action_id'], action['version'], expected_digest=profile['digest']))
        self.assertEqual(reviewed['review_status'], 'current')
        self.assertEqual(reviewed['status'], 'todo')
        self.assertEqual(reviewed['origin_context']['finding']['status'], 'met')

    def test_source_flag_origin_observes_repeated_changes_even_when_reason_is_identical(self):
        source = self.add_source()
        linked = self.library.link_source(self.identity, 1, {'source_id': source['source_id'], 'source_version': 1,
            'target_id': 'requirement:thermal_limit', 'note': 'Manual thermal context.'})['links'][0]
        self.library.save_source(self.identity, 1, self.source(source_id=source['source_id'], base_version=1, excerpt='Version two.'))
        origin = 'source_link:' + linked['link_id']
        action = self.action(self.create(origin))
        self.assertEqual(action['review_status'], 'current')
        self.library.save_source(self.identity, 1, self.source(source_id=source['source_id'], base_version=2, excerpt='Version three.'))
        self.assertEqual(self.action()['review_status'], 'needs_review')
        current = self.profile()
        reviewed = self.action(self.queue.review(self.identity, 1, action['action_id'], action['version'], expected_digest=current['digest']))
        self.assertEqual(reviewed['origin_context']['latest_source']['version'], 3)
        revision = self.revise(density=.02)
        self.assertEqual(self.action(self.profile(revision))['review_status'], 'current')
        revision = self.revise(heat_input=350)
        self.assertEqual(self.action(self.profile(revision))['review_status'], 'needs_review')

    def test_expected_context_and_base_versions_refuse_stale_writes(self):
        self.calculate()
        profile = self.create()
        action = self.action(profile)
        self.calculate()
        with self.assertRaises(ConflictError):
            self.queue.update(self.identity, 1, action['action_id'], action['version'], self.spec(action, 'in_progress'), expected_digest=profile['digest'])
        current = self.profile()
        reviewed = self.action(self.queue.review(self.identity, 1, action['action_id'], action['version'], expected_digest=current['digest']))
        with self.assertRaises(ConflictError):
            self.queue.update(self.identity, 1, action['action_id'], 1, self.spec(reviewed, 'in_progress'), expected_digest=self.profile()['digest'])
        for digest in (None, '', 'A' * 64, 42, True):
            with self.subTest(digest=digest), self.assertRaises(WorkspaceError):
                self.queue.review(self.identity, 1, reviewed['action_id'], reviewed['version'], expected_digest=digest)

    def test_source_support_cannot_change_between_visible_review_and_close(self):
        self.calculate()
        source = self.add_source()
        action = self.action(self.create())
        action = self.action(self.update(action, 'in_progress', support_ids=['source:' + source['source_id']]))
        profile = self.update(action, 'ready_for_review')
        action = self.action(profile)
        self.library.save_source(self.identity, 1, self.source(source_id=source['source_id'], base_version=1, excerpt='Unseen replacement passage.'))
        with self.assertRaises(ConflictError):
            self.queue.update(self.identity, 1, action['action_id'], action['version'],
                              self.spec(action, 'closed', closure_note='Reviewed old passage.'), expected_digest=profile['digest'])
        self.assertEqual(self.action()['status'], 'ready_for_review')
        self.assertEqual(self.action()['version'], action['version'])

    def test_chained_source_flag_origin_detects_upstream_change_but_ignores_unrelated_input(self):
        project = deepcopy(example_projects()['chain_review'])
        self.identity = project['project_id']
        self.store.create_project(project)
        source = self.add_source()
        linked = self.library.link_source(self.identity, 1, {'source_id': source['source_id'], 'source_version': 1,
            'target_id': 'requirement:mount_stress', 'note': 'Declared drag-to-beam transfer applicability.'})['links'][0]
        self.revise(density=.6)
        action = self.action(self.create('source_link:' + linked['link_id'], revision=2))
        self.assertEqual(action['review_status'], 'current')
        self.revise(heat_input=300)
        self.assertEqual(self.action(self.profile(3))['review_status'], 'current')
        self.revise(density=.9)
        flagged = self.action(self.profile(4))
        self.assertEqual(flagged['review_status'], 'needs_review')
        self.assertEqual(flagged['origin_context']['link']['review_reasons'],
                         self.library.summary(self.identity, 4)['links'][0]['review_reasons'])

    def test_explicit_action_and_version_bounds_preserve_prior_records(self):
        self.calculate()
        action = self.action(self.create())
        with patch('sixd.workspace_actions.MAX_VERSIONS', 1), self.assertRaises(WorkspaceError):
            self.update(action, 'in_progress')
        profile = self.profile()
        other = next(item for item in profile['origins'] if item['target_id'] != action['origin']['target_id'])
        with patch('sixd.workspace_actions.MAX_ACTIONS', 1), self.assertRaises(WorkspaceError):
            self.queue.create(self.identity, 1, {'origin_id': other['target_id'], **other['suggested'], 'note': ''},
                              expected_digest=self.profile()['digest'])
        self.assertEqual(self.action()['version'], 1)
        self.assertEqual(len(self.profile()['actions']), 1)

    def test_history_and_new_records_are_hidden_from_older_project_revisions(self):
        self.calculate()
        action = self.action(self.create())
        revision = self.revise(heat_input=250)
        self.calculate(revision)
        old = self.profile(1)
        self.assertEqual(old['actions'][0]['version'], 1)
        with self.assertRaises(ConflictError):
            self.queue.update(self.identity, 1, action['action_id'], action['version'], self.spec(action, 'in_progress'), expected_digest=old['digest'])
        profile = self.profile(revision)
        self.queue.review(self.identity, revision, action['action_id'], action['version'], expected_digest=profile['digest'])
        self.assertEqual(self.action(self.profile(1))['version'], 1)
        self.assertEqual(self.action(self.profile(revision))['version'], 2)

    def test_note_update_does_not_relabel_old_origin_context_as_new_revision(self):
        self.calculate()
        action = self.action(self.create())
        revision = self.revise(heat_input=250)
        updated = self.action(self.update(action, 'in_progress', revision=revision, note='Awaiting a supported rerun.'))
        self.assertEqual(updated['basis_revision'], 2)
        self.assertEqual(updated['origin_basis_revision'], 1)
        self.assertEqual(updated['review_status'], 'origin_unavailable')
        self.calculate(2)
        profile = self.profile(2)
        reviewed = self.action(self.queue.review(self.identity, 2, updated['action_id'], updated['version'], expected_digest=profile['digest']))
        self.assertEqual(reviewed['origin_basis_revision'], 2)
        self.assertEqual(reviewed['history'][-2]['origin_basis_revision'], 1)

    def test_duplicate_open_origin_and_invalid_fields_are_rejected(self):
        self.calculate()
        action = self.action(self.create())
        with self.assertRaises(ConflictError):
            self.create()
        for changes in ({'title': ''}, {'next_check': ''}, {'status': 'approved'}, {'support_ids': ['missing']},
                        {'support_ids': ['finding:thermal_limit'] * 2}, {'closure_note': '\0'}):
            with self.subTest(changes=changes), self.assertRaises((WorkspaceError, ConflictError)):
                self.update(action, **changes)

    def test_queue_records_are_project_scoped_and_tampering_is_controlled(self):
        self.calculate()
        action = self.action(self.create())
        other = deepcopy(self.project)
        other['project_id'] = 'another-project'
        self.store.create_project(other)
        other_profile = self.queue.summary(other['project_id'], 1)
        with self.assertRaises(ConflictError):
            self.queue.update(other['project_id'], 1, action['action_id'], 1, self.spec(action), expected_digest=other_profile['digest'])
        with self.store._connect(write=True) as connection:
            row = connection.execute('SELECT * FROM project_action_versions').fetchone()
            value = __import__('json').loads(row['snapshot'])
            value['origin_context']['finding']['status'] = 'met'
            connection.execute('UPDATE project_action_versions SET snapshot=?,digest=?', (_encode(value), _digest(value)))
        with self.assertRaises(WorkspaceError):
            self.profile()

    def test_reads_and_action_writes_never_run_calculators_or_modify_canonical_rows(self):
        self.calculate()
        before = self.canonical()
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('No calculations')):
            profile = self.create()
            action = self.action(profile)
            self.update(action, 'in_progress', support_ids=['finding:thermal_limit'])
            self.assertEqual(self.profile(), self.profile())
        self.assertEqual(self.canonical(), before)


if __name__ == '__main__':
    unittest.main()
