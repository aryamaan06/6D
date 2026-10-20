from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import engineering, lifecycle, project_authoring, project_investigation, workspace
from sixd.project_examples import example_projects
from sixd.providers import Turn
from sixd.workspace import WorkspaceStore, _digest
from sixd.workspace_scenarios import WorkspaceScenarios
from sixd.workspace_test_data import WorkspaceTestData


class OfflineAttitudeProvider:
    mode='offline_transport_fixture'
    model='offline-attitude-evidence-test'
    def __init__(self):self.request_attempts=0;self.histories=[]
    def complete(self,messages,tools):
        self.request_attempts+=1;self.histories.append(deepcopy(messages))
        available={t['function']['name']:t for t in tools}
        required=json.loads(messages[1]['content'])['required_actions']
        action=next(k for k in ('read_requirement','read_model','read_changes','recheck_model','finish') if k in available and (k!='read_changes' or k in required))
        args={}
        if action=='finish':
            args={'evidence_ids':available[action]['function']['parameters']['properties']['evidence_ids']['items']['enum'],
                  'summary':'The calculated criterion is met within the supplied single-axis sampled model. Review the inertia, controller gains, torque authority and disturbance sources; inspect the assessment window and grid differences. Obtain independent control analysis and sensor and actuator evidence. Navigation, three-axis motion and hardware validity remain unassessed.'}
        return Turn({'role':'assistant','content':None,'tool_calls':[{'id':'offline-attitude-'+str(self.request_attempts),
            'type':'function','function':{'name':action,'arguments':json.dumps(args)}}]},{'prompt_tokens':10,'completion_tokens':10})


class AttitudeWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.addCleanup(self.tmp.cleanup)
        self.store=WorkspaceStore(Path(self.tmp.name)/'workspace.sqlite3')
        self.project=example_projects()['attitude_review'];self.identity=self.project['project_id']
    def run_reference(self):
        self.store.create_project(self.project)
        return self.store.run(self.identity,1)

    def test_saved_review_reopens_with_complete_response(self):
        v=self.run_reference()
        self.assertTrue(lifecycle.verify_review(v['run']['review']))
        self.assertEqual(v['run']['review']['findings']['pointing_window']['status'],'met')
        self.assertEqual(v['run']['live_model_calls'],0)
        self.assertFalse(v['run']['review']['launch_authorization'])
        response=v['run']['model_results']['pointing']['attitude_response']
        self.assertEqual(len(response['samples']),1025)
        self.assertEqual(response,v['run']['review']['evidence']['pointing']['attitude_response'])
        with patch.object(workspace,'evaluate_models',side_effect=AssertionError('Read must not execute adapters')), patch.object(engineering.attitude,'_integrate',side_effect=AssertionError('Read must not integrate')):
            self.assertEqual(self.store.get(self.identity),v)

    def test_change_torque_targets_control_and_reuses_thermal(self):
        v=self.run_reference();p=deepcopy(v['project']);p['inputs']['max_torque']['value']=0
        with patch.object(workspace,'evaluate_models',side_effect=AssertionError('Draft preview must not calculate')):
            impact=self.store.preview_change(self.identity,1,p)
        self.assertEqual(impact['affected_model_ids'],['pointing'])
        self.store.save_revision(self.identity,1,p)
        current=self.store.run(self.identity,2)
        self.assertEqual(current['run']['executed_model_ids'],['pointing'])
        self.assertEqual(current['run']['reused_model_ids'],['thermal'])
        self.assertEqual(current['run']['model_results']['pointing']['status'],'completed')
        self.assertEqual(current['run']['review']['findings']['pointing_window']['status'],'not_met')
        self.assertEqual(current['run']['review']['findings']['rate_window']['status'],'met')
        self.assertEqual(self.store.get(self.identity,1)['run']['review'],v['run']['review'])

    def test_limit_only_revision_reuses_response_but_changes_criterion(self):
        v=self.run_reference();p=deepcopy(v['project']);p['inputs']['pointing_limit']['value']=0
        self.store.save_revision(self.identity,1,p);c=self.store.run(self.identity,2)
        self.assertEqual(c['run']['executed_model_ids'],[])
        self.assertEqual(set(c['run']['reused_model_ids']),{'pointing','thermal'})
        self.assertEqual(c['run']['review']['findings']['pointing_window']['status'],'not_met')
        self.assertEqual(c['run']['model_results']['pointing'],v['run']['model_results']['pointing'])

    def test_invalid_model_is_unassessed_and_thermal_remains_available(self):
        self.project['inputs']['inertia']['value']=0
        v=self.run_reference()
        self.assertEqual(v['run']['model_results']['pointing']['status'],'invalid_inputs')
        self.assertEqual(v['run']['review']['findings']['pointing_window']['status'],'not_assessed')
        self.assertEqual(v['run']['model_results']['thermal']['status'],'completed')

    def test_requirement_unit_mismatch_is_a_gap(self):
        self.project['inputs']['pointing_limit']['unit']='m'
        v=self.run_reference()
        self.assertEqual(v['run']['model_results']['pointing']['status'],'completed')
        self.assertEqual(v['run']['review']['findings']['pointing_window']['status'],'not_assessed')

    def test_absent_and_illegal_artifacts_cannot_pass(self):
        good=engineering.evaluate_models(self.project)
        for failure in ('absent','invalid','modified'):
            bad=deepcopy(good)
            if failure=='absent':del bad['pointing']['attitude_response']
            if failure=='invalid':bad['pointing']['status']='invalid_inputs';bad['pointing']['metrics']={}
            if failure=='modified':bad['pointing']['attitude_response']['samples'][1]['error_rad']=0
            with self.subTest(failure=failure),self.assertRaises(ValueError):
                lifecycle.review_project(self.project,bad)

    def test_rehashed_review_cannot_hide_changed_response(self):
        r=deepcopy(self.run_reference()['run']['review']);e=r['evidence']['pointing']
        e['attitude_response']['samples'][1]['error_rad']=0
        e['fingerprint']=_digest({k:v for k,v in e.items() if k!='fingerprint'})
        r['digest']=_digest({k:v for k,v in r.items() if k!='digest'})
        with self.assertRaises(ValueError):lifecycle.verify_review(r)

    def test_legacy_orbital_source_set_stays_readable(self):
        p=example_projects()['orbital_review']
        versions={k:v for k,v in engineering.MODEL_VERSIONS.items() if k!='attitude_control'}
        sources={k:v for k,v in lifecycle._verification_sources().items() if k not in {'attitude.py','chains.py'}}
        with patch.object(lifecycle,'_verification_sources',return_value=sources),patch.dict(engineering.MODEL_VERSIONS,versions,clear=True):
            r=lifecycle.review_project(p,engineering.evaluate_models(p))
        self.assertTrue(lifecycle.verify_review(r))
        self.assertNotIn('attitude.py',r['verification_sources'])

    def test_attitude_cannot_omit_new_solver_source(self):
        sources={k:v for k,v in lifecycle._verification_sources().items() if k not in {'attitude.py','chains.py'}}
        with patch.object(lifecycle,'_verification_sources',return_value=sources),self.assertRaises(ValueError):
            lifecycle.review_project(self.project,engineering.evaluate_models(self.project))

    def test_catalog_and_preflight_are_exact_and_do_not_calculate(self):
        with patch.object(engineering.attitude,'evaluate',side_effect=AssertionError('No calculation')):
            c=project_authoring.catalog();p=project_authoring.preflight(self.project)
        self.assertTrue(p['can_run'])
        model=next(m for m in c['models'] if m['type']=='attitude_control')
        self.assertEqual({r['name']:r['unit'] for r in model['parameters']},engineering.attitude.PARAMETERS)
        self.assertEqual(len(model['metrics']),9)

    def test_torque_sweep_preserves_baseline_and_reports_failure(self):
        v=self.run_reference()
        r=WorkspaceScenarios(self.store).run(self.identity,1,v['run']['run_id'],{
            'schema':'sixd.scenario-spec.v1','name':'Constructed actuator authority alternatives',
            'source':'Synthetic assumptions, not hardware data','mode':'sweep','input_id':'max_torque','values':[1,0]})
        a,b=r['receipt']['cases']
        self.assertEqual(a['executed_model_ids'],[])
        self.assertEqual(b['executed_model_ids'],['pointing'])
        row=next(f for f in b['findings'] if f['requirement_id']=='pointing_window')
        self.assertEqual(row['status'],'not_met')
        self.assertEqual(self.store.get(self.identity),v)

    def test_scalar_test_uses_declared_window_observable_separate_from_prediction(self):
        v=self.run_reference()
        r=WorkspaceTestData(self.store).run(self.identity,1,v['run']['run_id'],{
            'schema':'sixd.test-comparison-spec.v1','name':'Constructed pointing observation',
            'source':'Synthetic scalar observation, not measured hardware','data_kind':'synthetic',
            'test_conditions':'Same declared maximum absolute error observable over sampled assessment window; unverified conditions.',
            'conditions_match':'declared_match','filename':'pointing.csv',
            'csv_text':'id,req,value,unit,tolerance\na,pointing_window,0.002,rad,0.003\n',
            'mapping':{'measurement_id':'id','requirement_id':'req','value':'value','unit':'unit','tolerance':'tolerance'}})
        row=r['receipt']['row_results'][0]
        self.assertEqual(row['measurement_requirement']['status'],'not_met')
        self.assertEqual(row['prediction_agreement']['status'],'within_tolerance')
        self.assertEqual(v['run']['review']['findings']['pointing_window']['status'],'met')

    def test_offline_assistant_reads_bounded_projection_and_rechecks_control_only(self):
        v=self.run_reference();provider=OfflineAttitudeProvider()
        with patch.object(project_investigation,'evaluate_models',wraps=engineering.evaluate_models) as calculate:
            r=project_investigation.investigate_project(v,'pointing_window','Explain this criterion.',provider,investigation_id='offline-attitude')
        self.assertEqual(r['state'],'completed',r)
        self.assertEqual(r['live_model_calls'],0)
        self.assertEqual(calculate.call_count,1)
        self.assertEqual(calculate.call_args.args[0]['models'][0]['id'],'pointing')
        self.assertTrue(r['evidence']['recheck:pointing']['matches_saved_result'])
        evidence=r['evidence']['model:pointing']
        full=evidence['recorded_evidence']['attitude_response']
        projection=project_investigation._provider_evidence(evidence)['recorded_evidence']
        self.assertNotIn('attitude_response',projection)
        self.assertEqual(projection['attitude_summary_projection']['artifact_digest'],lifecycle._digest(full))
        self.assertLessEqual(len(projection['attitude_summary_projection']['witness_samples']),7)
        self.assertEqual(self.store.get(self.identity),v)


if __name__=='__main__':unittest.main()
