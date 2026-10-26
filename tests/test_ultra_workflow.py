"""Fresh Ultra screening preserves old proof and uses isolated constructed cases."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'),str(ROOT/'tests')]
from test_workspace_ai_api import offline_transport
from sixd.model_evaluation import CANDIDATES
from sixd.project_investigation import ProjectActionAdapter
from sixd.providers import BudgetLedger, LiveConfig, ProviderError, TokenFactoryProvider
from sixd.workspace import ConflictError, WorkspaceError, WorkspaceStore
from sixd.workspace_ai import WorkspaceAI, _digest, _encode
from sixd.workspace_evaluation import WorkspaceEvaluation
from sixd.workspace_ultra_workflow import (CAP_USD, MAX_REQUESTS, ULTRA,
    UltraWorkflow, build_plan, run_cases, scorecard, validate_plan)

KEY = 'synthetic-ultra-six-key-only'


class UltraWorkflowTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'work')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.config = LiveConfig('https://api.tokenfactory.nebius.com/v1/',
            'nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B','ultra-six-existing-approval',
            29.5,.06,.24,2048,45,'native_no_thinking','forced_action_v1')
        self.config_path = self.folder/'token-factory.json'
        self.config_path.write_text(json.dumps({**asdict(self.config),'account_verified':True,
            'model_license_reviewed':True,'spend_approved':True}),encoding='utf-8')
        self.original_config = self.config_path.read_bytes()
        self.store = WorkspaceStore(self.folder/'workspace.sqlite3')
        self.default = self.store.ensure_default()
        self.before = self.store.get(self.default,1)
        self.factories = []

        def factory(config,ledger,key):
            self.factories.append((config,ledger.max_reservation_usd,key))
            return TokenFactoryProvider(config,ledger,api_key=key,
                transport=offline_transport,action_adapter=ProjectActionAdapter())
        with patch.dict('os.environ',{'NEBIUS_API_KEY':''}):
            self.ai = WorkspaceAI(self.store,self.folder,provider_factory=factory)
        self.service = UltraWorkflow(self.ai)

    def await_screen(self,identity):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            value=self.service.get(identity)
            if value['state'] not in {'queued','running'}:
                while self.ai._active and time.monotonic()<deadline:time.sleep(.005)
                return value
            time.sleep(.01)
        self.fail('Offline Ultra workflow did not finish.')

    def test_prepare_status_are_free_and_pack_is_six_original_cases(self):
        self.assertIsNone(self.service.status()['latest'])
        prepared=self.service.prepare()
        self.assertEqual(prepared['live_calls'],0)
        self.assertTrue(prepared['capacity_preflight']['fits'])
        self.assertEqual(len(prepared['plan']['case_pack']['cases']),6)
        self.assertEqual(prepared['capacity_preflight']['max_request_reservations'],36)
        self.assertEqual(self.factories,[])
        self.assertFalse((self.folder/'budget.sqlite3').exists())
        self.assertEqual(self.config_path.read_bytes(),self.original_config)
        self.assertEqual(self.store.get(self.default,1),self.before)

    def test_tampered_candidate_settings_or_case_pack_is_rejected(self):
        plan=build_plan(temporary_root=self.folder/'cases')
        for change in ('candidate','settings','case'):
            bad=deepcopy(plan)
            if change=='candidate':bad['candidate']['id']='super'
            elif change=='settings':bad['settings']['max_output_tokens']=4096
            else:bad['case_pack']['cases'][0]['view']['project']['inputs']['heat_input']['value']=900
            bad['plan_digest']=_digest({k:v for k,v in bad.items() if k!='plan_digest'})
            with self.assertRaises(ValueError):validate_plan(bad)

    def test_all_six_share_approval_and_caps_without_owner_projects_or_default_changes(self):
        self.ai.connect(KEY)
        record=self.await_screen(self.service.start(allow_spend=True,allowance_usd=CAP_USD)['comparison_id'])
        self.assertEqual(record['state'],'completed')
        card=scorecard(record['report'])
        self.assertEqual((card['attempted'],card['completed'],card['workflow_passes'],card['not_run']),(6,6,6,0))
        self.assertEqual(len(self.factories),6)
        for config,cap,key in self.factories:
            self.assertEqual(config.model,ULTRA['model'])
            self.assertEqual(config.approval_id,self.config.approval_id)
            self.assertEqual(config.spend_cap_usd,29.5)
            self.assertEqual(cap,.35)
            self.assertEqual(key,KEY)
        self.assertLessEqual(record['request_reservations'],MAX_REQUESTS)
        self.assertLessEqual(record['reserved_usd'],CAP_USD)
        self.assertEqual(self.config_path.read_bytes(),self.original_config)
        self.assertEqual(self.store.list_projects(),[{'project_id':self.default,
            'created_at':self.store.list_projects()[0]['created_at'],'revision':1,
            'name':self.before['project']['name']}])
        self.assertEqual(self.store.get(self.default,1),self.before)
        self.assertEqual(self.ai._config(),self.config)
        self.assertTrue(self.service.status()['latest']['current_sources_match'])
        self.assertFalse(self.service.status()['automatic_model_selection'])
        self.assertAlmostEqual(self.ai._budget(self.config)['reserved_usd'],record['reserved_usd'])

    def test_explanation_failure_does_not_skip_other_independent_cases(self):
        plan=build_plan(temporary_root=self.folder/'cases')
        called=[]
        class Ledger:
            count=0;reserved=0.0
            def reserve(self,config,amount):self.count+=1;self.reserved+=amount
        def factory(candidate,case):
            from dataclasses import replace
            called.append(case['id'])
            config=replace(self.config,model=ULTRA['model'],input_usd_per_million_ceiling=1,
                output_usd_per_million_ceiling=3)
            def transport(request):
                result=offline_transport(request)
                payload=json.loads(request.data);menu=json.loads(payload['messages'][-1]['content'])
                call=result['choices'][0]['message']['tool_calls'][0]['function']
                args=json.loads(call['arguments'])
                if case['id']=='thermal-met' and args['action']=='finish':
                    args['summary']='This bounded review claims a fabricated thermal quantity of 12345 K.'
                    call['arguments']=json.dumps(args)
                return result
            return TokenFactoryProvider(config,Ledger(),api_key=KEY,transport=transport,action_adapter=ProjectActionAdapter())
        report=run_cases(plan,factory,mode='offline')
        self.assertEqual(len(called),6)
        self.assertEqual(report['rows'][0]['state'],'failed')
        self.assertEqual(report['rows'][0]['error_code'],'explanation_rejected')
        self.assertTrue(all(row['state']=='completed' for row in report['rows'][1:]))
        self.assertEqual(scorecard(report)['not_run'],0)

    def test_authentication_failure_stops_and_redacts_factory_text(self):
        plan=build_plan(temporary_root=self.folder/'cases')
        called=[]
        def rejected(candidate,case):
            called.append(case['id'])
            raise ProviderError('private-remote-text-must-not-escape',
                code='provider_transport_error',diagnostic={'http_status':401})
        report=run_cases(plan,rejected)
        self.assertEqual(len(called),1)
        self.assertEqual(scorecard(report)['failed'],1)
        self.assertEqual(scorecard(report)['not_run'],5)
        self.assertNotIn('private-remote-text',json.dumps(report))

    def test_start_needs_exact_authorisation_and_existing_capacity(self):
        for spend,amount in ((False,CAP_USD),(True,2),(True,'2.10'),(1,CAP_USD)):
            with self.assertRaises(WorkspaceError):self.service.start(allow_spend=spend,allowance_usd=amount)
        self.ai.connect(KEY)
        BudgetLedger(self.folder/'budget.sqlite3').reserve(self.config,29.0)
        with self.assertRaises(ConflictError):self.service.start(allow_spend=True,allowance_usd=CAP_USD)
        self.assertEqual(self.factories,[])
        self.assertIsNone(self.ai._active)

    def test_restart_marks_only_fresh_partial_screen_interrupted(self):
        identity='a'*32
        record={'comparison_id':identity,'state':'running','rows':[]}
        with self.ai._db() as db:
            db.execute(f'INSERT INTO {self.service.TABLE} VALUES (?,?,?,?,?,?)',
                (identity,'2026-10-16T00:00:00Z','running','older-owner',_encode(record),_digest(record)))
        recreated=UltraWorkflow(self.ai)
        self.assertEqual(recreated.get(identity)['state'],'interrupted')
        self.assertEqual(self.factories,[])

    def test_historical_status_distinguishes_failed_and_untested_without_rewriting(self):
        legacy=WorkspaceEvaluation(self.ai)
        identity='b'*32
        record={'comparison_id':identity,'state':'completed','created_at':'2026-10-16T00:00:00Z',
            'completed_at':'2026-10-16T00:01:00Z','plan':{'cases':[{}]*6,'candidates':deepcopy(list(CANDIDATES))},
            'rows':[{'candidate_id':'ultra','state':'completed','score':{'workflow_gate_pass':True}},
                    {'candidate_id':'ultra','state':'completed','score':{'workflow_gate_pass':True}},
                    {'candidate_id':'ultra','state':'failed','score':None}],
            'report':{'historical':True},'agent_sources':{'older':'source'}}
        encoded=_encode(record)
        with self.ai._db() as db:
            db.execute('INSERT INTO model_comparisons VALUES (?,?,?,?,?,?)',
                (identity,record['created_at'],'completed','old-owner',encoded,_digest(record)))
        status=legacy.status()['latest_comparison']
        ultra=next(row for row in status['candidate_results'] if row['candidate_id']=='ultra')
        self.assertEqual((ultra['workflow_passes'],ultra['attempted'],ultra['failed'],ultra['not_run']),(2,3,1,3))
        self.assertEqual(status['created_at'],record['created_at'])
        self.assertFalse(status['current_sources_match'])
        with self.ai._db() as db:
            self.assertEqual(db.execute('SELECT record FROM model_comparisons WHERE comparison_id=?',(identity,)).fetchone()[0],encoded)


if __name__=='__main__':unittest.main()
