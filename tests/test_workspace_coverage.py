"""Coverage declarations cannot manufacture calculated evidence or applicability."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import workspace, workspace_coverage
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError, _digest
from sixd.workspace_coverage import WorkspaceCoverage


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.store = WorkspaceStore(Path(self.temp.name) / 'workspace.sqlite3')
        self.project = deepcopy(example_projects()['baseline'])
        self.pid = self.project['project_id']
        self.store.create_project(self.project)
        self.coverage = WorkspaceCoverage(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def spec(self, **overrides):
        value = {'check_id': None, 'base_version': None, 'title': 'Thermal mission applicability',
                 'phase': 'Orbit operations', 'discipline': 'Thermal', 'requirement_id': 'thermal_limit',
                 'applicability': 'required', 'applicability_note': '', 'model_fit': 'unknown',
                 'fit_note': '', 'next_step': 'Review heat paths and steady-state assumptions.'}
        value.update(overrides)
        return value

    def save(self, spec=None, revision=1):
        return self.coverage.save(self.pid, revision, self.spec() if spec is None else spec,
                                  self.coverage.summary(self.pid, revision)['digest'])

    @staticmethod
    def declared(summary):
        return next(row for row in summary['checks'] if row['origin'] == 'declared')

    def update(self, row, revision=1, **changes):
        spec = {key: row[key] for key in workspace_coverage.SPEC_FIELDS}
        spec.update(changes)
        return self.save(spec, revision)

    def revise(self, **inputs):
        project = deepcopy(self.store.get(self.pid)['project'])
        base = int(project['revision'])
        for key, value in inputs.items():
            project['inputs'][key]['value'] = value
        self.store.save_revision(self.pid, base, project)
        return base + 1

    def canonical(self):
        with self.store._connect() as connection:
            return {table: [tuple(row) for row in connection.execute('SELECT * FROM '+table+' ORDER BY rowid')]
                    for table in ('projects', 'revisions', 'runs')}

    def test_empty_profile_exposes_every_requirement_without_inventing_run_or_fit(self):
        before = self.canonical()
        with patch.object(workspace, 'evaluate_models', side_effect=AssertionError('No calculations')):
            summary = self.coverage.summary(self.pid, 1)
        self.assertEqual(len(summary['checks']), len(self.project['requirements']))
        self.assertEqual({row['calculation_status'] for row in summary['checks']}, {'not_run'})
        self.assertEqual({row['model_fit'] for row in summary['checks']}, {'unknown'})
        self.assertEqual({row['coverage_status'] for row in summary['checks']}, {'applicability_unknown'})
        self.assertIsNone(summary['run_id'])
        self.assertEqual(summary, self.coverage.summary(self.pid, 1))
        self.assertEqual(before, self.canonical())

    def test_met_calculation_never_implies_model_fit(self):
        self.store.run(self.pid, 1)
        summary = self.save()
        row = self.declared(summary)
        self.assertEqual(row['calculation_status'], 'assessed')
        self.assertEqual(row['criterion_status'], 'met')
        self.assertEqual(row['coverage_status'], 'applicability_unknown')
        self.assertEqual(row['model']['physical_applicability'], 'not_assessed')
        self.assertEqual(len(summary['checks']), len(self.project['requirements']))
        self.assertTrue(row['model']['assumptions'])
        self.assertTrue(row['model']['not_assessed'])

    def test_fit_declaration_is_saved_as_unverified_and_never_changes_receipt(self):
        self.store.run(self.pid, 1)
        before = self.canonical()
        with patch.object(workspace, 'evaluate_model', side_effect=AssertionError('No calculator')):
            row = self.declared(self.save(self.spec(model_fit='declared_fit', fit_note='Constructed steady, single-surface case.')))
        self.assertEqual(row['coverage_status'], 'criterion_met')
        self.assertIn('unverified', row['reason'])
        self.assertEqual(row['model']['physical_applicability'], 'not_assessed')
        self.assertEqual(before, self.canonical())

    def test_outside_assumptions_wins_even_when_linked_criterion_is_met(self):
        self.store.run(self.pid, 1)
        row = self.declared(self.save(self.spec(model_fit='outside_assumptions', fit_note='Transient heating is required.')))
        self.assertEqual(row['criterion_status'], 'met')
        self.assertEqual(row['coverage_status'], 'outside_assumptions')

    def test_exclusion_never_erases_unmet_canonical_criterion(self):
        self.revise(maximum_temperature=200)
        self.store.run(self.pid, 2)
        before = self.canonical()
        profile = self.save(self.spec(applicability='excluded', applicability_note='A supplied exclusion that is not independently approved.'), 2)
        row = self.declared(profile)
        self.assertEqual(row['coverage_status'], 'excluded')
        self.assertEqual(row['criterion_status'], 'not_met')
        self.assertGreaterEqual(profile['criterion_counts']['not_met'], 1)
        self.assertEqual(before, self.canonical())

    def test_missing_and_undecided_checks_are_explicit_and_have_no_fake_model(self):
        row = self.declared(self.save(self.spec(requirement_id=None, title='Entry heating')))
        self.assertEqual(row['coverage_status'], 'missing_analysis')
        self.assertIsNone(row['model'])
        row = self.declared(self.update(row, applicability='undecided'))
        self.assertEqual(row['coverage_status'], 'undecided')

    def test_unsupported_model_is_missing_analysis_not_engineering_failure(self):
        project = deepcopy(example_projects()['missing_evidence'])
        project['project_id'], project['revision'] = 'unsupported-project', '1'
        self.store.create_project(project)
        self.store.run(project['project_id'], 1)
        profile = self.coverage.summary(project['project_id'], 1)
        row = next(row for row in profile['checks'] if row['requirement_id'] == 'control_tracking')
        self.assertEqual(row['calculation_status'], 'unsupported')
        self.assertEqual(row['criterion_status'], 'not_assessed')
        self.assertEqual(row['coverage_status'], 'missing_analysis')
        self.assertFalse(row['model']['supported'])

    def test_new_revision_and_rerun_do_not_reconfirm_old_declaration(self):
        self.store.run(self.pid, 1)
        original = self.declared(self.save(self.spec(model_fit='declared_fit', fit_note='Review of original conditions.')))
        self.revise(heat_input=600)
        row = self.declared(self.coverage.summary(self.pid, 2))
        self.assertTrue(row['needs_review'])
        self.assertEqual(row['calculation_status'], 'stale')
        self.assertIsNone(row['criterion_status'])
        self.store.run(self.pid, 2)
        row = self.declared(self.coverage.summary(self.pid, 2))
        self.assertEqual(row['criterion_status'], 'not_met')
        self.assertEqual(row['coverage_status'], 'needs_review')
        revised = self.declared(self.update(row, 2, fit_note='Reviewed revised conditions.'))
        self.assertFalse(revised['needs_review'])
        self.assertEqual(revised['coverage_status'], 'criterion_unmet')
        self.assertEqual(revised['version'], 2)
        self.assertEqual(revised['history'][0]['digest'], original['digest'])
        old = self.coverage.summary(self.pid, 1)
        self.assertFalse(old['can_edit'])
        self.assertEqual(self.declared(old)['version'], 1)
        self.assertEqual(self.declared(old)['criterion_status'], 'met')

    def test_unrelated_input_does_not_invalidate_mapped_fit_but_unmapped_is_conservative(self):
        row = self.declared(self.save())
        self.save(self.spec(requirement_id=None, title='Unmapped mission concern'))
        self.revise(thrust=400)
        summary = self.coverage.summary(self.pid, 2)
        linked = next(item for item in summary['checks'] if item['check_id'] == row['check_id'])
        unmapped = next(item for item in summary['checks'] if item['title'] == 'Unmapped mission concern')
        self.assertFalse(linked['needs_review'])
        self.assertTrue(unmapped['needs_review'])

    def test_removed_mapping_remains_visible_and_requires_review(self):
        row = self.declared(self.save())
        project = deepcopy(self.project)
        project['requirements'] = [item for item in project['requirements'] if item['id'] != 'thermal_limit']
        self.store.save_revision(self.pid, 1, project)
        row = self.declared(self.coverage.summary(self.pid, 2))
        self.assertEqual(row['coverage_status'], 'needs_review')
        self.assertIsNone(row['model'])
        self.assertIn('no longer', row['review_reasons'][0])
        with self.assertRaises(WorkspaceError):
            self.update(row, 2)
        updated = self.declared(self.update(row, 2, requirement_id=None, model_fit='unknown', fit_note=''))
        self.assertEqual(updated['coverage_status'], 'missing_analysis')

    def test_fresh_saved_run_invalidates_displayed_save_digest(self):
        old = self.coverage.summary(self.pid, 1)
        self.store.run(self.pid, 1)
        with self.assertRaises(ConflictError):
            self.coverage.save(self.pid, 1, self.spec(), old['digest'])

    def test_concurrent_edits_and_cross_project_record_ids_are_rejected(self):
        old = self.coverage.summary(self.pid, 1)
        row = self.declared(self.save())
        with self.assertRaises(ConflictError):
            self.coverage.save(self.pid, 1, self.spec(), old['digest'])
        self.update(row, title='Changed')
        with self.assertRaises(ConflictError):
            self.update(row, title='Stale edit')
        other = deepcopy(self.project)
        other['project_id'] = 'other-project'
        self.store.create_project(other)
        spec = {key: row[key] for key in workspace_coverage.SPEC_FIELDS}
        with self.assertRaises(ConflictError):
            self.coverage.save('other-project', 1, spec, self.coverage.summary('other-project', 1)['digest'])

    def test_historical_writes_missing_digests_invalid_declarations_are_rejected(self):
        for changes in ({'applicability':'excluded'}, {'model_fit':'declared_fit'},
                        {'model_fit':'outside_assumptions'}, {'title':''}, {'phase':''},
                        {'applicability':['required']}, {'base_version':True},
                        {'requirement_id':'unknown'}, {'extra':'ignored'}):
            with self.subTest(changes=changes), self.assertRaises(WorkspaceError):
                self.save(self.spec(**changes))
        for digest in (None, '', 'x'*64):
            with self.subTest(digest=digest), self.assertRaises(WorkspaceError):
                self.coverage.save(self.pid, 1, self.spec(), digest)
        self.revise(heat_input=600)
        with self.assertRaises(ConflictError):
            self.save()

    def test_declared_limits_bound_growth_and_preserve_old_versions(self):
        row = self.declared(self.save())
        with patch.object(workspace_coverage, 'MAX_CHECKS', 1), self.assertRaises(WorkspaceError):
            self.save(self.spec(title='Second check'))
        with patch.object(workspace_coverage, 'MAX_VERSIONS', 1), self.assertRaises(WorkspaceError):
            self.update(row, title='Second version')
        self.assertEqual(self.declared(self.coverage.summary(self.pid, 1))['version'], 1)

    def test_tampered_record_is_rejected(self):
        row = self.declared(self.save())
        with self.store._connect(write=True) as connection:
            connection.execute('UPDATE project_coverage_versions SET digest=? WHERE check_id=?', ('0'*64, row['check_id']))
        with self.assertRaisesRegex(WorkspaceError, 'inconsistent'):
            self.coverage.summary(self.pid, 1)

    def test_upstream_chain_edit_invalidates_downstream_declaration(self):
        project = deepcopy(example_projects()['chain_review'])
        self.store.create_project(project)
        identity = project['project_id']
        spec = self.spec(requirement_id='mount_stress', title='Beam load context')
        self.coverage.save(identity, 1, spec, self.coverage.summary(identity, 1)['digest'])
        project['inputs']['density']['value'] = .8
        self.store.save_revision(identity, 1, project)
        row = self.declared(self.coverage.summary(identity, 2))
        self.assertTrue(row['needs_review'])

    def test_current_requirement_unit_mismatch_stays_unassessed_even_with_declared_fit(self):
        project = deepcopy(self.project)
        project['project_id'] = 'unit-gap'
        project['inputs']['maximum_temperature']['unit'] = 'm'
        self.store.create_project(project)
        self.store.run(project['project_id'], 1)
        spec = self.spec(model_fit='declared_fit', fit_note='Supplied claim cannot repair incorrect units.')
        summary = self.coverage.save(project['project_id'], 1, spec, self.coverage.summary(project['project_id'], 1)['digest'])
        row = self.declared(summary)
        self.assertEqual(row['criterion_status'], 'not_assessed')
        self.assertEqual(row['coverage_status'], 'unassessed')


if __name__ == '__main__':
    unittest.main()
