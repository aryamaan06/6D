"""Stage/profile evidence stays bound to exact saved inputs and revisions."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import (staged_ascent,engineering,lifecycle,project_authoring,
                  project_investigation,evidence_roles,explanation_quality)
from sixd.project_examples import guided_ascent_review
from sixd.providers import Turn
from sixd.workspace import WorkspaceStore,WorkspaceError
from sixd.workspace_coverage import WorkspaceCoverage
from sixd.workspace_scenarios import WorkspaceScenarios
from sixd.workspace_test_data import WorkspaceTestData
from sixd.test_evidence import TestEvidence


def fixture():
    project=guided_ascent_review()
    project.update(project_id='constructed-staged-workspace',name='Constructed staged review',
        description='Constructed two-stage point mass with analytical throttle impulse and ideal zero-impulse dry-mass separation; no flight data or closed-loop launch GNC.')
    project['models']=[model for model in project['models'] if model['id']!='propulsion']
    project['requirements']=[row for row in project['requirements'] if row['model_id']!='propulsion']
    for system in project['systems']:
        if system['id']=='propulsion': system['model_ids']=[]
    values=dict(payload_mass=100.,reference_area=.8,drag_coefficient=.4,reference_density=.1,
                scale_height=8500.,gravitational_parameter=3.986004418e14,launch_radius=6371000.,
                coast_duration=20.,steps=16,position_numerical_tolerance=.5,
                velocity_numerical_tolerance=.02,relative_numerical_tolerance=1e-6,
                pitch_start_time=5.,pitch_end_time=60.,initial_pitch_angle=0.,final_pitch_angle=.35)
    for stage,dry,prop,isp,delay,segments in (
        (1,200.,300.,250.,2.,[(20.,16000.,12000.),(60.,12000.,14000.)]),
        (2,100.,100.,280.,0.,[(100.,8000.,6000.)]),
    ):
        prefix=f'stage.{stage}.'
        values.update({prefix+'dry_mass':dry,prefix+'propellant_mass':prop,
                       prefix+'specific_impulse':isp,prefix+'separation_delay':delay})
        for index,(duration,start,end) in enumerate(segments,1):
            row=prefix+f'segment.{index}.'
            values.update({row+'duration':duration,row+'thrust_start':start,row+'thrust_end':end})
    units=staged_ascent.parameter_units(values)
    bindings={key:'staged_'+key.replace('.','_') for key in values}
    for key,value in values.items():
        project['inputs'][bindings[key]]=dict(value=value,unit=units[key],
            source='Constructed profile/stack input; not measured hardware or flight data.')
    model=next(row for row in project['models'] if row['id']=='guided_flight')
    model.update(id='staged_flight',type='staged_ascent',inputs=bindings,
                 description='Variable-thrust stages with analytical fuel and ideal zero-impulse dry-mass jettison.')
    for row in project['models']:
        for link in row.get('links',{}).values():
            if link['model_id']=='guided_flight':link['model_id']='staged_flight'
    for row in project['requirements']:
        if row['model_id']=='guided_flight':row['model_id']='staged_flight'
    for row in project['systems']:
        row['model_ids']=['staged_flight' if identity=='guided_flight' else identity for identity in row['model_ids']]
    return project


class StagedProvider:
    mode='offline_transport_fixture'
    model='offline-staged-evidence-test'
    def __init__(self): self.request_attempts=0
    def complete(self,messages,tools):
        self.request_attempts+=1
        available={tool['function']['name']:tool for tool in tools}
        required=json.loads(messages[1]['content'])['required_actions']
        action=next(name for name in ('read_requirement','read_model','read_changes','recheck_model','finish')
                    if name in available and (name!='read_changes' or name in required))
        arguments={}
        if action=='finish':
            arguments=dict(evidence_ids=available[action]['function']['parameters']['properties']['evidence_ids']['items']['enum'],
                summary='The criterion is met within the declared staged point-mass model. Verify supplied thrust endpoints, durations, stage masses, specific impulse and atmosphere sources. Inspect analytical fuel exhaustion, retained separation and ignition event sides, and vector-state grid comparisons. Compare with an independent staged trajectory analysis. Dry-mass removal assumes no separation impulse; hardware separation, ignition reliability, attitude, closed-loop guidance, aeroheating and landing remain unassessed.')
        return Turn(dict(role='assistant',content=None,tool_calls=[dict(id='staged-'+str(self.request_attempts),type='function',
                    function=dict(name=action,arguments=json.dumps(arguments)))]),dict(prompt_tokens=10,completion_tokens=10))


class StagedAscentWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(dir=ROOT/'work');cls.addClassCleanup(cls.temporary.cleanup)
        cls.store=WorkspaceStore(Path(cls.temporary.name)/'workspace.sqlite3')
        cls.project=fixture();cls.identity=cls.project['project_id']
        cls.store.create_project(cls.project);cls.baseline=cls.store.run(cls.identity,1)
        draft=deepcopy(cls.baseline['project'])
        draft['inputs']['staged_stage_1_segment_2_thrust_end']['value']=9000.
        with patch.object(staged_ascent,'evaluate',side_effect=AssertionError('Preview cannot execute')):
            cls.impact=cls.store.preview_change(cls.identity,1,draft)
        cls.saved=cls.store.save_revision(cls.identity,1,draft)
        cls.revised=cls.store.run(cls.identity,2)

    def test_saved_mass_event_scope_and_unassessed_launch_gnc(self):
        review=self.baseline['run']['review'];self.assertTrue(lifecycle.verify_review(review))
        evidence=review['evidence']['staged_flight'];self.assertEqual(evidence['status'],'completed')
        artifact=evidence['staged_response'];self.assertEqual(artifact['frame']['id'],'body_centered_inertial_plane')
        metrics=evidence['metrics'];self.assertEqual(metrics['initial_mass']['value'],800.)
        self.assertEqual(metrics['final_mass']['value'],200.)
        self.assertEqual(metrics['propellant_consumed']['value'],400.)
        self.assertEqual(metrics['jettisoned_mass']['value'],200.)
        self.assertEqual(review['findings']['launch_guidance']['status'],'not_assessed')
        self.assertFalse(review['launch_authorization']);self.assertEqual(self.baseline['run']['live_model_calls'],0)

    def test_profile_edit_recomputes_transitive_chain_and_equals_full(self):
        self.assertEqual(set(self.impact['affected_model_ids']),{'staged_flight','atmospheric_load','mount'})
        self.assertIsNone(self.saved['run']);run=self.revised['run']
        self.assertEqual(set(run['executed_model_ids']),{'staged_flight','atmospheric_load','mount'})
        self.assertIn('thermal',run['reused_model_ids'])
        self.assertEqual(run['model_origins']['thermal']['run_id'],self.baseline['run']['run_id'])
        full=lifecycle.review_project(self.revised['project'],engineering.evaluate_models(self.revised['project']))
        self.assertEqual(run['review'],full)
        self.assertEqual(self.store.get(self.identity,1)['run']['review'],self.baseline['run']['review'])
        self.assertNotEqual(run['model_results']['staged_flight']['metrics']['burn_duration'],
                            self.baseline['run']['model_results']['staged_flight']['metrics']['burn_duration'])

    def test_reading_history_never_integrates_or_borrows_new_evidence(self):
        with patch.object(staged_ascent,'evaluate',side_effect=AssertionError('History cannot execute')):
            self.assertEqual(self.store.get(self.identity,1)['run']['review'],self.baseline['run']['review'])
            self.assertEqual(self.store.get(self.identity,2)['run']['review'],self.revised['run']['review'])

    def test_catalog_preflight_profiles_units_and_coverage_are_explicit(self):
        catalog=next(row for row in project_authoring.catalog()['models'] if row['type']=='staged_ascent')
        self.assertEqual(catalog['profile']['editor'],'staged_ascent')
        with patch.object(staged_ascent,'evaluate',side_effect=AssertionError('Preflight cannot execute')):
            self.assertTrue(project_authoring.preflight(self.project)['can_run'])
            coverage=WorkspaceCoverage(self.store).summary(self.identity,1)
        row=next(row for row in coverage['checks'] if row['requirement_id']=='burnout_height')
        self.assertEqual(row['discipline'],'Flight dynamics');self.assertEqual(row['coverage_status'],'applicability_unknown')
        malformed=fixture();model=next(row for row in malformed['models'] if row['id']=='staged_flight')
        del model['inputs']['stage.1.segment.2.thrust_end']
        self.assertFalse(project_authoring.preflight(malformed)['can_run'])
        mismatch=fixture();mismatch['inputs']['staged_stage_2_propellant_mass']['unit']='N'
        issues=project_authoring.preflight(mismatch)['issues'];self.assertTrue(any(row['code']=='input_unit_mismatch' for row in issues))

    def test_missing_vector_support_blocks_linked_load_and_structure(self):
        p=fixture()
        for key,value in dict(steps=8,position_numerical_tolerance=1e-12,velocity_numerical_tolerance=1e-12,relative_numerical_tolerance=0).items():
            p['inputs']['staged_'+key]['value']=value
        results=engineering.evaluate_models(p);self.assertEqual(results['staged_flight']['status'],'completed')
        self.assertIsNotNone(engineering.evidence_accuracy_gap(results['staged_flight']))
        for identity in ('atmospheric_load','mount'):
            self.assertEqual(results[identity]['status'],'not_assessed');self.assertEqual(results[identity]['metrics'],{})
        review=lifecycle.review_project(p,results);self.assertEqual(review['findings']['burnout_height']['status'],'not_assessed')
        guidance=json.dumps(explanation_quality.build_guidance(p,review,'burnout_height'))
        self.assertIn('staged',guidance);self.assertNotIn('resolve_orbital_accuracy',guidance)

    def test_numerical_allowance_blocks_near_criterion_and_exact_mass_remains_algebraic(self):
        p=deepcopy(self.baseline['project']);results=deepcopy(self.baseline['run']['model_results'])
        p['inputs']['minimum_burnout_altitude']['value']=results['staged_flight']['metrics']['burnout_altitude']['value']
        review=lifecycle.review_project(p,results);self.assertEqual(review['findings']['burnout_height']['status'],'not_assessed')
        r=results['staged_flight'];self.assertEqual(staged_ascent.metric_allowance(r['staged_response'],'jettisoned_mass'),0.)
        self.assertIsNone(engineering.requirement_accuracy_gap(r,dict(metric='jettisoned_mass',operator='=='),
                                                              r['metrics']['jettisoned_mass'],dict(value=200.,unit='kg')))

    def test_retained_stage_mass_tampering_cannot_receive_valid_review(self):
        results=deepcopy(self.baseline['run']['model_results'])
        artifact=results['staged_flight']['staged_response']
        event=next(row for row in artifact['samples'] if row['event']=='separation_after')
        event['mass_kg']+=1.
        with self.assertRaises(ValueError):lifecycle.review_project(self.baseline['project'],results)

    def test_previous_guided_manifest_stays_readable_but_cannot_validate_staged(self):
        guided=guided_ascent_review();results=engineering.evaluate_models(guided)
        sources={key:value for key,value in lifecycle._verification_sources().items()
                 if key in lifecycle.GUIDED_ASCENT_VERIFICATION_SOURCE_NAMES}
        with patch.object(lifecycle,'_verification_sources',return_value=sources):
            old=lifecycle.review_project(guided,results)
        self.assertTrue(lifecycle.verify_review(old))
        with patch.object(lifecycle,'_verification_sources',return_value=sources),self.assertRaises(ValueError):
            lifecycle.review_project(self.baseline['project'],self.baseline['run']['model_results'])

    def test_provider_projection_keeps_stage_mass_and_event_witnesses_without_grids(self):
        full=dict(recorded_evidence=deepcopy(self.baseline['run']['review']['evidence']['staged_flight']))
        projected=project_investigation._provider_evidence(full);result=projected['recorded_evidence']
        self.assertNotIn('staged_response',result);self.assertIn('staged_response',full['recorded_evidence'])
        summary=result['staged_summary_projection'];self.assertEqual(len(summary['solver']['stage_plan']),2)
        events={row['event'] for row in summary['witness_samples']}
        self.assertTrue({'separation_before','separation_after','ignition_after','stage_burnout_after'}<=events)
        self.assertNotIn('refinement',summary);self.assertLessEqual(len(summary['witness_samples']),32)
        self.assertLess(len(json.dumps(projected)),70000)

    def test_scenario_budget_counts_all_profiles_and_events(self):
        p=fixture();p['inputs']['staged_steps']['value']=128
        cases=[dict(name='profile '+str(i),changes={'staged_stage_1_segment_2_thrust_end':10000.+i}) for i in range(2)]
        with self.assertRaises(WorkspaceError):WorkspaceScenarios._budget(p,cases,'Constructed work bound')

    def test_test_observation_projects_scalar_staged_accuracy(self):
        tests=WorkspaceTestData(self.store);run=self.baseline['run']
        predicted=run['model_results']['staged_flight']['metrics']['burnout_altitude']['value']
        record=tests.run(self.identity,1,run['run_id'],dict(schema='sixd.test-comparison-spec.v1',
            name='Constructed staged observation',source='Synthetic observation, not flight data',data_kind='synthetic',
            test_conditions='Declared same final-stage burnout observable; conditions unverified.',conditions_match='declared_match',
            filename='staged.csv',csv_text=f'id,req,value,unit,tolerance\na,burnout_height,{predicted},m,50\n',
            mapping=dict(measurement_id='id',requirement_id='req',value='value',unit='unit',tolerance='tolerance')))
        context=TestEvidence(self.store,tests).investigation_context(self.identity,1,'burnout_height',record['receipt']['comparison_id'],2)
        self.assertIn('staged_response',context['recorded']['model']);self.assertNotIn('samples',context['recorded']['model']['staged_response'])
        self.assertEqual(record['receipt']['row_results'][0]['prediction_agreement']['status'],'within_tolerance')

    def test_offline_assistant_uses_mass_roles_and_one_reproducibility_check(self):
        provider=StagedProvider()
        with patch.object(project_investigation,'evaluate_models',wraps=engineering.evaluate_models) as calculate:
            result=project_investigation.investigate_project(self.baseline,'burnout_height','Explain staged evidence.',provider,investigation_id='offline-staged')
        self.assertEqual(result['state'],'completed',result);self.assertEqual(result['live_model_calls'],0)
        self.assertEqual(calculate.call_count,1);self.assertTrue(result['evidence']['recheck:staged_flight']['matches_saved_result'])
        roles={row['role'] for row in result['evidence_roles']['roles']}
        self.assertIn('position_grid_tolerance',roles);self.assertIn('velocity_difference_middle_to_fine',roles)
        self.assertIn('stage_1_post_separation_mass',roles)
        self.assertEqual(evidence_roles.evaluate_roles(result)['flags'],[])


if __name__=='__main__':unittest.main()
