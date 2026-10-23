from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import powered_flight, engineering, lifecycle, project_authoring, project_investigation, workspace
from sixd.project_examples import powered_flight_review, example_projects
from sixd.workspace import WorkspaceStore
from sixd.workspace_scenarios import WorkspaceScenarios
from sixd.workspace_test_data import WorkspaceTestData
from sixd.test_evidence import TestEvidence
from sixd.workspace_coverage import WorkspaceCoverage
from sixd.providers import Turn


class OfflineFlightProvider:
    mode='offline_transport_fixture'
    model='offline-flight-workflow-test'
    def __init__(self):self.request_attempts=0
    def complete(self,messages,tools):
        self.request_attempts+=1
        available={t['function']['name']:t for t in tools}
        required=json.loads(messages[1]['content'])['required_actions']
        action=next(k for k in ('read_requirement','read_model','read_changes','recheck_model','finish') if k in available and (k!='read_changes' or k in required))
        args={}
        if action=='finish':args={'evidence_ids':available[action]['function']['parameters']['properties']['evidence_ids']['items']['enum'],
            'summary':'The saved burnout altitude meets the declared criterion within this bounded vertical model. Check the thrust and specific impulse sources, atmosphere approximation and coefficient with an independent reference. Review grid agreement and the exact cutoff. Staging, steering, aeroheating, landing and hardware validity remain unassessed.'}
        return Turn({'role':'assistant','content':None,'tool_calls':[{'id':'flight-'+str(self.request_attempts),'type':'function','function':{'name':action,'arguments':json.dumps(args)}}]},{'prompt_tokens':10,'completion_tokens':10})


class PoweredFlightWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.addCleanup(self.tmp.cleanup)
        self.store=WorkspaceStore(Path(self.tmp.name)/'workspace.sqlite3')
        self.project=powered_flight_review();self.identity=self.project['project_id']
        independent=example_projects()['baseline']
        thermal=next(m for m in independent['models'] if m['id']=='thermal')
        self.project['models'].append(deepcopy(thermal))
        for key in thermal['inputs'].values():self.project['inputs'][key]=deepcopy(independent['inputs'][key])

    def run_reference(self):
        self.store.create_project(self.project)
        return self.store.run(self.identity,1)

    def test_saved_result_reload_report_and_coverage(self):
        v=self.run_reference();r=v['run']
        self.assertTrue(lifecycle.verify_review(r['review']))
        self.assertEqual(r['live_model_calls'],0)
        self.assertEqual(r['model_results']['vertical_flight']['flight_response'],r['review']['evidence']['vertical_flight']['flight_response'])
        with patch.object(powered_flight,'_integrate',side_effect=AssertionError('History must not integrate')):
            self.assertEqual(self.store.get(self.identity),v)
            profile=WorkspaceCoverage(self.store).summary(self.identity,1)
        self.assertTrue(profile['checks'])
        self.assertFalse(r['review']['launch_authorization'])

    def test_opening_existing_default_after_verifier_update_never_reruns(self):
        identity=self.store.ensure_default();before=self.store.get(identity,1)['run']['review']
        with patch.object(self.store,'_fresh',return_value=False),patch.object(self.store,'run',side_effect=AssertionError('Opening must not calculate')):
            self.assertEqual(self.store.ensure_default(),identity)
        self.assertEqual(self.store.get(identity,1)['run']['review'],before)

    def test_thrust_change_reruns_flight_reuses_thermal(self):
        old=self.run_reference();p=deepcopy(old['project']);p['inputs']['thrust']['value']=11000
        with patch.object(powered_flight,'evaluate',side_effect=AssertionError('Preview must not calculate')):
            impact=self.store.preview_change(self.identity,1,p)
        self.assertEqual(impact['affected_model_ids'],['vertical_flight'])
        self.store.save_revision(self.identity,1,p);new=self.store.run(self.identity,2)
        self.assertEqual(new['run']['executed_model_ids'],['vertical_flight'])
        self.assertEqual(new['run']['reused_model_ids'],['thermal'])
        self.assertEqual(new['run']['review']['findings']['burnout_height']['status'],'not_met')
        self.assertEqual(self.store.get(self.identity,1)['run']['review'],old['run']['review'])

    def test_limit_change_reuses_response_and_changes_finding(self):
        old=self.run_reference();p=deepcopy(old['project']);p['inputs']['maximum_dynamic_pressure']['value']=100
        self.store.save_revision(self.identity,1,p);new=self.store.run(self.identity,2)
        self.assertEqual(new['run']['executed_model_ids'],[])
        self.assertEqual(new['run']['model_results']['vertical_flight'],old['run']['model_results']['vertical_flight'])
        self.assertEqual(new['run']['review']['findings']['dynamic_pressure']['status'],'not_met')

    def test_grid_gap_propagates_through_scalar_chain(self):
        p=deepcopy(self.project);mount=next(m for m in example_projects()['baseline']['models'] if m['id']=='mount');base=example_projects()['baseline']
        mount=deepcopy(mount);mount['inputs'].pop('tip_force');mount['links']={'tip_force':dict(model_id='vertical_flight',metric='max_sampled_drag',unit='N',rationale='Constructed transverse tip load from sampled drag magnitude; no distributed or time-dependent loading implied.')}
        p['models'].append(mount)
        for key in mount['inputs'].values():p['inputs'][key]=deepcopy(base['inputs'][key])
        p['inputs']['steps']['value']=8;p['inputs']['altitude_numerical_tolerance']['value']=1e-12;p['inputs']['velocity_numerical_tolerance']['value']=1e-12;p['inputs']['relative_numerical_tolerance']['value']=0
        r=engineering.evaluate_models(p)
        self.assertEqual(r['mount']['status'],'not_assessed');self.assertEqual(r['mount']['metrics'],{})
        self.assertTrue(lifecycle.verify_review(lifecycle.review_project(p,r)))

    def test_scoped_assistant_projection_is_bounded_and_retains_cutoff(self):
        v=self.run_reference();record=v['run']['review']['evidence']['vertical_flight']
        full={'recorded_evidence':deepcopy(record)}
        projected=project_investigation._provider_evidence(full)
        result=projected['recorded_evidence'];self.assertNotIn('flight_response',result)
        summary=result['flight_summary_projection']
        self.assertLess(len(json.dumps(projected)),30000)
        self.assertIn('before_cutoff',{r['event'] for r in summary['witness_samples']})
        self.assertIn('after_cutoff',{r['event'] for r in summary['witness_samples']})
        self.assertIn('flight_response',full['recorded_evidence'])

    def test_scenarios_retain_baseline_and_bounded_work(self):
        v=self.run_reference();s=WorkspaceScenarios(self.store)
        study=s.run(self.identity,1,v['run']['run_id'],dict(schema='sixd.scenario-spec.v1',name='Thrust choices',source='Constructed inputs',mode='sweep',input_id='thrust',values=[20000,13000]))
        self.assertTrue(study)
        self.assertEqual(self.store.get(self.identity,1)['run']['review'],v['run']['review'])
        p=deepcopy(self.project);p['inputs']['steps']['value']=512
        with self.assertRaises(workspace.WorkspaceError):s._budget(p,[{'name':str(i),'changes':{'thrust':15000+i}} for i in range(10)],'Constructed')

    def test_scalar_observation_captures_compact_flight_accuracy(self):
        v=self.run_reference();tests=WorkspaceTestData(self.store)
        record=tests.run(self.identity,1,v['run']['run_id'],{
            'schema':'sixd.test-comparison-spec.v1','name':'Constructed flight observation',
            'source':'Synthetic observation, not measured hardware','data_kind':'synthetic',
            'test_conditions':'Declared same burnout-altitude observable; unverified conditions.',
            'conditions_match':'declared_match','filename':'flight.csv',
            'csv_text':'id,req,value,unit,tolerance\na,burnout_height,6100,m,50\n',
            'mapping':{'measurement_id':'id','requirement_id':'req','value':'value','unit':'unit','tolerance':'tolerance'}})
        link=TestEvidence(self.store,tests)
        context=link.investigation_context(self.identity,1,'burnout_height',record['receipt']['comparison_id'],2)
        self.assertIn('flight_response',context['recorded']['model'])
        self.assertNotIn('samples',context['recorded']['model']['flight_response'])
        self.assertEqual(record['receipt']['row_results'][0]['prediction_agreement']['status'],'within_tolerance')

    def test_catalog_contains_all_exact_flight_parameters(self):
        c=next(m for m in project_authoring.catalog()['models'] if m['type']=='powered_flight')
        self.assertEqual({x['name']:x['unit'] for x in c['parameters']},powered_flight.PARAMETERS)
        self.assertTrue(project_authoring.preflight(self.project)['can_run'])

    def test_offline_assistant_rechecks_selected_flight_and_cites_saved_evidence(self):
        v=self.run_reference();provider=OfflineFlightProvider()
        with patch.object(project_investigation,'evaluate_models',wraps=engineering.evaluate_models) as calc:
            r=project_investigation.investigate_project(v,'burnout_height','Explain this criterion.',provider,investigation_id='offline-flight')
        self.assertEqual(r['state'],'completed',r)
        self.assertEqual(r['live_model_calls'],0)
        self.assertEqual(calc.call_count,1)
        self.assertEqual([m['id'] for m in calc.call_args.args[0]['models']],['vertical_flight'])
        self.assertTrue(r['evidence']['recheck:vertical_flight']['matches_saved_result'])
        self.assertEqual(self.store.get(self.identity),v)

    def test_missing_solver_manifest_rejected_but_old_chain_manifest_retained(self):
        p=example_projects()['chain_review'];r=engineering.evaluate_models(p)
        sources={k:v for k,v in lifecycle._verification_sources().items() if k in lifecycle.CHAIN_VERIFICATION_SOURCE_NAMES}
        with patch.object(lifecycle,'_verification_sources',return_value=sources):old=lifecycle.review_project(p,r)
        self.assertTrue(lifecycle.verify_review(old))
        with patch.object(lifecycle,'_verification_sources',return_value=sources),self.assertRaises(ValueError):
            lifecycle.review_project(self.project,engineering.evaluate_models(self.project))


if __name__=='__main__':unittest.main()
