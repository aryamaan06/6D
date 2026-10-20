"""Verify the differential harness detects deliberately stale evidence."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
import verify_recalculation as verification
import audit_recalculation_reuse as reuse_audit
from recalculation_cases import build_cases
from sixd import engineering,workspace
from sixd.project_examples import example_projects


def thermal_case():
    before=example_projects()['baseline']
    before['models']=[m for m in before['models'] if m['id']=='thermal']
    before['requirements']=[r for r in before['requirements'] if r['model_id']=='thermal']
    after=deepcopy(before);after['inputs']['heat_input']['value']=700
    return dict(id='thermal-verification',family='radiative_equilibrium',operation='numeric_input',
                expected_valid=True,before=before,after=after,detail='Changed heat must recalculate thermal evidence.')


class VerificationHarnessTests(unittest.TestCase):
    def check(self,case):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as directory:
            return verification.check_case(case,Path(directory))

    def test_real_incremental_change_matches_complete_fresh_review(self):
        row=self.check(thermal_case())
        self.assertEqual(row['outcome'],'equivalent')
        self.assertEqual(row['executed_model_ids'],['thermal'])
        self.assertEqual(row['requirement_statuses']['thermal_limit'],'not_met')

    def test_deliberately_broken_reuse_key_is_detected(self):
        with patch.object(workspace,'_model_key',return_value='deliberately-unsafe-reuse'):
            with self.assertRaisesRegex(AssertionError,'Targeted/full engineering reviews differ'):
                self.check(thermal_case())

    def test_complete_comparison_retains_non_numerical_evidence(self):
        left={'evidence':{'a':{'assumptions':['declared basis'],'metrics':{'x':{'value':1,'unit':'N'}}}}}
        right=deepcopy(left);right['evidence']['a']['assumptions']=['different basis']
        self.assertEqual(verification.differences(left,right)[0]['path'],'$.evidence.a.assumptions[0]')

    def test_invalid_reference_and_workspace_edit_are_rejected_without_mutation(self):
        case=thermal_case();case['expected_valid']=False
        case['after']['requirements'][0]['operator']='approximately'
        row=self.check(case)
        self.assertEqual(row['outcome'],'rejected_consistently')
        self.assertEqual(set(row['workspace_errors']),{'preview','save'})

    def test_structurally_valid_wrong_unit_remains_a_gap_on_both_paths(self):
        case=thermal_case();case['after']['inputs']['heat_input']['unit']='kW'
        row=self.check(case)
        self.assertEqual(row['model_statuses']['thermal'],'invalid_inputs')
        self.assertEqual(row['requirement_statuses']['thermal_limit'],'not_assessed')

    def test_full_reference_never_uses_workspace_selection(self):
        with patch.object(workspace,'_model_key',side_effect=AssertionError('reuse forbidden')),patch.object(workspace,'_impact',side_effect=AssertionError('impact forbidden')):
            review=verification.full_review(thermal_case()['after'])
        self.assertEqual(review['findings']['thermal_limit']['status'],'not_met')

    def test_generated_cases_are_reproducible_stratified_and_seeded(self):
        a=list(build_cases(20261019,256));b=list(build_cases(20261019,256));c=list(build_cases(20261020,256))
        self.assertEqual(verification.encode(a),verification.encode(b))
        self.assertNotEqual(verification.encode(a),verification.encode(c))
        self.assertEqual(len({row['id'] for row in a}),256)
        self.assertEqual(len({row['family'] for row in a}),8)
        self.assertGreater(len({row['operation'] for row in a}),45)
        for row in a:
            from sixd.lifecycle import validate_project
            validate_project(row['before'])
            try:validate_project(row['after']);valid=True
            except ValueError:valid=False
            self.assertEqual(valid,row['expected_valid'],row['id']+' '+row['operation'])

    def test_signed_zero_retains_exact_fresh_receipt_identity(self):
        case=thermal_case()
        case['before']['inputs']['heat_input']['value']=0.0
        case['before']['inputs']['background_temperature']['value']=0.0
        case['after']=deepcopy(case['before']);case['after']['inputs']['background_temperature']['value']=-0.0
        row=self.check(case)
        self.assertEqual(row['outcome'],'equivalent')
        self.assertEqual(row['executed_model_ids'],['thermal'])

    def test_signed_zero_reuse_fix_preserves_ordinary_numeric_equivalence(self):
        case=thermal_case();project=case['before'];model=project['models'][0]
        def key(value):
            p=deepcopy(project);p['inputs']['heat_input']['value']=value
            return workspace._model_key(p,model,workspace._sources(),workspace.MODEL_VERSIONS)
        self.assertEqual(key(0),key(0.0))
        self.assertNotEqual(key(0.0),key(-0.0))
        self.assertEqual(key(200),key(200.0))

    def test_independent_reuse_audit_rejects_same_value_new_source(self):
        case=thermal_case();case['after']=deepcopy(case['before'])
        case['after']['inputs']['heat_input']['source']='Different supplied provenance'
        self.assertEqual(reuse_audit.unsafe_reuse(case,['thermal']),['thermal'])

    def test_independent_reuse_audit_follows_upstream_rationales(self):
        project=example_projects()['chain_review'];after=deepcopy(project)
        after['models'][0]['links']['tip_force']['rationale']='Changed physical mapping assumption'
        self.assertEqual(reuse_audit.unsafe_reuse({'before':project,'after':after},['beam','aero','thermal']),['beam'])

    def test_independent_reuse_audit_allows_unchanged_exact_numeric_value(self):
        case=thermal_case();case['after']=deepcopy(case['before'])
        case['after']['inputs']['heat_input']['value']=200.0
        self.assertEqual(reuse_audit.unsafe_reuse(case,['thermal']),[])


if __name__=='__main__':unittest.main()
