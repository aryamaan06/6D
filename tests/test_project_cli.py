from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from sixd.cli import main
from sixd.engineering import evaluate_models
from sixd.lifecycle import compare_reviews, review_project, validate_project
from sixd.project_examples import example_projects
from sixd.project_io import read_json, read_review, save_review


class ProjectWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def run_cli(self, arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(arguments)
        return result, output.getvalue()

    def test_constructed_change_detects_thermal_requirement_and_selective_dependencies(self):
        examples = example_projects()
        reviews = {key: review_project(validate_project(project), evaluate_models(project))
                   for key, project in examples.items()}
        baseline, revised, missing = (reviews[key] for key in ('baseline', 'revised', 'missing_evidence'))
        self.assertEqual(baseline['review_status'], 'supported_requirements_met')
        self.assertEqual(revised['failed_requirements'], ['thermal_limit'])
        self.assertEqual(missing['review_status'], 'incomplete')
        self.assertEqual(missing['unresolved_requirements'], ['control_tracking'])
        self.assertEqual(missing['failed_requirements'], ['thermal_limit'])
        impact = compare_reviews(baseline, revised)
        self.assertEqual(impact['changed_inputs'], ['heat_input', 'thrust'])
        self.assertEqual(impact['unchanged_evidence_applicability'], ['drag_limit'])
        self.assertEqual(set(impact['previous_evidence_needs_rechecking']),
                         {'fuel_margin', 'burn_duration', 'mount_stress', 'mount_deflection', 'thermal_limit'})
        self.assertTrue(all(review['launch_authorization'] is False for review in reviews.values()))

    def test_demo_writes_preserved_verified_snapshots_without_provider_access(self):
        self.assertIn('orbital_review', example_projects())
        with patch('sixd.providers.make_provider', side_effect=AssertionError('No provider in project demo')), \
                patch('sixd.orbital_adapter.evaluate', side_effect=AssertionError('Independent templates do not enter the revision-chain demo')):
            result, output = self.run_cli(['project-demo', '--output', str(self.directory)])
        self.assertEqual(result, 0)
        self.assertIn('Live model calls: 0', output)
        records = [read_review(path) for path in self.directory.glob('*.json')]
        self.assertEqual(len(records), 3)
        self.assertEqual({review['revision'] for review in records}, {'1', '2', '3'})
        self.assertEqual({review['project_id'] for review in records}, {'constructed-engineering-change'})

    def test_json_input_to_review_compare_and_verify_is_usable(self):
        examples = example_projects()
        project_path = self.directory / 'project.json'
        project_path.write_text(json.dumps(examples['baseline']), encoding='utf-8')
        output_directory = self.directory / 'reviews'
        result, _ = self.run_cli(['project-review', str(project_path), '--output', str(output_directory)])
        self.assertEqual(result, 0)
        old = next(output_directory.glob('*.json'))
        original = old.read_bytes()
        project_path.write_text(json.dumps(examples['revised']), encoding='utf-8')
        result, output = self.run_cli(['project-review', str(project_path), '--output', str(output_directory), '--compare-with', str(old)])
        self.assertEqual(result, 1)
        self.assertIn('requirements_not_met', output)
        self.assertIn('previous_evidence_needs_rechecking', output)
        new = next(path for path in output_directory.glob('*.json') if path != old)
        self.assertEqual(old.read_bytes(), original)
        self.assertEqual(self.run_cli(['project-verify', str(new)])[0], 0)
        self.assertEqual(self.run_cli(['project-compare', str(old), str(new)])[0], 0)

    def test_invalid_units_create_unresolved_requirement_without_invented_conversion(self):
        project = example_projects()['baseline']
        project['inputs']['heat_input']['unit'] = 'kW'
        review = review_project(validate_project(project), evaluate_models(project))
        self.assertEqual(review['findings']['thermal_limit']['status'], 'not_assessed')
        self.assertEqual(review['review_status'], 'incomplete')
        self.assertEqual(review['evidence']['thermal']['metrics'], {})

    def test_cross_project_comparison_does_not_write_a_new_review(self):
        project = example_projects()['baseline']
        old = save_review(review_project(project, evaluate_models(project)), self.directory)
        changed = deepcopy(project)
        changed['project_id'] = 'different-project'
        source = self.directory / 'new-input.json'
        source.write_text(json.dumps(changed), encoding='utf-8')
        output = self.directory / 'output'
        result, message = self.run_cli(['project-review', str(source), '--output', str(output), '--compare-with', str(old)])
        self.assertEqual(result, 2)
        self.assertIn('different projects', message)
        self.assertFalse(output.exists())

    def test_duplicate_fields_and_nonstandard_constants_rejected_before_evaluation(self):
        for contents in ('{"schema":"a","schema":"b"}', '{"value":NaN}', '{"value":Infinity}'):
            source = self.directory / 'bad.json'
            source.write_text(contents, encoding='utf-8')
            with self.assertRaises(ValueError):
                read_json(source)
            with patch('sixd.engineering.evaluate_models', side_effect=AssertionError('Invalid JSON must not reach solver')):
                self.assertEqual(self.run_cli(['project-review', str(source)])[0], 2)

    def test_saved_review_edit_is_rejected(self):
        project = example_projects()['baseline']
        path = save_review(review_project(project, evaluate_models(project)), self.directory)
        record = json.loads(path.read_text(encoding='utf-8'))
        record['findings']['fuel_margin']['status'] = 'not_met'
        path.write_text(json.dumps(record), encoding='utf-8')
        self.assertEqual(self.run_cli(['project-verify', str(path)])[0], 2)


if __name__ == '__main__':
    unittest.main()
