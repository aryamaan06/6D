"""Targeted Ultra service boundaries; every provider here is an offline fixture."""
from pathlib import Path
from http.client import HTTPConnection
import json,sys,tempfile,time,unittest,threading
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
from sixd.workspace_workflow_evaluation import UltraDiagnostic,WorkflowEvaluation
from sixd.workspace_ai import WorkspaceAI,_encode,_digest
from sixd.workspace import WorkspaceStore,WorkspaceError,ConflictError
from sixd.project_examples import example_projects
from sixd.workspace_server import create_server
from test_workspace_ai_api import KEY,offline_factory,write_offline_config


class UltraDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);write_offline_config(self.folder)
        self.store=WorkspaceStore(self.folder/'workspace.sqlite3')
        self.ai=WorkspaceAI(self.store,self.folder,provider_factory=offline_factory)
        self.old=WorkflowEvaluation(self.ai);self.service=UltraDiagnostic(self.ai)

    def case(self):
        project=example_projects()['orbital_review'];self.store.create_project(project)
        view=self.store.run(project['project_id'],1)
        return {'id':'orbit-met','view':view,'requirement_id':'orbit_max_radius','question':'Explain recorded evidence and the next independent check.'}

    def test_status_and_invalid_authorization_do_not_prepare_or_spend(self):
        self.assertIsNone(self.service.status()['latest'])
        with patch('sixd.workspace_workflow_evaluation.build_plan',side_effect=AssertionError('no preparation')):
            for amount,allow in [(3,True),(.5,False),(True,True),(float('nan'),True)]:
                with self.assertRaises(WorkspaceError):self.service.start(allowance_usd=amount,allow_spend=allow)
        self.assertFalse((self.folder/'budget.sqlite3').exists())

    def test_missing_private_connection_cannot_start_a_diagnostic(self):
        with patch('sixd.workspace_workflow_evaluation.build_plan',return_value={'cases':[{'id':'orbit-met'}]}):
            with self.assertRaises(ConflictError):self.service.start(allowance_usd=.5,allow_spend=True)
        self.assertIsNone(self.service.status()['latest'])
        self.assertFalse((self.folder/'budget.sqlite3').exists())

    def test_single_offline_case_preserves_comparison_selection_and_shared_budget(self):
        self.ai.connect(KEY);case=self.case()
        with patch('sixd.workspace_workflow_evaluation.build_plan',return_value={'cases':[case]}):
            started=self.service.start(allowance_usd=.5,allow_spend=True)
        end=time.monotonic()+15
        while time.monotonic()<end:
            record=self.service.get(started['comparison_id'])
            if record['state'] not in {'queued','running'}:break
            time.sleep(.02)
        self.assertEqual(record['state'],'completed',record)
        self.assertEqual(record['receipt']['provider_mode'],'offline_transport_fixture')
        self.assertEqual(record['receipt']['live_model_calls'],0)
        self.assertIn('Ultra',record['model'])
        self.assertLessEqual(record['request_reservations'],6)
        self.assertLessEqual(record['reserved_usd'],.35)
        self.assertFalse(record['active_model_changed'])
        self.assertEqual(self.store.get(case['view']['project_id'],1),case['view'])
        self.assertIsNone(self.old.status()['latest'])
        self.assertFalse((self.folder/'project-assistant-model.json').exists())
        self.assertNotIn(KEY,json.dumps(record))
        self.assertIsNone(self.ai._active)

    def test_restart_does_not_resume_or_replace_historical_comparisons(self):
        identity='d'*32
        record={'comparison_id':identity,'state':'running','created_at':'2026-10-20',
                'model':'constructed-offline-ultra','receipt':None,'reserved_usd':.1,'request_reservations':3}
        with self.ai._db() as db:
            db.execute('INSERT INTO ultra_diagnostics VALUES (?,?,?,?,?,?)',
                       (identity,'2026-10-20','running','old-owner',_encode(record),_digest(record)))
        restarted=UltraDiagnostic(self.ai);saved=restarted.get(identity)
        self.assertEqual(saved['state'],'interrupted');self.assertEqual(saved['reserved_usd'],.1)
        self.assertIsNone(self.old.status()['latest'])


class UltraDiagnosticAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.addCleanup(self.temp.cleanup)
        folder=Path(self.temp.name);write_offline_config(folder)
        self.server=create_server(port=0,db_path=folder/'workspace.sqlite3',provider_factory=offline_factory)
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown();self.server.server_close();self.worker.join()

    def request(self,path,body=None,headers=None):
        connection=HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        connection.request('GET' if body is None else 'POST',path,
                           body=None if body is None else json.dumps(body),
                           headers={'Content-Type':'application/json',**(headers or {})})
        response=connection.getresponse();status=response.status;data=json.loads(response.read());connection.close()
        return status,data

    def test_read_status_and_strict_start_fields_are_offline(self):
        status,data=self.request('/api/ultra-diagnostic/status')
        self.assertEqual(status,200);self.assertEqual(data['cap_usd'],.5);self.assertIsNone(data['latest'])
        self.assertEqual(self.request('/api/ultra-diagnostic/start',{'allow_spend':True,'allowance_usd':3})[0],400)
        self.assertEqual(self.request('/api/ultra-diagnostic/start',{'allow_spend':True,'allowance_usd':.5,'extra':True})[0],400)
        with patch('sixd.workspace_workflow_evaluation.build_plan',return_value={'cases':[{'id':'orbit-met'}]}):
            self.assertEqual(self.request('/api/ultra-diagnostic/start',{'allow_spend':True,'allowance_usd':.5})[0],409)
        self.assertIsNone(self.server.ultra_diagnostic.status()['latest'])
        self.assertIsNone(self.server.workflow_evaluation.status()['latest'])

    def test_origin_and_id_guards_prevent_start_and_private_access(self):
        self.assertEqual(self.request('/api/ultra-diagnostic/start',{'allow_spend':True,'allowance_usd':.5},
                                      {'Origin':'https://example.org'})[0],403)
        self.assertEqual(self.request('/api/ultra-diagnostic/runs/not-an-id')[0],400)
        self.assertIsNone(self.server.ai._active)


if __name__=='__main__':unittest.main()
