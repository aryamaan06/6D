"""Limited reference-existence guards; no claim of semantic completeness."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from sixd.explanation_quality import uncaptured_linked_reference_claim, explanation_acceptance
from sixd.whole_project_investigation import _quality
from sixd.workspace import WorkspaceStore
from sixd.project_investigation import investigate_project
from test_project_investigation import ScriptProvider


class UncapturedReferenceTests(unittest.TestCase):
    def test_positive_linked_reference_claim_is_blocked_only_with_known_empty_context(self):
        text='The linked NASA thermal control reference is an untrusted supplemental annotation.'
        for context in ({'links':[]}, {}, {'thermal_limit':{'links':[]}}):
            self.assertTrue(uncaptured_linked_reference_claim(text, context))
        for context in (None, {'links':[{'source_id':'captured'}]}, {'thermal_limit':{'links':[{}]}}):
            self.assertFalse(uncaptured_linked_reference_claim(text, context))

    def test_explicit_absence_and_requests_to_obtain_new_material_are_not_existing_link_claims(self):
        for text in ('No linked references are captured.',
                     'There are no currently linked references.',
                     'The linked reference is not available.',
                     'Do not assume the linked reference exists.',
                     'Obtain a suitable NASA thermal reference and review its applicability.',
                     'Review the input source records and linked calculation metrics.'):
            with self.subTest(text=text):
                self.assertFalse(uncaptured_linked_reference_claim(text, {'links':[]}))

    def test_whole_project_rejected_scope_proposal_stays_rejected_and_new_scoped_paragraph_passes(self):
        findings={'thermal_limit':{'status':'not_met'}, 'control_tracking':{'status':'not_assessed'}}
        failed='Focus on thermal limit and control tracking. Verify thermal model applicability and obtain control analysis.'
        self.assertIn('scope_missing', _quality(failed, findings)['blocked_codes'])
        clean=('This is a bounded review of the saved evidence; excluded effects remain unassessed. '
               'Inspect the thermal assumptions and obtain applicable control analysis before extending these component findings to the wider design.')
        self.assertTrue(_quality(clean, findings, linked_sources={})['accepted'])
        invented=clean+' Review the linked NASA thermal control reference.'
        self.assertIn('uncaptured_linked_reference', _quality(invented, findings, linked_sources={})['blocked_codes'])

    def test_requirement_acceptance_rejects_invented_link_and_numeric_revision_without_weakening_clean_case(self):
        work=ROOT/'work';work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as folder:
            store=WorkspaceStore(Path(folder)/'workspace.sqlite3');identity=store.ensure_default()
            record=investigate_project(store.get(identity), 'thermal_limit', 'Explain the saved finding.',
                                       ScriptProvider(), investigation_id='reference-guard-fixture')
        self.assertEqual(record['state'],'completed')
        record['project_sources']={'links':[]}
        clean=('The calculated criterion is met within the bounded model. Review heat-load provenance, '
               'emissivity and the steady radiator assumptions before extending this result to a physical system.')
        record['summary']=clean
        self.assertTrue(explanation_acceptance(record)['accepted'])
        record['summary']=clean+' The linked NASA thermal control reference covers idealized cases.'
        self.assertIn('uncaptured_linked_reference', explanation_acceptance(record)['blocked_codes'])
        record['summary']=clean+' This is revision 2. The linked NASA thermal control reference covers idealized cases.'
        blocked=explanation_acceptance(record)['blocked_codes']
        self.assertIn('uncaptured_linked_reference',blocked)
        self.assertIn('unbound_numeric_literal',blocked)


if __name__=='__main__':
    unittest.main()
