"""Owner diagnostics stay private; visitor spend booleans preserve live limits."""
from contextlib import closing
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd.hosted_runtime import HostedRuntimeFactory
from sixd.hosted_server import HostedConfig, create_hosted_server
from sixd.providers import LiveConfig, ProviderError
from sixd.workspace_server import create_server

ORIGIN='https://owner-boundary.example.test'
CODE='synthetic-owner-boundary-invitation-code-only'
KEY='synthetic-owner-boundary-token-key-only'


class OwnerSettingsBoundaryTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'work').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work')
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.calls=[]
        self.config=LiveConfig('https://api.tokenfactory.nebius.com/v1/',
            'nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B','synthetic-owner-boundary-approval',
            5,.06,.24,2048,45,'native_no_thinking','forced_action_v1')
        prior=self.folder/'prior.sqlite3'
        with closing(sqlite3.connect(prior)) as db, db:
            db.execute('CREATE TABLE budget(id TEXT PRIMARY KEY,cap REAL,reserved REAL)')
            db.execute('INSERT INTO budget VALUES(?,?,?)',(self.config.approval_id,5,1.25))
        self.state=self.folder/'state'
        def forbidden(request):
            self.calls.append(request)
            raise AssertionError('No provider call is allowed during a boundary status check.')
        self.factory=HostedRuntimeFactory(self.state,config=self.config,api_key=KEY,
            prior_budget_path=prior,daily_cap_usd=.2,session_cap_usd=.1,transport=forbidden)
        self.host_config=HostedConfig(self.state,ORIGIN,CODE,max_sessions=4,
            get_limit=500,post_limit=100,login_limit=100)
        self.server=create_hosted_server(self.host_config,port=0,runtime_factory=self.factory)
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.worker.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown();self.server.server_close();self.worker.join(timeout=5)

    def request(self,path,body=None,*,cookie=None):
        headers={'Host':'owner-boundary.example.test'}
        if body is not None:headers.update({'Origin':ORIGIN,'Content-Type':'application/json'})
        if cookie:headers['Cookie']=cookie
        conn=HTTPConnection('127.0.0.1',self.server.server_port,timeout=20)
        try:
            conn.request('GET' if body is None else 'POST',path,
                None if body is None else json.dumps(body),headers)
            response=conn.getresponse();raw=response.read();metadata=dict(response.getheaders())
            self.assertNotIn(KEY.encode(),raw)
            self.assertNotIn(CODE.encode(),raw)
            value=json.loads(raw) if 'application/json' in metadata.get('Content-Type','') else raw
            return response.status,value,metadata
        finally:conn.close()

    def login(self):
        code,value,headers=self.request('/api/hosted/login',{'access_code':CODE})
        self.assertEqual(code,200,value)
        cookie=headers['Set-Cookie'].split(';',1)[0]
        token=cookie.split('=',1)[1]
        session=self.server.manager.session(token)
        return cookie,session

    def test_live_visitor_status_redacts_owner_accounting_and_keeps_all_models(self):
        cookie,session=self.login()
        code,status,_=self.request('/api/ai/status',cookie=cookie)
        self.assertEqual(code,200)
        self.assertTrue(status['configured'])
        self.assertTrue(status['spend_available'])
        self.assertFalse(status['owner_controls'])
        self.assertTrue(status['usage_managed'])
        self.assertEqual({r['id'] for r in status['available_models']},{'nano','super','ultra'})
        for key in ('budget','max_job_reservation_usd','key_source','key_remembered',
                'credential_error','environment_key_configured'):
            self.assertNotIn(key,status)
        for option in status['available_models']:
            self.assertNotIn('max_job_reservation_usd',option)
        code,hosted,_=self.request('/api/hosted/status',cookie=cookie)
        self.assertEqual(code,200)
        self.assertTrue(hosted['live_ai_enabled'])
        self.assertTrue(hosted['inference_available'])
        self.assertNotIn('inference_budget',hosted)
        self.assertNotIn('budget',hosted)
        for value in (status,hosted):
            encoded=json.dumps(value)
            self.assertNotIn(self.config.approval_id,encoded)
            self.assertNotIn('reserved_usd',encoded)
            self.assertNotIn('remaining_usd',encoded)
        self.assertEqual(self.calls,[])

    def test_session_then_day_exhaustion_changes_booleans_without_disabling_enforcement(self):
        cookie,session=self.login()
        self.factory.ledger.reserve(session['id'],self.config,.1)
        _,status,_=self.request('/api/ai/status',cookie=cookie)
        _,hosted,_=self.request('/api/hosted/status',cookie=cookie)
        self.assertFalse(status['spend_available'])
        self.assertFalse(hosted['inference_available'])
        runtime=self.server.manager.runtime(session)
        class Job:
            count=0
            def reserve(self,config,amount):self.count+=1
        job=Job();provider=runtime.ai._factory(self.config,job,KEY)
        with self.assertRaises(ProviderError):provider.ledger.reserve(self.config,.000001)
        self.assertEqual(job.count,0)
        second,session2=self.login()
        self.assertTrue(self.request('/api/ai/status',cookie=second)[1]['spend_available'])
        self.factory.ledger.reserve(session2['id'],self.config,.1)
        third,session3=self.login()
        self.assertFalse(self.request('/api/ai/status',cookie=third)[1]['spend_available'])
        self.assertFalse(self.request('/api/hosted/status',cookie=third)[1]['inference_available'])
        with self.assertRaises(ProviderError):self.factory.ledger.reserve(session3['id'],self.config,.000001)
        self.assertEqual(self.calls,[])

    def test_owner_diagnostics_and_new_ultra_actions_are_forbidden_to_visitors(self):
        cookie,_=self.login()
        paths=['/api/ai-quality/status','/api/model-evaluation/status',
            '/api/workflow-evaluation/status','/api/evidence-evaluation/status',
            '/api/ultra-diagnostic/status','/api/ultra-workflow/status',
            '/api/ultra-workflow/runs/'+'a'*32,'/api/observability/status']
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0],401)
                code,value,_=self.request(path,cookie=cookie)
                self.assertEqual(code,403,value)
        for path,body in [('/api/ultra-workflow/prepare',{}),
                ('/api/ultra-workflow/start',{'allow_spend':True,'allowance_usd':2.1}),
                ('/api/ai/connect',{'api_key':'synthetic-replacement-not-allowed'}),
                ('/api/shutdown',{})]:
            with self.subTest(path=path):
                self.assertEqual(self.request(path,body,cookie=cookie)[0],403)
        self.assertEqual(self.calls,[])

    def test_disabled_hosted_instance_reports_unavailable_without_owner_numbers(self):
        separate=HostedConfig(self.folder/'disabled',ORIGIN,CODE,get_limit=100,login_limit=20)
        server=create_hosted_server(separate,port=0)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        previous=self.server;self.server=server
        try:
            cookie,_=self.login()
            _,ai,_=self.request('/api/ai/status',cookie=cookie)
            _,hosted,_=self.request('/api/hosted/status',cookie=cookie)
            self.assertFalse(ai['configured']);self.assertFalse(ai['spend_available'])
            self.assertFalse(hosted['live_ai_enabled']);self.assertFalse(hosted['inference_available'])
            self.assertNotIn('inference_budget',hosted)
        finally:
            server.shutdown();server.server_close();worker.join(timeout=5);self.server=previous

    def test_owner_ultra_routes_are_wired_and_strict_without_paid_action(self):
        def forbidden(*args,**kwargs):raise AssertionError('Owner route test must remain offline.')
        server=create_server(port=0,db_path=self.folder/'owner.sqlite3',
            ai_local_directory=self.folder/'owner-private',provider_factory=forbidden)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        def request(path,body=None):
            headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:'+str(server.server_port)}
            conn=HTTPConnection('127.0.0.1',server.server_port,timeout=20)
            try:
                conn.request('GET' if body is None else 'POST',path,
                    None if body is None else json.dumps(body),headers)
                response=conn.getresponse();return response.status,json.loads(response.read())
            finally:conn.close()
        try:
            code,status=request('/api/ultra-workflow/status')
            self.assertEqual(code,200,status)
            self.assertEqual(status['case_count'],6)
            self.assertIsNone(status['latest'])
            self.assertEqual(request('/api/ultra-workflow/not-a-route')[0],404)
            self.assertEqual(request('/api/ultra-workflow/not-a-route',{})[0],404)
            self.assertEqual(request('/api/ultra-workflow/prepare',{'extra':True})[0],400)
            for body in ({'allow_spend':False,'allowance_usd':2.1},
                    {'allow_spend':True,'allowance_usd':2.1,'model':'other'},
                    {'allow_spend':True,'allowance_usd':2.1,'max_requests':100},
                    {'allow_spend':True,'allowance_usd':2.1,'api_key':KEY}):
                self.assertEqual(request('/api/ultra-workflow/start',body)[0],400)
            self.assertIsNone(server.ai._active)
            self.assertFalse((self.folder/'owner-private'/'budget.sqlite3').exists())
        finally:server.shutdown();server.server_close();worker.join(timeout=5)


if __name__=='__main__':unittest.main()
